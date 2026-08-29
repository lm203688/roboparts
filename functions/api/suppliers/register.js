/**
 * 供应商入驻申请 API
 * POST /api/suppliers/register
 *
 * 请求体：
 * {
 *   "company_name": "深圳机器人配件有限公司",
 *   "contact_name": "张三",
 *   "contact_email": "zhangsan@robotparts.cn",
 *   "contact_phone": "13800138000",
 *   "company_website": "https://example.com",
 *   "product_categories": ["actuators", "sensors"],
 *   "product_count": 50,
 *   "description": "专注人形机器人关节模组...",
 *   "has_ros_support": true,
 *   "annual_revenue_range": "1000万-5000万"
 * }
 *
 * 功能：
 * - CORS 支持（onRequestOptions）
 * - 验证必填字段（company_name, contact_email, product_categories）
 * - 生成供应商 ID（SUP + 时间戳）
 * - 存储到 KV（env.SUPPLIERS，key 为 supplier_id）
 * - 返回供应商 ID 和审核状态（pending）
 * - 同时存储邮箱索引（email_supplier_ + email）用于查重
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

// 合法的品类标识（用于校验，保持与前端一致）
const VALID_CATEGORIES = [
  'actuators',      // 执行器
  'sensors',        // 传感器
  'chips',          // 芯片
  'controllers',    // 控制器
  'protocols',      // 通信协议
  'structures',     // 结构件
  '3d_printing',    // 3D 打印服务
];

// 合法的年营收范围
const VALID_REVENUE_RANGES = [
  '100万以下',
  '100-1000万',
  '1000-5000万',
  '5000万以上',
];

// 邮箱格式校验
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// URL 格式校验（可选字段，允许为空）
const URL_REGEX = /^https?:\/\/[^\s]+$/;

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet() {
  return new Response(JSON.stringify({
    endpoint: '/api/suppliers/register',
    method: 'POST',
    description: '供应商入驻申请：提交公司信息与产品品类，生成供应商 ID（SUP + 时间戳）并存入 KV，初始审核状态为 pending，同时建立邮箱查重索引（同一邮箱不可重复入驻）。',
    request_body: {
      company_name: 'string (必填) - 公司名称，不超过 100 字符',
      contact_name: 'string - 联系人姓名',
      contact_email: 'string (必填) - 联系邮箱，需符合邮箱格式',
      contact_phone: 'string - 联系电话',
      company_website: 'string - 公司网站，需以 http:// 或 https:// 开头',
      product_categories: 'string[] (必填) - 产品品类，可选值：actuators / sensors / chips / controllers / protocols / structures / 3d_printing',
      product_count: 'number - 产品数量，0-1000000',
      description: 'string - 公司描述，不超过 500 字',
      has_ros_support: 'boolean - 是否支持 ROS',
      annual_revenue_range: 'string - 年营收范围：100万以下 / 100-1000万 / 1000-5000万 / 5000万以上',
    },
    example: {
      company_name: '深圳机器人配件有限公司',
      contact_name: '张三',
      contact_email: 'zhangsan@robotparts.cn',
      contact_phone: '13800138000',
      company_website: 'https://example.com',
      product_categories: ['actuators', 'sensors'],
      product_count: 50,
      description: '专注人形机器人关节模组...',
      has_ros_support: true,
      annual_revenue_range: '1000-5000万',
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
      company_name,
      contact_name,
      contact_email,
      contact_phone,
      company_website,
      product_categories,
      product_count,
      description,
      has_ros_support,
      annual_revenue_range,
    } = body;

    // ========== 字段校验 ==========
    const errors = [];

    // 必填字段：company_name
    if (!company_name || typeof company_name !== 'string' || company_name.trim().length === 0) {
      errors.push('公司名称 (company_name) 为必填项');
    } else if (company_name.trim().length > 100) {
      errors.push('公司名称长度不能超过 100 字符');
    }

    // 必填字段：contact_email
    if (!contact_email || typeof contact_email !== 'string') {
      errors.push('联系邮箱 (contact_email) 为必填项');
    } else if (!EMAIL_REGEX.test(contact_email.trim())) {
      errors.push('联系邮箱格式不正确');
    }

    // 必填字段：product_categories（数组，至少一项）
    if (!product_categories || !Array.isArray(product_categories) || product_categories.length === 0) {
      errors.push('产品品类 (product_categories) 为必填项，且至少选择一项');
    } else {
      // 校验每个品类是否合法
      const invalidCats = product_categories.filter(c => !VALID_CATEGORIES.includes(c));
      if (invalidCats.length > 0) {
        errors.push('产品品类包含无效值: ' + invalidCats.join(', ') + '（合法值: ' + VALID_CATEGORIES.join(', ') + '）');
      }
    }

    // 选填字段校验：contact_phone
    if (contact_phone && typeof contact_phone !== 'string') {
      errors.push('联系电话格式不正确');
    }

    // 选填字段校验：company_website（URL 格式）
    if (company_website && typeof company_website === 'string' && company_website.trim().length > 0) {
      if (!URL_REGEX.test(company_website.trim())) {
        errors.push('公司网站格式不正确（需以 http:// 或 https:// 开头）');
      }
    }

    // 选填字段校验：product_count（数字）
    if (product_count !== undefined && product_count !== null && product_count !== '') {
      const pc = Number(product_count);
      if (isNaN(pc) || pc < 0 || pc > 1000000) {
        errors.push('产品数量 (product_count) 必须为 0-1000000 之间的数字');
      }
    }

    // 选填字段校验：description（最多 500 字）
    if (description && typeof description === 'string' && description.length > 500) {
      errors.push('公司描述不能超过 500 字');
    }

    // 选填字段校验：annual_revenue_range
    if (annual_revenue_range && !VALID_REVENUE_RANGES.includes(annual_revenue_range)) {
      errors.push('年营收范围无效（合法值: ' + VALID_REVENUE_RANGES.join(', ') + '）');
    }

    // 选填字段校验：has_ros_support（布尔）
    if (has_ros_support !== undefined && typeof has_ros_support !== 'boolean') {
      errors.push('ROS 支持标识 (has_ros_support) 必须为布尔值');
    }

    if (errors.length > 0) {
      return new Response(JSON.stringify({
        success: false,
        error: '参数校验失败',
        details: errors,
      }), { status: 400, headers: corsHeaders });
    }

    // ========== 邮箱查重 ==========
    const normalizedEmail = contact_email.trim().toLowerCase();
    if (env.SUPPLIERS) {
      const existingSupplierId = await env.SUPPLIERS.get('email_supplier_' + normalizedEmail);
      if (existingSupplierId) {
        return new Response(JSON.stringify({
          success: false,
          error: '该邮箱已注册供应商，请勿重复入驻',
          existing_supplier_id: existingSupplierId,
        }), { status: 409, headers: corsHeaders });
      }
    }

    // ========== 生成供应商 ID ==========
    const timestamp = Date.now();
    const randomSuffix = Math.floor(Math.random() * 10000).toString().padStart(4, '0');
    const supplierId = 'SUP' + timestamp + randomSuffix;

    // ========== 构建供应商数据 ==========
    const supplierData = {
      supplier_id: supplierId,
      company_name: company_name.trim(),
      contact_name: contact_name ? contact_name.trim() : '',
      contact_email: normalizedEmail,
      contact_phone: contact_phone ? contact_phone.trim() : '',
      company_website: company_website ? company_website.trim() : '',
      product_categories: product_categories,
      product_count: product_count !== undefined && product_count !== null && product_count !== ''
        ? Number(product_count) : 0,
      description: description ? description.trim() : '',
      has_ros_support: has_ros_support === true,
      annual_revenue_range: annual_revenue_range || '',
      review_status: 'pending', // pending / approved / rejected
      created: new Date().toISOString(),
      updated: new Date().toISOString(),
      inquiry_count: 0,
    };

    // ========== 存储 ==========
    if (env.SUPPLIERS) {
      // 主记录：key 为 supplier_id
      await env.SUPPLIERS.put(supplierId, JSON.stringify(supplierData));
      // 邮箱索引：用于查重
      await env.SUPPLIERS.put('email_supplier_' + normalizedEmail, supplierId);
    }

    // ========== 返回结果 ==========
    return new Response(JSON.stringify({
      success: true,
      supplier_id: supplierId,
      review_status: 'pending',
      message: '供应商入驻申请已提交，我们将在 1-3 个工作日内完成审核。请妥善保存您的供应商 ID，用于后续询价。',
      submitted_at: supplierData.created,
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
