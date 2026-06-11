// ==========================================
// Vercel Serverless: 创建虎皮椒支付订单
// POST /api/create-order
// ==========================================

const crypto = require('crypto');

// 虎皮椒签名算法
function generateHash(params, secret) {
  const sortedKeys = Object.keys(params)
    .filter(k => k !== 'hash' && params[k] !== '' && params[k] != null)
    .sort();
  const str = sortedKeys.map(k => `${k}=${params[k]}`).join('&');
  return crypto.createHash('md5').update(str + secret).digest('hex');
}

module.exports = async (req, res) => {
  // CORS preflight
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { stl_id, stl_name, amount, payment_type, material, shipping } = req.body;

    if (!stl_id || !amount || amount <= 0) {
      return res.status(400).json({ error: '缺少必要参数' });
    }

    const appId = process.env.XUNHU_APP_ID;
    const appSecret = process.env.XUNHU_APP_SECRET;

    if (!appId || !appSecret) {
      console.error('XUNHU_APP_ID or XUNHU_APP_SECRET not configured');
      return res.status(500).json({ error: '支付服务未配置，请联系管理员' });
    }

    // 生成唯一订单号（<=32字符，只能包含字母数字_-*）
    const ts = Date.now().toString(36).toUpperCase();
    const rand = crypto.randomBytes(4).toString('hex').toUpperCase();
    const tradeOrderId = `RL${ts}${rand}`;

    const nonceStr = crypto.randomBytes(16).toString('hex');
    const time = Math.floor(Date.now() / 1000);

    // 虎皮椒API参数
    const params = {
      version: '1.1',
      appid: appId,
      trade_order_id: tradeOrderId,
      total_fee: parseFloat(amount).toFixed(2),
      title: `3D打印:${(stl_name || '').substring(0, 28)}`,
      time,
      notify_url: 'https://roboparts.cc/api/payment-callback',
      return_url: `https://roboparts.cc/?order=${tradeOrderId}`,
      callback_url: 'https://roboparts.cc/#stl',
      nonce_str: nonceStr,
      plugins: 'robolink-v1',
      attach: JSON.stringify({ sid: stl_id, mat: material || 'PLA' }),
    };

    // 签名
    params.hash = generateHash(params, appSecret);

    // 调用虎皮椒
    const xunhuRes = await fetch('https://api.xunhupay.com/payment/do.html', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });

    const xunhuData = await xunhuRes.json();

    if (xunhuData.errcode !== 0) {
      console.error('Xunhupay error:', xunhuData);
      return res.status(400).json({ error: xunhuData.errmsg || '创建支付失败' });
    }

    // 存入Supabase
    try {
      const sbUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://pendpzoycfngylrrbwon.supabase.co';
      const sbKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

      await fetch(`${sbUrl}/rest/v1/payment_orders`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'apikey': sbKey,
          'Prefer': 'return=minimal',
        },
        body: JSON.stringify({
          trade_order_id: tradeOrderId,
          stl_id,
          stl_name: (stl_name || '').substring(0, 100),
          amount: parseFloat(amount),
          payment_type: payment_type || 'wechat',
          material: material || 'PLA',
          shipping: shipping || 'standard',
          status: 'pending',
          nonce_str: nonceStr,
        }),
      });
    } catch (dbErr) {
      console.warn('Supabase save failed (non-critical):', dbErr);
    }

    return res.status(200).json({
      order_id: tradeOrderId,
      url: xunhuData.url || null,
      url_qrcode: xunhuData.url_qrcode || null,
      errcode: 0,
    });

  } catch (err) {
    console.error('Create order error:', err);
    return res.status(500).json({ error: err.message });
  }
};
