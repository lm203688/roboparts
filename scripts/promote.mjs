#!/usr/bin/env node
/**
 * RoboParts 自动推广脉冲（promotion pulse）
 * 每次部署后由 deploy.mjs 调用，也可单独 `node scripts/promote.mjs` 运行。
 *
 * 自动化的部分（无需人工）：
 *  1) IndexNow 重提（Bing/必应 + Yandex 等下游）—— 让新页面/改动的页面尽快被收录
 *  2) Google / Bing sitemap ping
 *  3) 把各 MCP / llms.txt 目录的「提交入口」与当前端点信息写入推广日志（供飞轮/人工一键提交）
 *
 * 不自动化的部分（社区禁自动化发帖）：知乎/CSDN/Reddit/HN 等社区投稿，
 * 只在本脚本的日志里给出回链文案与提交入口，由用户或飞轮（带人工确认）发起。
 *
 * 2026-09-01 飞轮幂等/可恢复治理（signal→candidate→promote→effect）：
 *  - 新增「效果台账」ops/promotion/ledger.json：按日期幂等记录本轮推广结果
 *    （OpenClaw 的 effect 阶段有了可度量痕迹，重跑同日只覆盖不重复）。
 *  - 通过 scripts/flywheel_state.py record promote 写入阶段状态，
 *    使 promote 阶段纳入统一的可恢复/幂等台账。
 *  - 导出纯函数 fingerprintUrls / buildPromoEntry（供 scripts/test_promote_ledger.mjs 测试）。
 */
import { readFileSync, mkdirSync, writeFileSync, renameSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { checkHostParity } from './verify_host_parity.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const HOST = 'roboparts.cc';
const KEY = 'roboparts2026indexnow';
const KEY_LOC = `https://${HOST}/roboparts2026indexnow.txt`;
const SITE = `https://${HOST}`;
const FLYWHEEL_STATE = join(ROOT, 'scripts', 'flywheel_state.py');
const LEDGER = join(ROOT, 'ops', 'promotion', 'ledger.json');

const log = [];
const note = (s) => { console.log(s); log.push(s); };

/** 纯函数：URL 集合的稳定指纹（顺序无关）。 */
export function fingerprintUrls(urls) {
  const h = createHash('sha256');
  for (const u of [...urls].sort()) h.update(u);
  return h.digest('hex').slice(0, 16);
}

/** 纯函数：构造一条效果台账条目（供幂等覆盖 + 测试）。 */
export function buildPromoEntry(site, urlCount, engineResults) {
  return {
    date: new Date().toISOString().slice(0, 10),
    site,
    url_count: urlCount,
    engines: engineResults,
    generated_at: new Date().toISOString(),
  };
}

async function getSitemapUrls() {
  try {
    const xml = readFileSync(join(ROOT, 'sitemap.xml'), 'utf8');
    return [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1].trim()).filter(Boolean);
  } catch (e) { note('[warn] 读 sitemap.xml 失败: ' + e.message); return []; }
}

const lastResults = {};   // 本轮各引擎结果，供效果台账使用

async function indexNow(urls) {
  if (!urls.length) return;
  const body = JSON.stringify({ host: HOST, key: KEY, keyLocation: KEY_LOC, urlList: urls });
  try {
    const r = await fetch('https://api.indexnow.org/indexnow', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
    });
    lastResults.indexnow = r.status;
    note(`[IndexNow] HTTP ${r.status} · 提交 ${urls.length} 条 URL` + (r.status === 200 ? ' ✅' : ' ⚠️'));
  } catch (e) { lastResults.indexnow = 'fail'; note('[IndexNow] 请求失败: ' + e.message); }
}

async function pingSitemap(engine, base) {
  const url = `${base}?sitemap=${encodeURIComponent(SITE + '/sitemap.xml')}`;
  try {
    const r = await fetch(url, { method: 'GET', redirect: 'follow' });
    lastResults[engine.toLowerCase()] = r.status;
    note(`[ping ${engine}] HTTP ${r.status} ✅`);
  } catch (e) { lastResults[engine.toLowerCase()] = 'fail'; note(`[ping ${engine}] 失败: ${e.message}`); }
}

