/**
 * RoboParts Hosted MCP 端点 —— Streamable HTTP
 * POST https://roboparts.cc/mcp
 *
 * ═══════════════════════════════════════════════════════════════════════════
 * 【20260806-00 · 为什么建这个东西 —— 证据链，不是拍脑袋】
 *
 * 连续三轮我们都在修「AI 找不到接入入口」，依次补了三个位置：
 *   20:00  llms.txt 加零摩擦接入指令      → stat:src:agent = 0
 *   21:00  下沉到 18 个真实被抓的 HTML 页  → stat:src:agent = 0
 *   22:00  注入 meta.access 到 25 个 JSON  → stat:src:agent = 0
 * 与此同时 /api/* 的抓取占比 16% → 36.6% → 71.1%，真实爬虫命中 27 → 42 → 45。
 *
 * 结论已经不能再回避：**AI 大量地读我们，从不注册我们。**
 * "位置"这条线已被三次实验证伪，不存在第四个值得补的位置。
 * 瓶颈不在"知不知道有入口"，而在**入口本身要求的动作太重**：
 *   领 key → 存 key → 装包 → 起进程 → 才能问第一个问题。
 * 对一个只是想确认"这两个零件能不能配"的 Agent 来说，这个代价远大于收益，
 * 它宁可去读我们的 JSON 自己猜 —— 遥测里 71% 的 /api/* 抓取就是这个行为的证据。
 *
 * 同赛道对手（ResolveMesh / FoundryNet）给出的答案是一致的：**不发包，挂托管端点**。
 * 用户侧成本从「装包 + 领 key + 起进程」降到「粘贴一个 URL」。
 * 我们已经跑在 Pages Functions 上，加一个路由即可，且不依赖任何人工令牌
 * （npm 那条路至今卡在人工换发 Granular Token —— 那是别人的日程，不是我们的）。
 *
 * ⚠️ 本端点默认免鉴权只读。这意味着「注册数」不再是 AI 通道的唯一转化信号，
 *    若不同步埋点，我们会重蹈"指标看不见 = 以为没人用"的覆辙。
 *    故 recordMcp() 与端点同生共死：见下方遥测段。
 * ═══════════════════════════════════════════════════════════════════════════
 */

import { judgePair, loadEntityMap, loadCuratedList } from './_lib/compat_engine.js';

const SERVER_NAME = 'roboparts';
const SERVER_VERSION = '1.1.0';

/** 支持的协议版本，降序。客户端报的版本若在列则原样回应，否则回落到首个。 */
const SUPPORTED_PROTOCOLS = ['2025-06-18', '2025-03-26', '2024-11-05'];
const PREFERRED_PROTOCOL = SUPPORTED_PROTOCOLS[0];

const CATEGORIES = [
  'actuators', 'sensors', 'chips', 'protocols', 'platforms',
  'llms', 'interfaces', 'flexible_actuators', 'robot_ai_models', 'data_acquisition',
  'connectors',
];

/**
 * 【20260810】MCP 资源：把训练数据集暴露给 agent 自动发现。
 * 这是「让 agent 直接发现 RoboParts 有一份可训练消费的数据集」的关键一环，
 * 与物理 AI / 具身智能方向直接呼应。resources/read 不返回 10MB 全文
 * （会撑爆单次响应），而返回 meta 摘要 + 直链，完整文件由调用方 HTTP GET 拉取。
 */
const RESOURCES = [
  {
    uri: 'https://roboparts.cc/api/training_dataset.json',
    name: 'RoboParts 物理 AI 训练数据集',
    description:
      '面向物理 AI / 具身智能 / TurboVLA 类 V+L→A 策略的多模态结构化数据集（schema v2.0）：零件目录' +
      '（含标准标签、证据等级、多模态暴露 force/tactile/geometric/electrical/vision）+ ' +
      '兼容性关系（四维裁决现算，并标注 interaction_type 与 force_profile 力觉剖面）+ ' +
      '互操作性标准登记表。force/tactile 仅声明级参数，原始传感时序为零。免鉴权，HTTP GET 即可拉取全文。',
    mimeType: 'application/json',
  },
];

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Accept, Authorization, MCP-Protocol-Version, Mcp-Session-Id',
  'Access-Control-Expose-Headers': 'Mcp-Session-Id, MCP-Protocol-Version',
  'Access-Control-Max-Age': '86400',
};

const jsonHeaders = { ...corsHeaders, 'Content-Type': 'application/json; charset=utf-8' };

/* ═══════════════════════════════════════════════════════════════════════════
 * 遥测 —— 端点侧独立埋点
 *
 * 免鉴权端点没有 user 概念，KV 里的 stat:users:* 永远看不到它。
 * 若只靠中间件的 path:/mcp 计数，我们只知道"有人打了这个路径"，
 * 却不知道**它到底问了什么** —— 而"AI 实际在问哪类问题"是我们目前
 * 最缺、也最值钱的一手信息（比任何竞品报告都真）。
 *
 * 约束与中间件一致：isolate 内存累加 + 分片落盘 + 日写额度兜底，
 * 绝不按请求写 KV，绝不让遥测影响响应正确性。
 * 复用 metrics: 前缀，scripts/read_metrics.py 无需改造即可读到。
 * ═══════════════════════════════════════════════════════════════════════════ */
const SHARDS = 16;
const METRIC_TTL = 60 * 60 * 24 * 90;
const MAX_WRITES_PER_ISOLATE_DAY = 200;
let _buf = Object.create(null);
let _writes = 0;
let _writeDay = '';
let _shard = -1;
/** 分片号懒初始化：Cloudflare Workers 禁止在模块顶层作用域调用 Math.random()
 *  （启动即抛错 → 配合 _routes.json 的 /* 会造成全站 404），故必须在请求作用域内
 *  首次使用时才取值。每个 isolate 取一次，全天复用同一分片。 */
function shardOf() {
  if (_shard < 0) _shard = Math.floor(Math.random() * SHARDS);
  return _shard;
}

function bump(key, n = 1) { _buf[key] = (_buf[key] || 0) + n; }

