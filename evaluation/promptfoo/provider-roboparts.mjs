// RoboParts REST API 作为 promptfoo provider
//
// 设计：RoboParts MCP 的每个工具都有对应的公开 REST 端点，且这些端点
//   1. 免费访问（无 API key 门槛）
//   2. 稳定 URL 契约（Cloudflare Pages 托管，5 分钟缓存）
//   3. 响应体即引擎真实输出（非 LLM 生成的话术）
// 因此直接以 REST 为 provider 比走 MCP 更稳：
//   - 无需 MCP handshake、API key、OAuth
//   - 断言直接对齐引擎字段（tier / verdict / evidence），不受 LLM 复述噪声干扰
//   - promptfoo 的 custom provider 用 fetch 即可，无需装 @modelcontextprotocol/sdk
//
// 端点映射表（tool → REST）：
//   get_component_detail   GET  /api/search?id=<id>         —— 单件详情（走白名单投影，付费字段已剥离）
//   search_components      GET  /api/search?q=<query>       —— 关键词检索
//   check_compatibility    GET  /api/compatibility?a=&b=    —— 四维兼容判定
//   check_co_mount         GET  /api/co-mount?host=&a=&b=   —— 三段共装查询
//   bom_compatibility_check POST /api/bom/check             —— 两两矩阵 + 装配步骤
//   lint_urdf              POST /api/urdf/lint              —— URDF 静态检查
//
// 使用：
//   在 promptfooconfig.yaml 里写 provider:
//     - id: file://provider-roboparts.mjs
//   每个 test 通过 vars.tool 指定工具名，vars 其余字段作为参数。

const API_BASE = (process.env.ROBOPARTS_API_BASE || 'https://roboparts.cc').replace(/\/$/, 'https://roboparts.cc');

const ROUTES = {
  get_component_detail: (v) => ({
    // 线上 /api/entity/{id} 是单件详情端点（2026-10-11 curl 实测 200）；
    // /api/search 只支持 q=（关键词检索），不支持 id= 参数（实测 400）。
    url: `${API_BASE}/api/entity/${encodeURIComponent(v.id)}`,
    method: 'GET',
  }),
  search_components: (v) => ({
    url: `${API_BASE}/api/search?q=${encodeURIComponent(v.query)}`,
    method: 'GET',
  }),
  check_compatibility: (v) => ({
    url: `${API_BASE}/api/compatibility?a=${encodeURIComponent(v.a)}&b=${encodeURIComponent(v.b)}`,
    method: 'GET',
  }),
  check_co_mount: (v) => ({
    url: `${API_BASE}/api/co-mount?host=${encodeURIComponent(v.host)}&a=${encodeURIComponent(v.a)}&b=${encodeURIComponent(v.b)}`,
    method: 'GET',
  }),
  bom_compatibility_check: (v) => ({
    url: `${API_BASE}/api/bom/check`,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(v.bom),
  }),
  lint_urdf: (v) => ({
    url: `${API_BASE}/api/urdf/lint`,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ urdf_xml: v.urdf_xml, check_level: v.check_level || 'all' }),
  }),
};

// promptfoo custom provider 契约：async function({ prompt, vars, ...rest }) → { output, isError, error }
export default async function robopartsProvider({ prompt, vars = {} }) {
  const route = ROUTES[vars.tool];
  if (!route) {
    return {
      output: JSON.stringify({ error: `unknown_tool`, message: `unknown tool: ${vars.tool}`, known: Object.keys(ROUTES) }),
      isError: true,
    };
  }
  const { url, method, headers, body } = route(vars);
  try {
    const res = await fetch(url, { method, headers, body });
    const text = await res.text();
    if (!res.ok) {
      return { output: text, isError: true, error: `${res.status} ${res.statusText}` };
    }
    // 输出为原始 JSON 文本，便于 assert 用 regex / contains 直接匹配引擎字段
    return { output: text };
  } catch (e) {
    return { output: e.message, isError: true, error: e.message };
  }
}
