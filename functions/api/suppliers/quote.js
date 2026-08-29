/**
 * 供应商报价响应 API
 * POST /api/suppliers/quote
 *
 * 请求体：
 * {
 *   "api_key": "gtk_xxx",
 *   "inquiry_id": "INQ-xxx",
 *   "supplier_id": "SUP-xxx",
 *   "price": 1500,
 *   "moq": 100,
 *   "delivery_days": 7,
 *   "notes": "批量优惠"
 * }
 *
 * 功能：
 * - CORS 支持
 * - 验证 api_key
 * - 更新 SUPPLIER_INQUIRIES KV 中对应询价的状态和报价信息
 * - 添加状态字段：status=pending→quoted，quote_price，quote_moq，quote_delivery_days，quote_notes，quoted_at
 * - 返回更新后的询价详情
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    const body = await request.json();

    const { api_key, inquiry_id, supplier_id, price, moq, delivery_days, notes } = body;

    // ========== 1. 参数校验 ==========
    const errors = [];

    if (!api_key || typeof api_key !== 'string' || !api_key.startsWith('gtk_')) {
      errors.push('API Key (api_key) 为必填项，且需以 gtk_ 开头');
    }

    if (!inquiry_id || typeof inquiry_id !== 'string' || !inquiry_id.startsWith('INQ')) {
      errors.push('询价单号 (inquiry_id) 为必填项，且需以 INQ 开头');
    }

    if (!supplier_id || typeof supplier_id !== 'string' || !supplier_id.startsWith('SUP')) {
      errors.push('供应商 ID (supplier_id) 为必填项，且需以 SUP 开头');
    }

    // price 必填且为正数
    if (price === undefined || price === null || typeof price !== 'number' || price <= 0) {
      errors.push('报价价格 (price) 为必填项，且必须为正数');
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

    // ========== 2.1 管理员角色校验（P0 安全修复：任何注册用户此前可对任意询价单报价）============
    let parsedUser = null;
    try { parsedUser = JSON.parse(userRecord); } catch (e) {}
    const adminAllowlist = (env.ADMIN_API_KEYS || '').split(',').map(s => s.trim()).filter(Boolean);
    const isAdmin = (parsedUser && parsedUser.role === 'admin') || adminAllowlist.includes(api_key);
    if (!isAdmin) {
      return new Response(JSON.stringify({
        success: false,
        error: '权限不足：仅管理员可提交供应商报价',
        code: 'FORBIDDEN',
      }), { status: 403, headers: corsHeaders });
    }

    // ========== 3. 验证询价单存在 ==========
    if (!env.SUPPLIER_INQUIRIES) {
      return new Response(JSON.stringify({
        success: false,
        error: '询价系统未配置',
      }), { status: 500, headers: corsHeaders });
    }

    const inquiryRecord = await env.SUPPLIER_INQUIRIES.get(inquiry_id);
    if (!inquiryRecord) {
      return new Response(JSON.stringify({
        success: false,
        error: '询价单不存在',
        inquiry_id: inquiry_id,
      }), { status: 404, headers: corsHeaders });
    }

    const inquiryData = JSON.parse(inquiryRecord);

    // ========== 4. 状态校验 ==========
    if (inquiryData.status !== 'pending') {
      return new Response(JSON.stringify({
        success: false,
        error: '该询价单当前状态为 ' + inquiryData.status + '，无法再次报价',
        current_status: inquiryData.status,
      }), { status: 409, headers: corsHeaders });
    }

    // ========== 5. 验证供应商匹配 ==========
    if (inquiryData.supplier_id !== supplier_id) {
      return new Response(JSON.stringify({
        success: false,
        error: '该询价单不属于此供应商',
        inquiry_supplier_id: inquiryData.supplier_id,
      }), { status: 403, headers: corsHeaders });
    }

    // ========== 6. 更新询价记录 ==========
    inquiryData.status = 'quoted';
    inquiryData.quote_price = Number(price);
    inquiryData.quote_moq = (moq !== undefined && moq !== null) ? Number(moq) : 1;
    inquiryData.quote_delivery_days = (delivery_days !== undefined && delivery_days !== null) ? Number(delivery_days) : 7;
    inquiryData.quote_notes = notes ? notes.trim() : '';
    inquiryData.quoted_at = new Date().toISOString();
    inquiryData.updated = new Date().toISOString();

    await env.SUPPLIER_INQUIRIES.put(inquiry_id, JSON.stringify(inquiryData));

    // ========== 7. 返回结果 ==========
    return new Response(JSON.stringify({
      success: true,
      inquiry_id: inquiryData.inquiry_id,
      supplier_id: inquiryData.supplier_id,
      supplier_name: inquiryData.supplier_name,
      status: inquiryData.status,
      quote_price: inquiryData.quote_price,
      quote_moq: inquiryData.quote_moq,
      quote_delivery_days: inquiryData.quote_delivery_days,
      quote_notes: inquiryData.quote_notes,
      quoted_at: inquiryData.quoted_at,
      message: '报价已提交，采购方将收到报价通知。',
    }), { headers: corsHeaders });

  } catch (e) {
    return new Response(JSON.stringify({
      success: false,
      error: '服务器内部错误: ' + e.message,
    }), { status: 500, headers: corsHeaders });
  }
}
