// ==========================================
// RoboLink - 机器人零件对接平台
// 数据层: 零件库、社区内容、STL设计、监控数据
// ==========================================

// ========== 零件数据库 ==========
const ROBOT_ARMS = [
  // === 工业协作臂 ===
  { id: 'dobot-magician', brand: 'DOBOT', model: 'Magician', type: '协作臂', flange: 'ISO 9409-50-4-M6', protocol: 'Modbus RTU', voltage: '24VDC', payload: '0.5kg', repeatability: '0.2mm' },
  { id: 'dobot-m1', brand: 'DOBOT', model: 'M1', type: '协作臂', flange: 'ISO 9409-50-4-M6', protocol: 'Modbus RTU/TCP', voltage: '24VDC', payload: '3kg', repeatability: '0.1mm' },
  { id: 'dobot-cr3', brand: 'DOBOT', model: 'CR3', type: '协作臂', flange: 'ISO 9409-50-4-M6', protocol: 'Modbus RTU/TCP', voltage: '48VDC', payload: '3kg', repeatability: '0.05mm' },
  { id: 'ur3e', brand: 'Universal Robots', model: 'UR3e', type: '协作臂', flange: 'ISO 9409-50-4-M6', protocol: 'URScript/Modbus', voltage: '24VDC', payload: '3kg', repeatability: '0.1mm' },
  { id: 'ur5e', brand: 'Universal Robots', model: 'UR5e', type: '协作臂', flange: 'ISO 9409-50-4-M6', protocol: 'URScript/Modbus', voltage: '24VDC', payload: '5kg', repeatability: '0.1mm' },
  { id: 'franka-panda', brand: 'Franka Emika', model: 'Panda', type: '协作臂', flange: 'ISO 9409-50-4-M6', protocol: 'libfranka/ROS2', voltage: '48VDC', payload: '3kg', repeatability: '0.1mm' },
  { id: 'hiwin-6f', brand: 'HIWIN', model: 'RA610-6F', type: '协作臂', flange: 'ISO 9409-50-4-M6', protocol: 'Modbus RTU', voltage: '24VDC', payload: '6kg', repeatability: '0.1mm' },
  { id: 'auber-06', brand: 'AUBO', model: 'i06', type: '协作臂', flange: 'ISO 9409-50-4-M6', protocol: 'Modbus RTU/TCP', voltage: '24VDC', payload: '6kg', repeatability: '0.05mm' },
  // === 桌面/创客臂 ===
  { id: 'uarm-metal', brand: 'uArm', model: 'Swift Pro Metal', type: '桌面臂', flange: '自定义 M4x4', protocol: 'UART/I2C', voltage: '5-12VDC', payload: '0.5kg', repeatability: '0.5mm' },
  { id: 'lofi-robot', brand: 'LoFi Robot', model: 'MK2', type: '开源臂', flange: '自定义卡扣', protocol: 'PWM/Servo', voltage: '6-12VDC', payload: '0.3kg', repeatability: '1mm' },
  { id: 'elephant-06', brand: 'Elephant Robotics', model: 'myCobot 280', type: '桌面臂', flange: '自定义 M4', protocol: 'UART/I2C', voltage: '12VDC', payload: '0.25kg', repeatability: '1mm' },
  { id: 'elephant-320', brand: 'Elephant Robotics', model: 'myCobot 320', type: '桌面臂', flange: 'ISO 9409-40-4-M4', protocol: 'UART/I2C', voltage: '12VDC', payload: '0.5kg', repeatability: '0.5mm' },
  { id: 'elephant-630', brand: 'Elephant Robotics', model: 'myCobot 630', type: '桌面臂', flange: 'ISO 9409-50-4-M6', protocol: 'Modbus RTU/TCP', voltage: '24VDC', payload: '2kg', repeatability: '0.2mm' },
  { id: 'seeed-rebot', brand: '矽递科技', model: 'reBot-DevArm', type: '开源臂', flange: '自定义 M4x4', protocol: 'UART/I2C', voltage: '12VDC', payload: '0.5kg', repeatability: '0.5mm' },
  { id: 'so-arm100', brand: 'SO-ARM', model: 'SO-ARM100', type: '开源臂', flange: '自定义卡扣', protocol: 'UART/ROS2', voltage: '12VDC', payload: '0.3kg', repeatability: '0.8mm' },
  { id: 'cr4-robot', brand: 'CRobot', model: 'CR4', type: '桌面臂', flange: '自定义 M4', protocol: 'UART/PWM', voltage: '12VDC', payload: '0.3kg', repeatability: '1mm' },
  { id: 'dobot-lite', brand: 'DOBOT', model: 'Lite 6', type: '桌面臂', flange: '自定义 M4', protocol: 'UART/Modbus', voltage: '24VDC', payload: '0.5kg', repeatability: '0.2mm' },
];