/* 【20260806-15】flush 串行化 —— 修一个「计数器自己在丢数」的静默缺陷。
 *
 * 实测证据：对生产端点连打 2 次 tools/call 后，`mcp:tool:check_compatibility`
 * 纹丝不动（停在 11），而 `mcp:toolsrc:script:check_compatibility` 记到了 1。
 * 不是巧合，是下面这条竞态的确定性后果：
 *
 *   每次 tools/call 会**连续两次**调 recordMcp（先 tool:，后 toolsrc:），
 *   各自 waitUntil(flushMcp)。两个 flush 交错执行：
 *     A: 取走 _buf={tool:1} → await kv.get(key) ──┐ 读到 prev
 *     B: 取走 _buf={toolsrc:1} → await kv.get(key) ┘ 读到**同一份** prev
 *     A: put(prev + tool:1)
 *     B: put(prev + toolsrc:1)   ← 后写覆盖，A 的 tool: 计数凭空消失
 *
 * 危害不在于少了几个数，而在于**它让计数器在无声地低报，却看起来一切正常**。
 * MCP 是否有真实需求这个 P0 商业判断正是建立在这些计数上——
 * 一个会丢写的仪表，读出来的任何结论都只是下界，却极容易被当成精确值。
 *
 * 修法：isolate 内用一条 promise 链把 flush 串起来，保证第 N+1 次的 kv.get
 * 一定发生在第 N 次的 kv.put 完成之后。副作用是每请求通常只剩一次 KV 写
 * （后一次 flush 发现 _buf 已空即返回），写额度反而更省。
 *
 * 【仍未解决·如实记录】跨 isolate 的同分片竞争依旧存在：两个 isolate 若随机
 * 取到同一 shard 并同时写，还是会互相覆盖。彻底解决需要 isolate 独占 key
 * （读侧 scripts/read_metrics.py 现按固定 s0..s15 遍历，须同步改成前缀列举）
 * 或 Durable Object。故当前读数应按**下界**理解，不可当作精确值。
 */
let _flushChain = Promise.resolve();

function scheduleFlush(context) {
  _flushChain = _flushChain.then(() => flushMcp(context.env)).catch(() => {});
  context.waitUntil(_flushChain);
}

async function flushMcp(env) {
  const entries = Object.entries(_buf);
  if (!entries.length) return;
  const day = new Date().toISOString().slice(0, 10);
  if (day !== _writeDay) { _writeDay = day; _writes = 0; }
  if (_writes >= MAX_WRITES_PER_ISOLATE_DAY) return;
  _buf = Object.create(null);
  const kv = env && env.USER_CREDITS;
  if (!kv) return;
  _writes++;
  const key = `metrics:${day}:s${shardOf()}`;
  let prev = {};
  try { prev = (await kv.get(key, { type: 'json' })) || {}; } catch { /* 读失败按新建处理 */ }
  for (const [k, v] of entries) prev[k] = (prev[k] || 0) + v;
  prev._updated = new Date().toISOString();
  await kv.put(key, JSON.stringify(prev), { expirationTtl: METRIC_TTL });
}

/** 自检探针隔离：与中间件同一个头，飞轮自己的验证流量绝不混入真实信号。 */
const SELFTEST_HEADER = 'x-roboparts-selftest';

/* ───────────────────────────────────────────────────────────────────────────
 * 调用方归因 —— 为什么必须在 tools/call 现场记
 *
 * clientInfo 只在 initialize 出现，而本端点是无状态 HTTP：initialize 与
 * tools/call 是两个独立请求，没有 session 能把二者缝合。于是 `client:*` 与
 * `tool:*` 是两条互不相交的计数线 —— 我们知道"有 N 次业务调用"，也知道
 * "有哪些 client 握过手"，却**无法知道那 N 次是谁打的**。
 *
 * 这正是最贵的一个未知：它直接决定"MCP 到底有没有真实需求"。若不在调用现场
 * 留下归因，任何"已剔除探针"的说法都是把「无法归因」渲染成「已归因」——
 * 与 L1.22–L1.25 同族的假绿，且发生在最影响判断的商业指标上。
 * User-Agent 是 tools/call 现场唯一稳定可得的调用方线索，故在此分类落盘，
 * 让业务调用从下一次起真正可分账。
 * ─────────────────────────────────────────────────────────────────────────── */
const PROBE_UA_RE = /probe|verifymcp|enricher|scanner|health[-_]?check|monitor|inspector|glama|glimind|mcpbeat|scoring/i;

/** 归因粒度刻意取粗：probe/script/browser/bot/unknown，避免 KV 键爆炸。 */
function callerKind(context) {
  try {
    const ua = context.request.headers.get('user-agent') || '';
    if (!ua) return 'empty-ua';
    if (PROBE_UA_RE.test(ua)) return 'probe';
    if (/curl|wget|python-requests|httpx|go-http|java\/|okhttp|axios|node-fetch|postman/i.test(ua))
      return 'script';
    if (/bot|spider|crawler/i.test(ua)) return 'bot';
    if (/mozilla|safari|chrome/i.test(ua)) return 'browser';
    return 'unknown';
  } catch { return 'unknown'; }
}

