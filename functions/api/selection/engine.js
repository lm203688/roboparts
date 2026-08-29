/**
 * RoboParts 智能选型引擎 API
 * POST /api/selection/engine
 *
 * Body:
 * {
 *   "api_key": "gtk_xxx",
 *   "application": "humanoid",          // humanoid|quadruped|robot_arm|amr|industrial
 *   "requirements": {
 *     "max_budget": 50000,
 *     "torque_min": 10,
 *     "weight_max": 2000,
 *     "voltage": 48,
 *     "ros_required": true,
 *     "protocol": "EtherCAT",
 *     "ai_perf_min": 100
 *   },
 *   "categories": ["actuators", "sensors", "chips"],
 *   "count_per_category": 3
 * }
 *
 * 功能：
 * 1. CORS 支持（onRequestOptions）
 * 2. 验证 api_key（消耗 2 积分）
 * 3. 根据 application 确定推荐权重
 * 4. 对每个品类筛选 + 排序
 * 5. 计算综合评分（0-100）：性能匹配度 40% + 成本效益 30% + 生态兼容性 20% + 成熟度 10%
 * 6. 返回推荐列表（含评分、理由、兼容性分析）
 *
 * 数据来源：通过 env.ASSETS.fetch 读取 /api/*.json
 */

const CREDIT_COST = 2;
const UPGRADE_URL = 'https://roboparts.cc/credits';

// B3 度量：KV 读-改-写计数器（stat: 前缀，避免与 gtk_ 用户键冲突）
async function bumpStat(env, key, by = 1) {
  if (!env || !env.USER_CREDITS) return;
  try {
    const cur = await env.USER_CREDITS.get(key);
    const n = (cur ? parseInt(cur, 10) : 0) || 0;
    await env.USER_CREDITS.put(key, String(n + by));
  } catch (e) { /* 度量失败不影响主流程 */ }
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Access-Control-Expose-Headers': 'X-Credits-Remaining, X-Credits-Warning, X-Credits-Threshold, X-API-Tier',
  'Content-Type': 'application/json; charset=utf-8',
};

// 各应用场景的选型权重配置
// - torque_threshold: 优先扭矩阈值（Nm）
// - weight_threshold: 优先重量阈值（g）
// - preferred_protocols: 优先协议列表
// - precision_priority: 精度优先权重（0-1）
// - power_priority: 功耗优先权重（0-1）
// - reliability_priority: 可靠性优先权重（0-1）
// - preferred_sensor_types: 优先传感器类型
const APPLICATION_WEIGHTS = {
  humanoid: {
    label: '人形机器人',
    torque_threshold: 20,
    weight_threshold: 1000,
    preferred_protocols: ['EtherCAT', 'CAN', 'RS485'],
    precision_priority: 0.5,
    power_priority: 0.5,
    reliability_priority: 0.5,
    preferred_sensor_types: ['Tactile', 'Camera', 'IMU', 'Force Torque', 'Force-Torque'],
  },
  quadruped: {
    label: '四足机器人',
    torque_threshold: 10,
    weight_threshold: 500,
    preferred_protocols: ['CAN'],
    precision_priority: 0.5,
    power_priority: 0.6,
    reliability_priority: 0.5,
    preferred_sensor_types: ['IMU', 'LiDAR', 'Camera'],
  },
  robot_arm: {
    label: '机械臂',
    torque_threshold: 5,
    weight_threshold: 2000,
    preferred_protocols: ['EtherCAT'],
    precision_priority: 1.0,
    power_priority: 0.3,
    reliability_priority: 0.5,
    preferred_sensor_types: ['Force Torque', 'Force-Torque', 'Tactile', 'Camera'],
  },
  amr: {
    label: '自主移动机器人',
    torque_threshold: 5,
    weight_threshold: 5000,
    preferred_protocols: ['CAN'],
    precision_priority: 0.3,
    power_priority: 1.0,
    reliability_priority: 0.5,
    preferred_sensor_types: ['LiDAR', 'Camera', 'Ultrasonic'],
  },
  industrial: {
    label: '工业机器人',
    torque_threshold: 10,
    weight_threshold: 10000,
    preferred_protocols: ['EtherCAT'],
    precision_priority: 0.5,
    power_priority: 0.3,
    reliability_priority: 1.0,
    preferred_sensor_types: ['Force Torque', 'Force-Torque', 'Camera', 'LiDAR'],
  },
};

// 价格区间中位数映射（兜底，主用 parsePrice 动态解析）
const PRICE_RANGE_MAP = {
  '0-5': 3,
  '0-20': 10,
  '0-30': 15,
  '0-50': 25,
  '0-100': 50,
  '100-200': 150,
  '150-300': 225,
  '200-400': 300,
  '300-500': 400,
  '500-1000': 750,
  '600-2000': 1300,
  '1000-2000': 1500,
  '2000-5000': 3500,
  '5000-10000': 7500,
};

const VALID_APPLICATIONS = Object.keys(APPLICATION_WEIGHTS);
const VALID_CATEGORIES = ['actuators', 'sensors', 'chips'];

