/**
 * RoboParts 国产化率分析 API
 * POST /api/localization/analyze
 *
 * Body:
 * {
 *   api_key: 'gtk_xxx',
 *   items: [
 *     { id: 'ACT-001', manufacturer: 'ROBOTIS', price: 1200, quantity: 2 },
 *     { id: 'CHIP-099', manufacturer: 'Rockchip (瑞芯微)', price: 100, quantity: 1 }
 *   ]
 * }
 *
 * 功能：
 * 1. CORS 支持（onRequestOptions）
 * 2. 验证 api_key（消耗 1 积分）
 * 3. 根据 manufacturer 判断国产/进口
 * 4. 按数量×价格加权计算国产化率
 * 5. 返回详细分析报告（按品类、按供应商、替代建议）
 */

const CREDIT_COST = 1;
const UPGRADE_URL = 'https://roboparts.cc/credits';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS, GET',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Access-Control-Expose-Headers': 'X-Credits-Remaining, X-Credits-Warning, X-Credits-Threshold, X-API-Tier',
  'Content-Type': 'application/json; charset=utf-8',
};

// 国产制造商关键词匹配表
const DOMESTIC_KEYWORDS = [
  '瑞芯微', 'Rockchip', '地平线', 'Horizon', '寒武纪', 'Cambricon',
  '华为', 'Huawei', '昇腾', 'Ascend',
  '蓝点触控', 'LinkTouch', '宇立', 'Sunrise', 'SRI',
  '鑫精诚', '昊志', '柯力', '坤维',
  '汉威', '能斯达', '帕西尼', 'PaXini', '他山',
  '戴盟', 'Daimon', '纬钛',
  '途见', 'TachinTech',
  '宇树', 'Unitree',
  '智元', 'Zhiyuan',
  '优必选', 'UBTECH',
  '傅利叶', 'Fourier',
  '小鹏', 'XPeng',
  '大象机器人', 'Elephant Robotics',
  '睿尔曼', 'Realman',
  '大然', 'DARAN',
  '星动纪元', 'RobotEra',
  '逐际动力', 'LimX',
  '银河通用', 'Galbot',
  '有鹿', 'LU Robotics',
  '嘉立创', '米思米', 'Misumi',
  'NOKOV', '度量',
  '天工', 'TienKung',
  '国家地方共建',
  'Agibot', ' FlexiPick',
];

// 进口制造商关键词（用于高精度判断）
const IMPORT_KEYWORDS = [
  'NVIDIA', 'Intel', 'Qualcomm', 'AMD',
  'ATI', 'Novanta', 'OnRobot', 'Bota',
  'GelSight', 'MIT', 'Meta', 'SynTouch',
  'Tekscan', 'PPS', 'Pressure Profile',
  'Boston Dynamics', 'Figure AI', 'Sanctuary',
  'ANYbotics', 'PAL Robotics', 'Pollen',
  'FANUC', 'KUKA', 'ABB', 'Doosan', 'Mujin',
  'Universal Robots', 'Robotiq', 'Franka',
  'Kinova', 'UR5e',
  'Google', 'Hailo', 'Kinara', 'NXP',
  'OptiTrack', 'NaturalPoint', 'Vicon',
  'Motion Analysis', 'Xsens', 'Movella',
  'ROBOTIS', 'Bosch', 'STMicroelectronics',
  'Velodyne', 'Ouster', 'Luminar', 'Hesai',
  'Prophesee', 'iniVation',
  'Odrive', 'T-Motor',
  'Shadow', 'Daimon Robotics',
  'AgileX',
  'Willow Garage', 'Open Robotics',
];

// 国产替代建议映射
const DOMESTIC_ALTERNATIVES = {
  'NVIDIA': { alt: '地平线征程J6M / 华为昇腾310B', note: '算力相当，功能安全认证更优' },
  'ATI': { alt: '蓝点触控六维力 / 宇立仪器M4313', note: '精度0.1%FS，价格降低50%+' },
  'OnRobot': { alt: '坤维科技 / 鑫精诚', note: '协作臂末端力控，国产性价比高' },
  'Bota Systems': { alt: '蓝点触控 Mini系列', note: '数字式即插即用，ROS友好' },
  'GelSight': { alt: '戴盟DM-Tac W2 / 纬钛GelFinger', note: '40000单元/cm²，IP65防护' },
  'SynTouch': { alt: '帕西尼PX-6AX', note: 'ITPU多维触觉，全栈方案' },
  'Tekscan': { alt: '汉威/能斯达 柔性阵列', note: '石墨烯压阻，厚度≤0.3mm' },
  'PPS': { alt: '汉威/能斯达 柔性阵列', note: '电容式替代方案' },
  'Google': { alt: '瑞芯微RK3588', note: '6 TOPS NPU，成本低90%' },
  'Hailo': { alt: '寒武纪MLU220 / 瑞芯微RK3588', note: '边缘AI加速，国产供应链' },
  'ROBOTIS': { alt: '大象机器人 / 睿尔曼', note: '国产协作臂，价格降低60%+' },
  'FANUC': { alt: '大然DR-07 / 睿尔曼RM65-B', note: '国产协作机械臂' },
  'KUKA': { alt: '大然DR-07 / 睿尔曼RM65-B', note: '国产协作机械臂' },
  'ABB': { alt: '大然DR-07 / 睿尔曼RM65-B', note: '国产协作机械臂' },
  'Universal Robots': { alt: '大象机器人myCobot / 睿尔曼RM65-B', note: '国产协作机械臂' },
  'Franka': { alt: '大象机器人myCobot 280', note: '教育科研首选国产' },
  'OptiTrack': { alt: 'NOKOV度量', note: '国产光学动捕，自主可控' },
  'Vicon': { alt: 'NOKOV度量', note: '国产替代，价格降低50%+' },
};

