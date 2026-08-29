/**
 * RoboParts 边缘安全中间件
 * 作用：在所有请求（含静态资源）被处理前拦截私有/内部目录，
 *       直接返回 404，避免 .workbuddy（本地记忆/用户档案）、ops/（运营内部报告）
 *       等被公开访问。wrangler pages deploy 会以 git 仓库根为部署源，
 *       无法靠 .gitignore 排除这些目录，故在边缘层兜底拦截。
 *
 * ─────────────────────────────────────────────────────────────────────────
 * 【N03 20260805-r3 · S-01 事故修复记录 —— 勿回退】
 *
 * 事故：https://roboparts.cc/wrangler.toml 线上返回 200，内含明文 ADMIN_API_KEYS，
 *       任何人可下载后越权调用 /api/suppliers/approve 与 /api/suppliers/quote。
 *       同时泄露 /.gitignore、/integrity_report.txt、/scripts/deploy.mjs、
 *       /scripts/regression.py、/intelligence-analysis-*.docx。
 *
 * 根因：本中间件的判断逻辑本身没错，但 `_routes.json` 的 include 是「枚举式白名单」，
 *       只列了几个已知私有目录。Pages Function 仅在 include 命中的路径上运行，
 *       根级文件与 scripts/ tasks/ 从未进入 include —— 本中间件对它们压根没被调用。
 *       **拦截规则写了，但执行入口没打开。**
 *
 * 修复：`_routes.json` 的 include 改为 ["/*"]，语义反转为「默认全部经过中间件」，
 *       由下方黑名单决定拦截。此后新增私有文件无需再改路由配置。
 *
 * ⚠️ 不变式：include 必须保持 "/*"。若有人为省函数调用量把它改回枚举式白名单，
 *    本文件的全部拦截规则会再次静默失效，且不会有任何报错 —— 与本次事故完全同型。
 *    `scripts/regression.py` 已加入 L1.6 断言守护该不变式。
 * ─────────────────────────────────────────────────────────────────────────
 */
const PRIVATE_PREFIXES = [
  '/.workbuddy',
  '/ops',
  '/mcp-server',
  '/multi-persona-ux-analysis-v3',
  '/robot-ai-models-evaluation',
  '/scheduled-tasks-closure-analysis',
  '/roboparts-dataset-github',
  // 【N03 20260805-r3 修复 S-01】本轮实测发现的新增泄露面
  '/scripts',   // deploy.mjs / regression.py 等运维脚本，暴露部署与校验逻辑
  '/tasks',     // 内部周任务清单
  // 【20260805-15 修复软 404】/functions/** 此前回落首页并返回 200（源码未泄露，
  // 但对搜索引擎构成大量重复内容页面）。这里改为硬 404，语义正确且不喂垃圾给 GEO 抓取。
  '/functions',
  // 注：/content 暂不拦截 —— functions/api/analytics/seo.js 将其中的 markdown
  // 列为对外投稿候选物料，且对 GEO 抓取可能有正向价值，需人工确认后再决定。
];

/**
 * 【N03 20260805-r3 修复 S-01】根级私有「文件」精确拦截清单。
 *
 * 事故背景：wrangler pages deploy 以仓库根为源上传全部文件，此前仅拦截私有「目录」，
 * 根目录下的单个文件从未被覆盖。实测 https://roboparts.cc/wrangler.toml 返回 200
 * 且含明文 ADMIN_API_KEYS —— 任何人可下载后越权调用供应商审批 / 报价接口。
 *
 * ⚠️ 新增拦截项必须同步写入 _routes.json 的 include，否则 Pages Function
 * 根本不会在该路径上运行，此处判断形同虚设 —— 这正是本次泄露的直接机理。
 */
const PRIVATE_FILES = [
  '/wrangler.toml',          // 含 ADMIN_API_KEYS 明文
  '/.gitignore',             // 暴露目录结构
  '/integrity_report.txt',   // 内部审计产出
  '/package.json',
  '/package-lock.json',
  '/.dev.vars',              // 防御性：wrangler 本地密钥文件
  '/.env',
  '/.env.local',
];

