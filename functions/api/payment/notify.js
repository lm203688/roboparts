/**
 * 虎皮椒支付回调通知 API
 * POST /api/payment/notify
 * 
 * 虎皮椒在用户支付成功后会向 notify_url 发送 POST 通知
 * 服务器需返回 "success" 表示已收到通知
 */

const CREDIT_MAP = {
  'starter': 100,
  'pro': 500,
  'lifetime': 999999,
};

/**
 * Hash email using SHA-256 for privacy-safe storage
 */
async function hashEmail(email) {
  if (!email) return null;
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

export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    // 虎皮椒回调是 form 表单类型
    const contentType = request.headers.get('content-type') || '';
    let params;

    if (contentType.includes('application/x-www-form-urlencoded')) {
      const formData = await request.formData();
      params = {};
      for (const [key, value] of formData.entries()) {
        params[key] = value;
      }
    } else if (contentType.includes('application/json')) {
      params = await request.json();
    } else {
      // 尝试解析为 form
      const text = await request.text();
      params = {};
      const searchParams = new URLSearchParams(text);
      for (const [key, value] of searchParams.entries()) {
        params[key] = value;
      }
    }

    const {
      trade_order_id,
      total_fee,
      transaction_id,
      open_order_id,
      order_title,
      status,
      plugins,
      attach,
      appid,
      time,
      nonce_str,
      hash,
    } = params;

    // 验证签名
    const secret = env.XUNHU_SECRET;
    if (!secret) {
      // 生产环境必须有密钥——否则无法验证签名
      console.error('[PAYMENT] XUNHU_SECRET not configured, rejecting callback');
      return new Response(JSON.stringify({
        error: 'Payment verification disabled',
        error_kind: 'no_secret_configured',
        message: 'Server configuration error: payment secret not set'
      }), { status: 503, headers: corsHeaders });
      console.error('XUNHU_SECRET not configured');
      return new Response('fail', { status: 500 });
    }

    // 生成签名验证
    const expectedHash = generateHash(params, secret);
    if (hash !== expectedHash) {
      console.error('Signature mismatch', { expected: expectedHash, actual: hash });
      return new Response('fail', { status: 401 });
    }

    // 验证支付状态
    if (status !== 'OD') {
      console.log('Order not paid', { order_id: trade_order_id, status });
      return new Response('success', { status: 200 });
    }

    // 从 attach 中提取用户信息
    let userInfo = {};
    if (attach) {
      try {
        userInfo = JSON.parse(attach);
      } catch (e) {
        // attach 不是 JSON，尝试从 KV 中查找订单
      }
    }

    // 从 KV 中查找订单记录
    // 测试订单隔离（与 create.js / creem.js 同步）：真实订单走 order_，
    // E2E/冒烟订单走 testorder_。此处先查真实前缀，未命中再回落测试前缀，
    // 保证测试链路仍可端到端验证，同时统计侧只扫 order_ 即为干净数据。
    if (env.USER_CREDITS && trade_order_id) {
      let orderKey = 'order_' + trade_order_id;
      let orderDataStr = await env.USER_CREDITS.get(orderKey);
      if (!orderDataStr) {
        const testKey = 'testorder_' + trade_order_id;
        const testStr = await env.USER_CREDITS.get(testKey);
        if (testStr) {
          orderKey = testKey;
          orderDataStr = testStr;
        }
      }

      if (orderDataStr) {
        const orderData = JSON.parse(orderDataStr);

        // 防止重复充值
        if (orderData.status === 'completed') {
          console.log('Order already completed', trade_order_id);
          return new Response('success', { status: 200 });
        }

        const userKey = userInfo.api_key || orderData.api_key;
        const creditsToAdd = userInfo.credits || orderData.credits || CREDIT_MAP[orderData.plan] || 0;

        if (creditsToAdd > 0 && userKey) {
          // 获取用户当前积分
          const userStr = await env.USER_CREDITS.get(userKey);
          let user;
          if (userStr) {
            user = JSON.parse(userStr);
          } else {
            // 新用户
            const emailHash = await hashEmail(userInfo.email || orderData.email);
            user = {
              email_hash: emailHash,
              credits: 0,
              plan: 'free',
              api_calls: 0,
              created: new Date().toISOString(),
            };
          }

          // 增加积分
          user.credits = (user.credits || 0) + creditsToAdd;
          user.plan = 'pro';
          user.last_recharge = new Date().toISOString();
          user.last_recharge_amount = total_fee;
          user.last_recharge_order = trade_order_id;

          // 如果用户之前有低积分预警，充值后重置
          if (user.credits > 20 && user.low_alert_sent) {
            user.low_alert_sent = false;
            delete user.low_alert_at;
          }

          await env.USER_CREDITS.put(userKey, JSON.stringify(user));

          // 更新订单状态
          orderData.status = 'completed';
          orderData.transaction_id = transaction_id;
          orderData.open_order_id = open_order_id;
          orderData.completed_at = new Date().toISOString();
          await env.USER_CREDITS.put(orderKey, JSON.stringify(orderData));

          // 同步更新 API_KEYS 记录
          if (env.API_KEYS) {
            const apiStr = await env.API_KEYS.get(userKey);
            if (apiStr) {
              const apiData = JSON.parse(apiStr);
              apiData.plan = 'pro';
              apiData.last_recharge = new Date().toISOString();
              await env.API_KEYS.put(userKey, JSON.stringify(apiData));
            }
          }

          console.log('Recharge success', {
            user: userKey,
            credits_added: creditsToAdd,
            total_credits: user.credits,
            order: trade_order_id,
          });
        }
      } else {
        console.error('Order not found', trade_order_id);
      }
    }

    // 返回 success 告诉虎皮椒已收到通知
    return new Response('success', {
      status: 200,
      headers: { 'Content-Type': 'text/plain' },
    });

  } catch (e) {
    console.error('Payment notify error', e);
    return new Response('fail', { status: 500 });
  }
}

/**
 * 虎皮椒签名验证算法
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
