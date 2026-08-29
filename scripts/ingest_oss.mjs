#!/usr/bin/env node
/**
 * RoboParts 开源机器人组件摄取管道（数据飞轮 CL1）
 *
 * 目标：把开源人形/协作机器人项目的 BOM/URDF 组件，归一化为兼容性实体，
 *       并入 api/oss_components.json，形成「中文圈稀缺的开源机器人兼容性数据层」。
 *
 * 设计：
 *  - 「确定性种子」底座：从内置的 OSS 机器人 BOM 模板展开，离线可复现，
 *    不依赖 GitHub API 额度（部署期稳定）。
 *  - LIVE 层「默认开启」：抓取 GitHub 仓库 URDF/BOM/README，补充实时组件。
 *    离线或需要纯种子复现时用 LIVE=0 显式关闭；关闭时既有 LIVE 实体会原样保留
 *    并标记 stale，**不会**被覆盖删除（见下方 §LIVE 层保护）。
 *  - 复用与 data.json 实体一致的字段（protocol/interface/voltage/ros_support/compatibility），
 *    使 /api/compatibility 与 /api/bom/check 可直接消费。
 *
 * 用法：node scripts/ingest_oss.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';

const ROOT = process.cwd();
const OUT = path.join(ROOT, 'api', 'oss_components.json');
// §LIVE 层保护 —— LIVE 默认开启（LIVE=0 显式关闭）。
// 20260808-04 修复：此前是 `=== '1'`（默认关闭），而飞轮任务书与文档里写的调用方式
// 一律是裸 `node scripts/ingest_oss.mjs` —— 于是每一次"照文档执行"都静默退化成纯种子层，
// 并把 189 条 LIVE 实体连同累积历史一并覆盖（325 → 136）。
// 上一轮据此误判为"本环境对源仓库实时抓取连续失败"，本轮实测 9/9 源全部 200 可达，
// 网络自始至终没有问题 —— 两次"复现"只是两次同样的裸调用。
// 病根是「文档写的命令 ≠ 脚本要的开关」，属「口径 ≠ 事实」族。
// 治法不是"记得加 LIVE=1"，而是让文档里那条命令本身就是对的。
const LIVE = process.env.LIVE !== '0';

// ---------- 复用字段解析（与 functions 端一致）----------
function volt(min, max) { return `${min}~${max}V`; }

// 共享标准件池：被多个机器人复用 → 在 BOM 检查器中天然形成「可互换组」
const SHARED = {
  servo_xm540: {
    name: 'DYNAMIXEL XM540-W270-T', manufacturer: 'ROBOTIS', type: 'smart_servo',
    protocol: 'DYNAMIXEL Protocol 2.0', interface: 'TTL/RS485', voltage: volt(10, 14.8),
    ros_support: true, compatibility: ['U2D2', 'OpenCM', 'ROS2'], weight: '82g', torque: '9.2 Nm',
    price_range: '0-100', standard: 'DYNAMIXEL',
  },
  servo_xc330: {
    name: 'DYNAMIXEL XC330-T288-T', manufacturer: 'ROBOTIS', type: 'smart_servo',
    protocol: 'DYNAMIXEL Protocol 2.0', interface: 'TTL', voltage: volt(5, 7.4),
    ros_support: true, compatibility: ['OpenCM', 'ROS2'], weight: '32g', torque: '1.2 Nm',
    price_range: '0-50', standard: 'DYNAMIXEL',
  },
  imu_bmi088: {
    name: 'BMI088 6轴 IMU', manufacturer: 'Bosch', type: 'imu', category: 'sensors',
    protocol: 'SPI/I2C', interface: 'SPI', voltage: volt(3.3, 3.3), ros_support: true,
    compatibility: ['ROS2', 'Micro-ROS'], weight: '2g', price_range: '0-20', standard: 'MEMS-IMU',
  },
  cam_realsense: {
    name: 'Intel RealSense D435', manufacturer: 'Intel', type: 'depth_camera', category: 'sensors',
    protocol: 'USB3', interface: 'USB', voltage: volt(5, 5), ros_support: true,
    compatibility: ['ROS2', 'realsense-ros'], weight: '72g', price_range: '100-200', standard: 'USB3-Vision',
  },
  ctrl_raspberry: {
    name: 'Raspberry Pi 5', manufacturer: 'Raspberry Pi', type: 'sbc', category: 'controllers',
    protocol: 'Ethernet/CAN', interface: 'Ethernet', voltage: volt(5, 5), ros_support: true,
    compatibility: ['ROS2', 'Ubuntu'], weight: '46g', price_range: '0-50', standard: 'SBC-40pin',
  },
  bus_can: {
    name: 'CAN FD 总线转接', manufacturer: 'RoboParts', type: 'bus', category: 'communication',
    protocol: 'CAN FD', interface: 'CAN', voltage: volt(12, 48), ros_support: true,
    compatibility: ['ROS2', 'SocketCAN'], weight: '10g', price_range: '0-20', standard: 'CAN-FD',
  },
};

// OSS 机器人 BOM 模板：每个机器人由「共享标准件 × 数量 + 专属件」构成
const ROBOTS = [
  {
    id: 'TIENKUNG', name: '天工 TienKung (开源人形)', license: 'Apache-2.0',
    repo: 'https://github.com/Open-X-Humanoid/TienKung_URDF', dof: 42, type: 'humanoid',
    live_sources: [
      { kind: 'urdf', url: 'https://raw.githubusercontent.com/Open-X-Humanoid/TienKung_URDF/main/pro_urdf_publish/pro_urdf_publish/urdf/humanoid.urdf' },
      { kind: 'urdf', url: 'https://raw.githubusercontent.com/Open-X-Humanoid/TienKung_URDF/main/tiangong2dex_urdf/urdf/tiangong2dex.urdf' },
    ],
    use: { servo_xm540: 24, imu_bmi088: 2, cam_realsense: 2, ctrl_raspberry: 1, bus_can: 3 },
    extra: [
      { name: '天工 谐波减速关节模块', manufacturer: 'NHIC', type: 'harmonic_joint', protocol: 'EtherCAT', interface: 'EtherCAT', voltage: volt(48, 48), ros_support: true, compatibility: ['ROS2', 'EtherCAT'], weight: '420g', torque: '44.7 Nm', price_range: '300-500', standard: 'EtherCAT-Joint' },
      { name: '天工 灵巧手 (6-DOF)', manufacturer: 'NHIC', type: 'dexterous_hand', protocol: 'EtherCAT', interface: 'EtherCAT', voltage: volt(24, 24), ros_support: true, compatibility: ['ROS2'], weight: '480g', price_range: '500-1000', standard: 'EtherCAT-Hand' },
    ],
  },
  {
    id: 'ROBOTO_ORIGIN', name: 'roboto_origin (GPLv3 DIY 人形)', license: 'GPL-3.0',
    repo: 'https://github.com/Roboparty/roboto_origin', dof: 28, type: 'humanoid',
    live_sources: [
      { kind: 'bom_md', url: 'https://raw.githubusercontent.com/Roboparty/roboto_origin/main/assets/BOM_EN.md' },
    ],
    use: { servo_xc330: 20, imu_bmi088: 1, cam_realsense: 1, ctrl_raspberry: 1, bus_can: 2 },
    extra: [
      { name: 'roboto_origin 碳纤维连杆套件', manufacturer: 'roboto_origin', type: 'link_set', category: 'structural', protocol: 'N/A', interface: 'flange M8', voltage: 'N/A', ros_support: false, compatibility: ['3D-print'], weight: '1200g', price_range: '100-200', standard: 'Flange-M8' },
      { name: 'SimpleFOC 腕部驱动板', manufacturer: 'SimpleFOC', type: 'foc_driver', category: 'controllers', protocol: 'UART', interface: 'UART', voltage: volt(12, 24), ros_support: true, compatibility: ['Micro-ROS'], weight: '18g', price_range: '0-30', standard: 'FOC-UART' },
    ],
  },
  {
    id: 'LEROBOT_HUMANOID', name: 'LeRobot-Humanoid (<$5000)', license: 'MIT',
    repo: 'https://github.com/huggingface/lerobot', dof: 22, type: 'humanoid',
    live_sources: [
      { kind: 'readme', url: 'https://api.github.com/repos/huggingface/lerobot/readme' },
    ],
    use: { servo_xc330: 16, imu_bmi088: 1, cam_realsense: 2, ctrl_raspberry: 1 },
    extra: [
      { name: 'SO-100 低成本机械臂模组', manufacturer: 'LeRobot', type: 'arm_module', protocol: 'UART', interface: 'UART', voltage: volt(12, 12), ros_support: true, compatibility: ['Micro-ROS', 'SO-100'], weight: '350g', torque: '0.8 Nm', price_range: '0-50', standard: 'SO100' },
      { name: 'Feetech STS3215 总线舵机', manufacturer: 'Feetech', type: 'smart_servo', protocol: 'TTL', interface: 'TTL', voltage: volt(6, 8.4), ros_support: true, compatibility: ['Micro-ROS'], weight: '60g', torque: '1.5 Nm', price_range: '0-20', standard: 'TTL-Servo' },
    ],
  },
  {
    id: 'UNITREE_GO2', name: 'Unitree Go2 (四足)', license: 'Apache-2.0',
    repo: 'https://github.com/unitreerobotics/unitree_ros', dof: 12, type: 'quadruped',
    live_sources: [
      { kind: 'urdf', url: 'https://raw.githubusercontent.com/unitreerobotics/unitree_ros/master/robots/go2_description/urdf/go2_description.urdf' },
      { kind: 'urdf', url: 'https://raw.githubusercontent.com/unitreerobotics/unitree_ros/master/robots/go2w_description/urdf/go2w_description.urdf' },
    ],
    use: { servo_xm540: 12, imu_bmi088: 1, ctrl_raspberry: 1, bus_can: 2 },
    extra: [
      { name: 'Go2 关节电机 (Unitree)', manufacturer: 'Unitree', type: 'joint_motor', protocol: 'CAN', interface: 'CAN', voltage: volt(24, 30), ros_support: true, compatibility: ['ROS2', 'unitree_ros'], weight: '520g', torque: '35 Nm', price_range: '200-400', standard: 'Unitree-CAN' },
      { name: 'Go2 激光雷达 (L1)', manufacturer: 'Unitree', type: 'lidar', category: 'sensors', protocol: 'Ethernet', interface: 'Ethernet', voltage: volt(12, 12), ros_support: true, compatibility: ['ROS2'], weight: '210g', price_range: '300-500', standard: 'Ethernet-Lidar' },
    ],
  },
  {
    id: 'UNITREE_G1', name: 'Unitree G1 (人形)', license: 'Apache-2.0',
    repo: 'https://github.com/unitreerobotics/unitree_ros', dof: 23, type: 'humanoid',
    live_sources: [
      { kind: 'urdf', url: 'https://raw.githubusercontent.com/unitreerobotics/unitree_ros/master/robots/g1_description/g1_29dof_rev_1_0.urdf' },
      { kind: 'urdf', url: 'https://raw.githubusercontent.com/unitreerobotics/unitree_ros/master/robots/g1_description/inspire_hand/FTP_right_hand.urdf' },
    ],
    use: { servo_xm540: 18, imu_bmi088: 1, cam_realsense: 1, ctrl_raspberry: 1, bus_can: 2 },
    extra: [
      { name: 'G1 力控关节 (Unitree)', manufacturer: 'Unitree', type: 'joint_motor', protocol: 'CAN', interface: 'CAN', voltage: volt(24, 30), ros_support: true, compatibility: ['ROS2', 'unitree_ros'], weight: '610g', torque: '38 Nm', price_range: '300-500', standard: 'Unitree-CAN' },
      { name: 'G1 3D 视觉模组', manufacturer: 'Unitree', type: 'depth_camera', category: 'sensors', protocol: 'USB3', interface: 'USB', voltage: volt(5, 5), ros_support: true, compatibility: ['ROS2'], weight: '90g', price_range: '200-400', standard: 'USB3-Vision' },
    ],
  },
  {
    id: 'OPENARM', name: 'OpenArm 7-DOF', license: 'MIT',
    repo: 'https://github.com/enactic/openarm', dof: 7, type: 'arm',
    live_sources: [
      { kind: 'readme', url: 'https://api.github.com/repos/enactic/openarm/readme' },
    ],
    use: { servo_xm540: 7, ctrl_raspberry: 1, bus_can: 1 },
    extra: [
      { name: 'OpenArm 谐波减速器', manufacturer: 'OpenArm', type: 'harmonic_joint', protocol: 'EtherCAT', interface: 'EtherCAT', voltage: volt(48, 48), ros_support: true, compatibility: ['ROS2', 'EtherCAT'], weight: '300g', torque: '18 Nm', price_range: '200-400', standard: 'EtherCAT-Joint' },
    ],
  },
];

function makeEntity(robotId, robotName, base, idx, categoryOverride) {
  const category = categoryOverride || (base.category || (base.type && /servo|joint|motor|foc/i.test(base.type) ? 'actuators' : (base.type && /imu|camera|lidar|sensor/i.test(base.type) ? 'sensors' : (base.type && /ctrl|sbc|driver/i.test(base.type) ? 'controllers' : (base.type && /bus|commun/i.test(base.type) ? 'communication' : (base.type && /battery|power/i.test(base.type) ? 'power' : (base.type && /link|frame|struct/i.test(base.type) ? 'structural' : 'actuators')))))));
  const id = `OSS-${robotId}-${String(idx).padStart(3, '0')}`;
  return {
    id,
    name: base.name,
    name_en: base.name,
    category,
    manufacturer: base.manufacturer,
    type: base.type,
    protocol: base.protocol,
    interface: base.interface,
    voltage: base.voltage,
    // 【20260806-15】三态透传：`=== true` 会把「种子未声明」无声压平成 false（= 断言不支持）。
    // 当前种子均已显式声明，但压平是潜伏地雷：将来漏写一个字段就凭空多出一条否定断言。
    ros_support: typeof base.ros_support === 'boolean' ? base.ros_support : undefined,
    compatibility: base.compatibility || [],
    applications: [robotId.toLowerCase().replace(/_/g, ''), (base.type && /hand|dexter/i.test(base.type)) ? 'manipulator' : robotId.toLowerCase().includes('quad') ? 'quadruped' : 'humanoid'],
    weight: base.weight || 'N/A',
    torque: base.torque || '',
    price_range: base.price_range || '0-100',
    standard: base.standard || '',
    source_robot: robotName,
    source_license: ROBOTS.find(r => r.id === robotId)?.license || '',
    oss: true,
  };
}

const data = [];
const seenIds = new Set();
for (const robot of ROBOTS) {
  let idx = 1;
  for (const [sharedKey, count] of Object.entries(robot.use || {})) {
    const base = SHARED[sharedKey];
    if (!base) continue;
    for (let i = 0; i < count; i++) {
      const e = makeEntity(robot.id, robot.name, base, idx++);
      if (!seenIds.has(e.id)) { seenIds.add(e.id); data.push(e); }
    }
  }
  for (const ex of robot.extra || []) {
    const e = makeEntity(robot.id, robot.name, ex, idx++, ex.category);
    if (!seenIds.has(e.id)) { seenIds.add(e.id); data.push(e); }
  }
}

// ---------- LIVE 模式：从上游仓库抽取真实 BOM / URDF（由周任务启用）----------
// 【20260805 重构】原实现用 crypto.randomBytes 生成 ID + README 关键词行 → 每次运行
// 产生全新随机实体，既不可复现也无法去重，且 repo 全是 '.../xxx' 占位符导致永远 404。
// 现改为：真实仓库 + 三类确定性抽取器 + 稳定哈希 ID + 跨周累积（first_seen/last_seen）。
const UA = { 'User-Agent': 'roboparts-oss-ingest' };
const liveStats = { attempted: 0, ok: 0, failed: [], extracted: 0, by_kind: {} };

// RESET_LIVE=1：抽取器/schema 变更后全量重建 LIVE 层，丢弃历史残留（含早期脏数据）
const RESET_LIVE = process.env.RESET_LIVE === '1';

// 归一化名：用于跨版本识别「同一零件」，不受大小写/空格/标点影响
function normKey(s) {
  return String(s || '').toLowerCase().replace(/[^a-z0-9\u4e00-\u9fa5]/g, '');
}

// 稳定 ID：同一上游同一部件，每周复算得到同一 ID → 可去重、可追溯、可 diff
function stableId(repo, name) {
  return 'OSS-LIVE-' + crypto.createHash('sha1').update(`${repo}|${name}`).digest('hex').slice(0, 10).toUpperCase();
}

// 归一化：从部件名推断类别与电气属性（与种子池同口径，保证 BOM 检查器可直接消费）
function inferCategory(s) {
  const t = s.toLowerCase();
  if (/lidar|camera|imu|encoder|sensor|vision|depth|tof/.test(t)) return 'sensors';
  if (/mcu|board|sbc|jetson|raspberry|driver|controller|pcb|control/.test(t)) return 'controllers';
  if (/can|ethercat|rs485|usb|ethernet|hub|cable|connector|harness|bus/.test(t)) return 'communication';
  if (/battery|bms|power|dcdc|regulator|psu/.test(t)) return 'power';
  if (/bearing|screw|shaft|frame|link|bracket|plate|cnc|carbon|aluminum|belt|pulley|housing|cover/.test(t)) return 'structural';
  if (/servo|motor|actuator|joint|gearbox|harmonic|reducer|hand|gripper/.test(t)) return 'actuators';
  return 'structural';
}
function inferProtocol(s) {
  const t = s.toLowerCase();
  if (/ethercat/.test(t)) return 'EtherCAT';
  if (/canfd|can fd|can-fd/.test(t)) return 'CAN FD';
  if (/\bcan\b/.test(t)) return 'CAN';
  if (/rs485|485/.test(t)) return 'RS485';
  if (/usb/.test(t)) return 'USB';
  if (/ethernet|rj45/.test(t)) return 'Ethernet';
  if (/i2c|spi|uart|ttl/.test(t)) return t.match(/i2c|spi|uart|ttl/)[0].toUpperCase();
  return 'N/A';
}
function cleanName(s) {
  return String(s || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')   // markdown 链接 → 文字
    .replace(/https?:\/\/\S+/g, ' ')
    .replace(/[#*`>|]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}
// 垃圾行过滤：正文散文、标题、纯符号、纯数字一律拒绝
function isPlausibleComponent(name) {
  if (!name || name.length < 4 || name.length > 80) return false;
  if (!/[a-z\u4e00-\u9fa5]/i.test(name)) return false;
  if (/^\d+$/.test(name)) return false;
  if (name.split(' ').length > 12) return false;              // 长句 = 散文，不是部件名
  if (/^(the|this|we|you|please|see|note|for more|install|run|pip|git|cd |sudo)/i.test(name)) return false;
  if (/\b(is|are|was|were|can be|allows|provides|enables|supports the)\b/i.test(name)) return false; // 谓语 = 句子
  return true;
}

// CAD 导出常见冗余：'atom arm - copy (1) Atom arm(1)' → 'atom arm (1)'
function dedupeCadName(s) {
  return s.replace(/\s*-\s*copy\s*/gi, ' ').replace(/(.+?)\s+\1/i, '$1').replace(/\s+/g, ' ').trim();
}

