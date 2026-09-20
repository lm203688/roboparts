#!/usr/bin/env node
/**
 * 需求信号回流器（api/demand-signal.json）—— 单一实现，deploy 与手工都调它。
 *
 * 【为什么要有这个文件 · 20260915】
 * deploy.mjs 的 0b3 步骤原先只是把 ops 里最新的 demand-signal-YYYYMMDD.json
 * **原样复制**到 api/。问题在于：那份快照里既有无需重算的历史信号（社区提问计数，
 * 本就是累计量），也混着**本该现算**的字段（mechanical 声明率 / 实体总数）。
 * 一旦快照陈旧（本仓库实测：最新快照停在 2026-08-28，18 天没更新），
 * 每次部署都会把这些过期数字**重新灌回对外端点** —— 手工改 api/ 会被静默覆盖。
 * 这正是「口径 ≠ 事实」的又一形态：派生物一旦对外，它的现算字段就必须与真相源
 * 同一时刻更新，不能继承快照。与 deploy 链上 0b/0c/0d 同一条纪律。
 *
 * 【为什么回流必须重新判别 · 20260920】
 * 上面那条纪律只管「数字现算」，没管「计数是真信号吗」。ops 里的旧快照由旧版
 * demand_scan 产出：sources[] 每条 `real_signal: true` 是写死常量，verdict 写着
 * 「已捕获 10 条真实兼容性提问信号」——而那 10 条全是 AI/LLM 仓库的软件 PR
 * （"OpenAI-compatible providers"、"ABI-compatible"、"GEMM replacement"）。
 * 若回流只重算声明率，这句对外假陈述会原样进 /api/demand-signal 端点，
 * 每次部署静默重写。所以本脚本第 3 步是**按判别层重判 sources**，
 * 而不是信任快照里的 real_query_count。
 *
 * 本脚本做三件事，顺序不可换：
 *   1) 取 ops 里最新的 demand-signal-*.json 复制到 api/（保住历史信号块）；
 *   2) 用 api/entities.json（单一真相源）**重算**现算块：
 *        can_answer_today.{mech_decl_rate, mech_declared, total_entities, mech_applicable}
 *      重算口径 = (declared + partial) / (declared + partial + not_declared)
 *      —— 与 scripts/add_mechanical_interface.py 及 onboarding_block.facts() 同式。
 *   3) 用 scripts/lib/demand_signal_rules.mjs **重判** sources[]，重建三态计数
 *      与 verdict（verdict 由 buildVerdict 生成，不再靠正则替换旧句里的百分比）。
 *
 * 纪律：现算字段只从真相源取；计数只从判别层取；不编造数字、不保留旧版假陈述。
 * 无快照可复制时以 api/ 现状为底本原地重算（端点不会因此 404）。
 *
 * 用法：
 *   node scripts/reflow_demand_signal.mjs            # 回流
 *   node scripts/reflow_demand_signal.mjs --self-test  # 离线自测（不落盘）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  classifyBatch, toPublicSources, buildVerdict, estimateAnswerability,
  buildActionableFixes, CROSS_BRAND_RE,
} from './lib/demand_signal_rules.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE);
const API_DS = path.join(ROOT, 'api', 'demand-signal.json');
const API_ENT = path.join(ROOT, 'api', 'entities.json');

/** 声明率口径（唯一）：分子含 partial，分母只算「适用」实体。 */
function mechCoverage(entities) {
  const cnt = { declared: 0, partial: 0, not_declared: 0, n_a: 0 };
  for (const e of entities) {
    const s = (e && e.mechanical_interface && e.mechanical_interface.status) || 'not_declared';
    if (s in cnt) cnt[s] += 1;
    else cnt.not_declared += 1; // 未知取值按"适用但未声明"处理，绝不静默算成不适用
  }
  const applicable = cnt.declared + cnt.partial + cnt.not_declared;
  const withLead = cnt.declared + cnt.partial;
  const rate = applicable ? withLead / applicable : 0;
  return { cnt, applicable, withLead, rate };
}

function newestSnapshot() {
  const opsDir = path.join(ROOT, 'ops');
  if (!fs.existsSync(opsDir)) return null;
  const files = fs.readdirSync(opsDir)
    .filter((f) => /^demand-signal-\d{4}-\d{2}-\d{2}\.json$/.test(f))
    .map((f) => ({ f, t: fs.statSync(path.join(opsDir, f)).mtimeMs }))
    .sort((a, b) => b.t - a.t);
  return files[0] || null;
}

