/**
 * 虎皮椒支付订单创建 API
 * POST /api/payment/create
 * Body: { plan: 'starter'|'pro'|'lifetime', api_key: 'gtk_xxx', email: 'xxx@xxx.com' }
 * 
 * 积分套餐（1积分 = 1次API调用，积分永久有效，无月费）：
 * - starter: ¥9 / 100积分
 * - pro: ¥29 / 500积分
 * - lifetime: ¥199 / 无限积分(999999)
 */

const PLANS = {
  starter: { price: 9, credits: 100, title: 'RoboParts Starter - 100积分' },
  pro: { price: 29, credits: 500, title: 'RoboParts Pro - 500积分' },
  lifetime: { price: 199, credits: 999999, title: 'RoboParts Lifetime - 无限积分' },
};

const API_GATEWAY = 'https://api.xunhupay.com/payment/do.html';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json',
};

/**
 * 测试订单隔离（与 creem.js / notify.js 保持同步）
 * E2E 自检、冒烟测试产生的订单不得污染真实转化指标。
 */
function isTestEmail(email) {
  const s = String(email || '').toLowerCase().trim();
  if (!s) return false;
  // 1) 自有域名下单一律视为内部测试（真实客户不会用平台自身域名邮箱付费）
  if (/@roboparts\.cc$/.test(s)) return true;
  // 2) 保留域名 / 一次性邮箱
  if (/@(example\.(com|org|net)|test\.|localhost|invalid|mailinator\.com)/.test(s)) return true;
  // 3) 本地部分含测试语义词，但排除 contest/latest/protest 等英文常见词误伤
  const local = s.split('@')[0];
  if (/(contest|latest|greatest|protest|attest|detest)/.test(local)) return false;
  return /(test|e2e|smoke|probe|dummy|fake|verify|demo)/.test(local);
}

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    let body;
    try {
      body = await request.json();
    } catch {
      return new Response(JSON.stringify({ error: 'Invalid or empty request body' }),
        { status: 400, headers: corsHeaders });
    }
    const { plan, api_key, email } = body;

    // Validate plan
    if (!plan || !PLANS[plan]) {
      return new Response(JSON.stringify({
        error: 'Invalid plan',
        available_plans: Object.keys(PLANS).map(k => ({ id: k, ...PLANS[k] })),
      }), { status: 400, headers: corsHeaders });
    }

    const planConfig = PLANS[plan];

    // Validate API key (optional for new users, but recommended for credit tracking)
    let userKey = api_key;
    if (!userKey && env.USER_CREDITS) {
      // Generate a new key for users without one
      userKey = 'gtk_' + Array.from(crypto.getRandomValues(new Uint8Array(24)))
        .map(b => b.toString(16).padStart(2, '0')).join('');
    }

    // Create order in KV for tracking
    const orderId = 'RP' + Date.now() + Math.floor(Math.random() * 10000);
    const isTest = isTestEmail(email);
    const orderData = {
      order_id: orderId,
      api_key: userKey,
      email: email || 'unknown',
      plan: plan,
      credits: planConfig.credits,
      price: planConfig.price,
      status: 'pending',
      is_test: isTest,
      created: new Date().toISOString(),
    };

    if (env.USER_CREDITS) {
      await env.USER_CREDITS.put((isTest ? 'testorder_' : 'order_') + orderId, JSON.stringify(orderData));
    }

    // Build 虎皮椒 request parameters
    const appid = env.XUNHU_APPID;
    const secret = env.XUNHU_SECRET;

    if (!appid || !secret) {
      return new Response(JSON.stringify({
        error: 'Payment gateway not configured',
        message: 'XUNHU_APPID or XUNHU_SECRET environment variables missing',
      }), { status: 500, headers: corsHeaders });
    }

    // Determine the base URL for callbacks (use custom domain or pages.dev)
    const requestUrl = new URL(request.url);
    const baseUrl = requestUrl.hostname === 'localhost'
      ? 'https://robotparts-924.pages.dev'
      : requestUrl.origin;

    const params = {
      version: '1.1',
      appid: appid,
      trade_order_id: orderId,
      total_fee: String(planConfig.price),
      title: planConfig.title,
      time: String(Math.floor(Date.now() / 1000)),
      notify_url: baseUrl + '/api/payment/notify',
      return_url: baseUrl + '/credits.html?status=success&order=' + orderId,
      callback_url: baseUrl + '/credits.html?status=cancel',
      plugins: 'roboparts',
      nonce_str: Math.random().toString(36).slice(2, 18),
      attach: JSON.stringify({ api_key: userKey, plan: plan, credits: planConfig.credits }),
    };

    // Generate signature: sort by ASCII, concatenate as key=value&key=value, append secret, MD5
    const hash = generateHash(params, secret);
    params.hash = hash;

    // Call 虎皮椒 API
    const formData = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      formData.append(key, value);
    }

    const xunhuResponse = await fetch(API_GATEWAY, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: formData.toString(),
    });

    const xunhuResult = await xunhuResponse.json();

    if (xunhuResult.errcode === 0 && xunhuResult.url) {
      // Success: return payment URL for mobile redirect
      return new Response(JSON.stringify({
        success: true,
        order_id: orderId,
        api_key: userKey,
        payment_url: xunhuResult.url,
        qrcode_url: xunhuResult.url_qrcode || null,
        price: planConfig.price,
        credits: planConfig.credits,
        plan: plan,
        message: 'Please complete payment. Credits will be added after successful payment.',
      }), { headers: corsHeaders });
    } else {
      // Payment gateway error
      return new Response(JSON.stringify({
        success: false,
        error: 'Payment gateway error',
        errcode: xunhuResult.errcode,
        errmsg: xunhuResult.errmsg,
        order_id: orderId,
      }), { status: 502, headers: corsHeaders });
    }

  } catch (e) {
    return new Response(JSON.stringify({
      error: 'Internal error',
    }), { status: 500, headers: corsHeaders });
  }
}

