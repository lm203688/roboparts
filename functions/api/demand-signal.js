/**
 * 真实需求信号端点 — 自动化运营补强（H2/L4/L6 回流）
 * GET /api/demand-signal
 *
 * 读取部署产物 api/demand-signal.json（由 scripts/demand_scan.mjs 现算、
 * 经 deploy.mjs 0b3 段从 ops/ 刷新而来）。该文件是「真实社区兼容性提问」的
 * 机器可读度量，等价于把 scoreboard.html 里原本手工维护的「外部信号」单元格
 * 改成自动回流 —— 监听器产物不再需人工填表。
 *
 * 本端点只读、不触发任何外部请求；信号采集的活全在 demand_scan.mjs 里（带通道
 * 存活探测，绝不把「不可达」当「零需求」）。发帖响应层保持人工闸门，永不自动化。
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

async function readSignal(env) {
  // 部署产物落 api/ 目录，经 ASSETS 读取（与 loadEntityMap 同源）
  const r = await env.ASSETS.fetch(new URL('/api/demand-signal.json', 'http://localhost'));
  if (!r.ok) {
    const e = new Error(`signal file HTTP ${r.status}`);
    e.status = r.status;
    throw e;
  }
  return r.json();
}

export async function onRequestGet(context) {
  const { env } = context;
  try {
    const data = await readSignal(env);
    return new Response(JSON.stringify({ success: true, ...data }, null, 2), {
      status: 200,
      headers: corsHeaders,
    });
  } catch (e) {
    // 数据源缺文件 = 诚实 404；不是 500 也不是空对象伪绿
    const status = e.status === 404 ? 404 : 503;
    return new Response(JSON.stringify({
      error: status === 404 ? '信号文件尚未生成（请先运行 demand_scan）' : '数据源不可用',
      detail: String(e && e.message || e),
    }), { status, headers: corsHeaders });
  }
}

export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
