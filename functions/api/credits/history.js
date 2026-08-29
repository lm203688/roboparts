/**
 * 积分使用历史 API
 * GET  /api/credits/history?key=gtk_xxx
 * POST /api/credits/history  { "api_key": "gtk_xxx" }
 *
 * 功能：
 * - CORS 支持
 * - 验证 api_key
 * - 通过 _lib/ledger.js 读取该用户的积分账本（唯一入口）
 * - 返回历史记录列表 + ledger_status
 *
 * 【口径】账本读不出来 ≠ 你没有交易。
 * 只有 ledger_status='empty'（后端可用且确认无记录）才允许对外说"暂无记录"；
 * unavailable / corrupt 一律走非 2xx + error_kind，绝不返回 success:true + 空数组。
 * 汇总数在不可读时为 null，不是 0——0 会被页面原样渲染成"消费 0 / 充值 0"。
 */

import { readLedger, summarizeLedger, ledgerHttp } from '../../_lib/ledger.js';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Content-Type': 'application/json',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const apiKey = url.searchParams.get('key') || url.searchParams.get('api_key');
  return await handleHistory(apiKey, env);
}

export async function onRequestPost(context) {
  const { request, env } = context;
  try {
    const body = await request.json();
    const { api_key } = body;
    return await handleHistory(api_key, env);
  } catch (e) {
    return new Response(JSON.stringify({
      success: false,
      error: '请求格式错误: ' + e.message,
    }), { status: 400, headers: corsHeaders });
  }
}

async function handleHistory(apiKey, env) {
  try {
    // ========== 1. 参数校验 ==========
    if (!apiKey || typeof apiKey !== 'string' || !apiKey.startsWith('gtk_')) {
      return new Response(JSON.stringify({
        success: false,
        error: 'API Key (api_key) 为必填项，且需以 gtk_ 开头',
      }), { status: 400, headers: corsHeaders });
    }

    // ========== 2. 验证 API Key ==========
    if (!env.USER_CREDITS) {
      return new Response(JSON.stringify({
        success: false,
        error: '积分系统未配置',
      }), { status: 500, headers: corsHeaders });
    }

    const userRecord = await env.USER_CREDITS.get(apiKey);
    if (!userRecord) {
      return new Response(JSON.stringify({
        success: false,
        error: 'API Key 无效或不存在',
      }), { status: 401, headers: corsHeaders });
    }

    // ========== 3. 读取账本（四态：ok / empty / unavailable / corrupt）==========
    const read = await readLedger(env, apiKey);

    // 不可读必须让调用方知道，不能降级成"空账本 + success:true"
    const httpErr = ledgerHttp(read);
    if (httpErr) {
      return new Response(JSON.stringify({
        success: false,
        error_kind: httpErr.error_kind,
        error: httpErr.error,
        ledger_status: read.status,
        ledger_backend: read.backend,
        detail: read.reason,
      }), { status: httpErr.status, headers: corsHeaders });
    }

    // ========== 4. 统计汇总（仅在 ok/empty 下才是数字）==========
    const sum = summarizeLedger(read);

    // ========== 5. 返回结果 ==========
    return new Response(JSON.stringify({
      success: true,
      ledger_status: read.status,          // 'ok' | 'empty'
      ledger_backend: read.backend,
      history: read.records,
      total: sum.total,
      total_consumed: sum.total_consumed,
      total_recharged: sum.total_recharged,
    }), { headers: corsHeaders });

  } catch (e) {
    return new Response(JSON.stringify({
      success: false,
      error: '服务器内部错误: ' + e.message,
    }), { status: 500, headers: corsHeaders });
  }
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