/** 用判别层重判 sources[]，重建三态计数与全部派生计数。
 * 兼容旧版快照（sources[] 只有 real_signal/evidence，无 signal_state）：
 * 一律重新判别，绝不沿用旧计数。 */
function normalizeByRule(ds) {
  const raw = Array.isArray(ds.sources) ? ds.sources : [];
  const needsRejudge = raw.some((s) => !s.signal_state);
  const hits = raw.map((s) => ({
    source: s.name || s.source || 'unknown',
    title: s.evidence || s.title || '',
    url: s.url || null,
    created: s.created || null,
  }));
  const { byState, out } = classifyBatch(hits);
  const confirmedItems = out.filter((c) => c.signal_state === 'confirmed');

  ds.sources = toPublicSources(out);
  ds.classification = {
    rule_module: 'scripts/lib/demand_signal_rules.mjs',
    rule:
      '三态 fail-closed：confirmed / unclassified / noise。仅 confirmed 计入 real_query_count；' +
      '不可判定退判 unclassified，绝不默认判真。',
    total_hits: hits.length,
    confirmed: byState.confirmed,
    unclassified: byState.unclassified,
    noise: byState.noise,
    rejudged_from_snapshot: needsRejudge,
  };
  ds.real_query_count = byState.confirmed;
  ds.real_demand_signal_count = byState.confirmed;
  ds.explicit_compatibility_pain = confirmedItems.filter((c) =>
    /compat|flange|替换|互[操相]?作|replacement|interchange/i.test(String(c.title || ''))
  ).length;
  ds.cross_brand_compat_engine_users = confirmedItems.filter((c) =>
    CROSS_BRAND_RE.test(String(c.title || ''))
  ).length;

  const total = hits.length;
  const noiseShare = total ? byState.noise / total : 0;
  ds.retrieval_quality = {
    noise_share: +noiseShare.toFixed(3),
    note: noiseShare > 0.5
      ? '检索词未锚定机器人领域：多数命中被判为非机器人信号，建议收窄检索式（限定 repo: 或补硬件锚词）'
      : '检索词锚定尚可',
  };
  return { byState, needsRejudge, hits };
}

/** 把「数字现算」与「计数重判」合为一步，供 main 与自测共用。 */
/** buildVerdict 的入参契约守卫：declRatePct 必须是**裸数字串**。
 * 只做「防御性剥 %」会把调用方的错误静默补偿掉 —— 两处 bug 互相掩盖，
 * 对外结果看起来是对的，但契约已经破了。故这里 fail-fast：宁可崩，不可假绿。
 * （变异探针 F 即验证：若有人把已带 % 的 pct 传进来，此处必须抛错。） */
function barePct(value, label) {
  const s = String(value);
  if (/%$/.test(s)) {
    throw new Error(`buildVerdict 契约要求裸数字串，${label} 收到 "${s}"（请去掉尾部 %）`);
  }
  return s;
}

function applyFacts(ds, entities) {
  const { applicable, withLead, rate } = mechCoverage(entities);
  // buildVerdict 契约是「裸数字串」（内部自加 %）。此前误传已带 % 的 pct，
  // 对外 verdict 出现「5.75%%」——正是自测只喂裸串才一直没暴露的那种契约不一致假绿。
  const pctNum = (rate * 100).toFixed(2);
  const pct = pctNum + '%';
  const { needsRejudge } = normalizeByRule(ds);
  const aliveSources = Object.values(ds.channels || {})
    .filter((c) => c && c.alive).length;

  ds.can_answer_today = {
    mech_decl_rate: Number(rate.toFixed(4)),
    mech_declared: withLead,
    total_entities: entities.length,
    mech_applicable: applicable,
    estimate: estimateAnswerability(rate),
  };
  ds.verdict = buildVerdict({
    confirmed: ds.real_query_count,
    unclassified: ds.classification.unclassified,
    noise: ds.classification.noise,
    aliveSources,
    totalHits: ds.classification.total_hits,
    declRatePct: barePct(pctNum, 'reflow.applyFacts'),
  });
  // 旧快照的 actionable_fixes 是失效指令（「导入开源人形 BOM 反喂」→ 写 oss_components.json，
  // 与声明率的分母 entities.json 不相通）。对外端点不能继续挂一条做不到的建议，一律覆盖。
  ds.actionable_fixes = buildActionableFixes(rate);
  ds.reflow_note = {
    reflowed_at: new Date().toISOString().slice(0, 10),
    rule_module: 'scripts/lib/demand_signal_rules.mjs',
    note: needsRejudge
      ? '原快照缺 signal_state（旧版格式：real_signal 为写死常量而非判定结果），已按三态判别层重判；'
        + 'real_query_count 现只计 confirmed，旧版「已捕获 N 条真实兼容性提问信号」表述已作废。'
      : '原快照已含 signal_state，仅复核并重算计数。',
  };
  return { rate, pct, applicable, withLead, needsRejudge };
}

