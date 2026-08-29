/**
 * 可嵌入徽章端点 —— GET /api/badge
 *
 * 返回一个 shields 风格 SVG，显示 RoboParts 实时实体数。
 * 用途：让开源人形 DIY 项目的 README / 博客通过
 *   <img src="https://www.roboparts.cc/api/badge" />
 * 直接"嫁接"本项目，访客点击徽章即回流主站 —— 这是零成本的平台嫁接钩子。
 *
 * 设计纪律：徽章只展示"<N> 机器人零部件 · 开源兼容数据库"这一诚实、正向、可验证的事实，
 * 不展示"兼容声明 1.68%"这类会削弱信任的数字（那是引擎待修项，不是卖点）。
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Content-Type': 'image/svg+xml; charset=utf-8',
  'Cache-Control': 'public, max-age=300',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}

export async function onRequestGet(context) {
  let total = '—';
  try {
    const d = await (await fetch('/api/data.json')).json();
    total = d?.meta?.total_entities ?? '—';
  } catch (e) { /* 取数失败不影响徽章渲染，显示占位符 */ }

  const label = 'RoboParts';
  const msg = (typeof total === 'number' ? total : '—') + ' 机器人零部件';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="236" height="20" role="img" aria-label="${label}: ${msg}">
  <linearGradient id="g" x1="0" x2="1" y1="0" y2="0">
    <stop offset="0%" stop-color="#0b1020"/>
    <stop offset="100%" stop-color="#13204a"/>
  </linearGradient>
  <rect width="236" height="20" rx="3" fill="url(#g)"/>
  <rect width="94" height="20" rx="3" fill="#3b82f6"/>
  <text x="47" y="14" fill="#fff" font-family="monospace,Consolas" font-size="11" text-anchor="middle" font-weight="bold">${label}</text>
  <text x="158" y="14" fill="#e5e7eb" font-family="monospace,Consolas" font-size="11" text-anchor="middle">${msg}</text>
</svg>`;
  return new Response(svg, { status: 200, headers: corsHeaders });
}
