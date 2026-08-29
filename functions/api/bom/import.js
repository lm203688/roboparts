/**
 * BOM 导入端点（P0 数据飞轮 · 人工贡献入口）
 * POST /api/bom/import
 *
 * 接收用户/开源项目提交的 BOM（零件清单 + 接口声明），做结构校验后写入待审队列
 * （KV bom:pending:*），由维护者审核后通过 scripts/build_flywheel_layer.mjs 合入
 * 静态贡献层 api/entities.contrib.json，再经引擎合并进主裁决流。
 *
 * 诚实性闸门（与飞轮纪律同源）：
 *   - 机械接口声明（mechanical_interface.standard）必须附带 source_url 方可采信，
 *     否则拒绝该条（不可核实的接口事实 = 污染），只作协议/电气层补充。
 *   - 写入走 KV 待审，不直接进裁决流，避免任意提交污染线上结论。
 *   - 自检流量（x-roboparts-selftest）只返回预览、不落盘，绝不混入真实贡献。
 */
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

const ALLOWED_CATS = new Set([
  'actuators', 'sensors', 'chips', 'protocols', 'platforms', 'llms',
  'interfaces', 'flexible_actuators', 'data_acquisition', 'robot_ai_models', 'connectors',
]);

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestHead(context) {
  return new Response(null, { status: 204, headers: corsHeaders });
}

export async function onRequestPost(context) {
  const { request, env } = context;
  let body;
  try { body = await request.json(); } catch {
    return new Response(JSON.stringify({ error: 'JSON 解析失败' }), { status: 400, headers: corsHeaders });
  }
  const comps = Array.isArray(body) ? body : (body && body.components) || [];
  if (!Array.isArray(comps) || !comps.length) {
    return new Response(JSON.stringify({ error: '缺少 components 数组或为空' }), { status: 400, headers: corsHeaders });
  }

  const preview = [];
  const valid = [];
  for (const c of comps) {
    if (!c || !c.id) { preview.push({ status: 'rejected', reason: '缺少 id' }); continue; }
    const mech = c.mechanical_interface;
    const mechSrc = c.source_url || (mech && mech.source_url);
    if (mech && mech.standard && !mechSrc) {
      preview.push({ id: c.id, status: 'rejected', reason: '机械接口声明需 source_url 方可核实（避免不可核实数据污染）' });
      continue;
    }
    const cat = ALLOWED_CATS.has(c.category) ? c.category : 'actuators';
    valid.push({ ...c, category: cat, source_url: mechSrc || null });
    preview.push({
      id: c.id,
      category: cat,
      action: c.id.startsWith('OSS-') ? 'supplement' : 'new',
      will_declare_mech: !!(mech && mech.standard),
      protocol: c.protocol || null,
      voltage: c.voltage || null,
      ros_support: typeof c.ros_support === 'boolean' ? c.ros_support : undefined,
    });
  }

  const isSelf = context.request.headers.get('x-roboparts-selftest');
  if (!isSelf && env && env.USER_CREDITS && valid.length) {
    const key = 'bom:pending:' + new Date().toISOString() + ':' + Math.random().toString(36).slice(2, 8);
    try {
      await env.USER_CREDITS.put(key, JSON.stringify({
        components: valid,
        received_at: new Date().toISOString(),
        submitter: (body && body.submitter) || 'web',
      }), { expirationTtl: 60 * 60 * 24 * 30 });
    } catch (e) {
      return new Response(JSON.stringify({ error: '待审队列写入失败', detail: String(e && e.message || e) }), { status: 503, headers: corsHeaders });
    }
  }

  return new Response(JSON.stringify({
    accepted: true,
    queued: valid.length,
    rejected: preview.filter(p => p.status === 'rejected').length,
    note: '已存入待审队列；维护者审核后通过 scripts/build_flywheel_layer.mjs 合入贡献层并部署，方进入公开裁决流。',
    preview,
  }, null, 2), { status: 200, headers: corsHeaders });
}
