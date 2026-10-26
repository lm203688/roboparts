/**
 * RoboParts 主链路漏斗查询 API
 * GET /api/analytics/funnel
 *
 * 功能：
 * 1. 读取当前漏斗数据（今日）
 * 2. 返回各步骤转化率与历史趋势
 * 3. 免鉴权、只读、零成本
 *
 * 数据源：KV 中的 funnel:current（由 events.js 的 updateFunnelData 写入）
 *
 * 隐私：无 PII，仅聚合计数。
 * 契约版本：X-Data-Version: 2026-10-26
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Content-Type': 'application/json',
  'Cache-Control': 'no-store, no-cache',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet(context) {
  const { env } = context;

  try {
    const today = new Date().toISOString().split('T')[0];

    // 读取当前漏斗
    let funnel = {
      date: today,
      visits: 0,
      signups: 0,
      trials_started: 0,
      trials_completed: 0,
      payments_started: 0,
      payments_success: 0,
      conversions: 0,
      feature_use: {},
      events: [],
    };

    try {
      const stored = await env.USER_CREDITS.get('funnel:current');
      if (stored) {
        const parsed = JSON.parse(stored);
        funnel = { ...funnel, ...parsed };
      }
    } catch (e) {
      console.error('读取漏斗数据失败:', e);
    }

    // 读取近 7 天历史（用于趋势）
    const history = [];
    for (let i = 1; i <= 7; i++) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];
      try {
        const stored = await env.USER_CREDITS.get(`funnel:history:${dateStr}`);
        if (stored) {
          const parsed = JSON.parse(stored);
          history.push({
            date: dateStr,
            visits: parsed.visits || 0,
            signups: parsed.signups || 0,
            conversions: parsed.conversions || 0,
          });
        }
      } catch (e) {
        // 跳过缺失日期
      }
    }

    // 计算转化率
    const rates = {
      signup_rate: funnel.visits > 0 ? funnel.signups / funnel.visits : 0,
      trial_start_rate: funnel.signups > 0 ? funnel.trials_started / funnel.signups : 0,
      trial_complete_rate: funnel.trials_started > 0 ? funnel.trials_completed / funnel.trials_started : 0,
      payment_start_rate: funnel.trials_completed > 0 ? funnel.payments_started / funnel.trials_completed : 0,
      payment_success_rate: funnel.payments_started > 0 ? funnel.payments_success / funnel.payments_started : 0,
      conversion_rate: funnel.visits > 0 ? funnel.conversions / funnel.visits : 0,
    };

    // 主链 5 步使用率（feature_use 事件）
    const pipelineSteps = ['selection', 'build_planner', 'designer', 'bom_checker', 'adapter_generator'];
    const pipelineUsage = {};
    if (funnel.feature_use) {
      for (const step of pipelineSteps) {
        pipelineUsage[step] = funnel.feature_use[step] || 0;
      }
    }

    const result = {
      date: funnel.date,
      counts: {
        visits: funnel.visits,
        signups: funnel.signups,
        trials_started: funnel.trials_started,
        trials_completed: funnel.trials_completed,
        payments_started: funnel.payments_started,
        payments_success: funnel.payments_success,
        conversions: funnel.conversions,
      },
      rates: rates,
      pipeline_usage: pipelineUsage,
      history_7d: history,
      meta: {
        endpoint: '/api/analytics/funnel',
        data_version: '2026-10-26',
        privacy: '聚合计数，无 PII；隐私策略见 /PRIVACY.md',
        note: 'P1-6 主链路埋点 2026-10-26 上线；数据从此刻起开始积累',
      },
    };

    return new Response(JSON.stringify(result), {
      status: 200,
      headers: {
        ...corsHeaders,
        'X-Data-Version': '2026-10-26',
      },
    });

  } catch (error) {
    console.error('漏斗查询失败:', error);
    return new Response(JSON.stringify({
      error: 'processing_failed',
      message: '漏斗查询失败',
    }), {
      status: 500,
      headers: corsHeaders,
    });
  }
}

// HEAD 探活
export async function onRequestHead() {
  return new Response(null, {
    status: 200,
    headers: corsHeaders,
  });
}