function main() {
  const snap = newestSnapshot();
  const base = fs.existsSync(API_DS)
    ? (() => { try { return JSON.parse(fs.readFileSync(API_DS, 'utf8')); } catch { return {}; } })()
    : {};
  let ds;
  if (snap) {
    // 由快照为底本，但**保留 base.meta**：meta.access（领 key 入口）由 inject_api_access.py 注入，
    // 而 deploy 链里该步跑在回流**之后**；若此处整份复制快照，就会把领 key 入口抹掉
    // （回归 L1.14「无对外 JSON 遗漏 meta.access」会判红 —— 本脚本首版实测踩到）。
    // 保留它可让回流与步骤顺序无关，手工单独跑也不会破坏产物。
    const snapshot = JSON.parse(fs.readFileSync(path.join(ROOT, 'ops', snap.f), 'utf8'));
    ds = { ...snapshot };
    if (base.meta && !ds.meta) ds.meta = base.meta;
    if (base.meta && ds.meta) ds.meta = { ...ds.meta, ...base.meta };
    console.log(`   ✅ 需求信号已回流: ${snap.f} → api/demand-signal.json`
      + (ds.meta ? '（保留 meta.access 领 key 入口）' : ''));
  } else if (fs.existsSync(API_DS)) {
    ds = base;
    console.log('   ℹ️ 未发现 ops/demand-signal-*.json，以 api/ 现状为底本原地重算');
  } else {
    console.warn('   ⚠️ 既无快照也无 api/demand-signal.json，跳过（端点将返回 404）');
    return;
  }

  const entities = JSON.parse(fs.readFileSync(API_ENT, 'utf8')).entities || [];
  const before = JSON.stringify({ v: ds.verdict, c: ds.can_answer_today, r: ds.real_query_count });
  const { pct, withLead, applicable, needsRejudge } = applyFacts(ds, entities);

  // 幂等：内容不变则不落盘，避免制造无意义的部署漂移。
  const next = JSON.stringify(ds, null, 2) + '\n';
  if (fs.existsSync(API_DS) && next === fs.readFileSync(API_DS, 'utf8')) {
    console.log(`   ✅ 已是最新（mech 率 ${pct}，${withLead}/${applicable}；`
      + `确认信号 ${ds.real_query_count}/${ds.classification.total_hits}），无需改写`);
    return;
  }
  fs.writeFileSync(API_DS, next);
  console.log(`   ✅ 已按真相源重算 + 按判别层重判（mech 率 ${pct}，${withLead}/${applicable}；`
    + `实体 ${entities.length}；确认 ${ds.real_query_count} / 未判 ${ds.classification.unclassified}`
    + ` / 噪声 ${ds.classification.noise}${needsRejudge ? '；原快照为旧格式，已重判' : ''}`
    + (before === JSON.stringify({ v: ds.verdict, c: ds.can_answer_today, r: ds.real_query_count })
      ? '（仅版面差异）' : '') + ')');
}

// ---------------------------------------------------------------- 自测（离线、不落盘）

/** 旧版格式快照 fixture：real_signal 写死 true、无 signal_state、verdict 宣称 3 条真实提问。
 * 其中只有 1 条是真机器人信号 —— 用来证明回流会把它纠正为 1。 */
function legacySnapshotFixture() {
  return {
    scan_date: '2026-08-28',
    method: 'scripts/demand_scan.mjs 只读监听（旧版）。绝不发帖。',
    channels: { github: { label: 'GitHub Issues/PRs', alive: true, status: 200, err: null, hit_count: 3 } },
    real_query_count: 3,
    explicit_compatibility_pain: 3,
    cross_brand_compat_engine_users: 0,
    verdict: '已捕获 3 条真实兼容性提问信号（跨品牌引擎潜在用户 0 条）。',
    sources: [
      { name: 'github', url: 'https://example.invalid/1', signal_type: '社区兼容性提问', real_signal: true, evidence: 'declare C and C-unwind as mutually ABI-compatible' },
      { name: 'github', url: 'https://example.invalid/2', signal_type: '社区兼容性提问', real_signal: true, evidence: 'humanoid robot shoulder joint flange not interchangeable across brands' },
      { name: 'ros_discourse', url: 'https://example.invalid/3', signal_type: '社区兼容性提问', real_signal: true, evidence: 'Which versions are compatible with this release?' },
    ],
    meta: { access: { note: '领 key 入口，回流不得抹掉' } },
  };
}

