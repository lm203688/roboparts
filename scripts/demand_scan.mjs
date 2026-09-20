#!/usr/bin/env node
/**
 * demand_scan.mjs —— 飞轮监听层(H2)：只读扫社区真实兼容性提问 → 判别 → 度量 → 结构化输出。
 *
 * 纪律（飞轮 L 阶段「口径 ≠ 事实」反复踩坑后定）：
 *   1. **只读、绝不发帖**。本脚本是「需求是否存在」的仪器，不是广播工具。
 *      响应层（回帖/发 issue）一律人工闸门，绝不经此自动发出。
 *   2. **通道存活探测优先于计数**。某源 fetch 失败（status=0 / 不可达）→ 标记
 *      channel_alive=false，**绝不把「通道死了」当成「需求为零」**（这是空表假绿的
 *      经典陷阱：ndls 返回挑战页→total=0→0==0→complete=True 的翻版）。
 *   3. **数字现算，不写死**。声明率从 entities.json 实时统计，不手填常量。
 *   4. 判「能否答」基于机械接口声明率诚实推断：声明率 <5% → 跨品牌兼容类提问
 *      今天绝大多数答不出，如实标注「需求存在、供给不足」，不粉饰。
 *   5. **三态 fail-closed，绝不默认判真**（2026-09-20 事故后定）。旧版本
 *      `real_signal: true` 是写死常量而非判定结果，导致 GitHub 源的
 *      "OpenAI-compatible providers"、"ABI-compatible"、"GEMM replacement" 类
 *      软件 PR 被计为真实机器人零件提问，公开端点因此对外宣称了 10 条不存在的
 *      信号。判别层现统一在 scripts/lib/demand_signal_rules.mjs：confirmed /
 *      unclassified / noise，只有 confirmed 才计入 real_query_count。
 *      本文件不得自行决定 real_signal —— 那是判别层的唯一职责。
 *
 * 用法：
 *   node scripts/demand_scan.mjs                 # 扫三源、写 ops/demand-signal-YYYYMMDD.json
 *   node scripts/demand_scan.mjs --json          # 写完再打印机读摘要
 *   node scripts/demand_scan.mjs --self-test     # 阴阳对照（离线 fixture，不联网、不落盘）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  classifyBatch, toPublicSources, buildVerdict, estimateAnswerability,
  buildActionableFixes, CROSS_BRAND_RE,
} from './lib/demand_signal_rules.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'ops');

// ---- 真值源现算（绝不写死数字） ----
const entitiesData = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'api', 'entities.json'), 'utf8')
);
const entities = entitiesData.entities || [];
const totalEntities = entities.length;

// 机械接口声明率：status ∈ {declared, partial} 才算有声明；not_declared / n_a 是显式缺口。
// 注意：字段是对象 {status, mount_type, ...}，不能拿整串去匹配（declared 对象里
// standard:null 会被粗正则误判成缺口）。只取 .status。
function mechStatus(e) {
  const mi = e.mechanical_interface;
  if (!mi || typeof mi !== 'object') return null;
  return mi.status;
}
const mechDeclared = entities.filter((e) => {
  const s = mechStatus(e);
  return s === 'declared' || s === 'partial';
}).length;
// 分母必须是 applicable（declared + partial + not_declared），与正统口径
// （onboarding_block.facts()['mech_pct'] / add_mechanical_interface.py）同源。
// 【20260915 事故】此处原为 totalEntities（全库 798）→ 25/798 = 3.13%，
// 与对外口径 25/435 = 5.75% 不一致；这是同一指标的**第三套分母**。
// 脚本注释写着「数字现算、不写死」，但现算了却用错分母 —— 现算 ≠ 同源。
const mechApplicable = entities.filter((e) => {
  const s = mechStatus(e);
  return s === 'declared' || s === 'partial' || s === 'not_declared';
}).length;
const mechDeclRate = mechApplicable ? mechDeclared / mechApplicable : 0;

const cats = {};
entities.forEach((e) => {
  if (e.category) cats[e.category] = (cats[e.category] || 0) + 1;
});

// ---- 社区源（带通道存活探测） ----
// PAIN_RE 只是 fetch 层的**预筛**（把明显无关的条目先筛掉，减小载荷），
// 它不是判别：「标题里有兼容词」≠「这是机器人零件的兼容提问」。
// 三态判别统一在 lib/demand_signal_rules.mjs，本文件不得据此决定 real_signal。
const PAIN_RE = /compat|interchange|flange|适配|替换|互[操相]?作|cross[- ]?brand|replacement|mounting|可?互?换/gi;

const SOURCES = [
  {
    name: 'github',
    label: 'GitHub Issues/PRs',
    url:
      'https://api.github.com/search/issues?q=robot+OR+humanoid+(flange+OR+compatible+OR+interchangeable+OR+replacement)+in:title&per_page=20&sort=updated&order=desc',
    parse: (j) => {
      const d = JSON.parse(j);
      return (d.items || []).map((i) => ({
        title: i.title,
        url: i.html_url,
        created: i.created_at,
      }));
    },
  },
  {
    name: 'ros_discourse',
    label: 'Open Robotics Discourse',
    url:
      'https://discourse.openrobotics.org/search.json?q=compatible+OR+flange+OR+replacement&limit=20',
    parse: (j) => {
      const d = JSON.parse(j);
      const posts = d.posts || [];
      return posts.map((p) => ({
        title: p.topic_title || p.blurb || '',
        url: 'https://discourse.openrobotics.org/t/' + p.topic_id,
        created: null,
      }));
    },
  },
  {
    name: 'stack_exchange',
    label: 'Robotics Stack Exchange',
    url:
      'https://api.stackexchange.com/2.3/search?order=desc&sort=activity&intitle=robot+compatible+OR+flange&site=robotics&pagesize=20',
    parse: (j) => {
      const d = JSON.parse(j);
      return (d.items || []).map((i) => ({
        title: i.title,
        url: i.link,
        created: i.creation_date ? new Date(i.creation_date * 1000).toISOString() : null,
      }));
    },
  },
  {
    // 沙箱实测 fetch failed（反爬/出口限制），标记优雅降级：不计入零需求。
    name: 'reddit',
    label: 'Reddit r/robotics',
    url: 'https://www.reddit.com/r/robotics/search.json?q=compatible&limit=20&sort=new',
    parse: (j) => {
      const d = JSON.parse(j);
      const ch = (d.data && d.data.children) || [];
      return ch.map((c) => ({
        title: c.data.title,
        url: 'https://reddit.com' + c.data.permalink,
        created: null,
      }));
    },
    known_blocked: true,
  },
];

async function fetchWithTimeout(url, ms = 15000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  try {
    const r = await fetch(url, {
      headers: { 'user-agent': 'roboparts-demand-scan/1.0 (automation)' },
      signal: ctrl.signal,
    });
    const txt = await r.text();
    return { ok: r.ok, status: r.status, text: txt, err: null };
  } catch (e) {
    return { ok: false, status: 0, text: '', err: e.message };
  } finally {
    clearTimeout(t);
  }
}

function buildReport({ channels, classified, today, selfTest = false }) {
  const { byState, out } = classified;
  const confirmedItems = out.filter((c) => c.signal_state === 'confirmed');
  const aliveSources = Object.values(channels).filter((c) => c.alive).length;

  // real_query_count 只计 confirmed；unclassified / noise 一律不计（fail-closed）。
  const real_query_count = byState.confirmed;
  const cross_brand = confirmedItems.filter((c) =>
    CROSS_BRAND_RE.test(String(c.title || ''))
  ).length;
  const explicit_pain = confirmedItems.filter((c) =>
    /compat|flange|替换|互[操相]?作|replacement|interchange/i.test(String(c.title || ''))
  ).length;

  // can_answer_today 基于声明率诚实估算（不粉饰）
  const can_answer_today = {
    mech_decl_rate: +mechDeclRate.toFixed(4),
    mech_declared: mechDeclared,
    mech_applicable: mechApplicable,
    total_entities: totalEntities,
    estimate: estimateAnswerability(mechDeclRate),
  };

  const verdict = buildVerdict({
    confirmed: byState.confirmed,
    unclassified: byState.unclassified,
    noise: byState.noise,
    aliveSources,
    totalHits: out.length,
    declRatePct: (mechDeclRate * 100).toFixed(2),
  });

  const total = out.length;
  const noiseShare = total ? byState.noise / total : 0;

  return {
    scan_date: today,
    method:
      'scripts/demand_scan.mjs 只读监听（GitHub/ROS/Stack 可达；Reddit 沙箱不可达已降级）。绝不发帖。' +
      (selfTest ? ' [SELF-TEST]' : ''),
    channels,
    // 判别层留痕：让消费方能看出「抓到 N 条」与「确认 N 条」是两回事
    classification: {
      rule_module: 'scripts/lib/demand_signal_rules.mjs',
      rule:
        '三态 fail-closed：confirmed / unclassified / noise。仅 confirmed 计入 real_query_count；' +
        '不可判定退判 unclassified，绝不默认判真。',
      total_hits: total,
      confirmed: byState.confirmed,
      unclassified: byState.unclassified,
      noise: byState.noise,
    },
    retrieval_quality: {
      noise_share: +noiseShare.toFixed(3),
      note: noiseShare > 0.5
        ? '检索词未锚定机器人领域：多数命中被判为非机器人信号，建议收窄检索式（限定 repo: 或补硬件锚词）'
        : '检索词锚定尚可',
    },
    real_query_count,
    explicit_compatibility_pain: explicit_pain,
    cross_brand_compat_engine_users: cross_brand,
    can_answer_today,
    category_counts: cats,
    verdict,
    // 实际命中（可追溯；兼容 20260814 版 sources 字段名，并新增 signal_state）
    sources: toPublicSources(out.slice(0, 50)),
    // 沿用 20260814 版字段名，兼容既有消费方
    real_demand_signal_count: real_query_count,
    // 合法通道清单走共享真相源（reflow 也调同一函数），不在此处手写第二份
    actionable_fixes: buildActionableFixes(mechDeclRate),
  };
}

/** --self-test 用的离线 fixture：不联网、不落盘。
 * 覆盖三态：历史噪声（应判 noise）/ 真信号（应判 confirmed）/ 领域源无锚词（应判 unclassified）。
 * 这些不是「编造的需求」——它们是可复现的判别基准：历史噪声逐条来自
 * 2026-08-16/28 真实快照，真信号用于证明阳性通道没被写死为假。 */
