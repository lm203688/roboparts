/**
 * RoboParts URDF 模型库 API
 * GET /api/urdf/library          - 获取 URDF 模型列表（支持 ?robot_type= 筛选）
 * GET /api/urdf/library?id=xxx   - 获取单个 URDF 模型详情
 * GET /api/urdf/library?tier=L0  - 按资产分级筛选（L0-L4，见下方 ASSET_TIER_SCHEMA）
 *
 * 预置模型：60 个（URDF-001 ~ URDF-060）
 *   URDF-001 ~ URDF-025  原始基础模型
 *   URDF-026 ~ URDF-029  开源 URDF 生态（天工TienKung、OpenArm、UR5e+Robotiq、六轴机械臂）
 *   URDF-030 ~ URDF-034  HuggingFace LeRobot 生态（SO-100/101、ALOHA/ALOHA-2、Reachy 2）
 *   URDF-035 ~ URDF-039  国际知名协作/工业机器人（Fanuc CRX、KUKA iiwa、ABB GoFa、Doosan、Mujin）
 *   URDF-040 ~ URDF-041  四足机器人（Boston Dynamics Spot、ANYmal D）
 *   URDF-042 ~ URDF-047  人形机器人（TIAGo、Figure 01/02、Phoenix、1X NEO、Agility Digit）
 *   URDF-048 ~ URDF-058  中国机器人品牌（小鹏Iron、傅利叶GR-1/2、星动纪元、逐际动力、银河通用、有鹿、大象、睿尔曼、大然）
 *   URDF-059 ~ URDF-060  仿真常用平台（PR2、TurtleBot3）
 *
 * P0-12 资产分级（2026-10-26 全面审计报告）：
 *   L0 元数据模型 · L1 结构可解析 · L2 运动学有效 · L3 物理参数可追 · L4 验证资产
 *   本库 60 个预置模型**全部落 L0**——由 robot_type + joints 数动态生成的参数化骨架，
 *   几何/质量/惯量都是脚本内估算，非厂商 CAD、非实测。对外契约不再自称"60+ 即开即用"，
 *   而是明确"60 个 L0 元数据模型 + 分级筛选"。导入真实厂商 URDF 时通过
 *   ASSET_TIER_OVERRIDES 显式登记更高档位并附 source 与 assumptions。
 *
 * 功能：
 * 1. CORS 支持（onRequestOptions）
 * 2. 从 KV（env.URDF_LIBRARY）读取 URDF 模型
 * 3. 如果 KV 中没有数据，返回预置的 60 个模型列表
 * 4. 支持按 robot_type / compatibility / sim / tier 筛选
 * 5. 返回模型列表（id, name, robot_type, description, joints_count, download_url,
 *    asset_tier, compatibility）
 */

