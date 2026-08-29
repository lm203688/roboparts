/**
 * P1 推荐流水线本地验证：用真实 entities.json 构建 map，跑 buildRecommender。
 * 断言：
 *  1) Source 召回同类/同接口族候选；
 *  2) Filter 剔除硬冲突（overall_compatible===false 不出现）；
 *  3) Rank 兼容(score!=null)排前、未定(score==null)排后，且类内降序；
 *  4) 输出带 score_basis（与 compat_engine 同源，未重写裁决）；
 *  5) 不存在 ID 返回 error。
 */
import { buildRecommender } from '../functions/_lib/recommender.js';
import { judgePair } from '../functions/_lib/compat_engine.js';
import { readFileSync } from 'node:fs';

const d = JSON.parse(readFileSync('api/entities.json', 'utf8'));
const map = {};
for (const e of (d.entities || d.data || [])) map[e.id] = e;
const rec = buildRecommender();

let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; } else { fail++; console.log('  ❌ ' + m); } };

// 动态选有代表性的目标 ID：每类取首个，跨 3 类以上
const byCat = {};
for (const e of (d.entities || d.data || [])) (byCat[e.category] ||= []).push(e.id);
const targets = [];
for (const cat of ['actuators', 'sensors', 'connectors', 'controllers', 'chips']) {
  if (byCat[cat] && byCat[cat][0]) targets.push(byCat[cat][0]);
}
ok(targets.length >= 2, '应有至少 2 个真实目标 ID 可测（实际 ' + targets.length + '）');

for (const id of targets) {
  const r = await rec(id, map, { limit: 10 });
  console.log(`\n=== for ${id} (${map[id]?.category}) 召回 ${r.source_recalled} → 过滤后 ${r.after_filter} → 返回 ${r.count} ===`);
  ok(!r.error, `${id} 不应报错`);
  ok(r.pipeline.includes('CandidatePipeline'), 'pipeline 标记应为 CandidatePipeline');
  ok(Array.isArray(r.recommendations), 'recommendations 应为数组');

  // 断言 2+3：无硬冲突；排序：兼容在前、未定在后；类内降序
  let prevClass = 2, prevKey = Infinity, monotonic = true;
  for (const x of r.recommendations) {
    ok(x.overall_compatible !== false, `${id}→${x.id} 不应含硬冲突`);
    ok(x.score_basis != null, `${id}→${x.id} 应带 score_basis`);
    const cls = x.overall_compatible === true ? 1 : 0;
    const key = x.overall_compatible === true ? (x.compatibility_score || 0) : (x.score_basis?.weight_sum_decided || 0);
    if (cls > prevClass || (cls === prevClass && key > prevKey)) monotonic = false;
    prevClass = cls; prevKey = key;
  }
  ok(monotonic, `${id} 排序应为「兼容在前降序 / 未定在后按证据量降序」`);

  // 断言 4：推荐分数与直接用 judgePair 一致（未重写裁决）
  for (const x of r.recommendations) {
    const direct = judgePair(map[id], map[x.id]);
    ok(direct.compatibility_score === x.compatibility_score, `${id}→${x.id} 分数须与 compat_engine 一致`);
  }

  // 抽样打印前 3 条，人工可见
  r.recommendations.slice(0, 3).forEach((x) => {
    console.log(`   · ${x.id} (${x.category}) overall=${x.overall_compatible} score=${x.compatibility_score} decided=${x.score_basis?.weight_sum_decided}`);
  });
}

// 断言 5：不存在 ID
const ne = await rec('NOPE-999', map, {});
ok(ne.error && ne.recommendations.length === 0, '不存在 ID 应返回 error + 空列表');

console.log(`\n===== P1 校验：${pass} 通过 / ${fail} 失败 =====`);
process.exit(fail ? 1 : 0);