const SELFTEST_HITS = [
  { source: 'github', title: 'declare C and C-unwind as mutually ABI-compatible', url: 'https://example.invalid/1', created: null },
  { source: 'github', title: '[HIP] [FlyDSL] [Kernel] Extend MXFP4 GEMM1 replacement to A4W4', url: 'https://example.invalid/2', created: null },
  { source: 'github', title: 'feat: stream compatible Chat completions', url: 'https://example.invalid/3', created: null },
  { source: 'github', title: 'humanoid robot shoulder joint flange not interchangeable across brands', url: 'https://example.invalid/4', created: null },
  { source: 'reddit', title: '舵机延长线不兼容，需要替代品', url: 'https://example.invalid/5', created: null },
  { source: 'ros_discourse', title: 'Which versions are compatible with this release?', url: 'https://example.invalid/6', created: null },
];

/** 报告组装自测：验证三态计数、字段一致性、三条 verdict 分支。全部离线。 */
function selfTestReport() {
  let passed = 0;
  const failures = [];
  function check(name, cond, detail = '') {
    if (cond) passed += 1;
    else failures.push(name + (detail ? ' — ' + detail : ''));
  }

  const channels = {};
  for (const s of SOURCES) {
    channels[s.name] = { label: s.label, alive: false, status: null, err: null, hit_count: 0 };
  }
  channels.github.alive = true;
  channels.github.hit_count = 4;
  channels.reddit.alive = true;
  channels.reddit.hit_count = 1;
  channels.ros_discourse.alive = true;
  channels.ros_discourse.hit_count = 1;

  const report = buildReport({
    channels,
    classified: classifyBatch(SELFTEST_HITS),
    today: '2026-09-20',
    selfTest: true,
  });

  check('计数·real_query_count 只计 confirmed（=2）',
    report.real_query_count === 2, '实得 ' + report.real_query_count);
  check('计数·noise=3（历史噪声全部被拦）',
    report.classification.noise === 3, JSON.stringify(report.classification));
  check('计数·unclassified=1（领域源无锚词）',
    report.classification.unclassified === 1, JSON.stringify(report.classification));
  check('计数·total_hits=6',
    report.classification.total_hits === 6, String(report.classification.total_hits));
  check('计数·三态之和 = total_hits',
    report.classification.confirmed + report.classification.unclassified
      + report.classification.noise === report.classification.total_hits);
  check('字段·real_demand_signal_count 与 real_query_count 一致',
    report.real_demand_signal_count === report.real_query_count);
  check('字段·cross_brand 只在 confirmed 内计数',
    report.cross_brand_compat_engine_users <= report.real_query_count);
  check('字段·sources.real_signal 与 signal_state 一致',
    report.sources.every((s) => s.real_signal === (s.signal_state === 'confirmed')));
  check('字段·历史噪声无一被判成 confirmed',
    report.sources.filter((s) => s.real_signal).every((s) =>
      !/ABI-compatible|GEMM1|Chat completions/.test(s.evidence)));
  check('字段·relevance 不再是写死的「需判别」占位',
    report.sources.every((s) => !/需判别/.test(s.relevance)));
  check('字段·estimate 不再宣称开源 BOM 反喂 ingestion',
    !/反喂 ingestion/.test(report.can_answer_today.estimate));
  check('字段·can_answer_today 披露分母 mech_applicable',
    Number.isInteger(report.can_answer_today.mech_applicable));
  check('verdict·confirmed>0 时给出三态计数',
    /确认兼容性提问 2 条/.test(report.verdict)
      && /未判 1 条/.test(report.verdict) && /非机器人信号 3 条/.test(report.verdict));
  check('verdict·不再用「已捕获 N 条真实兼容性提问信号」句式',
    !/已捕获 \d+ 条真实兼容性提问信号/.test(report.verdict));

  // 分支一：通道全不可达 → UNKNOWN，绝不把「通道死了」当「需求为零」
  const deadChannels = {};
  for (const s of SOURCES) {
    deadChannels[s.name] = {
      label: s.label, alive: false, status: 0,
      err: 'SELF-TEST: 模拟通道不可达', hit_count: 0,
    };
  }
  const deadReport = buildReport({
    channels: deadChannels,
    classified: classifyBatch([]),
    today: '2026-09-20',
    selfTest: true,
  });
  check('UNKNOWN·通道全不可达时 verdict 标 UNKNOWN', /UNKNOWN/.test(deadReport.verdict));
  check('UNKNOWN·不推断需求为零', /不推断需求为零/.test(deadReport.verdict));
  check('UNKNOWN·real_query_count=0 且不宣称「未捕获提问」',
    deadReport.real_query_count === 0 && !/本轮未捕获明确兼容性提问/.test(deadReport.verdict));

  // 分支二：通道存活但零确认 → 不得宣称真实提问，须明示历史误判成因
  const zeroReport = buildReport({
    channels: {
      github: { label: 'GitHub Issues/PRs', alive: true, status: 200, err: null, hit_count: 3 },
    },
    classified: classifyBatch(SELFTEST_HITS.filter((h) => !/humanoid|舵机/.test(h.title))),
    today: '2026-09-20',
    selfTest: true,
  });
  check('零确认·不宣称「真实兼容性提问」', !/真实兼容性提问/.test(zeroReport.verdict));
  check('零确认·明示零确认与历史误判成因',
    /零确认信号/.test(zeroReport.verdict) && /real_signal=true/.test(zeroReport.verdict));

  if (failures.length) {
    console.log('\n[demand_scan 报告组装]');
    console.log(`  ❌ ${failures.length} 项未通过（通过 ${passed} 项）`);
    for (const f of failures) console.log('     - ' + f);
    return false;
  }
  console.log(`\n[demand_scan 报告组装]  ✅ 全部通过（${passed} 项）`);
  return true;
}

