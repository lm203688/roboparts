/**
 * 机械编码「书写形式」行为对照 —— 证明引擎不再把排版差异判成「装不上」，
 * 也不会为了消除差异而凭空断言两种编码等价。
 *
 * 为什么需要这支测试（20260811-09）
 * ---------------------------------
 * 20260811-08 那轮修的是**登记表侧**：实体写 `ISO 9409-1-50-4-M6`（无 A、带空格），
 * 登记表 id 写 `ISO9409-1-A50-4-M6`（有 A、无空格），707 处 registry_ref 零命中，
 * 于是给登记表补了 aliases 与归一化规则。
 *
 * 但**真正对用户输出结论的那一段代码没动**：`compat_engine.js` 的
 * `idValues()` 只做 `trim().toLowerCase()`，两个实体之间的比对仍是逐字符相等。
 * 实测（修复前，用生产代码跑）：
 *   `ISO 9409-1-50-4-M6` × `ISO9409-1-50-4-M6` → compatible=**false**「机械接口无交集」
 * 同一个法兰，只因一个空格，被判"装不上"。这不是判不了，是**带着数据外观的错误结论**。
 *
 * 数据侧修好、判定侧没修，是本项目反复出现的一类：
 * 修的是我看得见的那一层，而结论从另一层出去。故本轮把归一化下沉到引擎，
 * 并用本测试锁死两条**方向相反**的不变式：
 *   ① 纯词法差异（大小写 / 空白 / Unicode 连字符）必须归一 → 不许假红；
 *   ② 语义未定差异（带 A 与不带 A）必须判 null → 既不许假红，也不许假绿。
 *
 * 自证不空转：下方 legacyIdValues() 是**冻结的修复前实现**（照抄 20260811-09 之前的
 * `idValues`），不是 `git show HEAD` —— 锚在会随提交移动的引用上，修好那一刻自证就蒸发。
 */
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';