/** 内部产物扩展名（如内部情报分析 docx、运维脚本），一律不对外 */
const PRIVATE_EXTENSIONS = ['.docx', '.xlsx', '.pptx', '.toml', '.py', '.mjs', '.log'];

/* ═══════════════════════════════════════════════════════════════════════════
 * 【20260805-18 新增】边缘遥测 —— GEO 曝光与访问信号采集
 *
 * 背景：连续 4 轮飞轮运行判定瓶颈为「获客」，但站点**没有任何流量埋点**，
 *       ops/funnel/ 只能测「可用性」与「KV 里的转化终点(0)」。
 *       结果是永远只看得到 0，却无法区分「没人来」还是「来了没转化」——
 *       "获客效果验证" 在无埋点的前提下是不可能完成的任务。
 *
 * 设计约束（零成本，不得超出 Cloudflare 免费额度 1000 KV写/日）：
 *   1. 不按请求写 KV。用 isolate 级内存累加器，最多每 FLUSH_MS 落盘一次。
 *   2. 分 16 个 shard key，避免跨 isolate 读改写竞争丢数；单日键数上限 16。
 *   3. expirationTtl 自动过期，KV 不会无界增长。
 *   4. 全程 try/catch + waitUntil：遥测**绝不允许**影响响应正确性。
 *
 * 读取方式：不开公开端点（避免新增攻击面），用
 *   npx wrangler kv key list --namespace-id=<USER_CREDITS> --remote | grep metrics:
 * ═══════════════════════════════════════════════════════════════════════════ */

/** 已知 AI 检索爬虫 —— 命中即为 GEO 曝光（robots.txt 已显式放行这批） */
const AI_BOTS = [
  ['gptbot', 'GPTBot'], ['oai-searchbot', 'OAI-SearchBot'], ['chatgpt-user', 'ChatGPT-User'],
  ['claudebot', 'ClaudeBot'], ['anthropic-ai', 'anthropic-ai'], ['claude-web', 'Claude-Web'],
  ['perplexitybot', 'PerplexityBot'], ['perplexity-user', 'Perplexity-User'],
  ['google-extended', 'Google-Extended'], ['applebot-extended', 'Applebot-Extended'],
  ['bytespider', 'Bytespider'], ['petalbot', 'PetalBot'], ['youbot', 'YouBot'],
  ['ccbot', 'CCBot'], ['diffbot', 'Diffbot'], ['cohere-ai', 'cohere-ai'],
  ['meta-externalagent', 'Meta-ExternalAgent'], ['amazonbot', 'Amazonbot'],
];

/** 传统搜索引擎爬虫 —— 命中即为 SEO 收录进展 */
const SEARCH_BOTS = [
  ['googlebot', 'Googlebot'], ['bingbot', 'Bingbot'], ['baiduspider', 'Baiduspider'],
  ['yandexbot', 'YandexBot'], ['duckduckbot', 'DuckDuckBot'], ['sogou', 'Sogou'],
  ['360spider', '360Spider'], ['slurp', 'Yahoo-Slurp'], ['applebot', 'Applebot'],
];

const FLUSH_MS = 60_000;        // 普通流量：每个 isolate 最多每 60s 落盘一次
const SHARDS = 16;              // 单日 KV 键数上限
const METRIC_TTL = 60 * 60 * 24 * 120; // 120 天后自动过期
/**
 * 【20260805-18 二次修正 —— 勿改回纯节流】
 * 纯 60s 节流在**零流量站点**上会系统性丢数：缓冲区必须等"下一个请求"
 * 才可能触发落盘，而低流量时下一个请求可能永远不来，isolate 被回收后
 * 内存计数直接蒸发。实测 6 次探针只落盘 5 条，referer 归因与 /pricing 全丢。
 *
 * 解法：按价值分级落盘 —— AI/搜索爬虫命中（GEO 曝光，低频高价值）立即落盘；
 * 普通访问（高频低价值）仍走 60s 节流。再加每 isolate 每日写次数硬上限兜底，
 * 防流量突增击穿免费额度（1000 写/日）。
 */
const MAX_WRITES_PER_ISOLATE_DAY = 150;

/** isolate 级累加器（跨请求复用同一 isolate 内存，零 KV 成本） */
let _buf = Object.create(null);
let _lastFlush = 0;
let _writes = 0;      // 本 isolate 当日已写次数（额度兜底）
let _writeDay = '';   // 跨日自动重置

