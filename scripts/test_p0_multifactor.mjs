/**
 * P0 多因子兼容度评分引擎 · 本地验证
 * 直接 import 生产源码 functions/_lib/compat_engine.js（不复制逻辑）。
 *
 * 覆盖：
 *  ① 加权折算数值正确（对比手算）
 *  ② 可解释分解（score_basis.breakdown）存在且字段完整
 *  ③ 三态不变式：overall=null ⇒ compatibility_score===null 且 score_basis===null
 *  ④ 与旧"简单比例"公式产生区分度（重维度冲突应更重地拉低分数）
 *  ⑤ 维度权重之和=1（调参时不破坏归一化）
 */
import { judgePair, scoreBreakdown, SCORE_WEIGHTS } from '../functions/_lib/compat_engine.js';

let pass = 0, fail = 0;
function ok(cond, msg) {
  if (cond) { pass++; console.log('  ✓ ' + msg); }
  else { fail++; console.log('  ✗ ' + msg); }
}
const mk = (id, f = {}) => ({
  id, name: id, category: 'actuators', entity_kind: 'component', ...f,
});
const show = (label, r) => {
  console.log(`\n【${label}】overall=${r.overall_compatible} score=${r.compatibility_score}`);
  if (r.score_basis) {
    for (const b of r.score_basis.breakdown) {
      console.log(`    - ${b.dimension}: w=${b.weight} verdict=${b.verdict} contribution=${b.contribution}`);
    }
  } else {
    console.log('    score_basis=null');
  }
};

console.log('=== ① 机械可互换（仅机械有数据，其余未声明）===');
const A = mk('A', { mechanical_interface: { status: 'declared', standard: ['ISO 9409-1-50-4-M6'] } });
const B = mk('B', { mechanical_interface: { status: 'declared', standard: ['ISO 9409-1-50-4-M6'] } });
const r1 = judgePair(A, B);
show('A×B', r1);
ok(r1.overall_compatible === true, '整体兼容=true（机械为硬约束且有双方声明）');
ok(r1.compatibility_score === 100, `分数=100（仅机械维度 0.35/0.35）实得 ${r1.compatibility_score}`);
ok(r1.score_basis && r1.score_basis.breakdown.length === 4, 'score_basis 含 4 维分解');
ok(r1.dimensions.find(d => d.dimension === 'mechanical').relation === 'interchangeable', '机械维度 relation=interchangeable');

console.log('\n=== ② 协议真冲突（CAN vs EtherCAT，均声明）===');
const C = mk('C', { protocol: 'CAN' });
const D = mk('D', { protocol: 'EtherCAT' });
const r2 = judgePair(C, D);
show('C×D', r2);
ok(r2.overall_compatible === false, '整体不兼容=true（协议冲突）');
ok(r2.compatibility_score === 0, `分数=0（协议维度冲突 0/0.25）实得 ${r2.compatibility_score}`);

console.log('\n=== ③ ROS2 单方声明兼容、其余全无 → 整体无法判定 ===');
const E = mk('E', { ros_support: true });
const F = mk('F', { ros_support: true });
const r3 = judgePair(E, F);
show('E×F', r3);
ok(r3.overall_compatible === null, '整体=null（仅 ROS2 软维度，无硬约束证据）');
ok(r3.compatibility_score === null, 'compatibility_score=null（不把"不知道"伪装成 0 或 100）');
ok(r3.score_basis === null, 'score_basis=null（与分数一致，避免假精确）');

console.log('\n=== ④ 混合冲突：机械冲突 + 协议兼容 + 电气兼容（旧比例=67，加权应更低）===');
const I = mk('I', { mechanical_interface: { status: 'declared', standard: ['ISO 9409-1-50-4-M6'] }, protocol: 'CAN', voltage: '24~24V' });
const J = mk('J', { mechanical_interface: { status: 'declared', standard: ['ISO 9409-1-31.5-4-M5'] }, protocol: 'CAN', voltage: '24~24V' });
const r4 = judgePair(I, J);
show('I×J', r4);
ok(r4.overall_compatible === false, '整体不兼容=true（机械冲突）');
// 手算：贡献 = 机械0(0.35×0) + 协议0.25 + 电气0.25 = 0.50；权重和 = 0.35+0.25+0.25 = 0.85
// 0.50/0.85 = 58.82 → 59；旧比例 2/3 = 66.67 → 67。加权更重地惩罚了最关键的机械冲突。
ok(r4.compatibility_score === 59, `分数=59（加权惩罚重维度冲突）实得 ${r4.compatibility_score}`);
ok(r4.compatibility_score !== 67, '与旧简单比例(67)产生区分度');

console.log('\n=== ⑤ 权重归一化 ===');
const wsum = Object.values(SCORE_WEIGHTS).reduce((a, b) => a + b, 0);
ok(Math.abs(wsum - 1) < 1e-9, `SCORE_WEIGHTS 之和=1（实得 ${wsum}）`);

console.log(`\n=== 结果：${pass} 通过 / ${fail} 失败 ===`);
process.exit(fail ? 1 : 0);