/* ===================== 解析工具函数 ===================== */

// 解析扭矩："9.2 Nm @ 12V" / "44.7 Nm @ 48V" / "17 Nm" / "varies (up to 100+ Nm)"
function parseTorque(str) {
  if (!str) return 0;
  const match = String(str).match(/([\d.]+)\s*Nm/i);
  return match ? parseFloat(match[1]) : 0;
}

// 解析重量："82g" / "840g" / "1.5kg" / "N/A"
function parseWeight(str) {
  if (!str) return 999999;
  const s = String(str);
  const kgMatch = s.match(/([\d.]+)\s*kg/i);
  if (kgMatch) return parseFloat(kgMatch[1]) * 1000;
  const gMatch = s.match(/([\d.]+)\s*g/i);
  if (gMatch) return parseFloat(gMatch[1]);
  return 999999;
}

// 解析价格区间："0-100" / "300-500" / "1000+" / "00-600"
function parsePrice(str) {
  if (!str) return 999999;
  const s = String(str).trim();
  // 优先查映射表
  if (PRICE_RANGE_MAP[s] !== undefined) return PRICE_RANGE_MAP[s];
  // "1000+" 格式
  const plusMatch = s.match(/([\d.]+)\s*\+/);
  if (plusMatch) return parseFloat(plusMatch[1]) * 1.2;
  // "100-200" / "100~200" 格式
  const rangeMatch = s.match(/([\d.]+)\s*[-~]\s*([\d.]+)/);
  if (rangeMatch) {
    return (parseFloat(rangeMatch[1]) + parseFloat(rangeMatch[2])) / 2;
  }
  // 单个数字
  const numMatch = s.match(/([\d.]+)/);
  if (numMatch) return parseFloat(numMatch[1]);
  return 999999;
}

// 解析 AI 算力："70 TOPS" / "275 TOPS" / "2070 FP4 TFLOPS" / "N/A (Hailo-8L AI kit: 13 TOPS)"
function parseAIPerf(str) {
  if (!str) return 0;
  const s = String(str);
  const topsMatch = s.match(/([\d.]+)\s*(?:FP\d\s*)?TOPS/i);
  if (topsMatch) return parseFloat(topsMatch[1]);
  // TFLOPS 粗略换算为 TOPS（×2），支持 "2070 FP4 TFLOPS" 格式
  const tflopsMatch = s.match(/([\d.]+)\s*(?:FP\d\s*)?TFLOPS/i);
  if (tflopsMatch) return parseFloat(tflopsMatch[1]) * 2;
  return 0;
}

// 解析功耗 TDP："10-25W" / "<1W" / "40-130W" / "5W"
function parseTDP(str) {
  if (!str) return 999999;
  const s = String(str);
  const ltMatch = s.match(/<\s*([\d.]+)\s*W/i);
  if (ltMatch) return parseFloat(ltMatch[1]);
  const rangeMatch = s.match(/([\d.]+)\s*[-~]\s*([\d.]+)\s*W/i);
  if (rangeMatch) return (parseFloat(rangeMatch[1]) + parseFloat(rangeMatch[2])) / 2;
  const numMatch = s.match(/([\d.]+)\s*W/i);
  if (numMatch) return parseFloat(numMatch[1]);
  return 999999;
}

// 解析电压范围："10.0~14.8V" / "12-48V" / "24V" / "48-400V"
function parseVoltageRange(str) {
  if (!str) return null;
  const s = String(str);
  const rangeMatch = s.match(/([\d.]+)\s*[~\-]\s*([\d.]+)\s*V/i);
  if (rangeMatch) return { min: parseFloat(rangeMatch[1]), max: parseFloat(rangeMatch[2]) };
  const singleMatch = s.match(/([\d.]+)\s*V/i);
  if (singleMatch) return { min: parseFloat(singleMatch[1]), max: parseFloat(singleMatch[1]) };
  return null;
}

// 解析位置分辨率："4096" / "501900" / "14-bit encoder" / "external encoder"
function parseResolution(str) {
  if (!str) return 0;
  const s = String(str);
  // "14-bit encoder" -> 2^14 = 16384（兼容 "14-bit" 与 "14 bit"）
  const bitMatch = s.match(/([\d.]+)\s*[-\s]*bit/i);
  if (bitMatch) return Math.pow(2, parseInt(bitMatch[1], 10));
  const numMatch = s.match(/([\d.]+)/);
  if (numMatch) return parseInt(numMatch[1], 10);
  return 0;
}

// 协议/接口匹配：检查 item 的 protocol、interface、interfaces 字段是否包含目标协议
function protocolMatch(item, protocol) {
  if (!protocol) return false;
  const fields = [
    item.protocol,
    item.interface,
    Array.isArray(item.interfaces) ? item.interfaces.join('/') : '',
  ].filter(Boolean).join(' ');
  return fields.toLowerCase().includes(protocol.toLowerCase());
}