function recordMcp(context, event) {
  try {
    const ns = context.request.headers.get(SELFTEST_HEADER) ? 'selftest:mcp' : 'mcp';
    bump(`${ns}:${event}`);
    // MCP 调用天然低频且每一次都是强信号（真有 Agent 在用），立即落盘，
    // 不能像普通流量那样等下一个请求来触发 —— 零流量站点上那等于永久丢失。
    // 经 scheduleFlush 串行化，避免同一请求内两次 record 的 flush 互相覆盖。
    scheduleFlush(context);
  } catch { /* 遥测永不影响主流程 */ }
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 工具定义
 * ═══════════════════════════════════════════════════════════════════════════ */

const TOOLS = [
  {
    name: 'search_components',
    description:
      '搜索机器人零部件。可按品类、关键词筛选，返回匹配条目的摘要（id/name/category/manufacturer/关键规格/证据等级）。' +
      '覆盖执行器、传感器、芯片、通信协议、接口、机器人平台、具身智能模型等 10 个品类。' +
      '库存实时口径（总数/可选型/已隔离）见 initialize 的 instructions 或 GET /mcp 的 dataset 字段 —— ' +
      '此处不写死数字，避免文案与真实库存漂移。',
    inputSchema: {
      type: 'object',
      properties: {
        category: {
          type: 'string',
          description:
            '品类精确筛选，取值必须来自 enum（严格相等，不做别名映射：传 "actuator"、"电机" 均返回空）。' +
            '不传则跨全部 10 个品类检索。注意品类与 ID 前缀不是一一对应的，请以本字段为准。',
          enum: CATEGORIES,
        },
        keyword: {
          type: 'string',
          description:
            '关键词，对 name / name_en / manufacturer / type / protocol / interface / description ' +
            '七个字段做大小写不敏感的**子串**匹配（非分词、非模糊、不纠错）。' +
            '**中英文命中集合可能完全不重叠**，务必两种都试：实测 "六维力" 命中 16 条、"force torque" 命中 2 条、' +
            '交集为 0（部分国产条目尚无英文名）。' +
            '多个词不做 AND 拆分，"harmonic drive 20Nm" 会被当作一整个串匹配，实测返回 0 条；' +
            '请只给一个词（如 "harmonic" 命中 9 条），再用 category 收窄。',
        },
        limit: { type: 'number', description: '返回条数上限，默认 10，最大 50（超出按 50 截断）。', default: 10 },
        include_market_intelligence: {
          type: 'boolean',
          description:
            '默认 false。库内另有 3 条市场情报条目（专利地图/咨询报告/趋势条目），它们不是可采购零件，' +
            '默认不返回；仅在你确实想查行业研究材料时设为 true。',
          default: false,
        },
      },
    },
  },
  {
    name: 'get_component_detail',
    description:
      '按 ID 获取单个零部件的完整字段，包含 source_tier（数据来源等级）、confidence（置信度）、' +
      'data_quality 与 mechanical_interface 等元数据。用于在做出采购/设计决策前核对证据强度。',
    inputSchema: {
      type: 'object',
      properties: {
        id: {
          type: 'string',
          description:
            '零部件 ID，如 ACT-001 / CHIP-001 / SENS-001。大小写与连字符需完全匹配，不做模糊查找；' +
            '建议先由 search_components 返回值取得。注意 ID 前缀不能反推 category（库内存在前缀与品类不一致的条目，实时条数见 GET /mcp 的 dataset.id_category_mismatch）。',
        },
      },
      required: ['id'],
    },
  },
  {
    name: 'check_compatibility',
    description:
      '判定两个零部件在 protocol（协议）/ electrical（电气）/ mechanical（机械）/ software（ROS2）四个维度的兼容性，' +
      '返回逐维结论、总体判定与置信说明。注意：结论基于厂商公开声明字段做规则推断，非实验室实测；' +
      '厂商未声明的维度记为"无法判定"，既不计入兼容也不计入不兼容。',
    inputSchema: {
      type: 'object',
      properties: {
        component1_id: {
          type: 'string',
          description:
            '零件 1 的 ID，形如 ACT-001 / CHIP-001 / PROTO-012。请先用 search_components 取得，' +
            '不要自行拼造：ID 前缀与 category 并非一一对应（' +
            '例如 sensors 品类下存在 CHIP-67，platforms 下存在 ACT-patsnap-actuator；' +
            '实时不一致条数见 GET /mcp 的 dataset.id_category_mismatch），' +
            '按品类猜前缀会取到错误条目或直接查无此项。',
        },
        component2_id: {
          type: 'string',
          description: '零件 2 的 ID，取值方式同 component1_id。两个 ID 可以属于不同品类（跨品类比对正是本工具的用途）。',
        },
      },
      required: ['component1_id', 'component2_id'],
    },
  },
  {
    name: 'recommend_for_application',
    description:
      '按应用场景推荐零部件组合，可选预算上限（USD）。返回各品类的候选项及推荐理由。' +
      '这是基于库内字段的启发式筛选，不构成工程选型意见，最终仍需核对厂商原始数据手册。',
    inputSchema: {
      type: 'object',
      properties: {
        application: {
          type: 'string',
          description:
            '应用场景，必填，取值限 enum。判定方式是拿一组固定场景词去匹配条目的 ' +
            'applications/name/type/description 字段，而非人工标注的场景分类：' +
            'humanoid=人形/双足，quadruped=四足，robot_arm=机械臂/协作臂，amr=移动机器人/AGV，industrial=工业产线。' +
            '若某品类下无任何条目命中该场景，该品类会退化为品类罗列并在 scene_matched=false 中标明，' +
            '此时结果不代表适配该场景，应改用 search_components 按具体参数筛选。',
          enum: ['humanoid', 'quadruped', 'robot_arm', 'amr', 'industrial'],
        },
        budget: {
          type: 'number',
          description:
            '单件预算上限（USD，正数），可选。**价格字段覆盖率有限**（实时覆盖数见 GET /mcp 的 dataset.priced），' +
            '因此本参数只能剔除「确定超预算」的条目，不能保证结果全部在预算内。' +
            '每条结果会附 price_fit：within（确定在预算内）/ partial（区间跨越预算）/ unknown（库内无价格，未经校验）。' +
            '不传则不做任何价格筛选，也不返回 price_fit。',
        },
        count: { type: 'number', description: '每品类返回条数，默认 3，上限 10（超出按 10 截断）。四个品类各自独立计数。', default: 3 },
      },
      required: ['application'],
    },
  },
  {
    name: 'get_parameter_semantics',
    description:
      '获取参数口径规范：同一个 torque/speed 字段在不同厂商那里含义可能不同（库内 torque 出现 19 种口径、speed 37 种，' +
      '甚至混入 Gbps 与 rad/s）。本工具返回物理红线、单位换算、可比性分级与向厂商问询的清单，' +
      '用于判断两份参数表到底能不能直接比较。',
    inputSchema: { type: 'object', properties: {} },
  },
];

// 对外契约的唯一真相源。skills/manifest.json、skills/README.md、agent-discovery.json
// 的 skills 段必须由 scripts/gen_skills_manifest.mjs 从这里生成，禁止手写第二份。
// 20260807-12 教训：手写的 manifest 声明了 5 个 mcp_tool 技能，实跑 5/5 全部调不通
//（2 个工具名不存在、3 个参数名对不上），而它正是我们请外部框架自动解析的机读契约。
// Cloudflare Pages Functions 只识别 onRequest*，多一个具名导出无副作用。
export { TOOLS };

/* ═══════════════════════════════════════════════════════════════════════════
 * 数据加载（isolate 级缓存）
 *
 * entities.json 约 1MB，逐请求 JSON.parse 会吃掉可观 CPU。
 * 缓存在模块作用域，同一 isolate 内复用；isolate 回收即自然失效，不会读到陈旧数据超过分钟级。
 * ═══════════════════════════════════════════════════════════════════════════ */
let _entityMapCache = null;
let _entityListCache = null;
let _curatedListCache = null;
let _flywheelExtraCache = null;

async function getEntities(env, request) {
  if (_entityMapCache && _entityListCache) {
    return { map: _entityMapCache, list: _entityListCache, curatedList: _curatedListCache, flywheelExtra: _flywheelExtraCache };
  }
  const map = await loadEntityMap(env, request);   // 合并飞轮贡献层后的全量（裁决用）
  const list = Object.values(map);
  const curatedList = await loadCuratedList(env, request);  // 主库真值（对外数字口径，不含贡献层）
  _entityMapCache = map;
  _entityListCache = list;
  _curatedListCache = curatedList;
  _flywheelExtraCache = Math.max(0, list.length - curatedList.length);
  return { map, list, curatedList, flywheelExtra: _flywheelExtraCache };
}

async function getJsonAsset(env, request, path) {
  const resp = await env.ASSETS.fetch(new URL(path, request.url));
  if (!resp.ok) throw new Error(`${path} 加载失败: HTTP ${resp.status}`);
  return await resp.json();
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 数据集实况（运行时现算）
 *
 * 【20260808-10】为什么必须现算，而不是把常量里的数字改对一次：
 * 本次巡检实测，线上 MCP 对每一个接入的 agent 宣称「收录 688 条实体，其中 685 条
 * 可选型」——真值是 706 / 703，`GET /mcp` 的 `dataset.total_entities: 688` 更是**机读**
 * 错值，直接喂给目录站与调用方。而 `ID 前缀与 category 不一致 38 条` 的真值只有 15，
 * 虚高 2.5 倍。三个数字都不是一开始就错，是**入库涨了、文案没跟**。
 *
 * 本仓已有「页面数字唯一真相源 + 全量注入器」的纪律，但注入器只覆盖 *.html 与 api/，
 * **覆盖不到 functions/ 里的模板字符串** —— 服务层因此成了唯一一处数字会自己腐烂的地方。
 * 修法不是再挂一个注入器（等于给易腐常量加保鲜膜），而是让服务层从它**本来就已经
 * 加载好的那份数据**里现算：数字要么是真的，要么根本不出现，不存在"陈旧"这个状态。
 *
 * 同时补上一个从未对外披露的事实：库内有一批 quarantine=true 的已知可疑条目
 * （占比两位数）。旧 instructions 只说"标记 quarantine 的不应作为决策依据"，
 * 却从不说有多少条 —— 调用方无从判断这个提醒是边角情况还是普遍情况。
 * ═══════════════════════════════════════════════════════════════════════════ */
const ID_PREFIX_CATEGORY = {
  ACT: 'actuators', SENS: 'sensors', CHIP: 'chips', PROT: 'protocols',
  IFACE: 'interfaces', PLAT: 'platforms', LLM: 'llms',
  FLEX: 'flexible_actuators', DAQ: 'data_acquisition', RAM: 'robot_ai_models',
  CONN: 'connectors',
};

/**
 * 【20260809-05】白名单语义：可选型 = entity_kind 明确为 component
 * （缺字段的老数据按 component 放行，与 compat_engine.nonJudgeableKind 同一口径）。
 * 此前这里写的是黑名单（`!== 'market_intelligence' && !== 'organization'`）。
 * 黑名单的毛病不在当时算错，而在**新增种类时静默失效**：本轮新增 specification /
 * software 两档后，黑名单会继续把 101 条协议规范与 86 条 AI 模型算作"可选型零部件"，
 * 且不报任何错。种类是开放集合，过滤必须用白名单。
 */
function isSelectableComponent(e) {
  return !e.entity_kind || e.entity_kind === 'component';
}

function datasetFacts(list, flywheelExtra) {
  const total = list.length;
  const marketIntel = list.filter((e) => e.entity_kind === 'market_intelligence').length;
  const quarantined = list.filter((e) => e.quarantine === true).length;
  const priced = list.filter((e) => e.price_range).length;
  const idCatMismatch = list.filter((e) => {
    const p = String(e.id || '').split('-')[0].toUpperCase();
    return ID_PREFIX_CATEGORY[p] && ID_PREFIX_CATEGORY[p] !== e.category;
  }).length;
  // 【20260809-03】此前 selectable = total - marketIntel，把 9 条**企业主体条目**
  // （Figure AI / 特斯拉 / 波士顿动力…）算进了"可选型零部件"。公司不是零件。
  const organizations = list.filter((e) => e.entity_kind === 'organization').length;
  // 【20260809-05】同理：协议/接口规范（EtherCAT、USB 3.0…）与 AI 模型（GPT-4o、RT-2…）
  // 也不是可采购零件。它们此前占 selectable 的 27%。
  const specifications = list.filter((e) => e.entity_kind === 'specification').length;
  const software = list.filter((e) => e.entity_kind === 'software').length;
  const selectable = list.filter(isSelectableComponent).length;
  return {
    total_entities: total,
    flywheel_contributions: flywheelExtra || 0,  // 飞轮贡献层额外可查实体（开源 BOM 反喂等），不计入 total_entities
    selectable,                       // 可进检索/推荐的条目（白名单：仅 component）
    market_intelligence: marketIntel, // 专利地图/咨询报告，默认不出现在结果里
    organizations,                    // 企业/机构主体条目，无物理接口，不进选型与兼容判定
    specifications,                   // 接口/协议规范条目（规范本身，不是实现它的零件）
    software,                         // AI 模型 / 软件条目，无机械与电气接口
    quarantined,                      // 有已知疑点、默认不进选型结果
    usable: selectable - list.filter((e) => e.quarantine === true
      && isSelectableComponent(e)).length,
    priced,                           // 带 price_range 的条目
    id_category_mismatch: idCatMismatch,
    categories: CATEGORIES,
  };
}

/** 把实况渲染成给 agent 看的一段话。数据不可用时返回 ''（宁可不说，绝不说错）。 */
function factsNarrative(f) {
  if (!f) return '';
  const pct = f.total_entities ? Math.round((f.quarantined * 1000) / f.total_entities) / 10 : 0;
  return [
    `数据集实况（本次响应实时统计，非写死文案）：共 ${f.total_entities} 条实体，`,
    `其中 ${f.selectable} 条为可选型零部件、${f.specifications} 条为接口/协议规范（EtherCAT、USB 3.0…）、`,
    `${f.software} 条为 AI 模型与软件（GPT-4o、RT-2…）、${f.market_intelligence} 条为市场情报（专利地图/咨询报告）、`,
    `${f.organizations} 条为企业/机构主体条目（如 Figure AI、波士顿动力）。`,
    `后四类都没有物理接口，不进检索推荐、也不作为兼容性判定操作数。`,
    `另有 ${f.quarantined} 条（占 ${pct}%）标记 quarantine=true —— 存在已知疑点（占位 ID / 无法核实的厂商 / 重复 / 根本不是零件的行业词），`,
    `本端点的检索与推荐已默认排除它们，实际可选型 ${f.usable} 条。若你从 REST 接口（/api/*.json）自行取数，`,
    `这些条目会照原样返回，请自行按 quarantine 字段过滤。带价格字段的仅 ${f.priced} 条。`,
  ].join('');
}

/** 安全取实况：任何失败都返回 null，由调用方降级为"不提数字"。 */
async function tryFacts(env, request) {
  try {
    const { curatedList, flywheelExtra } = await getEntities(env, request);
    return datasetFacts(curatedList, flywheelExtra);
  } catch (e) {
    return null;
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 工具实现
 * ═══════════════════════════════════════════════════════════════════════════ */

function summarize(e) {
  return {
    id: e.id,
    name: e.name,
    category: e.category,
    manufacturer: e.manufacturer || null,
    type: e.type || null,
    key_specs: {
      torque: e.torque || null,
      speed: e.speed || null,
      voltage: e.voltage || null,
      protocol: e.protocol || null,
      interface: e.interface || null,
      price_range: e.price_range || null,
    },
    evidence: {
      source_tier: e.source_tier || null,
      confidence: e.confidence || null,
      verified: e.verified === true,
      entity_kind: e.entity_kind || 'component',
    },
  };
}

function toolSearch(list, args) {
  const { category, keyword } = args || {};
  const limit = Math.min(Math.max(parseInt(args?.limit ?? 10, 10) || 10, 1), 50);
  const includeMI = args?.include_market_intelligence === true;

  // 默认剔除市场情报条目（专利地图 / 咨询报告 / 趋势条目）。
  // 它们留在库里有参考价值，但把「罗兰贝格执行器趋势」当成一款可选执行器返回给 Agent，
  // 会让对方对整个数据集失去信任 —— 见 scripts/govern_entity_kind.py 的发现经过。
  let rows = includeMI ? list : list.filter(e => e.entity_kind !== 'market_intelligence');
  if (category) rows = rows.filter(e => e.category === category);
  if (keyword) {
    const kw = String(keyword).toLowerCase();
    rows = rows.filter(e =>
      [e.name, e.name_en, e.manufacturer, e.type, e.protocol, e.interface, e.description]
        .filter(Boolean).some(f => String(f).toLowerCase().includes(kw))
    );
  }

  return {
    total_matched: rows.length,
    returned: Math.min(rows.length, limit),
    results: rows.slice(0, limit).map(summarize),
    note: rows.length > limit
      ? `共匹配 ${rows.length} 条，此处返回前 ${limit} 条。可用 category/keyword 收窄或提高 limit。`
      : undefined,
  };
}

function toolDetail(map, args) {
  const id = args?.id;
  // 参数缺失与查无此物是两件事，必须分开回答。
  // map[undefined] 同样落空，若共用下面的 not_found 分支，就会对外断言「未找到实体: undefined」
  // 并让调用方去 search_components 核对 ID —— 那是关于数据库的断言，而真相是本次调用没给参数。
  if (id === undefined || id === null || String(id).trim() === '') {
    return {
      error: '缺少必填参数 id',
      error_kind: 'invalid_params',
      hint: '请传入 id，形如 ACT-001 / CHIP-001 / SENS-001。这不是「查无此物」，而是本次调用未提供该参数，无需去核对 ID 是否存在。',
    };
  }
  const e = map[id];
  if (!e) {
    return {
      error: `未找到实体: ${id}`,
      error_kind: 'not_found',
      hint: '请先用 search_components 确认 ID。ID 形如 ACT-001 / CHIP-001 / SENS-001。',
    };
  }
  return {
    entity: e,
    evidence_note:
      'source_tier 与 confidence 表示该条目的证据强度，非厂商背书。' +
      'quarantine 为 true 表示该条数据存在已知疑点，已被隔离，不应直接用于决策。',
  };
}

function toolCompat(map, args) {
  // 同 toolDetail：先分辨「没给参数」再判断「库里没有」，否则漏传 component2_id 会被报成
  // 「未找到实体: undefined」，把调用方的请求错误伪装成对数据库的事实断言。
  const missing = ['component1_id', 'component2_id'].filter((k) => {
    const v = args?.[k];
    return v === undefined || v === null || String(v).trim() === '';
  });
  if (missing.length) {
    return {
      error: `缺少必填参数: ${missing.join(', ')}`,
      error_kind: 'invalid_params',
      hint: '请同时传入 component1_id 与 component2_id。这不是「查无此物」，而是本次调用未提供该参数，无需去核对 ID 是否存在。',
    };
  }
  const a = map[args.component1_id];
  const b = map[args.component2_id];
  if (!a) return { error: `未找到实体: ${args.component1_id}`, error_kind: 'not_found', hint: '请先用 search_components 确认 ID。' };
  if (!b) return { error: `未找到实体: ${args.component2_id}`, error_kind: 'not_found', hint: '请先用 search_components 确认 ID。' };
  return judgePair(a, b);
}

const APP_HINTS = {
  humanoid: ['humanoid', '人形', 'biped', '双足'],
  quadruped: ['quadruped', '四足', 'legged'],
  robot_arm: ['arm', '机械臂', 'manipulator', 'collaborative'],
  amr: ['amr', 'agv', 'mobile', '移动'],
  industrial: ['industrial', '工业', 'factory'],
};

function toolRecommend(list, args) {
  const app = args?.application;
  const count = Math.min(Math.max(parseInt(args?.count ?? 3, 10) || 3, 1), 10);
  const budget = args?.budget != null ? Number(args.budget) : null;
  const hints = APP_HINTS[app] || [];

  // 价格区间解析。
  //
  // 旧实现是 `String(e.price_range).match(/[\d.]+/g)[0]`，有两处错误：
  //   1) 字符类不含逗号，'From $13,500' 被截成 13 —— 全库最贵的条目之一
  //      因此能通过 budget=50。解析失败必须表现为「未知」，绝不能表现为「很便宜」。
  //   2) 只取第一个数字。'500-1000' 取 500，于是上限 1000 的条目在 budget=600
  //      时被当成「完全在预算内」返回，而它可能并不是。
  //
  // 现在返回 {min,max,kind}，判不出来的一律 kind='unknown'，交给调用方显式看见。
  const priceBounds = (e) => {
    const raw = String(e.price_range || '').trim();
    if (!raw) return { min: null, max: null, kind: 'unknown' };
    // 去千分位逗号（只去夹在数字之间的，避免误伤 "a, b" 这类枚举写法）
    const norm = raw.replace(/(\d),(?=\d{3}(\D|$))/g, '$1');
    const nums = (norm.match(/\d+(?:\.\d+)?/g) || []).map(parseFloat);
    if (!nums.length) return { min: null, max: null, kind: 'unknown' };   // 'N/A (internal)' 等
    if (/\+|以上|起|from/i.test(norm)) return { min: nums[0], max: Infinity, kind: 'open' };
    if (nums.length >= 2) return { min: Math.min(...nums), max: Math.max(...nums), kind: 'range' };
    return { min: nums[0], max: nums[0], kind: 'exact' };
  };

  // 相对预算的判定。四个值的语义必须说死：
  //   within  —— 价格上限 <= 预算，确定买得起
  //   partial —— 预算落在区间内，可能买得起，取决于具体配置
  //   over    —— 价格下限已超预算，确定买不起（唯一可安全剔除的一类）
  //   unknown —— 库内没有价格。**这不是「买得起」，只是没有依据。**
  const priceFit = (e, b) => {
    if (b == null) return null;
    const { min, max, kind } = priceBounds(e);
    if (kind === 'unknown') return 'unknown';
    if (max <= b) return 'within';
    if (min <= b) return 'partial';
    return 'over';
  };

  const pick = (cat) => {
    let rows = list.filter(e =>
      e.category === cat &&
      e.quarantine !== true &&
      isSelectableComponent(e)   // 白名单：只有实物零部件进选型候选（见 isSelectableComponent 注释）
    );
    const scored = rows.map(e => {
      const hay = [e.applications, e.name, e.type, e.description]
        .flat().filter(Boolean).join(' ').toLowerCase();
      const hit = hints.filter(h => hay.includes(h)).length;
      return { e, hit };
    });
    const matched = scored.filter(s => s.hit > 0).sort((x, y) => y.hit - x.hit);
    // 无场景标注时退回全量罗列 —— 但必须**逐品类**说清这一点。
    // 此前只在最外层给一句总的 caveat，若 actuators 命中而 platforms 没命中，
    // 调用方会以为四个品类都是场景匹配出来的，等于用一个真结论替另一个假结论背书。
    const sceneMatched = matched.length > 0;
    let out = (sceneMatched ? matched : scored).map(s => s.e);

    // ── 预算过滤 ──────────────────────────────────────────────────────────
    // 旧行为：`p == null || p <= budget`，即**无价格的条目无条件放行**。
    // 全库仅少数条目有 price_range（实时数见 dataset.priced），于是 budget=50 会原样返回
    // Tesla Optimus / Figure 03 这类整机，而响应里还回显 budget_usd=50 —— 
    // 等于主动断言「已按预算过滤」。这与本项目在 check_compatibility 上
    // 的既有教义（未声明的维度记为「无法判定」，不计入兼容）直接冲突：
    // **未知不得冒充通过**。
    //
    // 现在：只剔除 over（确定超预算）；unknown 保留但打标并计数，
    // 且排序上让有价格依据的排在前面。剔除 unknown 是另一种失真 ——
    // 「没有价格数据」不等于「买不起」，直接删掉会让 71.8% 的库存凭空消失。
    let budgetNote;
    if (budget != null) {
      const RANK = { within: 0, partial: 1, unknown: 2 };
      const tagged = out.map(e => ({ e, fit: priceFit(e, budget) }));
      const kept = tagged.filter(t => t.fit !== 'over');
      const dropped = tagged.length - kept.length;
      // 稳定排序：同一 fit 档内保持原有的场景相关性顺序
      kept.forEach((t, i) => { t._i = i; });
      kept.sort((a, b) => (RANK[a.fit] - RANK[b.fit]) || (a._i - b._i));
      const n = f => kept.filter(t => t.fit === f).length;
      const nUnknown = n('unknown'), nWithin = n('within'), nPartial = n('partial');
      budgetNote =
        `预算 ${budget} USD：确定在预算内 ${nWithin} 条，可能在预算内 ${nPartial} 条，` +
        `库内无价格、未经预算校验 ${nUnknown} 条，确定超预算已剔除 ${dropped} 条。` +
        (nUnknown ? '标记 price_fit="unknown" 的条目**不代表符合预算**，只代表库内没有价格依据，需向厂商询价。' : '');
      out = kept.map(t => t.e);
      const fitById = new Map(kept.map(t => [t.e.id, t.fit]));
      return {
        scene_matched: sceneMatched,
        basis: sceneMatched
          ? '按场景词命中数排序'
          : '该品类下无任何条目标注了此场景，以下仅为品类罗列，不代表适配该场景',
        budget_note: budgetNote,
        items: out.slice(0, count).map(e => {
          const s = summarize(e);
          s.price_fit = fitById.get(e.id) || 'unknown';
          return s;
        }),
      };
    }

    return {
      scene_matched: sceneMatched,
      basis: sceneMatched
        ? '按场景词命中数排序'
        : '该品类下无任何条目标注了此场景，以下仅为品类罗列，不代表适配该场景',
      items: out.slice(0, count).map(summarize),
    };
  };

  const recommendations = {
    actuators: pick('actuators'),
    sensors: pick('sensors'),
    chips: pick('chips'),
    platforms: pick('platforms'),
  };

  const unmatched = Object.entries(recommendations)
    .filter(([, v]) => !v.scene_matched).map(([k]) => k);

  return {
    application: app,
    budget_usd: budget,
    // budget_usd 单独出现会被读成「结果已按此预算过滤干净」。库内只有少数条目
    // 有价格字段，这个断言在多数品类上不成立，必须与口径说明同时出现。
    // 覆盖数从 list 现算 —— 曾写死 194/688，总数涨到 706 后分母就成了谎。
    budget_semantics: budget == null
      ? undefined
      : `库内 ${list.length} 条中仅 ${list.filter((e) => e.price_range).length} 条带 price_range。本次只剔除了「确定超预算」的条目；` +
        '每条结果附 price_fit（within=确定在预算内 / partial=可能在预算内 / unknown=库内无价格，未经校验）。' +
        'unknown 不是「符合预算」，逐品类数量见 recommendations[*].budget_note。',
    recommendations,
    method: '按 applications/name/type 字段的场景词命中数排序；已排除 quarantine 条目与市场情报条目',
    caveat: '这是基于库内声明字段的启发式筛选，不是工程选型结论；下单前请核对厂商原始数据手册。',
    coverage_warning: unmatched.length
      ? `以下品类在库内没有针对 ${app} 的场景标注，其结果仅为品类罗列、不代表适配：${unmatched.join(' / ')}。` +
        '这些品类建议改用 search_components 按具体参数筛选。'
      : undefined,
  };
}

/* ═══════════════════════════════════════════════════════════════════════════
 * JSON-RPC 分发
 * ═══════════════════════════════════════════════════════════════════════════ */

function rpcResult(id, result) { return { jsonrpc: '2.0', id, result }; }
function rpcError(id, code, message, data) {
  const e = { jsonrpc: '2.0', id: id ?? null, error: { code, message } };
  if (data !== undefined) e.error.data = data;
  return e;
}

// 【20260808-10】此处**刻意不写任何库存数字**：写死的数字会随入库增长而变成谎言
// （实测旧文案 688/685 在真值已是 706/703 时仍对每个 agent 播报了不知多少轮）。
// 精确条数由 buildInstructions() 在响应时从实时数据现算后追加。
const INSTRUCTIONS_STATIC = [
  'RoboParts 是仿生/人形机器人零部件的兼容性数据层（执行器、传感器、芯片、通信协议、接口、平台、具身智能模型等 10 个品类）。',
  '',
  '适合用它来做：确认两个零件能否搭配、按场景筛选候选件、核对某个参数的口径是否可比。',
  '',
  '必须如实转述给最终用户的边界：',
  '1. 我们既不生产也不转售任何零部件，与任何厂商无商业绑定，数据层保持中立。',
  '2. 兼容性结论来自厂商公开声明字段的规则推断，不是实验室实测。厂商未声明的维度一律标为"无法判定"，我们不会拿它凑分数。',
  '3. 参数口径在行业内并不统一（库内 torque 字段出现 19 种口径、speed 37 种），跨厂商直接比数字往往是错的 —— 需要时请调用 get_parameter_semantics。',
  '4. 标记 quarantine=true 的条目存在已知疑点，不应作为决策依据。',
  '',
  '本端点只读、免鉴权、不写入任何用户数据、不设 cookie。若需要写入类能力（BOM 保存、选型报告导出），见 https://roboparts.cc/mcp-guide',
].join('\n');

/**
 * 组装 instructions：静态边界声明 + 实时数据集实况。
 * 实况取不到时只返回静态部分 —— 少说一句，好过说一句陈旧的数字。
 */
function buildInstructions(facts) {
  const live = factsNarrative(facts);
  return live ? `${INSTRUCTIONS_STATIC}\n\n${live}` : INSTRUCTIONS_STATIC;
}

async function handleRpc(msg, context) {
  const { request, env } = context;
  const { id, method, params } = msg || {};
  const isNotification = id === undefined || id === null;

  switch (method) {
    case 'initialize': {
      const asked = params?.protocolVersion;
      const version = SUPPORTED_PROTOCOLS.includes(asked) ? asked : PREFERRED_PROTOCOL;
      const client = params?.clientInfo?.name;
      recordMcp(context, 'initialize');
      if (client) recordMcp(context, `client:${String(client).slice(0, 24).replace(/[^\w.-]/g, '_')}`);
      // 实况取数失败不阻断握手：tryFacts 返回 null，instructions 降级为纯静态边界声明。
      const initFacts = await tryFacts(env, request);
      return rpcResult(id, {
        protocolVersion: version,
        capabilities: { tools: { listChanged: false }, resources: { listChanged: false } },
        serverInfo: { name: SERVER_NAME, version: SERVER_VERSION, title: 'RoboParts 机器人零部件兼容性' },
        instructions: buildInstructions(initFacts),
      });
    }

    case 'notifications/initialized':
    case 'notifications/cancelled':
      return null;   // 通知无响应

    case 'ping':
      return rpcResult(id, {});

    case 'tools/list':
      recordMcp(context, 'tools_list');
      return rpcResult(id, { tools: TOOLS });

    case 'tools/call': {
      const name = params?.name;
      const args = params?.arguments || {};
      const toolSlug = String(name || 'unknown').slice(0, 32).replace(/[^\w.-]/g, '_');
      recordMcp(context, `tool:${toolSlug}`);
      // 归因线：与 tool:* 同时写，读侧据此把业务调用分账为 probe / 真实调用方。
      // 没有这一行，"业务调用 N 次"就永远只是个不可归因的裸数字。
      recordMcp(context, `toolsrc:${callerKind(context)}:${toolSlug}`);

      // 必填参数校验以 TOOLS 里对外公布的 required 为唯一依据，避免校验与 schema 各写一份而漂移。
      // 缺参属于协议层的请求错误（-32602），不能落进工具的业务失败分支被渲染成数据结论。
      const toolSpec = TOOLS.find((t) => t.name === name);
      if (toolSpec) {
        const missingArgs = (toolSpec.inputSchema?.required || []).filter((k) => {
          const v = args[k];
          return v === undefined || v === null || (typeof v === 'string' && v.trim() === '');
        });
        if (missingArgs.length) {
          recordMcp(context, 'invalid_params');
          return rpcError(id, -32602, `缺少必填参数: ${missingArgs.join(', ')}（工具 ${name}）`, {
            tool: name,
            missing_parameters: missingArgs,
            note: '这是请求参数缺失，不代表相关条目在库中不存在，请勿据此推断数据库无此数据。',
          });
        }

        // 【20260807-08】未知参数必须报错，不得静默丢弃。
        //
        // 实测：`search_components{"query":"harmonic reducer"}` 返回 total_matched=685、
        // 首条 ACT-001 DYNAMIXEL 智能舵机；换成 `{"query":"zzzznonexistentxyz"}` 返回**完全相同**的结果。
        // 因为本工具的筛选参数叫 keyword，`query` 属未知键 —— 旧实现直接忽略，
        // 于是「没有任何筛选条件」被当成「浏览全库」，把 685 条原样返回。
        //
        // 这是本仓修过三次的同族缺陷（truthy 折叠 / key_specs 空洞 / 未声明当 false）的第四型：
        // **不确定的输入被折叠成一个看起来很确定的输出**。而这一型危害更大，因为失败伪装成成功：
        // 调用方收到的不是错误，是「共匹配 685 条」—— 读起来像一次命中极广的成功检索。
        // Agent 会据此把 ACT-001 起的前 10 条当作 "harmonic reducer" 的最佳匹配来回答用户，
        // 错误结论还挂着 RoboParts 的名字。而 `query` 恰恰是 MCP 生态里最常见的检索参数名，
        // 不读 schema 直接猜的调用方几乎必然踩中 —— 我们刚把「用户照文档能接进来」这扇门修好，
        // 门后第一个工具却是这个行为。
        //
        // 判据以 schema 的 properties 为唯一依据，与 required 校验同源，杜绝两处各写一份而漂移。
        const allowed = Object.keys(toolSpec.inputSchema?.properties || {});
        const unknownArgs = Object.keys(args).filter((k) => !allowed.includes(k));
        if (allowed.length && unknownArgs.length) {
          recordMcp(context, 'invalid_params');
          // 常见误名 → 正确参数名，直接把人送回正轨，而不是只说"你错了"。
          const ALIAS = {
            query: 'keyword', q: 'keyword', search: 'keyword', term: 'keyword',
            text: 'keyword', name: 'keyword', kw: 'keyword',
            type: 'category', kind: 'category', class: 'category',
            max: 'limit', count: 'limit', top_k: 'limit', n: 'limit',
            id1: 'component1_id', id2: 'component2_id',
            component_id: 'id', entity_id: 'id',
          };
          const guesses = unknownArgs
            .map((k) => (ALIAS[k] && allowed.includes(ALIAS[k]) ? `${k} → ${ALIAS[k]}` : null))
            .filter(Boolean);
          return rpcError(id, -32602, `未知参数: ${unknownArgs.join(', ')}（工具 ${name}）`, {
            tool: name,
            unknown_parameters: unknownArgs,
            accepted_parameters: allowed,
            did_you_mean: guesses.length ? guesses : undefined,
            note:
              '本次调用已被拒绝，未返回任何数据。这样做是刻意的：若忽略未知参数继续执行，' +
              '筛选条件会被悄悄丢弃，你会收到一份「全库结果」并误以为它们是本次查询的匹配项。',
          });
        }
      }

      let payload;
      try {
        if (name === 'get_parameter_semantics') {
          payload = await getJsonAsset(env, request, '/api/parameter_semantics.json');
        } else if (name === 'search_components') {
          const { list } = await getEntities(env, request);
          payload = toolSearch(list, args);
        } else if (name === 'get_component_detail') {
          const { map } = await getEntities(env, request);
          payload = toolDetail(map, args);
        } else if (name === 'check_compatibility') {
          const { map } = await getEntities(env, request);
          payload = toolCompat(map, args);
        } else if (name === 'recommend_for_application') {
          const { list } = await getEntities(env, request);
          payload = toolRecommend(list, args);
        } else {
          return rpcError(id, -32602, `未知工具: ${name}`);
        }
      } catch (e) {
        // 数据源故障必须让调用方看见，绝不返回空结果假装查无此物（环境要点 #19）。
        recordMcp(context, 'tool_error');
        return rpcResult(id, {
          isError: true,
          content: [{ type: 'text', text: `RoboParts 数据源暂时不可用: ${String(e && e.message || e)}` }],
        });
      }

      return rpcResult(id, {
        content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }],
      });
    }

    case 'resources/list':
      return rpcResult(id, { resources: RESOURCES });
    case 'resources/read': {
      const uri = params?.uri;
      const res = RESOURCES.find((r) => r.uri === uri);
      if (!res) return rpcError(id, -32602, `未知资源: ${uri}`);
      try {
        const data = await getJsonAsset(env, request, '/api/training_dataset.json');
        const text = JSON.stringify({
          uri: res.uri,
          note: '完整数据集约 10MB，建议直接 HTTP GET 该 uri 拉取。此处仅返回 meta 摘要。',
          meta: data.meta || {},
        }, null, 2);
        return rpcResult(id, {
          contents: [{ uri: res.uri, mimeType: res.mimeType, text }],
        });
      } catch (e) {
        return rpcError(id, -32603, `资源读取失败: ${String(e && e.message || e)}`);
      }
    }
    case 'prompts/list':
      return rpcResult(id, { prompts: [] });

    default:
      if (isNotification) return null;
      return rpcError(id, -32601, `不支持的方法: ${method}`);
  }
}

/* ═══════════════════════════════════════════════════════════════════════════
 * HTTP 层
 * ═══════════════════════════════════════════════════════════════════════════ */

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: corsHeaders });
}

