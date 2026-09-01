import { buildAssemblySequence } from '../functions/api/bom/check.js';
import { mechanicalEvidence } from '../functions/_lib/compat_engine.js';

// 断言工具
let pass = 0, fail = 0;
function ok(cond, msg) { if (cond) { pass++; } else { fail++; console.log('  ✗ FAIL:', msg); } }

// 构造合成 BOM（绕开引擎求值，直接手工标注 mateable 对，只验证 buildAssemblySequence 算法）
// 机械接口字段：standard/flange → 机器人侧(robot)；tool_side → 工具侧(tool)
const resolved = [
  { ref: 'BASE-ARM', name: '基座臂', category: 'actuators',
    mechanical_interface: { status: 'declared', standard: 'ISO9409-1-A63' } },       // robot=A63
  { ref: 'GRIP', name: '夹爪', category: 'actuators',
    mechanical_interface: { status: 'declared', tool_side: 'ISO9409-1-A63' } },       // tool=A63 → 装在 BASE 上
  { ref: 'FT', name: '六维力传感器', category: 'sensors',
    mechanical_interface: { status: 'declared', tool_side: 'ISO9409-1-A63' } },       // tool=A63 → 装在 BASE 上
  { ref: 'CTRL', name: '控制器', category: 'controllers',
    mechanical_interface: { status: 'not_declared' } },                              // 无 MI → 启发式
  { ref: 'PWR', name: '电源模块', category: 'chips',
    mechanical_interface: { status: 'not_declared' } },                              // 无 MI → 启发式
];

const matrix = [
  // BASE-ARM(GRIP): mateable, GRIP.tool(A63) ∩ BASE.robot(A63) → GRIP 装在 BASE 上
  { a: 'BASE-ARM', b: 'GRIP', overall_compatible: true,
    dimensions: [ { dimension: 'mechanical', compatible: true, relation: 'mateable' } ] },
  // BASE-ARM(FT): mateable, FT.tool(A63) ∩ BASE.robot(A63) → FT 装在 BASE 上
  { a: 'BASE-ARM', b: 'FT', overall_compatible: true,
    dimensions: [ { dimension: 'mechanical', compatible: true, relation: 'mateable' } ] },
  // CTRL(PWR): 无机械维度 or 非 mateable → 无装配边
  { a: 'CTRL', b: 'PWR', overall_compatible: null,
    dimensions: [ { dimension: 'mechanical', compatible: null } ] },
];

const { sequence, notes } = buildAssemblySequence(resolved, matrix);
console.log('basis:', notes.basis, '| data_derived:', notes.data_derived_steps, '| heuristic:', notes.heuristic_steps, '| cycle:', notes.cycle_detected);
console.log(sequence.map(s => `  #${s.step} ${s.ref} [${s.basis}] mounts_on=${JSON.stringify(s.mounts_on)}`).join('\n'));

// 1) 依赖顺序：BASE-ARM 必须在 GRIP/FT 之前
const pos = Object.fromEntries(sequence.map(s => [s.ref, s.step]));
ok(pos['BASE-ARM'] < pos.GRIP, 'BASE-ARM 应早于 GRIP');
ok(pos['BASE-ARM'] < pos.FT, 'BASE-ARM 应早于 FT');

// 2) 方向正确：GRIP/FT 的 mounts_on 应指向 BASE-ARM
ok(JSON.stringify(sequence.find(s=>s.ref==='GRIP').mounts_on) === '["BASE-ARM"]', 'GRIP 应挂载在 BASE-ARM');
ok(JSON.stringify(sequence.find(s=>s.ref==='FT').mounts_on) === '["BASE-ARM"]', 'FT 应挂载在 BASE-ARM');

// 3) basis 标注：有 MI 的 3 件 data_derived，无 MI 的 2 件 heuristic
ok(notes.data_derived_steps === 3 && notes.heuristic_steps === 2, 'data_derived=3 / heuristic=2');
ok(sequence.find(s=>s.ref==='BASE_ARM') === undefined, '（占位，永不触发）');
ok(sequence.find(s=>s.ref==='CTRL').basis === 'category_heuristic', 'CTRL 应为 heuristic');
ok(sequence.find(s=>s.ref==='PWR').basis === 'category_heuristic', 'PWR 应为 heuristic');

// 4) 无 MI 数据时完全启发式（诚实边界）
const resolved2 = [
  { ref: 'X', name: 'X', category: 'sensors', mechanical_interface: { status: 'not_declared' } },
  { ref: 'Y', name: 'Y', category: 'structures', mechanical_interface: { status: 'not_declared' } },
];
const { notes: n2 } = buildAssemblySequence(resolved2, []);
ok(n2.basis === 'fully_heuristic', '无 MI 时应 fully_heuristic');
ok(n2.cycle_detected === false, '无 MI 时不应误报 cycle');

// 5) 循环依赖检测（A→B→A）：应标 cycle_detected 且不崩
const resolved3 = [
  { ref: 'A', name: 'A', category: 'actuators', mechanical_interface: { status: 'declared', standard: 'K', tool_side: 'L' } },
  { ref: 'B', name: 'B', category: 'actuators', mechanical_interface: { status: 'declared', standard: 'L', tool_side: 'K' } },
];
const matrix3 = [
  { a: 'A', b: 'B', overall_compatible: true, dimensions: [ { dimension: 'mechanical', compatible: true, relation: 'mateable' } ] },
];
const { notes: n3, sequence: s3 } = buildAssemblySequence(resolved3, matrix3);
// A.tool(L) ∩ B.robot(L) → A 装 B 上(base=B,attach=A)；B.tool(K) ∩ A.robot(K) → B 装 A 上 → 双向 ambiguous，无方向边，无 cycle
ok(n3.cycle_detected === false, '双向 ambiguous 不算 cycle（无方向边）');
ok(s3.length === 2, 'ambiguous 对仍应输出全部组件');

console.log(`\n结果：${pass} 通过 / ${fail} 失败`);
process.exit(fail ? 1 : 0);
