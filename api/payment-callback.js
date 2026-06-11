// ==========================================
// Vercel Serverless: 虎皮椒支付回调
// POST /api/payment-callback
// 虎皮椒支付成功后自动POST到此端点
// ==========================================

const crypto = require('crypto');

function generateHash(params, secret) {
  const sortedKeys = Object.keys(params)
    .filter(k => k !== 'hash' && params[k] !== '' && params[k] != null)
    .sort();
  const str = sortedKeys.map(k => `${k}=${params[k]}`).join('&');
  return crypto.createHash('md5').update(str + secret).digest('hex');
}

module.exports = async (req, res) => {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).send('Method not allowed');
  }

  try {
    const appSecret = process.env.XUNHU_APP_SECRET;

    if (!appSecret) {
      console.error('XUNHU_APP_SECRET not configured');
      return res.status(500).send('config error');
    }

    // 虎皮椒回调为 form 表单格式
    let params;
    const contentType = req.headers['content-type'] || '';

    if (contentType.includes('application/x-www-form-urlencoded')) {
      if (typeof req.body === 'string') {
        params = Object.fromEntries(new URLSearchParams(req.body));
      } else if (typeof req.body === 'object') {
        params = { ...req.body };
      }
    } else if (contentType.includes('application/json')) {
      params = req.body;
    } else {
      // 兜底：尝试解析
      if (typeof req.body === 'string') {
        try {
          params = Object.fromEntries(new URLSearchParams(req.body));
        } catch {
          params = req.body;
        }
      } else {
        params = req.body;
      }
    }

    console.log('Payment callback received:', {
      order: params.trade_order_id,
      status: params.status,
      amount: params.total_fee,
    });

    // 验签
    const expectedHash = generateHash(params, appSecret);
    if (expectedHash !== params.hash) {
      console.error('Hash verification FAILED', {
        expected: expectedHash,
        received: params.hash,
      });
      return res.status(400).send('invalid hash');
    }

    const { trade_order_id, status, transaction_id, total_fee } = params;

    if (!trade_order_id || !status) {
      console.error('Missing required params');
      return res.status(400).send('missing params');
    }

    // 状态映射
    const statusMap = {
      'OD': 'paid',
      'CD': 'refunded',
      'RD': 'refunding',
      'UD': 'refund_failed',
    };
    const newStatus = statusMap[status] || status;

    // 更新Supabase
    const sbUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://pendpzoycfngylrrbwon.supabase.co';
    const sbKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    const updateData = {
      status: newStatus,
      transaction_id: transaction_id || null,
      paid_amount: total_fee ? parseFloat(total_fee) : null,
      paid_at: new Date().toISOString(),
    };

    const updateRes = await fetch(
      `${sbUrl}/rest/v1/payment_orders?trade_order_id=eq.${encodeURIComponent(trade_order_id)}`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'apikey': sbKey,
          'Prefer': 'return=minimal',
        },
        body: JSON.stringify(updateData),
      }
    );

    if (updateRes.ok) {
      console.log(`Order ${trade_order_id} -> ${newStatus}`);
    } else {
      console.error('Supabase update failed:', await updateRes.text());
    }

    // 虎皮椒要求返回纯文本 "success"
    return res.status(200).send('success');

  } catch (err) {
    console.error('Callback error:', err);
    return res.status(500).send('error');
  }
};
