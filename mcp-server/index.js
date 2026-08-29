#!/usr/bin/env node

/**
 * RoboParts MCP Server
 * 
 * 基于 Model Context Protocol (MCP) 的机器人零部件数据查询服务
 * 允许 AI Agent 通过标准化协议查询机器人零部件数据
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

// ============================================================
// 路径与常量配置
// ============================================================

const __dirname = dirname(fileURLToPath(import.meta.url));
const API_DIR = join(__dirname, '..', 'api');

// ------------------------------------------------------------
// 【20260805-22 修复】数据源：远程优先，本地仅作仓库内开发回退
//
// 原实现只做 readFileSync(../api/*.json)，而 npm 包里根本不含这些文件
// （tarball 仅 README + index.js + package.json）。装包后 API_DIR 不存在，
// 加之 catch 里静默 `data = []`，用户会得到「查询成功、结果为空」——
// 一个假装正常工作的坏包，比直接报错危害更大。这也是它至今未能发布的真因。
//
// 改为默认拉取 https://roboparts.cc/api/*，附带 ITSELF 可识别的 UA：
// 每一次 Agent 调用都会在边缘遥测里留下 mcp 来源记录，
// 这正是当前唯一缺失的「AI 通道是否真被使用」的可测量信号。
// ------------------------------------------------------------
const PKG_VERSION = '1.0.2';
const REMOTE_BASE = (process.env.ROBOPARTS_API_BASE || 'https://roboparts.cc/api')
  .replace(/\/+$/, '');
const USER_AGENT = `roboparts-mcp-server/${PKG_VERSION} (+https://roboparts.cc; mcp)`;
const FETCH_TIMEOUT_MS = 15000;

// USD 转 CNY 汇率（近似值，用于预算估算）
const USD_TO_CNY_RATE = 7.2;

// 数据缓存
const dataCache = new Map();

// ============================================================
// 数据加载
// ============================================================

/**
 * 加载指定品类的本地 JSON 数据文件
 * @param {string} category - 品类标识
 * @returns {Array} 零部件数据数组
 */
// 【20260805-22】此前只列 7 个品类 = 580 条，而全站对外口径是 688 条。
// MCP 是我们在 AI Agent 侧的门面，少 108 条等于对外报了个不一致的数字。
// 补齐 flexible_actuators(21) / robot_ai_models(44) / data_acquisition(43)。
const FILE_MAP = {
  'actuators': 'actuators.json',
  'sensors': 'sensors.json',
  'chips': 'chips.json',
  'protocols': 'protocols.json',
  'platforms': 'platforms.json',
  'llms': 'llms.json',
  'interfaces': 'interfaces.json',
  'flexible_actuators': 'flexible_actuators.json',
  'robot_ai_models': 'robot_ai_models.json',
  'data_acquisition': 'data_acquisition.json'
};

/**
 * 取一个 JSON 资源：先远程（带退避重试），失败再回退本地（仅在仓库内运行时存在）。
 * 两者都失败就抛错 —— 绝不静默返回空数组假装成功。
 *
 * 【20260805-23】为什么必须重试：预载是 11 路并发 + 启动失败即拒启，
 * 任何一路抖一下整个服务就起不来。本机实测 3 次自检失败 1 次（fetch failed），
 * 单发与 11 路并发复测均 200 —— 即纯属瞬时抖动，而非限流或文件名错误。
 * 不重试 = 把「网络偶发」直接放大成「装完用不了」，用户不会重装第二次。
 * 4xx 不重试（是我们自己的路径写错了，重试多少次都一样，且会掩盖真错）。
 */
const FETCH_RETRIES = 3;
const RETRY_BASE_MS = 400;

