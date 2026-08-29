/**
 * 供应商审核 API
 * POST /api/suppliers/approve
 *
 * 请求体：
 * {
 *   "api_key": "gtk_xxx",
 *   "supplier_id": "SUP-xxx",
 *   "action": "approve" | "reject",
 *   "reason": "审核通过"
 * }
 *
 * 功能：
 * - CORS 支持（onRequestOptions）
 * - 验证 api_key（从 USER_CREDITS KV 查询）
 * - 验证 supplier_id 存在（从 SUPPLIERS KV 查询）
 * - 更新 supplier 状态：pending → approved / rejected
 * - 记录审核时间和审核原因
 * - 返回更新后的供应商信息
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json',
};

const VALID_ACTIONS = ['approve', 'reject'];

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    const body = await request.json();

    const { api_key, supplier_id, action, reason } = body;

    // ========== 1. 参数校验 ==========
    const errors = [];

    if (!api_key || typeof api_key !== 'string' || !api_key.startsWith('gtk_')) {
      errors.push('API Key (api_key) 为必填项，且需以 gtk_ 开头');
    }

    if (!supplier_id || typeof supplier_id !== 'string' || !supplier_id.startsWith('SUP')) {
      errors.push('供应商 ID (supplier_id) 为必填项，且需以 SUP 开头');
    }

    if (!action || !VALID_ACTIONS.includes(action)) {
      errors.push('审核动作 (action) 必须为 approve 或 reject');
    }

    if (errors.length > 0) {
      return new Response(JSON.stringify({
        success: false,
        error: '参数校验失败',
        details: errors,
      }), { status: 400, headers: corsHeaders });
    }

    // ========== 2. 验证 API Key ==========
    if (!env.USER_CREDITS) {
      return new Response(JSON.stringify({
        success: false,
        error: '积分系统未配置',
      }), { status: 500, headers: corsHeaders });
    }

    const userRecord = await env.USER_CREDITS.get(api_key);
    if (!userRecord) {
      return new Response(JSON.stringify({
        success: false,
        error: 'API Key 无效或不存在',
      }), { status: 401, headers: corsHeaders });
    }

    // ========== 2.1 管理员角色校验（P0 安全修复：任何注册用户此前可审批任意供应商）============
    let parsedUser = null;
    try { parsedUser = JSON.parse(userRecord); } catch (e) {}
    const adminAllowlist = (env.ADMIN_API_KEYS || '').split(',').map(s => s.trim()).filter(Boolean);
    const isAdmin = (parsedUser && parsedUser.role === 'admin') || adminAllowlist.includes(api_key);
    if (!isAdmin) {
      return new Response(JSON.stringify({
        success: false,
        error: '权限不足：仅管理员可审核供应商',
        code: 'FORBIDDEN',
      }), { status: 403, headers: corsHeaders });
    }

    // ========== 3. 验证供应商存在 ==========
    if (!env.SUPPLIERS) {
      return new Response(JSON.stringify({
        success: false,
        error: '供应商系统未配置',
      }), { status: 500, headers: corsHeaders });
    }

    const supplierRecord = await env.SUPPLIERS.get(supplier_id);
    if (!supplierRecord) {
      return new Response(JSON.stringify({
        success: false,
        error: '供应商 ID 不存在',
        supplier_id: supplier_id,
      }), { status: 404, headers: corsHeaders });
    }

    const supplierData = JSON.parse(supplierRecord);

    // ========== 4. 状态校验 ==========
    if (supplierData.review_status !== 'pending') {
      return new Response(JSON.stringify({
        success: false,
        error: '该供应商当前状态为 ' + supplierData.review_status + '，无法再次审核',
        current_status: supplierData.review_status,
      }), { status: 409, headers: corsHeaders });
    }

    // ========== 5. 更新供应商状态 ==========
    supplierData.review_status = action;
    supplierData.review_reason = reason ? reason.trim() : '';
    supplierData.reviewed_at = new Date().toISOString();
    supplierData.updated = new Date().toISOString();

    await env.SUPPLIERS.put(supplier_id, JSON.stringify(supplierData));

    // ========== 6. 返回结果 ==========
    return new Response(JSON.stringify({
      success: true,
      supplier_id: supplier_id,
      company_name: supplierData.company_name,
      review_status: supplierData.review_status,
      review_reason: supplierData.review_reason,
      reviewed_at: supplierData.reviewed_at,
      message: action === 'approve'
        ? '供应商审核已通过'
        : '供应商审核已拒绝',
    }), { headers: corsHeaders });

  } catch (e) {
    return new Response(JSON.stringify({
      success: false,
      error: '服务器内部错误: ' + e.message,
    }), { status: 500, headers: corsHeaders });
  }
}
