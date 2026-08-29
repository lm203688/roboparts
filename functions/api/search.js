/**
 * 关键词检索端点 —— GET /api/search?q=keyword
 *
 * 【20260808-11 为什么现在才有这个文件】
 * 这不是新功能，是**补上一个已经对外宣称了很久、但线上一直 404 的承诺**。
 * 修复前实测：
 *   - `index.html` 的 schema.org `SearchAction` 把 `https://roboparts.cc/api/search?q={q}`
 *     声明为本站检索入口 —— 这是**机器可读**的，搜索引擎与 AI agent 会照此发起请求；
 *   - `llms.txt:160` 与 `README.md:67` 同样列出 `GET /api/search?q=keyword — 搜索`；
 *   - 而 `functions/api/` 下没有 search.js、`api/` 下也没有 search.json，
 *     线上返回 catch-all 兜底的 404。
 * 属本仓反复出现的"口径 ≠ 事实"型缺陷：对外宣称的东西敲不开。
 * 修法只有一条正路 —— 把承诺兑现，而不是把承诺删掉（SearchAction 是 GEO 入口，
 * 删掉等于主动放弃一个 agent 发现通道）。
 *
 * ── 几条刻意的设计决定 ────────────────────────────────────────────────────
 * 1) **失败绝不返回空列表。** 数据加载失败一律 503。空结果集与"没搜到"在 JSON 上
 *    长得一模一样，调用方会把系统故障当成"库里没有这个零件"—— 假阴性比报错有害。
 * 2) **quarantine 默认排除，但必须把排除条数说出来。** 本库 99 条标记 quarantine=true
 *    （占位 ID / 无法核实的厂商 / 重复 / 把行业词当零件）。检索是"推荐面"而非"全量导出面"，
 *    与 MCP 选型保持一致默认排除；但静默排除就成了另一种失真，故在 meta 里报明条数，
 *    并提供 `include_quarantine=1` 让调用方自行取回。
 * 3) **付费字段不进检索命中域，也不出现在结果里。** 检索是发现面，
 *    命中理由若来自 price_range/compatibility 这类付费字段，等于绕开付费墙泄露内容。
 * 4) **结果用白名单投影而非黑名单剔除。** 日后实体上新增字段时，
 *    白名单不会"默认放行"一个本该收费的新字段。
 * 5) **非法 category 报 400，不返回空。** 静默空结果会让调用方以为"该品类下无匹配"。
 */

import { loadEntityMap } from '../_lib/compat_engine.js';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Content-Type': 'application/json; charset=utf-8',
  'Cache-Control': 'public, max-age=300',
};

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj, null, 2), { status, headers: corsHeaders });

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

// Pages 不会把 HEAD 自动映射到 GET；不导出就是 404，
// 而目录站/健康检查恰恰爱用 HEAD 探活 —— 等于对它们宣告本端点已下线。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}

/* ── 命中域与权重 ──────────────────────────────────────────────────────────
 * 权重表达的是"命中这个字段说明相关性有多强"，不是数据可信度。
 * 注意此处**不含任何付费字段**（见文件头第 3 条）。 */
const FIELD_WEIGHTS = [
  { fields: ['id'], weight: 40 },
  { fields: ['name', 'name_en', 'codename'], weight: 30 },
  { fields: ['manufacturer', 'manufacturer_en', 'vendor', 'company'], weight: 20 },
  { fields: ['type', 'type_en', 'category', 'form_factor'], weight: 15 },
  { fields: ['applications', 'application', 'application_en', 'interface',
             'interfaces', 'protocol', 'key_features', 'features',
             'bionic_features'], weight: 10 },
  { fields: ['description', 'description_en', 'specs', 'key_findings'], weight: 5 },
];

/** 把任意字段值摊平成可检索文本（数组/对象都吃）。 */
function flatten(v) {
  if (v == null) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (Array.isArray(v)) return v.map(flatten).join(' ');
  if (typeof v === 'object') return Object.values(v).map(flatten).join(' ');
  return '';
}