/**
 * GET 用于两个目的：
 *  - 带 Accept: text/event-stream 的是 MCP 客户端在尝试开 SSE 通道。本服务无服务端主动推送，
 *    按规范返回 405（明确表示"不提供"，客户端会安静地退回纯 POST 模式）。
 *  - 其余 GET 视为人/爬虫在浏览，返回一份自描述文档 —— 这本身就是 GEO 资产：
 *    抓到这个 URL 的 AI 能直接读懂怎么用它，无需再跳转。
 */
export async function onRequestGet(context) {
  const accept = context.request.headers.get('accept') || '';
  if (accept.includes('text/event-stream')) {
    return new Response(JSON.stringify({
      error: 'SSE 流不适用于本服务',
      detail: '本端点为无状态只读服务，无服务端主动推送。请直接用 POST 发送 JSON-RPC。',
    }), { status: 405, headers: { ...jsonHeaders, 'Allow': 'POST, OPTIONS' } });
  }

  recordMcp(context, 'discovery_get');
  // dataset 是**机读**字段，目录站与 agent 会直接采信。此前写死 total_entities: 688
  // （真值 706）—— 一个错值被官方 Registry / Glama 等抓走后还会被二次分发。
  // 现改为实时统计；取数失败时给 null + 说明，绝不回落到某个"上次记得的数字"。
  const facts = await tryFacts(context.env, context.request);
  return new Response(JSON.stringify({
    name: SERVER_NAME,
    version: SERVER_VERSION,
    transport: 'streamable-http',
    endpoint: 'https://roboparts.cc/mcp',
    protocol_versions: SUPPORTED_PROTOCOLS,
    authentication: 'none — 只读、免鉴权、不设 cookie、不存储调用方数据',
    tools: TOOLS.map(t => ({ name: t.name, description: t.description })),
    resources: RESOURCES,
    dataset: facts || {
      total_entities: null,
      categories: CATEGORIES,
      note: '本次实体统计取数失败，故不提供条数。宁可缺字段，也不返回可能已陈旧的数字。',
    },
    instructions: buildInstructions(facts),
    quickstart: {
      claude_desktop: '在 MCP 设置里添加一个 Streamable HTTP 服务器，URL 填 https://roboparts.cc/mcp，无需 API Key。',
      curl: `curl -s -X POST https://roboparts.cc/mcp -H 'Content-Type: application/json' -H 'Accept: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'`,
    },
    docs: 'https://roboparts.cc/mcp-guide',
  }, null, 2), { status: 200, headers: jsonHeaders });
}