async function main() {
  const selfTest = process.argv.includes('--self-test');
  const asJson = process.argv.includes('--json');
  const today = new Date().toISOString().slice(0, 10);

  if (selfTest) {
    // 自测走离线 fixture：CI 无外网不能依赖 fetch；且不落盘，避免污染 ops 快照。
    const ok = selfTestReport();
    process.exit(ok ? 0 : 1);
  }

  const channels = {};
  const allHits = [];

  for (const src of SOURCES) {
    channels[src.name] = {
      label: src.label,
      alive: false,
      status: null,
      err: null,
      hit_count: 0,
    };
    if (selfTest || src.known_blocked) {
      channels[src.name].alive = false;
      channels[src.name].err = selfTest
        ? 'SELF-TEST: 模拟通道不可达'
        : 'known_blocked_in_sandbox (fetch failed) — 不计入零需求';
      continue;
    }
    const res = await fetchWithTimeout(src.url);
    channels[src.name].status = res.status;
    if (!res.ok || res.err) {
      channels[src.name].alive = false;
      channels[src.name].err = res.err || 'HTTP ' + res.status;
      continue; // 不可达 → 不判零
    }
    try {
      const items = src.parse(res.text);
      channels[src.name].alive = true;
      channels[src.name].hit_count = items.length;
      items.forEach((it) => {
        if (it.title && PAIN_RE.test(it.title)) {
          allHits.push({ source: src.name, title: it.title, url: it.url, created: it.created });
        }
      });
    } catch (e) {
      channels[src.name].alive = false;
      channels[src.name].err = 'parse_error: ' + e.message;
    }
  }

  const classified = classifyBatch(allHits);
  const report = buildReport({ channels, classified, today });
  const outPath = path.join(OUT_DIR, `demand-signal-${today}.json`);
  fs.writeFileSync(outPath, JSON.stringify(report, null, 2));

  console.log('✅ demand_scan 完成 → ' + outPath);
  console.log(
    '  可达源=' +
      Object.values(channels).filter((c) => c.alive).length +
      '/' +
      SOURCES.length +
      '  命中=' +
      report.classification.total_hits +
      '  确认=' +
      report.classification.confirmed +
      '  未判=' +
      report.classification.unclassified +
      '  噪声=' +
      report.classification.noise +
      '  跨品牌=' +
      report.cross_brand_compat_engine_users +
      '  声明率=' +
      (mechDeclRate * 100).toFixed(2) +
      '%'
  );
  console.log('  verdict: ' + report.verdict);
  if (process.argv.includes('--json')) console.log(JSON.stringify(report, null, 2));
  return report;
}

main().catch((e) => {
  console.error('demand_scan 异常:', e);
  process.exit(1);
});
