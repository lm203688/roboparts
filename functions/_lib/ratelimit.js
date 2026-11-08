/**
 * 滑动窗口限流（P0-12）
 *
 * 为什么必须有它：
 *   此前**零限流** —— X-RateLimit-Limit 只是响应头声明（地基审计 2.2），
 *   register.js:168 存的 rate_limit:30 从不执行；无任何 429 逻辑。公共数据端点
 *   可被脚本刷爆，且付费墙/计费端点（POST /payment/*）无防护 = 可被无限叩击。
 *
 * 实现：
 *   - 复用**已存在**的 USER_CREDITS KV（前缀 `rl:`），不新增绑定 → 不引入部署风险。
 *   - 固定窗口计数（bucket = floor(now/windowMs)），超限返回 429 + Retry-After。
 *   - 窗口桶带 TTL（expirationTtl = 窗口剩余秒），KV 自动清理，不长期占用。
 *   - **失败开放**：KV 不可用 → 放行 + X-RateLimit-Status: degraded。限流是
 *     可用性保护不是正确性；限流把自己也限死 = 反向 DoS（可用性 > 严格性）。
 *   - 诚实标记：KV 最终一致（~60s），限流不是精确计数，但**是真执行**（此前连
 *     执行都没有）。响应头 X-RateLimit-Limit / Remaining / Reset 如实上报。
 *
 * 用法：
 *   import { checkRateLimit, rateLimitHeaders } from '../_lib/ratelimit.js';
 *   const rl = await checkRateLimit(env, { ip, scope: 'api:entities', limit: 300, windowSec: 3600 });
 *   if (!rl.allowed) return new Response(JSON.stringify({error:'rate limited'}), {
 *     status: 429, headers: { 'Content-Type':'application/json', ...rateLimitHeaders(rl), ...cors } });
 *   // 放行时也要带 rl 头，让调用方知道限额。
 */

export async function checkRateLimit(env, opts) {
  const ip = (opts.ip || 'unknown').slice(0, 64);
  const scope = (opts.scope || 'global').slice(0, 64);
  const limit = Math.max(1, opts.limit || 60);
  const windowSec = Math.max(10, opts.windowSec || 3600);
  const res = {
    allowed: true,
    remaining: limit - 1,
    retryAfter: 0,
    degraded: false,
    limit,
    windowSec,
    used: 1,
  };
  if (!env || !env.USER_CREDITS) {
    res.degraded = true;
    res.used = 0;
    res.remaining = limit;
    return res;
  }
  const now = Date.now();
  const windowMs = windowSec * 1000;
  const bucket = Math.floor(now / windowMs);
  const key = `rl:${ip}:${scope}:${bucket}`;
  try {
    const raw = await env.USER_CREDITS.get(key);
    const used = (raw ? parseInt(raw, 10) : 0) || 0;
    res.used = used + 1;
    if (used >= limit) {
      res.allowed = false;
      res.remaining = 0;
      res.retryAfter = Math.max(1, Math.ceil((windowMs - (now % windowMs)) / 1000));
    } else {
      res.remaining = limit - used - 1;
      const ttl = Math.max(30, windowSec - Math.floor((now % windowMs) / 1000));
      await env.USER_CREDITS.put(key, String(used + 1), { expirationTtl: ttl });
    }
  } catch (e) {
    res.degraded = true;
    res.used = 0;
    res.remaining = limit;
  }
  return res;
}

export function rateLimitHeaders(rl) {
  const h = {
    'X-RateLimit-Limit': String(rl.limit || 60),
    'X-RateLimit-Remaining': String(Math.max(0, rl.remaining || 0)),
    'X-RateLimit-Status': rl.degraded ? 'degraded' : 'ok',
  };
  if (rl.retryAfter > 0) h['Retry-After'] = String(rl.retryAfter);
  return h;
}
