/**
 * /api/copilot — 服务端代理 Agnes AI，为 Copilot 页面生成自然语言解释。
 *
 * 设计要点：
 *   - AGNES_API_KEY 等服务端密钥只存在于 Cloudflare 加密 secret，绝不进前端。
 *   - 仅允许本站（roboparts.cc）来源调用，防止密钥被第三方站点滥用。
 *   - Agnes 为 OpenAI 兼容协议：POST {base}/chat/completions，Bearer 鉴权。
 *
 * 环境变量（Cloudflare secret）：
 *   AGNES_API_KEY   必填（sk-… 形式）
 *   AGNES_BASE_URL  默认 https://apihub.agnes-ai.cn/v1
 *   AGNES_MODEL     默认 agnes-2.0-flash
 *
 * 请求：POST { prompt: string }  →  响应：{ text: string, model: string }
 *
 * 2026-08-30 修订（defensive + grounding）：
 *   - 上游 fetch 加 25s AbortController 超时，避免一个挂起的请求把 worker 卡 60s（实测偶发）。
 *   - 注入 grounding system prompt：本平台是工业机器人末端接口/ISO 9409-1 法兰数据库，
 *     模型必须基于平台真实 meta 与 canonical 法兰梯级作答，严禁臆造尺寸或混淆标准
 *     （实测 Agnes 曾把 ISO 9409-1 答成焊接坡口标准 ISO 9692）。
 *   - grounding meta 在请求时同源拉取 /api/data.json（5s 超时，失败则退化为静态 canonical），
 *     始终不带密钥、不外发用户数据。
 */
const DEFAULT_BASE = 'https://apihub.agnes-ai.cn/v1';
const DEFAULT_MODEL = 'agnes-2.0-flash';
const UPSTREAM_TIMEOUT_MS = 25000;
const GROUNDING_TIMEOUT_MS = 5000;

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

// 平台 canonical 法兰梯级（权威源 Industrial Robotics Hub《Robot Tool Flange Sizes by Brand》2026-07-25）。
// 这是已发布标准的引用，非平台私有数据；用于锚定模型、防止臆造尺寸。
const CANONICAL_FLANGE = [
  'A40=4×M6', 'A50=4×M6', 'A63=6×M6', 'A80=6×M8',
  'A100=6×M10', 'A160=8×M16', 'A250=8×M20',
];

const SYSTEM_BASE = [
  '你是 RoboParts 兼容助手机器人（Copilot），专精工业机器人末端执行器机械接口与 ISO 9409-1 安装法兰。',
  '核心事实（务必基于以下，不要臆造）：',
  '- ISO 9409-1 规定的是工业机器人**圆形安装法兰的螺栓孔/销孔节圆（PCD）**尺寸系列，**不是焊接坡口几何**（那是 ISO 9692）。标准标号 A{n} 中 n 为节圆直径 PCD（mm），而非外径。',
  '- 平台 canonical 法兰梯级：' + CANONICAL_FLANGE.join('、') + '。',
  '- 同一 A 标号不同厂商几何可能不同（如 Hub 偏离：A100-4-M8、A160-4-M12 的 KUKA 型）。',
  '回答准则：',
  '- 法兰螺栓/销孔规格只能依据上述 canonical 梯级，或注明“以厂商官方规格为准”，不得凭空生成尺寸。',
  '- 涉及具体零件兼容性时，指向平台数据与 ISO 9409-1；不确定时明确说“暂无数据/需查证”。',
  '- 不要编造平台不存在的实体或标准号。',
].join('\n');

