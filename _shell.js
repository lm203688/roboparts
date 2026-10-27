/* RoboParts 统一 Shell 注入脚本
 * 运行时向页面注入：顶部导航 / 面包屑 / 下一步 CTA / 底部页脚
 * 幂等：多次加载不会重复注入
 *
 * 页面通过 data-* 属性定制：
 *   <script src="/_shell.js" data-rp-section="selection" data-rp-next="bom-check"></script>
 * 或通过 <meta name="rp-section" content="...">
 *
 * Section 分组（7 大类）：
 *   selection  — 选型：selection / co-mount / iso-9409-flange / robot-joint-parameter-spec
 *   planner    — 规划：build-planner / bom-manager / bom-import / reference-builds
 *   design     — 设计：designer / adapter-generator / bom-checker / assembly
 *   data       — 数据：data-hub / parts-viewer / urdf-library / standard-audit / robot-joint-parameter-spec
 *   agent      — Agent：copilot / mcp-guide / agent-architecture / agent-discovery
 *   oss        — 开源与协议：oss / spec-declare / contributors / credits / credits-history
 *   commerce   — 商业：pricing / api-pricing / order / suppliers / supplier-admin / credits
 *   community  — 社区：waitlist / funnel / scoreboard / bionic / promotion
 *   about      — 关于：index / demo-flow / geo-dashboard / compatibility-viz / compatibility-viewer / promo-poster / 404
 */
