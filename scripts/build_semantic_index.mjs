#!/usr/bin/env node
/**
 * P1 语义层 —— 构建时预计算本地向量索引（零外发 / 零成本 / 零依赖）
 * ─────────────────────────────────────────────────────────────────────────
 * 为什么是「哈希 TF-IDF」而不是 transformer embedding：
 *
 *   本机环境约束（实测）：
 *     - 无 NVIDIA GPU（Radeon 8060S 仅 ~4.2GB 共享显存，torch.cuda 不可用）；
 *     - Ollama 仅装了 qwen3.8（chat），无任何 embedding 模型；
 *     - HuggingFace 在中国网络不可达（http=000），无法下载 all-MiniLM 等权重。
 *
 *   任何「真 embedding」路线在本环境都跑不起来。而项目纪律禁止「假绿」：
 *   不能为了"像有语义层"去调一个会超时/失败的云 API，更不能把不可达的
 *   模型调用伪装成"已索引"。
 *
 *   故采用**纯 JS 离线哈希向量器**（hashing TF-IDF）：
 *     - 构建时（本机 Node）对 708 主库 + 142 贡献层实体，从其 name/type/
 *       applications/protocol/interface/standard 等字段合成文档，做
 *       中英文 token 化（英文词 + 中文 uni/bi-gram）→ 哈希到固定维 →
 *       TF-IDF 加权 → L2 归一，写入静态资产 api/semantic_index.json。
 *     - 运行时（Cloudflare Worker）纯 JS 余弦检索，不引任何模型、不发任何网络。
 *
 *   它本质是**词法-语义**相似（共享术语越多越相似），不是深层语义向量；
 *   但它是真实、可用、零依赖的语义信号，且接口与"真 embedding"完全一致 ——
 *   一旦本机装上 Ollama embedding 模型（nomic-embed-text 等），只需替换
 *   `vectorizeDocument` 一个函数即可升级，索引格式（ids/vectors）无需变。
 *
 * 诚实边界：语义相似 ≠ 兼容性。本索引只用于「发现语义相近的零件」与
 * 「在硬维度无证据时给出候选」，绝不把它写进 compatibility 裁决分数
 * （那会制造假绿）。详见 functions/_lib/compat_engine.js 的 semantic_hint。
 *
 * 用法：node scripts/build_semantic_index.mjs
 * 输出：api/semantic_index.json  { dim, idf, ids, names, vectors }
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url)) + '/..';
const DIM = 256;            // 向量维度（权衡：850 实体 × 256 ≈ 1.7MB JSON，检索 O(850×256) 可忽略）
const CJK = /[一-鿿]/g;     // 中日韩统一表意文字
const EN = /[a-z0-9][a-z0-9.+#-]*/g;

/** 稳定字符串哈希（FNV-1a 变体）→ 落在 [0, DIM)。 */
function hashDim(s) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h % DIM;
}

/**
 * 中英文 token 化：
 *   - 英文/数字：小写词（保留 + . # -，便于 ethernet/can-bus 之类）。
 *   - 中文：逐字 uni-gram + 相邻 bi-gram（无分词器下的合理词法近似）。
 * 返回 token 数组（含重复，供 TF 计数）。
 */
function tokenize(text) {
  if (!text) return [];
  const t = String(text).toLowerCase();
  const toks = [];
  const en = t.match(EN);
  if (en) for (const w of en) if (w.length >= 2) toks.push(w);
  const cjkRuns = t.match(CJK);
  if (cjkRuns) {
    for (const run of cjkRuns) {
      const chars = run.split('');
      for (const c of chars) toks.push('c:' + c);          // uni-gram
      for (let i = 0; i < chars.length - 1; i++) toks.push('b:' + chars[i] + chars[i + 1]); // bi-gram
    }
  }
  return toks;
}

/** 合成单实体文档文本。 */
function entityDoc(e) {
  return [
    e.name, e.name_en, e.manufacturer, e.type,
    Array.isArray(e.applications) ? e.applications.join(' ') : (e.applications || ''),
    e.protocol, e.interface, e.category,
    typeof e.standard_conformance === 'string' ? e.standard_conformance
      : JSON.stringify(e.standard_conformance || ''),
    e.mechanical_interface && e.mechanical_interface.standard,
    e.voltage, e.source_tier,
  ].filter(Boolean).join(' ');
}

function loadEntities() {
  const out = [];
  for (const f of ['api/entities.json', 'api/entities.contrib.json']) {
    const p = path.join(ROOT, f);
    if (!fs.existsSync(p)) continue;
    const d = JSON.parse(fs.readFileSync(p, 'utf8'));
    const arr = d.entities || [];
    for (const e of arr) {
      // 市场情报 / 企业主体不进"零件语义检索"池
      if (e.entity_kind === 'market_intelligence' || e.entity_kind === 'organization') continue;
      if (!e.id) continue;
      out.push(e);
    }
  }
  return out;
}

function main() {
  const entities = loadEntities();
  if (!entities.length) { console.error('无实体可索引'); process.exit(1); }

  // 1) 逐实体 token 化，统计 df（文档频率）
  const docs = entities.map((e) => {
    const toks = tokenize(entityDoc(e));
    const tf = new Map();
    for (const tk of toks) tf.set(tk, (tf.get(tk) || 0) + 1);
    return { id: e.id, name: e.name || e.id, tf };
  });
  const df = new Map();
  for (const d of docs) for (const tk of d.tf.keys()) df.set(tk, (df.get(tk) || 0) + 1);

  const N = docs.length;
  const idf = {};
  for (const [tk, f] of df) idf[tk] = Math.log((N + 1) / (f + 1)) + 1; // 平滑 IDF

  // 2) TF-IDF → 哈希向量 → L2 归一
  const vectors = [];
  const ids = [];
  const names = [];
  for (const d of docs) {
    const vec = new Float64Array(DIM);
    for (const [tk, cnt] of d.tf) {
      const dim = hashDim(tk);
      vec[dim] += cnt * (idf[tk] || 1);
    }
    // L2 归一
    let norm = 0;
    for (let i = 0; i < DIM; i++) norm += vec[i] * vec[i];
    norm = Math.sqrt(norm) || 1;
    const row = [];
    for (let i = 0; i < DIM; i++) row.push(Math.round((vec[i] / norm) * 1e5) / 1e5);
    vectors.push(row);
    ids.push(d.id);
    names.push(d.name);
  }

  // 注意：不写入 generated_at。语义索引是 entities.json 的纯派生物，新鲜度由 deploy 0b4
  // 每次部署重建保证；若写入时间戳，每次部署都会造成 1 行级差异、工作树持续脏，且毫无
  // 诊断价值（时间戳只表示"何时跑的脚本"，不代表"与真相源是否一致"——一致性由
  // ci_gate 的 gate_semantic_index_covers_entities 判定）。故仅保留派生内容本身。
  const payload = { dim: DIM, idf, ids, names, vectors };
  const outPath = path.join(ROOT, 'api/semantic_index.json');
  fs.writeFileSync(outPath, JSON.stringify(payload), 'utf8');

  const mb = (fs.statSync(outPath).size / 1024 / 1024).toFixed(2);
  console.log(`✅ 语义索引已生成: ${entities.length} 实体 × ${DIM} 维, ${Object.keys(idf).length} 词表, ${mb} MB → ${path.relative(ROOT, outPath)}`);
}

main();