/**
 * ⚠️【20260805-18 事故：全站 404 —— 勿回退】
 * 初版把分片号写成模块顶层的 `const _shard = Math.floor(Math.random()*SHARDS)`。
 * Cloudflare Workers **禁止在模块顶层作用域生成随机数 / 做 I/O**
 * （"can only be performed while handling a request"），worker 启动即抛错；
 * 又因 _routes.json 的 include 是 "/*"，全部请求都要经过这个 worker，
 * 结果整站（含 / 与 /api/*）全部 404 —— 单行代码造成全站不可用。
 * 部署闸门在预览环境拦下，未污染生产。
 * 不变式：分片号必须**懒初始化到首个请求内**；Functions 顶层禁止 Math.random()/Date.now()。
 * scripts/regression.py 的 L1.9 已加断言守护。
 */
let _shard = null;
function shardId() {
  if (_shard === null) _shard = Math.floor(Math.random() * SHARDS);
  return _shard;
}

function bump(key) {
  _buf[key] = (_buf[key] || 0) + 1;
}

/** UA 归类：ai / search / tool / human，返回 [类别, 具体名] */
function classifyUA(ua) {
  const u = (ua || '').toLowerCase();
  if (!u) return ['tool', 'empty-ua'];
  for (const [needle, name] of AI_BOTS) if (u.includes(needle)) return ['ai', name];
  for (const [needle, name] of SEARCH_BOTS) if (u.includes(needle)) return ['search', name];
  if (/curl|wget|python-requests|httpx|go-http|java\/|okhttp|axios|node-fetch|postman/.test(u))
    return ['tool', 'script'];
  if (u.includes('bot') || u.includes('spider') || u.includes('crawler'))
    return ['search', 'other-bot'];
  if (u.includes('mozilla') || u.includes('safari') || u.includes('chrome'))
    return ['human', 'browser'];
  return ['tool', 'unknown'];
}

/** 仅统计内容页与关键转化页，避免键爆炸 */
function normalizePath(p) {
  if (p === '/' || p === '/index.html') return '/';
  if (p.startsWith('/articles/')) return p === '/articles/' ? '/articles/' : '/articles/*';
  if (p.startsWith('/api/')) return '/api/*';
  const tracked = [
    '/pricing', '/data-hub', '/bom-checker', '/iso-9409-flange', '/selection',
    '/suppliers', '/designer', '/oss', '/credits', '/mcp-guide', '/api-pricing',
    '/llms.txt', '/sitemap.xml', '/robots.txt',
    // 【20260806-00】hosted MCP 端点。它是免鉴权只读的，KV 里没有 user 记录，
    // 若不在此显式追踪，所有 Agent 调用都会落进 __other 被丢弃 ——
    // 那就等于新开了一条通道却看不见它有没有人走（"指标看不见 = 以为没人用"）。
    // 注：/mcp 与 /mcp-guide 是精确匹配，互不影响。
    '/mcp',
  ];
  const base = p.replace(/\.html$/, '');
  if (tracked.includes(base)) return base;
  return '__other';
}

/** 漏洞扫描器特征：这些 404 是噪声，不给它们在 KV 里开独立键 */
const SCAN_RE =
  /wp-|wordpress|\.env|\.git|\.svn|\.aws|\.ssh|id_rsa|phpmyadmin|xmlrpc|eval-stdin/i;
const SCAN_EXT_RE = /\.(php|asp|aspx|jsp|sql|bak|old|zip|tar|gz|ini|yml|yaml)$/i;
const SCAN_PATH_RE = /^\/(admin|vendor|cgi-bin|backup|actuator|shell|config)(\/|$)/i;