const ROOT = path.dirname(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')));
const enginePath = path.join(ROOT, 'functions', '_lib', 'compat_engine.js');
const { evalDimension, judgePair, normalizeMechToken, parseIsoFlange } =
  await import(pathToFileURL(enginePath).href);

let fail = 0;
const ok = (cond, label) => {
  console.log((cond ? '  ✅ ' : '  ❌ ') + label);
  if (!cond) fail++;
};

const ent = (id, mi) => ({
  id, name: id, category: 'sensors', entity_kind: 'component',
  mechanical_interface: { status: 'declared', mount_type: 'flange_mount', source: '测试夹具', ...mi },
});
const OEM = 'ISO 9409-1-50-4-M6';        // UR / Robotiq 一手手册写法（有空格、无 A）
const NOSPACE = 'ISO9409-1-50-4-M6';     // 同一编码，无空格
const APREFIX = 'ISO9409-1-A50-4-M6';    // 第三方集成商汇编写法（有 A）
const NBHYPHEN = 'ISO 9409\u20111\u201150\u20114\u2011M6';  // PDF 复制常见的非断字连字符
const OTHER = 'ISO 9409-1-31.5-4-M5';    // 真正不同的尺寸

// ── 冻结的修复前实现（只用于证明测试压在真缺陷上，不参与生产路径） ──────────
function legacyIdValues(v) {
  return (Array.isArray(v) ? v : [v])
    .filter(x => x !== null && x !== undefined)
    .map(x => String(x).trim().toLowerCase())
    .filter(x => x && x !== 'unknown');
}
function legacyMechanical(sa, sb) {
  const ea = legacyIdValues(sa), eb = legacyIdValues(sb);
  if (!ea.length || !eb.length) return { compatible: null };
  const shared = ea.filter(p => eb.includes(p));
  return { compatible: shared.length > 0, notes: shared.length ? '安装侧接口一致' : '机械接口无交集' };
}

console.log('=== 阳性 1：纯词法差异不得判「装不上」（空格 / 大小写 / 全角空格 / U+2011） ===');
for (const [label, other] of [
  ['无空格写法', NOSPACE],
  ['小写写法', OEM.toLowerCase()],
  ['全角空格', 'ISO\u30009409-1-50-4-M6'],
  ['非断字连字符 U+2011', NBHYPHEN],
  ['首尾空白', `  ${OEM}\t`],
]) {
  const r = evalDimension('mechanical', ent('A', { standard: OEM }), ent('B', { standard: other }));
  ok(r.compatible === true && r.relation === 'interchangeable', `${label} → 判为可互换（compatible=${r.compatible}）`);
}

console.log('=== 阳性 2：工具侧↔安装侧的对接判定同样吃归一化（否则假红换个地方复发） ===');
{
  const r = evalDimension('mechanical',
    ent('A', { standard: OTHER, tool_side: NOSPACE }),
    ent('B', { standard: OEM }));
  ok(r.compatible === true && r.relation === 'mateable', `跨写法仍判可对接（relation=${r.relation}）`);
}

console.log('=== 阴性 1：真正不同的尺寸仍必须判 false（不得被归一化洗成兼容） ===');
{
  const r = evalDimension('mechanical', ent('A', { standard: OEM }), ent('B', { standard: OTHER }));
  ok(r.compatible === false && r.relation === 'none', `50-4-M6 × 31.5-4-M5 仍判 false（compatible=${r.compatible}）`);
  const r2 = evalDimension('mechanical', ent('A', { standard: 'PCD56-8-M4' }), ent('B', { standard: 'PCD60-4-M5' }));
  ok(r2.compatible === false, '非 ISO 编码的真冲突仍判 false（归一化只动排版，不动内容）');
}

console.log('=== 阴性 2：带 A 与不带 A 属语义未定 → 必须判 null，两个方向都不许下结论 ===');
{
  const r = evalDimension('mechanical', ent('A', { standard: OEM }), ent('B', { standard: APREFIX }));
  ok(r.compatible === null, `不判 false（假红）也不判 true（假绿），实得 compatible=${r.compatible}`);
  ok(r.relation === 'undecided_designation_form', `relation=undecided_designation_form（实得 ${r.relation}）`);
  ok(/ISO 9409-1 标准原文/.test(r.notes || ''), '说明里点明"须以标准原文为准、本平台未持有"，不含糊');
}

console.log('=== 阴性 3：尺寸段不同就算都带前缀也不许并成「书写形式之争」 ===');
{
  const r = evalDimension('mechanical', ent('A', { standard: OEM }), ent('B', { standard: 'ISO9409-1-A31.5-4-M5' }));
  ok(r.compatible === false && r.relation === 'none',
    `A31.5-4-M5 × 50-4-M6 仍是真冲突（compatible=${r.compatible} / relation=${r.relation}）`);
}

console.log('=== 阴性 4：老不变式不许被本次改动破坏（无数据 ≠ 不兼容） ===');
{
  const r = evalDimension('mechanical',
    { id: 'A', name: 'A', mechanical_interface: { status: 'not_declared' } },
    ent('B', { standard: OEM }));
  ok(r.compatible === null, 'not_declared 仍为 null');
  const r2 = evalDimension('mechanical',
    ent('A', { standard: null, flange: null, mount_type: 'flange_mount' }),
    ent('B', { standard: OEM }));
  ok(r2.compatible === null, '只给 mount_type 仍为 null（L1.64 不许回退）');
}

console.log('=== 解析器：只认 ISO 9409-1 形态，不猜 ===');
{
  ok(normalizeMechToken(' iso 9409\u20111-50-4-m6 ') === 'ISO9409-1-50-4-M6', 'normalizeMechToken 归一到统一大写无空白形式');
  const p = parseIsoFlange(APREFIX);
  ok(p && p.form === 'A' && p.d1 === 50 && p.bolts === 4 && p.thread === 'M6', 'parseIsoFlange 拆出 form/d1/bolts/thread 且保留字母前缀');
  ok(parseIsoFlange('PCD56-8-M4') === null, '非 ISO 编码返回 null（不硬套）');
  ok(parseIsoFlange('ISO 9409-1-50-4') === null, '缺螺纹段的残缺编码返回 null（不补全）');
}

console.log('=== 端到端：新状态必须活到对外响应，不能只活在 notes 里 ===');
{
  const jp = judgePair(ent('A', { standard: OEM }), ent('B', { standard: APREFIX }));
  const md = jp.dimensions.find(d => d.dimension === 'mechanical');
  ok(md && md.compatible === null, 'judgePair 的 mechanical 维度为 null');
  ok(md && md.relation === 'undecided_designation_form', `judgePair 透传 relation（实得 ${md && md.relation}）`);
  ok(jp.overall_compatible !== false, '整体结论不因书写形式之争塌成 false');
}

console.log('=== 覆盖面：真实库里在用的编码必须都能被解析器认出（防判据只对夹具有效） ===');
{
  const entsPath = path.join(ROOT, 'api', 'entities.json');
  const db = JSON.parse(fs.readFileSync(entsPath, 'utf8'));
  const tokens = new Set();
  for (const e of db.entities || []) {
    const mi = e.mechanical_interface || {};
    for (const k of ['standard', 'flange', 'tool_side', 'tool_side_flange']) {
      const v = mi[k];
      for (const x of (Array.isArray(v) ? v : [v])) {
        if (typeof x === 'string' && /9409/.test(x)) tokens.add(x);
      }
    }
  }
  ok(tokens.size > 0, `实体库中 ISO 9409 编码 ${tokens.size} 种（解析器覆盖面非空）`);
  const unparsed = [...tokens].filter(t => parseIsoFlange(t) === null);
  ok(unparsed.length === 0, `全部可被 parseIsoFlange 解析（无法解析: ${unparsed.join(', ') || '无'}）`);
}

console.log('=== 证非空转：冻结的修复前实现对同一输入确实判出假红 ===');
{
  const legacy = legacyMechanical(OEM, NOSPACE);
  ok(legacy.compatible === false,
    `修复前实现复现缺陷：同一法兰的两种写法被判 compatible=false（${legacy.notes}）`);
  const legacyA = legacyMechanical(OEM, APREFIX);
  ok(legacyA.compatible === false,
    '修复前实现对 A 前缀同样给出确定性 false（而正确答案是"判不了"）');
}

if (fail) {
  console.log(`\n❌ 机械编码书写形式行为对照失败 ${fail} 项`);
  process.exit(1);
}
console.log('\n✅ 机械编码书写形式行为对照全部通过');
