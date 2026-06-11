// ==========================================
// RoboLink - 配置文件
// 请替换为你的 Supabase 项目凭据
// 获取方式: supabase.com > 项目设置 > API
// ==========================================

const SUPABASE_CONFIG = {
  // 替换为你的 Supabase Project URL
  url: 'https://pendpzoycfngylrrbwon.supabase.co',
  // 替换为你的 Supabase Anon (public) Key
  anonKey: 'sb_publishable_Cm0je2pGSzSctnoNJh7wig_qsw-YxDo',
};

// 域名配置（部署后替换为你的实际域名）
const SITE_CONFIG = {
  domain: 'roboparts.cc',
  siteName: 'RoboParts',
  siteUrl: 'https://roboparts.cc',
  siteDescription: 'RoboLink是面向机器人创客和爱好者的零件对接平台，提供零件选型、兼容性检查、STL转接件下载、3D打印代打和社区交流。',
};

// 3D打印服务追踪配置
const PRINT_PARTNERS = {
  jlc: {
    name: '嘉立创3D打印',
    url: 'https://www.jlc-3dp.cn/',
    commission: 0.05, // 5% 佣金比例（示例）
  },
  mohou: {
    name: '魔猴网',
    url: 'https://www.mohou.com/',
    commission: 0.05,
  },
};

// 导购追踪配置（已启用淘宝搜索链接）
const AFFILIATE_CONFIG = {
  enabled: true,
  // 各品牌跳转淘宝搜索（用户后续可替换为淘宝客PID实现佣金）
  // 注册淘宝客: https://pub.alimama.com → 获取PID后替换链接中的 &pid=YOUR_PID
  brandLinks: {
    '慧灵科技': 'https://s.taobao.com/search?q=慧灵',
    '大寰机器人': 'https://s.taobao.com/search?q=大寰机器人',
    '柔触机器人': 'https://s.taobao.com/search?q=柔触机器人',
    '沃姆机器人': 'https://s.taobao.com/search?q=沃姆机器人',
    '天机机器人': 'https://s.taobao.com/search?q=天机机器人',
    '一元智能': 'https://s.taobao.com/search?q=一元智能+夹爪',
    '知行机器人': 'https://s.taobao.com/search?q=知行机器人',
    'DOBOT': 'https://s.taobao.com/search?q=越疆+DOBOT',
    'Robotiq': 'https://s.taobao.com/search?q=Robotiq',
    'OnRobot': 'https://s.taobao.com/search?q=OnRobot',
    'Schunk': 'https://s.taobao.com/search?q=Schunk+夹爪',
    'Festo': 'https://s.taobao.com/search?q=Festo+夹爪',
    'Universal Robots': 'https://s.taobao.com/search?q=优傲机器人',
    'Franka Emika': 'https://s.taobao.com/search?q=Franka+机器人',
    'HIWIN': 'https://s.taobao.com/search?q=HIWIN+机器人',
    'AUBO': 'https://s.taobao.com/search?q=遨博机器人',
    'Elephant Robotics': 'https://s.taobao.com/search?q=大象机器人+myCobot',
    'uArm': 'https://s.taobao.com/search?q=uArm+机械臂',
    'LoFi Robot': 'https://s.taobao.com/search?q=LoFi+机器人',
    '矽递科技': 'https://s.taobao.com/search?q=矽递科技+机械臂',
    'SO-ARM': 'https://s.taobao.com/search?q=SO-ARM',
    'CRobot': 'https://s.taobao.com/search?q=CRobot',
    '通用舵机': 'https://s.taobao.com/search?q=',
  },
};