/**
 * 404 路径归类：既要能定位断链，又不能被扫描器撑爆 KV 键空间。
 *
 * 【20260807-16】此前 404 只写一个 `status:404` 计数 —— 知道每天在流血，
 * 却查不出伤口在哪。根因是 normalizePath() 本质是**已知好页面的白名单**，
 * 而 404 按定义必然不在白名单里，一律落 `__other` 被丢弃。于是当日 42 次 404
 * 无一可定位，更要命的是分不清两种性质完全相反的东西：
 *   · 我方死链（llms.txt / sitemap / 文章互链指错）—— 每一次都是 GEO 抓取与
 *     Agent 接入的直接损失，必须修；
 *   · 扫描器噪声 —— 完全无需理会。
 * 混成一个数字，就只能在"要不要慌"之间瞎猜。这与 L1.42 同型：
 * **有计数无归因的指标不会让人更清醒，只会让人更笃定地猜错。**
 *
 * 有界化三分法（键空间上界 ≈ 我方 URL 空间 + 2，扫描器再野也撑不爆）：
 *   scan   —— 命中扫描特征，聚合成一个键
 *   <slug> —— 形似我方地址（≤3 段、仅安全字符、≤48 字符），逐条记，这才是要修的
 *   other  —— 其余一律聚合；宁可粗，也不让键爆炸把真实断链淹掉
 */
function classify404(p) {
  const raw = (p || '/').toLowerCase();
  if (SCAN_RE.test(raw) || SCAN_EXT_RE.test(raw) || SCAN_PATH_RE.test(raw)) return 'scan';
  if (raw.length > 48) return 'other';
  if (!/^\/[a-z0-9._\-/]*$/.test(raw)) return 'other';
  if (raw.split('/').filter(Boolean).length > 3) return 'other';
  return raw === '/' ? '/' : raw.replace(/\/+$/, '');
}

async function flush(env) {
  const entries = Object.entries(_buf);
  if (!entries.length) return;
  const day = new Date().toISOString().slice(0, 10);
  if (day !== _writeDay) { _writeDay = day; _writes = 0; }   // 跨日重置额度
  if (_writes >= MAX_WRITES_PER_ISOLATE_DAY) return;          // 额度兜底：保留缓冲，不清空
  _buf = Object.create(null);                                 // 先清空，避免重复计数
  const key = `metrics:${day}:s${shardId()}`;
  const kv = env && env.USER_CREDITS;
  if (!kv) return;
  _writes++;
  let prev = {};
  try {
    prev = (await kv.get(key, { type: 'json' })) || {};
  } catch { /* 读失败则按新建处理，宁可丢历史也不丢本批 */ }
  for (const [k, v] of entries) prev[k] = (prev[k] || 0) + v;
  prev._updated = new Date().toISOString();
  await kv.put(key, JSON.stringify(prev), { expirationTtl: METRIC_TTL });
}

/**
 * 自检隔离标记头。
 * 【20260805-18 防自污染 —— 与 15:00 的 testorder_ 隔离同源教训】
 * 飞轮验证埋点时会伪造 GPTBot/ClaudeBot UA 发探针，若与真实流量混记，
 * 下一轮报告就会把自己的探针读成"GEO 曝光"，做出错误的经营判断
 * （14:00 轮的 verify@example.com 测试订单污染就是同型事故）。
 * 带此头的请求全部记入 selftest: 命名空间，不进任何真实计数。
 */
const SELFTEST_HEADER = 'x-roboparts-selftest';

