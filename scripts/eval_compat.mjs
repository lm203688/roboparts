import { readFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { judgePair } from '../functions/_lib/compat_engine.js';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const ENTITIES_PATH = join(ROOT, 'api', 'entities.json');
const GOLDEN_PATH = join(ROOT, 'api', 'eval', 'compatibility-golden.json');

if (!existsSync(ENTITIES_PATH) || !existsSync(GOLDEN_PATH)) {
  console.error('❌ 评估前置文件缺失:', { entities: existsSync(ENTITIES_PATH), golden: existsSync(GOLDEN_PATH) });
  process.exit(1);
}

const data = JSON.parse(readFileSync(ENTITIES_PATH, 'utf8'));
const golden = JSON.parse(readFileSync(GOLDEN_PATH, 'utf8'));
const ents = new Map(data.entities.map((e) => [e.id, e]));

function evalCase(c) {
  const a = ents.get(c.component1_id);
  const b = ents.get(c.component2_id);
  let result;
  try {
    result = judgePair(a, b);
  } catch (e) {
    return { caseId: c.id, status: 'CRASH', error: e.message };
  }

  const exp = c.expect;
  const failures = [];

  if (exp.not_crash === true) {
    // 只要求不崩
    if (!result) failures.push('not_crash: 返回 null/undefined');
  } else {
    // applicable
    if (exp.applicable !== undefined && result.applicable !== exp.applicable) {
      failures.push(`applicable: 期望 ${exp.applicable} 实得 ${result.applicable}`);
    }
    // overall_compatible（boolean: true / false / null）
    if (exp.overall_compatible !== undefined && result.overall_compatible !== exp.overall_compatible) {
      failures.push(`overall_compatible: 期望 ${exp.overall_compatible} 实得 ${result.overall_compatible}`);
    }
    if (exp.overall_in) {
      // overall_in 接受 "compatible"→true, "incompatible"→false, "needs_review"→null
      const map = { compatible: true, incompatible: false, needs_review: null };
      const expected = exp.overall_in.map((s) => map[s] ?? s);
      if (!expected.includes(result.overall_compatible)) {
        failures.push(`overall_compatible: 实得 ${result.overall_compatible} 不在期望范围 ${exp.overall_in.join(',')}`);
      }
    }
    // evidence_count_min
    const evCount = result.evidence_count ?? (result.evidence_sources || []).length;
    if (exp.evidence_count_min !== undefined && evCount < exp.evidence_count_min) {
      failures.push(`evidence_count: 期望 >=${exp.evidence_count_min} 实得 ${evCount}`);
    }
    // dimensions_expected: 用 DIMENSION_BY_IDX 索引（0=electrical 1=mechanical 2=protocol 3=software）
    const DIMENSION_BY_IDX = ['electrical', 'mechanical', 'protocol', 'software'];
    if (exp.dimensions_expected) {
      for (const [dimName, expected] of Object.entries(exp.dimensions_expected)) {
        const idx = DIMENSION_BY_IDX.indexOf(dimName);
        if (idx === -1) continue;
        const actual = result.dimensions?.[idx]?.compatible;
        if (expected === null) {
          if (actual !== null) failures.push(`dimensions[${idx}](${dimName}): 期望 null 实得 ${actual}`);
        } else {
          // actual 可能为 true / false / "true(弱)" 之类字符串，规范化
          const actualNorm = actual === true || (typeof actual === 'string' && actual.startsWith('true'))
            ? true
            : actual === false
              ? false
              : null;
          if (actualNorm !== expected) {
            failures.push(`dimensions[${idx}](${dimName}): 期望 ${expected} 实得 ${actual}`);
          }
        }
      }
    }
    // verdict_reason_contains
    if (exp.verdict_reason_contains) {
      const reason = (result.verdict_reason || '') + (result.overall === 'incompatible' ? ' ' + (result.verdict_reason || '') : '');
      const joined = result.verdict_reason || '';
      for (const kw of exp.verdict_reason_contains) {
        if (!joined.includes(kw)) failures.push(`verdict_reason 不包含 "${kw}"`);
      }
    }
  }

  return { caseId: c.id, type: c.type, status: failures.length ? 'FAIL' : 'PASS', failures };
}

const results = golden.cases.map(evalCase);
const pass = results.filter((r) => r.status === 'PASS').length;
const fail = results.filter((r) => r.status !== 'PASS').length;
const crash = results.filter((r) => r.status === 'CRASH').length;

console.log('═'.repeat(54));
console.log(' RoboParts 兼容性裁决评估 · ' + new Date().toISOString().slice(0, 19));
console.log('═'.repeat(54));
console.log(` Golden 集: ${golden._meta.freeze_anchors} freeze-anchor + ${golden._meta.badcases} badcase = ${golden._meta.total_cases} 条`);
console.log('');

for (const r of results) {
  const mark = r.status === 'PASS' ? '✅' : r.status === 'CRASH' ? '💥' : '❌';
  console.log(` ${mark} ${r.caseId}: ${r.status}${r.type ? ' (' + r.type + ')' : ''}`);
  if (r.failures) r.failures.forEach((f) => console.log(`     - ${f}`));
  if (r.error) console.log(`     - ${r.error.slice(0, 200)}`);
}

console.log('');
console.log('─'.repeat(54));
console.log(` 结果: ${pass} PASS / ${fail} FAIL / ${crash} CRASH  (共 ${results.length})`);
if (fail === 0 && crash === 0) console.log(' 判定: 全绿 ✅（规则引擎与预期一致，无回归）');
else if (crash === 0) console.log(' 判定: 有 FAIL ⚠️（引擎行为与 Golden 集不一致，需排查——但也可能是 Golden 集与规则有差异）');
else console.log(' 判定: 有 CRASH ❌（引擎崩溃，阻塞）');
console.log('');
console.log(' 注：Golden 集为冻结回归锚点，非第三方认证真值。');
console.log(' 规则修改后应更新 Golden 集或记录偏差原因。');
console.log('═'.repeat(54));

process.exit(fail === 0 && crash === 0 ? 0 : 1);