// 估算技术成熟度 TRL（1-9），数据中无显式 TRL 字段，基于兼容性与完整度推断
function estimateTRL(item) {
  let trl = 5;
  if (item.compatibility && item.compatibility.length >= 2) trl += 1;
  if (item.compatibility && item.compatibility.length >= 4) trl += 1;
  if (rosState(item) === 'yes') trl += 1; // 仅明确声明支持才加分（未声明不加分，也不扣分）
  if (item.applications && item.applications.length >= 3) trl += 1;
  if (item.price_range) trl += 1;
  return Math.min(9, trl);
}

/* ===================== 数据获取 ===================== */

// 通过 env.ASSETS.fetch 读取 /api/<category>.json
// 返回 { ok, items, reason }。
// 取数失败**不能**返回空数组：调用方拿到 length===0 会当成"该品类确实没有符合条件的零件"
// 并把空推荐当结论输出给用户，而真相是我们根本没读到数据。
async function fetchCategoryData(env, request, category) {
  const fileName = category + '.json';
  try {
    const assetUrl = new URL('/api/' + fileName, request.url);
    const resp = await env.ASSETS.fetch(assetUrl);
    if (!resp.ok) return { ok: false, items: null, reason: 'upstream_status_' + resp.status };
    const json = await resp.json();
    return { ok: true, items: json.data || json || [], reason: null };
  } catch (e) {
    return { ok: false, items: null, reason: 'upstream_fetch_failed: ' + e.message };
  }
}

/* ===================== 筛选函数 ===================== */

// 执行器筛选：扭矩、重量、协议、电压
function filterActuators(items, requirements) {
  let filtered = items.filter(a => {
    if (requirements.torque_min) {
      const t = parseTorque(a.torque);
      if (t > 0 && t < requirements.torque_min) return false;
    }
    if (requirements.weight_max) {
      const w = parseWeight(a.weight);
      if (w < 999999 && w > requirements.weight_max) return false;
    }
    if (requirements.protocol && !protocolMatch(a, requirements.protocol)) return false;
    if (requirements.voltage) {
      const v = parseVoltageRange(a.voltage);
      if (v && (requirements.voltage < v.min || requirements.voltage > v.max)) return false;
    }
    return true;
  });
  // 若筛选结果为空，放宽协议与电压限制，仅保留硬性数值筛选
  if (filtered.length === 0) {
    filtered = items.filter(a => {
      if (requirements.torque_min) {
        const t = parseTorque(a.torque);
        if (t > 0 && t < requirements.torque_min) return false;
      }
      if (requirements.weight_max) {
        const w = parseWeight(a.weight);
        if (w < 999999 && w > requirements.weight_max) return false;
      }
      return true;
    });
  }
  return filtered.length > 0 ? filtered : items;
}

// 传感器筛选：类型、精度、接口
function filterSensors(items, requirements, weights) {
  let filtered = items;
  // 按应用场景优先类型筛选
  if (weights.preferred_sensor_types && weights.preferred_sensor_types.length > 0) {
    const preferred = filtered.filter(s =>
      weights.preferred_sensor_types.some(t =>
        String(s.type || '').toLowerCase().includes(t.toLowerCase())
      )
    );
    if (preferred.length > 0) filtered = preferred;
  }
  // 按精度/量程筛选（range 字段含数值时）
  if (requirements.precision_min) {
    const precise = filtered.filter(s => {
      const m = String(s.range || '').match(/([\d.]+)/);
      return m && parseFloat(m[1]) >= requirements.precision_min;
    });
    if (precise.length > 0) filtered = precise;
  }
  return filtered.length > 0 ? filtered : items;
}

// 芯片筛选：AI 算力、功耗、接口
function filterChips(items, requirements) {
  let filtered = items.filter(c => {
    if (requirements.ai_perf_min) {
      const ai = parseAIPerf(c.ai_perf);
      if (ai > 0 && ai < requirements.ai_perf_min) return false;
    }
    if (requirements.power_max) {
      const tdp = parseTDP(c.tdp);
      if (tdp < 999999 && tdp > requirements.power_max) return false;
    }
    if (requirements.protocol) {
      const ifaces = Array.isArray(c.interfaces) ? c.interfaces.join('/') : '';
      if (!ifaces.toLowerCase().includes(requirements.protocol.toLowerCase())) return false;
    }
    return true;
  });
  if (filtered.length === 0) {
    filtered = items.filter(c => {
      if (requirements.ai_perf_min) {
        const ai = parseAIPerf(c.ai_perf);
        if (ai > 0 && ai < requirements.ai_perf_min) return false;
      }
      return true;
    });
  }
  return filtered.length > 0 ? filtered : items;
}

/* ===================== 评分函数 ===================== */

// ROS 支持三态判定
// 数据集中 614/688 实体从未声明 ros_support（执行器 167/199 = 84%）。
// 布尔字段没有「空串 = 未声明」的天然保护，若用 truthy 判断，
// 「厂商未声明」会被渲染成「声明为不支持」——这是对用户的事实性谎报。
// 返回 'yes' | 'no' | 'unknown'；调用方必须分别处理，禁止把 unknown 并入 no。
function rosState(item) {
  const v = item && item.ros_support;
  if (typeof v === 'boolean') return v ? 'yes' : 'no';
  if (v === undefined || v === null || v === '') return 'unknown';
  if (typeof v === 'string') {
    const s = v.trim().toLowerCase();
    if (['true', 'yes', 'supported', '支持'].includes(s)) return 'yes';
    if (['false', 'no', 'unsupported', '不支持'].includes(s)) return 'no';
  }
  return 'unknown';
}