function record(context, url, status) {
  try {
    const req = context.request;
    const [kind, name] = classifyUA(req.headers.get('user-agent'));
    const path = normalizePath(url.pathname);

    // 自检探针：只记隔离计数，绝不污染真实流量/曝光指标
    if (req.headers.get(SELFTEST_HEADER)) {
      bump('selftest:total');
      bump(`selftest:ua:${kind}`);
      if (kind === 'ai' || kind === 'search') bump(`selftest:bot:${name}`);
      if (path !== '__other') bump(`selftest:path:${path}`);
      // 自检 404 单独计数：deploy.mjs 每轮都会故意探私有路径拿 404，
      // 若不在此显式隔离，下面新增的 404 归因就会把飞轮自己的探针
      // 读成"站点有断链"—— 与 L1.42 同一个坑，先堵住再开新指标。
      if (status === 404) bump('selftest:status:404');
      if (req.headers.get('referer')) bump('selftest:ref');
      context.waitUntil(flush(context.env).catch(() => {}));
      return;
    }

    bump('total');
    bump(`ua:${kind}`);
    if (kind === 'ai' || kind === 'search') bump(`bot:${name}`);
    if (status === 404) {
      bump('status:404');
      // 归因两条腿：谁撞的（爬虫撞死链最伤 GEO）+ 撞的是哪条（才修得了）
      bump(`404ua:${kind}`);
      bump(`404path:${classify404(url.pathname)}`);
    }
    if (path !== '__other') bump(`path:${path}`);

    // 来源归因：识别自然搜索/AI 引擎跳转（获客证据链的关键一环）
    const ref = req.headers.get('referer');
    if (ref) {
      try {
        const h = new URL(ref).hostname.replace(/^www\./, '');
        if (!h.endsWith('roboparts.cc')) bump(`ref:${h.slice(0, 40)}`);
      } catch { /* 非法 referer 忽略 */ }
    }

    // 分级落盘：爬虫命中是 GEO 曝光的核心证据且天然低频，必须立即落盘，
    // 否则在零流量站点上会因等不到下一个请求而永久丢失（见 MAX_WRITES 处注释）。
    const highValue = (kind === 'ai' || kind === 'search');
    const now = Date.now();
    if (highValue || now - _lastFlush >= FLUSH_MS) {
      _lastFlush = now;
      context.waitUntil(flush(context.env).catch(() => {}));
    }
  } catch { /* 遥测永不影响主流程 */ }
}

// 导出供 L1.44 闸门真跑（同 L1.43 的做法：对外可测的真相源只此一份，
// 不允许测试脚本另抄一个分类器 —— 抄一份就等于闸门守的是抄件不是本体）。
// Pages Functions 只识别 onRequest* 具名导出，多这一个不影响路由。
export { classify404 };

export async function onRequest(context) {
  const url = new URL(context.request.url);
  const p = url.pathname;
  const lower = p.toLowerCase();
  const isPrivate =
    PRIVATE_PREFIXES.some(
      (prefix) => p === prefix || p.startsWith(prefix + '/')
    ) ||
    PRIVATE_FILES.includes(lower) ||
    PRIVATE_EXTENSIONS.some((ext) => lower.endsWith(ext));
  if (isPrivate) {
    record(context, url, 404);
    return new Response('Not Found', {
      status: 404,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' },
    });
  }
  /**
   * 【20260807-16/17】HEAD 探活问题的处置记录（两次失败，第三次才对，留档防重蹈）：
   *
   * 现象：Pages Functions 按 onRequest<Method> 具名导出路由，全站没有一个 onRequestHead，
   * 于是**所有函数路由对 HEAD 一律 404**，而 GET 是 200。实测 HEAD /mcp = 404。
   * 这不是小瑕疵：目录站、链接检查器、可用性监控**默认用 HEAD**，/mcp 正是我们唯一
   * 进了 MCP 官方 Registry / Glama / mcp.so 的对外通道 —— 它们探一次拿到 404，
   * 结论就是"这个 MCP 服务器挂了"。我们一边铺曝光，一边对来探活的人说"我不在"。
   *
   * ❌ 尝试一：next() 拿到 404 后再 next(GET) 补偿。Pages 一个请求周期只允许调一次
   *    next()，第二次抛异常被 catch 吞掉。线上 HEAD 依旧 404，连补偿头都没有。
   * ❌ 尝试二：一次性用 GET Request 调 next()。补偿头出现了，状态码却纹丝不动 ——
   *    next(request) 不会按新 Request 的 method 重新分发 handler，方法匹配早已定死。
   *    这一版尤其危险：它挂上了 x-head-fallback 头，看起来"补偿生效"，实则毫无作用。
   * ✅ 最终：老老实实在每个函数路由具名导出 onRequestHead（见 mcp.js / api/*.js），
   *    并由 regression L1.44 扫描 llms.txt+sitemap 里声明的函数路由、强制其必须导出，
   *    把"每加一个新路由都要记得做"从人的自觉变成机器的断言。
   *
   * 教训：中间件能改的是响应，不是路由。凡是"路由层没匹配上"的问题，中间件补不了；
   * 而带着补偿头返回错误状态，比干脆不补偿更难排查。
   */
  // 非私有路径：继续正常处理（静态资源 / API）
  const res = await context.next();

  record(context, url, res && res.status);
  return res;
}
