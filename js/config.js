// ==========================================
// RoboLink - 配置文件
// 请替换为你的 Supabase 项目凭据
// 获取方式: supabase.com > 项目设置 > API
// ==========================================

const SUPABASE_CONFIG = {
  // 替换为你的 Supabase Project URL
  url: 'YOUR_SUPABASE_URL_HERE',
  // 替换为你的 Supabase Anon (public) Key
  anonKey: 'YOUR_SUPABASE_ANON_KEY_HERE',
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

// 导购追踪配置
const AFFILIATE_CONFIG = {
  enabled: false, // 启用后，零件卡片会显示"去购买"按钮
  // 各品牌的购买链接模板（后续配置）
  brandLinks: {
    '慧灵科技': 'https://detail.1688.com/search?q=',
    '大寰机器人': 'https://detail.1688.com/search?q=',
    '柔触机器人': 'https://detail.1688.com/search?q=',
    '沃姆机器人': 'https://detail.1688.com/search?q=',
    '天机机器人': 'https://detail.1688.com/search?q=',
    '一元智能': 'https://detail.1688.com/search?q=',
    'DOBOT': 'https://www.dobot.cc/',
    'Robotiq': 'https://robotiq.com/products/',
    'OnRobot': 'https://onrobot.com/products/',
    '通用舵机': 'https://detail.1688.com/search?q=',
  },
};
