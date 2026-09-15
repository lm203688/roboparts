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

/**
 * attempts[].error 会被回给**公开端点**，因此任何后端错误文本在出网前必须先脱敏。
 * 起因（20260915）：本轮修 push-gitdata.mjs 的 PAT 明文泄露时发现同类风险 ——
 * 若某运行时把请求头带进 fetch 的异常消息，密钥就会随诊断字段公开泄露。
 * 这里一律抹掉 Bearer 串 / sk- 前缀密钥 / Authorization 头。
 */
function redactErr(msg) {
  return String(msg == null ? '' : msg)
    .replace(/(Authorization:\s*Bearer\s+)\S+/gi, '$1***')
    .replace(/(\bBearer\s+)[A-Za-z0-9_\-.=]{16,}/g, '$1***')
    .replace(/\bsk-[A-Za-z0-9_\-]{16,}/g, 'sk-***')
    .slice(0, 140);
}

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

// ---- archify 借鉴：验证式兼容图（typed IR + 数据校验 + 确定性渲染 + fail-closed）----
// 借鉴开源 Agent skill Archify（tt-a1i/archify，MIT）的核心范式：Agent 只产出结构化
// 中间表示（IR），由校验器对照**真实数据**逐项核验，无背书即丢弃（fail-closed，绝不让
// 图里冒出数据中不存在的零件），渲染交给确定性编译器。区别在于：这里的 IR 生产者不是
// LLM，而是规则引擎本身 —— 更彻底地不给「AI 编造接口」留位置。
// 规则：一个节点/边，只有能被 canonical 法兰梯级、用户显式给出的三要素、平台实体库、
//       或可构造的转接件 URL 背书时才进图；否则进 dropped[] 并如实回传（不静默）。
function buildCompatIR(ctx, entities) {
  const ir = { kind: 'roboparts.compat-graph', version: 1, subject: null, nodes: [], edges: [], dropped: [] };
  if (!ctx) return ir;
  const canon = (f) => CANONICAL_FLANGE.find((l) => l.startsWith('A' + f.pcd + '=')) || null;
  const mkFlangeNode = (f, side) => {
    const c = canon(f);
    return {
      id: 'side' + side,
      type: 'flange',
      label: `A${f.pcd}-${f.holes}-${f.thread}`,
      evidence: c
        ? { source: 'canonical_flange', ref: c, tier: 'canonical' }
        : { source: 'user_input', ref: `${f.pcd}mm/${f.holes}孔/${f.thread}`, tier: 'user_supplied' },
    };
  };
  const fl = Array.isArray(ctx.flanges) ? ctx.flanges : [];
  if (fl.length >= 2) {
    const [a, b] = fl;
    ir.subject = `A${a.pcd}-${a.holes}-${a.thread} ↔ A${b.pcd}-${b.holes}-${b.thread}`;
    ir.nodes.push(mkFlangeNode(a, 'A'), mkFlangeNode(b, 'B'));
    const ok = ctx.verdict === 'ok';
    ir.edges.push({
      from: 'sideA', to: 'sideB', kind: 'verdict',
      label: ok ? '直接兼容' : '需转接件',
      evidence: { source: 'iso9409-1', ref: '节圆/孔数/螺纹逐项比对（judgeFlanges）' },
    });
    if (!ok) {
      if (ctx.adapterUrl && /^https?:\/\//.test(ctx.adapterUrl)) {
        ir.nodes.push({
          id: 'adapter', type: 'adapter', label: '转接板',
          evidence: { source: 'adapter_generator', ref: ctx.adapterUrl, tier: 'rule' },
        });
        ir.edges.push(
          { from: 'sideA', to: 'adapter', kind: 'mediated', label: '生成', evidence: { source: 'rule', ref: 'adapterUrl' } },
          { from: 'adapter', to: 'sideB', kind: 'mediated', label: '对接', evidence: { source: 'rule', ref: 'adapterUrl' } },
        );
      } else {
        ir.dropped.push({ candidate: 'adapter', reason: '裁决需转接件，但未能生成有效转接件 URL —— 不画无背书节点' });
      }
    }
  } else if (fl.length === 1) {
    ir.nodes.push(mkFlangeNode(fl[0], 'A'));
    ir.dropped.push({ candidate: 'sideB', reason: '仅识别到一侧法兰，无法成图（需两侧）' });
  }
  // 实体引用：只有命中平台真实实体才进图；未命中如实进 dropped（不臆造实体引用）
  if (Array.isArray(ctx.mentions) && ctx.mentions.length) {
    const ents = Array.isArray(entities) ? entities : [];
    for (const m of ctx.mentions.slice(0, 6)) {
      const token = String(m).toLowerCase();
      const hit = ents.find((e) =>
        [e.id, e.name, e.brand || ''].filter(Boolean).join(' ').toLowerCase().includes(token));
      if (hit) {
        ir.nodes.push({
          id: 'ent:' + hit.id, type: 'entity', label: `${hit.name || hit.id}`,
          evidence: { source: 'entities.json', ref: hit.id, tier: 'platform_data' },
        });
      } else {
        ir.dropped.push({ candidate: String(m), reason: '平台实体库无匹配 —— 不臆造实体引用' });
      }
    }
  }
  return ir;
}