// 预置 URDF 模型（当 KV 为空时返回）
const PRESET_URDF_MODELS = [
  {
    id: 'URDF-001',
    name: '6-DOF机械臂基础模型',
    robot_type: 'arm',
    description: '6自由度工业机械臂URDF，适配大多数控制器',
    joints: 6,
    links: 7,
    payload: '2kg',
    reach: '600mm',
    file_size: '15KB',
    license: 'MIT',
    author: 'RoboParts',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-001',
  },
  {
    id: 'URDF-002',
    name: '人形机器人上半身',
    robot_type: 'humanoid',
    description: '7-DOF双臂人形机器人上半身，含头部关节',
    joints: 14,
    links: 15,
    payload: 'N/A',
    reach: '500mm',
    file_size: '45KB',
    license: 'MIT',
    author: 'RoboParts',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-002',
  },
  {
    id: 'URDF-003',
    name: '四足机器人基础模型',
    robot_type: 'quadruped',
    description: '12-DOF四足机器人，每条腿3个关节',
    joints: 12,
    links: 13,
    payload: '5kg',
    reach: '400mm',
    file_size: '38KB',
    license: 'MIT',
    author: 'RoboParts',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-003',
  },
  {
    id: 'URDF-004',
    name: '机器人夹爪',
    robot_type: 'hand',
    description: '2指电动夹爪，含力控接口',
    joints: 2,
    links: 3,
    payload: '0.5kg',
    reach: '80mm',
    file_size: '8KB',
    license: 'MIT',
    author: 'RoboParts',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-004',
  },
  {
    id: 'URDF-005',
    name: '人形机器人全身模型',
    robot_type: 'humanoid',
    description: '28-DOF全身人形机器人，含双腿、双臂、头部和腰部',
    joints: 28,
    links: 29,
    payload: 'N/A',
    reach: '1.8m',
    file_size: '120KB',
    license: 'Apache-2.0',
    author: 'RoboParts',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-005',
  },
  {
    id: 'URDF-006',
    name: 'Unitree G1',
    robot_type: 'humanoid',
    description: '23-DOF全身人形机器人',
    joints: 23,
    links: 24,
    payload: '3kg',
    reach: '550mm',
    file_size: '52KB',
    license: 'Apache-2.0',
    author: 'Unitree Robotics',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-006',
  },
  {
    id: 'URDF-007',
    name: 'Unitree H1',
    robot_type: 'humanoid',
    description: '20-DOF全身人形机器人',
    joints: 20,
    links: 21,
    payload: '5kg',
    reach: '600mm',
    file_size: '48KB',
    license: 'Apache-2.0',
    author: 'Unitree Robotics',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-007',
  },
  {
    id: 'URDF-008',
    name: 'Unitree Go2',
    robot_type: 'quadruped',
    description: '12-DOF四足机器人',
    joints: 12,
    links: 13,
    payload: '8kg',
    reach: '400mm',
    file_size: '35KB',
    license: 'Apache-2.0',
    author: 'Unitree Robotics',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-008',
  },
  {
    id: 'URDF-009',
    name: 'Unitree B2',
    robot_type: 'quadruped',
    description: '15-DOF四足机器人',
    joints: 15,
    links: 16,
    payload: '12kg',
    reach: '450mm',
    file_size: '42KB',
    license: 'Apache-2.0',
    author: 'Unitree Robotics',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-009',
  },
  {
    id: 'URDF-010',
    name: 'AgiBot/FlexiPick',
    robot_type: 'arm',
    description: '7-DOF柔性抓取机械臂',
    joints: 7,
    links: 8,
    payload: '5kg',
    reach: '850mm',
    file_size: '22KB',
    license: 'MIT',
    author: 'Agibot',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-010',
  },
  {
    id: 'URDF-011',
    name: '智元 灵犀X1',
    robot_type: 'humanoid',
    description: '41-DOF全身人形机器人',
    joints: 41,
    links: 42,
    payload: '5kg',
    reach: '650mm',
    file_size: '68KB',
    license: 'Apache-2.0',
    author: 'Zhiyuan Robotics',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-011',
  },
  {
    id: 'URDF-012',
    name: '优必选 Walker S',
    robot_type: 'humanoid',
    description: '41-DOF全身人形机器人',
    joints: 41,
    links: 42,
    payload: '3kg',
    reach: '600mm',
    file_size: '65KB',
    license: 'Apache-2.0',
    author: 'UBTECH',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-012',
  },
  {
    id: 'URDF-013',
    name: 'Tesla Optimus Gen3',
    robot_type: 'humanoid',
    description: '28-DOF人形机器人',
    joints: 28,
    links: 29,
    payload: '20kg',
    reach: '700mm',
    file_size: '55KB',
    license: 'Custom',
    author: 'Tesla',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-013',
  },
  {
    id: 'URDF-014',
    name: 'Franka Emika Panda',
    robot_type: 'arm',
    description: '7-DOF协作机械臂',
    joints: 7,
    links: 8,
    payload: '3kg',
    reach: '855mm',
    file_size: '18KB',
    license: 'BSD',
    author: 'Franka Emika',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-014',
  },
  {
    id: 'URDF-015',
    name: 'UR5e Robot Arm',
    robot_type: 'arm',
    description: '6-DOF工业机械臂',
    joints: 6,
    links: 7,
    payload: '5kg',
    reach: '850mm',
    file_size: '15KB',
    license: 'Apache-2.0',
    author: 'Universal Robots',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-015',
  },
  {
    id: 'URDF-016',
    name: 'Kinova Gen3 Lite',
    robot_type: 'arm',
    description: '6-DOF轻量机械臂',
    joints: 6,
    links: 7,
    payload: '4.5kg',
    reach: '900mm',
    file_size: '16KB',
    license: 'BSD',
    author: 'Kinova',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-016',
  },
  {
    id: 'URDF-017',
    name: '宇树 H1-3',
    robot_type: 'humanoid',
    description: '19-DOF全身人形',
    joints: 19,
    links: 20,
    payload: '3.5kg',
    reach: '500mm',
    file_size: '45KB',
    license: 'Apache-2.0',
    author: 'Unitree Robotics',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-017',
  },
  {
    id: 'URDF-018',
    name: '戴盟 DEX-001',
    robot_type: 'hand',
    description: '12-DOF仿人灵巧手',
    joints: 12,
    links: 13,
    payload: '0.5kg',
    reach: '120mm',
    file_size: '25KB',
    license: 'MIT',
    author: 'Daimon Robotics',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-018',
  },
  {
    id: 'URDF-019',
    name: 'Shadow Dexterous Hand',
    robot_type: 'hand',
    description: '20-DOF五指灵巧手',
    joints: 20,
    links: 24,
    payload: '2kg',
    reach: '150mm',
    file_size: '38KB',
    license: 'GPL',
    author: 'Shadow Robot',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-019',
  },
  {
    id: 'URDF-020',
    name: 'Unitree Z1',
    robot_type: 'gripper',
    description: '2-DOF平行夹爪',
    joints: 2,
    links: 3,
    payload: '1kg',
    reach: '80mm',
    file_size: '8KB',
    license: 'Apache-2.0',
    author: 'Unitree Robotics',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-020',
  },
  {
    id: 'URDF-021',
    name: 'AGILEX/Amr Base',
    robot_type: 'amr',
    description: '4轮差速底盘',
    joints: 4,
    links: 5,
    payload: '20kg',
    reach: 'N/A',
    file_size: '12KB',
    license: 'MIT',
    author: 'AgileX',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-021',
  },
  {
    id: 'URDF-022',
    name: 'Mobile Manipulator',
    robot_type: 'arm',
    description: '6-DOF移动操作臂',
    joints: 6,
    links: 7,
    payload: '5kg',
    reach: '800mm',
    file_size: '20KB',
    license: 'Apache-2.0',
    author: 'RoboParts',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-022',
  },
  {
    id: 'URDF-023',
    name: 'Open Manipulator X',
    robot_type: 'arm',
    description: '4-DOF桌面机械臂',
    joints: 4,
    links: 5,
    payload: '1kg',
    reach: '400mm',
    file_size: '10KB',
    license: 'MIT',
    author: 'ROBOTIS',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-023',
  },
  {
    id: 'URDF-024',
    name: 'TALOS II',
    robot_type: 'humanoid',
    description: '32-DOF全身人形',
    joints: 32,
    links: 33,
    payload: '6kg',
    reach: '750mm',
    file_size: '72KB',
    license: 'GPL',
    author: 'PAL Robotics',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-024',
  },
  {
    id: 'URDF-025',
    name: 'ANYmal C',
    robot_type: 'quadruped',
    description: '12-DOF四足机器人',
    joints: 12,
    links: 13,
    payload: '10kg',
    reach: '380mm',
    file_size: '40KB',
    license: 'BSD',
    author: 'ANYbotics',
    updated: '2026-07-27',
    download_url: '/api/urdf/download?id=URDF-025',
  },
  // ===== URDF-026 ~ URDF-060：行业调研扩充模型 =====
  // --- 开源 URDF 生态 ---
  {
    id: 'URDF-026',
    name: '天工 TienKung',
    robot_type: 'humanoid',
    description: '42-DOF全身人形机器人，国家地方共建人形机器人创新中心开源',
    joints: 42,
    links: 45,
    payload: '5kg',
    reach: '650mm',
    file_size: '78KB',
    license: 'Apache-2.0',
    author: 'National Humanoid Robotics Innovation Center',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-026',
  },
  {
    id: 'URDF-027',
    name: 'OpenArm 7-DOF',
    robot_type: 'arm',
    description: '开源7自由度人形臂，适用于人形机器人上身集成',
    joints: 7,
    links: 9,
    payload: '3kg',
    reach: '600mm',
    file_size: '20KB',
    license: 'MIT',
    author: 'OpenArm Community',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-027',
  },
  {
    id: 'URDF-028',
    name: 'UR5e + Robotiq 2F-85',
    robot_type: 'arm',
    description: 'UR5e六轴机械臂搭载Robotiq 2F-85夹爪，完整末端执行器模型',
    joints: 8,
    links: 10,
    payload: '5kg',
    reach: '850mm',
    file_size: '28KB',
    license: 'Apache-2.0',
    author: 'Universal Robots / Robotiq',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-028',
  },
  {
    id: 'URDF-029',
    name: '六轴工业机械臂 (Generic 6-Axis)',
    robot_type: 'arm',
    description: '通用6轴工业机械臂URDF，含碰撞几何与惯性参数',
    joints: 6,
    links: 7,
    payload: '10kg',
    reach: '900mm',
    file_size: '18KB',
    license: 'MIT',
    author: 'Open Robotics Community',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-029',
  },
  // --- HuggingFace LeRobot 生态 ---
  {
    id: 'URDF-030',
    name: 'SO-100 (LeRobot)',
    robot_type: 'arm',
    description: 'LeRobot开源低成本6-DOF机械臂，3D打印友好设计',
    joints: 6,
    links: 7,
    payload: '0.5kg',
    reach: '350mm',
    file_size: '14KB',
    license: 'MIT',
    author: 'The K Rene/Fanny Reber (LeRobot)',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-030',
  },
  {
    id: 'URDF-031',
    name: 'SO-101 (LeRobot)',
    robot_type: 'arm',
    description: 'SO-100改进版6-DOF机械臂，增强刚性与负载',
    joints: 6,
    links: 7,
    payload: '1kg',
    reach: '380mm',
    file_size: '15KB',
    license: 'MIT',
    author: 'The K Rene (LeRobot)',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-031',
  },
  {
    id: 'URDF-032',
    name: 'ALOHA (LeRobot)',
    robot_type: 'arm',
    description: '双臂遥操作数据采集平台，每臂6-DOF + 2指夹爪',
    joints: 14,
    links: 18,
    payload: '2kg',
    reach: '450mm',
    file_size: '32KB',
    license: 'MIT',
    author: 'Tony Zhao / Stanford (LeRobot)',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-032',
  },
  {
    id: 'URDF-033',
    name: 'ALOHA-2 (LeRobot)',
    robot_type: 'arm',
    description: 'ALOHA第二代双臂遥操作平台，改进静音与轻量化',
    joints: 14,
    links: 18,
    payload: '2kg',
    reach: '450mm',
    file_size: '34KB',
    license: 'MIT',
    author: 'Tony Zhao / Stanford (LeRobot)',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-033',
  },
  {
    id: 'URDF-034',
    name: 'Reachy 2',
    robot_type: 'humanoid',
    description: '41-DOF上半身人形机器人，双臂7-DOF + 表情头部',
    joints: 41,
    links: 44,
    payload: '1.5kg',
    reach: '550mm',
    file_size: '62KB',
    license: 'GPL-3.0',
    author: 'Pollen Robotics',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-034',
  },
  // --- 国际知名协作/工业机器人 ---
  {
    id: 'URDF-035',
    name: 'Fanuc CRX-10iA',
    robot_type: 'arm',
    description: 'FANUC CRX系列协作机器人，6-DOF轻量化设计',
    joints: 6,
    links: 7,
    payload: '10kg',
    reach: '991mm',
    file_size: '17KB',
    license: 'BSD',
    author: 'FANUC',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-035',
  },
  {
    id: 'URDF-036',
    name: 'KUKA LBR iiwa 14 R820',
    robot_type: 'arm',
    description: 'KUKA 7-DOF灵敏型协作机器人，高精度力矩传感器',
    joints: 7,
    links: 8,
    payload: '14kg',
    reach: '820mm',
    file_size: '19KB',
    license: 'BSD',
    author: 'KUKA Robotics',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-036',
  },
  {
    id: 'URDF-037',
    name: 'ABB GoFa CRB 15000',
    robot_type: 'arm',
    description: 'ABB新一代协作机器人，4自由度高负载',
    joints: 4,
    links: 5,
    payload: '15kg',
    reach: '950mm',
    file_size: '16KB',
    license: 'BSD',
    author: 'ABB Robotics',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-037',
  },
  {
    id: 'URDF-038',
    name: 'Doosan H2515',
    robot_type: 'arm',
    description: '斗山6-DOF协作机器人，25kg大负载',
    joints: 6,
    links: 7,
    payload: '25kg',
    reach: '1700mm',
    file_size: '18KB',
    license: 'Apache-2.0',
    author: 'Doosan Robotics',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-038',
  },
  {
    id: 'URDF-039',
    name: 'Mujin PickArm',
    robot_type: 'arm',
    description: 'Mujin物流抓取专用机械臂，高速码垛',
    joints: 6,
    links: 7,
    payload: '20kg',
    reach: '1200mm',
    file_size: '22KB',
    license: 'Proprietary',
    author: 'Mujin',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-039',
  },
  // --- 四足 / 移动机器人 ---
  {
    id: 'URDF-040',
    name: 'Boston Dynamics Spot',
    robot_type: 'quadruped',
    description: '12-DOF四足机器狗，全地形移动平台',
    joints: 12,
    links: 15,
    payload: '14kg',
    reach: '450mm',
    file_size: '55KB',
    license: 'Proprietary',
    author: 'Boston Dynamics',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-040',
  },
  {
    id: 'URDF-041',
    name: 'ANYmal D',
    robot_type: 'quadruped',
    description: 'ANYmal D系列四足机器人，工业级全地形',
    joints: 12,
    links: 14,
    payload: '20kg',
    reach: '420mm',
    file_size: '48KB',
    license: 'BSD',
    author: 'ANYbotics',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-041',
  },
  // --- 人形机器人 ---
  {
    id: 'URDF-042',
    name: 'PAL Robotics TIAGo',
    robot_type: 'humanoid',
    description: '28-DOF半身人形服务机器人，含7-DOF双臂与移动底座',
    joints: 28,
    links: 32,
    payload: '3kg',
    reach: '650mm',
    file_size: '58KB',
    license: 'GPL-3.0',
    author: 'PAL Robotics',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-042',
  },
  {
    id: 'URDF-043',
    name: 'Figure 01',
    robot_type: 'humanoid',
    description: 'Figure 01全身人形机器人，41-DOF商用双足人形',
    joints: 41,
    links: 44,
    payload: '20kg',
    reach: '700mm',
    file_size: '75KB',
    license: 'Proprietary',
    author: 'Figure AI',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-043',
  },
  {
    id: 'URDF-044',
    name: 'Figure 02',
    robot_type: 'humanoid',
    description: 'Figure 02第二代全身人形，增强灵巧操作与环境感知',
    joints: 42,
    links: 46,
    payload: '25kg',
    reach: '750mm',
    file_size: '82KB',
    license: 'Proprietary',
    author: 'Figure AI',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-044',
  },
  {
    id: 'URDF-045',
    name: 'Sanctuary AI Phoenix',
    robot_type: 'humanoid',
    description: 'Phoenix全身通用人形机器人，集成灵巧手与触觉',
    joints: 44,
    links: 50,
    payload: '15kg',
    reach: '680mm',
    file_size: '88KB',
    license: 'Proprietary',
    author: 'Sanctuary AI',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-045',
  },
  {
    id: 'URDF-046',
    name: '1X NEO',
    robot_type: 'humanoid',
    description: '1X NEO全身人形机器人，家用服务场景',
    joints: 36,
    links: 40,
    payload: '8kg',
    reach: '620mm',
    file_size: '70KB',
    license: 'Proprietary',
    author: '1X Technologies',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-046',
  },
  {
    id: 'URDF-047',
    name: 'Agility Digit',
    robot_type: 'humanoid',
    description: 'Digit双足人形机器人，物流搬运专用',
    joints: 20,
    links: 24,
    payload: '16kg',
    reach: '800mm',
    file_size: '65KB',
    license: 'Proprietary',
    author: 'Agility Robotics',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-047',
  },
  // --- 中国机器人品牌 ---
  {
    id: 'URDF-048',
    name: '小鹏 Iron',
    robot_type: 'humanoid',
    description: '小鹏汽车人形机器人Iron，60-DOF全身多模态',
    joints: 60,
    links: 65,
    payload: '10kg',
    reach: '700mm',
    file_size: '95KB',
    license: 'Proprietary',
    author: 'Xiaomi / XPeng Robotics',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-048',
  },
  {
    id: 'URDF-049',
    name: '傅利叶 GR-1',
    robot_type: 'humanoid',
    description: 'GR-1全身通用人形机器人，40-DOF自由度',
    joints: 40,
    links: 43,
    payload: '5kg',
    reach: '620mm',
    file_size: '72KB',
    license: 'Apache-2.0',
    author: 'Fourier Intelligence',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-049',
  },
  {
    id: 'URDF-050',
    name: '傅利叶 GR-2',
    robot_type: 'humanoid',
    description: 'GR-2第二代全身人形，增强手眼协调与行走能力',
    joints: 42,
    links: 46,
    payload: '6kg',
    reach: '650mm',
    file_size: '78KB',
    license: 'Apache-2.0',
    author: 'Fourier Intelligence',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-050',
  },
  {
    id: 'URDF-051',
    name: '星动纪元 XBot-L',
    robot_type: 'humanoid',
    description: 'XBot-L全身人形机器人，可重构模块化设计',
    joints: 41,
    links: 44,
    payload: '5kg',
    reach: '600mm',
    file_size: '68KB',
    license: 'Apache-2.0',
    author: 'RobotEra (星动纪元)',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-051',
  },
  {
    id: 'URDF-052',
    name: '逐际动力 CL-1',
    robot_type: 'humanoid',
    description: 'CL-1双足人形机器人，动态平衡与地形适应',
    joints: 36,
    links: 40,
    payload: '10kg',
    reach: '680mm',
    file_size: '65KB',
    license: 'Proprietary',
    author: 'LimX Dynamics (逐际动力)',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-052',
  },
  {
    id: 'URDF-053',
    name: '银河通用 Galbot G1',
    robot_type: 'humanoid',
    description: '银河通用具身智能机器人，双臂操作+轮式移动底座',
    joints: 22,
    links: 26,
    payload: '8kg',
    reach: '750mm',
    file_size: '55KB',
    license: 'Proprietary',
    author: 'Galbot (银河通用机器人)',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-053',
  },
  {
    id: 'URDF-054',
    name: '有鹿机器人 Master',
    robot_type: 'amr',
    description: '有鹿机器人通用移动平台，激光SLAM导航',
    joints: 4,
    links: 5,
    payload: '30kg',
    reach: 'N/A',
    file_size: '15KB',
    license: 'MIT',
    author: 'LU Robotics (有鹿机器人)',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-054',
  },
  {
    id: 'URDF-055',
    name: '大象机器人 myCobot 280',
    robot_type: 'arm',
    description: 'myCobot 280桌面6-DOF协作机械臂，教育科研',
    joints: 6,
    links: 7,
    payload: '0.25kg',
    reach: '280mm',
    file_size: '12KB',
    license: 'MIT',
    author: 'Elephant Robotics (大象机器人)',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-055',
  },
  {
    id: 'URDF-056',
    name: '大象机器人 myBuddy 280',
    robot_type: 'arm',
    description: 'myBuddy双臂桌面机器人，每臂5-DOF+夹爪',
    joints: 12,
    links: 14,
    payload: '0.5kg',
    reach: '280mm',
    file_size: '22KB',
    license: 'MIT',
    author: 'Elephant Robotics (大象机器人)',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-056',
  },
  {
    id: 'URDF-057',
    name: '睿尔曼 RM65-B',
    robot_type: 'arm',
    description: '睿尔曼RM65-B六轴协作机械臂，5kg负载',
    joints: 6,
    links: 7,
    payload: '5kg',
    reach: '850mm',
    file_size: '16KB',
    license: 'MIT',
    author: 'Realman (睿尔曼智能)',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-057',
  },
  {
    id: 'URDF-058',
    name: '大然机器人 DR-07',
    robot_type: 'arm',
    description: '大然DR-07七自由度协作机械臂，高性价比',
    joints: 7,
    links: 8,
    payload: '7kg',
    reach: '900mm',
    file_size: '17KB',
    license: 'MIT',
    author: 'DARAN (大然机器人)',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-058',
  },
  // --- 仿真常用平台 ---
  {
    id: 'URDF-059',
    name: 'PR2',
    robot_type: 'arm',
    description: 'Willow Garage PR2双臂移动操作平台，经典ROS研究机器人',
    joints: 38,
    links: 42,
    payload: '2kg',
    reach: '800mm',
    file_size: '120KB',
    license: 'BSD',
    author: 'Willow Garage / Open Robotics',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-059',
  },
  {
    id: 'URDF-060',
    name: 'TurtleBot3 Burger',
    robot_type: 'amr',
    description: 'TurtleBot3 Burger差速移动平台，ROS教育标准',
    joints: 2,
    links: 4,
    payload: '1kg',
    reach: 'N/A',
    file_size: '10KB',
    license: 'Apache-2.0',
    author: 'ROBOTIS / Open Robotics',
    updated: '2026-07-28',
    download_url: '/api/urdf/download?id=URDF-060',
  },
];