async function fetchOnce(url) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': USER_AGENT, 'Accept': 'application/json' },
      signal: ctl.signal
    });
    if (!res.ok) {
      const err = new Error(`HTTP ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

async function fetchJSON(filename) {
  const url = `${REMOTE_BASE}/${filename}`;
  let remoteErr;

  for (let attempt = 1; attempt <= FETCH_RETRIES; attempt++) {
    try {
      return await fetchOnce(url);
    } catch (e) {
      remoteErr = e;
      // 4xx 是确定性错误（路径写错/被删），重试无意义且会掩盖真因。
      if (e.status && e.status >= 400 && e.status < 500) break;
      if (attempt < FETCH_RETRIES) {
        // 静默兜底是假绿温床（环境要点 #19）：重试过程必须可见。
        console.error(
          `[RoboParts MCP] ${filename} 第 ${attempt}/${FETCH_RETRIES} 次拉取失败` +
          `（${e.message}），退避重试中…`
        );
        await new Promise(r => setTimeout(r, RETRY_BASE_MS * Math.pow(2, attempt - 1)));
      }
    }
  }

  // 回退：仓库内开发时 ../api 存在；npm 安装场景下这一步必然失败。
  try {
    return JSON.parse(readFileSync(join(API_DIR, filename), 'utf-8'));
  } catch (localErr) {
    throw new Error(
      `无法加载 ${filename}：远程 ${url} 连续 ${FETCH_RETRIES} 次失败` +
      `（末次：${remoteErr && remoteErr.message}），` +
      `本地回退亦不可用（${localErr.message}）。` +
      `若网络受限，可设置环境变量 ROBOPARTS_API_BASE 指向可达的镜像地址。`
    );
  }
}

/**
 * 启动时一次性预载全部数据。
 * 预载失败即启动失败 —— 宁可起不来，也不要起一个查什么都返回空的服务。
 */
async function preloadAll() {
  const jobs = Object.entries(FILE_MAP).map(async ([cat, filename]) => {
    const parsed = await fetchJSON(filename);
    dataCache.set(cat, parsed.data || []);
  });
  jobs.push((async () => {
    dataCache.set('__compat__', await fetchJSON('compatibility_matrix.json'));
  })());
  await Promise.all(jobs);

  const total = Object.keys(FILE_MAP)
    .reduce((n, c) => n + (dataCache.get(c) || []).length, 0);
  if (total === 0) {
    throw new Error('预载完成但实体总数为 0，判定为数据源异常，拒绝以空库启动。');
  }
  console.error(`[RoboParts MCP] 已加载 ${total} 条实体（数据源 ${REMOTE_BASE}）`);
}

/**
 * 加载指定品类数据（同步，读预载缓存）
 * @param {string} category - 品类标识
 * @returns {Array} 零部件数据数组
 */
function loadData(category) {
  return dataCache.get(category) || [];
}

/**
 * 加载兼容性矩阵
 * @returns {Object} 兼容性矩阵数据
 */
function loadCompatibilityMatrix() {
  return dataCache.get('__compat__') || { compatibility_pairs: [], rules: [] };
}

// ============================================================
// 辅助函数
// ============================================================

/**
 * 数组/标量字段归一化为可读字符串，未声明一律 'N/A'。
 */
function fmtSpec(v) {
  if (Array.isArray(v)) return v.length ? v.join(' / ') : 'N/A';
  // 对象直接透传会把 {status,reason,registry_ref,...} 整块倒进 key_specs，
  // 对调用方是噪声而非规格；这里统一收敛为 'N/A'，需要结构化的走专用字段。
  if (v !== null && typeof v === 'object') return 'N/A';
  return (v === undefined || v === null || v === '') ? 'N/A' : v;
}

/**
 * 布尔能力字段的三态输出。
 *
 * 【20260806-20】同族缺陷第三处：旧写法 `item.embodied_ai || false` 把「厂商未声明」
 * 压成「声明为 false」。本函数里所有字符串字段都走 `|| 'N/A'`（诚实表达未知），
 * 唯独布尔字段折成了 false —— 字符串靠「空串 = 未声明」天然有保护，布尔没有，
 * 与 20260806-12 修 compat_engine、20260806-08 修 protocol/mechanical 是同一个根因。
 * 危害是实打实的：llms 品类 42 条里 20 条从未声明 embodied_ai，却被 MCP 一律
 * 报成 `false`，等于向调用方的 AI Agent 断言「此模型不支持具身智能」。
 * 未声明返回 'N/A'，与同函数内字符串字段口径一致；已声明才回真实布尔值。
 */
function triSpec(v) {
  return typeof v === 'boolean' ? v : 'N/A';
}

/**
 * 根据品类提取关键规格信息
 * @param {Object} item - 零部件对象
 * @param {string} category - 品类
 * @returns {Object} 关键规格对象
 */
function getKeySpecs(item, category) {
  switch (category) {
    case 'actuators':
      return {
        type: item.type || 'N/A',
        torque: item.torque || 'N/A',
        speed: item.speed || 'N/A',
        voltage: item.voltage || 'N/A',
        protocol: item.protocol || 'N/A',
        interface: item.interface || 'N/A'
      };
    case 'sensors':
      return {
        type: item.type || 'N/A',
        range: item.range || 'N/A',
        description: (item.description || '').substring(0, 120)
      };
    case 'chips':
      return {
        type: item.type || 'N/A',
        cpu: item.cpu || 'N/A',
        gpu: item.gpu || 'N/A',
        ai_perf: item.ai_perf || 'N/A',
        tdp: item.tdp || 'N/A',
        memory: item.memory || 'N/A'
      };
    case 'protocols':
      return {
        type: item.type || 'N/A',
        speed: item.speed || 'N/A',
        latency: item.latency || 'N/A',
        determinism: item.determinism || 'N/A',
        max_nodes: item.max_nodes || 'N/A'
      };
    case 'platforms':
      return {
        type: item.type || 'N/A',
        manufacturer: item.manufacturer || 'N/A',
        application: item.application || 'N/A',
        description: (item.description || '').substring(0, 120)
      };
    case 'llms':
      return {
        type: item.type || 'N/A',
        parameters: item.parameters || 'N/A',
        input: item.input || 'N/A',
        output: item.output || 'N/A',
        embodied_ai: triSpec(item.embodied_ai)
      };
    case 'interfaces':
      return {
        type: item.type || 'N/A',
        speed: item.speed || 'N/A',
        power: item.power || 'N/A',
        connector: item.connector || 'N/A'
      };
    // 【20260809-07】connectors 新类目。连接器的关键规格既不是扭矩也不是算力，
    // 而是「载流 / 速率 / 走线开口 / 对接方向 / 形态」—— 套用别的品类字段等于一律 N/A。
    // routing_opening 与 mating_orientations 是本品类做互换判定的入口字段。
    case 'connectors':
      return {
        type: item.type || 'N/A',
        current: item.current || 'N/A',
        data_rate: item.data_rate || 'N/A',
        protocol: item.protocol || 'N/A',
        routing_opening: item.routing_opening || 'N/A',
        mating_orientations: Array.isArray(item.mating_orientations)
          ? item.mating_orientations.join(' / ')
          : (item.mating_orientations || 'N/A'),
        form_factor: item.form_factor || 'N/A'
      };
    // 【20260806-20】以下三类此前落到 default 返回 {}，共 108/688 条（15.7%）实体
    // 在 MCP 响应里 key_specs 恒为空对象 —— 对调用方而言等同「这条没有任何规格」。
    // 尤其讽刺的是：全库仅有的 7 条 embodied_ai=true 全在 robot_ai_models，
    // 恰好落在这个空洞里；而暴露该字段的 llms 品类反倒一条 true 都没有。
    // 即「有信号的地方不给，给的地方没信号」。
    case 'robot_ai_models':
      return {
        type: item.type || 'N/A',
        parameters: item.parameters || 'N/A',
        manufacturer: item.manufacturer || 'N/A',
        embodied_ai: triSpec(item.embodied_ai)
      };
    case 'data_acquisition':
      return {
        type: item.type || 'N/A',
        manufacturer: item.manufacturer || 'N/A',
        interfaces: fmtSpec(item.interfaces),
        applications: fmtSpec(item.applications)
      };
    case 'flexible_actuators':
      return {
        type: item.type || 'N/A',
        manufacturer: item.manufacturer || 'N/A',
        application: fmtSpec(item.application)
      };
    default:
      return {};
  }
}

/**
 * 解析价格范围字符串，提取数值
 * 支持 "0-100"、"600-2000"、"$0.5-10/1M tokens" 等格式
 * @param {string} priceStr - 价格范围字符串
 * @returns {Object|null} { min, max, mid, unit }
 */
function parsePrice(priceStr) {
  if (!priceStr || typeof priceStr !== 'string') return null;
  const numbers = priceStr.match(/[\d.]+/g);
  if (!numbers || numbers.length === 0) return null;
  if (numbers.length === 1) {
    const val = parseFloat(numbers[0]);
    return { min: 0, max: val, mid: val / 2, unit: 'USD' };
  }
  const min = parseFloat(numbers[0]);
  const max = parseFloat(numbers[1]);
  return { min, max, mid: (min + max) / 2, unit: 'USD' };
}

/**
 * 解析电压范围字符串
 * 支持 "10.0~14.8V"、"12-48V"、"5-30V" 等格式
 * @param {string} voltageStr - 电压范围字符串
 * @returns {Object|null} { min, max }
 */
function parseVoltage(voltageStr) {
  if (!voltageStr || typeof voltageStr !== 'string') return null;
  const numbers = voltageStr.match(/[\d.]+/g);
  if (!numbers || numbers.length < 2) {
    if (numbers && numbers.length === 1) {
      const val = parseFloat(numbers[0]);
      return { min: val, max: val };
    }
    return null;
  }
  return { min: parseFloat(numbers[0]), max: parseFloat(numbers[1]) };
}

/**
 * 检查两个电压范围是否重叠
 * @param {Object} v1 - 电压范围 1
 * @param {Object} v2 - 电压范围 2
 * @returns {boolean|null} 是否重叠，null 表示无法判断
 */
function voltageOverlap(v1, v2) {
  if (!v1 || !v2) return null;
  return v1.min <= v2.max && v2.min <= v1.max;
}

/**
 * 在指定品类中查找零部件
 * @param {string} id - 零部件 ID
 * @param {string} category - 品类
 * @returns {Object|null} 零部件对象
 */
function findComponent(id, category) {
  const data = loadData(category);
  return data.find(item => item.id === id) || null;
}

/**
 * 生成零部件摘要信息
 * @param {Object} item - 零部件对象
 * @param {string} category - 品类
 * @returns {Object} 摘要对象
 */
function summarizeComponent(item, category) {
  return {
    id: item.id,
    name: item.name,
    category: category,
    manufacturer: item.manufacturer || 'N/A',
    key_specs: getKeySpecs(item, category),
    price_range: item.price_range || item.price || 'N/A'
  };
}

/**
 * 根据厂商生成供应商建议
 * @param {string} manufacturer - 厂商名称
 * @returns {Object} 供应商建议
 */
function getSupplierSuggestion(manufacturer) {
  const knownSuppliers = {
    'ROBOTIS': 'ROBOTIS 官方商店 / RobotShop / 易睿科技(中国代理)',
    'NVIDIA': 'NVIDIA 官网 / 安富利(Avnet) / Mouser / 得捷(DigiKey)',
    'STMicroelectronics': 'ST 官方 / Mouser / DigiKey / 立创商城',
    'Raspberry Pi Foundation': 'Raspberry Pi 官方 / 立创商城 / Mouser / RobotShop',
    'Odrive': 'Odrive 官方 / RobotShop / AliExpress',
    'SimpleFOC': 'SimpleFOC GitHub / AliExpress',
    'Bosch': 'Bosch 官方 / Mouser / DigiKey / 立创商城',
    'Analog Devices': 'ADI 官方 / Mouser / DigiKey / 立创商城',
    'Velodyne (Ouster), Luminar, Hesai, Livox, Innoviz': 'Livox 官方(中国) / Ouster 官方 / RobotShop',
    'Unitree Robotics': 'Unitree 官方淘宝店 / Unitree 官网',
    'Boston Dynamics (Hyundai)': 'Boston Dynamics 官方(企业销售)',
    'Tesla': 'Tesla 官方(限量供应)',
    'Figure AI': 'Figure AI 官方(企业合作)',
    'Google DeepMind': '研究合作(非商业销售)',
    'Berkeley': '开源项目 GitHub(免费)',
    'OpenAI': 'OpenAI API 平台',
    'Anthropic': 'Anthropic API 平台',
    'ANYbotics (ETH Zurich spinoff)': 'ANYbotics 官方(企业销售)',
    'DJI': 'DJI 官方 / DJI 授权经销商',
  };

  if (knownSuppliers[manufacturer]) {
    return { manufacturer, supplier: knownSuppliers[manufacturer] };
  }
  return {
    manufacturer,
    supplier: `${manufacturer} 官方渠道 / Mouser / DigiKey / 立创商城 / AliExpress`
  };
}

// ============================================================
// 工具实现
// ============================================================

/**
 * 工具1: search_components
 * 搜索机器人零部件，支持按品类、关键词、规格筛选
 */
function searchComponents(args) {
  const { category, keyword, limit } = args;
  const maxResults = typeof limit === 'number' && limit > 0 ? limit : 10;

  const categories = category
    ? [category]
    : ['actuators', 'sensors', 'chips', 'protocols', 'platforms', 'llms', 'interfaces'];

  const results = [];

  for (const cat of categories) {
    const data = loadData(cat);
    for (const item of data) {
      // 如果有关键词，进行匹配
      if (keyword) {
        const searchText = [
          item.id, item.name, item.manufacturer, item.type,
          item.description, item.category, item.protocol,
          item.interface, JSON.stringify(item.applications || []),
          JSON.stringify(item.interfaces || []),
          JSON.stringify(item.compatibility || [])
        ].filter(Boolean).join(' ').toLowerCase();

        if (!searchText.includes(keyword.toLowerCase())) {
          continue;
        }
      }

      results.push(summarizeComponent(item, cat));
    }
  }

  const limited = results.slice(0, maxResults);

  return {
    query: { category: category || 'all', keyword: keyword || '', limit: maxResults },
    total_found: results.length,
    returned: limited.length,
    components: limited
  };
}

/**
 * 工具2: get_component_detail
 * 获取单个零部件的详细信息
 */
function getComponentDetail(args) {
  const { id, category } = args;

  if (!id || !category) {
    return { error: '参数缺失: id 和 category 均为必填项' };
  }

  const component = findComponent(id, category);

  if (!component) {
    return {
      error: '未找到零部件',
      id,
      category,
      suggestion: '请检查 ID 和品类是否正确。可使用 search_components 工具搜索正确的零部件。'
    };
  }

  return {
    id: component.id,
    name: component.name,
    category: category,
    ...component
  };
}

/**
 * 工具3: check_compatibility
 * 检查两个零部件的兼容性
 */
function checkCompatibility(args) {
  const {
    component1_id, component1_category,
    component2_id, component2_category
  } = args;

  // 查找两个零部件
  const c1 = findComponent(component1_id, component1_category);
  const c2 = findComponent(component2_id, component2_category);

  if (!c1) {
    return {
      error: `未找到零部件: ${component1_id} (品类: ${component1_category})`,
      suggestion: '请使用 search_components 工具确认正确的 ID 和品类'
    };
  }
  if (!c2) {
    return {
      error: `未找到零部件: ${component2_id} (品类: ${component2_category})`,
      suggestion: '请使用 search_components 工具确认正确的 ID 和品类'
    };
  }

  const reasons = [];
  const warnings = [];
  let compatible = true;

  // 获取品类对（排序以便匹配规则）
  const pair = [component1_category, component2_category].sort().join('+');
  const actuator = component1_category === 'actuators' ? c1 : (component2_category === 'actuators' ? c2 : null);
  const chip = component1_category === 'chips' ? c1 : (component2_category === 'chips' ? c2 : null);
  const sensor = component1_category === 'sensors' ? c1 : (component2_category === 'sensors' ? c2 : null);
  const proto = component1_category === 'protocols' ? c1 : (component2_category === 'protocols' ? c2 : null);
  const iface = component1_category === 'interfaces' ? c1 : (component2_category === 'interfaces' ? c2 : null);

  // ============================================================
  // 规则1: 执行器 + 芯片/控制器 — 检查协议匹配 + 电压范围
  // ============================================================
  if (pair === 'actuators+chips' && actuator && chip) {
    const actProtocol = (actuator.protocol || '').toUpperCase();
    const chipInterfaces = (chip.interfaces || []).map(i => String(i).toUpperCase());
    const chipCompat = (chip.compatibility || []).map(c => String(c).toUpperCase());
    const allChipIfaces = [...chipInterfaces, ...chipCompat];
    const chipStr = allChipIfaces.join(' ');

    // --- 协议匹配检查 ---
    if (actProtocol.includes('DYNAMIXEL')) {
      // DYNAMIXEL Protocol 需要 RS485/TTL 接口或 U2D2/OpenCM 控制器
      if (chipStr.includes('RS485') || chipStr.includes('TTL') ||
          chipStr.includes('U2D2') || chipStr.includes('OPENCM') ||
          chipStr.includes('DYNAMIXEL')) {
        reasons.push(`协议匹配: ${actuator.name} 使用 ${actuator.protocol}, ${chip.name} 支持 RS485/TTL 接口`);
      } else {
        compatible = false;
        reasons.push(`协议不匹配: ${actuator.name} 需要 DYNAMIXEL Protocol (RS485/TTL), ${chip.name} 接口为 [${chipInterfaces.join(', ')}], 不直接支持`);
        warnings.push(`建议使用 U2D2 或 OpenCM 控制器桥接 DYNAMIXEL 协议, 或选择带 RS485 接口的控制器`);
      }
    } else if (actProtocol.includes('CAN')) {
      if (chipStr.includes('CAN')) {
        reasons.push(`协议匹配: ${actuator.name} 使用 CAN 总线, ${chip.name} 支持 CAN 接口`);
      } else {
        compatible = false;
        reasons.push(`协议不匹配: ${actuator.name} 需要 CAN 总线, ${chip.name} 不支持 CAN 接口`);
        warnings.push(`建议增加 CAN 桥接模块(如 PiCAN)或选择带 CAN 接口的芯片`);
      }
    } else if (actProtocol.includes('UART') || actProtocol.includes('I2C') || actProtocol.includes('SPI')) {
      const protocols = actProtocol.split(/[\/,]/).map(p => p.trim()).filter(p => p.length > 0);
      const hasMatch = protocols.some(p => {
        const pUpper = p.toUpperCase();
        return chipStr.includes(pUpper) || allChipIfaces.some(i => i.includes(pUpper));
      });
      if (hasMatch) {
        reasons.push(`协议匹配: ${actuator.name} 使用 ${actuator.protocol}, ${chip.name} 支持对应接口`);
      } else {
        warnings.push(`协议可能不匹配: ${actuator.name} 使用 ${actuator.protocol}, 请确认 ${chip.name} 是否支持`);
      }
    } else if (actProtocol && actProtocol !== 'N/A') {
      warnings.push(`执行器协议 "${actuator.protocol}" 未在已知规则中, 建议人工确认兼容性`);
    }

    // --- 电压范围检查 ---
    const actVoltage = parseVoltage(actuator.voltage);
    if (actVoltage) {
      reasons.push(`电压信息: ${actuator.name} 工作电压 ${actuator.voltage} (范围: ${actVoltage.min}V ~ ${actVoltage.max}V)`);
      if (actVoltage.min > 24) {
        warnings.push(`${actuator.name} 工作电压较高 (${actuator.voltage}), 需要独立供电电路, ${chip.name} 不能直接驱动, 需配置电机驱动板`);
      } else if (actVoltage.min >= 10 && actVoltage.max <= 14.8) {
        reasons.push(`电压匹配: ${actuator.name} 工作电压在常见 12V 供电范围内, 可使用标准电源方案`);
      }
    }
  }

  // ============================================================
  // 规则2: 芯片 + 传感器 — 检查接口兼容 (I2C/SPI/UART/USB)
  // ============================================================
  if (pair === 'chips+sensors' && chip && sensor) {
    const chipInterfaces = (chip.interfaces || []).map(i => String(i).toUpperCase());
    // 传感器可能没有显式接口字段, 从描述/类型中推断
    const sensorText = `${sensor.name || ''} ${sensor.type || ''} ${sensor.description || ''} ${sensor.range || ''}`.toUpperCase();
    const commonInterfaces = ['I2C', 'SPI', 'UART', 'USB', 'CAN', 'ETHERNET', 'GBE', '10GBE', 'MIPI', 'CSI', 'PCIe', 'ADC'];
    const sensorIfaces = commonInterfaces.filter(iface => sensorText.includes(iface));

    if (sensorIfaces.length === 0) {
      // 无法确定传感器接口
      warnings.push(`传感器 ${sensor.name} 未明确标注接口类型, ${chip.name} 接口: [${chipInterfaces.join(', ')}]`);
      warnings.push(`建议查阅传感器数据手册确认通信接口`);
      reasons.push(`接口信息: ${chip.name} 支持 [${chipInterfaces.join(', ')}] 接口`);
    } else {
      // 检查是否有交集
      const matched = sensorIfaces.filter(si =>
        chipInterfaces.some(ci => ci.includes(si) || si.includes(ci))
      );
      if (matched.length > 0) {
        reasons.push(`接口兼容: 传感器 ${sensor.name} 需要 [${matched.join(', ')}] 接口, ${chip.name} 支持对应接口`);
      } else {
        compatible = false;
        reasons.push(`接口不兼容: 传感器 ${sensor.name} 需要 [${sensorIfaces.join(', ')}] 接口, ${chip.name} 仅支持 [${chipInterfaces.join(', ')}]`);
        warnings.push(`建议使用接口转换模块或更换兼容的芯片/传感器`);
      }
    }
  }

  // ============================================================
  // 规则3: 协议 + 接口 — 检查物理层兼容性
  // ============================================================
  if (pair === 'interfaces+protocols' && proto && iface) {
    const protoName = (proto.name || '').toUpperCase();
    const protoType = (proto.type || '').toUpperCase();
    const protoCable = (proto.cable || '').toUpperCase();
    const ifaceName = (iface.name || '').toUpperCase();
    const ifaceType = (iface.type || '').toUpperCase();
    const ifaceApps = (iface.applications || []).map(a => String(a).toUpperCase());
    const ifaceStr = `${ifaceName} ${ifaceType} ${ifaceApps.join(' ')}`;

    // EtherCAT / PROFINET 等工业以太网协议需要以太网接口
    if (protoName.includes('ETHERCAT') || protoName.includes('PROFINET') || protoType.includes('ETHERNET')) {
      if (ifaceStr.includes('ETHERNET') || ifaceStr.includes('GBE') || ifaceStr.includes('10GBE') || ifaceName.includes('ETHERNET')) {
        reasons.push(`物理层兼容: ${proto.name} 基于工业以太网, ${iface.name} 支持以太网物理层`);
      } else {
        compatible = false;
        reasons.push(`物理层不兼容: ${proto.name} 需要以太网物理层, ${iface.name} 不支持以太网`);
      }
    } else if (protoName.includes('CAN') || protoType.includes('FIELDBUS')) {
      // CANopen 等 CAN 总线协议
      if (ifaceName.includes('CAN') || ifaceStr.includes('CAN')) {
        reasons.push(`物理层兼容: ${proto.name} 使用 CAN 总线, ${iface.name} 支持 CAN 物理层`);
      } else {
        compatible = false;
        reasons.push(`物理层不兼容: ${proto.name} 需要 CAN 总线物理层, ${iface.name} 不支持 CAN`);
        warnings.push(`建议增加 CAN 收发器模块或选择带 CAN 接口的方案`);
      }
    } else if (protoName.includes('USB')) {
      if (ifaceName.includes('USB')) {
        reasons.push(`物理层兼容: ${proto.name} 与 ${iface.name} 均基于 USB 物理层`);
      } else {
        compatible = false;
        reasons.push(`物理层不兼容: ${proto.name} 需要 USB 接口, ${iface.name} 不支持 USB`);
      }
    } else if (protoName.includes('MODBUS') || protoType.includes('SERIAL')) {
      if (ifaceName.includes('UART') || ifaceName.includes('RS485') || ifaceName.includes('RS232')) {
        reasons.push(`物理层兼容: ${proto.name} 基于串口通信, ${iface.name} 支持串口物理层`);
      } else {
        warnings.push(`${proto.name} 基于串口通信, 请确认 ${iface.name} 是否支持 UART/RS485`);
      }
    } else {
      reasons.push(`协议 ${proto.name} 与接口 ${iface.name} 的物理层兼容性需要进一步确认`);
      reasons.push(`协议线缆: ${proto.cable || 'N/A'}, 接口类型: ${iface.type || 'N/A'}`);
    }
  }

  // ============================================================
  // 通用检查: 应用场景匹配
  // ============================================================
  const apps1 = c1.applications || [];
  const apps2 = c2.applications || [];
  if (apps1.length > 0 && apps2.length > 0) {
    const commonApps = apps1.filter(a => apps2.includes(a));
    if (commonApps.length > 0) {
      reasons.push(`应用场景匹配: 两者均适用于 [${commonApps.join(', ')}]`);
    } else {
      warnings.push(`应用场景不重叠: ${c1.name} 适用于 [${apps1.join(', ')}], ${c2.name} 适用于 [${apps2.join(', ')}]`);
    }
  }

  // ============================================================
  // 通用检查: ROS2 支持
  // ============================================================
  if (c1.ros_support !== undefined && c2.ros_support !== undefined) {
    if (c1.ros_support && c2.ros_support) {
      reasons.push(`ROS2 支持: 两者均原生支持 ROS2, 软件集成方便`);
    } else if (!c1.ros_support && !c2.ros_support) {
      warnings.push(`ROS2 支持: 两者均不原生支持 ROS2, 可能需要开发自定义驱动`);
    } else {
      const noRos = !c1.ros_support ? c1.name : c2.name;
      warnings.push(`ROS2 支持: ${noRos} 不原生支持 ROS2, 可能需要额外驱动开发`);
    }
  }

  // ============================================================
  // 通用检查: 兼容性列表匹配
  // ============================================================
  const compat1 = c1.compatibility || [];
  const compat2 = c2.compatibility || [];
  if (compat1.length > 0) {
    const name2Upper = (c2.name || '').toUpperCase();
    const matchedCompat = compat1.filter(c =>
      name2Upper.includes(String(c).toUpperCase()) ||
      String(c).toUpperCase().includes(name2Upper)
    );
    if (matchedCompat.length > 0) {
      reasons.push(`官方兼容性列表: ${c1.name} 声明兼容 [${matchedCompat.join(', ')}]`);
    }
  }
  if (compat2.length > 0) {
    const name1Upper = (c1.name || '').toUpperCase();
    const matchedCompat = compat2.filter(c =>
      name1Upper.includes(String(c).toUpperCase()) ||
      String(c).toUpperCase().includes(name1Upper)
    );
    if (matchedCompat.length > 0) {
      reasons.push(`官方兼容性列表: ${c2.name} 声明兼容 [${matchedCompat.join(', ')}]`);
    }
  }

  // 如果没有任何检查结果
  if (reasons.length === 0 && warnings.length === 0) {
    reasons.push(`未找到针对品类组合 [${component1_category} + ${component2_category}] 的明确兼容性规则, 建议人工确认`);
    warnings.push(`当前品类组合不在自动检查范围内, 请查阅产品文档或联系厂商确认兼容性`);
  }

  return {
    component1: { id: c1.id, name: c1.name, category: component1_category },
    component2: { id: c2.id, name: c2.name, category: component2_category },
    compatible,
    reasons,
    warnings,
    summary: compatible
      ? `兼容性检查通过: ${c1.name} 与 ${c2.name} 可以配合使用`
      : `兼容性检查未通过: ${c1.name} 与 ${c2.name} 存在兼容性问题, 请查看 reasons 和 warnings 了解详情`
  };
}

/**
 * 工具4: recommend_for_application
 * 根据应用场景推荐零部件组合
 */
function recommendForApplication(args) {
  const { application, budget, count } = args;
  const n = typeof count === 'number' && count > 0 ? count : 3;

  // 应用场景映射
  const appMap = {
    'humanoid': ['humanoid', 'humanoid_hip'],
    'quadruped': ['quadruped'],
    'robot_arm': ['robot_arm', 'manipulator', 'large_manipulator'],
    'amr': ['autonomous_vehicle', 'mobile_robot', 'amr', 'autonomous'],
    'industrial': ['industrial', 'industrial_robot', 'large_manipulator', 'CNC', 'motion_control']
  };

  // 传感器推荐关键词映射
  const sensorKeywords = {
    'humanoid': ['IMU', 'TACTILE', 'FORCE', 'TORQUE', 'CAMERA', 'VISION', 'DEPTH'],
    'quadruped': ['IMU', 'LIDAR', 'DEPTH', 'CAMERA', 'FORCE'],
    'robot_arm': ['FORCE', 'TORQUE', 'TACTILE', 'CAMERA', 'VISION', 'DEPTH'],
    'amr': ['LIDAR', 'IMU', 'CAMERA', 'DEPTH', 'RADAR'],
    'industrial': ['FORCE', 'TORQUE', 'VISION', 'CAMERA', 'PROXIMITY', 'TEMPERATURE']
  };

  const targetApps = appMap[application] || [application];
  const keywords = sensorKeywords[application] || [];

  // 预算分配（CNY → USD）
  const budgetUSD = budget ? budget / USD_TO_CNY_RATE : null;
  // 各品类预算占比: 执行器 40%, 芯片 25%, 传感器 20%, 控制器 15%
  const budgetAllocation = budgetUSD ? {
    actuators: budgetUSD * 0.40,
    chips: budgetUSD * 0.25,
    sensors: budgetUSD * 0.20,
    controllers: budgetUSD * 0.15
  } : null;

  /**
   * 按预算筛选并排序
   */
  function filterAndSort(items, category, allocKey) {
    let filtered = items;
    if (budgetAllocation && allocKey) {
      const alloc = budgetAllocation[allocKey];
      const withinBudget = items.filter(item => {
        const price = parsePrice(item.price_range || item.price);
        if (!price) return true; // 无价格信息的不排除
        return price.mid <= alloc;
      });
      // 如果预算内没有足够项目, 返回所有项目(按价格升序)
      filtered = withinBudget.length >= Math.min(n, items.length) ? withinBudget : items;
    }
    // 按价格升序排序(性价比优先)
    return filtered.sort((a, b) => {
      const pa = parsePrice(a.price_range || a.price);
      const pb = parsePrice(b.price_range || b.price);
      if (pa && pb) return pa.mid - pb.mid;
      if (pa && !pb) return -1;
      if (!pa && pb) return 1;
      return 0;
    });
  }

  // --- 执行器推荐 ---
  const allActuators = loadData('actuators');
  const matchedActuators = allActuators.filter(a => {
    const apps = a.applications || [];
    return apps.some(app => targetApps.includes(app));
  });
  const sortedActuators = filterAndSort(matchedActuators, 'actuators', 'actuators');
  const actuatorRecs = sortedActuators.slice(0, n).map(a => summarizeComponent(a, 'actuators'));

  // --- 芯片推荐 (计算芯片) ---
  const allChips = loadData('chips');
  const matchedComputeChips = allChips.filter(c => {
    const apps = c.applications || [];
    return apps.some(app => targetApps.includes(app)) && c.category === 'compute';
  });
  const sortedComputeChips = filterAndSort(matchedComputeChips, 'chips', 'chips');
  const chipRecs = sortedComputeChips.slice(0, n).map(c => summarizeComponent(c, 'chips'));

  // --- 控制器推荐 (MCU) ---
  const matchedControllers = allChips.filter(c => {
    const apps = c.applications || [];
    return apps.some(app => targetApps.includes(app)) && c.category === 'mcu';
  });
  const sortedControllers = filterAndSort(matchedControllers, 'chips', 'controllers');
  const controllerRecs = sortedControllers.slice(0, n).map(c => summarizeComponent(c, 'chips'));

  // --- 传感器推荐 ---
  const allSensors = loadData('sensors');
  const matchedSensors = allSensors.filter(s => {
    const text = `${s.name || ''} ${s.type || ''} ${s.description || ''}`.toUpperCase();
    return keywords.some(kw => text.includes(kw));
  });
  // 传感器通常没有 price_range, 不做预算筛选
  const sensorRecs = matchedSensors.slice(0, n).map(s => summarizeComponent(s, 'sensors'));

  // 计算预估总成本
  let estimatedCostUSD = 0;
  const allRecs = [...sortedActuators.slice(0, n), ...sortedComputeChips.slice(0, n),
  ...sortedControllers.slice(0, n), ...matchedSensors.slice(0, n)];
  for (const item of allRecs) {
    const price = parsePrice(item.price_range || item.price);
    if (price) estimatedCostUSD += price.mid;
  }

  return {
    application,
    budget_cny: budget || '不限',
    budget_usd: budgetUSD ? budgetUSD.toFixed(2) : '不限',
    count_per_category: n,
    estimated_cost_usd: estimatedCostUSD.toFixed(2),
    estimated_cost_cny: (estimatedCostUSD * USD_TO_CNY_RATE).toFixed(2),
    recommendations: {
      actuators: {
        count: actuatorRecs.length,
        items: actuatorRecs
      },
      sensors: {
        count: sensorRecs.length,
        items: sensorRecs
      },
      chips: {
        count: chipRecs.length,
        items: chipRecs
      },
      controllers: {
        count: controllerRecs.length,
        items: controllerRecs
      }
    },
    note: budget
      ? `推荐已按预算 ${budget} CNY (约 ${budgetUSD.toFixed(0)} USD) 筛选, 各品类预算占比: 执行器40%, 芯片25%, 传感器20%, 控制器15%`
      : '未设置预算限制, 按性价比排序推荐'
  };
}

/**
 * 工具5: export_bom
 * 从选定的零部件列表导出 BOM 清单
 */
function exportBom(args) {
  const { project_name, items } = args;

  if (!project_name) {
    return { error: '参数缺失: project_name 为必填项' };
  }
  if (!Array.isArray(items) || items.length === 0) {
    return { error: '参数缺失或为空: items 为必填项, 且需包含至少一个零部件' };
  }

  const bomItems = [];
  const warnings = [];
  let totalCostUSD = 0;
  let totalModules = 0;
  const manufacturers = new Set();
  const notFoundItems = [];

  for (const item of items) {
    const { id, category, quantity } = item;
    const qty = typeof quantity === 'number' && quantity > 0 ? quantity : 1;

    const component = findComponent(id, category);

    if (!component) {
      notFoundItems.push({ id, category });
      bomItems.push({
        id,
        category,
        name: '未找到',
        status: 'NOT_FOUND',
        quantity: qty,
        unit_price_usd: 0,
        subtotal_usd: 0
      });
      warnings.push(`零部件 ${id} (品类: ${category}) 未找到, 请检查 ID 和品类`);
      continue;
    }

    const price = parsePrice(component.price_range || component.price);
    const unitPrice = price ? price.mid : 0;
    const subtotal = unitPrice * qty;

    totalCostUSD += subtotal;
    totalModules += qty;

    if (component.manufacturer) {
      manufacturers.add(component.manufacturer);
    }

    bomItems.push({
      id: component.id,
      name: component.name,
      category: category,
      manufacturer: component.manufacturer || 'N/A',
      quantity: qty,
      unit_price_usd: unitPrice.toFixed(2),
      subtotal_usd: subtotal.toFixed(2),
      price_range: component.price_range || component.price || 'N/A',
      key_specs: getKeySpecs(component, category),
      status: 'OK'
    });
  }

  const totalCostCNY = totalCostUSD * USD_TO_CNY_RATE;

  // 生成供应商建议
  const supplierSuggestions = Array.from(manufacturers).map(m => getSupplierSuggestion(m));

  // 生成采购建议
  const procurementAdvice = [];
  if (manufacturers.size > 3) {
    procurementAdvice.push(`涉及 ${manufacturers.size} 个不同厂商, 建议优先选择有代理或本地仓的供应商以降低物流成本`);
  }
  if (totalCostUSD > 1000) {
    procurementAdvice.push(`总成本较高 ($${totalCostUSD.toFixed(2)}), 建议联系厂商或代理商获取批量折扣`);
  }
  if (notFoundItems.length > 0) {
    procurementAdvice.push(`${notFoundItems.length} 个零部件未找到, 请核实后补充`);
  }
  if (procurementAdvice.length === 0) {
    procurementAdvice.push('建议从官方授权渠道采购以确保正品和售后保障');
  }

  return {
    project_name,
    generated_at: new Date().toISOString(),
    summary: {
      total_cost_usd: parseFloat(totalCostUSD.toFixed(2)),
      total_cost_cny: parseFloat(totalCostCNY.toFixed(2)),
      total_modules: totalModules,
      item_count: bomItems.length,
      found_count: bomItems.filter(i => i.status === 'OK').length,
      not_found_count: notFoundItems.length,
      manufacturer_count: manufacturers.size
    },
    items: bomItems,
    supplier_suggestions: supplierSuggestions,
    procurement_advice: procurementAdvice,
    warnings: warnings.length > 0 ? warnings : undefined,
    cost_breakdown: {
      currency_note: '价格基于数据中的 price_range 中值估算, 实际价格以供应商报价为准',
      usd_to_cny_rate: USD_TO_CNY_RATE
    }
  };
}

// ============================================================
// MCP Server 定义
// ============================================================

const server = new Server(
  {
    name: 'roboparts-mcp-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// ============================================================
// 工具定义 (ListTools)
// ============================================================

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'search_components',
      description: '搜索机器人零部件，支持按品类、关键词、规格筛选。返回匹配的零部件列表（id, name, category, manufacturer, key_specs）。',
      inputSchema: {
        type: 'object',
        properties: {
          category: {
            type: 'string',
            description: '品类: actuators(执行器) / sensors(传感器) / chips(芯片) / protocols(通信协议) / platforms(机器人平台) / llms(大语言模型) / interfaces(接口)',
            enum: ['actuators', 'sensors', 'chips', 'protocols', 'platforms', 'llms', 'interfaces', 'flexible_actuators', 'robot_ai_models', 'data_acquisition']
          },
          keyword: {
            type: 'string',
            description: '搜索关键词，匹配名称、厂商、类型、描述等字段'
          },
          limit: {
            type: 'number',
            description: '返回数量限制，默认10',
            default: 10
          }
        }
      }
    },
    {
      name: 'get_component_detail',
      description: '获取单个零部件的详细信息，返回完整规格数据。',
      inputSchema: {
        type: 'object',
        properties: {
          id: {
            type: 'string',
            description: '零部件ID，如 "ACT-001"、"CHIP-001"、"SENS-001"'
          },
          category: {
            type: 'string',
            description: '品类: actuators / sensors / chips / protocols / platforms / llms / interfaces',
            enum: ['actuators', 'sensors', 'chips', 'protocols', 'platforms', 'llms', 'interfaces', 'flexible_actuators', 'robot_ai_models', 'data_acquisition']
          }
        },
        required: ['id', 'category']
      }
    },
    {
      name: 'check_compatibility',
      description: '检查两个零部件的兼容性，基于协议、接口、电压等维度。兼容性检查规则：执行器+芯片(协议匹配+电压范围)、芯片+传感器(接口兼容)、协议+接口(物理层兼容)、通用检查(应用场景+ROS2支持)。',
      inputSchema: {
        type: 'object',
        properties: {
          component1_id: {
            type: 'string',
            description: '零件1 ID'
          },
          component1_category: {
            type: 'string',
            description: '零件1品类',
            enum: ['actuators', 'sensors', 'chips', 'protocols', 'platforms', 'llms', 'interfaces', 'flexible_actuators', 'robot_ai_models', 'data_acquisition']
          },
          component2_id: {
            type: 'string',
            description: '零件2 ID'
          },
          component2_category: {
            type: 'string',
            description: '零件2品类',
            enum: ['actuators', 'sensors', 'chips', 'protocols', 'platforms', 'llms', 'interfaces', 'flexible_actuators', 'robot_ai_models', 'data_acquisition']
          }
        },
        required: ['component1_id', 'component1_category', 'component2_id', 'component2_category']
      }
    },
    {
      name: 'recommend_for_application',
      description: '根据应用场景推荐零部件组合。基于应用场景(humanoid/quadruped/robot_arm/amr/industrial)和预算，推荐最优零部件组合（执行器、传感器、芯片、控制器各自top推荐）。',
      inputSchema: {
        type: 'object',
        properties: {
          application: {
            type: 'string',
            description: '应用场景',
            enum: ['humanoid', 'quadruped', 'robot_arm', 'amr', 'industrial']
          },
          budget: {
            type: 'number',
            description: '预算上限（CNY 人民币）'
          },
          count: {
            type: 'number',
            description: '每个品类推荐数量，默认3',
            default: 3
          }
        },
        required: ['application']
      }
    },
    {
      name: 'export_bom',
      description: '从选定的零部件列表导出BOM（Bill of Materials）清单。计算总成本（USD+CNY），提供供应商建议和采购建议。',
      inputSchema: {
        type: 'object',
        properties: {
          project_name: {
            type: 'string',
            description: '项目名称'
          },
          items: {
            type: 'array',
            description: '零部件列表',
            items: {
              type: 'object',
              properties: {
                id: {
                  type: 'string',
                  description: '零部件ID'
                },
                category: {
                  type: 'string',
                  description: '品类',
                  enum: ['actuators', 'sensors', 'chips', 'protocols', 'platforms', 'llms', 'interfaces', 'flexible_actuators', 'robot_ai_models', 'data_acquisition']
                },
                quantity: {
                  type: 'number',
                  description: '数量',
                  default: 1
                }
              },
              required: ['id', 'category']
            }
          }
        },
        required: ['project_name', 'items']
      }
    }
  ]
}));

// ============================================================
// 工具调用处理 (CallTool)
// ============================================================

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  let result;

  try {
    switch (name) {
      case 'search_components':
        result = searchComponents(args || {});
        break;

      case 'get_component_detail':
        result = getComponentDetail(args || {});
        break;

      case 'check_compatibility':
        result = checkCompatibility(args || {});
        break;

      case 'recommend_for_application':
        result = recommendForApplication(args || {});
        break;

      case 'export_bom':
        result = exportBom(args || {});
        break;

      default:
        throw new Error(`未知工具: ${name}`);
    }

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
  } catch (error) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: `工具执行错误: ${name}`,
            message: error.message,
            arguments: args
          }, null, 2)
        }
      ],
      isError: true
    };
  }
});

// ============================================================
// 启动 Server
// ============================================================

async function main() {
  // 先备好数据再对外提供服务：连不上数据源就直接失败退出，
  // 而不是连上 stdio 之后对每个查询都回「没找到」。
  await preloadAll();
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error) => {
  console.error('RoboParts MCP Server 启动失败:', error);
  process.exit(1);
});