function selfTest() {
  let passed = 0;
  const failures = [];
  function check(name, cond, detail = '') {
    if (cond) passed += 1;
    else failures.push(name + (detail ? ' — ' + detail : ''));
  }

  // 声明率口径（唯一）：含 n_a 与缺字段两种边界，rate 落到 <5% 分支
  const ents = [
    { mechanical_interface: { status: 'declared' } },
    ...Array.from({ length: 24 }, () => ({ mechanical_interface: { status: 'not_declared' } })),
    { mechanical_interface: { status: 'n_a' } },
    {},
  ];
  const mc = mechCoverage(ents);
  check('口径·分母只算 applicable（n_a 与未知均不计入，=26）',
    mc.applicable === 26, JSON.stringify(mc.cnt));
  check('口径·缺 mechanical_interface 的实体按「适用但未声明」处理',
    mc.cnt.not_declared === 25, JSON.stringify(mc.cnt));
  check('口径·分子含 partial（此处无 partial，=1）', mc.withLead === 1, String(mc.withLead));
  check('口径·rate=1/26', Math.abs(mc.rate - 1 / 26) < 1e-9, String(mc.rate));

  const ds = legacySnapshotFixture();
  applyFacts(ds, ents);

  check('重判·旧快照被识别为需重判', ds.classification.rejudged_from_snapshot === true);
  check('计数·real_query_count 从 3 纠正为 1（只计 confirmed）',
    ds.real_query_count === 1, '实得 ' + ds.real_query_count);
  check('计数·real_demand_signal_count 同步为 1', ds.real_demand_signal_count === 1);
  check('计数·noise=1（ABI-compatible 软件 PR）', ds.classification.noise === 1,
    JSON.stringify(ds.classification));
  check('计数·unclassified=1（领域源无锚词）', ds.classification.unclassified === 1);
  check('计数·total_hits=3', ds.classification.total_hits === 3);
  check('计数·三态之和 = total_hits',
    ds.classification.confirmed + ds.classification.unclassified + ds.classification.noise
      === ds.classification.total_hits);
  check('字段·sources.real_signal 与 signal_state 一致',
    ds.sources.every((s) => s.real_signal === (s.signal_state === 'confirmed')));
  check('字段·唯一 confirmed 是那条硬件锚定的真信号',
    ds.sources.filter((s) => s.real_signal).length === 1
      && /humanoid/.test(ds.sources.find((s) => s.real_signal).evidence));
  check('字段·noise 条目 real_signal=false',
    ds.sources.filter((s) => s.signal_state === 'noise').every((s) => s.real_signal === false));
  check('字段·保留向后兼容字段 name/url/signal_type/evidence/relevance',
    ds.sources.every((s) => 'name' in s && 'url' in s && 'signal_type' in s
      && 'evidence' in s && 'relevance' in s));
  check('字段·relevance 不再是写死的「需判别」占位',
    ds.sources.every((s) => !/需判别/.test(s.relevance)));

  check('verdict·不再宣称「真实兼容性提问信号」', !/真实兼容性提问/.test(ds.verdict));
  // 阳性对照：reflow 曾把已带 % 的 pct 传给 buildVerdict，对外出现「3.85%%」。
  // 自测若只喂裸串就永远看不见——所以这里直接验最终产物，不验入参。
  check('verdict·无 %% 双百分号（对外可见产物级校验）',
    !/%%/.test(ds.verdict), ds.verdict.slice(0, 200));
  check('verdict·声明率百分号出现恰好一次',
    (ds.verdict.match(/%/g) || []).length === 1, ds.verdict.slice(0, 200));

  // actionable_fixes 必须被覆盖：旧快照里的「开源人形 BOM 反喂」是做不到的一条
  // 注意：这里必须空值安全 —— 若上游被改坏成 undefined，应当报失败而不是抛异常，
  // 否则变异探针看到的会是「崩了」而不是「哪条断言失败」。
  const fixes = Array.isArray(ds.actionable_fixes) ? ds.actionable_fixes : [];
  const fixesText = fixes.join('');
  check('fixes·存在且非空', fixes.length > 0, JSON.stringify(ds.actionable_fixes));
  check('fixes·覆盖旧快照的失效指令（不再提「反喂 ingestion」）',
    !fixes.some((f) => /反喂 ingestion/.test(f)), JSON.stringify(ds.actionable_fixes));
  check('fixes·指出合法通道 datasheet / ISO 9409-1 / 用户提交',
    /datasheet/.test(fixesText) && /ISO 9409-1/.test(fixesText) && /用户提交/.test(fixesText));
  check('fixes·明示 oss_components.json 与 entities.json 两条链路不相通',
    /oss_components\.json/.test(fixesText) && /entities\.json/.test(fixesText));
  check('fixes·低声明率时追加「先证明需求再投数据采集」',
    /先证明需求/.test(fixesText));

  // barePct 契约守卫的阴阳对照：裸串放行、带 % 的串必须抛错
  check('契约·barePct 放行裸数字串', barePct('5.75', 'selftest') === '5.75');
  let threwOnPct = false;
  try {
    barePct('5.75%', 'selftest');
  } catch (e) {
    threwOnPct = /契约要求裸数字串/.test(String(e.message));
  }
  check('契约·barePct 对已带 % 的串 fail-fast（不让 bug 被静默补偿）', threwOnPct);
  check('verdict·给出三态计数',
    /确认兼容性提问 1 条/.test(ds.verdict)
      && /未判 1 条/.test(ds.verdict) && /非机器人信号 1 条/.test(ds.verdict));
  check('verdict·引用重算后的声明率（3.85%）', /3\.85%/.test(ds.verdict), ds.verdict);
  check('verdict·声明率由 buildVerdict 生成而非正则替换',
    !/已捕获 \d+ 条/.test(ds.verdict));

  check('estimate·低声明率走「极低」分支', /极低/.test(ds.can_answer_today.estimate));
  check('estimate·不宣称开源 BOM 反喂 ingestion', !/反喂 ingestion/.test(ds.can_answer_today.estimate));
  check('estimate·给出合法通道 datasheet/ISO/用户提交',
    /datasheet/.test(ds.can_answer_today.estimate) && /ISO 9409-1/.test(ds.can_answer_today.estimate));
  check('estimate·披露分母 mech_applicable',
    ds.can_answer_today.mech_applicable === mc.applicable);

  check('retrieval_quality·noise_share=1/3', ds.retrieval_quality.noise_share === 0.333,
    String(ds.retrieval_quality.noise_share));

  check('留痕·reflow_note 记录重判与规则模块',
    /重判/.test(ds.reflow_note.note)
      && ds.reflow_note.rule_module === 'scripts/lib/demand_signal_rules.mjs');
  check('留痕·meta.access 未被抹掉',
    ds.meta && ds.meta.access && /领 key 入口/.test(ds.meta.access.note));

  // 幂等：二次回流结果一致
  const once = JSON.stringify({ s: ds.sources, v: ds.verdict, r: ds.real_query_count });
  applyFacts(ds, ents);
  const twice = JSON.stringify({ s: ds.sources, v: ds.verdict, r: ds.real_query_count });
  check('幂等·二次回流结果一致', once === twice);

  // 空 sources 快照：不得产出假计数（通道存活、命中为零 → 零确认分支）
  const empty = { channels: { github: { label: 'GitHub Issues/PRs', alive: true, hit_count: 0 } }, sources: [] };
  applyFacts(empty, ents);
  check('空快照·real_query_count=0 且三态全零',
    empty.real_query_count === 0 && empty.classification.total_hits === 0);
  check('空快照·verdict 走零确认分支且不宣称真实提问',
    !/真实兼容性提问/.test(empty.verdict) && /零确认信号/.test(empty.verdict));

  // 通道全不可达
  const dead = { channels: { github: { alive: false } }, sources: [] };
  applyFacts(dead, ents);
  check('UNKNOWN·通道全不可达时 verdict 标 UNKNOWN 且不推断零需求',
    /UNKNOWN/.test(dead.verdict) && /不推断需求为零/.test(dead.verdict));

  if (failures.length) {
    console.log('\n[需求信号回流器（reflow_demand_signal）]');
    console.log(`  ❌ ${failures.length} 项未通过（通过 ${passed} 项）`);
    for (const f of failures) console.log('     - ' + f);
    return false;
  }
  console.log(`\n[需求信号回流器（reflow_demand_signal）]  ✅ 全部通过（${passed} 项）`);
  return true;
}

const argv = process.argv.slice(2);
if (argv.includes('--self-test')) {
  process.exit(selfTest() ? 0 : 1);
}
main();