// MCP / llms.txt 目录：能 GET 提交的就提交，不能的给出入口
const MCP_DIRS = [
  { name: 'MCP 官方 Registry', note: '已通过 server.json 域名验证自动收录（cc.roboparts/roboparts），无需手动', submit: null },
  { name: 'Glama', note: '官方 Registry 下游自动抓取，已收录', submit: null },
  { name: 'Smithery', note: '仓库含 smithery.yaml，已被索引', submit: null },
  { name: 'mcp.so', note: '提交 GitHub 仓库 URL 即可', submit: `https://mcp.so/submit?link=${encodeURIComponent('https://github.com/lm203688/roboparts')}` },
  { name: 'PulseMCP', note: '提交表单', submit: 'https://www.pulsemcp.com/submit' },
  { name: 'LobeHub MCP', note: '提交表单', submit: 'https://lobehub.com/mcp' },
  { name: 'llms.txt 目录 (llmstxt.site)', note: '提交站点 llms.txt', submit: `https://llmstxt.site/?q=${encodeURIComponent(SITE + '/llms.txt')}` },
];

async function submitDirs() {
  for (const d of MCP_DIRS) {
    if (d.submit) {
      try {
        const r = await fetch(d.submit, { method: 'HEAD', redirect: 'follow' });
        note(`[dir ${d.name}] HEAD ${r.status} · 入口 ${d.submit}`);
      } catch (e) { note(`[dir ${d.name}] 入口待人工打开 · ${d.submit}`); }
    } else {
      note(`[dir ${d.name}] ${d.note}`);
    }
  }
}

// 国内搜索引擎主动提交（Baidu 需站长 token；360/搜狗给出收录入口）
//
// 【2026-08-08 自动化】自动读取 .env.local（已在 .gitignore，不进仓库/前端）里的
// BAIDU_PUSH_TOKEN / BAIDU_SITE，让飞轮每小时跑本脚本时无需手输参数即可自动推送。
// 仅当环境变量未显式传入时才用文件里的值（显式 env 优先，便于临时覆盖）。
function loadEnvLocal() {
  try {
    const raw = readFileSync(join(ROOT, '.env.local'), 'utf8');
    for (const line of raw.split('\n')) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$/);
      if (m && !(m[1] in process.env)) process.env[m[1]] = m[2];
    }
  } catch { /* 无 .env.local 时走原逻辑（靠显式 env 或跳过） */ }
}
loadEnvLocal();

// 每日节流：百度新站主动推送配额仅 10 条/天，飞轮每小时跑会把它在第一轮刷爆，
// 之后 23 轮全 over quota 刷屏。用本地日期戳文件约束「每天只推一次」。
const BAIDU_STAMP = join(ROOT, '.baidu-push-stamp');
function baiduPushedToday() {
  try { return readFileSync(BAIDU_STAMP, 'utf8').trim() === new Date().toISOString().slice(0, 10); }
  catch { return false; }
}
function markBaiduPushed() {
  try { writeFileSync(BAIDU_STAMP, new Date().toISOString().slice(0, 10)); } catch { /* 忽略 */ }
}

