/**
 * 双流零件发现端点（V-Link 借鉴 · 产品化落地）
 * GET /api/discover?of=<entityId>&q=<text>&limit=10
 *
 * 映射 V-Link「别把几何与语义压成一个 embedding，分开建流再融合」的思路：
 *   - 语义流(semantic)：对查询词 / 种子零件做哈希 TF-IDF 余弦召回（复用 compat_engine.semanticSearch）。
 *   - 几何流(geometric)：对种子零件跑 judgePair 四维硬约束裁决（协议/电气/机械/软件），
 *     找出"已验证可兼容"(overall_compatible=true) 的零件。
 *   - 融合：两流候选并集，排除 overall=false（硬不兼容已证伪），按透明加权排序：
 *       fusion = 0.6 * semantic_similarity + 0.4 * geometric_bonus
 *       geometric_bonus = 1（overall=true 已验证兼容）/ 0.35（overall=null 无硬证据·未验证）/ 0（排除）
 *   每个候选都回传两流各自的子分数与裁决理由，绝不做黑箱；overall=null 永不计为兼容。
 *
 * 诚实边界：几何流仅在 MI 数据存在时有产出（当前机械接口声明率 ~1.52%，故几何流通常稀疏）；
 * 此时发现以语义流主导、几何流作"已验证/未验证"标记 —— 不把无证据伪装成兼容（守假绿纪律）。
 */
import { judgePair, loadEntityMap, semanticSearch } from '../_lib/compat_engine.js';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const of = (url.searchParams.get('of') || '').trim();
  const q = (url.searchParams.get('q') || '').trim();
  const limit = Math.min(Math.max(parseInt(url.searchParams.get('limit') || '10', 10) || 10, 1), 50);
  if (!of && !q) {
    return new Response(JSON.stringify({
      error: '缺少参数 of 或 q',
      usage: '/api/discover?of=ACT-028&limit=10 或 /api/discover?q=六维力传感器',
    }), { status: 400, headers: corsHeaders });
  }
  try {
    const map = await loadEntityMap(env, request);
    let seed = null;
    if (of) {
      seed = map[of];
      if (!seed) {
        return new Response(JSON.stringify({ error: `未找到实体: ${of}` }),
          { status: 404, headers: corsHeaders });
      }
    }

    // ── 语义流：TF-IDF 余弦召回（宽召回） ──────────────────────────────
    const semQuery = q || [
      seed.name, seed.type,
      Array.isArray(seed.applications) ? seed.applications.join(' ') : '',
      seed.standard_conformance,
    ].filter(Boolean).join(' ');
    const semRes = await semanticSearch(env, request, semQuery, Math.max(limit * 4, 40));
    const semMap = {};
    if (semRes && semRes.available && Array.isArray(semRes.results)) {
      for (const r of semRes.results) semMap[r.id] = r.similarity;
    }

    // ── 几何流：对种子零件跑 judgePair 四维硬约束（精确过滤） ───────────
    // 仅把"已验证兼容"(overall=true) 的零件作为几何流独立候选纳入（封顶保护 CF CPU，
    // 几何流天然稀疏）；null（无硬证据）不单独成候选，只在语义命中的件上附 verdict。
    const judged = {};   // id -> judgePair 结果（种子模式全量缓存，避免重复计算）
    const geomMap = {}; // id -> {overall, score, reason}
    if (seed) {
      let kept = 0;
      for (const id of Object.keys(map)) {
        if (id === of) continue;
        const j = judgePair(seed, map[id]);
        judged[id] = j;
        if (j.overall_compatible === true) {
          geomMap[id] = { overall: true, score: j.compatibility_score, reason: j.verdict_reason };
          kept += 1;
        }
        if (kept >= 20) break;
      }
    }

    // ── 融合：两流候选并集，排除硬不兼容，透明加权排序 ─────────────────
    const candIds = new Set([...Object.keys(semMap), ...Object.keys(geomMap)]);
    const ranked = [];
    for (const id of candIds) {
      if (seed && id === of) continue; // 不把种子零件自身当"发现"结果（自比还会判成兼容）
      const e = map[id];
      if (!e) continue;
      const j = seed ? (judged[id] || judgePair(seed, e)) : null;
      const overall = j ? j.overall_compatible : null;
      if (overall === false) continue; // 硬不兼容，直接排除
      const sim = semMap[id] != null ? semMap[id] : 0;
      const geomBonus = overall === true ? 1 : (overall === null ? 0.35 : 0);
      const fusion = Math.round((0.6 * sim + 0.4 * geomBonus) * 1000) / 1000;
      ranked.push({
        id,
        name: e.name,
        category: e.category,
        semantic_similarity: sim,
        geometric_verdict: overall,        // true | null（false 已被排除）
        compatibility_score: j ? j.compatibility_score : null,
        fusion_score: fusion,
        reason: j ? j.verdict_reason
          : (sim > 0 ? '语义相近（几何流无双方声明，未验证兼容）' : '几何流已验证兼容'),
      });
    }
    ranked.sort((a, b) => b.fusion_score - a.fusion_score);

    const out = {
      available: true,
      method: 'V-Link 双流融合：semantic(TF-IDF 余弦宽召回) + geometric(judgePair 四维硬约束) | '
        + 'fusion=0.6*similarity+0.4*geomBonus(verified=1/unverified=0.35) | 排除 overall=false',
      seed: seed ? { id: seed.id, name: seed.name, category: seed.category } : null,
      query: q || null,
      honest_boundary: 'geometric_verdict=null 表示几何流无双方声明、无法判定兼容，不等于兼容；'
        + 'overall=false 已排除。语义相近 ≠ 能装在一起。',
      semantic_available: !!(semRes && semRes.available),
      count: ranked.length,
      results: ranked.slice(0, limit),
    };
    return new Response(JSON.stringify(out, null, 2), { status: 200, headers: corsHeaders });
  } catch (e) {
    return new Response(JSON.stringify({ error: '发现失败: ' + e.message }),
      { status: 500, headers: corsHeaders });
  }
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