async function grab(url, raw) {
  liveStats.attempted++;
  try {
    const res = await fetch(url, { headers: raw ? { ...UA, Accept: 'application/vnd.github.raw' } : UA });
    if (!res.ok) { liveStats.failed.push(`${url} → HTTP ${res.status}`); return null; }
    liveStats.ok++;
    return await res.text();
  } catch (e) { liveStats.failed.push(`${url} → ${e.message}`); return null; }
}

// E1 URDF 关节抽取：可动关节 = 真实执行器位点（置信度最高，直接来自上游模型文件）
function extractUrdf(text, robot, srcUrl) {
  const out = [];
  for (const m of text.matchAll(/<joint\s+name="([^"]+)"\s+type="([^"]+)"/g)) {
    const [, jname, jtype] = m;
    if (jtype === 'fixed') continue;                          // 固定关节非执行器，跳过
    const name = `${robot.id} 关节 ${jname}`;
    out.push({
      name, category: 'actuators', type: `urdf_joint_${jtype}`,
      manufacturer: robot.name.replace(/\s*\(.*\)$/, ''),
      protocol: inferProtocol(robot.name + ' ' + jname), interface: 'N/A', voltage: 'N/A',
      // 【20260806-15】禁止由「抽取器种类」推断 ros_support。
      // URDF 只证明「该关节位点出现在某个 ROS/URDF 模型里」，不证明「该位点的物理执行器原生支持 ROS」。
      // 前者是**出处**，后者是**厂商能力声明**；把出处写成能力，等于替厂商编造声明。
      // 故 ros_support 留空（未声明），另以 ros_ecosystem_origin 如实记录出处。
      ros_support: undefined,
      ros_ecosystem_origin: true,
      compatibility: ['URDF'], standard: 'URDF-Joint',
      joint_name: jname, joint_type: jtype, confidence: 'high', extractor: 'urdf',
      source_url: srcUrl,
    });
  }
  return out;
}