function isDomestic(manufacturer) {
  if (!manufacturer) return false;
  const name = String(manufacturer);
  // 优先匹配国产关键词
  if (DOMESTIC_KEYWORDS.some(k => name.includes(k))) return true;
  // 再检查是否匹配进口关键词
  if (IMPORT_KEYWORDS.some(k => name.includes(k))) return false;
  // 默认未知 → 标记为进口（保守估计）
  return false;
}

function getCountry(manufacturer) {
  if (!manufacturer) return 'Unknown';
  const name = String(manufacturer);
  if (DOMESTIC_KEYWORDS.some(k => name.includes(k))) return 'China';
  if (IMPORT_KEYWORDS.some(k => name.includes(k))) {
    if (name.match(/NVIDIA|Intel|Google|Meta|Boston Dynamics|Figure|Sanctuary|1X|Agility|ATI|OnRobot|Tekscan|PPS|GelSight|SynTouch|OptiTrack|Vicon|Motion Analysis|Xsens|Movella|Franka|Kinova|Universal Robots|Robotiq|Hailo|Kinara|NXP|Bota/i)) return 'USA/Israel/Europe';
    if (name.match(/ROBOTIS|Doosan/i)) return 'Korea';
    if (name.match(/FANUC|KUKA|ABB|Mujin/i)) return 'Japan/Germany/Switzerland';
    if (name.match(/Bosch|STMicroelectronics/i)) return 'Germany/France';
    if (name.match(/Qualcomm/i)) return 'USA';
  }
  return 'Unknown';
}

function getDomesticAlternative(manufacturer) {
  if (!manufacturer) return null;
  for (const [key, val] of Object.entries(DOMESTIC_ALTERNATIVES)) {
    if (String(manufacturer).includes(key)) return val;
  }
  return null;
}

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet() {
  return new Response(JSON.stringify({
    endpoint: '/api/localization/analyze',
    method: 'POST',
    description: '国产化率分析：根据BOM条目的制造商来源计算国产化率，提供按品类/价格加权的详细分析报告及国产替代建议。每次分析消耗1积分。',
    request_body: {
      api_key: 'string (必填) - API密钥，gtk_前缀',
      items: 'array (必填) - BOM条目数组，每项含 id / manufacturer / price / quantity / category',
    },
    response_fields: {
      overall_rate: '总体国产化率(%)',
      by_value: '按价值加权国产化率(%)',
      by_count: '按数量加权国产化率(%)',
      domestic_items: '国产件列表',
      imported_items: '进口件列表',
      alternatives: '国产替代建议',
      summary: '分析总结',
    },
    note: '此端点仅支持POST请求，请使用curl或fetch发送POST请求',
  }, null, 2), {
    status: 200,
    headers: { ...corsHeaders, 'Cache-Control': 'public, max-age=3600' },
  });
}

