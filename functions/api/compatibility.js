/**
 * 兼容性裁决引擎 REST 端点 — 修复 T3「兼容矩阵是静态假数据」
 * GET /api/compatibility?a=ACT-001&b=SEN-001
 *
 * 基于实体真实字段（protocol / interface / voltage / ros_support）跨四个维度判定兼容性：
 *   protocol   协议/接口一致性
 *   electrical 电气（电压区间重叠）
 *   mechanical 机械（接口/连接器匹配）
 *   software   软件（ROS2 支持）
 * 与 selection/engine.js 的 analyzeCompatibility 不同，本端点是「给定两个真实实体 ID」的判定，
 * 数据全部来自 entities.json，不再依赖静态示意表。
 *
 * 【20260806-00】裁决逻辑已提取至 ../_lib/compat_engine.js，
 * 与 hosted MCP 端点 /mcp 共用同一实现。本文件只负责 HTTP 形态（参数解析 / 状态码 / CORS），
 * ⚠️ 不得在此重新实现 evalDimension —— 那会让 REST 与 MCP 对同一对零件给出不同答案。
 */

import { judgePair, loadEntityMap } from '../_lib/compat_engine.js';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

/**
 * 【M2 P0-2 · 2026-10-15】模糊名称→实体 ID 解析桥
 *
 * 用户脑子里是「Robotiq 2F-85」「UR5e」「ATI FTS-300」，不是本库内部 ID（ACT-028/SEN-049）。
 * 本函数把两者接起来：先精确 ID 匹配，失败后按名称/型号做大小写不敏感子串匹配，
 * 返回单一结果或候选列表供调用方消歧。
 *
 * 匹配口径（保守）：
 *   - 只匹配 `name` / `name_en` / `model` / `id` 字段（不把厂商、品牌混进来，避免歧义）
 *   - 归一化：去空格、小写、把 "  " 归一为 " "，让 "Robotiq 2F-85" 与 "robotiq 2f-85" 等价
 *   - 匹配得分：先精确 ID > 精确 name > 前缀 name > 子串 name；同分时取 id 字母序（可复现）
 *
 * 不匹配的场景（诚实返回空）：
 *   - 输入包含明显非实体词（如"这个"、"能不能"）：返回 candidates: []
 *   - 匹配到 > MAX_CANDIDATES 个：截断到 MAX_CANDIDATES 并置 has_more=true
 */
const MAX_CANDIDATES = 5;
const RESOLVE_FIELDS = ['id', 'name', 'name_en', 'model', 'part_number'];