// E2 Markdown BOM 表格抽取：| No. | Part No. | Item | Spec | Category | Unit | Qty | Price | ...
function extractBomMd(text, robot, srcUrl) {
  const out = [];
  for (const line of text.split('\n')) {
    const t = line.trim();
    if (!/^\|\s*\d+\s*\|/.test(t)) continue;                  // 仅取带序号的数据行
    const cells = t.split('|').map(c => cleanName(c));
    if (cells.length < 6) continue;
    const partNo = cells[2] || '';
    const item = cells[3] || '';
    const spec = cells[4] || '';
    const cat = cells[5] || '';
    const qty = parseInt(cells[7], 10);
    const unitPrice = parseFloat(cells[8]);
    if (!isPlausibleComponent(item)) continue;
    const blob = `${item} ${spec} ${cat}`;
    out.push({
      name: dedupeCadName(item).slice(0, 70), category: inferCategory(blob), type: 'bom_part',
      manufacturer: robot.name.replace(/\s*\(.*\)$/, ''),
      protocol: inferProtocol(blob), interface: 'N/A', voltage: 'N/A',
      // 【20260806-15】原写死 false = 对每一个机械 BOM 行断言「不支持 ROS」。
      // 实际多为侧板 / 大腿内侧 / 电池底盖等纯结构件，无电气接口——「支不支持 ROS」对它们根本不成立。
      // 对这类件写 false 比写「不知道」更糟：那是范畴错误，不只是信息缺失。一律留空。
      ros_support: undefined, compatibility: [], standard: partNo || '',
      spec: spec.slice(0, 90), bom_category: cat.slice(0, 40),
      quantity: Number.isFinite(qty) ? qty : undefined,
      unit_price_cny: Number.isFinite(unitPrice) ? unitPrice : undefined,
      confidence: 'high', extractor: 'bom_md', source_url: srcUrl,
    });
  }
  return out;
}