// 执行器评分
function scoreActuator(actuator, requirements, weights) {
  const reasons = [];
  let performance = 0; // /40
  let cost = 0;        // /30
  let ecosystem = 0;   // /20
  let maturity = 0;    // /10

  // --- 性能匹配度 (40) ---
  const torque = parseTorque(actuator.torque);
  const torqueMin = requirements.torque_min || weights.torque_threshold;
  if (torque > 0) {
    if (torque >= torqueMin) {
      performance += 22;
      reasons.push('扭矩' + torque + 'Nm满足≥' + torqueMin + 'Nm要求');
    } else {
      const ratio = torque / torqueMin;
      performance += Math.round(22 * ratio);
      reasons.push('扭矩' + torque + 'Nm，低于' + torqueMin + 'Nm推荐值');
    }
    if (torque >= weights.torque_threshold) {
      performance += 4;
    }
  } else {
    performance += 8;
    reasons.push('扭矩取决于配用电机，需另行选型');
  }

  // 重量
  const weight = parseWeight(actuator.weight);
  const weightMax = requirements.weight_max || weights.weight_threshold;
  if (weight < 999999) {
    if (weight <= weightMax) {
      performance += 10;
      reasons.push('重量' + weight + 'g≤' + weightMax + 'g限制');
    } else {
      performance += 4;
      reasons.push('重量' + weight + 'g超出' + weightMax + 'g限制');
    }
  } else {
    performance += 4;
  }

  // 电压兼容
  if (requirements.voltage) {
    const vRange = parseVoltageRange(actuator.voltage);
    if (vRange && requirements.voltage >= vRange.min && requirements.voltage <= vRange.max) {
      performance += 4;
      reasons.push('电压' + actuator.voltage + '兼容' + requirements.voltage + 'V');
    }
  }

  // 精度优先（机械臂场景）
  if (weights.precision_priority >= 1.0) {
    const res = parseResolution(actuator.position_resolution);
    if (res >= 4096) {
      performance += 4;
      reasons.push('高位置分辨率' + res);
    }
  }

  // --- 成本效益 (30) ---
  const price = parsePrice(actuator.price_range);
  if (requirements.max_budget) {
    if (price <= requirements.max_budget) {
      const budgetRatio = price / requirements.max_budget;
      cost = Math.round(30 * (1 - budgetRatio * 0.3));
      cost = Math.max(15, cost);
      reasons.push('预估价$' + price + '在预算$' + requirements.max_budget + '内');
    } else {
      cost = 5;
      reasons.push('预估价$' + price + '超出预算$' + requirements.max_budget);
    }
  } else {
    cost = 20;
  }

  // --- 生态兼容性 (20) ---
  const reqProtocol = requirements.protocol;
  if (reqProtocol && protocolMatch(actuator, reqProtocol)) {
    ecosystem += 8;
    reasons.push(reqProtocol + '协议匹配');
  } else if (weights.preferred_protocols.some(p => protocolMatch(actuator, p))) {
    const matched = weights.preferred_protocols.find(p => protocolMatch(actuator, p));
    ecosystem += 6;
    reasons.push(matched + '协议适配' + weights.label + '场景');
  }

  const actRos = rosState(actuator);
  if (requirements.ros_required) {
    if (actRos === 'yes') {
      ecosystem += 8;
      reasons.push('支持ROS2');
    } else if (actRos === 'no') {
      reasons.push('警告：厂商明确标注不支持ROS，需额外适配');
    } else {
      // 未声明 ≠ 不支持：不给分，但也不得谎报为「不支持」
      reasons.push('ROS支持情况厂商未声明（非「不支持」），建议向厂商确认后再定案');
    }
  } else if (actRos === 'yes') {
    ecosystem += 4;
  }

  if (actuator.compatibility && actuator.compatibility.length > 0) {
    ecosystem += Math.min(4, actuator.compatibility.length);
  }

  // --- 成熟度 (10) ---
  const trl = estimateTRL(actuator);
  maturity = Math.round((trl - 1) / 8 * 10);

  const score = Math.min(100, Math.round(performance + cost + ecosystem + maturity));

  return {
    score,
    dimensions: { performance, cost, ecosystem, maturity, trl },
    reasons,
    estimated_price: price,
    compatibility_notes: actuatorCompatNotes(actuator),
  };
}

