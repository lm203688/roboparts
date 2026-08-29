/**
 * Points API - User points system
 * GET /api/points - Get user points
 * HEAD /api/points - Health check
 * POST /api/points/earn - Earn points
 * POST /api/points/redeem - Redeem points
 */
export async function onRequestHead(context) {
  return new Response(null, {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    }
  });
}

export async function onRequestGet(context) {
  const { env, request } = context;
  const url = new URL(request.url);
  const userId = url.searchParams.get('user_id') || 'default';
  
  try {
    let points = { balance: 0, history: [] };
    
    if (env.MARKETPLACE_KV) {
      const data = await env.MARKETPLACE_KV.get(`points:${userId}`, 'json');
      points = data || points;
    } else {
      points = getDemoPoints(userId);
    }
    
    return new Response(JSON.stringify({
      success: true,
      data: points
    }), {
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

export async function onRequestPost(context) {
  const { env, request } = context;
  const url = new URL(request.url);
  const action = url.pathname.split('/').pop();
  
  try {
    const body = await request.json();
    const { user_id, points, reason } = body;
    
    if (!user_id || !points) {
      return new Response(JSON.stringify({
        success: false,
        error: 'user_id and points are required'
      }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    let currentPoints = { balance: 0, history: [] };
    
    if (env.MARKETPLACE_KV) {
      const data = await env.MARKETPLACE_KV.get(`points:${user_id}`, 'json');
      currentPoints = data || currentPoints;
    }
    
    if (action === 'earn') {
      currentPoints.balance += points;
      currentPoints.history.push({
        type: 'earn',
        points,
        reason,
        date: new Date().toISOString()
      });
    } else if (action === 'redeem') {
      if (currentPoints.balance < points) {
        return new Response(JSON.stringify({
          success: false,
          error: 'Insufficient points'
        }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' }
        });
      }
      currentPoints.balance -= points;
      currentPoints.history.push({
        type: 'redeem',
        points: -points,
        reason,
        date: new Date().toISOString()
      });
    }
    
    if (env.MARKETPLACE_KV) {
      await env.MARKETPLACE_KV.put(`points:${user_id}`, JSON.stringify(currentPoints));
    }
    
    return new Response(JSON.stringify({
      success: true,
      data: currentPoints
    }), {
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ success: false, error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    }
  });
}

function getDemoPoints(userId) {
  const demoData = {
    'user-123': {
      balance: 2340,
      history: [
        { type: 'earn', points: 10, reason: '上传数据', date: '2026-08-20' },
        { type: 'earn', points: 5, reason: '被下载', date: '2026-08-19' },
        { type: 'earn', points: 1, reason: '被点赞', date: '2026-08-18' },
        { type: 'earn', points: 50, reason: '优质认证', date: '2026-08-15' },
        { type: 'redeem', points: -100, reason: '兑换折扣券', date: '2026-08-10' },
      ]
    }
  };
  
  return demoData[userId] || { balance: 0, history: [] };
}
