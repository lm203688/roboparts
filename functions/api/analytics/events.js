/**
 * RoboParts 事件追踪 API
 * POST /api/analytics/events
 *
 * 功能：
 * 1. 接收前端事件（访问、试用、付费等）
 * 2. 实时写入 KV 存储
 * 3. 返回事件确认
 *
 * 事件类型：
 * - page_view: 页面访问
 * - feature_use: 功能使用（BOM检查、选型等）
 * - signup: 注册
 * - trial_start: 首次试用
 * - trial_complete: 完成试用
 * - payment_start: 开始支付
 * - payment_success: 支付成功
 * - payment_failed: 支付失败
 *
 * 注意：无需 API Key，不消耗积分。
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS, POST',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Content-Type': 'application/json',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestPost(context) {
  const { request, env } = context;

  try {
    // 解析请求体
    const body = await request.json();
    const { event_type, event_data, user_id, session_id, timestamp } = body;

    // 验证必填字段
    if (!event_type || !event_data) {
      return json({
        error: 'invalid_request',
        message: '缺少必填字段：event_type, event_data',
      }, 400);
    }

    // 验证事件类型
    const validEvents = [
      'page_view', 'feature_use', 'signup', 'trial_start', 'trial_complete',
      'payment_start', 'payment_success', 'payment_failed', 'conversion'
    ];
    if (!validEvents.includes(event_type)) {
      return json({
        error: 'invalid_event_type',
        message: `无效事件类型。支持：${validEvents.join(', ')}`,
      }, 400);
    }

    // 生成事件 ID 和默认时间戳
    const eventId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const eventTimestamp = timestamp || new Date().toISOString();
    
    // 构造事件对象
    const event = {
      id: eventId,
      event_type,
      event_data,
      user_id: user_id || null,
      session_id: session_id || null,
      timestamp: eventTimestamp,
      user_agent: request.headers.get('User-Agent'),
      referer: request.headers.get('Referer'),
    };

    // 写入 KV 存储（按日期分组）
    const dateKey = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
    const eventsKey = `events:${dateKey}`;
    
    // 获取当日现有事件
    let existingEvents = [];
    try {
      const stored = await env.USER_CREDITS.get(eventsKey);
      if (stored) {
        existingEvents = JSON.parse(stored);
      }
    } catch (e) {
      console.error('读取现有事件失败:', e);
    }

    // 添加新事件
    existingEvents.push(event);
    
    // 限制单日事件数量（防止恶意刷量）
    if (existingEvents.length > 10000) {
      existingEvents = existingEvents.slice(-9000); // 保留最近 9000 条
    }

    // 写回 KV
    await env.USER_CREDITS.put(eventsKey, JSON.stringify(existingEvents));

    // 实时计算激活漏斗数据
    await updateFunnelData(env, event);

    return json({
      success: true,
      event_id: eventId,
      message: '事件已记录',
    });

  } catch (error) {
    console.error('事件处理失败:', error);
    return json({
      error: 'processing_failed',
      message: '事件处理失败',
      detail: error.message,
    }, 500);
  }
}

// 更新激活漏斗数据
async function updateFunnelData(env, event) {
  const funnelKey = 'funnel:current';
  const today = new Date().toISOString().split('T')[0];
  
  // 获取现有漏斗数据
  let funnelData = {
    date: today,
    visits: 0,
    signups: 0,
    trials_started: 0,
    trials_completed: 0,
    payments_started: 0,
    payments_success: 0,
    conversions: 0,
    events: []
  };

  try {
    const stored = await env.USER_CREDITS.get(funnelKey);
    if (stored) {
      const storedData = JSON.parse(stored);
      // 如果是新的日期，重置数据
      if (storedData.date !== today) {
        // 保留历史数据
        const historyKey = `funnel:history:${today}`;
        await env.USER_CREDITS.put(historyKey, JSON.stringify(storedData));
      } else {
        funnelData = storedData;
      }
    }
  } catch (e) {
    console.error('读取漏斗数据失败:', e);
  }

  // 更新计数器
  switch (event.event_type) {
    case 'page_view':
      funnelData.visits++;
      break;
    case 'signup':
      funnelData.signups++;
      break;
    case 'trial_start':
      funnelData.trials_started++;
      break;
    case 'trial_complete':
      funnelData.trials_completed++;
      break;
    case 'payment_start':
      funnelData.payments_started++;
      break;
    case 'payment_success':
      funnelData.payments_success++;
      break;
    case 'conversion':
      funnelData.conversions++;
      break;
  }

  // 添加事件详情
  funnelData.events.push({
    timestamp: event.timestamp,
    type: event.event_type,
    user_id: event.user_id,
    session_id: event.session_id,
  });

  // 保存更新后的漏斗数据
  await env.USER_CREDITS.put(funnelKey, JSON.stringify(funnelData));
}

// 辅助函数：返回 JSON 响应
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: corsHeaders,
  });
}