/** 结果白名单：只放发现所需的字段，深度数据引导到 /api/entity/{id} 与 entities.json。 */
function project(e) {
  const out = {};
  for (const k of ['id', 'name', 'name_en', 'category', 'manufacturer',
                   'type', 'entity_kind', 'data_quality', 'source_tier',
                   'quarantine', 'verified']) {
    if (e[k] !== undefined) out[k] = e[k];
  }
  return out;
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  const q = (url.searchParams.get('q') || '').trim();
  const category = (url.searchParams.get('category') || '').trim().toLowerCase();
  const includeQ = ['1', 'true', 'yes'].includes(
    (url.searchParams.get('include_quarantine') || '').toLowerCase());
  let limit = parseInt(url.searchParams.get('limit') || '20', 10);
  if (!Number.isFinite(limit) || limit < 1) limit = 20;
  limit = Math.min(limit, 100);

  if (!q) {
    return json({
      error: 'missing_query',
      message: '缺少查询词。用法：GET /api/search?q=keyword',
      parameters: {
        q: '必填，关键词。多个词以空格分隔，按「全部命中」(AND) 匹配',
        category: '选填，限定品类',
        limit: '选填，返回条数，默认 20，上限 100',
        include_quarantine: '选填，=1 时把已隔离的可疑条目一并返回',
      },
      example: 'https://roboparts.cc/api/search?q=harmonic%20drive&limit=10',
    }, 400);
  }

  // ── 取数：失败即 503，不降级为空结果 ──────────────────────────────────
  let list;
  try {
    const map = await loadEntityMap(env, request);
    list = Object.values(map);
  } catch (err) {
    return json({
      error: 'dataset_unavailable',
      message: '实体库暂时不可用，本次检索未执行。这是服务故障，不代表库中没有匹配项。',
      detail: String(err && err.message || err),
    }, 503);
  }

  const totalIndexed = list.length;
  const categories = [...new Set(list.map(e => e.category).filter(Boolean))].sort();

  if (category && !categories.includes(category)) {
    return json({
      error: 'unknown_category',
      message: `品类 "${category}" 不存在。返回空结果会让你误以为该品类下无匹配，故报错。`,
      valid_categories: categories,
    }, 400);
  }

  // ── 过滤 ────────────────────────────────────────────────────────────────
  // 注意这里**不预先剔除 quarantine**：先对全量打分，再按 quarantine 拆分。
  // 【首版自查修正】初版是先剔除再打分，于是 meta 只能报出"全库有 99 条被隔离"。
  // 但调用方看到 `matched:15 / quarantine_excluded:99` 会读成"还有 99 条命中被藏了"——
  // 事实是这 99 条里绝大多数与本次查询毫不相干。报一个真数字却给出假印象，
  // 与本仓一直在修的"口径 ≠ 事实"是同一种病。改为报**真正被扣下的命中数**。
  const pool = category ? list.filter(e => e.category === category) : list;
  const quarantineInIndex = pool.filter(e => e.quarantine === true).length;

  // ── 打分：多词 AND，每词取其命中的最高权重字段 ──────────────────────────
  const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
  const scored = [];
  for (const e of pool) {
    // 预摊平：字段名 -> 小写文本
    const text = {};
    for (const group of FIELD_WEIGHTS) {
      for (const f of group.fields) {
        if (e[f] !== undefined) text[f] = flatten(e[f]).toLowerCase();
      }
    }
    let score = 0;
    const matched = new Set();
    let allTermsHit = true;
    for (const t of terms) {
      let best = 0;
      let bestField = null;
      for (const group of FIELD_WEIGHTS) {
        for (const f of group.fields) {
          const hay = text[f];
          if (!hay || !hay.includes(t)) continue;
          // id 完全相等时额外加权：精确 ID 查询应当排第一
          const w = (f === 'id' && hay === t) ? group.weight * 3 : group.weight;
          if (w > best) { best = w; bestField = f; }
        }
      }
      if (best === 0) { allTermsHit = false; break; }
      score += best;
      matched.add(bestField);
    }
    if (!allTermsHit) continue;
    scored.push({ e, score, matched: [...matched] });
  }

  // 同分时按 id 稳定排序，保证同一查询多次调用结果一致
  scored.sort((a, b) => b.score - a.score || String(a.e.id).localeCompare(String(b.e.id)));

  // 命中里有多少条是隔离条目 —— 这才是"因隔离而没给你看"的真实数量
  const hiddenMatched = scored.filter(s => s.e.quarantine === true).length;
  const visible = includeQ ? scored : scored.filter(s => s.e.quarantine !== true);

  const results = visible.slice(0, limit).map(s => ({
    ...project(s.e),
    relevance_score: s.score,
    matched_fields: s.matched,
    detail_url: `/api/entity/${encodeURIComponent(s.e.id)}`,
  }));

  return json({
    query: { q, category: category || null, limit, include_quarantine: includeQ },
    meta: {
      total_indexed: totalIndexed,
      searched_in: category ? `category=${category}` : 'all_categories',
      matched: visible.length,
      returned: results.length,
      // 刻意区分这两个数：前者是"本次查询里被扣下的命中"，后者是"检索范围内的隔离总量"。
      // 只报后者会让人以为有一大批相关结果被藏起来了。
      quarantine_matched_withheld: includeQ ? 0 : hiddenMatched,
      quarantine_in_index: quarantineInIndex,
      ranking: '按字段加权的子串命中数排序（id > 名称 > 厂商 > 类型 > 应用/接口 > 描述）；'
             + '多个查询词按全部命中(AND)匹配。这是字面匹配，不是语义检索。',
      not_searched: '价格/兼容性/置信度/来源/合规/国产化率等付费字段不参与匹配，也不在结果中返回；'
                  + '完整字段见 /api/entities.json（需 API Key）。',
      caveat: '命中即相关的字面匹配结果，不构成选型建议，也不构成兼容性结论。'
            + '兼容性判定请用 POST /api/compatibility。',
    },
    results,
  });
}