const END_EFFECTORS = [
  // === 进口工业夹爪 ===
  { id: 'robotiq-2f85', brand: 'Robotiq', model: '2F-85', category: 'electric-gripper', type: '电动夹爪', force: '5-85N', stroke: '0-85mm', voltage: '24VDC', protocol: 'Modbus RTU', flange: 'ISO 9409-50-4-M6', weight: '0.95kg', price: 8500, repeatability: '0.02mm' },
  { id: 'robotiq-2f140', brand: 'Robotiq', model: '2F-140', category: 'electric-gripper', type: '电动夹爪', force: '5-140N', stroke: '0-140mm', voltage: '24VDC', protocol: 'Modbus RTU', flange: 'ISO 9409-50-4-M6', weight: '1.1kg', price: 9200, repeatability: '0.02mm' },
  { id: 'robotiq-hande', brand: 'Robotiq', model: 'Hand-E', category: 'electric-gripper', type: '电动夹爪', force: '2.5-25N', stroke: '0-50mm', voltage: '24VDC', protocol: 'Modbus RTU', flange: 'ISO 9409-40-4-M4', weight: '0.62kg', price: 7800, repeatability: '0.02mm' },
  { id: 'onrobot-rg2', brand: 'OnRobot', model: 'RG2', category: 'electric-gripper', type: '电动夹爪', force: '5-100N', stroke: '0-50mm', voltage: '24VDC', protocol: 'Modbus RTU', flange: 'ISO 9409-50-4-M6', weight: '0.85kg', price: 6800, repeatability: '0.02mm' },
  { id: 'onrobot-rg6', brand: 'OnRobot', model: 'RG6', category: 'electric-gripper', type: '电动夹爪', force: '5-150N', stroke: '0-60mm', voltage: '24VDC', protocol: 'Modbus RTU', flange: 'ISO 9409-50-4-M6', weight: '1.0kg', price: 7500, repeatability: '0.02mm' },
  { id: 'onrobot-vgc10', brand: 'OnRobot', model: 'VGC10', category: 'vacuum', type: '真空吸盘', force: '5-20N', stroke: 'N/A', voltage: '24VDC', protocol: 'Modbus RTU', flange: 'ISO 9409-50-4-M6', weight: '0.48kg', price: 5600, repeatability: '0.5mm' },
  { id: 'schunk-egp40', brand: 'Schunk', model: 'EGP-40', category: 'electric-gripper', type: '电动夹爪', force: '1-40N', stroke: '0-40mm', voltage: '24VDC', protocol: 'Modbus RTU/Profibus', flange: 'ISO 9409-50-4-M6', weight: '0.8kg', price: 12000, repeatability: '0.01mm' },
  { id: 'festo-dhg', brand: 'Festo', model: 'DHGP', category: 'electric-gripper', type: '电动夹爪', force: '5-70N', stroke: '0-40mm', voltage: '24VDC', protocol: 'Modbus RTU/IO-Link', flange: 'ISO 9409-50-4-M6', weight: '0.65kg', price: 9500, repeatability: '0.05mm' },
  // === 国产工业夹爪 ===
  { id: 'huiling-lfg', brand: '慧灵科技', model: 'LFG-2T', category: 'electric-gripper', type: '电动夹爪', force: '2-40N', stroke: '0-85mm', voltage: '12-24VDC', protocol: 'Modbus RTU/I2C', flange: 'ISO 9409-50-4-M6', weight: '0.38kg', price: 1680, repeatability: '0.05mm' },
  { id: 'huiling-lfg-mini', brand: '慧灵科技', model: 'LFG-Micro', category: 'electric-gripper', type: '电动夹爪', force: '0.5-10N', stroke: '0-25mm', voltage: '12VDC', protocol: 'I2C/UART', flange: '自定义 M4', weight: '0.12kg', price: 680, repeatability: '0.1mm' },
  { id: 'huiling-lfg3t', brand: '慧灵科技', model: 'LFG-3T', category: 'electric-gripper', type: '电动夹爪', force: '2-60N', stroke: '0-90mm', voltage: '24VDC', protocol: 'Modbus RTU/IO-Link', flange: 'ISO 9409-50-4-M6', weight: '0.42kg', price: 2280, repeatability: '0.05mm' },
  { id: 'dahang-gecko', brand: '大寰机器人', model: 'GECKO', category: 'electric-gripper', type: '电动夹爪', force: '1-25N', stroke: '0-65mm', voltage: '24VDC', protocol: 'Modbus RTU', flange: 'ISO 9409-50-4-M6', weight: '0.42kg', price: 2980, repeatability: '0.02mm' },
  { id: 'dahang-pika', brand: '大寰机器人', model: 'PIKA', category: 'electric-gripper', type: '电动夹爪', force: '0.5-8N', stroke: '0-30mm', voltage: '12VDC', protocol: 'I2C/UART', flange: '自定义 M3', weight: '0.09kg', price: 880, repeatability: '0.05mm' },
  { id: 'rouchu-fg', brand: '柔触机器人', model: 'FG-2', category: 'soft-gripper', type: '柔性夹爪', force: '1-15N', stroke: '自适应', voltage: '24VDC', protocol: 'Modbus RTU', flange: 'ISO 9409-50-4-M6', weight: '0.55kg', price: 3680, repeatability: '1mm' },
  { id: 'rouchu-fg-mini', brand: '柔触机器人', model: 'FG-mini', category: 'soft-gripper', type: '柔性夹爪', force: '0.5-8N', stroke: '自适应', voltage: '12VDC', protocol: 'I2C', flange: '自定义 M4', weight: '0.18kg', price: 1580, repeatability: '2mm' },
  { id: 'zhixing-hg', brand: '知行机器人', model: 'HG-210', category: 'electric-gripper', type: '电动夹爪', force: '5-100N', stroke: '0-70mm', voltage: '24VDC', protocol: 'Modbus RTU', flange: 'ISO 9409-50-4-M6', weight: '0.7kg', price: 3980, repeatability: '0.05mm' },
  // === 国产桌面/创客夹爪 ===
  { id: 'worm-wk01', brand: '沃姆机器人', model: 'WK-01', category: 'electric-gripper', type: '电动夹爪', force: '0.5-15N', stroke: '0-30mm', voltage: '12VDC', protocol: 'UART/I2C', flange: '自定义 M4', weight: '0.15kg', price: 580, repeatability: '0.1mm' },
  { id: 'tianji-tg01', brand: '天机机器人', model: 'TG-01', category: 'electric-gripper', type: '电动夹爪', force: '1-20N', stroke: '0-40mm', voltage: '12VDC', protocol: 'Modbus RTU', flange: '自定义 M4', weight: '0.22kg', price: 780, repeatability: '0.1mm' },
  { id: 'yiyuan-yg100', brand: '一元智能', model: 'YG-100', category: 'electric-gripper', type: '电动夹爪', force: '0.3-10N', stroke: '0-20mm', voltage: '5-12VDC', protocol: 'PWM/UART', flange: '标准舵机', weight: '0.08kg', price: 168, repeatability: '0.5mm' },
  // === 舵机夹爪 ===
  { id: 'servo-mg996r', brand: '通用舵机', model: 'MG996R', category: 'servo-gripper', type: '舵机夹爪', force: '10kg-cm', stroke: '180deg', voltage: '6VDC', protocol: 'PWM', flange: '标准舵机臂', weight: '0.055kg', price: 25, repeatability: '2deg' },
  { id: 'servo-mg995', brand: '通用舵机', model: 'MG995', category: 'servo-gripper', type: '舵机夹爪', force: '8.5kg-cm', stroke: '180deg', voltage: '6VDC', protocol: 'PWM', flange: '标准舵机臂', weight: '0.048kg', price: 18, repeatability: '2deg' },
  { id: 'servo-sg90', brand: '通用舵机', model: 'SG90', category: 'servo-gripper', type: '舵机夹爪', force: '1.8kg-cm', stroke: '180deg', voltage: '5VDC', protocol: 'PWM', flange: '标准舵机臂', weight: '0.009kg', price: 5, repeatability: '3deg' },
  { id: 'servo-ds3218', brand: '通用舵机', model: 'DS3218', category: 'servo-gripper', type: '舵机夹爪', force: '20kg-cm', stroke: '180deg', voltage: '7.4VDC', protocol: 'PWM', flange: '标准舵机臂', weight: '0.060kg', price: 35, repeatability: '1deg' },
  // === 真空吸盘 ===
  { id: 'vacuum-mini', brand: '慧灵科技', model: 'VG-Micro', category: 'vacuum', type: '微型真空吸盘', force: '2-8N', stroke: 'N/A', voltage: '12VDC', protocol: 'IO开关', flange: '自定义 M4', weight: '0.06kg', price: 320, repeatability: '1mm' },
  { id: 'vacuum-robotiq', brand: 'Robotiq', model: 'EPICK', category: 'vacuum', type: '电动真空吸盘', force: '5-20N', stroke: 'N/A', voltage: '24VDC', protocol: 'Modbus RTU', flange: 'ISO 9409-50-4-M6', weight: '0.7kg', price: 5800, repeatability: '0.5mm' },
];