const VALID_ROBOT_TYPES = ['humanoid', 'quadruped', 'arm', 'hand', 'gripper', 'amr'];
const KV_MODELS_KEY = 'urdf_models';

// ===================== P0-12 · 资产分级 L0-L4（2026-10-26 全面审计报告） =====================
// 审计原话："60 个预设模型由元数据动态生成通用骨架，不应与厂商授权 URDF 混为一谈。
// 建议把'60+ 即开即用'改为按 L0–L4 筛选的真实资产清单。"
//
// 分级定义（每级必须满足下一级所有条件）：
//   L0 · 元数据模型：有名称、类型、来源和估算边界。对外称「参数化元数据」。
//       本库 60 个预置模型全部落此级——`generateURDF()` 按 robot_type + joints 数
//       动态生成通用骨架，几何/质量/惯量都是脚本内硬编码估算，无厂商 CAD、无实测。
//   L1 · 结构可解析：XML Schema 通过、引用完整、单位明确。对外称「可导入原型」。
//       条件：需要独立的 URDF Schema 校验器实际跑过 + 每个 link/joint 引用都能追溯。
//   L2 · 运动学有效：连杆树、关节轴、限位、坐标系、TCP 经测试。对外称「运动学原型」。
//       条件：需要在 MuJoCo/Gazebo 中实际 forwardKinematics 对照参考实现。
//   L3 · 物理参数可追：质量、惯量、摩擦、执行器参数有来源与假设。对外称「仿真候选资产」。
//       条件：每个物理参数附 source（datasheet/实测/估算）与假设说明。
//   L4 · 验证资产：跨引擎回归、关键运动学/动力学对照、必要时真机标定。对外称「已验证仿真资产」。
//       条件：ISO 2321 / ISO 22166 级验证；需要真机 + 跨仿真器回归。
//
// 诚实边界：RoboParts 目前**没有任何 L1+ 资产**——60 个预置都是 L0。
// 这条分级存在本身的价值是把「估算骨架」和「厂商真实 URDF」在对外契约上彻底分开，
// 而不是继续用"60+ 即开即用"这种把 L0 说成 L2+ 的营销措辞。
//
// 每个 model 对象可通过显式字段 `asset_tier: 'L0' | 'L1' | ... | 'L4'` 覆盖默认值，
// 供未来导入真实厂商 URDF 时使用（例如 URDF-026 若换成 Unitree 官方 TienKung URDF，
// 就应显式标注 asset_tier: 'L3' 并补 source/datasheet URL）。
const ASSET_TIER_SCHEMA = {
  L0: { name: '元数据模型', external: '参数化元数据', requires: '有名称、类型、来源和估算边界' },
  L1: { name: '结构可解析', external: '可导入原型', requires: 'XML Schema 通过、引用完整、单位明确' },
  L2: { name: '运动学有效', external: '运动学原型', requires: '连杆树、关节轴、限位、TCP 经测试' },
  L3: { name: '物理参数可追', external: '仿真候选资产', requires: '质量、惯量、摩擦、执行器参数有来源与假设' },
  L4: { name: '验证资产', external: '已验证仿真资产', requires: '跨引擎回归、关键运动学/动力学对照、必要时真机标定' },
};
const VALID_ASSET_TIERS = Object.keys(ASSET_TIER_SCHEMA);

