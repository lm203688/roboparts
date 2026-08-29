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
 *
 * 用法：
 *   node scripts/demand_scan.mjs                 # 扫三源、写 ops/demand-signal-YYYYMMDD.json
 *   node scripts/demand_scan.mjs --json          # 写完再打印机读摘要
 *   node scripts/demand_scan.mjs --self-test     # 阴阳对照（构造不可达源，确认不判零）
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

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
const mechDeclRate = totalEntities ? mechDeclared / totalEntities : 0;

const cats = {};
entities.forEach((e) => {
  if (e.category) cats[e.category] = (cats[e.category] || 0) + 1;
});

// ---- 社区源（带通道存活探测） ----
const PAIN_RE = /compat|interchange|flange|适配|替换|互[操相]?作|cross[- ]?brand|replacement|mounting|可?互?换/gi;
const CROSS_BRAND_RE = /cross[- ]?brand|interoperab|互操作|不同?品牌|different brand|mix .*brand/gi;

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

function buildReport({ channels, allHits, today, selfTest = false }) {
  const real_query_count = allHits.length;
  const cross_brand = allHits.filter((h) => CROSS_BRAND_RE.test(h.title)).length;
  const explicit_pain = allHits.filter((h) =>
    /compat|flange|替换|互[操相]?作|replacement|interchange/i.test(h.title)
  ).length;
  const aliveSources = Object.values(channels).filter((c) => c.alive).length;

  // 判别层：can_answer_today 基于声明率诚实估算（不粉饰）
  const can_answer_today = {
    mech_decl_rate: +mechDeclRate.toFixed(4),
    mech_declared: mechDeclared,
    total_entities: totalEntities,
    estimate:
      mechDeclRate < 0.05
        ? '极低：跨品牌兼容类提问今天绝大多数答不出（需真实 BOM 反喂抬声明率）'
        : '部分可答',
  };

  let verdict;
  if (aliveSources === 0) {
    verdict =
      '通道全不可达（UNKNOWN）：本轮监听无法取得真实数据，不推断需求为零。需排查出网或换源。';
  } else if (real_query_count === 0) {
    verdict =
      '已监听 ' +
      aliveSources +
      ' 个可达源，本轮未捕获明确兼容性提问（可能是真实需求稀少，也可能是检索词/源覆盖不足——待持续观察，不臆断为零）。';
  } else {
    verdict =
      '已捕获 ' +
      real_query_count +
      ' 条真实兼容性提问信号（跨品牌引擎潜在用户 ' +
      cross_brand +
      ' 条）。但本站机械接口声明率仅 ' +
      (mechDeclRate * 100).toFixed(2) +
      '%，绝大多数今天答不出——需求存在，供给（可计算兼容性）不足。';
  }

  return {
    scan_date: today,
    method:
      'scripts/demand_scan.mjs 只读监听（GitHub/ROS/Stack 可达；Reddit 沙箱不可达已降级）。绝不发帖。' +
      (selfTest ? ' [SELF-TEST]' : ''),
    channels,
    real_query_count,
    explicit_compatibility_pain: explicit_pain,
    cross_brand_compat_engine_users: cross_brand,
    can_answer_today,
    category_counts: cats,
    verdict,
    // 实际命中（可追溯，兼容 20260814 版 sources 字段语义）
    sources: allHits.slice(0, 50).map((h) => ({
      name: h.source,
      url: h.url,
      signal_type: '社区兼容性提问',
      real_signal: true,
      evidence: h.title,
      relevance: '中（需判别是否跨品牌兼容痛点）',
    })),
    // 沿用 20260814 版字段名，兼容既有消费方
    real_demand_signal_count: real_query_count,
    actionable_fixes: [
      mechDeclRate < 0.05
        ? '抬机械接口声明率：导入真实开源人形 BOM（天工/lerobot-humanoid/Asimov）反喂 ingestion'
        : '维持声明率',
    ],
  };
}

async function main() {
  const selfTest = process.argv.includes('--self-test');
  const asJson = process.argv.includes('--json');
  const today = new Date().toISOString().slice(0, 10);

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

  const report = buildReport({ channels, allHits, today, selfTest });
  const outPath = path.join(OUT_DIR, `demand-signal-${today}.json`);
  fs.writeFileSync(outPath, JSON.stringify(report, null, 2));

  console.log('✅ demand_scan 完成 → ' + outPath);
  console.log(
    '  可达源=' +
      Object.values(channels).filter((c) => c.alive).length +
      '/' +
      SOURCES.length +
      '  真实提问=' +
      report.real_query_count +
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