(function () {
  'use strict';
  if (window.__rpShellInjected) return;
  window.__rpShellInjected = true;

  var SHELL_CSS_HREF = '/_shell.css';

  // ===================== P1-6 主链路埋点（2026-10-26） =====================
  // 背景：审计发现 29 调用 0 注册，但**没有数据**能回答"用户在哪一步流失"。
  // 此前只有 page_view 级统计，无 feature_use 埋点、无漏斗、无 session 归因。
  // 本模块是最小可行漏斗：page_view + feature_use（5 主链页面）+ session_id。
  //
  // 纪律：
  //   · 静默失败——API 挂了不阻塞页面（fire-and-forget）
  //   · 零依赖——不引第三方 SDK，纯 fetch + sendBeacon
  //   · 隐私优先——无 PII，session_id 是随机 UUID，不追踪个人
  //   · 隐私策略：docs/PRIVACY.md 已声明数据仅用于产品改进、可关闭（?rp_no_track=1）
  //   · 用户可关闭：URL 带 ?rp_no_track=1 或 localStorage rp_no_track=1 时不上报
  //
  // 事件契约（与 functions/api/analytics/events.js 对齐）：
  //   event_type: page_view | feature_use | signup | trial_start | ...
  //   event_data: { page, section, feature, ... } 自由结构
  //   session_id: 跨页持久的随机 UUID（30 天 TTL）
  //   user_id: null（未登录）
  // =========================================================================

  var TRACK_ENDPOINT = '/api/analytics/events';
  var SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000; // 30 天
  var SESSION_KEY = 'rp_session_id';
  var SESSION_TS_KEY = 'rp_session_ts';
  var NO_TRACK_KEY = 'rp_no_track';

  function optOut() {
    try {
      if (new URLSearchParams(location.search).get('rp_no_track') === '1') return true;
      return localStorage.getItem(NO_TRACK_KEY) === '1';
    } catch (e) { return false; }
  }

  function getSessionId() {
    try {
      var sid = localStorage.getItem(SESSION_KEY);
      var ts = parseInt(localStorage.getItem(SESSION_TS_KEY) || '0', 10);
      if (sid && ts && (Date.now() - ts) < SESSION_TTL_MS) return sid;
      // 生成新 session
      sid = 's_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 10);
      localStorage.setItem(SESSION_KEY, sid);
      localStorage.setItem(SESSION_TS_KEY, String(Date.now()));
      return sid;
    } catch (e) {
      return 's_ephemeral_' + Math.random().toString(36).slice(2, 8);
    }
  }

  // 主链页面 → feature 名映射（5 步主链）
  var PIPELINE_FEATURES = {
    'selection.html': 'selection',
    'build-planner.html': 'build_planner',
    'designer.html': 'designer',
    'bom-checker.html': 'bom_checker',
    'adapter-generator.html': 'adapter_generator',
  };

  function sendEvent(eventType, eventData) {
    if (optOut()) return;
    var payload = {
      event_type: eventType,
      event_data: eventData || {},
      session_id: getSessionId(),
      user_id: null,
      timestamp: new Date().toISOString(),
    };
    try {
      // 优先 sendBeacon（页面卸载时也能发送），失败退回 fetch
      var body = JSON.stringify(payload);
      if (navigator.sendBeacon) {
        var ok = navigator.sendBeacon(TRACK_ENDPOINT, new Blob([body], { type: 'application/json' }));
        if (ok) return;
      }
      fetch(TRACK_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body,
        keepalive: true,
      }).catch(function () {});
    } catch (e) {
      // 静默——埋点失败不影响页面
    }
  }

  // 暴露给页面脚本调用：window.rpTrack(event_type, data)
  window.rpTrack = sendEvent;

  // 首次加载：page_view + 主链 feature_use（如果有）
  function trackPageView() {
    if (optOut()) return;
    var path = location.pathname;
    var filename = path.split('/').pop() || 'index.html';
    var section = 'unknown';
    // 从 PAGE_META 推断 section（下方定义，此处只做粗分类）
    var pipelineFeature = PIPELINE_FEATURES[filename];
    var eventData = {
      page: filename,
      path: path,
      referrer: document.referrer || null,
      has_referrer: !!document.referrer,
    };
    sendEvent('page_view', eventData);
    if (pipelineFeature) {
      // 主链页面：额外发一个 feature_use（进入即算"开始使用"）
      sendEvent('feature_use', { feature: pipelineFeature, page: filename });
    }
  }

  // 延迟到 DOM 就绪后上报，避免在页面未完全加载前就发送（referrer 可能为空）
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      // 再延迟一点，让 referrer 稳定
      setTimeout(trackPageView, 100);
    });
  } else {
    setTimeout(trackPageView, 100);
  }

  // ===================== 配置 =====================
  var NAV = [
    { group: 'core', items: [
      { s: 'index',        href: '/index.html',          label: '首页' },
      { s: 'demo-flow',    href: '/demo-flow.html',      label: '▶ 快速上手' },
    ]},
    { group: 'pipeline', items: [
      { s: 'selection',    href: '/selection.html',      label: '① 选型' },
      { s: 'planner',      href: '/build-planner.html',  label: '② 规划' },
      { s: 'design',       href: '/designer.html',       label: '③ 设计' },
      { s: 'design',       href: '/bom-checker.html',    label: '④ BOM 校验' },
      { s: 'design',       href: '/adapter-generator.html', label: '⑤ 转接件' },
      { s: 'design',       href: '/compose-workbench.html', label: '🛠️ 组合工作台' },
    ]},
    { group: 'data', items: [
      { s: 'data',         href: '/data-hub.html',       label: '数据中枢' },
      { s: 'data',         href: '/parts-viewer.html',   label: '零件库' },
      { s: 'data',         href: '/urdf-library.html',   label: 'URDF 库' },
    ]},
    { group: 'agent', items: [
      { s: 'agent',        href: '/copilot.html',        label: 'AI Copilot' },
      { s: 'agent',        href: '/mcp-guide.html',      label: 'MCP' },
    ]},
    { group: 'about', items: [
      { s: 'oss',          href: '/oss.html',            label: '开源' },
      { s: 'commerce',     href: '/pricing.html',        label: '定价' },
    ]},
  ];

  var FOOTER = {
    about: {
      title: 'RoboParts',
      tag: '机器人零件兼容性判定层 · 中立第三方',
      links: [
        { href: '/index.html',          label: '首页' },
        { href: '/oss.html',            label: '开源与许可证' },
        { href: '/contributors.html',   label: '贡献者' },
        { href: '/data-hub.html',       label: '数据中枢' },
      ],
    },
    product: {
      title: '产品',
      links: [
        { href: '/selection.html',        label: '智能选型' },
        { href: '/build-planner.html',    label: 'Build Planner' },
        { href: '/designer.html',         label: '设计画布' },
        { href: '/bom-checker.html',      label: 'BOM 校验' },
        { href: '/adapter-generator.html', label: '转接件生成' },
        { href: '/compose-workbench.html', label: '组合工作台' },
        { href: '/assembly.html',         label: '装配级检查' },
      ],
    },
    agent: {
      title: 'Agent 接入',
      links: [
        { href: '/mcp-guide.html',        label: 'MCP 指南' },
        { href: '/copilot.html',          label: 'AI Copilot' },
        { href: '/agent-architecture.html', label: '架构' },
        { href: '/api-pricing.html',      label: 'API 定价' },
      ],
    },
    resources: {
      title: '资源',
      links: [
        { href: '/data-hub.html',          label: '数据集' },
        { href: '/iso-9409-flange.html',   label: 'ISO 9409-1 法兰' },
        { href: '/standard-audit.html',    label: '国标审计' },
        { href: '/robots.txt',             label: 'robots.txt' },
        { href: '/llms.txt',               label: 'llms.txt' },
      ],
    },
  };

  // 页面→栏目/下一步映射
  var PAGE_META = {
    'index.html':             { section: 'about',    breadcrumb: ['首页'], next: { title: '从选型开始', btns: [{ href: '/selection.html', label: '▶ 选型引擎' }, { href: '/demo-flow.html', label: '快速上手' }] } },
    'demo-flow.html':         { section: 'about',    breadcrumb: ['首页', '快速上手'], next: { title: '开始选型', btns: [{ href: '/selection.html', label: '▶ 选型引擎' }] } },
    'selection.html':         { section: 'selection', breadcrumb: ['首页', '选型'], next: { title: '选型完成？进入规划', btns: [{ href: '/build-planner.html', label: '▶ Build Planner' }, { href: '/co-mount.html', label: '共装检查' }] } },
    'co-mount.html':          { section: 'selection', breadcrumb: ['首页', '选型', '共装检查'], next: { title: '需要转接件？', btns: [{ href: '/adapter-generator.html', label: '▶ 转接件生成' }] } },
    'build-planner.html':     { section: 'planner',   breadcrumb: ['首页', '规划'], next: { title: '规划完成？进入设计画布', btns: [{ href: '/designer.html', label: '▶ 设计画布' }, { href: '/bom-checker.html', label: 'BOM 校验' }] } },
    'bom-manager.html':       { section: 'planner',   breadcrumb: ['首页', '规划', 'BOM 管理'], next: { title: '导入 BOM 或校验', btns: [{ href: '/bom-import.html', label: '▶ BOM 导入' }, { href: '/bom-checker.html', label: 'BOM 校验' }] } },
    'bom-import.html':        { section: 'planner',   breadcrumb: ['首页', '规划', 'BOM 导入'], next: { title: '导入后运行校验', btns: [{ href: '/bom-checker.html', label: '▶ BOM 校验' }] } },
    'reference-builds.html':  { section: 'planner',   breadcrumb: ['首页', '规划', '参考构型'], next: { title: '基于参考构型规划', btns: [{ href: '/build-planner.html', label: '▶ Build Planner' }] } },
    'designer.html':          { section: 'design',    breadcrumb: ['首页', '设计'], next: { title: '设计完成？进入 BOM 校验', btns: [{ href: '/bom-checker.html', label: '▶ BOM 校验' }, { href: '/adapter-generator.html', label: '转接件生成' }] } },
    'adapter-generator.html': { section: 'design',    breadcrumb: ['首页', '设计', '转接件生成'], next: { title: '生成后运行 BOM 校验', btns: [{ href: '/bom-checker.html', label: '▶ BOM 校验' }] } },
    'bom-checker.html':       { section: 'design',    breadcrumb: ['首页', '设计', 'BOM 校验'], next: { title: '校验结果有 type_error？生成转接件', btns: [{ href: '/adapter-generator.html', label: '▶ 转接件生成' }, { href: '/assembly.html', label: '装配级检查' }] } },
    'assembly.html':          { section: 'design',    breadcrumb: ['首页', '设计', '装配级检查'], next: { title: '回到 BOM 校验', btns: [{ href: '/bom-checker.html', label: '▶ BOM 校验' }] } },
    'compose-workbench.html': { section: 'design',    breadcrumb: ['首页', '设计', '组合工作台'], next: { title: '组合完成？校验 BOM', btns: [{ href: '/bom-checker.html', label: '▶ BOM 校验' }, { href: '/adapter-generator.html', label: '转接件生成' }] } },
    'data-hub.html':          { section: 'data',      breadcrumb: ['首页', '数据中枢'], next: { title: '浏览零件库', btns: [{ href: '/parts-viewer.html', label: '▶ 零件库' }] } },
    'parts-viewer.html':      { section: 'data',      breadcrumb: ['首页', '数据中枢', '零件库'], next: { title: '选型 / 校验', btns: [{ href: '/selection.html', label: '▶ 选型' }, { href: '/bom-checker.html', label: 'BOM 校验' }] } },
    'urdf-library.html':      { section: 'data',      breadcrumb: ['首页', '数据中枢', 'URDF 库'], next: { title: '查看 ISO 9409 法兰', btns: [{ href: '/iso-9409-flange.html', label: '▶ ISO 9409-1' }] } },
    'iso-9409-flange.html':   { section: 'data',      breadcrumb: ['首页', '数据中枢', 'ISO 9409-1 法兰'], next: { title: '生成转接件', btns: [{ href: '/adapter-generator.html', label: '▶ 转接件生成' }] } },
    'standard-audit.html':    { section: 'data',      breadcrumb: ['首页', '数据中枢', '国标审计'], next: { title: '查看数据中枢', btns: [{ href: '/data-hub.html', label: '▶ 数据中枢' }] } },
    'robot-joint-parameter-spec.html': { section: 'data', breadcrumb: ['首页', '数据中枢', '关节参数规范'], next: { title: '回到数据中枢', btns: [{ href: '/data-hub.html', label: '▶ 数据中枢' }] } },
    'copilot.html':           { section: 'agent',     breadcrumb: ['首页', 'AI Copilot'], next: { title: '接入你自己的 Agent', btns: [{ href: '/mcp-guide.html', label: '▶ MCP 指南' }] } },
    'mcp-guide.html':         { section: 'agent',     breadcrumb: ['首页', 'MCP 指南'], next: { title: '试用 Copilot', btns: [{ href: '/copilot.html', label: '▶ Copilot' }, { href: '/agent-architecture.html', label: '架构' }] } },
    'agent-architecture.html':{ section: 'agent',     breadcrumb: ['首页', 'Agent 架构'], next: { title: '看 MCP 指南', btns: [{ href: '/mcp-guide.html', label: '▶ MCP 指南' }] } },
    'oss.html':               { section: 'oss',       breadcrumb: ['首页', '开源'], next: { title: '贡献 / 查看协议', btns: [{ href: '/contributors.html', label: '▶ 贡献者' }, { href: '/spec-declare.html', label: 'Spec 声明' }] } },
    'spec-declare.html':      { section: 'oss',       breadcrumb: ['首页', '开源', 'Spec 声明'], next: { title: '加入贡献', btns: [{ href: '/contributors.html', label: '▶ 贡献者' }] } },
    'contributors.html':      { section: 'oss',       breadcrumb: ['首页', '贡献者'], next: { title: '查看开源政策', btns: [{ href: '/oss.html', label: '▶ 开源' }] } },
    'credits.html':           { section: 'commerce',  breadcrumb: ['首页', '积分'], next: { title: '了解定价', btns: [{ href: '/pricing.html', label: '▶ 定价' }] } },
    'credits-history.html':   { section: 'commerce',  breadcrumb: ['首页', '积分', '历史'], next: { title: '返回积分页', btns: [{ href: '/credits.html', label: '▶ 积分' }] } },
    'pricing.html':           { section: 'commerce',  breadcrumb: ['首页', '定价'], next: { title: '查看 API 定价', btns: [{ href: '/api-pricing.html', label: '▶ API 定价' }, { href: '/order.html', label: '下单' }] } },
    'api-pricing.html':       { section: 'commerce',  breadcrumb: ['首页', '定价', 'API'], next: { title: '回到主定价', btns: [{ href: '/pricing.html', label: '▶ 定价' }] } },
    'order.html':             { section: 'commerce',  breadcrumb: ['首页', '下单'], next: { title: '查看定价', btns: [{ href: '/pricing.html', label: '▶ 定价' }] } },
    'suppliers.html':         { section: 'commerce',  breadcrumb: ['首页', '供应商'], next: { title: '提交询价', btns: [{ href: '/supplier-admin.html', label: '▶ 供应商管理' }] } },
    'supplier-admin.html':    { section: 'commerce',  breadcrumb: ['首页', '供应商管理'], next: { title: '回到供应商页', btns: [{ href: '/suppliers.html', label: '▶ 供应商' }] } },
    'waitlist.html':          { section: 'community', breadcrumb: ['首页', '等待名单'], next: { title: '查看定价', btns: [{ href: '/pricing.html', label: '▶ 定价' }] } },
    'funnel.html':            { section: 'community', breadcrumb: ['首页', '转化漏斗'], next: { title: '开始选型', btns: [{ href: '/selection.html', label: '▶ 选型' }] } },
    'scoreboard.html':        { section: 'community', breadcrumb: ['首页', '积分榜'], next: { title: '开始选型', btns: [{ href: '/selection.html', label: '▶ 选型' }] } },
    'bionic.html':            { section: 'community', breadcrumb: ['首页', '仿生兼容层'], next: { title: '回到首页', btns: [{ href: '/index.html', label: '▶ 首页' }] } },
    'promotion.html':         { section: 'community', breadcrumb: ['首页', '推广'], next: { title: '查看定价', btns: [{ href: '/pricing.html', label: '▶ 定价' }] } },
    'geo-dashboard.html':     { section: 'about',     breadcrumb: ['首页', '地理看板'], next: { title: '回到首页', btns: [{ href: '/index.html', label: '▶ 首页' }] } },
    'compatibility-viz.html': { section: 'about',     breadcrumb: ['首页', '兼容性可视化'], next: { title: '回到首页', btns: [{ href: '/index.html', label: '▶ 首页' }] } },
    'compatibility-viewer.html': { section: 'about',  breadcrumb: ['首页', '兼容性查看器'], next: { title: '回到首页', btns: [{ href: '/index.html', label: '▶ 首页' }] } },
    'promo-poster.html':      { section: 'about',     breadcrumb: ['首页', '推广海报'], next: { title: '回到首页', btns: [{ href: '/index.html', label: '▶ 首页' }] } },
    '404.html':               { section: 'about',     breadcrumb: ['首页', '404'], next: { title: '返回站点', btns: [{ href: '/index.html', label: '▶ 首页' }] } },
  };

  // ===================== 工具 =====================
  function currentPageName() {
    var p = location.pathname.split('/').pop() || 'index.html';
    if (p === '') p = 'index.html';
    // 移除 .html 之外的 query
    return p;
  }
  function getMetaValue(name) {
    var el = document.querySelector('meta[name="' + name + '"]');
    return el ? el.getAttribute('content') : null;
  }
  function getScriptMeta() {
    var scripts = document.querySelectorAll('script[src*="/_shell.js"]');
    for (var i = 0; i < scripts.length; i++) {
      var s = scripts[i];
      var section = s.getAttribute('data-rp-section');
      var next = s.getAttribute('data-rp-next');
      if (section || next) return { section: section, next: next };
    }
    return {};
  }
  function resolveMeta() {
    var page = currentPageName();
    var meta = PAGE_META[page] || { section: 'about', breadcrumb: ['首页', page], next: { title: '回到首页', btns: [{ href: '/index.html', label: '▶ 首页' }] } };
    var overrides = getScriptMeta();
    if (overrides.section) meta.section = overrides.section;
    if (overrides.next) {
      try { meta.next = JSON.parse(overrides.next); } catch (e) {}
    }
    var pageSectionOverride = getMetaValue('rp-section');
    if (pageSectionOverride) meta.section = pageSectionOverride;
    return meta;
  }
  function isLegacyHeaderPresent() {
    // 只检测 <header> 元素（不含_rp-shell-header）
    var headers = document.querySelectorAll('header:not(.rp-shell-header)');
    for (var i = 0; i < headers.length; i++) {
      if (headers[i].offsetParent !== null || headers[i].offsetHeight > 0) return true;
    }
    return false;
  }

  // ===================== 渲染 =====================
  function renderShell() {
    var meta = resolveMeta();

    // 加载 CSS
    if (!document.getElementById('rp-shell-css')) {
      var link = document.createElement('link');
      link.id = 'rp-shell-css';
      link.rel = 'stylesheet';
      link.href = SHELL_CSS_HREF;
      document.head.appendChild(link);
    }

    // 检测旧 header：如果页面有 <header> 元素，标记 body，避免视觉重叠
    if (isLegacyHeaderPresent()) {
      document.body.classList.add('rp-has-legacy-header');
    }

    // ===== 顶部 header =====
    var header = document.createElement('header');
    header.className = 'rp-shell-header';
    header.setAttribute('role', 'banner');

    var inner = document.createElement('div');
    inner.className = 'rp-shell-header-inner';

    var logo = document.createElement('a');
    logo.href = '/index.html';
    logo.className = 'rp-shell-logo';
    logo.innerHTML = 'Robo<span>Parts</span>';
    inner.appendChild(logo);

    // nav
    var nav = document.createElement('nav');
    nav.className = 'rp-shell-nav';
    nav.setAttribute('aria-label', '主导航');
    var prevGroup = null;
    NAV.forEach(function (g) {
      if (prevGroup && prevGroup !== g.group) {
        var divider = document.createElement('span');
        divider.className = 'rp-shell-nav-divider';
        nav.appendChild(divider);
      }
      g.items.forEach(function (item) {
        var a = document.createElement('a');
        a.href = item.href;
        a.className = 'rp-shell-nav-item' + (meta.section === item.s ? ' active' : '');
        a.textContent = item.label;
        nav.appendChild(a);
      });
      prevGroup = g.group;
    });
    inner.appendChild(nav);

    // 五步流水线进度指示器（P1-1 前置：把 5 页流水线可见化）
    var PIPELINE_STEPS = [
      { id: 'selection', href: '/selection.html',         label: '① 选型',    sections: ['selection'] },
      { id: 'planner',   href: '/build-planner.html',     label: '② 规划',    sections: ['planner'] },
      { id: 'design',    href: '/designer.html',          label: '③ 设计',    sections: ['design'] },
      { id: 'bom',       href: '/bom-checker.html',       label: '④ BOM 校验', sections: ['design'] },
      { id: 'adapter',   href: '/adapter-generator.html', label: '⑤ 转接件',  sections: ['design'] },
    ];
    // 计算当前步：以 section 分组定位；同一 section 内按 nav items 顺序判
    var currentSection = meta.section;
    var currentStepIdx = -1;
    // 特殊：design section 里 designer→step2, bom-checker→step3, adapter-generator→step4
    var pageName = currentPageName();
    if (pageName === 'designer.html') currentStepIdx = 2;
    else if (pageName === 'bom-checker.html') currentStepIdx = 3;
    else if (pageName === 'adapter-generator.html') currentStepIdx = 4;
    else {
      for (var i = 0; i < PIPELINE_STEPS.length; i++) {
        if (PIPELINE_STEPS[i].sections.indexOf(currentSection) !== -1) {
          currentStepIdx = i;
          break;
        }
      }
    }

    // 判断用户在五步流水线内
    var inPipeline = currentStepIdx >= 0;
    if (inPipeline) {
      var pipeline = document.createElement('div');
      pipeline.className = 'rp-shell-pipeline';
      pipeline.setAttribute('aria-label', '五步流水线进度');

      var steps = document.createElement('div');
      steps.className = 'rp-shell-pipeline-steps';

      PIPELINE_STEPS.forEach(function (step, i) {
        // 步节点
        var s = document.createElement('a');
        s.href = step.href;
        var cls = 'rp-shell-pipeline-step';
        if (i < currentStepIdx) cls += ' done';
        else if (i === currentStepIdx) cls += ' current';
        s.className = cls;
        s.textContent = step.label;
        steps.appendChild(s);
        // 连接器
        if (i < PIPELINE_STEPS.length - 1) {
          var c = document.createElement('span');
          var ccls = 'rp-shell-pipeline-connector';
          if (i < currentStepIdx) ccls += ' done';
          else if (i === currentStepIdx) ccls += ' next';
          c.className = ccls;
          steps.appendChild(c);
        }
      });
      pipeline.appendChild(steps);

      // 进度计数
      var prog = document.createElement('span');
      prog.className = 'rp-shell-pipeline-progress';
      prog.innerHTML = '进度 <b>' + (currentStepIdx + 1) + '</b> / ' + PIPELINE_STEPS.length;
      pipeline.appendChild(prog);

      // 插在 nav 下面
      inner.insertBefore(pipeline, inner.children[2] || null);
    }

    // 搜索框
    var search = document.createElement('div');
    search.className = 'rp-shell-search';
    search.innerHTML = '<input id="rp-shell-search-input" type="search" placeholder="搜索零件 / 法兰 / BOM" aria-label="站内搜索"><button id="rp-shell-search-btn" type="button">🔍</button>';
    inner.appendChild(search);

    // ===== 项目徽章 (P1-1) =====
    // 显示当前 project 名称 + 下拉菜单（历史项目 / 新建 / 重置 / 分享）
    if (typeof window.RpProject === 'object') {
      var rpMenu = document.createElement('div');
      rpMenu.className = 'rp-shell-project-menu';
      rpMenu.id = 'rp-shell-project-menu';
      rpMenu.innerHTML = ''
        + '<button class="rp-shell-project-btn" id="rp-shell-project-btn" aria-haspopup="true" aria-expanded="false">'
        +   '<span class="rp-shell-project">'
        +     '<span class="rp-shell-project-dot"></span>'
        +     '<span class="rp-shell-project-name" id="rp-shell-project-name">加载中…</span>'
        +   '</span>'
        + '</button>'
        + '<div class="rp-shell-project-dropdown" id="rp-shell-project-dropdown" role="menu"></div>';
      inner.insertBefore(rpMenu, inner.lastElementChild);

      // 立即渲染当前 project
      (function renderProject(){
        try {
          var p = window.RpProject.all();
          var name = document.getElementById('rp-shell-project-name');
          if (name) name.textContent = p.name || '新构建';
        } catch (e) {}
      })();

      function renderDropdown(){
        try {
          var current = window.RpProject.all();
          var list = window.RpProject.list() || [];
          var steps = ['选型','规划','设计','BOM','转接件'];
          var html = '<div class="rp-shell-project-dropdown-header">历史项目 (' + list.length + ')</div>';
          if (!list.length) {
            html += '<div style="padding:8px 10px;color:#8a96b0;font-size:12px">还没有历史项目</div>';
          }
          list.forEach(function (item) {
            var isActive = item.id === current.id;
            var step = (typeof item.currentStep === 'number') ? steps[item.currentStep] || '?' : '?';
            var time = (item.updatedAt || '').slice(0, 10) || '';
            html += '<div class="rp-shell-project-item' + (isActive ? ' active' : '') + '" data-id="' + item.id + '" role="menuitem">'
              + '<span>' + (item.name || '未命名') + '</span>'
              + '<span class="step-badge">' + step + '</span>'
              + '<span class="item-time">' + time + '</span>'
              + '</div>';
          });
          html += '<div class="rp-shell-project-actions">'
            +   '<button class="primary" id="rp-proj-new">＋ 新建</button>'
            +   '<button id="rp-proj-share">🔗 分享</button>'
            +   '<button class="danger" id="rp-proj-reset">↺ 重置</button>'
            + '</div>';
          var dd = document.getElementById('rp-shell-project-dropdown');
          if (dd) dd.innerHTML = html;

          // 绑定事件
          var items = dd.querySelectorAll('.rp-shell-project-item');
          items.forEach(function (el) {
            el.addEventListener('click', function () {
              var id = el.getAttribute('data-id');
              if (id && id !== current.id) {
                window.RpProject.load(id);
                renderProject();
                dd.classList.remove('open');
                document.getElementById('rp-shell-project-btn').setAttribute('aria-expanded','false');
              }
            });
          });
          var bNew = document.getElementById('rp-proj-new');
          if (bNew) bNew.addEventListener('click', function () {
            window.RpProject.create('新构建 ' + new Date().toLocaleTimeString());
            renderProject();
            dd.classList.remove('open');
          });
          var bShare = document.getElementById('rp-proj-share');
          if (bShare) bShare.addEventListener('click', function () {
            var url = window.RpProject.shareUrl();
            navigator.clipboard && navigator.clipboard.writeText(url);
            bShare.textContent = '✓ 已复制';
            setTimeout(function () { bShare.textContent = '🔗 分享'; }, 1500);
          });
          var bReset = document.getElementById('rp-proj-reset');
          if (bReset) bReset.addEventListener('click', function () {
            if (confirm('重置当前项目？此操作不可撤销。')) {
              window.RpProject.reset();
              renderProject();
              dd.classList.remove('open');
            }
          });
        } catch (e) { /* 静默失败 */ }
      }

      var btn = document.getElementById('rp-shell-project-btn');
      if (btn) {
        btn.addEventListener('click', function (e) {
          e.stopPropagation();
          var dd = document.getElementById('rp-shell-project-dropdown');
          if (!dd) return;
          var willOpen = !dd.classList.contains('open');
          if (willOpen) renderDropdown();
          dd.classList.toggle('open', willOpen);
          btn.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
        });
        // 点击其他地方关闭
        document.addEventListener('click', function () {
          var dd = document.getElementById('rp-shell-project-dropdown');
          if (dd) {
            dd.classList.remove('open');
            btn.setAttribute('aria-expanded', 'false');
          }
        });
      }

      // 订阅 project 变更
      window.RpProject.onChange(function (key) {
        renderProject();
      });
    }

    // 移动端菜单按钮
    var toggle = document.createElement('button');
    toggle.className = 'rp-shell-menu-toggle';
    toggle.type = 'button';
    toggle.setAttribute('aria-label', '切换菜单');
    toggle.textContent = '☰';
    inner.appendChild(toggle);

    header.appendChild(inner);
    document.body.insertBefore(header, document.body.firstChild);

    // 事件绑定
    toggle.addEventListener('click', function () {
      nav.classList.toggle('open');
    });
    var searchInput = document.getElementById('rp-shell-search-input');
    var searchBtn = document.getElementById('rp-shell-search-btn');
    function doSearch() {
      var q = searchInput.value.trim();
      if (q) {
        location.href = '/api/search?q=' + encodeURIComponent(q);
      } else {
        location.href = '/parts-viewer.html';
      }
    }
    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') doSearch(); });

    // ===== 面包屑 =====
    var crumb = document.createElement('nav');
    crumb.className = 'rp-shell-breadcrumb';
    crumb.setAttribute('aria-label', '面包屑');
    meta.breadcrumb.forEach(function (part, idx) {
      if (idx > 0) {
        var sep = document.createElement('span');
        sep.className = 'sep';
        sep.textContent = '›';
        crumb.appendChild(sep);
      }
      if (idx === meta.breadcrumb.length - 1) {
        var cur = document.createElement('span');
        cur.className = 'current';
        cur.textContent = part;
        crumb.appendChild(cur);
      } else {
        var a = document.createElement('a');
        a.href = '/index.html';
        a.textContent = part;
        crumb.appendChild(a);
      }
    });
    document.body.insertBefore(crumb, document.body.children[1]);

    // ===== 下一步 CTA =====
    if (meta.next && meta.next.btns && meta.next.btns.length) {
      var next = document.createElement('aside');
      next.className = 'rp-shell-next';
      next.setAttribute('aria-label', '下一步建议');
      var label = document.createElement('span');
      label.className = 'rp-shell-next-label';
      label.textContent = '下一步';
      next.appendChild(label);
      var title = document.createElement('div');
      title.className = 'rp-shell-next-title';
      title.textContent = meta.next.title;
      next.appendChild(title);
      var btns = document.createElement('div');
      btns.className = 'rp-shell-next-btns';
      meta.next.btns.forEach(function (b, i) {
        var a = document.createElement('a');
        a.href = b.href;
        a.className = 'rp-shell-next-btn' + (i > 0 ? ' ghost' : '');
        a.textContent = b.label;
        btns.appendChild(a);
      });
      next.appendChild(btns);
      document.body.appendChild(next);
    }

    // ===== 底部页脚 =====
    var footer = document.createElement('footer');
    footer.className = 'rp-shell-footer';
    footer.setAttribute('role', 'contentinfo');

    var fInner = document.createElement('div');
    fInner.className = 'rp-shell-footer-inner';

    // about 列
    var col1 = document.createElement('div');
    col1.className = 'rp-shell-footer-col';
    col1.innerHTML = '<div class="rp-shell-footer-about"><div class="logo">Robo<span>Parts</span></div>'
      + '<div>' + FOOTER.about.tag + '</div>'
      + '<ul style="margin-top:12px">'
      + FOOTER.about.links.map(function (l) { return '<li><a href="' + l.href + '">' + l.label + '</a></li>'; }).join('')
      + '</ul></div>';
    fInner.appendChild(col1);

    // 其他三列
    ['product', 'agent', 'resources'].forEach(function (key) {
      var col = document.createElement('div');
      col.className = 'rp-shell-footer-col';
      col.innerHTML = '<h4>' + FOOTER[key].title + '</h4><ul>'
        + FOOTER[key].links.map(function (l) { return '<li><a href="' + l.href + '">' + l.label + '</a></li>'; }).join('')
        + '</ul>';
      fInner.appendChild(col);
    });

    footer.appendChild(fInner);

    var bottom = document.createElement('div');
    bottom.className = 'rp-shell-footer-bottom';
    bottom.innerHTML = '<div>© 2024-2026 RoboParts · 数据 CC BY 4.0 · 代码 MIT · <a href="https://github.com/lm203688/roboparts">GitHub</a></div>'
      + '<div>中立第三方 · 不生产不销售任何零部件 · <a href="/oss.html">开源协议</a></div>';
    footer.appendChild(bottom);

    // P0-4 部署指纹条：异步拉 /api/deployment 显示当前线上 commit + 构建时间。
    // 目的：把"我看到的到底是哪一版"从 CI 内部指标暴露给用户，也让 MCP 客户端
    // 能在会话开始时打一次 GET 拿到 fingerprint 作为证据链锚点。
    // 失败静默降级（老版本部署没有此端点时不报错、不占位）。
    try {
      fetch('/api/deployment', { cache: 'no-store' })
        .then(function (r) { if (!r.ok) throw new Error('http ' + r.status); return r.json(); })
        .then(function (fp) {
          if (!fp || fp.commit === 'unknown') return;
          var bar = document.createElement('div');
          bar.className = 'rp-shell-footer-fingerprint';
          bar.style.cssText = 'text-align:center;font-size:11px;color:#6b7280;padding:8px 0;'
            + 'font-family:ui-monospace,SFMono-Regular,Menlo,monospace;border-top:1px solid rgba(148,163,184,.2);'
            + 'margin-top:12px';
          var built = (fp.builtAt || '').slice(0, 16).replace('T', ' ');
          bar.textContent = '⚙ 线上部署 ' + fp.commitShort
            + ' · 构建 ' + built
            + ' · Node ' + (fp.nodeVersion || '?')
            + ' · 数据 ' + (fp.totalEntities || '?') + ' 实体'
            + (fp.dataFingerprint && fp.dataFingerprint.generatedAt
                ? ' · 数据版本 ' + fp.dataFingerprint.generatedAt.slice(0, 10) : '');
          footer.appendChild(bar);
        })
        .catch(function () { /* 老部署/端点故障，静默 */ });
    } catch (e) { /* fetch 不存在（极老浏览器）时不阻塞页面 */ }

    document.body.appendChild(footer);
  }

  // 等 DOM 就绪
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', renderShell);
  } else {
    renderShell();
  }
})();
