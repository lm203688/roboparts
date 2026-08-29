/**
 * 单实体详情端点 —— GET /api/entity/{id}
 *
 * 【20260808-11 同批补上的第二个 404】
 * 本轮排查 `/api/search` 时把 `llms.txt` / `README.md` 那份 API 清单**逐条回探**，
 * 发现 404 的不止一个：`GET /api/entity/{id}` 同样被公开列出、同样从未实现。
 * 若只修被点名的那一个，就是"修了报告里写着的那条，留下同一份清单里性质完全相同的另一条"。
 * 两条一起兑现。
 *
 * ── 付费边界 ──────────────────────────────────────────────────────────────
 * 本端点**只返回免费层字段**，付费字段一律不返回，但会把"这一条上到底锁了哪几个字段"
 * 明确列出来。理由：
 *   - 不在这里复制 `[[path]].js` 那套 license/积分校验（近 200 行）。
 *     复制鉴权逻辑是比复制字段清单更危险的重复 —— 两份鉴权分叉意味着一处是安全漏洞。
 *   - 只给"锁了 N 个字段"这种计数等于让调用方猜，故给出具体字段名。
 *   - 字段不存在于该实体时不计入 locked：不把"我们本来就没采到这个数据"
 *     包装成"你没付费所以看不到"。
 * 需要完整字段的调用方走 `/api/entities.json` 并带 API Key。
 */

import { loadEntityMap } from '../../_lib/compat_engine.js';
import { maskPremium } from '../../_lib/paywall.js';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Content-Type': 'application/json; charset=utf-8',
  'Cache-Control': 'public, max-age=300',
};

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj, null, 2), { status, headers: corsHeaders });

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

// Pages 不做 HEAD→GET 映射，缺这个导出就是 404（目录站探活会判本端点下线）
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}

export async function onRequestGet(context) {
  const { request, env, params } = context;
  const raw = Array.isArray(params.id) ? params.id.join('/') : (params.id || '');
  const id = decodeURIComponent(raw).trim();

  if (!id) {
    return json({
      error: 'missing_id',
      message: '用法：GET /api/entity/{id}，例如 /api/entity/ACT-001。'
             + '不知道 ID 时用 /api/search?q=keyword 先检索。',
    }, 400);
  }

  let map;
  try {
    map = await loadEntityMap(env, request);
  } catch (err) {
    return json({
      error: 'dataset_unavailable',
      message: '实体库暂时不可用，本次查询未执行。这是服务故障，不代表该实体不存在。',
      detail: String(err && err.message || err),
    }, 503);
  }

  // 大小写不敏感兜底：ID 形如 ACT-001，调用方小写传入不应算"不存在"
  let entity = map[id];
  if (!entity) {
    const lower = id.toLowerCase();
    const hit = Object.keys(map).find(k => k.toLowerCase() === lower);
    if (hit) entity = map[hit];
  }

  if (!entity) {
    // 给出同前缀的近邻，比单纯一句 not found 有用
    const prefix = id.split('-')[0].toUpperCase();
    const nearby = Object.keys(map)
      .filter(k => k.toUpperCase().startsWith(prefix))
      .sort().slice(0, 5);
    return json({
      error: 'entity_not_found',
      id,
      message: `实体 "${id}" 不在库中。`,
      did_you_mean: nearby,
      hint: '用 /api/search?q=keyword 按名称/厂商检索获取正确 ID。',
      total_entities: Object.keys(map).length,
    }, 404);
  }

  const { entity: free, locked } = maskPremium(entity);

  return json({
    entity: free,
    meta: {
      tier: 'free',
      locked_fields: locked,
      locked_note: locked.length
        ? '以上字段属付费层，本端点不返回。完整数据：GET /api/entities.json 并带 API Key '
          + '（Authorization: Bearer <key> 或 ?key=<key>），自助领取见 POST /api/register。'
        : '该实体上没有付费层字段被锁定。',
      quarantine: entity.quarantine === true,
      quarantine_note: entity.quarantine === true
        ? '该条目已标记 quarantine=true —— 存在已知疑点（占位 ID / 无法核实的厂商 / 重复 / '
          + '并非零件的行业词），不应作为选型或采购决策依据。'
        : null,
      caveat: '参数为厂商声明值或公开资料整理，未经我方实测；'
            + '兼容性判定请用 POST /api/compatibility，不要仅凭本页字段推断。',
    },
  });
}