/**
 * HEAD 探活。目录站（MCP 官方 Registry / Glama / mcp.so）、链接检查器与可用性监控
 * **默认发 HEAD**，而 Pages 不会把 HEAD 自动映射到 onRequestGet —— 缺这个导出就一律
 * 404，等于对每一个来探活的人宣告"这台 MCP 服务器已死"。/mcp 是我们唯一进了官方
 * Registry 的对外通道，这条 404 会让整条曝光链路白铺。
 *
 * 曾两次试图在 _middleware.js 集中补偿（先 next() 再 next(GET)／一次性传 GET Request），
 * 均告失败：中间件能改响应，改不了路由分发。方法级路由只能在方法级导出上解决。
 * 复用 GET 的真实状态与响应头，仅丢弃 body（HTTP 规定 HEAD 无消息体）。
 */
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}

export async function onRequestPost(context) {
  const { request } = context;

  let body;
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify(rpcError(null, -32700, 'JSON 解析失败')), {
      status: 400, headers: jsonHeaders,
    });
  }

  // 批量请求：2025-03-26 允许数组，2025-06-18 已移除。两者都接住，避免老客户端直接失败。
  const isBatch = Array.isArray(body);
  const msgs = isBatch ? body : [body];
  if (isBatch && msgs.length === 0) {
    return new Response(JSON.stringify(rpcError(null, -32600, '空批量请求')), {
      status: 400, headers: jsonHeaders,
    });
  }

  const responses = [];
  for (const m of msgs) {
    let r;
    try {
      r = await handleRpc(m, context);
    } catch (e) {
      r = rpcError(m?.id ?? null, -32603, '内部错误', String(e && e.message || e));
    }
    if (r) responses.push(r);
  }

  // 全是通知 → 202 且无 body，符合 Streamable HTTP 规范
  if (responses.length === 0) {
    return new Response(null, { status: 202, headers: corsHeaders });
  }

  const payload = isBatch ? responses : responses[0];
  return new Response(JSON.stringify(payload), { status: 200, headers: jsonHeaders });
}
