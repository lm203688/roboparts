#!/usr/bin/env node
/**
 * smoke_prod.mjs —— 生产冒烟测试（P0-5）
 *
 * 与 probe.mjs 的分工：
 *   · probe.mjs：HTTP 状态码探活（是否 200），关心"站点活着"
 *   · smoke_prod.mjs：**内容与契约验证**——JSON 能否解析、根元素对不对、
 *     下载内容是不是真的 XML、assetClass 头是否存在
 *
 * 为什么不能只靠 probe：一个 200 响应的 JSON 端点，如果返回 {"error": "xxx"}，
 * probe 看到 200 就判绿，但业务层完全炸了。2026-08-08 类事故正是这样漏的。
 *
 * 用法：
 *   node scripts/smoke_prod.mjs              # 全套
 *   node scripts/smoke_prod.mjs --json       # 机读输出
 *   node scripts/smoke_prod.mjs --target https://roboparts.cc/preview  # 预览域
 *   SMOKE_RETRIES=1 node scripts/smoke_prod.mjs  # 关掉重试（调试）
 */

const TARGET = (process.env.SMOKE_TARGET || process.argv.find(a => a.startsWith('http'))
  || 'https://roboparts.cc').replace(/\/$/, '');

const SELFTEST_HEADERS = { 'X-RoboParts-Selftest': '1' };
const RETRIES = Number(process.env.SMOKE_RETRIES ?? 2);
const TIMEOUT_MS = 15000;

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

/** 单次 GET 并读全文。transport 失败（无 HTTP 状态）会重试。 */
async function fetchText(path, init = {}) {
  let last;
  for (let attempt = 1; attempt <= RETRIES; attempt++) {
    const t0 = Date.now();
    try {
      const r = await fetch(TARGET + path, {
        ...init,
        headers: { ...SELFTEST_HEADERS, ...(init.headers || {}) },
        redirect: 'manual',
        signal: AbortSignal.timeout(TIMEOUT_MS),
      });
      const text = await r.text();
      return { ok: true, status: r.status, headers: Object.fromEntries(r.headers.entries()), text, ms: Date.now() - t0, attempt };
    } catch (e) {
      last = { ok: false, error: String(e && e.message || e), ms: Date.now() - t0, attempt };
      if (attempt < RETRIES) await sleep(attempt * 800);
    }
  }
  return { ...last, transport: true };
}

/** 冒烟用例：一条 path + 一个"内容必须满足的谓词" */
async function check(name, path, predicate, init = {}) {
  const r = await fetchText(path, init);
  if (!r.ok) {
    return { name, pass: false, reason: `transport fail after ${RETRIES} retries: ${r.error}` };
  }
  const expected = init.expectStatus || [200, 308];
  if (!expected.includes(r.status)) {
    return { name, pass: false, reason: `HTTP ${r.status}（期望 ${expected.join('/')})` };
  }
  try {
    const verdict = predicate(r);
    return { name, pass: !!verdict.ok, reason: verdict.ok ? '' : verdict.reason };
  } catch (e) {
    return { name, pass: false, reason: `predicate threw: ${e.message}` };
  }
}

// ========================= 用例集 =========================

/** 首页必须包含"RoboParts"品牌 + 至少一个导航链接 */
const checkIndex = async () => check(
  '首页 · 含品牌与导航',
  '/',
  (r) => {
    if (!r.text.includes('RoboParts')) return { ok: false, reason: '首页文本不含 "RoboParts"' };
    if (!/<a\s+href=/.test(r.text)) return { ok: false, reason: '首页无任何 <a href> 导航' };
    return { ok: true };
  }
);

/** /api/data.json 必须能解析 JSON 且 meta.generated_at 是 ISO 时间戳 */
const checkDataJson = async () => check(
  'data.json · JSON 可解析 + meta 完整',
  '/api/data.json',
  (r) => {
    let d;
    try { d = JSON.parse(r.text); }
    catch (e) { return { ok: false, reason: `JSON 解析失败: ${e.message}` }; }
    if (!d.meta) return { ok: false, reason: '缺 meta 字段' };
    if (!d.meta.generated_at) return { ok: false, reason: '缺 meta.generated_at' };
    if (!/^\d{4}-\d{2}-\d{2}T/.test(d.meta.generated_at)) return { ok: false, reason: `meta.generated_at 非 ISO 时间戳: ${d.meta.generated_at}` };
    if (typeof d.meta.total_entities !== 'number' || d.meta.total_entities < 100) {
      return { ok: false, reason: `meta.total_entities 异常: ${d.meta.total_entities}` };
    }
    return { ok: true };
  }
);

/** /api/deployment 必须返回 JSON，含 commit 与 builtAt */
const checkDeployment = async () => check(
  '/api/deployment · 指纹可读',
  '/api/deployment',
  (r) => {
    let d;
    try { d = JSON.parse(r.text); }
    catch (e) { return { ok: false, reason: `JSON 解析失败: ${e.message}` }; }
    if (!d.commit || d.commit === 'unknown') return { ok: false, reason: 'commit 为 unknown（静态文件未刷新或 env 未注入）' };
    if (!d.builtAt || d.builtAt === 'unknown') return { ok: false, reason: 'builtAt 为 unknown' };
    return { ok: true };
  }
);

/** /api/urdf/download 无 id 应返 400 + JSON 错误 */
const checkUrdfBadRequest = async () => check(
  '/api/urdf/download · 无 id 返回 400 + JSON',
  '/api/urdf/download',
  (r) => {
    if (r.status !== 400) return { ok: false, reason: `期望 400，实际 ${r.status}` };
    let d;
    try { d = JSON.parse(r.text); }
    catch (e) { return { ok: false, reason: `错误响应非 JSON: ${e.message}` }; }
    if (!d.error) return { ok: false, reason: '错误响应缺 error 字段' };
    return { ok: true };
  },
  { expectStatus: [400] }
);

