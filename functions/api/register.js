/**
 * API Key Registration — CF Pages Function
 * Handles user registration and API key generation
 * Flow: email → generate key → store in KV → return key
 *
 * Security note: Cloudflare KV is encrypted at rest. The email_hash field
 * (SHA-256) is an additional application-layer security measure that allows
 * email-based lookups/comparisons without relying on the plaintext value.
 */

import { appendLedger } from '../_lib/ledger.js';

/**
 * Hash an email address with SHA-256 (lowercased + trimmed for consistency).
 * Uses the Web Crypto API available in Cloudflare Workers runtime.
 * @param {string} email
 * @returns {Promise<string>} hex-encoded SHA-256 digest
 */
async function hashEmail(email) {
  const encoder = new TextEncoder();
  const data = encoder.encode(email.toLowerCase().trim());
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    }
  });
}

/**
 * 【20260805-20 转化归因】判定注册来源。
 *
 * 背景：连续 6 轮真实注册为 0，唯一走通的流量通道是 AI 爬虫（GPTBot /
 * ClaudeBot / PerplexityBot / OAI-SearchBot 已确认抓取）。若第一笔真实注册
 * 到来时无法回答"从哪来的"，就无法把资源投向有效渠道——与 18:00「没有流量
 * 埋点」、19:00「读不存在的字段做判断」是同一类断点：动作发生了却看不见。
 *
 * @param {Request} req
 * @returns {{source: string, detail: string}}
 */
function attribute(req) {
  const ua = (req.headers.get('user-agent') || '').toLowerCase();
  const ref = req.headers.get('referer') || '';
  const via = (req.headers.get('x-roboparts-via') || '').slice(0, 40); // 渠道自带标记

  if (via) return { source: 'channel', detail: via };

  // Agent 直连：AI 助手或脚本代用户执行 curl，通常无 referer、UA 为工具类
  const agentish = ['python-requests', 'node-fetch', 'axios', 'httpx', 'okhttp',
    'go-http-client', 'curl', 'wget', 'postman', 'openai', 'anthropic', 'langchain'];
  const hit = agentish.find((a) => ua.includes(a));
  if (hit) return { source: 'agent', detail: hit };

  if (ref) {
    try {
      const h = new URL(ref).hostname.replace(/^www\./, '');
      // 站内跳转记为 web，站外记为 referral 并保留来源域名
      return h.endsWith('roboparts.cc')
        ? { source: 'web', detail: new URL(ref).pathname.slice(0, 40) }
        : { source: 'referral', detail: h };
    } catch { /* referer 畸形，落到 unknown */ }
  }
  return { source: 'unknown', detail: ua.slice(0, 40) || 'no-ua' };
}

/**
 * GET 自述。
 * 【20260807-16】此前本端点只导出 onRequestPost，`GET /api/register` 直接 404。
 * 而 agent-discovery.json 把这个 URL 作为"自助领取 API Key"的入口对外公布 ——
 * Agent 与开发者拿到一个 URL，第一反应几乎都是先 GET 探一下。探到 404，
 * 得到的结论是"这个入口不存在"，而不是"应该改用 POST"。
 * **对外公布的地址，在用错方法时要把人送回正轨，不能装作自己不存在**
 * （同 L1.41 的 did_you_mean 思路：错误响应也是接入文档的一部分）。
 */