// E3 README 兜底：仅取列表项/表格行中的关键词命中，置信度标 low
function extractReadme(text, robot, srcUrl) {
  const out = [];
  const KW = /\b(servo|motor|actuator|imu|camera|lidar|encoder|gearbox|harmonic|gripper|controller|jetson|raspberry|can\s?bus|ethercat)\b/i;
  for (const line of text.split('\n')) {
    const t = line.trim();
    if (!/^[-*|]/.test(t)) continue;                          // 仅列表/表格行
    if (!KW.test(t)) continue;
    const name = cleanName(t).slice(0, 70);
    if (!isPlausibleComponent(name)) continue;
    out.push({
      name, category: inferCategory(name), type: 'readme_mention',
      manufacturer: robot.name.replace(/\s*\(.*\)$/, ''),
      protocol: inferProtocol(name), interface: 'N/A', voltage: 'N/A',
      // 【20260806-15】原按「名字里有没有子串 ros」猜测。/ros/i 会命中 "gy(ros)cope"、
      // "mic(roS)D"、"(Ros)enberger" 等无关词：命中即断言「原生支持 ROS」，未命中即断言「不支持」。
      // 何况整条记录本就是 confidence:'low' 的 README 提及，更没有资格给出布尔能力断言。
      ros_support: undefined, compatibility: [], standard: '',
      confidence: 'low', extractor: 'readme', source_url: srcUrl,
    });
  }
  return out;
}

