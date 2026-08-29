/**
 * RoboParts BOM 导出 API
 * POST /api/bom/export
 *
 * Body:
 * {
 *   api_key: 'gtk_xxx',                 // 必填，与积分系统一致的 API Key
 *   project_name: '人形机器人v1',          // 可选，项目名称
 *   format: 'csv' | 'json',             // 导出格式，默认 csv
 *   items: [                            // 必填，BOM 条目数组
 *     {
 *       id, name, category, manufacturer,
 *       specs, price, quantity, supplier
 *     }
 *   ],
 *   include_suppliers: true             // 可选，是否附带供应商建议
 * }
 *
 * 功能：
 * 1. CORS 支持（onRequestOptions）
 * 2. 验证 api_key（从 env.USER_CREDITS KV 查询，与现有积分系统一致）
 * 3. 支持 CSV / JSON 两种导出格式
 * 4. CSV 列：序号、模块名称、类别、品牌、规格、单价、数量、小计、供应商、3D打印建议
 * 5. JSON 含完整 BOM 结构 + 元数据（项目名、创建时间、总成本、总模块数）
 * 6. include_suppliers=true 时基于品类提供供应商建议
 * 7. 自动计算总成本（单价 × 数量）
 * 8. 每次导出消耗 1 积分
 */

const CREDIT_COST = 1;
const UPGRADE_URL = 'https://roboparts.cc/credits';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Access-Control-Expose-Headers': 'X-Credits-Remaining, X-Credits-Warning, X-Credits-Threshold, X-API-Tier',
  'Content-Type': 'application/json; charset=utf-8',
};

// 类别中文名映射（与 designer.html 保持一致并扩展）
const CATEGORY_NAMES = {
  'actuators': '执行器',
  'sensors': '传感器',
  'controllers': '控制器',
  'endeffectors': '末端执行器',
  'chips': '芯片',
  'structural': '结构件',
  'power': '电源',
  'communication': '通信',
};

// 供应商建议映射
const SUPPLIER_MAP = {
  'actuators': [
    { name: 'ROBOTIS官方', url: 'https://www.robotis.com', note: 'DYNAMIXEL系列正品' },
    { name: 'T-Motor', url: 'https://shop.tmotor.com', note: 'AK系列直驱电机' },
    { name: 'Unitree', url: 'https://www.unitree.com', note: 'B系列关节电机' },
    { name: '嘉立创FA', url: 'https://fa.jlc.com', note: '国产替代执行器' },
  ],
  'sensors': [
    { name: 'Bosch', url: 'https://www.bosch-sensortec.com', note: 'IMU/环境传感器' },
    { name: 'STMicroelectronics', url: 'https://www.st.com', note: 'IMU/ToF传感器' },
    { name: 'Ouster', url: 'https://ouster.com', note: 'LiDAR传感器' },
  ],
  'chips': [
    { name: 'NVIDIA', url: 'https://www.nvidia.com/embedded', note: 'Jetson系列' },
    { name: 'Qualcomm', url: 'https://www.qualcomm.com', note: 'RB系列机器人平台' },
    { name: '地平线', url: 'https://www.horizon.cc', note: '征程系列国产芯片' },
  ],
  'controllers': [
    { name: 'Odrive', url: 'https://odriverobotics.com', note: '电机控制器' },
    { name: 'SimpleFOC', url: 'https://simplefoc.com', note: '开源FOC驱动' },
  ],
  'default': [
    { name: '嘉立创FA', url: 'https://fa.jlc.com', note: '工业零部件一站式采购' },
    { name: '米思米', url: 'https://www.misumi.com.cn', note: '标准件快速采购' },
  ],
};

// 3D 打印建议（参考 designer.html get3DPrintAdvice）
const STRUCTURAL_KEYWORDS = ['bracket', 'joint', 'link', 'frame', 'mount', '支架', '关节', '连杆', '臂', '结构', '底座', '固定'];

function get3DPrintAdvice(category, name) {
  const lowerName = (name || '').toLowerCase();
  const isStructural = STRUCTURAL_KEYWORDS.some(k => lowerName.includes(k)) ||
    category === 'actuators' || category === 'endeffectors';
  if (isStructural) return '建议3D打印，预估成本¥30-200';
  // 传感器 / 控制器 / 其他均需外购
  return '需外购';
}

function getSupplierSuggestions(category) {
  return SUPPLIER_MAP[category] || SUPPLIER_MAP['default'];
}

function getCategoryName(category) {
  return CATEGORY_NAMES[category] || category || '未分类';
}