export async function onRequestGet() {
  return new Response(JSON.stringify({
    error: 'Method Not Allowed',
    message: '本端点用于自助领取 API Key，需以 POST 提交邮箱。',
    method: 'POST',
    endpoint: 'https://roboparts.cc/api/register',
    request_body: { email: 'string - 你的邮箱，用于接收与找回 Key' },
    example_curl: "curl -X POST https://roboparts.cc/api/register "
      + "-H 'Content-Type: application/json' -d '{\"email\":\"you@example.com\"}'",
    free_quota: '100 次/月，无需审批',
    docs: 'https://roboparts.cc/llms.txt',
  }, null, 2), {
    status: 405,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Allow': 'POST, OPTIONS',
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  });
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被探成"不存在"，比慢比错都糟。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead() {
  const r = await onRequestGet();
  return new Response(null, { status: r.status, headers: r.headers });
}

export async function onRequestPost(context) {
  const { request, env } = context;

  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
  };

  try {
    const body = await request.json();
    const email = body.email;
    
    if (!email || !email.includes('@')) {
      return new Response(JSON.stringify({ error: 'Valid email required' }), {
        status: 400, headers: corsHeaders
      });
    }
    
    // Compute SHA-256 hash of the email for application-layer lookups
    const emailHash = await hashEmail(email);

    /* 【20260805-20 自检隔离】飞轮每轮会对注册端点做端到端探活。若不分账，
       这些自测会被计入 stat:users:total，下一轮就会把自己的运维动作读成
       "有真实用户注册"。同 18:00 的探针污染、deploy.mjs 校验请求污染。
       隔离键用 selftest_ 前缀，可被 read_metrics / 清理脚本按前缀识别。 */
    const isSelftest = request.headers.get('x-roboparts-selftest') === '1';
    const attr = attribute(request);

    // Generate API key
    const key = (isSelftest ? 'selftest_' : 'gtk_')
      + Array.from(crypto.getRandomValues(new Uint8Array(24)))
        .map(b => b.toString(16).padStart(2, '0')).join('');

    const userData = {
      email_hash: emailHash, credits: 100, plan: 'free', api_calls: 0, role: 'user',
      created: new Date().toISOString(),
      source: attr.source, source_detail: attr.detail, selftest: isSelftest
    };
    
    // Store in KV (permanent, no TTL) — email stored as hash only, never plaintext
    if (env.API_KEYS) {
      await env.API_KEYS.put(key, JSON.stringify({
        email_hash: emailHash, plan: 'free', role: 'user', created: new Date().toISOString(),
        rate_limit: 30, calls_today: 0, source: attr.source, selftest: isSelftest
      }));
    }
    
    // Also create record in USER_CREDITS with same gtk_ key
    if (env.USER_CREDITS) {
      await env.USER_CREDITS.put(key, JSON.stringify(userData));
    }

    // B3 度量断点修复：注册用户数 +1（KV 读-改-写计数器，前缀 stat: 避免与 gtk_ 用户键冲突）
    // 自检注册不计入任何真实统计，只写隔离命名空间，保证转化基线可信。
    try {
      const statKey = isSelftest ? 'stat:selftest:registrations' : 'stat:users:total';
      const cur = await env.USER_CREDITS.get(statKey);
      const n = (cur ? parseInt(cur, 10) : 0) || 0;
      await env.USER_CREDITS.put(statKey, String(n + 1));

      // 真实注册按来源分桶，回答"第一个用户从哪来"——决定下一步资源投向
      if (!isSelftest) {
        const srcKey = `stat:src:${attr.source}`;
        const sc = await env.USER_CREDITS.get(srcKey);
        await env.USER_CREDITS.put(srcKey, String(((sc ? parseInt(sc, 10) : 0) || 0) + 1));
        // 保留首个真实注册的完整现场，只写一次，供人工复盘
        if (!(await env.USER_CREDITS.get('stat:first_signup'))) {
          await env.USER_CREDITS.put('stat:first_signup', JSON.stringify({
            at: new Date().toISOString(), source: attr.source, detail: attr.detail,
            ua: (request.headers.get('user-agent') || '').slice(0, 120),
            ref: (request.headers.get('referer') || '').slice(0, 120)
          }));
        }
      }
    } catch (e) { /* 度量失败不影响注册主流程 */ }
    
    // Write initial credit history record
    // 旧写法 `if (env.USER_CREDIT_HISTORY) {...}` 在该 KV 从未绑定的生产环境里
    // 恒为 false —— 赠送记录一条都没写过，而查询页照样说"你没有交易记录"。
    // 现在走统一入口（自动回落到已绑定的 USER_CREDITS），失败要留痕、要外露。
    const ledgerWrite = await appendLedger(env, key, {
      type: 'grant',
      amount: 100,
      balance: 100,
      description: '注册赠送',
      timestamp: new Date().toISOString(),
    });
    if (!ledgerWrite.ok) {
      console.error('[register] ledger append failed', { reason: ledgerWrite.reason, backend: ledgerWrite.backend });
    }

    return new Response(JSON.stringify({
      success: true,
      api_key: key,
      plan: 'free',
      credits: 100,
      rate_limit: '30 requests/hour',
      message: 'Save your API key. Use it as: Authorization: Bearer ' + key,
      upgrade_url: 'https://roboparts.cc/credits',
      ledger_recorded: ledgerWrite.ok,
      ledger_error: ledgerWrite.ok ? undefined : ledgerWrite.reason,
    }), { headers: corsHeaders });
    
  } catch(e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500, headers: corsHeaders
    });
  }
}