// ========== 兼容性匹配规则 ==========
// 定义法兰兼容组: 同组法兰可直接安装
const FLANGE_GROUPS = {
  'iso50-m6': {
    name: 'ISO 9409-50-4-M6',
    arms: ['ur3e','ur5e','franka-panda','hiwin-6f','auber-06','dobot-magician','dobot-m1','dobot-cr3','elephant-630'],
    grippers: ['robotiq-2f85','robotiq-2f140','onrobot-rg2','onrobot-rg6','onrobot-vgc10','schunk-egp40','festo-dhg','huiling-lfg','huiling-lfg3t','dahang-gecko','zhixing-hg','rouchu-fg','vacuum-robotiq']
  },
  'iso40-m4': {
    name: 'ISO 9409-40-4-M4',
    arms: ['elephant-320'],
    grippers: ['robotiq-hande']
  },
  'custom-m4': {
    name: '自定义 M4',
    arms: ['uarm-metal','elephant-06','seeed-rebot','dobot-lite','cr4-robot'],
    grippers: ['huiling-lfg-mini','rouchu-fg-mini','worm-wk01','tianji-tg01','vacuum-mini']
  },
  'servo': {
    name: '标准舵机',
    arms: ['lofi-robot','so-arm100'],
    grippers: ['servo-mg996r','servo-mg995','servo-sg90','servo-ds3218','yiyuan-yg100']
  }
};