function actuatorCompatNotes(actuator) {
  const notes = [];
  if (actuator.compatibility && actuator.compatibility.length > 0) {
    notes.push('兼容: ' + actuator.compatibility.join(', '));
  }
  if (actuator.interface && /RS485/i.test(actuator.interface)) {
    notes.push('需配U2D2或RS485转接器');
  }
  if (actuator.interface && /CAN/i.test(actuator.interface)) {
    notes.push('需配CAN总线收发器');
  }
  const actRosNote = rosState(actuator);
  if (actRosNote === 'no') {
    notes.push('原生不支持ROS，需自行编写驱动');
  } else if (actRosNote === 'unknown') {
    notes.push('ROS支持情况未声明，需向厂商确认');
  }
  if (actuator.voltage && /48V/i.test(actuator.voltage)) {
    notes.push('高压供电，需独立48V电源');
  }
  return notes.length > 0 ? notes.join('；') : '标准接口，通用性好';
}

// 传感器评分
function scoreSensor(sensor, requirements, weights) {
  const reasons = [];
  let performance = 0; // /40
  let cost = 0;        // /30
  let ecosystem = 0;   // /20
  let maturity = 0;    // /10

  const sensorType = String(sensor.type || '');

  // --- 性能匹配度 (40) ---
  // 类型与应用场景匹配
  const typeMatched = weights.preferred_sensor_types.some(t =>
    sensorType.toLowerCase().includes(t.toLowerCase())
  );
  if (typeMatched) {
    performance += 24;
    const matchedType = weights.preferred_sensor_types.find(t =>
      sensorType.toLowerCase().includes(t.toLowerCase())
    );
    reasons.push(matchedType + '类型适配' + weights.label + '场景');
  } else {
    performance += 10;
  }

  // 精度/量程
  const rangeStr = String(sensor.range || '');
  const rangeNum = rangeStr.match(/([\d.]+)/);
  if (rangeNum) {
    performance += 8;
    reasons.push('量程/精度: ' + rangeStr);
  }

  // 描述完整度（间接反映规格明确度）
  if (sensor.description && sensor.description.length > 50) {
    performance += 4;
  }
  if (sensor.manufacturer) {
    performance += 4;
    reasons.push('厂商: ' + String(sensor.manufacturer).split('(')[0].trim());
  }

  // --- 成本效益 (30) ---
  // 传感器数据无 price_range，给予中性偏上评分
  cost = 20;

  // --- 生态兼容性 (20) ---
  // 类型与机器人生态兼容性
  if (typeMatched) {
    ecosystem += 10;
  }
  // 已知厂商通常生态更完善
  if (sensor.manufacturer) {
    ecosystem += 6;
  }
  // 描述中提及 ROS / 接口关键词
  const desc = String(sensor.description || '').toLowerCase();
  if (desc.includes('ros') || desc.includes('ros2')) {
    ecosystem += 4;
    reasons.push('描述提及ROS支持');
  }

  // --- 成熟度 (10) ---
  let trl = 5;
  if (sensor.manufacturer) trl += 1;
  if (sensor.description && sensor.description.length > 80) trl += 1;
  if (sensor.year || sensor.source) trl += 1;
  if (typeMatched) trl += 1;
  trl = Math.min(9, trl);
  maturity = Math.round((trl - 1) / 8 * 10);

  const score = Math.min(100, Math.round(performance + cost + ecosystem + maturity));

  return {
    score,
    dimensions: { performance, cost, ecosystem, maturity, trl },
    reasons,
    estimated_price: 0, // 传感器无价格数据
    compatibility_notes: sensorCompatNotes(sensor, weights),
  };
}

function sensorCompatNotes(sensor, weights) {
  const notes = [];
  const sensorType = String(sensor.type || '');
  const typeMatched = weights.preferred_sensor_types.some(t =>
    sensorType.toLowerCase().includes(t.toLowerCase())
  );
  if (typeMatched) {
    notes.push('类型与' + weights.label + '需求高度匹配');
  } else {
    notes.push('通用型传感器，需确认接口适配');
  }
  if (sensor.manufacturer) {
    notes.push('建议联系厂商确认供货与数据手册');
  }
  return notes.join('；');
}