export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    const body = await request.json();
    const { api_key, items } = body;

    // 1. 验证 api_key
    if (!api_key) {
      return new Response(JSON.stringify({
        error: 'api_key is required',
        message: '请提供 api_key（gtk_ 前缀），可在 https://roboparts.cc 获取。',
      }), { status: 401, headers: corsHeaders });
    }

    // 2. 验证 items
    if (!Array.isArray(items) || items.length === 0) {
      return new Response(JSON.stringify({
        error: 'items must be a non-empty array',
        message: '请提供至少一个 BOM 条目。',
      }), { status: 400, headers: corsHeaders });
    }

    // 3. 验证积分
    if (!env.USER_CREDITS) {
      return new Response(JSON.stringify({
        error: 'Credits system not configured',
        message: 'USER_CREDITS KV 绑定缺失。',
      }), { status: 500, headers: corsHeaders });
    }

    const userData = await env.USER_CREDITS.get(api_key);
    if (!userData) {
      return new Response(JSON.stringify({
        error: 'Invalid API key',
        message: 'api_key 未在系统中注册。',
      }), { status: 403, headers: corsHeaders });
    }

    const user = JSON.parse(userData);

    if (user.credits < CREDIT_COST) {
      return new Response(JSON.stringify({
        error: 'Insufficient credits',
        credits_remaining: user.credits,
        required: CREDIT_COST,
        recharge_url: UPGRADE_URL,
        message: '积分不足，每次国产化率分析消耗1积分。',
      }), {
        status: 402,
        headers: { ...corsHeaders, 'X-Credits-Remaining': String(user.credits) },
      });
    }

    // 4. 扣除积分
    user.credits -= CREDIT_COST;
    user.api_calls = (user.api_calls || 0) + 1;
    await env.USER_CREDITS.put(api_key, JSON.stringify(user));

    // 5. 分析国产化率
    const analyzed = items.map(it => {
      const domestic = isDomestic(it.manufacturer);
      const country = getCountry(it.manufacturer);
      const price = Number(it.price) || 0;
      const qty = Number(it.quantity) || 1;
      const totalValue = price * qty;
      return {
        id: it.id || '',
        name: it.name || '',
        manufacturer: it.manufacturer || '',
        category: it.category || '',
        is_domestic: domestic,
        country: country,
        unit_price: price,
        quantity: qty,
        total_value: totalValue,
        domestic_alternative: domestic ? null : getDomesticAlternative(it.manufacturer),
      };
    });

    // 按数量计算
    const domesticCount = analyzed.filter(a => a.is_domestic).length;
    const byCount = analyzed.length > 0 ? (domesticCount / analyzed.length * 100) : 0;

    // 按价值加权计算
    const totalValue = analyzed.reduce((s, a) => s + a.totalValue, 0);
    const domesticValue = analyzed.filter(a => a.is_domestic).reduce((s, a) => s + a.totalValue, 0);
    const byValue = totalValue > 0 ? (domesticValue / totalValue * 100) : 0;

    // 总体国产化率（数量40% + 价值60%加权）
    const overallRate = byCount * 0.4 + byValue * 0.6;

    // 按品类分组
    const byCategory = {};
    for (const a of analyzed) {
      const cat = a.category || 'unknown';
      if (!byCategory[cat]) {
        byCategory[cat] = { total: 0, domestic: 0, total_value: 0, domestic_value: 0 };
      }
      byCategory[cat].total++;
      byCategory[cat].total_value += a.total_value;
      if (a.is_domestic) {
        byCategory[cat].domestic++;
        byCategory[cat].domestic_value += a.total_value;
      }
    }

    const categoryBreakdown = {};
    for (const [cat, data] of Object.entries(byCategory)) {
      categoryBreakdown[cat] = {
        total_items: data.total,
        domestic_items: data.domestic,
        domestic_rate_by_count: data.total > 0 ? (data.domestic / data.total * 100).toFixed(1) : '0',
        domestic_rate_by_value: data.total_value > 0 ? (data.domestic_value / data.total_value * 100).toFixed(1) : '0',
        total_value: data.total_value,
      };
    }

    // 国产替代建议汇总
    const alternatives = analyzed
      .filter(a => a.domestic_alternative)
      .map(a => ({
        original_manufacturer: a.manufacturer,
        item_name: a.name,
        alternative: a.domestic_alternative.alt,
        note: a.domestic_alternative.note,
      }));

    // 分析总结
    let tier;
    if (overallRate >= 80) tier = '高国产化率 - 基本自主可控';
    else if (overallRate >= 50) tier = '中国产化率 - 关键部件仍依赖进口';
    else if (overallRate >= 20) tier = '低国产化率 - 大部分依赖进口';
    else tier = '极低国产化率 - 几乎全进口';

    const result = {
      metadata: {
        analyzed_at: new Date().toISOString(),
        total_items: analyzed.length,
        credits_consumed: CREDIT_COST,
        credits_remaining: user.credits,
      },
      overall_rate: Number(overallRate.toFixed(1)),
      by_value: Number(byValue.toFixed(1)),
      by_count: Number(byCount.toFixed(1)),
      tier: tier,
      domestic_items: analyzed.filter(a => a.is_domestic),
      imported_items: analyzed.filter(a => !a.is_domestic),
      category_breakdown: categoryBreakdown,
      alternatives: alternatives,
      summary: {
        total_domestic: domesticCount,
        total_imported: analyzed.length - domesticCount,
        total_value: totalValue,
        domestic_value: domesticValue,
        imported_value: totalValue - domesticValue,
        alternative_count: alternatives.length,
      },
    };

    return new Response(JSON.stringify(result, null, 2), {
      status: 200,
      headers: {
        ...corsHeaders,
        'Cache-Control': 'no-store',
        'X-Credits-Remaining': String(user.credits),
        'X-API-Tier': 'credits',
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
