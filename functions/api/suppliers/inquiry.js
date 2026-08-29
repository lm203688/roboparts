/**
 * 供应商询价 API
 * POST /api/suppliers/inquiry
 *
 * 请求体：
 * {
 *   "api_key": "gtk_xxx",
 *   "supplier_id": "SUP1234567890",
 *   "component_ids": ["ACT-001", "ACT-002"],
 *   "quantity": 10,
 *   "project_name": "人形机器人v1",
 *   "message": "需要批量采购，请提供报价",
 *   "delivery_date": "2026-09-01"
 * }
 *
 * 功能：
 * - CORS 支持
 * - 验证 api_key（与现有积分系统一致，存储在 env.USER_CREDITS）
 * - 验证 supplier_id 存在（存储在 env.SUPPLIERS）
 * - 生成询价单号（INQ + 时间戳）
 * - 存储到 KV（env.SUPPLIER_INQUIRIES，key 为 inquiry_id）
 * - 同时存储到供应商的询价列表（supplier_inquiries_ + supplier_id）
 * - 消耗 1 积分
 * - 返回询价单号和状态
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

// 日期格式校验 YYYY-MM-DD
const DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet() {
  return new Response(JSON.stringify({
    endpoint: '/api/suppliers/inquiry',
    method: 'POST',
    description: '供应商询价：向指定已注册供应商发起询价单，生成询价单号（INQ + 时间戳）并存入 KV，同时更新供应商询价计数。每次询价消耗 1 积分。',
    request_body: {
      api_key: 'string (必填) - API 密钥，需以 gtk_ 开头',
      supplier_id: 'string (必填) - 供应商 ID，需以 SUP 开头',
      component_ids: 'string[] - 零部件 ID 列表，可选',
      quantity: 'number - 采购数量，1-1000000 之间的正整数',
      project_name: 'string - 项目名称，不超过 100 字',
      message: 'string - 询价留言，不超过 1000 字',
      delivery_date: 'string - 期望交付日期，格式 YYYY-MM-DD',
    },
    example: {
      api_key: 'gtk_demo_key',
      supplier_id: 'SUP1234567890',
      component_ids: ['ACT-001', 'ACT-002'],
      quantity: 10,
      project_name: '人形机器人v1',
      message: '需要批量采购，请提供报价',
      delivery_date: '2026-09-01',
    },
    note: '此端点仅支持 POST 请求，请使用 curl 或 fetch 发送 POST 请求',
  }, null, 2), {
    status: 200,
    headers: { ...corsHeaders, 'Cache-Control': 'public, max-age=3600' },
  });
}

export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    const body = await request.json();

    const {
      api_key,
      supplier_id,
      component_ids,
      quantity,
      project_name,
      message,
      delivery_date,
    } = body;

    // ========== 1. 参数校验 ==========
    const errors = [];

    // api_key 必填
    if (!api_key || typeof api_key !== 'string' || !api_key.startsWith('gtk_')) {
      errors.push('API Key (api_key) 为必填项，且需以 gtk_ 开头');
    }

    // supplier_id 必填
    if (!supplier_id || typeof supplier_id !== 'string' || !supplier_id.startsWith('SUP')) {
      errors.push('供应商 ID (supplier_id) 为必填项，且需以 SUP 开头');
    }

    // component_ids 选填但若有需为数组
    if (component_ids !== undefined && component_ids !== null) {
      if (!Array.isArray(component_ids)) {
        errors.push('零部件 ID 列表 (component_ids) 必须为数组');
      }
    }

    // quantity 选填但若有需为正整数
    if (quantity !== undefined && quantity !== null && quantity !== '') {
      const q = Number(quantity);
      if (isNaN(q) || q <= 0 || q > 1000000 || !Number.isInteger(q)) {
        errors.push('采购数量 (quantity) 必须为 1-1000000 之间的正整数');
      }
    }

    // delivery_date 选填但若有需为 YYYY-MM-DD
    if (delivery_date && typeof delivery_date === 'string' && delivery_date.trim().length > 0) {
      if (!DATE_REGEX.test(delivery_date.trim())) {
        errors.push('期望交付日期 (delivery_date) 格式应为 YYYY-MM-DD');
      }
    }

    // message 长度限制
    if (message && typeof message === 'string' && message.length > 1000) {
      errors.push('询价留言 (message) 长度不能超过 1000 字');
    }

    // project_name 长度限制
    if (project_name && typeof project_name === 'string' && project_name.length > 100) {
      errors.push('项目名称 (project_name) 长度不能超过 100 字');
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

    const userData = JSON.parse(userRecord);
    const currentCredits = userData.credits || 0;

    // 检查积分是否足够
    if (currentCredits < 1) {
      return new Response(JSON.stringify({
        success: false,
        error: '积分不足，每次询价需消耗 1 积分',
        current_credits: currentCredits,
        required_credits: 1,
        recharge_url: 'https://roboparts.cc/credits',
      }), { status: 402, headers: corsHeaders });
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

    // 校验供应商审核状态（仅 approved 状态可询价，但为兼容老数据，pending 也允许）
    if (supplierData.review_status === 'rejected') {
      return new Response(JSON.stringify({
        success: false,
        error: '该供应商审核未通过，暂无法询价',
        supplier_id: supplier_id,
      }), { status: 403, headers: corsHeaders });
    }

    // ========== 4. 扣减积分 ==========
    userData.credits = currentCredits - 1;
    userData.api_calls = (userData.api_calls || 0) + 1;
    await env.USER_CREDITS.put(api_key, JSON.stringify(userData));

    // ========== 5. 生成询价单号 ==========
    const timestamp = Date.now();
    const randomSuffix = Math.floor(Math.random() * 10000).toString().padStart(4, '0');
    const inquiryId = 'INQ' + timestamp + randomSuffix;

    // ========== 6. 构建询价数据 ==========
    const inquiryData = {
      inquiry_id: inquiryId,
      api_key: api_key,
      user_email: userData.email || '',
      supplier_id: supplier_id,
      supplier_name: supplierData.company_name || '',
      component_ids: Array.isArray(component_ids) ? component_ids : [],
      quantity: quantity !== undefined && quantity !== null && quantity !== ''
        ? Number(quantity) : 1,
      project_name: project_name ? project_name.trim() : '',
      message: message ? message.trim() : '',
      delivery_date: delivery_date ? delivery_date.trim() : '',
      status: 'pending', // pending / quoted / accepted / rejected / closed
      created: new Date().toISOString(),
      updated: new Date().toISOString(),
    };

    // ========== 7. 存储询价记录 ==========
    if (env.SUPPLIER_INQUIRIES) {
      // 主记录：key 为 inquiry_id
      await env.SUPPLIER_INQUIRIES.put(inquiryId, JSON.stringify(inquiryData));

      // 供应商的询价列表索引：value 为逗号分隔的 inquiry_id 列表
      // 为避免单 key 过大，采用追加方式（实际生产可考虑分页或列表 KV）
      const listKey = 'supplier_inquiries_' + supplier_id;
      const existingList = await env.SUPPLIER_INQUIRIES.get(listKey);
      const newList = existingList
        ? existingList + ',' + inquiryId
        : inquiryId;
      await env.SUPPLIER_INQUIRIES.put(listKey, newList);

      // 用户询价列表索引（方便用户查询自己发起的询价）
      const userListKey = 'user_inquiries_' + api_key;
      const existingUserList = await env.SUPPLIER_INQUIRIES.get(userListKey);
      const newUserList = existingUserList
        ? existingUserList + ',' + inquiryId
        : inquiryId;
      await env.SUPPLIER_INQUIRIES.put(userListKey, newUserList);
    }

    // ========== 8. 更新供应商的询价计数 ==========
    if (env.SUPPLIERS) {
      supplierData.inquiry_count = (supplierData.inquiry_count || 0) + 1;
      supplierData.updated = new Date().toISOString();
      await env.SUPPLIERS.put(supplier_id, JSON.stringify(supplierData));
    }

    // ========== 9. 返回结果 ==========
    return new Response(JSON.stringify({
      success: true,
      inquiry_id: inquiryId,
      status: 'pending',
      supplier_id: supplier_id,
      supplier_name: supplierData.company_name || '',
      message: '询价单已提交，供应商将在 1-3 个工作日内回复报价。',
      credits_consumed: 1,
      credits_remaining: userData.credits,
      submitted_at: inquiryData.created,
    }), { status: 201, headers: corsHeaders });

  } catch (e) {
    return new Response(JSON.stringify({
      success: false,
      error: '服务器内部错误: ' + e.message,
    }), { status: 500, headers: corsHeaders });
  }
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