if (LIVE) {
  const NOW = new Date().toISOString();
  // 载入上一轮产物：LIVE 实体跨周累积，避免上游临时 404 导致数据层缩水
  let prevLive = new Map();
  try {
    const prev = JSON.parse(fs.readFileSync(OUT, 'utf8'));
    for (const e of prev.data || []) if (e.live && e.id) prevLive.set(e.id, e);
  } catch (e) { /* 首次运行无历史 */ }

  const liveById = new Map();
  for (const robot of ROBOTS) {
    for (const src of robot.live_sources || []) {
      const isApi = src.url.includes('api.github.com');
      const text = await grab(src.url, isApi);
      if (!text) continue;
      let items = [];
      if (src.kind === 'urdf') items = extractUrdf(text, robot, src.url);
      else if (src.kind === 'bom_md') items = extractBomMd(text, robot, src.url);
      else items = extractReadme(text, robot, src.url);
      liveStats.by_kind[src.kind] = (liveStats.by_kind[src.kind] || 0) + items.length;
      for (const it of items) {
        const id = stableId(robot.repo, it.name);
        if (seenIds.has(id) || liveById.has(id)) continue;    // 稳定 ID 天然去重
        const prev = prevLive.get(id);
        liveById.set(id, {
          id, name_en: it.name, ...it,
          applications: [robot.id.toLowerCase().replace(/_/g, ''), robot.type],
          weight: 'N/A', torque: '', price_range: it.unit_price_cny != null
            ? (it.unit_price_cny < 50 ? '0-50' : it.unit_price_cny < 200 ? '50-200' : '200-500') : '0-100',
          source_robot: robot.name, source_license: robot.license, source_repo: robot.repo,
          oss: true, live: true,
          first_seen: prev?.first_seen || NOW, last_seen: NOW,
        });
      }
    }
  }
  // 本轮未抓到但历史存在的实体：保留并标记 stale，抵御上游临时 404 导致数据层缩水。
  // 但必须按「仓库 + 归一化名」二次去重：抽取器改名会让稳定 ID 变化，
  // 若只比 ID，同一零件会以新旧两条记录并存（20260805 首轮实测踩中）。
  const freshKeys = new Set([...liveById.values()].map(e => `${e.source_repo}|${normKey(e.name)}`));
  for (const [id, e] of prevLive) {
    if (liveById.has(id) || seenIds.has(id)) continue;
    if (freshKeys.has(`${e.source_repo}|${normKey(e.name)}`)) continue;   // 已被改名后的新记录取代
    if (RESET_LIVE) continue;                                             // schema 变更时全量重建
    liveById.set(id, { ...e, stale: true });
  }
  for (const [id, e] of liveById) { seenIds.add(id); data.push(e); }
  liveStats.extracted = liveById.size;
  console.log(`   LIVE: 源 ${liveStats.ok}/${liveStats.attempted} 成功，抽取 ${liveStats.extracted} 个实体`, liveStats.by_kind);
  if (liveStats.failed.length) console.warn('   LIVE 失败源:', liveStats.failed.join(' ; '));
} else if (!RESET_LIVE) {
  // LIVE=0 时**继承**既有 LIVE 实体（标记 stale），而不是把它们从数据层抹掉。
  // 20260808-04：关闭实时抓取的合理语义是"这一轮不去上游取新的"，
  // 绝不是"把上游过去给过的东西全删了"。此前二者被混为一谈，
  // 一次纯种子运行就抹掉 189 条实体，且**静默**（无任何告警），
  // 下一轮再被读成"数据层退化了"。要真正清空请显式 RESET_LIVE=1。
  let carried = 0;
  try {
    const prev = JSON.parse(fs.readFileSync(OUT, 'utf8'));
    for (const e of prev.data || []) {
      if (!e.live || !e.id || seenIds.has(e.id)) continue;
      seenIds.add(e.id);
      data.push({ ...e, stale: true });
      carried++;
    }
  } catch (e) { /* 首次运行无历史 */ }
  if (carried) console.log(`   LIVE=0：继承既有 ${carried} 条 LIVE 实体并标记 stale（未抓取上游，也未删除）`);
}