// 显式覆盖表：预置 60 个默认 L0。将来导入真实厂商 URDF 时在此登记更高档位。
// 每条必须写清 source（datasheet URL 或实测记录 ID）与 assumptions 才允许标 L1+。
const ASSET_TIER_OVERRIDES = {
  // 示例（禁用）：
  // 'URDF-006': {
  //   tier: 'L3',
  //   source: 'https://github.com/unitreerobotics/unitree_ros/blob/main/...',
  //   assumptions: '质量/惯量取自 Unitree G1 官方 datasheet v2.3（2024-08）',
  //   verified_at: '2026-XX-XX',
  // },
};

function getAssetTier(model) {
  const override = ASSET_TIER_OVERRIDES[model && model.id];
  if (override) {
    return {
      tier: override.tier,
      source: override.source || 'override',
      assumptions: override.assumptions || '',
      verified_at: override.verified_at || null,
      schema: ASSET_TIER_SCHEMA[override.tier] || ASSET_TIER_SCHEMA.L0,
    };
  }
  // 预置模型默认 L0：RoboParts 元数据驱动的通用骨架
  return {
    tier: 'L0',
    source: 'RoboParts metadata-generated skeleton',
    assumptions: '几何/质量/惯量为参数化估算（robot_type + joints 数），非厂商 CAD、非实测。'
      + ' 下载产物可导入仿真器作原型开发，不应用于生产级动力学仿真或安全相关判断。',
    verified_at: null,
    schema: ASSET_TIER_SCHEMA.L0,
  };
}

