/**
 * 站内零件兼容推荐流水线（P1）
 * ─────────────────────────────────────────────────────────────────────────
 * 架构借鉴 X 平台 x-algorithm 的 **Candidate Pipeline**：Source / Hydrator /
 * Filter / Scorer 各自是可插拔的纯函数 stage，按顺序串成流水线。这里把同一思想
 * 平移到 RoboParts 的场景——「给定零件 → 召回兼容零件 → 排序 → 可解释输出」。
 *
 * ⚠️ 纪律：本模块**不重新实现兼容裁决**。裁决的 SSOT 仍是 compat_engine.js 的
 * `judgePair` / `scoreBreakdown`。recommender 只做「编排」：召回候选、过滤、
 * 调仲裁引擎打分、排序。任何一处想改裁决逻辑都该去 compat_engine，不是这里。
 *
 * 调用形态：
 *   const recommend = buildRecommender();           // 用默认 stage
 *   const res = await recommend(forId, map, {limit});// map = {id: entity}
 * 与 HTTP/ASSETS 层解耦：端点 /api/recommend.js 负责加载 map 后调用本函数。
 */

import { judgePair } from './compat_engine.js';

/**
 * Source 召回信号：从实体抽取用于「召回」的归一化 token（协议 + 机械接口）。
 * 与 X 的 Source trait 同职责——低成本地圈出候选池，不做精确裁决。
 */
function recallTokens(e) {
  const t = new Set();
  const norm = (s) => String(s || '')
    .toLowerCase().split(/[\s,;/、|]+/).map((x) => x.trim()).filter(Boolean);
  for (const k of ['protocol', 'protocols', 'comm_protocol', 'interface', 'interfaces']) {
    const v = e[k];
    if (typeof v === 'string') norm(v).forEach((x) => t.add('p:' + x));
    else if (Array.isArray(v)) v.forEach((x) => norm(x).forEach((y) => t.add('p:' + y)));
  }
  for (const k of ['mechanical_interface', 'mounting', 'connector', 'flange', 'mount']) {
    const v = e[k];
    if (typeof v === 'string') norm(v).forEach((x) => t.add('m:' + x));
    else if (Array.isArray(v)) v.forEach((x) => norm(x).forEach((y) => t.add('m:' + y)));
  }
  return t;
}

// ───────────────────────── 默认 stage 实现（均可插拔替换） ─────────────────────────

/** Source：召回候选 ID。信号 = 同接口 token 重叠 或 同类别。 */
function defaultSource(target, all) {
  const tt = recallTokens(target);
  const out = [];
  const seen = new Set([target.id]);
  for (const e of all) {
    if (seen.has(e.id)) continue;
    if (e.category === target.category) { out.push(e.id); continue; }
    const et = recallTokens(e);
    let overlap = false;
    for (const tok of tt) if (et.has(tok)) { overlap = true; break; }
    if (overlap) out.push(e.id);
  }
  return out;
}

/** Hydrate：把候选 ID 还原成实体对象（此处直接取 map，预留远程 hydrate 接口）。 */
function defaultHydrate(ids, map) {
  return ids.map((id) => map[id]).filter(Boolean);
}

/**
 * Filter：只保留**确认兼容**（overall_compatible === true）。
 * 硬冲突（false）剔除；未定（null，即"无证据可裁决"）也剔除——把"不知道"当作
 * 推荐项会误导 builder（伪装成"我们推荐你用这个"）。冷启动下这会让召回偏少，
 * 但那是真实的证据缺口，P0/P1 不伪造兼容。未定数量已通过 after_filter 透出供后续分析。
 */
function defaultFilter(judged) {
  return judged.filter(({ verdict }) => verdict.overall_compatible === true);
}

/** Scorer：调 SSOT 的加权分（scoreBreakdown 已在 judgePair 内算好，直接取）。 */
function defaultScorer(filtered) {
  return filtered.map(({ b, verdict }) => ({
    id: b.id,
    name: b.name,
    category: b.category,
    overall_compatible: verdict.overall_compatible,
    compatibility_score: verdict.compatibility_score,
    score_basis: verdict.score_basis,
  }));
}

/**
 * Rank：兼容（有分数）优先，按 weighted_score 降序；未定（score=null）按证据量
 * （weight_sum_decided）降序排后。limit 截断。
 */
function defaultRanker(scored, limit = 10) {
  const rank = (x) => {
    const decided = x.score_basis?.weight_sum_decided || 0;
    // 兼容排前面（1 类），未定排后面（0 类）；类内按分数/证据量降序
    const cls = x.overall_compatible === true ? 1 : 0;
    const key = x.overall_compatible === true ? (x.compatibility_score || 0) : decided;
    return cls * 100000 + key;
  };
  return scored
    .slice()
    .sort((a, b) => rank(b) - rank(a))
    .slice(0, limit);
}

/**
 * 组装推荐流水线。传入任意 stage 即可替换默认实现（可插拔）。
 * 返回 `recommend(forId, map, {limit})`。
 */
export function buildRecommender(stages = {}) {
  const source = stages.source || defaultSource;
  const hydrate = stages.hydrate || defaultHydrate;
  const filter = stages.filter || defaultFilter;
  const scorer = stages.scorer || defaultScorer;
  const ranker = stages.ranker || defaultRanker;

  return async function recommend(forId, map, { limit = 10 } = {}) {
    const target = map[forId];
    if (!target) return { error: '实体不存在: ' + forId, recommendations: [] };

    const candidateIds = await source(target, Object.values(map), map); // Source
    const hydrated = await hydrate(candidateIds, map);                  // Hydrate
    const judged = hydrated.map((b) => ({ b, verdict: judgePair(target, b) }));
    const filtered = await filter(judged);                              // Filter
    const scored = await scorer(filtered);                              // Scorer
    const ranked = await ranker(scored, limit);                        // Rank

    return {
      for: { id: target.id, name: target.name, category: target.category },
      pipeline: 'CandidatePipeline(Source→Hydrate→Filter→Score→Rank)',
      source_recalled: candidateIds.length,
      after_filter: filtered.length,
      count: ranked.length,
      recommendations: ranked,
    };
  };
}

// 默认导出开箱即用的实例
export const recommend = buildRecommender();