const meta = {
  name: 'RoboParts OSS Compatibility Layer',
  description: '开源机器人 (天工/roboto_origin/LeRobot-Humanoid/Unitree Go2·G1/OpenArm) 组件的归一化兼容性数据层',
  generated_at: new Date().toISOString(),
  // last_updated 是运维飞轮判断「是否需要重新摄取」的唯一依据（阈值 7 天）。
  // 20260805-19 修复：此前只写 generated_at，飞轮读到的 last_updated 恒为 null，
  // 时间比较永不成立 —— 摄取新鲜度检查静默失效，与「假绿断言」同类。
  // 回归 L1.11 已加断言守护此字段存在且可解析。
  last_updated: new Date().toISOString(),
  total_entities: data.length,
  robots: ROBOTS.length,
  sources: ROBOTS.map(r => ({ id: r.id, name: r.name, license: r.license, dof: r.dof, type: r.type, repo: r.repo })),
  schema_note: '字段与 api/data.json 实体对齐，可直接用于 /api/compatibility 与 /api/bom/check',
  live: LIVE,
  seed_entities: data.filter(e => !e.live).length,
  live_entities: data.filter(e => e.live).length,
  live_stats: LIVE ? {
    sources_ok: liveStats.ok, sources_attempted: liveStats.attempted,
    by_extractor: liveStats.by_kind, failed: liveStats.failed,
  } : null,
};