// 需要转接件的对
const ADAPTER_PAIRS = {
  'iso50-m6_to_custom-m4': { name: 'ISO50法兰转M4转接板', stlAvailable: true, stlId: 'adapter-iso50-m4' },
  'iso40-m4_to_custom-m4': { name: 'ISO40法兰转M4转接板', stlAvailable: true, stlId: 'adapter-iso40-m4' },
  'iso50-m6_to_servo': { name: 'ISO50法兰转舵机支架', stlAvailable: true, stlId: 'adapter-iso50-servo' },
  'custom-m4_to_servo': { name: 'M4转舵机支架', stlAvailable: true, stlId: 'adapter-m4-servo' },
};

// ========== 社区帖子（模拟数据）==========
const COMMUNITY_POSTS = [
  {
    id: 'p1', author: '创客小张', avatar: 'Z', time: '2小时前', tab: 'combo', tag: 'combo', tagText: '搭配方案',
    title: 'DOBOT Magician + 慧灵LFG-2T 完美适配记录',
    content: '实测DOBOT Magician的ISO50法兰和慧灵LFG-2T直接对插，孔距完全一致。Modbus RTU协议需要改一下波特率为115200，接线4根（VCC/GND/RXD/TXD）。夹持力够用，用来抓取乐高零件完全没问题。',
    likes: 42, comments: 8
  },
  {
    id: 'p2', author: '机器人老王', avatar: 'W', time: '5小时前', tab: 'review', tag: 'review', tagText: '评测',
    title: '大寰PIKA vs 慧灵LFG-Mini 桌面级夹爪横评',
    content: '两款都是面向桌面臂的超轻量夹爪。PIKA的响应速度更快（30ms vs 60ms），但LFG-Mini的行程更大（25mm vs 30mm）。如果用uArm，两者都需要我设计的M4转接件（已上传STL）。',
    likes: 67, comments: 15
  },
  {
    id: 'p3', author: '新手小白', avatar: 'X', time: '昨天', tab: 'qa', tag: 'question', tagText: '求助',
    title: 'LoFi Robot MK2能接Robotiq 2F-85吗？',
    content: '想给LoFi MK2加一个工业级夹爪，但法兰接口完全不匹配。有没有人做过转接件？或者有更便宜的替代方案？',
    likes: 12, comments: 23
  },
  {
    id: 'p4', author: '3D打印侠', avatar: 'D', time: '2天前', tab: 'tutorial', tag: 'tutorial', tagText: '教程',
    title: '如何自己设计夹爪转接件: 从测量到打印完整流程',
    content: '手把手教你用游标卡尺测量法兰孔距，在Fusion 360中建模，导出STL文件。FDM打印机PLA材料足够创客使用，精度控制在0.2mm以内。附带了5种常见转接件的源文件。',
    likes: 128, comments: 34
  },
  {
    id: 'p5', author: '集成商阿伟', avatar: 'A', time: '3天前', tab: 'combo', tag: 'combo', tagText: '搭配方案',
    title: '柔性夹爪在生鲜分拣中的应用方案',
    content: '用AUBO i06 + 柔触FG-2 做了一个小型水果分拣原型。柔性夹爪对不同大小和形状的水果适应性很好，不会压坏。关键是调了PID参数来控制夹持力度，Modbus通讯延迟约3ms，够用。',
    likes: 56, comments: 11
  },
  {
    id: 'p6', author: '开源极客', avatar: 'K', time: '3天前', tab: 'tutorial', tag: 'tutorial', tagText: '教程',
    title: '用ESP32-C3自制机械臂夹爪控制器（全开源）',
    content: '开源了一个ESP32-C3夹爪控制板，支持PWM舵机控制和Modbus RTU透传。PCB已开源在GitHub，可以控制4路舵机或2路Modbus夹爪。成本不到30元。GitHub链接见评论区。',
    likes: 89, comments: 22
  },
];

