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

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const idA = url.searchParams.get('a');
  const idB = url.searchParams.get('b');

  if (!idA || !idB) {
    return new Response(JSON.stringify({
      error: '缺少参数',
      usage: '/api/compatibility?a=ACT-001&b=SEN-001',
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

  const a = map[idA], b = map[idB];
  if (!a) return new Response(JSON.stringify({ error: '实体不存在: ' + idA }), { status: 404, headers: corsHeaders });
  if (!b) return new Response(JSON.stringify({ error: '实体不存在: ' + idB }), { status: 404, headers: corsHeaders });

  const verdict = judgePair(a, b);

  return new Response(JSON.stringify({
    success: true,
    ...verdict,
  }, null, 2), { status: 200, headers: corsHeaders });
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
