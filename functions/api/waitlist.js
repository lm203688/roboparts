/**
 * Waitlist capture — CF Pages Function (RoboParts)
 *
 * 复用现有 USER_CREDITS KV（前缀 waitlist:），无需新增绑定，部署不依赖用户。
 * 同时给 builder / investor / supplier 分桶计数，作为"需求试水仪表盘"。
 *
 * 设计纪律（对齐 register.js）：
 *  - 邮箱以 SHA-256 哈希去重（防重复计数），同时落明文以便回访培育；
 *  - 明文邮箱仅在用户主动提交 waitlist 时采集（opt-in），用于后续触达，
 *    非第三方抓取；这是 waitlist 闭环可培育意向的必要条件；
 *  - 自检请求（x-roboparts-selftest=1）写隔离命名空间，不计入真实统计；
 *  - 计数用 KV 读-改-写，前缀 stat: 避免与 gtk_ 用户键冲突。
 */

async function hashEmail(email) {
  const encoder = new TextEncoder();
  const data = encoder.encode(email.toLowerCase().trim());
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

function cors() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
  };
}

// 零件类目白名单（与 demand-signal category_counts 对齐），防止 KV 被任意键污染
const NEED_CATEGORIES = [
  'actuators', 'sensors', 'connectors', 'controllers', 'chips', 'platforms',
  'interfaces', 'llms', 'protocols', 'flexible_actuators', 'data_acquisition', 'robot_ai_models',
];

export async function onRequestOptions() {
  return new Response(null, { headers: cors() });
}

/** HEAD：仅存活应答（目录站/可用性监控探活用，不处理业务体） */
export async function onRequestHead() {
  return new Response(null, { status: 200, headers: cors() });
}

/** GET：返回实时计数（仪表盘用，公开可读） */
export async function onRequestGet(context) {
  const { env } = context;
  const roles = ['builders', 'investors', 'suppliers'];
  const out = { total: 0, needs: {} };
  try {
    for (const r of roles) {
      const v = await env.USER_CREDITS.get('stat:waitlist:' + r);
      out[r] = parseInt(v || '0', 10) || 0;
      out.total += out[r];
    }
    // 零件级需求热度（waitlist 反喂，H6/L6 闭环）
    for (const c of NEED_CATEGORIES) {
      const v = await env.USER_CREDITS.get('stat:waitlist:need:' + c);
      const n = parseInt(v || '0', 10) || 0;
      if (n > 0) out.needs[c] = n;
    }
  } catch (e) { /* 读计数失败不影响主流程 */ }
  return new Response(JSON.stringify(out), { headers: cors() });
}

export async function onRequestPost(context) {
  const { request, env } = context;
  const h = cors();
  try {
    const body = await request.json();
    const email = (body.email || '').trim();
    const role = ['builder', 'investor', 'supplier'].includes(body.role) ? body.role : 'builder';
    const note = (body.note || '').toString().slice(0, 280);

    // 零件级需求（可多选，白名单校验，H6/L6 闭环信号）
    let needCategories = Array.isArray(body.need_categories) ? body.need_categories : [];
    needCategories = needCategories.filter((c) => NEED_CATEGORIES.includes(c)).slice(0, NEED_CATEGORIES.length);

    if (!email || !email.includes('@')) {
      return new Response(JSON.stringify({ error: 'Valid email required' }), { status: 400, headers: h });
    }

    const emailHash = await hashEmail(email);
    const isSelftest = request.headers.get('x-roboparts-selftest') === '1';
    const src = (request.headers.get('referer') || '').includes('roboparts.cc') ? 'web' : 'direct';

    // 去重：同一邮箱只计一次真实签名
    const key = 'waitlist:' + emailHash;
    const existing = await env.USER_CREDITS.get(key);
    let already = false;
    if (existing) {
      try { already = !JSON.parse(existing).selftest; } catch { already = false; }
    }

    const record = {
      email_hash: emailHash, email, role, note, need_categories: needCategories,
      source: src, created: new Date().toISOString(), selftest: isSelftest,
    };
    await env.USER_CREDITS.put(key, JSON.stringify(record));

    // 计数（仅真实且首次签名才 +1）
    if (!isSelftest && !already) {
      const roleKey = 'stat:waitlist:' + (role === 'builder' ? 'builders' : role === 'investor' ? 'investors' : 'suppliers');
      for (const k of ['stat:waitlist:total', roleKey]) {
        const cur = await env.USER_CREDITS.get(k);
        await env.USER_CREDITS.put(k, String((parseInt(cur || '0', 10) || 0) + 1));
      }
      // 零件级需求热度累加（仅真实首次签名，避免重复计数）
      for (const c of needCategories) {
        const cur = await env.USER_CREDITS.get('stat:waitlist:need:' + c);
        await env.USER_CREDITS.put('stat:waitlist:need:' + c, String((parseInt(cur || '0', 10) || 0) + 1));
      }
    }

    const totalRaw = await env.USER_CREDITS.get('stat:waitlist:total');
    const total = parseInt(totalRaw || '0', 10) || 0;

    return new Response(JSON.stringify({ success: true, total, duplicate: already, role }), { headers: h });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), { status: 500, headers: h });
  }
}