// ========== STL转接件设计 ==========
const STL_DESIGNS = [
  // --- 第一批：法兰转接件 ---
  { id: 'adapter-iso50-m4', name: 'ISO50法兰转M4转接板', desc: '适用于ISO9409-50机械臂连接M4接口夹爪，底板带4个M6安装耳，中心M8沉孔', compat: 'DOBOT/uArm/UR系列 + 慧灵Mini/大寰PIKA', downloads: 234, size: '29KB', ready: true },
  { id: 'adapter-iso40-m4', name: 'ISO40法兰转M4转接板', desc: '适用于Robotiq Hand-E等ISO40接口夹爪连接M4臂，4xM4 PCD36mm', compat: 'Robotiq Hand-E + uArm/Elephant', downloads: 156, size: '49KB', ready: true },
  { id: 'adapter-iso50-servo', name: 'ISO50法兰转舵机支架', desc: '将工业协作臂的ISO50法兰转为标准舵机接口，适配MG996R/MG995', compat: 'UR/DOBOT + MG996R/MG995', downloads: 189, size: '42KB', ready: true },
  { id: 'adapter-m4-servo', name: 'M4接口转舵机支架', desc: '桌面臂M4法兰连接舵机控制夹爪，4xM4 PCD22mm', compat: 'uArm/LoFi/Elephant + MG996R', downloads: 312, size: '43KB', ready: true },
  // --- 第一批：功能件 ---
  { id: 'adapter-dual-gripper', name: '双夹爪安装板', desc: '一个ISO50法兰同时安装两个小型夹爪，实现双手操作', compat: 'ISO50法兰通用', downloads: 98, size: '63KB', ready: true },
  { id: 'adapter-cable-chain', name: '线缆拖链安装支架', desc: '用于在机械臂末端安装线缆拖链，防止线缆缠绕，C形托架设计', compat: 'ISO50法兰通用', downloads: 145, size: '59KB', ready: true },
  { id: 'tool-changer-passive', name: '被动式快换接头', desc: '基于球头定位的快换机构，支持手动更换工具，4球头+中心定位销', compat: 'ISO50法兰通用', downloads: 203, size: '103KB', ready: true },
  { id: 'adapter-uarm-gripper', name: 'uArm通用夹爪安装座', desc: '专为uArm Swift Pro设计的通用夹爪安装座，多排M3安装孔', compat: 'uArm Swift Pro + 多种夹爪', downloads: 278, size: '83KB', ready: true },
  { id: 'gripper-jaw-custom', name: '可定制手指组件', desc: '模块化夹爪手指，L形设计，带卡扣安装结构，支持不同指尖', compat: '慧灵LFG系列通用', downloads: 167, size: '29KB', ready: true },
  { id: 'adapter-elephant-servo', name: 'myCobot舵机转接板', desc: '专为Elephant myCobot设计的舵机接口转接，M4法兰到舵机', compat: 'Elephant myCobot 280', downloads: 121, size: '39KB', ready: true },
  { id: 'mount-camera', name: '夹爪集成摄像头安装座', desc: '在夹爪侧面安装微型摄像头，实现视觉抓取，侧面伸出臂+圆柱座', compat: 'ISO50法兰通用', downloads: 156, size: '37KB', ready: true },
  { id: 'adapter-nema17', name: 'NEMA17步进电机安装板', desc: '在机械臂末端安装NEMA17电机驱动的自定义工具，ISO50到NEMA17', compat: 'ISO50法兰通用', downloads: 89, size: '97KB', ready: true },
  // --- 第二批：法兰转接 + 工具安装 ---
  { id: 'adapter-iso50-iso40', name: 'ISO50转ISO40法兰转接环', desc: '工业场景最常用：大法兰协作臂直接安装小法兰夹爪(如Hand-E)，锥台过渡设计', compat: 'UR/DOBOT/AUBO + Robotiq Hand-E', downloads: 0, size: '157KB', ready: true, isNew: true },
  { id: 'adapter-servo-claw', name: '舵机夹爪爪指套装', desc: '完整平行爪组件，底座+导轨+双指，适配MG996R/MG995，即插即用', compat: 'MG996R/MG995/DS3218舵机', downloads: 0, size: '64KB', ready: true, isNew: true },
  { id: 'mount-pen-holder', name: '画笔/工具夹持器', desc: '末端安装画笔或圆杆工具，教学演示、写字画画，带侧紧螺丝', compat: '通用M4/ISO50法兰', downloads: 0, size: '90KB', ready: true, isNew: true },
  { id: 'adapter-suction-cup', name: '通用真空吸盘安装座', desc: '法兰安装+气管接口，适配各种口径吸盘，适合薄片/光滑物体抓取', compat: 'M4/ISO50法兰通用', downloads: 0, size: '110KB', ready: true, isNew: true },
  // --- 第二批：夹爪配件 ---
  { id: 'gripper-finger-flat', name: '平行夹爪平面指尖', desc: '带摩擦纹理的平面指尖，适合抓取方块/薄片/扁平物体，卡扣安装', compat: '慧灵LFG/大寰GECKO通用', downloads: 0, size: '30KB', ready: true, isNew: true },
  { id: 'gripper-finger-round', name: '平行夹爪圆弧指尖', desc: 'V形圆弧指尖，适合抓取圆柱/球体/管道，自定心设计', compat: '慧灵LFG/大寰GECKO通用', downloads: 0, size: '29KB', ready: true, isNew: true },
  { id: 'gripper-finger-spring', name: '弹性手指组件', desc: '薄壁弹性设计带弹簧槽，过盈抓取不易损伤物体，适合脆弱物品', compat: '慧灵LFG/大寰PIKA通用', downloads: 0, size: '32KB', ready: true, isNew: true },
  // --- 第二批：末端工具配件 ---
  { id: 'adapter-elec-box', name: '小型控制器安装盒', desc: '法兰安装防水电子盒，可装ESP32/Arduino等控制板，侧面走线口', compat: 'ISO50/M4法兰通用', downloads: 0, size: '67KB', ready: true, isNew: true },
  { id: 'mount-led-ring', name: 'LED照明环安装座', desc: '12颗LED环形照明，末端视觉抓取补光，侧面出线', compat: '通用法兰', downloads: 0, size: '160KB', ready: true, isNew: true },
  { id: 'mount-screwdriver', name: '螺丝刀工具安装座', desc: '末端安装电动螺丝刀，带侧夹紧缝和紧固螺丝，适合装配场景', compat: 'ISO50法兰通用', downloads: 0, size: '79KB', ready: true, isNew: true },
  { id: 'endcap-iso50', name: 'ISO50法兰端盖保护罩', desc: '保护未使用的法兰接口防尘防水，O型圈槽设计，快拆安装', compat: 'ISO50法兰通用', downloads: 0, size: '89KB', ready: true, isNew: true },
  { id: 'adapter-quick-lock-pin', name: '快锁销机构', desc: '弹簧球头快拆销，快速手动更换末端工具，免工具操作', compat: '通用法兰', downloads: 0, size: '110KB', ready: true, isNew: true },
];

