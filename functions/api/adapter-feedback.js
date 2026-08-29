/**
 * 数字-物理反馈闭环（安装回填）
 * POST /api/adapter-feedback
 *
 * 用户下载 STL → 打印 → 安装后，回填「合适 / 不合适 / 需调整」，数据回流用于校准
 * 兼容性置信度与转接件生成参数。
 *
 * 存储：复用既有 KV 命名空间 SUPPLIER_INQUIRIES（MVP 阶段避免新开 KV；
 * 正式版应拆分为独立 ADAPTER_FEEDBACK 命名空间）。
 * 键：adapter_feedback:<uuid> 存明细；adapter_feedback:index 存 ID 列表。
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestPost(context) {
  const { request, env } = context;
  let body;
  try {
    body = await request.json();
  } catch (e) {
    return new Response(JSON.stringify({ error: '请求体不是合法 JSON' }), { status: 400, headers: corsHeaders });
  }

  const flangeA = String(body.flangeA || '').slice(0, 80);
  const flangeB = String(body.flangeB || '').slice(0, 80);
  const fit = String(body.fit || '').toLowerCase();
  const note = String(body.note || '').slice(0, 500);
  if (!['ok', 'bad', 'adjust'].includes(fit)) {
    return new Response(JSON.stringify({ error: 'fit 必须是 ok / bad / adjust 之一' }), { status: 400, headers: corsHeaders });
  }

  const id = 'adapter_feedback:' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  const record = {
    id,
    flangeA,
    flangeB,
    fit,
    note,
    ts: new Date().toISOString(),
    ua: request.headers.get('user-agent') || '',
  };

  try {
    const kv = env.SUPPLIER_INQUIRIES;
    if (!kv) throw new Error('KV 未绑定（SUPPLIER_INQUIRIES）');
    await kv.put(id, JSON.stringify(record));
    // 维护索引（追加 ID，保留最近 200 条）
    let index = [];
    const raw = await kv.get('adapter_feedback:index');
    if (raw) { try { index = JSON.parse(raw); } catch { index = []; } }
    index.unshift(id);
    index = index.slice(0, 200);
    await kv.put('adapter_feedback:index', JSON.stringify(index));
    return new Response(JSON.stringify({ ok: true, id, msg: '已记录，感谢回填！数据将用于校准转接件参数。' }), { status: 200, headers: corsHeaders });
  } catch (e) {
    return new Response(JSON.stringify({ error: '存储失败: ' + e.message }), { status: 500, headers: corsHeaders });
  }
}

// 供内部/运维查看最近反馈（只读）
export async function onRequestGet(context) {
  const { env } = context;
  try {
    const kv = env.SUPPLIER_INQUIRIES;
    if (!kv) return new Response(JSON.stringify({ error: 'KV 未绑定' }), { status: 500, headers: corsHeaders });
    const raw = await kv.get('adapter_feedback:index');
    const index = raw ? JSON.parse(raw) : [];
    const items = [];
    for (const key of index.slice(0, 50)) {
      const r = await kv.get(key);
      if (r) items.push(JSON.parse(r));
    }
    const stats = items.reduce((a, x) => { a[x.fit] = (a[x.fit] || 0) + 1; return a; }, {});
    return new Response(JSON.stringify({ total: index.length, stats, recent: items }), { status: 200, headers: corsHeaders });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: corsHeaders });
  }
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
