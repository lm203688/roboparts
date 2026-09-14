/**
 * /api/copilot — 多后端路由代理，为 Copilot 页面生成自然语言解释。
 *
 * 设计要点：
 *   - 仅限本站（roboparts.cc）来源调用，防止密钥被第三方站点滥用。
 *   - 服务端密钥只存在于 Cloudflare 加密 secret，绝不进前端。
 *   - 后端顺序（自动化运行逻辑在请求时按"实际可用性"裁决）：
 *       1) 若配置了 ECS 网关（自托管、可控、可随意换模型）→ 优先；
 *       2) 否则 Agnes AI（OpenAI 兼容协议）；
 *       3) 任一后端超时/报错自动降级到下一个；全部失败返回结构化"维护中"响应，
 *          不再 504 挂死、不再把错误抛给用户。
 *   - grounding system prompt 锚定平台真实 meta + canonical 法兰梯级，防核心标准答错。
 *
 * 环境变量（Cloudflare secret）：
 *   AGNES_API_KEY    Agnes 密钥（sk-…）
 *   AGNES_BASE_URL   默认 https://apihub.agnes-ai.cn/v1
 *   AGNES_MODEL      默认 agnes-2.0-flash
 *   ECS_API_KEY      腾讯云 ECS 网关密钥（配置后即自动优先）
 *   ECS_BASE_URL     默认 http://150.158.119.19:8420/v1
 *   ECS_MODEL        默认 deepseek-chat
 *   COPILOT_UPSTREAM_TIMEOUT_MS  单后端超时，默认 25000
 *
 * 2026-08-30 修订（multi-backend router + 维护中降级）：
 *   - 上一版仅死绑 Agnes，上游不稳时直接 502/504。现改为运行时按可用后端裁决，
 *     全部不可用返回友好降级文本，Copilot 永不在前端"崩"。
 */
const DEFAULT_AGNES_BASE = 'https://apihub.agnes-ai.cn/v1';
const DEFAULT_AGNES_MODEL = 'agnes-2.0-flash';
const DEFAULT_ECS_BASE = 'http://150.158.119.19:8420/v1';
const DEFAULT_ECS_MODEL = 'deepseek-chat';
const GROUNDING_TIMEOUT_MS = 5000;

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

// 平台 canonical 法兰梯级（权威源 Industrial Robotics Hub《Robot Tool Flange Sizes by Brand》2026-07-25）。
// 已发布标准的引用，非平台私有数据；用于锚定模型、防止臆造尺寸。
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

// 运行时按"实际可用性"裁决的后端列表：ECS 网关（若配置）优先，Agnes 次之。
function buildBackends(env) {
  const list = [];
  if (env.ECS_API_KEY) {
    list.push({
      name: 'ecs',
      base: (env.ECS_BASE_URL || DEFAULT_ECS_BASE).replace(/\/+$/, ''),
      model: env.ECS_MODEL || DEFAULT_ECS_MODEL,
      key: env.ECS_API_KEY,
    });
  }
  if (env.AGNES_API_KEY) {
    list.push({
      name: 'agnes',
      base: (env.AGNES_BASE_URL || DEFAULT_AGNES_BASE).replace(/\/+$/, ''),
      model: env.AGNES_MODEL || DEFAULT_AGNES_MODEL,
      key: env.AGNES_API_KEY,
    });
  }
  return list;
}

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

// ---- heyclicky 借鉴：上下文感知 + “指给你看”结构化引用 ----
// 缓存 entities.json（5 分钟），用于按品牌/型号名反查真实实体，做“指向具体零件”的引用。
let _entitiesCache = { at: 0, data: null };
async function loadEntities(host) {
  const now = Date.now();
  if (_entitiesCache.data && now - _entitiesCache.at < 300000) return _entitiesCache.data;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), GROUNDING_TIMEOUT_MS);
    const r = await fetch(`https://${host}/api/entities.json`, {
      signal: ctrl.signal,
      headers: { 'X-RoboParts-Selftest': '1' },
    });
    clearTimeout(t);
    if (!r.ok) return _entitiesCache.data; // 拉取失败则沿用旧缓存，不阻断
    const d = await r.json();
    _entitiesCache = { at: now, data: (d && d.entities) || [] };
    return _entitiesCache.data;
  } catch {
    return _entitiesCache.data;
  }
}

// 把用户当前判定的法兰 + 裁决 + 提到的品牌，拼成系统提示里的“上下文块”，
// 让 AI 解释「这一例」而非复述通用规则（对应 heyclicky「AI 看见你正在看的东西」）。
function contextBlock(ctx) {
  if (!ctx) return '';
  const parts = [];
  if (Array.isArray(ctx.flanges) && ctx.flanges.length) {
    const desc = ctx.flanges
      .map((f) => `A${f.pcd}-${f.holes}-${f.thread}（PCD ${f.pcd}mm/${f.holes}×${f.thread}）`)
      .join(' 与 ');
    parts.push(`用户当前正在判定的法兰：${desc}。`);
  }
  if (ctx.verdict) parts.push(`本例规则裁决：${ctx.verdict === 'ok' ? '直接兼容' : '需要转接件'}。`);
  if (Array.isArray(ctx.mentions) && ctx.mentions.length) {
    parts.push(`用户在问题中提到了这些品牌/型号关键词：${ctx.mentions.join('、')}。若平台有对应实体，请在解释中指向其数据页。`);
  }
  return parts.length ? '【当前上下文】\n' + parts.join('\n') : '';
}

