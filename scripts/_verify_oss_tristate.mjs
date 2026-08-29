// 功能复验：确认修复后，OSS 数据在真实兼容性引擎里走的是 unknown 分支，
// 而不是被伪造的布尔值推向「支持 / 不支持」的事实断言。
// 直接 import 生产源码 functions/_lib/compat_engine.js，不做任何复制或改写。
import { readFileSync } from 'node:fs';
import { judgePair } from '../functions/_lib/compat_engine.js';

const doc = JSON.parse(readFileSync(new URL('../api/oss_components.json', import.meta.url), 'utf-8'));
const rows = doc.data;
const byExt = (e) => rows.filter(r => r.extractor === e);

const urdf = byExt('urdf')[0];
const bom = byExt('bom_md')[0];
const seedTrue = rows.find(r => !r.extractor && r.ros_support === true);
const seedFalse = rows.find(r => !r.extractor && r.ros_support === false);

const soft = (a, b) => {
  const res = judgePair(a, b);
  const d = (res.dimensions || res.details || []).find(x => x.dimension === 'software')
    || (res.by_dimension && res.by_dimension.software);
  return d || res;
};

function show(label, a, b) {
  const d = soft(a, b);
  console.log(`\n${label}`);
  console.log(`  A=${(a.name || '').slice(0, 42)}  ros_support=${JSON.stringify(a.ros_support)}`);
  console.log(`  B=${(b.name || '').slice(0, 42)}  ros_support=${JSON.stringify(b.ros_support)}`);
  console.log(`  -> compatible=${JSON.stringify(d.compatible)}  notes="${d.notes}"`);
  return d;
}

let fail = 0;
const expect = (cond, msg) => { console.log(`  ${cond ? '✅' : '❌'} ${msg}`); if (!cond) fail++; };

console.log('=== OSS 三态功能复验（对生产引擎源码）===');

const d1 = show('[1] URDF 关节 × 机械 BOM 件（修复前：true × false = 断言「仅一方支持，需额外驱动」）', urdf, bom);
expect(d1.compatible === null, '双方未声明 -> compatible=null（无法判定），不是 false');
expect(/未声明/.test(d1.notes), 'notes 明说未声明，而非编造「不支持」');

const d2 = show('[2] URDF 关节 × 种子(明确支持 ROS)', urdf, seedTrue);
expect(d2.compatible === null, '一方未声明 -> null，不得因另一方 true 就判定兼容（防假绿）');

const d3 = show('[3] 种子(支持) × 种子(不支持) —— 真实声明冲突仍应判 false', seedTrue, seedFalse);
expect(d3.compatible === false, '双方均有真实声明且冲突 -> 仍判 false（未过度放宽）');

const d4 = show('[4] 种子(支持) × 种子(支持)', seedTrue, rows.filter(r => !r.extractor && r.ros_support === true)[1]);
expect(d4.compatible === true, '双方均声明支持 -> true');

console.log(`\n未声明项 ${rows.filter(r => r.ros_support === undefined).length}/${rows.length}`);
console.log(fail === 0 ? '\n✅ 功能复验通过：三态在真实引擎上全部正确' : `\n❌ ${fail} 项不符`);
process.exit(fail === 0 ? 0 : 1);