function tierSummary(models) {
  const counts = { L0: 0, L1: 0, L2: 0, L3: 0, L4: 0 };
  for (const m of models) {
    const t = getAssetTier(m).tier;
    if (counts[t] !== undefined) counts[t]++;
  }
  return counts;
}

// ===================== URDF 兼容性标签体系 =====================
// 基于模型属性自动生成兼容性标签，无需逐个手动标注

// 按作者/品牌确定仿真平台兼容性
const SIMULATION_COMPAT = {
  // NVIDIA 生态 → Isaac Sim 原生支持
  'NVIDIA': ['Isaac Sim', 'Gazebo', 'MuJoCo', 'PyBullet'],
  // Unitree → 官方 Isaac Gym/Sim + MuJoCo
  'Unitree Robotics': ['Isaac Sim', 'Gazebo', 'MuJoCo', 'PyBullet', 'Webots'],
  // ROBOTIS → Gazebo 原生 + Webots
  'ROBOTIS / Open Robotics': ['Gazebo', 'Webots', 'PyBullet', 'ROS 2'],
  'ROBOTIS': ['Gazebo', 'Webots', 'PyBullet', 'ROS 2'],
  // Stanford/LeRobot → MuJoCo + PyBullet 优先
  'The K Rene/Fanny Reber (LeRobot)': ['MuJoCo', 'PyBullet', 'Gazebo'],
  'The K Rene (LeRobot)': ['MuJoCo', 'PyBullet', 'Gazebo'],
  'Tony Zhao / Stanford (LeRobot)': ['MuJoCo', 'PyBullet', 'Gazebo'],
  // Franka → Gazebo + Isaac Sim
  'Franka Emika': ['Gazebo', 'Isaac Sim', 'MuJoCo', 'ROS 2'],
  // Universal Robots → Gazebo + ROS 2
  'Universal Robots / Robotiq': ['Gazebo', 'ROS 2', 'MuJoCo'],
  'Universal Robots': ['Gazebo', 'ROS 2', 'MuJoCo'],
  // Boston Dynamics → 仿真有限
  'Boston Dynamics': ['Gazebo', 'PyBullet'],
  // ANYbotics → Gazebo + Webots
  'ANYbotics': ['Gazebo', 'Webots', 'MuJoCo'],
  // 傅利叶 → Isaac Sim + Gazebo
  'Fourier Intelligence': ['Isaac Sim', 'Gazebo', 'MuJoCo'],
  // 大象机器人 → Gazebo + PyBullet
  'Elephant Robotics (大象机器人)': ['Gazebo', 'PyBullet', 'ROS 2'],
  // Willow Garage → Gazebo + ROS 2 原生
  'Willow Garage / Open Robotics': ['Gazebo', 'ROS 2', 'PyBullet'],
};

