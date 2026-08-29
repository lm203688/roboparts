/**
 * 运营度量端点 — B3 度量断点修复
 * GET /api/stats
 *
 * 返回累计运营计数（来自 USER_CREDITS KV 中以 stat: 为前缀的键）。
 * 无需鉴权，纯公开统计；失败时返回 available:false 而不报错。
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

export async function onRequestGet(context) {
  const { env } = context;
  const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
  const keys = [
    'stat:users:total',
    'stat:api_calls:total',
    'stat:api_calls:' + today,
    'stat:selection_calls:total',
    'stat:credits_consumed:total',
  ];

  if (!env.USER_CREDITS) {
    return new Response(JSON.stringify({
      available: false,
      error: '度量 KV 未配置',
    }), { status: 200, headers: corsHeaders });
  }

  const out = { available: true, updated_at: new Date().toISOString() };
  try {
    await Promise.all(keys.map(async k => {
      const v = await env.USER_CREDITS.get(k);
      out[k.replace('stat:', '')] = v ? parseInt(v, 10) : 0;
    }));
  } catch (e) {
    out.available = false;
    out.error = e.message;
  }

  return new Response(JSON.stringify(out, null, 2), { status: 200, headers: corsHeaders });
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