/** /api/urdf/download?id=URDF-001&format=urdf 应返回 URDF XML，根元素 <robot> */
const checkUrdfDownload = async () => check(
  '/api/urdf/download URDF-001 · 根元素 <robot>',
  '/api/urdf/download?id=URDF-001',
  (r) => {
    if (!r.text.trimStart().startsWith('<?xml')) return { ok: false, reason: '响应非 XML（缺 <?xml 头）' };
    if (!/<robot\s/.test(r.text)) return { ok: false, reason: '无 <robot 根元素——不合法 URDF' };
    if (!r.headers['content-disposition'] || !/attachment/.test(r.headers['content-disposition'])) {
      return { ok: false, reason: '缺 Content-Disposition: attachment' };
    }
    return { ok: true };
  }
);

/** /api/urdf/download?id=URDF-001&format=mjcf 应返回 MJCF XML，根元素 <mujoco> */
const checkMjcfDownload = async () => check(
  '/api/urdf/download URDF-001 · 根元素 <mujoco>',
  '/api/urdf/download?id=URDF-001&format=mjcf',
  (r) => {
    if (!r.text.trimStart().startsWith('<?xml')) return { ok: false, reason: '响应非 XML' };
    if (!/<mujoco\s/.test(r.text)) return { ok: false, reason: '无 <mujoco 根元素——不合法 MJCF' };
    if (!/<worldbody/.test(r.text)) return { ok: false, reason: '无 <worldbody>——MuJoCo 无法加载' };
    return { ok: true };
  }
);

/** 下载响应必须带 X-RoboParts-AssetClass 头（P0-12） */
const checkAssetClassHeader = async () => check(
  '/api/urdf/download · X-RoboParts-AssetClass 头存在',
  '/api/urdf/download?id=URDF-001',
  (r) => {
    const ac = r.headers['x-roboparts-assetclass'];
    if (!ac) return { ok: false, reason: '缺 X-RoboParts-AssetClass 响应头' };
    if (!/^L[0-4]$/.test(ac)) return { ok: false, reason: `X-RoboParts-AssetClass 值非法: "${ac}"（应为 L0-L4）` };
    return { ok: true };
  }
);

/** Copilot 端点必须响应（200 或 503 密钥缺失均可；403 = 无 Origin 头，也算可达） */
const checkCopilotReachable = async () => check(
  '/api/copilot · 端点可达（200/403/503）',
  '/api/copilot',
  (r) => {
    if (![200, 403, 503].includes(r.status)) return { ok: false, reason: `意外状态 ${r.status}` };
    return { ok: true };
  },
  { method: 'POST', body: JSON.stringify({ prompt: 'selftest' }),
    headers: { 'content-type': 'application/json', origin: 'https://roboparts.cc' },
    expectStatus: [200, 403, 503] }
);

/** robots.txt 存在 */
const checkRobotsTxt = async () => check(
  '/robots.txt · 存在',
  '/robots.txt',
  (r) => r.text.includes('User-agent') ? { ok: true } : { ok: false, reason: '无 User-agent 指令' }
);

/** P1-6 主链路埋点：/api/analytics/funnel 必须返回合法漏斗 JSON */
const checkFunnelEndpoint = async () => check(
  '/api/analytics/funnel · P1-6 漏斗端点可达 + 契约完整',
  '/api/analytics/funnel',
  (r) => {
    let d;
    try { d = JSON.parse(r.text); }
    catch (e) { return { ok: false, reason: `JSON 解析失败: ${e.message}` }; }
    if (!d.date) return { ok: false, reason: '缺 date 字段' };
    if (!d.counts || typeof d.counts.visits !== 'number') return { ok: false, reason: '缺 counts.visits（数字）' };
    if (!d.rates) return { ok: false, reason: '缺 rates 字段' };
    if (!d.pipeline_usage) return { ok: false, reason: '缺 pipeline_usage 字段（P1-6 主链 5 步）' };
    if (!d.meta || !d.meta.data_version) return { ok: false, reason: '缺 meta.data_version' };
    // pipeline_usage 必须含 5 步主链键
    const steps = ['selection', 'build_planner', 'designer', 'bom_checker', 'adapter_generator'];
    const missing = steps.filter(s => !(s in d.pipeline_usage));
    if (missing.length) return { ok: false, reason: `pipeline_usage 缺步骤: ${missing.join(',')}` };
    return { ok: true };
  }
);

const CHECKS = [
  checkIndex,
  checkDataJson,
  checkDeployment,
  checkUrdfBadRequest,
  checkUrdfDownload,
  checkMjcfDownload,
  checkAssetClassHeader,
  checkCopilotReachable,
  checkRobotsTxt,
  checkFunnelEndpoint,
];

async function main() {
  const asJson = process.argv.includes('--json');
  const results = [];
  for (const fn of CHECKS) {
    results.push(await fn());
  }
  const failed = results.filter(r => !r.pass);

  if (asJson) {
    console.log(JSON.stringify({
      target: TARGET,
      total: results.length,
      passed: results.length - failed.length,
      failed: failed.length,
      results,
    }, null, 2));
  } else {
    console.log(`=== RoboParts 生产冒烟 · ${TARGET} · ${results.length} 用例 ===`);
    for (const r of results) {
      const mark = r.pass ? '✅' : '❌';
      console.log(`${mark} ${r.name}` + (r.reason ? `\n     ↳ ${r.reason}` : ''));
    }
    console.log(`\n${failed.length === 0 ? '✅ 全部通过' : '❌ ' + failed.length + '/' + results.length + ' 失败'}`);
  }
  process.exit(failed.length ? 1 : 0);
}

main();