function csvEscape(value) {
  const str = String(value == null ? '' : value);
  if (/[",\n\r]/.test(str)) {
    return '"' + str.replace(/"/g, '""') + '"';
  }
  return str;
}

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet() {
  return new Response(JSON.stringify({
    endpoint: '/api/bom/export',
    method: 'POST',
    description: 'BOM 导出：将 BOM 条目导出为 CSV 或 JSON 格式，自动计算总成本，可选附带按品类聚合的供应商建议与 3D 打印建议。每次导出消耗 1 积分。',
    request_body: {
      api_key: 'string (必填) - API 密钥，gtk_ 前缀，可在 https://roboparts.cc 获取',
      project_name: 'string - 项目名称，可选，默认“未命名项目”',
      format: 'string - 导出格式：csv | json，默认 csv',
      items: 'array (必填) - BOM 条目数组，每项可含 id / name / category / manufacturer / specs / price / quantity / supplier',
      include_suppliers: 'boolean - 是否附带供应商建议，默认 false',
    },
    example: {
      api_key: 'gtk_demo_key',
      project_name: '人形机器人v1',
      format: 'csv',
      items: [
        {
          id: 'ACT-001',
          name: 'DYNAMIXEL XM540-W270-T',
          category: 'actuators',
          manufacturer: 'ROBOTIS',
          specs: '扭矩 10.0Nm @ 12V',
          price: 1200,
          quantity: 2,
          supplier: 'ROBOTIS官方',
        },
      ],
      include_suppliers: true,
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
    const { api_key, project_name, format, items, include_suppliers } = body;

    // 1. 验证 api_key
    if (!api_key) {
      return new Response(JSON.stringify({
        error: 'api_key is required',
        message: '请提供 api_key（gtk_ 前缀），可在 https://roboparts.cc 获取。',
      }), { status: 401, headers: corsHeaders });
    }

    // 2. 验证 format
    const fmt = (format || 'csv').toLowerCase();
    if (fmt !== 'csv' && fmt !== 'json') {
      return new Response(JSON.stringify({
        error: 'Invalid format',
        message: "format 必须为 'csv' 或 'json'",
        received: format,
      }), { status: 400, headers: corsHeaders });
    }

    // 3. 验证 items
    if (!Array.isArray(items) || items.length === 0) {
      return new Response(JSON.stringify({
        error: 'items must be a non-empty array',
        message: '请提供至少一个 BOM 条目。',
      }), { status: 400, headers: corsHeaders });
    }

    // 4. 验证积分系统
    if (!env.USER_CREDITS) {
      return new Response(JSON.stringify({
        error: 'Credits system not configured',
        message: 'USER_CREDITS KV 绑定缺失，无法完成积分扣费。',
      }), { status: 500, headers: corsHeaders });
    }

    // 5. 查询用户积分
    const userData = await env.USER_CREDITS.get(api_key);
    if (!userData) {
      return new Response(JSON.stringify({
        error: 'Invalid API key',
        message: 'api_key 未在系统中注册，请前往 https://roboparts.cc 获取有效密钥。',
      }), { status: 403, headers: corsHeaders });
    }

    const user = JSON.parse(userData);

    // 6. 积分不足
    if (user.credits < CREDIT_COST) {
      return new Response(JSON.stringify({
        error: 'Insufficient credits',
        credits_remaining: user.credits,
        required: CREDIT_COST,
        credits_needed: CREDIT_COST - user.credits,
        recharge_url: UPGRADE_URL,
        message: '积分不足，每次 BOM 导出消耗 1 积分。',
      }), {
        status: 402,
        headers: {
          ...corsHeaders,
          'X-Credits-Remaining': String(user.credits),
          'X-Upgrade-URL': UPGRADE_URL,
        },
      });
    }

    // 7. 扣除积分
    user.credits -= CREDIT_COST;
    user.api_calls = (user.api_calls || 0) + 1;

    // 低积分告警逻辑（与 [[path]].js 一致）
    const INITIAL_CREDITS = user.initial_credits || 100;
    const LOW_THRESHOLD = Math.max(20, Math.floor(INITIAL_CREDITS * 0.2));
    const responseExtraHeaders = {
      'X-API-Tier': 'credits',
      'X-Credits-Remaining': String(user.credits),
      'X-Upgrade-URL': UPGRADE_URL,
    };
    if (user.credits <= LOW_THRESHOLD) {
      responseExtraHeaders['X-Credits-Warning'] = 'low';
      responseExtraHeaders['X-Credits-Threshold'] = String(LOW_THRESHOLD);
      if (!user.low_alert_sent) {
        user.low_alert_sent = true;
        user.low_alert_at = new Date().toISOString();
      }
    }
    // 充值后重置告警状态
    if (user.credits > LOW_THRESHOLD && user.low_alert_sent) {
      user.low_alert_sent = false;
      delete user.low_alert_at;
    }

    await env.USER_CREDITS.put(api_key, JSON.stringify(user));

    // 8. 构建 BOM 数据
    const createdAt = new Date().toISOString();
    const enrichedItems = items.map((it, idx) => {
      const price = Number(it.price) || 0;
      const qty = Number(it.quantity) || 1;
      const subtotal = price * qty;
      const item = {
        index: idx + 1,
        id: it.id || '',
        name: it.name || '',
        category: it.category || '',
        category_name: getCategoryName(it.category),
        manufacturer: it.manufacturer || '',
        specs: it.specs || '',
        price: price,
        quantity: qty,
        subtotal: subtotal,
        supplier: it.supplier || '',
        print_advice: get3DPrintAdvice(it.category, it.name),
      };
      if (include_suppliers) {
        item.supplier_suggestions = getSupplierSuggestions(it.category);
      }
      return item;
    });

    const totalCost = enrichedItems.reduce((s, it) => s + it.subtotal, 0);
    const totalQuantity = enrichedItems.reduce((s, it) => s + it.quantity, 0);
    const itemCount = enrichedItems.length;

    // 9. 按格式返回
    if (fmt === 'json') {
      const result = {
        success: true,
        metadata: {
          project_name: project_name || '未命名项目',
          created_at: createdAt,
          currency: 'CNY',
          total_cost: totalCost,
          total_modules: totalQuantity,
          item_count: itemCount,
          format: 'json',
          include_suppliers: !!include_suppliers,
          credits_consumed: CREDIT_COST,
          credits_remaining: user.credits,
        },
        items: enrichedItems,
      };

      if (include_suppliers) {
        // 按品类汇总供应商建议
        const usedCategories = [...new Set(enrichedItems.map(i => i.category).filter(Boolean))];
        result.supplier_suggestions = {};
        for (const cat of usedCategories) {
          result.supplier_suggestions[cat] = {
            category_name: getCategoryName(cat),
            suppliers: getSupplierSuggestions(cat),
          };
        }
      }

      return new Response(JSON.stringify(result, null, 2), {
        status: 200,
        headers: {
          ...corsHeaders,
          'Cache-Control': 'no-store',
          ...responseExtraHeaders,
        },
      });
    }

    // CSV 格式
    const safeProject = (project_name || 'roboparts').replace(/[\\/:*?"<>|]/g, '_');
    const lines = [];

    // 元数据注释行
    lines.push('# RoboParts BOM Export');
    lines.push('# 项目名称: ' + (project_name || '未命名项目'));
    lines.push('# 导出时间: ' + createdAt);
    lines.push('# 总模块数: ' + totalQuantity + '  条目数: ' + itemCount + '  总成本(CNY): ' + totalCost);
    lines.push('# 剩余积分: ' + user.credits);

    // 表头（10 列）
    lines.push('序号,模块名称,类别,品牌,规格,单价(CNY),数量,小计(CNY),供应商,3D打印建议');

    // 数据行
    for (const it of enrichedItems) {
      let supplierCell = it.supplier;
      if (!supplierCell && include_suppliers) {
        supplierCell = getSupplierSuggestions(it.category).map(s => s.name).join('; ');
      }
      lines.push([
        it.index,
        csvEscape(it.name),
        csvEscape(it.category_name),
        csvEscape(it.manufacturer),
        csvEscape(it.specs),
        it.price,
        it.quantity,
        it.subtotal,
        csvEscape(supplierCell),
        csvEscape(it.print_advice),
      ].join(','));
    }

    // 总计行（总计标签置于序号列，数量合计置于数量列，成本合计置于小计列）
    lines.push('总计,,,,,,' + totalQuantity + ',' + totalCost + ',,');

    // 供应商建议汇总（仅 include_suppliers=true）
    if (include_suppliers) {
      lines.push('');
      lines.push('# --- 供应商建议 ---');
      const usedCategories = [...new Set(enrichedItems.map(i => i.category).filter(Boolean))];
      for (const cat of usedCategories) {
        const names = getSupplierSuggestions(cat).map(s => s.name).join('; ');
        lines.push('# ' + getCategoryName(cat) + '(' + cat + '): ' + names);
      }
    }

    const csv = '\uFEFF' + lines.join('\n') + '\n';
    const filename = 'roboparts_bom_' + safeProject + '.csv';

    return new Response(csv, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': 'attachment; filename="' + filename + '"',
        'Cache-Control': 'no-store',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Expose-Headers': 'Content-Disposition, X-Credits-Remaining, X-Credits-Warning, X-Credits-Threshold, X-API-Tier',
        ...responseExtraHeaders,
      },
    });

  } catch (e) {
    return new Response(JSON.stringify({
      error: 'Internal error',
      message: e.message,
      stack: e.stack,
    }), { status: 500, headers: corsHeaders });
  }
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
