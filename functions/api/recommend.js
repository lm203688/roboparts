/**
 * 站内零件兼容推荐端点（P1）—— 借鉴 X 平台 Candidate Pipeline 架构
 * GET /api/recommend?for=ACT-001&limit=10
 *
 * 编排逻辑全部在 ../_lib/recommender.js（buildRecommender），本文件只做 HTTP 形态：
 * 参数解析 / 加载实体 map / CORS / 状态码。兼容裁决的 SSOT 在 compat_engine.js。
 */

import { recommend } from '../_lib/recommender.js';
import { loadEntityMap } from '../_lib/compat_engine.js';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestHead() {
  return new Response(null, { status: 200, headers: corsHeaders });
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const forId = url.searchParams.get('for');
  const limit = Math.min(Math.max(parseInt(url.searchParams.get('limit') || '10', 10) || 10, 1), 50);

  if (!forId) {
    return new Response(JSON.stringify({
      error: '缺少参数',
      usage: '/api/recommend?for=ACT-001&limit=10',
    }), { status: 400, headers: corsHeaders });
  }

  let map;
  try {
    map = await loadEntityMap(env, request);
  } catch (e) {
    return new Response(JSON.stringify({
      error: '数据源不可用',
      detail: String(e && e.message || e),
    }), { status: 503, headers: corsHeaders });
  }

  const res = await recommend(forId, map, { limit });
  if (res.error && !res.recommendations) {
    return new Response(JSON.stringify(res), { status: 404, headers: corsHeaders });
  }
  return new Response(JSON.stringify(res), { status: 200, headers: corsHeaders });
}
