/**
 * @deprecated 20260807-17 —— Creem 国际支付通道已下线。
 *
 * 背景：Creem 账户始终未开启 Live Payments，所有真实点击都撞 "Live Payments Not Enabled"；
 * 8/6 决定去除该通道（海外自助付费需求极小，维护双网关的代价大于收益）。
 * 8/7 16:40 已从 credits.html / pricing.html 摘除入口，但**本端点仍然在线**，
 * 且 /api-pricing 的 FAQ 仍在对外承诺"credit card / PayPal / crypto via Creem"。
 *
 * 于是形成最坏的一种残留：入口看不见了，但地址还活着、文档还在推荐 ——
 * 任何存了旧链接、读了旧 FAQ、或让 Agent 照文档拼 URL 的人，
 * 拿到的不是"此路不通"，而是一个**会创建订单再失败**的收银台。
 * **下线一条收款通道，必须连同它的 URL 一起下线；留着的端点会替你继续做承诺。**
 *
 * 因此这里不删文件（删了会回落成 404，说不清是"没有"还是"搬走了"），
 * 而是显式 410 Gone + 指向仍然可用的路径。见 regression L1.45。
 */
const HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Allow': 'OPTIONS',
  'Content-Type': 'application/json; charset=utf-8',
  'Cache-Control': 'public, max-age=3600',
};

const BODY = {
  error: 'Gone',
  message: 'Creem 国际支付通道已于 2026-08-07 下线，本端点不再创建收银台。',
  message_en: 'The Creem international checkout was retired on 2026-08-07. This endpoint no longer creates checkouts.',
  use_instead: {
    self_serve: 'POST https://roboparts.cc/api/payment/create  (WeChat Pay / Alipay, CNY)',
    page: 'https://roboparts.cc/credits',
    outside_china: 'mailto:61960005@qq.com — 人工开票 + 手工发放积分 / manual invoicing',
  },
  reason: 'Live payments were never enabled on the Creem account; keeping the route alive only produced checkouts that failed after order creation.',
};

function gone() {
  return new Response(JSON.stringify(BODY, null, 2), { status: 410, headers: HEADERS });
}

export const onRequestGet = gone;
export const onRequestPost = gone;
export const onRequestPut = gone;
export const onRequestDelete = gone;

export async function onRequestOptions() {
  return new Response(null, { status: 204, headers: HEADERS });
}