// 芯片评分
function scoreChip(chip, requirements, weights) {
  const reasons = [];
  let performance = 0; // /40
  let cost = 0;        // /30
  let ecosystem = 0;   // /20
  let maturity = 0;    // /10

  // --- 性能匹配度 (40) ---
  const aiPerf = parseAIPerf(chip.ai_perf);
  const aiMin = requirements.ai_perf_min || 0;
  if (aiPerf > 0) {
    if (aiMin > 0 && aiPerf >= aiMin) {
      performance += 22;
      reasons.push('AI算力' + aiPerf + 'TOPS满足≥' + aiMin + 'TOPS要求');
    } else if (aiMin > 0) {
      const ratio = aiPerf / aiMin;
      performance += Math.round(22 * ratio);
      reasons.push('AI算力' + aiPerf + 'TOPS，低于' + aiMin + 'TOPS要求');
    } else {
      performance += 16;
      reasons.push('AI算力' + aiPerf + 'TOPS');
    }
  } else {
    // MCU 类无 AI 算力，但功耗低，适合实时控制
    performance += 8;
    if (chip.ai_perf && /N\/A/i.test(String(chip.ai_perf))) {
      reasons.push('无独立AI算力，适合实时控制场景');
    }
  }

  // 功耗（amr 场景功耗优先）
  const tdp = parseTDP(chip.tdp);
  if (tdp < 999999) {
    if (weights.power_priority >= 1.0) {
      // 功耗优先：低功耗加分
      if (tdp <= 10) {
        performance += 10;
        reasons.push('低功耗' + tdp + 'W，适合移动场景');
      } else if (tdp <= 25) {
        performance += 6;
      } else {
        performance += 2;
        reasons.push('功耗' + tdp + 'W较高，需散热设计');
      }
    } else {
      performance += 6;
      reasons.push('功耗' + tdp + 'W');
    }
  } else {
    performance += 4;
  }

  // 接口丰富度
  const ifaceCount = Array.isArray(chip.interfaces) ? chip.interfaces.length : 0;
  if (ifaceCount >= 6) {
    performance += 4;
    reasons.push('接口丰富(' + ifaceCount + '种)');
  } else if (ifaceCount >= 3) {
    performance += 2;
  }

  // --- 成本效益 (30) ---
  const price = parsePrice(chip.price_range);
  if (requirements.max_budget) {
    if (price <= requirements.max_budget) {
      const budgetRatio = price / requirements.max_budget;
      cost = Math.round(30 * (1 - budgetRatio * 0.3));
      cost = Math.max(15, cost);
      reasons.push('预估价$' + price + '在预算$' + requirements.max_budget + '内');
    } else {
      cost = 5;
      reasons.push('预估价$' + price + '超出预算$' + requirements.max_budget);
    }
  } else {
    cost = 20;
  }

  // --- 生态兼容性 (20) ---
  // 协议/接口匹配
  if (requirements.protocol) {
    const ifaces = Array.isArray(chip.interfaces) ? chip.interfaces.join('/') : '';
    if (ifaces.toLowerCase().includes(requirements.protocol.toLowerCase())) {
      ecosystem += 8;
      reasons.push(requirements.protocol + '接口匹配');
    }
  }
  if (weights.preferred_protocols.some(p => {
    const ifaces = Array.isArray(chip.interfaces) ? chip.interfaces.join('/') : '';
    return ifaces.toLowerCase().includes(p.toLowerCase());
  })) {
    const matched = weights.preferred_protocols.find(p => {
      const ifaces = Array.isArray(chip.interfaces) ? chip.interfaces.join('/') : '';
      return ifaces.toLowerCase().includes(p.toLowerCase());
    });
    ecosystem += 4;
    reasons.push('支持' + matched + '接口');
  }

  // ROS 支持
  const chipRos = rosState(chip);
  if (requirements.ros_required) {
    if (chipRos === 'yes') {
      ecosystem += 6;
      reasons.push('支持ROS2');
    } else if (chipRos === 'no') {
      reasons.push('警告：厂商明确标注不支持ROS，需额外适配');
    } else {
      reasons.push('ROS支持情况厂商未声明（非「不支持」），建议向厂商确认后再定案');
    }
  } else if (chipRos === 'yes') {
    ecosystem += 3;
  }

  // --- 成熟度 (10) ---
  const trl = estimateTRL(chip);
  maturity = Math.round((trl - 1) / 8 * 10);

  const score = Math.min(100, Math.round(performance + cost + ecosystem + maturity));

  return {
    score,
    dimensions: { performance, cost, ecosystem, maturity, trl },
    reasons,
    estimated_price: price,
    compatibility_notes: chipCompatNotes(chip),
  };
}

function chipCompatNotes(chip) {
  const notes = [];
  if (chip.form_factor) {
    notes.push('封装: ' + chip.form_factor);
  }
  if (chip.tdp) {
    notes.push('功耗: ' + chip.tdp);
  }
  const chipRosNote = rosState(chip);
  if (chipRosNote === 'no') {
    notes.push('原生不支持ROS，需自行移植');
  } else if (chipRosNote === 'unknown') {
    notes.push('ROS支持情况未声明，需向厂商确认');
  }
  if (chip.ai_perf && /N\/A/i.test(String(chip.ai_perf))) {
    notes.push('无独立AI加速，仅适合控制类任务');
  }
  const ifaceCount = Array.isArray(chip.interfaces) ? chip.interfaces.length : 0;
  if (ifaceCount > 0) {
    notes.push('接口: ' + chip.interfaces.join(', '));
  }
  return notes.length > 0 ? notes.join('；') : '标准计算模块';
}

/* ===================== 兼容性分析 ===================== */

