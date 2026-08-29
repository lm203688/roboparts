/**
 * CF Pages Function: API Gateway with Field-Level Paywall
 * - Free: summary fields only (id, name, category, focus truncated)
 * - Pro: full data (requires Creem license key)
 */

const PRO_PRODUCTS = [
  'prod_22YhSbYonX9hiC0OppnXTn',
  'prod_4EpFVQGKm5vWXChbRiFdbE',
  'prod_pny43rzDa0mmBaj7d9k4w',
  'prod_5IooNCEQoCyqp758oeVPGT',
  'prod_5OFcAcJeXzfTMkDDt6woBh',
  'prod_44o1TOBce0Zt00X4E5ACET'
];
// P0-2 付费墙修复：免费层默认返回除 PREMIUM_FIELDS 外的全部字段。
// 此前 FREE_FIELDS 引用了 focus/hq/founded/development_stage 等不存在的字段，
// 导致免费/付费返回内容差异失效。现改为"黑名单锁高价值字段"。
//
// 【20260808-11】清单已移入 `_lib/paywall.js` 作为单一真相源。
// 起因是新增 `/api/entity/{id}` 需要同一套判定，若各端点各抄一份，
// 两份清单必然随时间分叉，最终某个端点会在无人察觉时免费送出付费字段。
import { PREMIUM_FIELDS } from '../_lib/paywall.js';

const FOCUS_LIMIT = 200;
const UPGRADE_URL = 'https://roboparts.cc/credits';

// B3 度量：KV 读-改-写计数器（stat: 前缀）
async function bumpStat(env, key, by = 1) {
  if (!env || !env.USER_CREDITS) return;
  try {
    const cur = await env.USER_CREDITS.get(key);
    const n = (cur ? parseInt(cur, 10) : 0) || 0;
    await env.USER_CREDITS.put(key, String(n + by));
  } catch (e) { /* 度量失败不影响主流程 */ }
}

const CREDIT_COSTS = {
  'entities.json': 1,    // Full data export costs 1 credit (fixed from 50)
  'data.json': 0,        // data.json is free (directory data)
  'openapi.json': 0,     // API spec is free
  'graph.json': 0,       // Graph data is free
};

