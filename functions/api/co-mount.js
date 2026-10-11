/**
 * 共装查询 REST 端点 —— 把 co_mount 研究层能力做成用户/Agent 可查的产品入口。
 *
 *   GET /api/co-mount                                  → 全层摘要（关系语义 + 示例）
 *   GET /api/co-mount?host=HUB-030                     → 该宿主单件可装性 + 工具侧取证
 *   GET /api/co-mount?host=HUB-030&a=ACT-028&b=SENS-047 → 单对裁决 + 证据链
 *
 * 与 /api/compatibility?a=&b= 的区别：
 *   后者判「A 能不能插进 B」（二段互插，四维：protocol/electrical/mechanical/software）；
 *   本端点判「A 和 B 能不能**同时**装在同一台机器人的工具侧」（三段共装：
 *   mount_fit + port_budget + signal_complementary）。两者口径不同，不可混用。
 *
 * 【20261008】判定逻辑与 hosted MCP 的 check_co_mount **共用同一份**实现
 *   （../_lib/co_mount_engine.js 的 queryCoMount）—— 与 compatibility.js 顶部同一条纪律：
 *   不得在两处各写一份判定，否则 REST 与 MCP 会对同一对零件给出不同答案。
 */
import { queryCoMount } from '../_lib/co_mount_engine.js';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

/** 读静态资产；缺失返回 null（如实可见，不抛错）。 */
async function fetchAsset(env, request, path) {
  try {
    const r = await env.ASSETS.fetch(new URL('/' + path, request.url));
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const args = {
    host: url.searchParams.get('host') || '',
    a: url.searchParams.get('a') || '',
    b: url.searchParams.get('b') || '',
  };

  const [cm, ts] = await Promise.all([
    fetchAsset(env, request, 'api/co_mount.json'),
    fetchAsset(env, request, 'api/robot_tool_side.json'),
  ]);

  // 数据源故障必须以 5xx 明说，不降级成 404「查无此对」——
  // 那会让调用方以为是自己参数写错（环境要点 #19：兜底可以有，静默不行）。
  if (!cm) {
    return new Response(
      JSON.stringify({
        error: '共装数据源暂时不可用',
        error_kind: 'data_unavailable',
        note: 'api/co_mount.json 未部署或构建失败。',
      }),
      { status: 503, headers: corsHeaders },
    );
  }

  const out = queryCoMount(cm, ts, args);
  // 参数类错误 → 400；数据不足类 → 200（fail-closed 的 unknown 是**有效答案**，不是错误）。
  const status = out.error_kind === 'unknown_host' || out.error_kind === 'not_evaluated' ? 400 : 200;
  return new Response(JSON.stringify(out, null, 2), { status, headers: corsHeaders });
}

/**
 * HEAD 映射到 GET（Cloudflare Pages 不做 HEAD→GET 自动映射，缺它即 404）。
 * 目录站/爬虫用 HEAD 探活，404 会被读成「端点已下线」。
 * 与 compatibility.js / stats.js 同一范式。
 */
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