// 跨品类兼容性分析与警告
function analyzeCompatibility(recommendations) {
  const warnings = [];
  const topActuator = recommendations.actuators && recommendations.actuators[0];
  const topChip = recommendations.chips && recommendations.chips[0];

  // 电压不匹配警告
  if (topActuator && topChip) {
    const actV = parseVoltageRange(topActuator.specs.voltage);
    const chipTdp = topChip.specs.tdp ? String(topChip.specs.tdp) : '';
    if (actV && actV.max >= 48) {
      warnings.push('执行器高压(' + topActuator.specs.voltage + ')与芯片低压供电需额外电源管理模块');
    }
    // 协议一致性
    const actProto = String(topActuator.specs.protocol || '') + ' ' + String(topActuator.specs.interface || '');
    const chipIfaces = Array.isArray(topChip.specs.interfaces) ? topChip.specs.interfaces.join('/') : '';
    const commonProtos = ['CAN', 'EtherCAT', 'UART', 'SPI', 'I2C', 'USB'];
    const actHas = commonProtos.filter(p => actProto.toLowerCase().includes(p.toLowerCase()));
    const chipHas = commonProtos.filter(p => chipIfaces.toLowerCase().includes(p.toLowerCase()));
    const shared = actHas.filter(p => chipHas.includes(p));
    if (actHas.length > 0 && chipHas.length > 0 && shared.length === 0) {
      warnings.push('执行器(' + actHas.join('/') + ')与芯片(' + chipHas.join('/') + ')无共同通信协议，需协议转换桥接');
    }
  }

  // ROS 一致性
  const allItems = [
    ...(recommendations.actuators || []),
    ...(recommendations.chips || []),
  ].filter(i => rosState(i.specs) !== 'unknown');
  const rosMismatch = allItems.some(i => rosState(i.specs) === 'no') &&
                      allItems.some(i => rosState(i.specs) === 'yes');
  if (rosMismatch) {
    warnings.push('部分推荐器件不支持ROS，混合使用时需为非ROS器件编写额外驱动节点');
  }

  // 预算警告
  if (recommendations._total_cost_estimate != null && recommendations._budget != null) {
    if (recommendations._total_cost_estimate > recommendations._budget) {
      warnings.push('推荐方案总预估$' + recommendations._total_cost_estimate + '超出预算$' + recommendations._budget);
    }
  }

  return warnings;
}

