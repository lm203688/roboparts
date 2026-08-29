#!/usr/bin/env node
/**
 * probe.mjs —— 飞轮巡检的**唯一**对外探活入口。
 *
 * 为什么要有这个文件（20260808-01 事故）：
 *   飞轮每小时都会用裸 `curl` 扫一遍关键路径确认站点活着。裸 curl 不带
 *   `X-RoboParts-Selftest` 头，于是 `functions/_middleware.js` 把它当**真实流量**记账：
 *     · 真实请求数被灌水（每轮 +15~50，一天十几轮 ≈ 全站"真实流量"的大半）
 *     · 探到的 404（如 /api/metrics、/api/analytics/*）被记进「404 归因」，
 *       再被下一轮读成"站点有断链，正在实伤 GEO"——飞轮自己造伤口再自己报警
 *   当轮阳性对照已实证：裸 curl 打 `/__flywheel-pollution-probe-<ts>` 后，
 *   该路径出现在**真实** 404 归因里；同一路径带隔离头再打一次，只进 selftest 命名空间。
 *
 *   这是「自检探针污染」的**第四型**（前三型：伪造爬虫 UA 记成 GEO 曝光、
 *   deploy 探私有路径记成断链、目录站握手记成真实 Agent 接入）。前三型都在代码里
 *   堵死了，唯独"人/模型临时敲的 curl"没入口可管——**所以给它一个入口**。
 *
 * 纪律：飞轮巡检一律 `node scripts/probe.mjs`，禁止裸 curl 打 roboparts.cc。
 *
 * 用法：
 *   node scripts/probe.mjs              # 默认全套
 *   node scripts/probe.mjs --json       # 机读输出（含 site_failures / transport_failures 分类）
 *   node scripts/probe.mjs /pricing /oss  # 只探指定路径
 *   PROBE_RETRIES=1 node scripts/probe.mjs  # 关掉传输层重试（调试用，日常别关）
 *
 * 读结果的纪律（20260808-04 事故后加）：
 *   `[传输层无响应]` ≠ 站点挂了。先确认本机能出网，再下"站点断链"的结论。
 *   反过来，拿到 HTTP 状态的失败（500/404）是**确定性事实**，不会被重试洗掉。
 */

const TARGET = process.env.PROBE_TARGET || 'https://roboparts.cc';

/** 与 functions/_middleware.js 的 SELFTEST_HEADER 同名，改名必须两边一起改（L1.50 会查）。 */
const SELFTEST_HEADERS = { 'X-RoboParts-Selftest': '1' };

/** 关键路径与期望状态。308 是 .html → 无后缀的规范跳转，属正常。 */
const GET_PATHS = [
  ['/', [200]],
  ['/pricing', [200]],
  ['/credits.html', [200, 308]],
  ['/credits', [200]],
  ['/data-hub', [200]],
  ['/copilot', [200]],
  ['/mcp-guide', [200]],
  ['/parts-viewer', [200]],
  ['/promotion', [200]],
  ['/adapter-generator', [200]],
  ['/designer', [200]],
  ['/oss', [200]],
  ['/llms.txt', [200]],
  ['/sitemap.xml', [200]],
  ['/robots.txt', [200]],
  ['/api/data.json', [200]],
  ['/api/oss?stats=1', [200]],
  // —— 2026-08-08 自动化补全：把报告落地清单新增的 6 项能力纳入飞轮每小时监控 ——
  // 之前漏掉它们，部署成功后若回退/失效飞轮看不到（正是记忆反复警告的"线上跑的不是当前代码"盲区）。
  ['/agent-architecture', [200]],
  ['/build-planner', [200]],
  ['/geo-dashboard', [200]],
  ['/skills/manifest.json', [200]],
];

/** POST 探活：MCP 协议与 Copilot 代理。503 = Agnes 密钥未配置，属已知可接受态。 */
const POST_CHECKS = [
  {
    path: '/mcp',
    body: { jsonrpc: '2.0', id: 1, method: 'tools/list' },
    ok: [200],
    extra: { 'content-type': 'application/json' },
  },
  {
    path: '/api/copilot',
    body: { prompt: 'selftest' },
    ok: [200, 503],
    extra: { 'content-type': 'application/json', origin: 'https://roboparts.cc' },
  },
  {
    // 数字-物理反馈闭环的写入端点；400 = 正确校验入参（已知可接受态）
    path: '/api/adapter-feedback',
    body: { adapter: {} },
    ok: [200, 400],
    extra: { 'content-type': 'application/json' },
  },
];

