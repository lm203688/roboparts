/**
 * Credits Balance API
 * GET /api/credits/balance?key=xxx → returns user's credit balance
 * POST /api/credits/redeem → redeem a Creem license key for credits
 *
 * Security note: Cloudflare KV is encrypted at rest. The email_hash field
 * (SHA-256) is an additional application-layer security measure that allows
 * email-based lookups/comparisons without relying on the plaintext value.
 */

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

import { readLedger } from '../../_lib/ledger.js';

/**
 * 读账本用于附带展示。读不出来时返回 null（不是 []）——
 * [] 会被上层读成"这个账户没有任何交易"，而真相是我们没读到。
 */
async function readHistoryField(env, apiKey) {
  const read = await readLedger(env, apiKey);
  return {
    history: (read.status === 'ok' || read.status === 'empty') ? read.records : null,
    ledger_status: read.status,
    ledger_backend: read.backend,
  };
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    }
  });
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const apiKey = url.searchParams.get('key') || 
                 request.headers.get('Authorization')?.replace('Bearer ', '');
  
  const corsHeaders = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
  };
  
  if (!apiKey) {
    return new Response(JSON.stringify({ error: 'API key required' }), {
      status: 401, headers: corsHeaders
    });
  }
  
  // 存储未配置 ≠ 你余额为 0。这是我们的问题，必须说是我们的问题。
  if (!env.USER_CREDITS) {
    return new Response(JSON.stringify({
      error_kind: 'service_unconfigured',
      error: '积分系统未配置，无法查询余额（这不代表你的余额为 0）。',
    }), { status: 503, headers: corsHeaders });
  }

  const userData = await env.USER_CREDITS.get(apiKey);

  // Key 不存在 ≠ 一个余额为 0 的 free 账户。
  // 旧实现在这里返回 200 + {credits:0, plan:'free', message:'去充值'}，于是：
  //   - 用户把 key 打错一个字符 → 页面显示"0 积分 / free"，他会以为积分被清零，
  //     或者真的去给一个不存在的账户充值；
  //   - 而同一个 key 打到 /api/credits/history 却得到 401「API Key 无效或不存在」，
  //     两个接口对同一个 key 给出互相矛盾的答案。
  // 现在与 history.js 统一口径：404 + not_found。
  if (!userData) {
    return new Response(JSON.stringify({
      error_kind: 'not_found',
      error: 'API Key 无效或不存在。请核对 key；若尚未注册请先访问 /api/register 获取。',
    }), { status: 404, headers: corsHeaders });
  }

  let user;
  try {
    user = JSON.parse(userData);
  } catch (e) {
    return new Response(JSON.stringify({
      error_kind: 'account_corrupt',
      error: '账户记录存在但无法解析，已记录待人工核查（这不代表你的余额为 0）。',
    }), { status: 500, headers: corsHeaders });
  }

  const led = await readHistoryField(env, apiKey);
  return new Response(JSON.stringify({
    email_hash: user.email_hash,
    credits: user.credits || 0,
    plan: user.plan || 'free',
    api_calls: user.api_calls || 0,
    history: led.history,               // 不可读时为 null，不是 []
    ledger_status: led.ledger_status,
    ledger_backend: led.ledger_backend,
  }), { headers: corsHeaders });
}

export async function onRequestPost(context) {
  const { request, env } = context;
  const corsHeaders = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  };

  try {
    const body = await request.json();
    const { license_key, email, api_key } = body;

    // 如果只传了 api_key（无 license_key），则查询余额
    if (!license_key && api_key) {
      if (!env.USER_CREDITS) {
        return new Response(JSON.stringify({
          error_kind: 'service_unconfigured',
          error: '积分系统未配置，无法查询余额（这不代表你的余额为 0）。',
        }), { status: 503, headers: corsHeaders });
      }
      const userData = await env.USER_CREDITS.get(api_key);
      if (userData) {
        const user = JSON.parse(userData);
        const led = await readHistoryField(env, api_key);
        return new Response(JSON.stringify({
          email_hash: user.email_hash,
          credits: user.credits || 0,
          plan: user.plan || 'free',
          api_calls: user.api_calls || 0,
          history: led.history,           // 不可读时为 null，不是 []
          ledger_status: led.ledger_status,
          ledger_backend: led.ledger_backend,
        }), { headers: corsHeaders });
      }
      // not_found 的响应体里**不要**再带 credits/plan：
      // 那是账户属性，一个不存在的账户没有属性。带上就等于邀请调用方把它当余额读。
      return new Response(JSON.stringify({
        error_kind: 'not_found',
        error: 'API Key 无效或不存在。请核对 key；若尚未注册请先访问 /api/register 获取。',
      }), { status: 404, headers: corsHeaders });
    }

    if (!license_key) {
      return new Response(JSON.stringify({ error: 'license_key or api_key required' }), {
        status: 400, headers: corsHeaders
      });
    }
    
    // Validate license with Creem API
    const CREEM_API_KEY = env.CREEM_API_KEY;
    const creemResponse = await fetch('https://api.creem.io/v1/licenses/validate', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': CREEM_API_KEY,
      },
      body: JSON.stringify({ license_key }),
    });
    
    const creemData = await creemResponse.json();
    
    if (!creemData.valid && !creemData.activated) {
      return new Response(JSON.stringify({ error: 'Invalid license key' }), {
        status: 400, headers: corsHeaders
      });
    }
    
    // Determine credit amount based on product
    const productId = creemData.product?.id || '';
    let credits = 0;
    if (productId.includes('22YhSbY')) credits = 990; // Pro monthly
    else if (productId.includes('4EpFVQ')) credits = 500; // API Access
    else if (productId.includes('pny43r')) credits = 9999; // Lifetime
    else if (productId.includes('5IooNC')) credits = 4999; // One-time data
    else credits = 100; // Default
    
    // Store in KV
    if (env.USER_CREDITS) {
      // Determine user key: use provided api_key if it exists in KV, otherwise generate new gtk_ key
      let userKey;
      if (api_key && api_key.startsWith('gtk_')) {
        const existingCheck = await env.USER_CREDITS.get(api_key);
        if (existingCheck) {
          userKey = api_key;
        }
      }
      if (!userKey) {
        userKey = 'gtk_' + Array.from(crypto.getRandomValues(new Uint8Array(24)))
          .map(b => b.toString(16).padStart(2, '0')).join('');
      }
      
      const existing = await env.USER_CREDITS.get(userKey);
      const user = existing ? JSON.parse(existing) : { credits: 0, plan: 'free', api_calls: 0, created: new Date().toISOString() };
      user.credits = (user.credits || 0) + credits;
      if (email) {
        // Compute SHA-256 hash of the email for application-layer lookups
        user.email_hash = await hashEmail(email);
      }
      user.plan = 'pro';
      await env.USER_CREDITS.put(userKey, JSON.stringify(user));
      
      return new Response(JSON.stringify({
        success: true,
        api_key: userKey,
        credits_added: credits,
        total_credits: user.credits,
        plan: 'pro',
      }), { headers: corsHeaders });
    }
    
    return new Response(JSON.stringify({
      success: true,
      credits_added: credits,
      message: 'License valid. Contact support to activate credits.',
    }), { headers: corsHeaders });
    
  } catch(e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500, headers: corsHeaders
    });
  }
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