/* ===================== 请求处理器 ===================== */

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet() {
  return new Response(JSON.stringify({
    endpoint: '/api/selection/engine',
    method: 'POST',
    description: '智能选型引擎：根据机器人应用场景与需求参数，对执行器、传感器、芯片进行筛选与综合评分（0-100），返回推荐列表及跨品类兼容性分析。每次调用消耗 2 积分。',
    request_body: {
      api_key: 'string (必填) - API 密钥，gtk_ 前缀，可在 https://roboparts.cc 获取',
      application: 'string - 应用场景：humanoid | quadruped | robot_arm | amr | industrial，默认 humanoid',
      requirements: {
        max_budget: 'number - 最大预算（美元）',
        torque_min: 'number - 最小扭矩要求（Nm）',
        weight_max: 'number - 最大重量限制（g）',
        voltage: 'number - 工作电压（V）',
        ros_required: 'boolean - 是否要求支持 ROS',
        protocol: 'string - 期望协议，如 EtherCAT / CAN / RS485',
        ai_perf_min: 'number - 最小 AI 算力要求（TOPS）',
        precision_min: 'number - 传感器最小精度/量程',
        power_max: 'number - 芯片最大功耗（W）',
      },
      categories: 'string[] - 选型品类，可选值：actuators / sensors / chips，默认全部',
      count_per_category: 'number - 每个品类返回数量，1-20，默认 3',
    },
    example: {
      api_key: 'gtk_demo_key',
      application: 'humanoid',
      requirements: {
        max_budget: 50000,
        torque_min: 10,
        weight_max: 2000,
        voltage: 48,
        ros_required: true,
        protocol: 'EtherCAT',
        ai_perf_min: 100,
      },
      categories: ['actuators', 'sensors', 'chips'],
      count_per_category: 3,
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
    const { api_key, application, requirements, categories, count_per_category } = body;

    // 1. 验证 api_key
    if (!api_key) {
      return new Response(JSON.stringify({
        error: 'api_key is required',
        message: '请提供 api_key（gtk_ 前缀），可在 https://roboparts.cc 获取。',
      }), { status: 401, headers: corsHeaders });
    }

    // 2. 验证 application
    const app = application || 'humanoid';
    if (!VALID_APPLICATIONS.includes(app)) {
      return new Response(JSON.stringify({
        error: 'Invalid application',
        message: 'application 必须为: ' + VALID_APPLICATIONS.join(', '),
        received: application,
      }), { status: 400, headers: corsHeaders });
    }

    // 3. 验证 categories
    const cats = Array.isArray(categories) && categories.length > 0
      ? categories
      : VALID_CATEGORIES;
    const invalidCats = cats.filter(c => !VALID_CATEGORIES.includes(c));
    if (invalidCats.length > 0) {
      return new Response(JSON.stringify({
        error: 'Invalid categories',
        message: 'categories 仅支持: ' + VALID_CATEGORIES.join(', '),
        received: invalidCats,
      }), { status: 400, headers: corsHeaders });
    }

    const reqs = requirements || {};
    const count = Math.min(20, Math.max(1, Number(count_per_category) || 3));
    const weights = APPLICATION_WEIGHTS[app];

    // 4. 验证积分系统
    if (!env.USER_CREDITS) {
      return new Response(JSON.stringify({
        error: 'Credits system not configured',
        message: 'USER_CREDITS KV 绑定缺失，无法完成积分扣费。',
      }), { status: 500, headers: corsHeaders });
    }

    const userData = await env.USER_CREDITS.get(api_key);
    if (!userData) {
      return new Response(JSON.stringify({
        error: 'Invalid API key',
        message: 'api_key 未在系统中注册，请前往 https://roboparts.cc 获取有效密钥。',
      }), { status: 403, headers: corsHeaders });
    }

    const user = JSON.parse(userData);

    // 5. 积分不足
    if (user.credits < CREDIT_COST) {
      return new Response(JSON.stringify({
        error: 'Insufficient credits',
        credits_remaining: user.credits,
        required: CREDIT_COST,
        credits_needed: CREDIT_COST - user.credits,
        recharge_url: UPGRADE_URL,
        message: '积分不足，每次选型引擎调用消耗 ' + CREDIT_COST + ' 积分。',
      }), {
        status: 402,
        headers: {
          ...corsHeaders,
          'X-Credits-Remaining': String(user.credits),
          'X-Upgrade-URL': UPGRADE_URL,
        },
      });
    }

    // 6. 扣除积分
    user.credits -= CREDIT_COST;
    user.api_calls = (user.api_calls || 0) + 1;
    await bumpStat(env, 'stat:selection_calls:total');
    await bumpStat(env, 'stat:credits_consumed:total', CREDIT_COST);

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
    if (user.credits > LOW_THRESHOLD && user.low_alert_sent) {
      user.low_alert_sent = false;
      delete user.low_alert_at;
    }

    await env.USER_CREDITS.put(api_key, JSON.stringify(user));

    // 7. 加载数据并执行选型
    const recommendations = {};
    let totalCostEstimate = 0;

    const unavailableCats = {};
    for (const category of cats) {
      const fetched = await fetchCategoryData(env, request, category);
      // 取数失败 ≠ 无符合条件的零件。前者是我们的故障，必须单独记账并对外声明，
      // 不能和"筛完确实没有"共用一个空数组。
      if (!fetched.ok) {
        recommendations[category] = null;
        unavailableCats[category] = fetched.reason;
        continue;
      }
      const allItems = fetched.items;
      if (allItems.length === 0) {
        recommendations[category] = [];
        continue;
      }

      // 筛选
      let filtered;
      if (category === 'actuators') {
        filtered = filterActuators(allItems, reqs);
      } else if (category === 'sensors') {
        filtered = filterSensors(allItems, reqs, weights);
      } else if (category === 'chips') {
        filtered = filterChips(allItems, reqs);
      } else {
        filtered = allItems;
      }

      // 评分
      const scored = filtered.map(item => {
        let result;
        if (category === 'actuators') {
          result = scoreActuator(item, reqs, weights);
        } else if (category === 'sensors') {
          result = scoreSensor(item, reqs, weights);
        } else if (category === 'chips') {
          result = scoreChip(item, reqs, weights);
        } else {
          result = { score: 0, reasons: [], estimated_price: 0, compatibility_notes: '' };
        }
        return { item, result };
      });

      // 排序（按综合评分降序）
      scored.sort((a, b) => b.result.score - a.result.score);

      // 取前 N 个，构建响应
      const topN = scored.slice(0, count).map(({ item, result }) => {
        const rec = {
          id: item.id,
          name: item.name,
          score: result.score,
          reasons: result.reasons,
          specs: item,
          estimated_price: result.estimated_price,
          compatibility_notes: result.compatibility_notes,
          score_breakdown: result.dimensions,
        };
        if (result.estimated_price > 0) {
          totalCostEstimate += result.estimated_price;
        }
        return rec;
      });

      recommendations[category] = topN;
    }

    // 8. 跨品类兼容性分析
    recommendations._total_cost_estimate = totalCostEstimate;
    recommendations._budget = reqs.max_budget || null;
    const compatibilityWarnings = analyzeCompatibility(recommendations);
    delete recommendations._total_cost_estimate;
    delete recommendations._budget;

    // 9. 构建最终响应
    const response = {
      success: true,
      meta: {
        application: app,
        application_label: weights.label,
        budget: reqs.max_budget || null,
        credits_remaining: user.credits,
        credits_consumed: CREDIT_COST,
        analyzed_categories: cats,
        total_results: cats.reduce((sum, c) => sum + (recommendations[c] ? recommendations[c].length : 0), 0),
      },
      recommendations,
      total_cost_estimate: totalCostEstimate,
      compatibility_warnings: compatibilityWarnings,
      // 显式声明哪些品类是"没读到数据"而非"没有匹配项"。
      // recommendations[cat] === null 即代表未知；调用方不得把它当成空推荐。
      unavailable_categories: Object.keys(unavailableCats).length ? unavailableCats : undefined,
      partial: Object.keys(unavailableCats).length > 0 || undefined,
    };

    return new Response(JSON.stringify(response, null, 2), {
      status: 200,
      headers: {
        ...corsHeaders,
        'Cache-Control': 'no-store',
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