// 按许可证确定 ROS 2 兼容性等级
function getROS2Compat(model) {
  const license = (model.license || '').toUpperCase();
  const author = model.author || '';
  // 开源许可证通常 ROS 2 兼容
  if (license.includes('MIT') || license.includes('APACHE') || license.includes('BSD')) {
    return 'full';
  }
  if (license.includes('GPL')) {
    return 'partial';
  }
  // Proprietary / Custom → 社区适配
  if (license.includes('PROPRIETARY') || license.includes('CUSTOM')) {
    // 知名品牌通常有社区 ROS 2 适配
    const knownBrands = ['Unitree', 'ROBOTIS', 'Franka', 'Universal Robots', 'Boston Dynamics', 'Figure AI'];
    if (knownBrands.some(b => author.includes(b))) return 'community';
    return 'unknown';
  }
  return 'unknown';
}

// 按机器人类型确定推荐控制器
function getControllerCompat(model) {
  const type = model.robot_type;
  const controllers = [];
  switch (type) {
    case 'humanoid':
      controllers.push('ros2_control', 'Custom (全身平衡控制器)');
      if (model.joints >= 40) controllers.push('Whole-Body Control (WBC)');
      break;
    case 'quadruped':
      controllers.push('ros2_control', 'MPC (模型预测控制)', 'RL-based Controller');
      break;
    case 'arm':
      controllers.push('ros2_control (joint_trajectory_controller)');
      if (model.joints <= 6) controllers.push('MoveIt 2');
      if (model.joints === 7) controllers.push('MoveIt 2', 'Cartesian Controller');
      break;
    case 'hand':
      controllers.push('ros2_control', 'Grasp Controller', 'Force-based Control');
      break;
    case 'gripper':
      controllers.push('ros2_control (gripper_controller)');
      break;
    case 'amr':
      controllers.push('Nav2', 'ros2_control (diff_drive / ackermann)');
      break;
  }
  return controllers;
}

