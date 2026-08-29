/**
 * 供应商列表 API
 * GET /api/suppliers/list
 *
 * Query 参数：
 * - category: 按品类筛选（如 actuators、sensors）
 * - page: 页码（默认 1）
 * - limit: 每页数量（默认 20，最大 100）
 *
 * 功能：
 * - CORS 支持
 * - 从 KV 读取所有供应商（遍历 SUP 前缀的 key）
 * - 返回供应商公开信息（不含联系方式，需登录后查看）
 * - 免费访问，不需要 api_key
 * - 支持按品类筛选和分页
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json',
  'Cache-Control': 'no-store',
};

// 合法的品类列表（用于参数校验提示）
const VALID_CATEGORIES = [
  'actuators',
  'sensors',
  'chips',
  'controllers',
  'protocols',
  'structures',
  '3d_printing',
];

// 品类中文映射（便于前端展示）
const CATEGORY_LABELS = {
  actuators: '执行器',
  sensors: '传感器',
  chips: '芯片',
  controllers: '控制器',
  protocols: '通信协议',
  structures: '结构件',
  '3d_printing': '3D打印服务',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet(context) {
  const { request, env } = context;

  try {
    const url = new URL(request.url);
    const category = url.searchParams.get('category') || '';
    const page = Math.max(1, parseInt(url.searchParams.get('page') || '1', 10) || 1);
    const limit = Math.min(100, Math.max(1, parseInt(url.searchParams.get('limit') || '20', 10) || 20));

    // 校验 category 参数
    if (category && !VALID_CATEGORIES.includes(category)) {
      return new Response(JSON.stringify({
        success: false,
        error: '无效的品类参数',
        valid_categories: VALID_CATEGORIES.map(c => ({ id: c, label: CATEGORY_LABELS[c] })),
      }), { status: 400, headers: corsHeaders });
    }

    // ========== 读取所有供应商 ==========
    if (!env.SUPPLIERS) {
      return new Response(JSON.stringify({
        success: true,
        suppliers: [],
        total: 0,
        page: page,
        limit: limit,
        total_pages: 0,
        message: '供应商系统尚未配置',
      }), { headers: corsHeaders });
    }

    // 遍历 KV 中所有 SUP 前缀的 key
    // 注意：Cloudflare KV 的 list() 默认返回 1000 条，需要循环处理 cursor
    const allSuppliers = [];
    let cursor = undefined;
    let listComplete = false;

    while (!listComplete) {
      const listOptions = { prefix: 'SUP', limit: 1000 };
      if (cursor) {
        listOptions.cursor = cursor;
      }

      const listResult = await env.SUPPLIERS.list(listOptions);

      // 并行读取每个 key 的值
      if (listResult.keys && listResult.keys.length > 0) {
        const values = await Promise.all(
          listResult.keys.map(k => env.SUPPLIERS.get(k.name))
        );

        for (let i = 0; i < values.length; i++) {
          if (values[i]) {
            try {
              const supplier = JSON.parse(values[i]);
              // 【20260807-03 安全修复】原口径为 `review_status !== 'rejected'`，
              // 即「待审核(pending)也公开」。这让审核形同虚设：
              //   POST /api/suppliers/register（无鉴权/无限流/无验证码）→ 落库即 pending
              //   → GET /api/suppliers/list（无鉴权 + CORS *）立刻公开
              // 实测已复现：一次匿名 POST 后条目数秒内出现在公开目录中。
              // 即任何人可凭一个未鉴权请求，把任意公司注入 RoboParts 公开供应商目录；
              // 而该目录正被 GPTBot / Meta-ExternalAgent / Googlebot 抓取，会被吸收进
              // AI 对「RoboParts 供应商网络」的回答 —— 直接侵蚀平台可信度。
              // 污染已实际发生：公开目录中存在测试数据 "Test Company"（0 个产品）。
              // 改为白名单口径：**只有 approved 才公开**，使 approve.js 的管理员闸门
              // 真正成为发布前置条件。pending 仍留在 KV 等待审核，只是不对外可见。
              if (supplier.review_status === 'approved') {
                allSuppliers.push(supplier);
              }
            } catch (e) {
              // 跳过解析失败的记录
            }
          }
        }
      }

      listComplete = listResult.list_complete;
      cursor = listResult.cursor;
    }

    // ========== 按品类筛选 ==========
    let filteredSuppliers = allSuppliers;
    if (category) {
      filteredSuppliers = allSuppliers.filter(s => {
        return Array.isArray(s.product_categories) && s.product_categories.includes(category);
      });
    }

    // ========== 排序（按创建时间倒序，最新的在前） ==========
    filteredSuppliers.sort((a, b) => {
      const timeA = new Date(a.created || 0).getTime();
      const timeB = new Date(b.created || 0).getTime();
      return timeB - timeA;
    });

    // ========== 分页 ==========
    const total = filteredSuppliers.length;
    const totalPages = Math.ceil(total / limit) || 1;
    const startIndex = (page - 1) * limit;
    const pagedSuppliers = filteredSuppliers.slice(startIndex, startIndex + limit);

    // ========== 构造公开信息（脱敏：移除联系方式） ==========
    const publicSuppliers = pagedSuppliers.map(s => {
      return {
        supplier_id: s.supplier_id,
        company_name: s.company_name,
        product_categories: s.product_categories || [],
        product_count: s.product_count || 0,
        description: s.description || '',
        has_ros_support: s.has_ros_support === true,
        annual_revenue_range: s.annual_revenue_range || '',
        review_status: s.review_status || 'pending',
        inquiry_count: s.inquiry_count || 0,
        created: s.created || '',
        // 联系方式脱敏：仅返回是否有联系方式，不返回具体值
        has_contact: !!(s.contact_name || s.contact_email || s.contact_phone),
        has_website: !!(s.company_website),
        // 网站可公开（用于用户访问供应商官网）
        company_website: s.company_website || '',
      };
    });

    // ========== 返回结果 ==========
    return new Response(JSON.stringify({
      success: true,
      suppliers: publicSuppliers,
      total: total,
      page: page,
      limit: limit,
      total_pages: totalPages,
      category_filter: category || null,
      category_label: category ? CATEGORY_LABELS[category] : null,
      available_categories: VALID_CATEGORIES.map(c => ({ id: c, label: CATEGORY_LABELS[c] })),
    }), { headers: corsHeaders });

  } catch (e) {
    return new Response(JSON.stringify({
      success: false,
      error: '服务器内部错误: ' + e.message,
    }), { status: 500, headers: corsHeaders });
  }
}

export async function onRequestPost(context) {
  // POST supports body-based filters in addition to query params
  return onRequestGet(context);
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
