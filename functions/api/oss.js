/**
 * RoboParts 开源机器人兼容性数据层 API
 * GET /api/oss                      - 列表（支持 ?category / ?robot / ?q / ?limit）
 * GET /api/oss?stats=1              - 统计：来源机器人、各类别数量
 *
 * 数据来源：api/oss_components.json（由 scripts/ingest_oss.mjs 生成，CL1 数据飞轮）
 * 分级（对标 Octopart Data API）：免费层返回核心字段，Pro 层（gtk_ key 或 Creem license）
 *   返回完整规格（协议/接口/电压/兼容性/价格），用于构建者的深度选型。
 */

import {
  newFailureCollector, loadJsonAsset, upstreamUnavailableResponse,
  resolveAuthState, tierMessage, authHeaders,
} from '../_lib/upstream.js';

const PREMIUM_FIELDS = ['protocol', 'interface', 'voltage', 'ros_support', 'compatibility', 'price_range', 'standard', 'source_license', 'source_robot'];
const UPGRADE_URL = 'https://roboparts.cc/credits';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Content-Type': 'application/json; charset=utf-8',
};

// 数据源加载：**失败不再静默返回空集合**。
// 旧写法 catch → { data: [] } 会让 ?stats=1 返回 total:0、列表返回 total_matched:0（均 HTTP 200），
// 于是「我们没读到数据」被渲染成「开源组件库是空的 / 这个零件不存在」——A 类失败伪装成 B 类事实。
async function loadOss(env, request, failures) {
  return await loadJsonAsset(env, request, '/api/oss_components.json', failures);
}

function strip(e, tier) {
  if (tier === 'pro') return e;
  const out = {};
  for (const [k, v] of Object.entries(e)) {
    if (!PREMIUM_FIELDS.includes(k)) out[k] = v;
  }
  out._locked_fields = PREMIUM_FIELDS.filter(k => e[k] !== undefined).length;
  out._upgrade_url = UPGRADE_URL;
  return out;
}

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const failures = newFailureCollector();
  const loaded = await loadOss(env, request, failures);
  if (!loaded.ok) {
    return upstreamUnavailableResponse(failures, corsHeaders,
      '开源组件数据源未能读取；空结果与「不存在」不是同一件事，请勿据此判定组件缺失。');
  }
  const { meta, data } = loaded;

  if (url.searchParams.get('stats') === '1') {
    // `total` 是行数，本身不撒谎；会撒谎的是**只给行数**。
    // 本层的行按证据强度差着量级：有的是厂商声明的实测规格，有的只是从 URDF 里
    // 扒下来的一个刚体名（无协议/无接口/无电压/无兼容维度）。两者一旦并进同一个
    // total，这个数就只能回答「我们攒了多少行」，不能回答「有多少行能用来做兼容判断」——
    // 而后者才是调用方真正在问的。
    //
    // 这与本文件开头那条纪律同族：那条防「读不到数据」被渲染成「零件不存在」（A 类失败
    // 伪装成 B 类事实）；这条防「低证据行」被渲染成「已核实组件」（C 类线索伪装成 A 类数据）。
    //
    // 所以 total 保持原样（不改语义、不破坏既有调用方），但**强制**把成分摊开：
    // 今后任何低置信度批量摄取都会立刻在 by_confidence / by_source_tier 里显形，
    // 而不是悄悄把总数顶上去。decidable 直接回答"多少行真能参与兼容判断"。
    const byCat = {}, byRobot = {}, byConfidence = {}, byTier = {};
    let decidable = 0;
    for (const e of data) {
      byCat[e.category] = (byCat[e.category] || 0) + 1;
      const r = e.source_robot || 'unknown';
      byRobot[r] = (byRobot[r] || 0) + 1;
      // 未标注 confidence 的历史行记为 'unrated'，**不得**默认当成 high：
      // 「没评过级」和「评过级是高」是两件事，折叠掉就又回到了 truthy 折叠那个老毛病。
      const c = e.confidence || 'unrated';
      byConfidence[c] = (byConfidence[c] || 0) + 1;
      const t = e.source_tier || 'unrated';
      byTier[t] = (byTier[t] || 0) + 1;
      if (Array.isArray(e.compatibility) && e.compatibility.length > 0) decidable++;
    }
    return new Response(JSON.stringify({
      meta, total: data.length, by_category: byCat, by_robot: byRobot,
      by_confidence: byConfidence, by_source_tier: byTier,
      decidable_entities: decidable,
      decidable_note: 'decidable_entities = 带非空 compatibility 的行数，即真正能参与兼容判断的部分；'
        + 'total 仅为行数，两者的差额是「已收录但尚不能据以判断」的线索行，请勿混用。',
    }, null, 2), { status: 200, headers: { ...corsHeaders, 'Cache-Control': 'public, max-age=300' } });
  }

  const q = (url.searchParams.get('q') || '').toLowerCase();
  const cat = url.searchParams.get('category') || '';
  const robot = url.searchParams.get('robot') || '';
  let filtered = data.filter(e =>
    (!cat || e.category === cat) &&
    (!robot || (e.source_robot || '').includes(robot)) &&
    (!q || (e.name + ' ' + e.manufacturer + ' ' + (e.standard || '')).toLowerCase().includes(q))
  );

  const tierInfo = await resolveAuthState(request, env);
  const limit = Math.min(500, parseInt(url.searchParams.get('limit') || '50', 10));
  const items = filtered.slice(0, limit).map(e => strip(e, tierInfo.tier));

  // auth_state=unverified 时字段虽被剥离，但**不得**输出「需 Pro」话术：
  // 那是对用户付费状态的断言，而事实只是我们没验成密钥。
  return new Response(JSON.stringify({
    meta: { ...meta, tier: tierInfo.tier, auth_state: tierInfo.auth_state,
      auth_failure: tierInfo.auth_failure || undefined,
      total_matched: filtered.length, returned: items.length,
      upgrade_url: tierInfo.auth_state === 'unverified' ? undefined : UPGRADE_URL,
      message: tierMessage(tierInfo.auth_state,
        '免费预览：核心字段可见，完整规格（协议/接口/电压/兼容性/价格）需 Pro。使用 ?key=YOUR_API_KEY 或 Authorization: Bearer YOUR_API_KEY。',
        'Pro 层：完整规格已返回。') },
    data: items,
  }, null, 2), {
    status: 200,
    headers: {
      ...corsHeaders,
      'Cache-Control': tierInfo.auth_state === 'unverified' ? 'no-store' : 'public, max-age=300',
      'X-API-Tier': tierInfo.tier,
      ...authHeaders(tierInfo.auth_state, UPGRADE_URL),
    },
  });
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