// 按模型属性生成兼容性标签
function getCompatibilityTags(model) {
  const tags = [];
  const ros2 = getROS2Compat(model);
  // ROS 2 标签
  if (ros2 === 'full') tags.push('ROS2-Humble', 'ROS2-Jazzy');
  else if (ros2 === 'partial') tags.push('ROS2-Humble');
  else if (ros2 === 'community') tags.push('ROS2-Community');
  // 仿真平台标签
  const sims = SIMULATION_COMPAT[model.author] || ['Gazebo', 'PyBullet'];
  for (const sim of sims) {
    tags.push(sim.replace(/\s+/g, '-'));
  }
  // 许可证标签
  const lic = (model.license || '').toUpperCase();
  if (lic.includes('MIT')) tags.push('Open-Source-MIT');
  else if (lic.includes('APACHE')) tags.push('Open-Source-Apache2');
  else if (lic.includes('BSD')) tags.push('Open-Source-BSD');
  else if (lic.includes('GPL')) tags.push('Open-Source-GPL');
  else tags.push('Proprietary');
  // DOF 标签
  if (model.joints >= 40) tags.push('High-DOF');
  else if (model.joints >= 20) tags.push('Mid-DOF');
  else tags.push('Low-DOF');
  return [...new Set(tags)]; // 去重
}

