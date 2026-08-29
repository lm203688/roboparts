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
 */
const DEFAULT_BASE = 'https://apihub.agnes-ai.cn/v1';
const DEFAULT_MODEL = 'agnes-2.0-flash';

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

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

  try {
    const r = await fetch(baseUrl + '/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': 'Bearer ' + apiKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model,
        messages: [{ role: 'user', content: prompt }],
        temperature: 0.3,
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
    return new Response(JSON.stringify({ error: 'agnes_fetch_failed', message: String(e.message || e).slice(0, 200) }),
      { status: 502, headers: { ...CORS, 'Content-Type': 'application/json' } });
  }
}