const BAIDU_TOKEN = process.env.BAIDU_PUSH_TOKEN || ''; // 主动推送 token（若百度后台仍提供）
const BAIDU_SITE = process.env.BAIDU_SITE || HOST;        // 默认 roboparts.cc；若百度只验证了 www 子域，可设 BAIDU_SITE=www.roboparts.cc
async function submitDomestic(urls) {
  note('—— 国内引擎收录 ——');

  // 0) 【主机同源闸 · 2026-08-11 事故后加】提交前先证明 BAIDU_SITE 这台主机在播本仓内容。
  const parity = await checkHostParity(BAIDU_SITE);
  const parityHost = parity.ok ? BAIDU_SITE.replace(/^https?:\/\//, '') : HOST;
  if (!parity.ok) {
    note(`[主机同源闸] ${parity.host} → ${parity.transportError ? '探测失败 UNKNOWN' : '不同源 FAIL'}，本轮拒推百度（未消耗配额、未打节流戳）`);
    for (const r of parity.reasons) note(`   ✗ ${r}`);
    note('   → 修复入口：阿里云 DNS 删除/改正 www 记录，或在 Cloudflare Pages 项目 robotparts 添加该自定义域；详见 ops/results/_NEEDS_USER.md');
    lastResults.baidu = 'skipped-parity';
  }

  // 1) 百度主动推送（仅当配置了 BAIDU_PUSH_TOKEN；且每日仅推一次，避免刷爆配额）
  if (!parity.ok) {
    note('[百度主动推送] 因主机同源闸未通过，跳过（宁可不推，也不把假站喂给百度）');
  } else if (!BAIDU_TOKEN) {
    note('[百度主动推送] 未配置 BAIDU_PUSH_TOKEN（显式 env 或 .env.local），跳过');
    lastResults.baidu = 'skipped-no-token';
    note(`[百度站长] 收录入口 https://ziyuan.baidu.com/site · 收录查询 https://www.baidu.com/s?wd=site%3A${parityHost}`);
  } else if (baiduPushedToday()) {
    note('[百度主动推送] 今日已推送（每日节流），跳过 —— 明日飞轮自动再推');
    lastResults.baidu = 'throttled-today';
  } else {
    try {
      const siteHost = BAIDU_SITE.replace(/^https?:\/\//, '');
      const pushUrls = urls.map(u => {
        try { const uu = new URL(u); uu.host = siteHost; return uu.toString(); }
        catch { return u; }
      });
      const BAIDU_LIMIT = parseInt(process.env.BAIDU_LIMIT || '10', 10);
      const baiduUrls = pushUrls.slice(0, BAIDU_LIMIT);
      const r = await fetch(`http://data.zz.baidu.com/urls?site=${BAIDU_SITE}&token=${BAIDU_TOKEN}`, {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain' },
        body: baiduUrls.join('\n'),
      });
      const txt = await r.text();
      lastResults.baidu = r.status;
      note(`[百度主动推送] HTTP ${r.status} · ${txt.slice(0, 160)}`);
      markBaiduPushed();
    } catch (e) { lastResults.baidu = 'fail'; note(`[百度主动推送] 失败: ${e.message}`); markBaiduPushed(); }
  }
  note(`[360 搜索] 收录查询 https://www.so.com/s?q=site%3A${parityHost}`);
  note(`[搜狗 Sogou] 收录查询 https://www.sogou.com/web?query=site%3A${parityHost}`);
}

async function main() {
  const urls = await getSitemapUrls();
  note(`=== RoboParts 推广脉冲 @ ${new Date().toISOString()} ===`);
  note(`站点 ${SITE} · sitemap ${urls.length} 条 URL`);
  await indexNow(urls);
  await pingSitemap('Google', 'https://www.google.com/ping');
  await pingSitemap('Bing', 'https://www.bing.com/ping');
  await submitDirs();
  await submitDomestic(urls);
  note('');
  note('—— 需人工发起的社区分发（回链文案见 ops/promotion/OUTREACH_DRAFTS.md）——');
  note('  · 知乎 / CSDN / Reddit r-robotics / Hacker News Show HN / X / LinkedIn / ROS Discourse');
  note('  · 投稿前请跑 `python scripts/regression.py` 确认 L1.29 对外数字闸门通过');

  // 写入运行日志
  const runsDir = join(ROOT, 'ops/promotion/runs');
  mkdirSync(runsDir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:T]/g, '-').slice(0, 16);
  writeFileSync(join(runsDir, `${stamp}.md`), log.join('\n') + '\n', 'utf8');
  note(`\n[log] 已写入 ops/promotion/runs/${stamp}.md`);

  // 效果台账（幂等：按日期覆盖，同日记多次只留一份）
  try {
    const entry = buildPromoEntry(SITE, urls.length, { ...lastResults });
    let ledger = {};
    if (existsSync(LEDGER)) {
      try { ledger = JSON.parse(readFileSync(LEDGER, 'utf8')); }
      catch { ledger = {}; }
    }
    ledger[entry.date] = entry;
    const tmp = LEDGER + '.tmp';
    writeFileSync(tmp, JSON.stringify(ledger, null, 2) + '\n');
    renameSync(tmp, LEDGER);
    note(`[ledger] 效果台账已更新 ops/promotion/ledger.json（${entry.date}）`);
  } catch (e) {
    note(`[ledger] 写入失败（不阻塞）: ${e.message}`);
  }

  // 记录 promote 阶段状态（飞轮幂等/可恢复台账）
  try {
    const fp = fingerprintUrls(urls);
    spawnSync(process.execPath,
      [FLYWHEEL_STATE, 'record', 'promote', fp, '--ok', '1'],
      { encoding: 'utf8', timeout: 30000 });
  } catch { /* 记录失败不阻塞主流程 */ }

  return 0;
}

const isMain = process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  main().catch(e => { console.error(e); process.exit(1); });
}