// 把已校验的 IR 作为「唯一可信节点集」喂给模型，锁死它只能引用图中节点（对应 Archify 的
// 「AI 只描述、编译器渲染」——这里进一步要求 AI 连描述都不得越出已核验的节点集）。
function irGrounding(ir) {
  if (!ir || !ir.nodes.length) return '';
  const lines = ir.nodes.map((n) => `- ${n.id}: ${n.label}（${n.type}；出处 ${n.evidence.source}）`);
  const dropped = ir.dropped.length
    ? '\n以下提及因**缺少数据背书已被拒绝**，回答中不得补全或猜测：' + ir.dropped.map((d) => d.candidate).join('、') + '。'
    : '';
  return '\n【兼容性图（唯一可信节点集，禁止越出）】\n' + lines.join('\n')
    + '\n仅可引用以上节点；不得臆造图中不存在的零件、接口或尺寸。' + dropped;
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
  // archify 借鉴：先由规则引擎产出「已校验 IR」，再拿它同时喂给模型（锁死可引用节点集）
  // 与回传给前端（确定性渲染）。计算必须在任何 return 之前 —— 降级分支也要携带它。
  const ir = buildCompatIR(context, _entitiesForRef);
  const system = (await buildSystemPrompt(request)) + '\n' + contextBlock(context) + irGrounding(ir);

  const backends = buildBackends(env);
  if (backends.length === 0) {
    // 未配置任何后端：直接降级，不抛 5xx（仍携带 references 让前端可点）
    return new Response(JSON.stringify({
      text: 'Copilot 推理后端未配置（维护中）。兼容性裁决仍可在平台数据与 ISO 9409-1 法兰库中查证。',
      model: 'maintenance',
      degraded: true,
      detail: 'no_backend_configured',
      attempts: [],
      configured: [],
      references,
      ir,
    }), { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
  }

  const timeoutMs = Number(env.COPILOT_UPSTREAM_TIMEOUT_MS) || 25000;
  let lastDetail = null;
  // 每个后端的实际结果都要留痕。
  // 起因（20260915 实测）：lastDetail 只保留**最后一个**后端的错误，于是
  // 「首选后端（ECS）为什么失败」被次选后端（Agnes 429）的 detail 永久吞掉 ——
  // 线上只能看到 upstream_agnes_error:429，无法判断 ECS 那一跳是拒连、超时还是 401。
  // 降级时的可观测性不该取决于"谁是最后一个"。故逐后端记录 attempts。
  const attempts = [];
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
        attempts.push({ backend: b.name, ok: false, error: `http_${r.status}` });
        continue; // 降级到下一个后端
      }
      const d = await r.json();
      const text = (d.choices && d.choices[0] && d.choices[0].message && d.choices[0].message.content)
        ? d.choices[0].message.content : '';
      if (!text) {
        lastDetail = `upstream_${b.name}_empty`;
        attempts.push({ backend: b.name, ok: false, error: 'empty_content' });
        continue;
      }
      attempts.push({ backend: b.name, ok: true });
      return new Response(JSON.stringify({ text, model: `${b.name}:${b.model}`, references, ir,
        attempts, configured: backends.map((x) => `${x.name}:${x.model}`) }),
        { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
    } catch (e) {
      const aborted = e && e.name === 'AbortError';
      lastDetail = aborted ? `upstream_${b.name}_timeout` : `upstream_${b.name}_fetch_failed`;
      attempts.push({
        backend: b.name,
        ok: false,
        error: aborted ? `timeout_${timeoutMs}ms` : redactErr((e && e.message) || 'fetch_failed'),
      });
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
    attempts,
    configured: backends.map((x) => `${x.name}:${x.model}`),
    references,
    ir,
  }), { status: 200, headers: { ...CORS, 'Content-Type': 'application/json' } });
}
