/**
 * cross_engine_probe.mjs —— JS 侧跨引擎探针（P2-8 · 第一阶段）
 *
 * 对 compatibility-golden.json 的每个 case，用产品面引擎 judgePair(a,b) 裁决，
 * 输出精简 JSON（pair / overall / dimensions 的 compatible+relation）到 stdout，
 * 供 verify_cross_engine.py 消费（与 Python compose 侧做跨引擎比对）。
 *
 * 设计纪律：
 *  - 纯只读，不写任何文件，不发起网络（与 eval_compat.mjs 同源纪律）
 *  - 输出 JSON 数组到 stdout；退出码 0 = 正常完成
 *  - 输入契约：judgePair 吃完整 entity 对象（voltage/protocol/interface/mechanical_interface/entity_kind/source_tier）
 *
 * 用法：node scripts/cross_engine_probe.mjs > /tmp/probe_js.json
 */
import { readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { judgePair } from '../functions/_lib/compat_engine.js';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const ents = JSON.parse(readFileSync(join(ROOT, 'api', 'entities.json'), 'utf8')).entities;
const golden = JSON.parse(readFileSync(join(ROOT, 'api', 'eval', 'compatibility-golden.json'), 'utf8')).cases;

const byId = new Map(ents.map((e) => [e.id, e]));
const out = [];

for (const c of golden) {
  const a = byId.get(c.component1_id);
  const b = byId.get(c.component2_id);
  if (!a || !b) continue;
  let r;
  try {
    r = judgePair(a, b);
  } catch (e) {
    out.push({ id: c.id, pair: [c.component1_id, c.component2_id], crash: e.message.slice(0, 120) });
    continue;
  }
  out.push({
    id: c.id,
    pair: [c.component1_id, c.component2_id],
    overall: r.overall_compatible,
    applicable: r.applicable,
    dimensions: Object.fromEntries(
      r.dimensions.map((d) => [
        d.dimension,
        { compatible: d.compatible, score: d.score, relation: d.relation || null },
      ])
    ),
  });
}

console.log(JSON.stringify(out));
