import { aggregateCommunityFit } from '../functions/api/adapter-feedback.js';
import { aggregateRecfb } from '../functions/api/recommend-feedback.js';

let pass = 0, fail = 0;
function ok(cond, msg) { if (cond) pass++; else { fail++; console.log('  ✗ FAIL:', msg); } }

// ---- aggregateCommunityFit ----
// 1) 同对 3 条全 ok（达 minSamples）→ fits_well
const r1 = aggregateCommunityFit([
  { flangeA: 'A50', flangeB: 'A63', fit: 'ok' },
  { flangeA: 'A63', flangeB: 'A50', fit: 'ok' },   // 反向应归并同一对
  { flangeA: 'A50', flangeB: 'A63', fit: 'ok' },
], 3);
ok(r1.length === 1, '应聚合为 1 个配对');
ok(r1[0].samples === 3 && r1[0].ok === 3, 'samples=3 / ok=3');
ok(r1[0].signal === 'fits_well', '全 ok 达阈值 → fits_well');

// 2) 同对 1 ok + 2 bad（3 样本）→ bad 占比 0.667 ≥ 0.3 → needs_review
const r2 = aggregateCommunityFit([
  { flangeA: 'A50', flangeB: 'A63', fit: 'ok' },
  { flangeA: 'A63', flangeB: 'A50', fit: 'bad' },
  { flangeA: 'A50', flangeB: 'A63', fit: 'bad' },
], 3);
ok(r2[0].bad === 2 && r2[0].signal === 'needs_review', 'bad 占比 0.667 → needs_review');

// 3) 样本不足（2 < minSamples 3）→ insufficient_data
const r3 = aggregateCommunityFit([
  { flangeA: 'A50', flangeB: 'A63', fit: 'ok' },
  { flangeA: 'A50', flangeB: 'A63', fit: 'bad' },
], 3);
ok(r3[0].samples === 2 && r3[0].signal === 'insufficient_data', '样本不足 → insufficient_data（不误判）');

// 4) adjust 计入但不触发 needs_review（bad=0）→ fits_well
const r4 = aggregateCommunityFit([
  { flangeA: 'A50', flangeB: 'A63', fit: 'ok' },
  { flangeA: 'A50', flangeB: 'A63', fit: 'adjust' },
  { flangeA: 'A50', flangeB: 'A63', fit: 'ok' },
], 3);
ok(r4[0].adjust === 1 && r4[0].signal === 'fits_well', 'adjust 计入，bad=0 → fits_well');

// 5) 缺 flange 字段的记录被跳过
const r5 = aggregateCommunityFit([
  { fit: 'ok' },                            // 缺 flangeA/B
  { flangeA: 'A50', flangeB: 'A63', fit: 'ok' },
  { flangeA: 'A50', flangeB: 'A63', fit: 'ok' },
  { flangeA: 'A50', flangeB: 'A63', fit: 'ok' },
], 3);
ok(r5.length === 1 && r5[0].samples === 3, '缺 flange 的记录被跳过');

// ---- aggregateRecfb ----
const shards = [
  { r1: { adopt: 2, ignore: 1 }, _updated: 't1' },
  { r1: { adopt: 3, ignore: 0 }, r2: { adopt: 1, ignore: 1 } },
  null,                                     // 空分片容忍
];
const m = aggregateRecfb(shards);
ok(m.r1.adopt === 5 && m.r1.ignore === 1, 'r1 跨分片累加 adopt=5/ignore=1');
ok(m.r2.adopt === 1 && m.r2.ignore === 1, 'r2 累加 adopt=1/ignore=1');
ok(!('_updated' in m), '_updated 控制键被忽略');

console.log(`\n结果：${pass} 通过 / ${fail} 失败`);
process.exit(fail ? 1 : 0);
