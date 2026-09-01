/**
 * 数字-物理反馈闭环（安装回填）
 * POST /api/adapter-feedback  —— 采集（落盘）
 * GET  /api/adapter-feedback  —— 回流（只读聚合为透明社区安装口碑，不参与校准）
 *
 * 用户下载 STL → 打印 → 安装后，回填「合适 / 不合适 / 需调整」。
 * 反馈数据**回流**为社区安装口碑（community_fit）：同法兰配对聚合、bad 占比 ≥ 0.3
 * 标 needs_review（供人工复核），样本不足标 insufficient_data。
 * 该信号与 api/entities.json 的权威兼容性声明**相互独立**，**不自动改写**兼容性
 * 或转接件参数（守假绿纪律：冷启动小样本下自动校准 = 自欺）。
 *
 * 存储：复用既有 KV 命名空间 SUPPLIER_INQUIRIES（MVP 阶段避免新开 KV；
 * 正式版应拆分为独立 ADAPTER_FEEDBACK 命名空间）。
 * 键：adapter_feedback:<uuid> 存明细；adapter_feedback:index 存 ID 列表。
 */

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json; charset=utf-8',
};

export async function onRequestOptions() {
  return new Response(null, { headers: corsHeaders });
}

export async function onRequestPost(context) {
  const { request, env } = context;
  let body;
  try {
    body = await request.json();
  } catch (e) {
    return new Response(JSON.stringify({ error: '请求体不是合法 JSON' }), { status: 400, headers: corsHeaders });
  }

  const flangeA = String(body.flangeA || '').slice(0, 80);
  const flangeB = String(body.flangeB || '').slice(0, 80);
  const fit = String(body.fit || '').toLowerCase();
  const note = String(body.note || '').slice(0, 500);
  if (!['ok', 'bad', 'adjust'].includes(fit)) {
    return new Response(JSON.stringify({ error: 'fit 必须是 ok / bad / adjust 之一' }), { status: 400, headers: corsHeaders });
  }

  const id = 'adapter_feedback:' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  const record = {
    id,
    flangeA,
    flangeB,
    fit,
    note,
    ts: new Date().toISOString(),
    ua: request.headers.get('user-agent') || '',
  };

  try {
    const kv = env.SUPPLIER_INQUIRIES;
    if (!kv) throw new Error('KV 未绑定（SUPPLIER_INQUIRIES）');
    await kv.put(id, JSON.stringify(record));
    // 维护索引（追加 ID，保留最近 200 条）
    let index = [];
    const raw = await kv.get('adapter_feedback:index');
    if (raw) { try { index = JSON.parse(raw); } catch { index = []; } }
    index.unshift(id);
    index = index.slice(0, 200);
    await kv.put('adapter_feedback:index', JSON.stringify(index));
    return new Response(JSON.stringify({ ok: true, id, msg: '已记录，感谢回填！数据将作为社区安装口碑回流，供人工复核适配，不自动改写兼容性。' }), { status: 200, headers: corsHeaders });
  } catch (e) {
    return new Response(JSON.stringify({ error: '存储失败: ' + e.message }), { status: 500, headers: corsHeaders });
  }
}

// 纯函数：把一批反馈记录按 (flangeA, flangeB) 无序对聚合为社区安装信号。
// 不写 KV、不依赖引擎，便于单测与复用。signal 三态明确区分「样本足」与「不足」，
// 杜绝冷启动小样本下把偶然 bad 渲染成「不兼容」（守假绿纪律）。
export function aggregateCommunityFit(records, minSamples = 3) {
  const pairs = new Map();
  for (const r of records) {
    if (!r || !r.flangeA || !r.flangeB) continue;
    const key = [r.flangeA, r.flangeB].sort().join('|');
    if (!pairs.has(key)) pairs.set(key, { flangeA: r.flangeA, flangeB: r.flangeB, ok: 0, bad: 0, adjust: 0, samples: 0 });
    const p = pairs.get(key);
    if (r.fit === 'ok' || r.fit === 'bad' || r.fit === 'adjust') p[r.fit] += 1;
    p.samples += 1;
  }
  const out = [];
  for (const p of pairs.values()) {
    const decided = p.ok + p.bad + p.adjust;
    let signal;
    if (p.samples < minSamples) signal = 'insufficient_data';
    else if (p.bad === 0) signal = 'fits_well';
    else if (p.bad / decided >= 0.3) signal = 'needs_review';
    else signal = 'mixed_ok';
    out.push({
      pair: `${p.flangeA}<->${p.flangeB}`, flangeA: p.flangeA, flangeB: p.flangeB,
      ok: p.ok, bad: p.bad, adjust: p.adjust, samples: p.samples, signal,
    });
  }
  out.sort((a, b) => b.samples - a.samples);
  return out;
}

// 供内部/运维查看最近反馈（只读）；并在社区信号足够时回流为「安装口碑」
export async function onRequestGet(context) {
  const { env, request } = context;
  try {
    const kv = env.SUPPLIER_INQUIRIES;
    if (!kv) return new Response(JSON.stringify({ error: 'KV 未绑定' }), { status: 500, headers: corsHeaders });
    const raw = await kv.get('adapter_feedback:index');
    const index = raw ? JSON.parse(raw) : [];
    const items = [];
    for (const key of index.slice(0, 200)) {       // 全量读取（索引上限 200）做配对聚合
      const r = await kv.get(key);
      if (r) { try { items.push(JSON.parse(r)); } catch { /* 坏行跳过 */ } }
    }
    const stats = items.reduce((a, x) => { a[x.fit] = (a[x.fit] || 0) + 1; return a; }, {});
    // 回流 #1：物理安装反馈 → 社区口碑信号（透明、样本门控、不污染权威引擎）
    const minSamples = parseInt(new URL(request.url).searchParams.get('minSamples') || '3', 10) || 3;
    const communityFit = aggregateCommunityFit(items, minSamples);
    return new Response(JSON.stringify({
      total: index.length, stats, recent: items.slice(0, 50),
      community_fit: communityFit,
      community_fit_note: 'community_fit 为社区实测安装口碑（物理反馈回填），与 api/entities.json 的权威兼容性声明相互独立；'
        + `样本 < ${minSamples} 标 insufficient_data，bad 占比 ≥ 0.3 标 needs_review（供人工复核，不自动改写兼容性）。`,
    }), { status: 200, headers: corsHeaders });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: corsHeaders });
  }
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