/**
 * 传输层失败（拿不到任何 HTTP 状态）的重试次数。
 *
 * 为什么必须重试（20260808-04 事故 · 「口径 ≠ 事实」第 8 次）：
 *   那一轮 `/pricing` 报 `fetch failed`（10.3s），报告差点写成"站点断链"。
 *   随后 4 次独立复核（probe ×3 + curl ×1）全部 200 / 0.6~0.75s ——
 *   **站点一直是好的，抖的是本机网络**。探针的"口径"与"事实"再次分叉。
 *   单次瞬断判红有两重危害：①虚假 P0 上报给用户、可能触发无谓部署；
 *   ②红得多了就没人信，真红那次会被当噪声忽略。
 *
 * 两类失败必须分开对待，不能混为一谈：
 *   · status === 0 —— 压根没拿到响应（DNS/连接/超时）。**可能是我这边**，重试。
 *   · status 有值但不在期望内（如 500） —— 站点确实答错了，**确定性事实**，不重试。
 */
const TRANSPORT_RETRIES = Number(process.env.PROBE_RETRIES ?? 3);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function hitOnce(path, init = {}) {
  const t0 = Date.now();
  try {
    const r = await fetch(TARGET + path, {
      ...init,
      headers: { ...SELFTEST_HEADERS, ...(init.headers || {}) },
      redirect: 'manual',
      signal: AbortSignal.timeout(20000),
    });
    return { path, status: r.status, ms: Date.now() - t0 };
  } catch (e) {
    return { path, status: 0, ms: Date.now() - t0, error: String(e && e.message || e) };
  }
}

async function hit(path, init = {}) {
  let last;
  for (let attempt = 1; attempt <= TRANSPORT_RETRIES; attempt++) {
    last = await hitOnce(path, init);
    // 拿到了 HTTP 状态 = 站点给了确定答复，无论好坏都不该重试（重试只会掩盖真故障）。
    if (last.status !== 0) {
      if (attempt > 1) last.recovered = attempt; // 记下"第几次才通"，瞬断留痕不失真
      return last;
    }
    if (attempt < TRANSPORT_RETRIES) await sleep(attempt * 1000); // 1s, 2s 退避
  }
  last.attempts = TRANSPORT_RETRIES;
  last.transport = true; // 连续拿不到响应：本地网络 或 站点真的不可达
  return last;
}

async function main() {
  const argv = process.argv.slice(2);
  const asJson = argv.includes('--json');
  const only = argv.filter((a) => a.startsWith('/'));

  const gets = only.length ? only.map((p) => [p, [200]]) : GET_PATHS;
  const results = [];

  for (const [p, ok] of gets) {
    const r = await hit(p);
    r.expected = ok;
    r.pass = ok.includes(r.status);
    results.push(r);
  }

  if (!only.length) {
    for (const c of POST_CHECKS) {
      const r = await hit(c.path, {
        method: 'POST',
        headers: c.extra,
        body: JSON.stringify(c.body),
      });
      r.path = 'POST ' + r.path;
      r.expected = c.ok;
      r.pass = c.ok.includes(r.status);
      results.push(r);
    }
  }

  const bad = results.filter((r) => !r.pass);
  const transportBad = bad.filter((r) => r.transport);
  if (asJson) {
    console.log(JSON.stringify({
      target: TARGET, results, failed: bad.length,
      // 分开给出，读的人（含下一轮的我）才不会把"我这边没网"写成"站点断链"
      site_failures: bad.length - transportBad.length,
      transport_failures: transportBad.length,
      flaky_recovered: results.filter((r) => r.recovered).length,
    }, null, 2));
  } else {
    console.log(`=== RoboParts 探活 · ${TARGET} · 隔离头已带（不污染真实遥测）===`);
    for (const r of results) {
      const note = r.recovered ? `  (第${r.recovered}次重试才通·瞬断)` : '';
      const kind = r.transport ? `  [传输层无响应 ×${r.attempts}]` : '';
      console.log(`${r.pass ? '✅' : '❌'} ${String(r.status).padStart(3)} ${String(r.ms).padStart(5)}ms  ${r.path}${kind}${note}${r.error ? '  ' + r.error : ''}`);
    }
    const flaky = results.filter((r) => r.recovered).length;
    if (flaky) console.log(`\n⚠️  ${flaky} 条经重试后恢复（本机网络瞬断，非站点故障）`);
    if (transportBad.length) {
      console.log(`\n❗ ${transportBad.length} 条连续 ${TRANSPORT_RETRIES} 次拿不到响应：` +
        `先确认本机出网，再判定站点 —— 不要直接写成"站点断链"`);
    }
    console.log(bad.length ? `\n❌ ${bad.length}/${results.length} 条异常` : `\n✅ 全部 ${results.length} 条正常`);
  }
  process.exit(bad.length ? 1 : 0);
}

main();