function normalize(s) {
  return String(s || '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * 在实体映射中解析一个"ID 或名称"到实体。
 * @returns {{entity?: object, resolved_id?: string, exact?: boolean, candidates?: Array, ambiguous?: boolean, not_found?: boolean}}
 */
export function resolveEntity(query, map) {
  const q = normalize(query);
  if (!q) return { not_found: true, candidates: [] };

  // 1. 精确 ID 匹配（快路径）
  if (map[query]) {
    return { entity: map[query], resolved_id: query, exact: true, candidates: [] };
  }
  // 1b. 大小写不敏感的 ID 匹配
  for (const key of Object.keys(map)) {
    if (normalize(key) === q) {
      return { entity: map[key], resolved_id: key, exact: true, candidates: [] };
    }
  }

  // 2. 名称/型号模糊匹配
  const scored = [];
  for (const [id, ent] of Object.entries(map)) {
    let best = 0;
    let bestField = '';
    for (const field of RESOLVE_FIELDS) {
      if (field === 'id') continue; // 上面已处理
      const val = normalize(ent[field]);
      if (!val) continue;
      let score = 0;
      if (val === q) score = 100;           // 精确 name 匹配
      else if (val.startsWith(q)) score = 80; // 前缀
      else if (val.includes(q)) score = 60;   // 子串
      else if (q.includes(val) && val.length >= 3) score = 40; // 反向包含（避免空匹配）
      if (score > best) { best = score; bestField = field; }
    }
    if (best > 0) {
      scored.push({ id, entity: ent, score: best, matched_field: bestField, name: ent.name || ent.name_en || '' });
    }
  }

  scored.sort((x, y) => y.score - x.score || x.id.localeCompare(y.id));

  if (scored.length === 0) {
    return { not_found: true, candidates: [], query: q };
  }
  if (scored.length === 1) {
    return { entity: scored[0].entity, resolved_id: scored[0].id, exact: false, matched_field: scored[0].matched_field, candidates: [] };
  }
  // 多候选：返回前 MAX_CANDIDATES 个，让调用方消歧
  return {
    ambiguous: true,
    candidates: scored.slice(0, MAX_CANDIDATES).map(c => ({
      id: c.id, name: c.name, matched_field: c.matched_field, score: c.score,
    })),
    has_more: scored.length > MAX_CANDIDATES,
    query: q,
  };
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const idA = url.searchParams.get('a');
  const idB = url.searchParams.get('b');

  if (!idA || !idB) {
    return new Response(JSON.stringify({
      error: '缺少参数',
      usage: '/api/compatibility?a=ACT-001&b=SEN-001',
      fuzzy_hint: '支持用名称代替 ID：?a=Robotiq 2F-85&b=UR5e（会先精确匹配 ID，再模糊匹配名称）',
    }), { status: 400, headers: corsHeaders });
  }

  let map;
  try {
    map = await loadEntityMap(env, request);
  } catch (e) {
    // 数据源故障必须以 5xx 明说，不能降级成 404「实体不存在」——
    // 那会让调用方以为是自己 ID 写错了（环境要点 #19：兜底可以有，静默不行）。
    return new Response(JSON.stringify({
      error: '数据源不可用',
      detail: String(e && e.message || e),
    }), { status: 503, headers: corsHeaders });
  }

  // 解析 a / b：可能是 ID，也可能是名称（M2 P0-2）
  const resA = resolveEntity(idA, map);
  const resB = resolveEntity(idB, map);

  // 消歧：任一侧有多个候选时返回候选列表，不静默选一个（假绿禁令）
  if (resA.ambiguous || resB.ambiguous) {
    return new Response(JSON.stringify({
      success: false,
      ambiguous: true,
      query_a: idA, query_b: idB,
      candidates_a: resA.candidates || (resA.not_found ? [] : undefined),
      candidates_b: resB.candidates || (resB.not_found ? [] : undefined),
      hint: '请从 candidates 中选择具体 ID 后重试。例如 ?a=ACT-028&b=SEN-049',
    }), { status: 200, headers: corsHeaders });
  }

  // 未找到
  if (resA.not_found) {
    return new Response(JSON.stringify({
      success: false,
      not_found: true,
      query: idA,
      candidates: resA.candidates || [],
      hint: `未在 868 个实体中匹配到「${idA}」。试试精确 ID（如 ACT-028）或更具体的名称（如 Robotiq 2F-85）。`,
    }), { status: 404, headers: corsHeaders });
  }
  if (resB.not_found) {
    return new Response(JSON.stringify({
      success: false,
      not_found: true,
      query: idB,
      candidates: resB.candidates || [],
      hint: `未在 868 个实体中匹配到「${idB}」。试试精确 ID 或更具体的名称。`,
    }), { status: 404, headers: corsHeaders });
  }

  // 记录解析痕迹（便于用户看到"我说的是 UR5e，系统理解为 PLAT-035"）
  const resolveTrace = {};
  if (!resA.exact) resolveTrace.a = { input: idA, resolved_id: resA.resolved_id, matched_field: resA.matched_field };
  if (!resB.exact) resolveTrace.b = { input: idB, resolved_id: resB.resolved_id, matched_field: resB.matched_field };

  const a = resA.entity, b = resB.entity;
  const resolvedIdA = resA.resolved_id, resolvedIdB = resB.resolved_id;

  const verdict = judgePair(a, b);

  // 三态 → 可执行跳转：incompatible 时给一条"生成转接件"的直链（两侧零件 id 自动带过去）。
  // 目的：让"发现不兼容"不再是流程终点，而是通向解决的一步（M4-P0-1 + M5-P0-3）。
  // 只在明确 incompatible 时给；compatible / unknown 都不给——
  // unknown 是给"我不知道"用的诚实态，绝不能暗示"我们能修"。
  const verdictStr = String(verdict.verdict || verdict.result || verdict.compatible || '').toLowerCase();
  const isIncompatible = verdictStr.includes('incompatible') ||
    verdictStr === 'false' || verdictStr === 'no' || verdictStr === '0';
  const out = { success: true, ...verdict };
  if (Object.keys(resolveTrace).length > 0) {
    out.resolve_trace = resolveTrace;
    out.resolve_note = '输入的不是本库内部 ID，已按名称/型号模糊匹配到具体实体。若理解有误，请改用精确 ID 重试。';
  }
  if (isIncompatible) {
    const base = 'https://roboparts.cc/adapter-generator';
    // 用解析后的真实实体 ID 生成转接件链接（避免用户拿到一个名字而不是 ID）
    out.adapter_url = base + '?a=' + encodeURIComponent(resolvedIdA) + '&b=' + encodeURIComponent(resolvedIdB);
    out.adapter_cta = '两侧法兰不一致，生成转接件把它变兼容 →';
  }

  return new Response(JSON.stringify(out, null, 2), { status: 200, headers: corsHeaders });
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
