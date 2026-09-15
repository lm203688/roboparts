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
 * 本脚本做两件事，顺序不可换：
 *   1) 取 ops 里最新的 demand-signal-*.json 复制到 api/（保住历史信号块）；
 *   2) 用 api/entities.json（单一真相源）**重算**现算块：
 *        can_answer_today.{mech_decl_rate, mech_declared, total_entities, mech_applicable}
 *        verdict 里的「机械接口声明率仅 X%」
 *      重算口径 = (declared + partial) / (declared + partial + not_declared)
 *      —— 与 scripts/add_mechanical_interface.py 及 onboarding_block.facts() 同式。
 *
 * 纪律：本脚本只做「重算 + 覆盖现算字段」，不新增键、不改历史信号块、不编造数字。
 * 无快照可复制时以 api/ 现状为底本原地重算（端点不会因此 404）。
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

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
  const { applicable, withLead, rate } = mechCoverage(entities);
  const pct = (rate * 100).toFixed(2) + '%';

  const before = JSON.stringify(ds.can_answer_today || {});
  ds.can_answer_today = {
    mech_decl_rate: Number(rate.toFixed(4)),
    mech_declared: withLead,
    total_entities: entities.length,
    mech_applicable: applicable,
    estimate: '部分可答：跨品牌兼容类提问多数仍答不出（需真实 BOM 反喂抬声明率）',
  };
  if (typeof ds.verdict === 'string') {
    ds.verdict = ds.verdict.replace(/机械接口声明率仅\s*[\d.]+%/, '机械接口声明率仅 ' + pct);
  }

  // 幂等：内容不变则不落盘，避免制造无意义的部署漂移。
  const after = JSON.stringify(ds.can_answer_today);
  const orig = fs.readFileSync(API_DS, 'utf8');
  const next = JSON.stringify(ds, null, 2) + '\n';
  if (next === orig) {
    console.log(`   ✅ 现算块已是最新（mech 率 ${pct}，${withLead}/${applicable}），无需改写`);
    return;
  }
  fs.writeFileSync(API_DS, next);
  console.log(`   ✅ 现算块已按真相源重算（mech 率 ${pct}，${withLead}/${applicable}；`
    + `实体 ${entities.length}）${before === after ? '（仅版面差异）' : ''}`);
}

main();