/**
 * 虎皮椒签名算法
 * 1. 参数按 ASCII 字典序排序
 * 2. 拼接成 key=value&key=value 格式（跳过空值和 hash）
 * 3. 末尾直接拼接 APPSECRET
 * 4. MD5 运算，32位小写
 */
function generateHash(params, secret) {
  const sortedKeys = Object.keys(params).filter(k => {
    return k !== 'hash' && params[k] !== null && params[k] !== '' && params[k] !== undefined;
  }).sort();

  const stringA = sortedKeys.map(k => k + '=' + params[k]).join('&');
  const stringSignTemp = stringA + secret;

  return md5(stringSignTemp);
}

/**
 * MD5 实现 (基于 blueimp-md5，经过测试验证正确)
 * https://github.com/blueimp/JavaScript-MD5
 */
function md5(str) {
  function safeAdd(x, y) {
    var lsw = (x & 0xffff) + (y & 0xffff);
    var msw = (x >> 16) + (y >> 16) + (lsw >> 16);
    return (msw << 16) | (lsw & 0xffff);
  }
  function bitRotateLeft(num, cnt) {
    return (num << cnt) | (num >>> (32 - cnt));
  }
  function md5cmn(q, a, b, x, s, t) {
    return safeAdd(bitRotateLeft(safeAdd(safeAdd(a, q), safeAdd(x, t)), s), b);
  }
  function md5ff(a, b, c, d, x, s, t) { return md5cmn((b & c) | (~b & d), a, b, x, s, t); }
  function md5gg(a, b, c, d, x, s, t) { return md5cmn((b & d) | (c & ~d), a, b, x, s, t); }
  function md5hh(a, b, c, d, x, s, t) { return md5cmn(b ^ c ^ d, a, b, x, s, t); }
  function md5ii(a, b, c, d, x, s, t) { return md5cmn(c ^ (b | ~d), a, b, x, s, t); }

  function binlMD5(x, len) {
    x[len >> 5] |= 0x80 << (len % 32);
    x[(((len + 64) >>> 9) << 4) + 14] = len;
    var a = 1732584193, b = -271733879, c = -1732584194, d = 271733878;
    for (var i = 0; i < x.length; i += 16) {
      var olda = a, oldb = b, oldc = c, oldd = d;
      a = md5ff(a, b, c, d, x[i], 7, -680876936);
      d = md5ff(d, a, b, c, x[i + 1], 12, -389564586);
      c = md5ff(c, d, a, b, x[i + 2], 17, 606105819);
      b = md5ff(b, c, d, a, x[i + 3], 22, -1044525330);
      a = md5ff(a, b, c, d, x[i + 4], 7, -176418897);
      d = md5ff(d, a, b, c, x[i + 5], 12, 1200080426);
      c = md5ff(c, d, a, b, x[i + 6], 17, -1473231341);
      b = md5ff(b, c, d, a, x[i + 7], 22, -45705983);
      a = md5ff(a, b, c, d, x[i + 8], 7, 1770035416);
      d = md5ff(d, a, b, c, x[i + 9], 12, -1958414417);
      c = md5ff(c, d, a, b, x[i + 10], 17, -42063);
      b = md5ff(b, c, d, a, x[i + 11], 22, -1990404162);
      a = md5ff(a, b, c, d, x[i + 12], 7, 1804603682);
      d = md5ff(d, a, b, c, x[i + 13], 12, -40341101);
      c = md5ff(c, d, a, b, x[i + 14], 17, -1502002290);
      b = md5ff(b, c, d, a, x[i + 15], 22, 1236535329);
      a = md5gg(a, b, c, d, x[i + 1], 5, -165796510);
      d = md5gg(d, a, b, c, x[i + 6], 9, -1069501632);
      c = md5gg(c, d, a, b, x[i + 11], 14, 643717713);
      b = md5gg(b, c, d, a, x[i], 20, -373897302);
      a = md5gg(a, b, c, d, x[i + 5], 5, -701558691);
      d = md5gg(d, a, b, c, x[i + 10], 9, 38016083);
      c = md5gg(c, d, a, b, x[i + 15], 14, -660478335);
      b = md5gg(b, c, d, a, x[i + 4], 20, -405537848);
      a = md5gg(a, b, c, d, x[i + 9], 5, 568446438);
      d = md5gg(d, a, b, c, x[i + 14], 9, -1019803690);
      c = md5gg(c, d, a, b, x[i + 3], 14, -187363961);
      b = md5gg(b, c, d, a, x[i + 8], 20, 1163531501);
      a = md5gg(a, b, c, d, x[i + 13], 5, -1444681467);
      d = md5gg(d, a, b, c, x[i + 2], 9, -51403784);
      c = md5gg(c, d, a, b, x[i + 7], 14, 1735328473);
      b = md5gg(b, c, d, a, x[i + 12], 20, -1926607734);
      a = md5hh(a, b, c, d, x[i + 5], 4, -378558);
      d = md5hh(d, a, b, c, x[i + 8], 11, -2022574463);
      c = md5hh(c, d, a, b, x[i + 11], 16, 1839030562);
      b = md5hh(b, c, d, a, x[i + 14], 23, -35309556);
      a = md5hh(a, b, c, d, x[i + 1], 4, -1530992060);
      d = md5hh(d, a, b, c, x[i + 4], 11, 1272893353);
      c = md5hh(c, d, a, b, x[i + 7], 16, -155497632);
      b = md5hh(b, c, d, a, x[i + 10], 23, -1094730640);
      a = md5hh(a, b, c, d, x[i + 13], 4, 681279174);
      d = md5hh(d, a, b, c, x[i], 11, -358537222);
      c = md5hh(c, d, a, b, x[i + 3], 16, -722521979);
      b = md5hh(b, c, d, a, x[i + 6], 23, 76029189);
      a = md5hh(a, b, c, d, x[i + 9], 4, -640364487);
      d = md5hh(d, a, b, c, x[i + 12], 11, -421815835);
      c = md5hh(c, d, a, b, x[i + 15], 16, 530742520);
      b = md5hh(b, c, d, a, x[i + 2], 23, -995338651);
      a = md5ii(a, b, c, d, x[i], 6, -198630844);
      d = md5ii(d, a, b, c, x[i + 7], 10, 1126891415);
      c = md5ii(c, d, a, b, x[i + 14], 15, -1416354905);
      b = md5ii(b, c, d, a, x[i + 5], 21, -57434055);
      a = md5ii(a, b, c, d, x[i + 12], 6, 1700485571);
      d = md5ii(d, a, b, c, x[i + 3], 10, -1894986606);
      c = md5ii(c, d, a, b, x[i + 10], 15, -1051523);
      b = md5ii(b, c, d, a, x[i + 1], 21, -2054922799);
      a = md5ii(a, b, c, d, x[i + 8], 6, 1873313359);
      d = md5ii(d, a, b, c, x[i + 15], 10, -30611744);
      c = md5ii(c, d, a, b, x[i + 6], 15, -1560198380);
      b = md5ii(b, c, d, a, x[i + 13], 21, 1309151649);
      a = md5ii(a, b, c, d, x[i + 4], 6, -145523070);
      d = md5ii(d, a, b, c, x[i + 11], 10, -1120210379);
      c = md5ii(c, d, a, b, x[i + 2], 15, 718787259);
      b = md5ii(b, c, d, a, x[i + 9], 21, -343485551);
      a = safeAdd(a, olda);
      b = safeAdd(b, oldb);
      c = safeAdd(c, oldc);
      d = safeAdd(d, oldd);
    }
    return [a, b, c, d];
  }

  function binl2rstr(input) {
    var output = '';
    var length32 = input.length * 32;
    for (var i = 0; i < length32; i += 8) {
      output += String.fromCharCode((input[i >> 5] >>> (i % 32)) & 0xff);
    }
    return output;
  }

  function rstr2binl(input) {
    var output = [];
    output[(input.length >> 2) - 1] = undefined;
    for (var i = 0; i < output.length; i++) {
      output[i] = 0;
    }
    var length8 = input.length * 8;
    for (var i = 0; i < length8; i += 8) {
      output[i >> 5] |= (input.charCodeAt(i / 8) & 0xff) << (i % 32);
    }
    return output;
  }

  function rstr2hex(input) {
    var hexTab = '0123456789abcdef';
    var output = '';
    var x;
    for (var i = 0; i < input.length; i++) {
      x = input.charCodeAt(i);
      output += hexTab.charAt((x >>> 4) & 0x0f) + hexTab.charAt(x & 0x0f);
    }
    return output;
  }

  var utf8 = unescape(encodeURIComponent(str));
  return rstr2hex(binl2rstr(binlMD5(rstr2binl(utf8), utf8.length * 8)));
}
