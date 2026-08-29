/**
 * 站内行为回流端点（P3 · CLIFT 思想的轻量版）
 * POST /api/recommend-feedback
 * body: { for_id, rec_id, action: "adopt" | "ignore", ctx?: {...} }
 *
 * 借鉴 CLIFT（Berkeley/DeepMind/NVIDIA）：部署后行为 → 训练/排序信号。
 * 本端点只做**采集**，不做调权（冷启动阶段样本不足，任何调权都是空转——
 * 与全站"声明率 0.28% 下谈学习排序 = 自欺"同一纪律）。
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