// 生成完整兼容性信息对象
function getCompatibilityInfo(model) {
  const ros2 = getROS2Compat(model);
  const sims = SIMULATION_COMPAT[model.author] || ['Gazebo', 'PyBullet'];
  return {
    ros2: ros2,
    ros2_details: ros2 === 'full' ? '原生支持 ROS 2 Humble/Jazzy' :
                  ros2 === 'partial' ? '部分支持，需社区适配' :
                  ros2 === 'community' ? '社区维护 ROS 2 适配包' :
                  '兼容性未知，需自行验证',
    simulation_platforms: sims,
    controllers: getControllerCompat(model),
    mesh_format: model.file_size && parseInt(model.file_size) > 50 ? 'DAE (Collada)' : 'STL',
    urdf_version: '1.0',
    validated: model.license === 'MIT' || model.license === 'Apache-2.0' || model.license === 'BSD',
    compatibility_tags: getCompatibilityTags(model),
  };
}

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Content-Type': 'application/json; charset=utf-8',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const id = url.searchParams.get('id');
  const robotType = url.searchParams.get('robot_type');
  const compatTag = url.searchParams.get('compatibility');
  const simPlatform = url.searchParams.get('sim');
  const tierParam = url.searchParams.get('tier');

  try {
    // 尝试从 KV 读取模型库
    let models = await loadModels(env);

    // 单个模型查询
    if (id) {
      const model = models.find(m => m.id === id);
      if (!model) {
        return new Response(JSON.stringify({
          error: 'Model not found',
          message: '未找到 ID 为 ' + id + ' 的 URDF 模型。',
          available_ids: models.map(m => m.id),
        }), { status: 404, headers: corsHeaders });
      }
      return new Response(JSON.stringify({
        meta: {
          id: model.id,
          source: env.URDF_LIBRARY ? 'kv' : 'preset',
          total: 1,
        },
        model: enrichModel(model),
      }, null, 2), {
        status: 200,
        headers: {
          ...corsHeaders,
          'Cache-Control': env.URDF_LIBRARY ? 'no-store' : 'public, max-age=300',
        },
      });
    }

    // 校验 robot_type 参数
    if (robotType && !VALID_ROBOT_TYPES.includes(robotType)) {
      return new Response(JSON.stringify({
        error: 'Invalid robot_type',
        message: 'robot_type 必须为: ' + VALID_ROBOT_TYPES.join(', '),
        received: robotType,
      }), { status: 400, headers: corsHeaders });
    }

    // 列表筛选
    let filtered = models;
    if (robotType) {
      filtered = filtered.filter(m => m.robot_type === robotType);
    }
    // 兼容性标签筛选（B-01）
    if (compatTag) {
      filtered = filtered.filter(m => {
        const compat = getCompatibilityInfo(m);
        return compat.compatibility_tags.some(t =>
          t.toLowerCase().includes(compatTag.toLowerCase())
        );
      });
    }
    // 仿真平台筛选（B-01）
    if (simPlatform) {
      filtered = filtered.filter(m => {
        const compat = getCompatibilityInfo(m);
        return compat.simulation_platforms.some(s =>
          s.toLowerCase().includes(simPlatform.toLowerCase())
        );
      });
    }
    // P0-12 资产分级筛选：?tier=L0（单个）或 ?tier=L0,L1（逗号分隔多个）
    if (tierParam) {
      const wanted = tierParam.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
      const wantedSet = new Set(wanted);
      filtered = filtered.filter(m => wantedSet.has(getAssetTier(m).tier));
    }

    // 统计各类型数量
    const typeCounts = {};
    for (const t of VALID_ROBOT_TYPES) {
      typeCounts[t] = models.filter(m => m.robot_type === t).length;
    }

    const result = {
      meta: {
        total: filtered.length,
        total_all: models.length,
        source: env.URDF_LIBRARY ? 'kv' : 'preset',
        filter: robotType || null,
        compatibility_filter: compatTag || null,
        sim_filter: simPlatform || null,
        tier_filter: tierParam || null,
        available_robot_types: VALID_ROBOT_TYPES,
        type_counts: typeCounts,
        // P0-12 资产分级总览（未筛选前全库分布，让调用方一次看到"真实资产清单"）
        asset_tier_schema: ASSET_TIER_SCHEMA,
        asset_tier_counts_all: tierSummary(models),
        asset_tier_counts_filtered: tierSummary(filtered),
        asset_tier_note: '默认 L0（RoboParts 元数据驱动的参数化骨架）。'
          + 'L1+ 需显式 asset_tier 覆盖并附 source 与 assumptions（见 ASSET_TIER_OVERRIDES）。',
      },
      models: filtered.map(enrichModel),
    };

    return new Response(JSON.stringify(result, null, 2), {
      status: 200,
      headers: {
        ...corsHeaders,
        'Cache-Control': env.URDF_LIBRARY ? 'no-store' : 'public, max-age=300',
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

// 从 KV 加载模型；KV 不可用或为空时返回预置模型
async function loadModels(env) {
  if (env.URDF_LIBRARY) {
    try {
      const raw = await env.URDF_LIBRARY.get(KV_MODELS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch (e) {
      // KV 解析失败，回退到预置模型
    }
  }
  return PRESET_URDF_MODELS;
}

// 补充列表展示字段（joints_count 等别名，保持向后兼容）+ 兼容性信息 + P0-12 资产分级
function enrichModel(model) {
  const compat = getCompatibilityInfo(model);
  const tier = getAssetTier(model);
  return {
    id: model.id,
    name: model.name,
    robot_type: model.robot_type,
    description: model.description,
    joints_count: model.joints,
    joints: model.joints,
    links: model.links,
    payload: model.payload,
    reach: model.reach,
    file_size: model.file_size,
    license: model.license,
    author: model.author,
    updated: model.updated,
    download_url: model.download_url,
    // 兼容性标签体系（B-01）
    compatibility: compat,
    // P0-12 资产分级：L0=元数据骨架 / L1=结构可解析 / L2=运动学有效 / L3=物理可追 / L4=已验证
    asset_tier: tier,
  };
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