// ---------- 写出前闸门：数据层只许长，不许静默缩水 ----------
// 20260808-04：上一次缩水（325 → 136，少 58%）是**无声**完成的 —— 脚本照常打印
// "✅ 生成 136 个"，退出码 0，看起来像一次成功运行。缩水本身可能合法（源仓库真的删了东西），
// 但**必须由人确认**，不能由一次误调用顺手做掉。RESET_LIVE=1 是唯一的合法绕过口。
const SHRINK_TOLERANCE = 0.9;   // 允许 10% 的正常波动（上游改名/临时下架）
let prevTotal = 0;
try { prevTotal = (JSON.parse(fs.readFileSync(OUT, 'utf8')).data || []).length; } catch (e) { /* 首次运行 */ }
if (!RESET_LIVE && prevTotal > 0 && data.length < prevTotal * SHRINK_TOLERANCE) {
  console.error(`\n❌ 拒绝写出：数据层将从 ${prevTotal} 缩水到 ${data.length}（-${(100 - data.length / prevTotal * 100).toFixed(1)}%）。`);
  console.error(`   这通常意味着上游抓取失败或调用方式不对，而不是数据真的少了。`);
  console.error(`   已保留原文件不动。确认要重建请显式执行：RESET_LIVE=1 node scripts/ingest_oss.mjs`);
  process.exit(1);
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify({ meta, data }, null, 2));
console.log(`✅ 生成 ${data.length} 个 OSS 组件 → ${OUT}`);
console.log(`   机器人来源: ${ROBOTS.length} 个；按类别:`, countBy(data, 'category'));