// 生成“指给你看”的引用：canonical 法兰梯级 + ISO 9409-1 速查 + 转接件 + 命中的真实实体。
// 这是 heyclicky「屏幕光标点」的 Web 原生等价物——把答案锚定到可点击的真实数据。
function buildReferences(ctx, entities) {
  const refs = [];
  if (ctx && Array.isArray(ctx.flanges)) {
    for (const f of ctx.flanges) {
      const line = CANONICAL_FLANGE.find((l) => l.startsWith('A' + f.pcd + '='));
      if (line) refs.push({ kind: 'flange', label: `${line}（canonical 梯级）`, url: '/iso-9409-flange' });
    }
  }
  refs.push({ kind: 'ref', label: 'ISO 9409-1 法兰速查', url: '/iso-9409-flange' });
  if (ctx && ctx.adapterUrl) refs.push({ kind: 'tool', label: '打开转接件生成器', url: ctx.adapterUrl });
  if (ctx && Array.isArray(ctx.mentions) && ctx.mentions.length && Array.isArray(entities)) {
    const seen = new Set();
    const ents = refs.filter((r) => r.kind === 'entity');
    for (const m of ctx.mentions) {
      if (ents.length >= 3) break;
      const token = m.toLowerCase();
      for (const e of entities) {
        if (seen.has(e.id)) continue;
        const hay = [e.id, e.name, e.brand || ''].filter(Boolean).join(' ').toLowerCase();
        if (hay.includes(token)) {
          refs.push({ kind: 'entity', label: `${e.name || e.id}（${e.id}）`, url: '/bionic' });
          seen.add(e.id);
          if (refs.filter((r) => r.kind === 'entity').length >= 3) break;
        }
      }
    }
  }
  const uniq = [];
  const keys = new Set();
  for (const r of refs) {
    const k = r.kind + '|' + r.label;
    if (!keys.has(k)) { keys.add(k); uniq.push(r); }
  }
  return uniq;
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

  // heyclicky 借鉴（必须在后端可行性判断之前算好，供降级分支也携带引用）：
  // 解析上下文 → 反查命中实体 → 生成“指给你看”的引用链。
  const context = (body && body.context && typeof body.context === 'object') ? body.context : null;
  let _entitiesForRef = null;
  if (context && Array.isArray(context.mentions) && context.mentions.length) {
    _entitiesForRef = await loadEntities(new URL(request.url).host);
  }
  const references = buildReferences(context, _entitiesForRef);
  const system = (await buildSystemPrompt(request)) + '\n' + contextBlock(context);

  const backends = buildBackends(env);
  if (backends.length === 0) {
    // 未配置任何后端：直接降级，不抛 5xx（仍携带 references 让前端可点）
    return new Response(JSON.stringify({
      text: 'Copilot 推理后端未配置（维护中）。兼容性裁决仍可在平台数据与 ISO 9409-1 法兰库中查证。',
      model: 'maintenance',
      degraded: true,
      detail: 'no_backend_configured',
      references,
    }), { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
  }

  const timeoutMs = Number(env.COPILOT_UPSTREAM_TIMEOUT_MS) || 25000;
  let lastDetail = null;
  for (const b of backends) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const r = await fetch(b.base + '/chat/completions', {
        method: 'POST',
        signal: controller.signal,
        headers: {
          'Authorization': 'Bearer ' + b.key,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: b.model,
          messages: [
            { role: 'system', content: system },
            { role: 'user', content: prompt },
          ],
          temperature: 0.2,
          max_tokens: 400,
        }),
      });
      if (!r.ok) {
        lastDetail = `upstream_${b.name}_error:${r.status}`;
        continue; // 降级到下一个后端
      }
      const d = await r.json();
      const text = (d.choices && d.choices[0] && d.choices[0].message && d.choices[0].message.content)
        ? d.choices[0].message.content : '';
      if (!text) {
        lastDetail = `upstream_${b.name}_empty`;
        continue;
      }
      return new Response(JSON.stringify({ text, model: `${b.name}:${b.model}`, references }),
        { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
    } catch (e) {
      lastDetail = (e && e.name === 'AbortError')
        ? `upstream_${b.name}_timeout`
        : `upstream_${b.name}_fetch_failed`;
      continue; // 降级到下一个后端
    } finally {
      clearTimeout(timer);
    }
  }

  // 全部后端不可用：结构化降级，前端展示友好文案而非报错（仍携带 references）
  return new Response(JSON.stringify({
    text: 'Copilot 暂时不可用（推理后端维护中）。兼容性裁决仍可在平台数据与 ISO 9409-1 法兰库中查证。',
    model: 'maintenance',
    degraded: true,
    detail: lastDetail,
    references,
  }), { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
}
