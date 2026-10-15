/**
 * BOM 账户级持久化 API
 * GET  /api/bom/store?key=YOUR_API_KEY   — 获取 BOM
 * POST /api/bom/store?key=YOUR_API_KEY   — 保存 BOM
 *
 * 功能：
 * 1. 按 API Key 存储 BOM 到 KV
 * 2. 跨设备取回同一 BOM
 * 3. 支持多个 BOM 项目（按 bom_id 区分）
 *
 * 注意：需 API Key，不消耗积分（存储是免费功能）。
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

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const apiKey = url.searchParams.get('key');

  if (!apiKey) {
    return json({ error: 'missing_api_key', message: '需要提供 API Key' }, 400);
  }

  try {
    // 验证 API Key
    const keyData = await env.API_KEYS.get(apiKey);
    if (!keyData) {
      return json({ error: 'invalid_api_key', message: '无效的 API Key' }, 401);
    }

    // 获取用户所有 BOM
    const bomKey = `bom:${apiKey}`;
    const stored = await env.USER_CREDITS.get(bomKey);

    if (!stored) {
      return json({ boms: [], message: '暂无保存的 BOM' });
    }

    const boms = JSON.parse(stored);
    return json({ boms });

  } catch (error) {
    console.error('获取 BOM 失败:', error);
    return json({ error: 'failed_to_load', message: '获取 BOM 失败' }, 500);
  }
}

export async function onRequestPost(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const apiKey = url.searchParams.get('key');

  if (!apiKey) {
    return json({ error: 'missing_api_key', message: '需要提供 API Key' }, 400);
  }

  try {
    // 验证 API Key
    const keyData = await env.API_KEYS.get(apiKey);
    if (!keyData) {
      return json({ error: 'invalid_api_key', message: '无效的 API Key' }, 401);
    }

    // 解析请求体
    const body = await request.json();
    const { bom_id, name, items, notes } = body;

    if (!bom_id || !items) {
      return json({ error: 'invalid_request', message: '缺少必填字段：bom_id, items' }, 400);
    }

    // 获取现有 BOM 列表
    const bomKey = `bom:${apiKey}`;
    let boms = [];
    const stored = await env.USER_CREDITS.get(bomKey);
    if (stored) {
      boms = JSON.parse(stored);
    }

    // 更新或创建 BOM
    const bomData = {
      bom_id,
      name: name || '未命名 BOM',
      items,
      notes: notes || '',
      updated_at: new Date().toISOString(),
      item_count: items.length,
    };

    const existingIndex = boms.findIndex(b => b.bom_id === bom_id);
    if (existingIndex >= 0) {
      boms[existingIndex] = bomData;
    } else {
      boms.push(bomData);
    }

    // 限制每个用户的 BOM 数量
    if (boms.length > 50) {
      boms = boms.slice(-40); // 保留最近 40 个
    }

    // 保存到 KV
    await env.USER_CREDITS.put(bomKey, JSON.stringify(boms));

    return json({
      success: true,
      bom_id,
      item_count: items.length,
      total_boms: boms.length,
      message: 'BOM 已保存',
    });

  } catch (error) {
    console.error('保存 BOM 失败:', error);
    return json({ error: 'failed_to_save', message: '保存 BOM 失败' }, 500);
  }
}

// 删除单个 BOM
export async function onRequestDelete(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const apiKey = url.searchParams.get('key');
  const bomId = url.searchParams.get('bom_id');

  if (!apiKey || !bomId) {
    return json({ error: 'missing_params', message: '需要提供 API Key 和 bom_id' }, 400);
  }

  try {
    // 验证 API Key
    const keyData = await env.API_KEYS.get(apiKey);
    if (!keyData) {
      return json({ error: 'invalid_api_key', message: '无效的 API Key' }, 401);
    }

    // 获取现有 BOM 列表
    const bomKey = `bom:${apiKey}`;
    let boms = [];
    const stored = await env.USER_CREDITS.get(bomKey);
    if (stored) {
      boms = JSON.parse(stored);
    }

    // 删除指定 BOM
    const beforeCount = boms.length;
    boms = boms.filter(b => b.bom_id !== bomId);
    const deletedCount = beforeCount - boms.length;

    if (deletedCount === 0) {
      return json({ error: 'not_found', message: '未找到指定的 BOM' }, 404);
    }

    // 保存更新
    await env.USER_CREDITS.put(bomKey, JSON.stringify(boms));

    return json({
      success: true,
      bom_id: bomId,
      message: 'BOM 已删除',
    });

  } catch (error) {
    console.error('删除 BOM 失败:', error);
    return json({ error: 'failed_to_delete', message: '删除 BOM 失败' }, 500);
  }
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: corsHeaders,
  });
}