async function buildSystemPrompt(request) {
  // 同源拉取平台真实 meta 做 grounding（失败退化到静态 canonical，不阻断）。
  try {
    const host = new URL(request.url).host;
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), GROUNDING_TIMEOUT_MS);
    const r = await fetch(`https://${host}/api/data.json`, {
      signal: ctrl.signal,
      headers: { 'X-RoboParts-Selftest': '1' },
    });
    clearTimeout(t);
    if (!r.ok) return SYSTEM_BASE;
    const d = await r.json();
    const meta = (d && d.meta) || {};
    const parts = [SYSTEM_BASE];
    const total = meta.total_entities;
    const cats = meta.categories;
    if (typeof total === 'number') {
      const catN = (cats && typeof cats === 'object') ? Object.keys(cats).length : undefined;
      parts.push(`平台实时规模：实体 ${total}${catN ? ` 个、覆盖 ${catN} 个品类` : ''}。`);
    }
    const mech = meta.mechanical_interface_coverage;
    if (mech && typeof mech === 'object') {
      parts.push(
        `机械接口声明：declared ${mech.declared}/partial ${mech.partial}/not_declared ${mech.not_declared}/` +
        `not_applicable ${mech.not_applicable}（声明率约 1.52%，真实 BOM 数据缺口，非代码缺陷）。`
      );
    }
    return parts.join('\n');
  } catch {
    return SYSTEM_BASE;
  }
}

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: CORS });
}

export async function onRequestPost({ request, env }) {
  // 仅限本站来源，避免密钥被他站盗用
  const origin = request.headers.get('origin') || '';
  if (!origin.includes('roboparts.cc')) {
    return new Response(JSON.stringify({ error: 'forbidden_origin' }),
      { status: 403, headers: { ...CORS, 'Content-Type': 'application/json' } });
  }

  const apiKey = env.AGNES_API_KEY;
  if (!apiKey) {
    return new Response(JSON.stringify({ error: 'agnes_not_configured', message: '服务端未配置 AGNES_API_KEY' }),
      { status: 503, headers: { ...CORS, 'Content-Type': 'application/json' } });
  }

  let body;
  try { body = await request.json(); } catch {
    return new Response(JSON.stringify({ error: 'invalid_json' }),
      { status: 400, headers: { ...CORS, 'Content-Type': 'application/json' } });
  }
  const prompt = (body && body.prompt) ? String(body.prompt).slice(0, 2000) : '';
  if (!prompt) {
    return new Response(JSON.stringify({ error: 'missing_prompt' }),
      { status: 400, headers: { ...CORS, 'Content-Type': 'application/json' } });
  }

  const baseUrl = (env.AGNES_BASE_URL || DEFAULT_BASE).replace(/\/+$/, '');
  const model = env.AGNES_MODEL || DEFAULT_MODEL;
  const system = await buildSystemPrompt(request);

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);
  try {
    const r = await fetch(baseUrl + '/chat/completions', {
      method: 'POST',
      signal: controller.signal,
      headers: {
        'Authorization': 'Bearer ' + apiKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: 'system', content: system },
          { role: 'user', content: prompt },
        ],
        temperature: 0.2,
        max_tokens: 400,
      }),
    });
    if (!r.ok) {
      const err = await r.text();
      return new Response(JSON.stringify({ error: 'agnes_error', status: r.status, message: err.slice(0, 200) }),
        { status: 502, headers: { ...CORS, 'Content-Type': 'application/json' } });
    }
    const d = await r.json();
    const text = (d.choices && d.choices[0] && d.choices[0].message && d.choices[0].message.content)
      ? d.choices[0].message.content : '';
    return new Response(JSON.stringify({ text, model }),
      { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
  } catch (e) {
    if (e && e.name === 'AbortError') {
      return new Response(JSON.stringify({
        error: 'agnes_timeout',
        message: '上游推理超时',
        ms: UPSTREAM_TIMEOUT_MS,
      }), { status: 504, headers: { ...CORS, 'Content-Type': 'application/json' } });
    }
    return new Response(JSON.stringify({ error: 'agnes_fetch_failed', message: String(e.message || e).slice(0, 200) }),
      { status: 502, headers: { ...CORS, 'Content-Type': 'application/json' } });
  } finally {
    clearTimeout(timer);
  }
}
