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
//   get_component_detail    GET  /api/entity/<id>             —— 单件详情（白名单投影，付费字段已剥离）
//   search_components       GET  /api/search?q=<query>        —— 关键词检索
//   check_compatibility     GET  /api/compatibility?a=&b=     —— 四维兼容判定
//   check_co_mount          GET  /api/co-mount?host=&a=&b=    —— 三段共装查询
//   bom_compatibility_check POST /api/bom/check               —— 两两矩阵 + 装配步骤
//   lint_urdf               POST /api/urdf/lint               —— URDF 静态检查
//
// 使用：
//   在 promptfooconfig.yaml 里写 provider:
//     - id: file://provider-roboparts.mjs
//   每个 test 通过 vars.tool 指定工具名，vars 其余字段作为参数。
//
// 2026-10-12 修复：
//   1. promptfoo custom provider 必须导出 class（不能是 async function），否则
//      promptfoo 的 `new (await importModule(path))(...)` 抛 TypeError: not a constructor。
//   2. API_BASE 尾部斜杠清理原写成 `replace(/\/$/, 'https://roboparts.cc')`，
//      替换串应是空字符串，不是 URL。
//
// promptfoo 契约：class 需实现 id() 与 callApi(prompt, vars)。callApi 返回
// { output: string, isError?: boolean, error?: string }。

const ROUTES = {
  get_component_detail: (v, base) => ({
    // 线上 /api/entity/{id} 是单件详情端点（curl 实测 200）；
    // /api/search 只支持 q=（关键词检索），不支持 id= 参数（实测 400）。
    url: `${base}/api/entity/${encodeURIComponent(v.id)}`,
    method: 'GET',
  }),
  search_components: (v, base) => ({
    url: `${base}/api/search?q=${encodeURIComponent(v.query)}`,
    method: 'GET',
  }),
  check_compatibility: (v, base) => ({
    url: `${base}/api/compatibility?a=${encodeURIComponent(v.a)}&b=${encodeURIComponent(v.b)}`,
    method: 'GET',
  }),
  check_co_mount: (v, base) => ({
    url: `${base}/api/co-mount?host=${encodeURIComponent(v.host)}&a=${encodeURIComponent(v.a)}&b=${encodeURIComponent(v.b)}`,
    method: 'GET',
  }),
  bom_compatibility_check: (v, base) => ({
    url: `${base}/api/bom/check`,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    // v.bom 在 YAML 里是字符串（'{"items":[...]}'），已经是合法 JSON 文本；
    // 再 JSON.stringify 会双编码，服务端收到的是字符串而不是对象，报
    // "items 需为至少 2 个组件的数组"。直接透传即可。
    body: v.bom,
  }),
  lint_urdf: (v, base) => ({
    url: `${base}/api/urdf/lint`,
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ urdf_xml: v.urdf_xml, check_level: v.check_level || 'all' }),
  }),
};

export default class RoboPartsProvider {
  constructor(config = {}) {
    // 修 bug：replace 的第二个参数应为空字符串，不是 URL
    const fallback = 'https://roboparts.cc';
    this.apiBase = (config.apiBase || process.env.ROBOPARTS_API_BASE || fallback).replace(/\/$/, '');
    this.label = config.label || 'RoboParts REST';
  }

  // 必须是同步返回字符串：promptfoo 内部会 `p.id().split(':')`，
  // 若 id() 是 async 返回 Promise，`.split` 未定义。
  id() {
    return 'roboparts-rest';
  }

  // promptfoo 契约：callApi(prompt, context, options)。
  // vars 藏在 context.vars（不是第二参直传），旧版误把它当第二参，导致 vars.tool = undefined。
  //
  // isError 语义（2026-10-12 定）：
  //   - 网络层真故障（fetch 抛异常）→ isError:true，promptfoo 自动判错
  //   - HTTP 非 200 响应 → isError:false，把状态码写进 output，让断言判内容
  //   - 未知 tool 名    → isError:false，把 unknown_tool 写进 output，让断言判内容
  // 原因：promptfoo 对 isError:true 是硬编码判错、跳过断言；负测（期望 404/unknown_tool）
  // 需要断言去验内容，所以这类"预期内的引擎/路由错误"不能走 isError。
  async callApi(prompt, context = {}, options = {}) {
    const vars = context.vars || options.vars || {};
    const tool = vars.tool;
    const route = ROUTES[tool];
    if (!route) {
      return {
        output: JSON.stringify({
          error: 'unknown_tool',
          message: `unknown tool: ${tool}`,
          known: Object.keys(ROUTES),
        }),
      };
    }
    const { url, method, headers, body } = route(vars, this.apiBase);
    try {
      const res = await fetch(url, { method, headers, body });
      const text = await res.text();
      if (!res.ok) {
        // 把 HTTP 状态码前置到 output，便于断言用 regex 同时验状态与错误内容
        return { output: `HTTP ${res.status}\n${text}` };
      }
      return { output: text };
    } catch (e) {
      return { output: String(e.message || e), isError: true, error: String(e.message || e) };
    }
  }
}