// ========== 行业监控数据（模拟，后续由自动化任务写入）==========
const MONITOR_DATA = {
  brand: [
    { date: '2026-06-05', title: '慧灵科技发布LFG-3T新型电动夹爪', content: '夹持力范围升级至2-60N，新增IO-Link通讯支持，法兰兼容ISO9409-50，重量仅0.42kg。售价2280元。', source: '慧灵科技官网', impact: 'high' },
    { date: '2026-06-04', title: '大寰机器人GECKO系列新增变体', content: 'GECKO-Plus版本支持力控反馈，夹持精度提升至0.01mm，适配ROS2驱动已开源。', source: '大寰机器人公众号', impact: 'medium' },
    { date: '2026-06-03', title: 'Robotiq发布2F-85固件更新v4.2', content: '新增自适应抓取模式，可自动调节夹持力。支持URCap 5.x插件。需要通过Robotiq官方工具更新。', source: 'Robotiq Support', impact: 'low' },
  ],
  opensource: [
    { date: '2026-06-05', title: 'GitHub: ros2_gripper_driver 发布v2.0', content: '新增对慧灵LFG系列和柔触FG系列的ROS2驱动支持，支持force_feedback话题，适配Humble/Iron发行版。', source: 'github.com/robo-gripper', impact: 'high' },
    { date: '2026-06-04', title: 'Thingiverse: uArm双夹爪安装座设计', content: '一位创客上传了uArm Swift Pro的双夹爪安装板设计，支持同时安装两个小型夹爪。文件包含Fusion360源文件和STL。', source: 'Thingiverse', impact: 'medium' },
    { date: '2026-06-03', title: 'B站: 50元自制机械臂夹爪完整教程', content: 'UP主用3D打印外壳+MG996R舵机+ESP32控制板做了一个低成本夹爪，包含完整的接线说明和代码。播放量2.3万。', source: 'B站', impact: 'medium' },
  ],
  standard: [
    { date: '2026-06-05', title: 'IEEE发布机器人末端工具接口标准草案', content: 'IEEE P2998.1定义了末端执行器的统一机械接口规范（涵盖法兰、电气、通讯），征求意见阶段。涵盖4种标准法兰尺寸。', source: 'IEEE Standards', impact: 'high' },
    { date: '2026-06-02', title: '中国机器人产业联盟推进接口互操作规范', content: '联盟发布了《工业机器人末端执行器互操作指南》征求意见稿，覆盖协作臂末端法兰、电气接口定义、通讯协议映射表。', source: '中国机器人产业联盟', impact: 'high' },
    { date: '2026-05-30', title: 'ROS2 Humble新增robot_end_effector接口包', content: 'Open Robotics在ROS2 Humble中新增了标准化末端执行器描述格式，支持自动识别夹爪类型和参数。', source: 'ROS Discourse', impact: 'medium' },
  ]
};