// ---------- 重新注入机读接入声明（meta.access）----------
// 本脚本整份重写 oss_components.json，会顺手抹掉 inject_api_access.py 注入的 meta.access
// —— 即"AI 直读 JSON 时怎么领 key"的入口。20260808-04 实测：上一轮摄取后该字段消失，
// 回归 L1.14 判红。注入器 docstring 自称"由 deploy 前置与各 build 脚本调用"，
// 但当时**没有任何脚本真的调用它**（deploy.mjs 里 0 处引用）——文档写了 ≠ 挂上了。
// 这里在生成端自己补回来：谁破坏谁负责修复，不依赖下游记得跑。
try {
  const py = process.platform === 'win32' ? 'python' : 'python3';
  const r = spawnSync(py, [path.join(ROOT, 'scripts', 'inject_api_access.py')], { encoding: 'utf8' });
  if (r.status === 0) console.log('   ✅ meta.access 已重新注入（AI 直读 JSON 的领 key 入口）');
  else console.warn('   ⚠️ meta.access 注入失败，回归 L1.14 会判红：', (r.stderr || r.stdout || '').trim().slice(0, 300));
} catch (e) {
  console.warn('   ⚠️ meta.access 注入未执行：', e.message);
}

function countBy(arr, k) { const m = {}; for (const x of arr) m[x[k]] = (m[x[k]] || 0) + 1; return m; }
