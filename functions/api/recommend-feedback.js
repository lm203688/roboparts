/**
 * 站内行为回流端点（P3 · CLIFT 思想的轻量版）
 * POST /api/recommend-feedback   —— 采集（落盘）
 * GET  /api/recommend-feedback   —— 回流（只读聚合为透明社区采纳信号，不参与调权）
 * body(POST): { for_id, rec_id, action: "adopt" | "ignore", ctx?: {...} }
 *
 * 借鉴 CLIFT（Berkeley/DeepMind/NVIDIA）：部署后行为 → 训练/排序信号。
 * POST 侧只做**采集**，不做调权（冷启动阶段样本不足，任何调权都是空转——
 * 与全站"声明率 0.28% 下谈学习排序 = 自欺"同一纪律）。
 * GET 侧把已采集的分片合并为透明信号：adopt_rate ≥ 0.6 → well_adopted、
 * ≤ 0.3 → rarely_adopted、样本不足 → insufficient_data；信号仅供人工/运维复核，
 * **不自动改写推荐排序**（守假绿纪律）。
 *
 * 写入纪律（与 mcp.js 遥测同源）：isolate 内存缓冲 + 分片 flush 串行化，
 * 复用 metrics: 前缀（scripts/read_metrics.py 可直接读到），绝不按请求写 KV。
 * 自检流量（x-roboparts-selftest）只校验、不落盘。
 *
 * 数据形态（落盘后）：
 *   recfb:<date>:s<shard> = { "<rec_id>": {"adopt": n, "ignore": m}, ... , _updated }
 */
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

const SELFTEST_HEADER = 'x-roboparts-selftest';
const SHARDS = 16;
const METRIC_TTL = 60 * 60 * 24 * 90;
const MAX_WRITES_PER_ISOLATE_DAY = 200;

let _buf = Object.create(null);   // { "<rec_id>": {adopt, ignore} }
let _writes = 0;
let _writeDay = '';
let _shard = -1;
let _flushChain = Promise.resolve();

function shardOf() {
  if (_shard < 0) _shard = Math.floor(Math.random() * SHARDS);
  return _shard;
}

function scheduleFlush(context) {
  _flushChain = _flushChain.then(() => flushFeedback(context.env)).catch(() => {});
  context.waitUntil(_flushChain);
}

async function flushFeedback(env) {
  const entries = Object.entries(_buf);
  if (!entries.length) return;
  const day = new Date().toISOString().slice(0, 10);
  if (day !== _writeDay) { _writeDay = day; _writes = 0; }
  if (_writes >= MAX_WRITES_PER_ISOLATE_DAY) return;
  _buf = Object.create(null);
  const kv = env && env.USER_CREDITS;
  if (!kv) return;
  _writes++;
  const key = `recfb:${day}:s${shardOf()}`;
  let prev = {};
  try { prev = (await kv.get(key, { type: 'json' })) || {}; } catch { /* 读失败按新建 */ }
  for (const [recId, c] of entries) {
    prev[recId] = prev[recId] || { adopt: 0, ignore: 0 };
    prev[recId].adopt = (prev[recId].adopt || 0) + (c.adopt || 0);
    prev[recId].ignore = (prev[recId].ignore || 0) + (c.ignore || 0);
  }
  prev._updated = new Date().toISOString();
  await kv.put(key, JSON.stringify(prev), { expirationTtl: METRIC_TTL });
}

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

// 纯函数：把若干 recfb 分片合并为单 rec_id → {adopt, ignore} 累加。
// 不读 KV、不依赖引擎，便于单测。
export function aggregateRecfb(shards) {
  const merged = {};
  for (const shard of shards || []) {
    if (!shard || typeof shard !== 'object') continue;
    for (const [recId, c] of Object.entries(shard)) {
      if (recId === '_updated') continue;
      merged[recId] = merged[recId] || { adopt: 0, ignore: 0 };
      merged[recId].adopt += (c && c.adopt) || 0;
      merged[recId].ignore += (c && c.ignore) || 0;
    }
  }
  return merged;
}

// 回流 #2：站内行为反馈（adopt/ignore）→ 社区采纳信号（只读聚合，不调权）。
// 分片 key：recfb:<date>:s<0..15>，跨 16 分片合并；样本不足标 insufficient_data。
export async function onRequestGet(context) {
  const { env, request } = context;
  const kv = env && env.USER_CREDITS;
  if (!kv) return new Response(JSON.stringify({ error: 'KV 未绑定' }), { status: 500, headers: corsHeaders });
  const date = new URL(request.url).searchParams.get('date') || new Date().toISOString().slice(0, 10);
  const minSamples = parseInt(new URL(request.url).searchParams.get('minSamples') || '5', 10) || 5;
  const shards = [];
  for (let s = 0; s < SHARDS; s++) {
    try { const v = await kv.get(`recfb:${date}:s${s}`, { type: 'json' }); if (v) shards.push(v); } catch { /* 分片缺失跳过 */ }
  }
  const merged = aggregateRecfb(shards);
  const signals = Object.entries(merged).map(([recId, c]) => {
    const total = c.adopt + c.ignore;
    const adoptRate = total ? c.adopt / total : 0;
    const signal = total < minSamples ? 'insufficient_data'
      : (adoptRate >= 0.6 ? 'well_adopted' : adoptRate <= 0.3 ? 'rarely_adopted' : 'mixed');
    return { rec_id: recId, adopt: c.adopt, ignore: c.ignore, samples: total, adopt_rate: Math.round(adoptRate * 1000) / 1000, signal };
  }).sort((a, b) => b.samples - a.samples);
  return new Response(JSON.stringify({
    date, total_shards_read: shards.length, signals,
    note: '社区采纳信号（CLIFT 思想轻量版）：采集期回流为透明信号，样本不足标 insufficient_data，'
      + '不参与排序调权（冷启动防假绿）；adopt_rate ≥ 0.6 标 well_adopted，≤ 0.3 标 rarely_adopted。',
  }), { status: 200, headers: corsHeaders });
}

export async function onRequestPost(context) {
  const { request, env } = context;
  let body;
  try { body = await request.json(); } catch {
    return new Response(JSON.stringify({ error: 'JSON 解析失败' }), { status: 400, headers: corsHeaders });
  }
  const { for_id, rec_id, action } = body || {};
  if (!for_id || !rec_id) {
    return new Response(JSON.stringify({ error: '缺少 for_id 或 rec_id' }), { status: 400, headers: corsHeaders });
  }
  if (action !== 'adopt' && action !== 'ignore') {
    return new Response(JSON.stringify({ error: 'action 必须为 adopt 或 ignore' }), { status: 400, headers: corsHeaders });
  }

  // 自检流量不落盘：只回显会怎么记，绝不污染真实信号。
  if (request.headers.get(SELFTEST_HEADER)) {
    return new Response(JSON.stringify({ accepted: true, selftest: true, would_record: { [rec_id]: { [action]: 1 } } }),
      { status: 200, headers: corsHeaders });
  }

  _buf[rec_id] = _buf[rec_id] || { adopt: 0, ignore: 0 };
  _buf[rec_id][action] += 1;
  scheduleFlush(context);  // 隔离缓冲 + 分片串行 flush，不阻塞响应

  return new Response(JSON.stringify({
    accepted: true,
    note: '已记入行为回流缓冲（冷启动阶段仅采集，不参与排序调权）。',
    collected: { rec_id, action },
  }, null, 2), { status: 200, headers: corsHeaders });
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
