/**
 * 语义检索端点（P1 语义层 · Web 入口）
 * GET /api/semantic-search?q=六维力传感器&limit=5
 *
 * 复用 compat_engine.semanticSearch：对查询做哈希 TF-IDF 向量化 → 在构建时预计算的
 * 本地索引（api/semantic_index.json）上余弦召回。零外发、零模型、零成本。
 *
 * 诚实边界：语义相近 ≠ 兼容性。本端点只返回"语义最相近的零件"，
 * 不给出 compatibility 结论；是否与查询零件可互换，仍需 /api/compatibility 裁决。
 */
import { semanticSearch } from '../_lib/compat_engine.js';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const q = (url.searchParams.get('q') || url.searchParams.get('query') || '').trim();
  const limit = Math.min(Math.max(parseInt(url.searchParams.get('limit') || '5', 10) || 5, 1), 50);
  if (!q) {
    return new Response(JSON.stringify({ error: '缺少查询参数 q', usage: '/api/semantic-search?q=六维力传感器&limit=5' }),
      { status: 400, headers: corsHeaders });
  }
  const res = await semanticSearch(env, request, q, limit);
  return new Response(JSON.stringify(res, null, 2), { status: 200, headers: corsHeaders });
}

export async function onRequestPost(context) {
  const { request, env } = context;
  let body = {};
  try { body = await request.json(); } catch { /* 空 body 走 query 参数 */ }
  const q = String(body.query || body.q || '').trim();
  const limit = Math.min(Math.max(parseInt(body.limit || '5', 10) || 5, 1), 50);
  if (!q) {
    return new Response(JSON.stringify({ error: '缺少 query 字段' }), { status: 400, headers: corsHeaders });
  }
  const res = await semanticSearch(env, request, q, limit);
  return new Response(JSON.stringify(res, null, 2), { status: 200, headers: corsHeaders });
}