export async function onRequestGet(context) {
  const { request, env, params } = context;
  const url = new URL(request.url);
  const path = params.path || [];
  const pathStr = Array.isArray(path) ? path.join('/') : path;

  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Access-Control-Max-Age': '86400',
  };

  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders });
  }

  const requestedFile = pathStr.endsWith('.json') ? pathStr : pathStr + '.json';

  if (requestedFile.includes('..') || requestedFile.includes('//')) {
    return new Response(JSON.stringify({ error: 'Invalid path' }), {
      status: 400,
      headers: { 'Content-Type': 'application/json', ...corsHeaders },
    });
  }

  try {
    const assetUrl = new URL(`/api/${requestedFile}`, url.origin);
    const assetResponse = await env.ASSETS.fetch(assetUrl);

    // Cloudflare Pages may return index.html (SPA fallback) with status 200
    // when a static asset does not exist. Detect this by inspecting the
    // Content-Type header so we don't accidentally serve HTML as JSON.
    const assetContentType = assetResponse.headers.get('Content-Type') || '';
    const isHtmlFallback = assetContentType.includes('text/html');

    if (!assetResponse.ok || isHtmlFallback) {
      return new Response(JSON.stringify({
        error: 'Not Found',
        path: `/api/${requestedFile}`,
        status: isHtmlFallback ? 404 : assetResponse.status,
        hint: 'Available: entities.json, data.json, openapi.json, graph.json, robot_ai_models.json, flexible_actuators.json'
      }), {
        status: 404,
        headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }

    const data = await assetResponse.text();

    // B3 度量：每次成功的 API 资源读取计一次（总调用 + 当日调用）
    try {
      const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      await bumpStat(env, 'stat:api_calls:total');
      await bumpStat(env, 'stat:api_calls:' + today);
    } catch (e) {}

    // Apply paywall to entities.json only
    if (requestedFile === 'entities.json' || requestedFile.endsWith('/entities.json')) {
      return await applyPaywall(data, request, env, corsHeaders);
    }

    return new Response(data, {
      status: 200,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, max-age=300',
        'X-API-Tier': 'free',
        'X-Powered-By': 'GeneTech API Gateway',
        ...corsHeaders,
      }
    });
  } catch(e) {
    return new Response(JSON.stringify({
      error: 'Internal error',
      message: e.message,
      path: `/api/${requestedFile}`,
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', ...corsHeaders },
    });
  }
}

async function applyPaywall(data, request, env, corsHeaders) {
  let parsed;
  try {
    parsed = JSON.parse(data);
  } catch(e) {
    return new Response(data, {
      status: 200,
      headers: { 'Content-Type': 'application/json; charset=utf-8', ...corsHeaders },
    });
  }

  // Extract key from Authorization header or query parameter
  const authHeader = request.headers.get('Authorization') || '';
  const url = new URL(request.url);
  const queryKey = url.searchParams.get('key') || '';
  let apiKey = '';
  let licenseKey = '';
  if (authHeader.startsWith('Bearer ')) {
    const providedKey = authHeader.slice(7).trim();
    if (providedKey.startsWith('gtk_')) {
      apiKey = providedKey;
    } else {
      licenseKey = providedKey;
    }
  } else if (queryKey) {
    const providedKey = queryKey.trim();
    if (providedKey.startsWith('gtk_')) {
      apiKey = providedKey;
    } else {
      licenseKey = providedKey;
    }
  }

  // Credits system: check for gtk_ prefix API key
  if (apiKey.startsWith('gtk_')) {
    if (env.USER_CREDITS) {
      const userData = await env.USER_CREDITS.get(apiKey);
      if (userData) {
        const user = JSON.parse(userData);
        const cost = CREDIT_COSTS['entities.json'] || 1;
        const INITIAL_CREDITS = user.initial_credits || 100;
        const LOW_THRESHOLD = Math.max(20, Math.floor(INITIAL_CREDITS * 0.2));

        if (user.credits >= cost) {
          // Deduct credits
          user.credits -= cost;
          user.api_calls = (user.api_calls || 0) + 1;

          // Low-credit alert: trigger when credits drop to/below 20% threshold
          const responseHeaders = {
            'Content-Type': 'application/json; charset=utf-8',
            'Cache-Control': 'no-store',
            'X-API-Tier': 'credits',
            'X-Credits-Remaining': String(user.credits),
            'X-Upgrade-URL': UPGRADE_URL,
            ...corsHeaders,
          };

          if (user.credits <= LOW_THRESHOLD) {
            responseHeaders['X-Credits-Warning'] = 'low';
            responseHeaders['X-Credits-Threshold'] = String(LOW_THRESHOLD);
            // Track alert state to avoid spamming (alert once per threshold crossing)
            if (!user.low_alert_sent) {
              user.low_alert_sent = true;
              user.low_alert_at = new Date().toISOString();
            }
          }

          // Reset alert when user recharges above threshold
          if (user.credits > LOW_THRESHOLD && user.low_alert_sent) {
            user.low_alert_sent = false;
            delete user.low_alert_at;
          }

          await env.USER_CREDITS.put(apiKey, JSON.stringify(user));
          return new Response(data, {
            status: 200,
            headers: responseHeaders,
          });
        } else {
          // Insufficient credits: structured 402 with conversion guidance
          return new Response(JSON.stringify({
            error: 'Insufficient credits',
            credits_remaining: user.credits,
            required: cost,
            credits_needed: cost - user.credits,
            recharge_url: 'https://roboparts.cc/credits',
            upgrade_options: [
              { tier: 'Starter', price: '$9/mo', credits: 500, url: 'https://roboparts.cc/credits' },
              { tier: 'Pro', price: '$29/mo', credits: 2000, url: 'https://roboparts.cc/credits' },
              { tier: 'Lifetime', price: '$199', credits: 9999, url: 'https://roboparts.cc/credits' },
            ],
            message: 'Your free credits are exhausted. Recharge to unlock full data access.'
          }), {
            status: 402,
            headers: {
              'Content-Type': 'application/json',
              'X-Credits-Remaining': '0',
              'X-Upgrade-URL': UPGRADE_URL,
              ...corsHeaders,
            }
          });
        }
      }
    }
    // User not found in credits system, fall through to free tier
  }

  // Fallback: Creem license validation (backward compatibility)
  if (licenseKey && !licenseKey.startsWith('gtk_')) {
    const isValid = await validateLicense(licenseKey, env);
    if (isValid) {
      return new Response(data, {
        status: 200,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Cache-Control': 'no-store',
          'X-API-Tier': 'pro',
          ...corsHeaders,
        }
      });
    }
  }

  // Free tier: filter fields
  let entities, meta;
  if (Array.isArray(parsed)) {
    entities = parsed;
    meta = { total: parsed.length };
  } else {
    entities = parsed.entities || parsed.data || [];
    meta = parsed.meta || {};
  }

  const filtered = entities.map(e => {
    const out = {};
    for (const [k, v] of Object.entries(e)) {
      if (!PREMIUM_FIELDS.includes(k)) out[k] = v;
    }
    // Count locked (premium) fields actually present on this entity
    const lockedCount = PREMIUM_FIELDS.filter(k => e[k] !== undefined).length;
    out._locked_fields = lockedCount;
    out._upgrade_url = UPGRADE_URL;
    return out;
  });

  const result = {
    meta: {
      ...meta,
      total_returned: filtered.length,
      tier: 'free',
      locked_fields_per_entity: PREMIUM_FIELDS.filter(k => (entities[0] || {})[k] !== undefined).length,
      upgrade_url: UPGRADE_URL,
      message: 'Free preview: 核心规格可见，深度数据（价格/兼容性/置信度/来源/合规/国产化率）需升级 Pro。使用 ?key=YOUR_API_KEY 或 Authorization: Bearer YOUR_API_KEY 获取完整数据。'
    },
    entities: filtered
  };

  return new Response(JSON.stringify(result, null, 2), {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-API-Tier': 'free',
      ...corsHeaders,
    }
  });
}

async function validateLicense(key, env) {
  try {
    const CREEM_API_KEY = env.CREEM_API_KEY;
    const resp = await fetch('https://api.creem.io/v1/licenses/validate', {
      method: 'POST',
      headers: {
        'X-API-KEY': CREEM_API_KEY,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ key })
    });
    const data = await resp.json();
    if (data.status === 'active' && PRO_PRODUCTS.includes(data.product_id)) {
      return true;
    }
    // Fallback: search endpoint
    const searchResp = await fetch('https://api.creem.io/v1/licenses/search', {
      method: 'POST',
      headers: {
        'X-API-KEY': CREEM_API_KEY,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ key })
    });
    if (searchResp.ok) {
      const searchData = await searchResp.json();
      if (searchData.items && searchData.items.length > 0) {
        const license = searchData.items[0];
        if (license.status === 'active' && PRO_PRODUCTS.includes(license.product_id)) {
          return true;
        }
      }
    }
    return false;
  } catch(e) {
    return false;
  }
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
