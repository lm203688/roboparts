/**
 * RoboParts BOM 兼容性检查器（免费构建者工具，对标 TraceParts）
 * POST /api/bom/check
 *
 * Body:
 * {
 *   "api_key": "gtk_xxx (可选，Pro 解锁无限制)",
 *   "items": [
 *     { "id": "OSS-TIENKUNG-001" },          // 引用库内实体（data.json / oss_components.json）
 *     { "id": "ACT-001" },
 *     { "protocol": "EtherCAT", "interface": "EtherCAT", "voltage": "48~48V", "ros_support": true, "name": "自定义关节" }
 *   ]
 * }
 *
 * 返回：
 *  - matrix: 两两兼容性（4 维：protocol/electrical/mechanical/software）
 *  - interchangeable_groups: 彼此全兼容的组件簇（可互换选型）
 *  - warnings: 冲突/风险提示
 *
 * 免费层默认允许 ≤ 12 个组件；Pro（gtk_ 或 Creem license）无限制。
 */

const FREE_ITEM_LIMIT = 12;
const UPGRADE_URL = 'https://roboparts.cc/credits';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization',
  'Content-Type': 'application/json; charset=utf-8',
};

/**
 * 【20260806-08】此处原有一份 evalDimension/tokens/parseVoltageRange 的本地副本，
 * 违反 compat_engine.js 文件头声明的"不得自带副本"约束，且已与引擎漂移：
 * 词表多出 ttl/dynamixel/standard（已并入引擎 PROTOCOL_VOCAB / MECH_VOCAB），
 * mechanical 有 null 分支但用 `!hasA && !hasB` 的 AND，单方缺数据仍落回 false。
 * 现统一改用引擎，副本删除 —— 同一份判据只能有一处实现。
 */
import { DIMENSIONS, evalDimension, scoreBreakdown, mechanicalEvidence } from '../../_lib/compat_engine.js';
import {
  newFailureCollector, loadJsonAsset, upstreamUnavailableResponse,
  resolveAuthState, authUnavailableResponse, authHeaders,
} from '../../_lib/upstream.js';

// 目录加载：三源逐个尝试。旧写法对失败一律 continue / catch 吞掉，
// 全部失败也照常返回空 map —— 下游把每个 BOM 行判成「自定义组件·无声明」，
// 于是「我们没读到实体库」被渲染成「这些零件没有声明数据」（假证据不足）。
// 现回报失败种类：全失败 → 503；部分失败 → 结果里显式标注目录降级。
async function loadAllEntities(env, request, failures) {
  const map = {};
  const sources = ['/api/data.json', '/api/oss_components.json', '/api/entities.json'];
  let okCount = 0;
  for (const f of sources) {
    const r = await loadJsonAsset(env, request, f, failures);
    if (!r.ok) continue;
    okCount++;
    for (const e of r.data) if (e && e.id) map[e.id] = e;
  }
  return { map, okCount, total: sources.length };
}

// ============ CL5：BOM → 采购转化（可购性标注） ============
const CATEGORY_NORMALIZE = {
  actuators: 'actuators', flexible_actuators: 'actuators',
  sensors: 'sensors', data_acquisition: 'sensors',
  chips: 'chips', llms: 'chips', robot_ai_models: 'chips',
  controllers: 'controllers',
  protocols: 'protocols', interfaces: 'protocols', communication: 'protocols',
  structures: 'structures', platforms: 'structures',
  '3d_printing': '3d_printing',
};
function normalizeCategory(cat) {
  if (!cat) return 'actuators';
  return CATEGORY_NORMALIZE[String(cat).toLowerCase()] || 'actuators';
}
// 供应商数据源两处加载：失败时仍返回空结构以免中断兼容性主流程，
// 但必须把 degraded 标记透传出去 —— 否则「供应商库没读到」会被渲染成
// 「这个零件没有采购渠道」，与本文件其它地方修过的假红同源。
//
// 注意 degraded 收集器必须**按请求**创建并显式传入，不能用模块级数组：
// Workers 的模块作用域在同一 isolate 内跨请求存活，模块级可变状态会不断累积，
// 把上一个请求的故障算到下一个请求头上（同 mcp.js 模块顶层 Math.random() 那次事故）。
function newDegradedCollector() {
  return [];
}
function markSupplierDegraded(collector, source, reason) {
  if (collector) collector.push({ source, reason });
}

async function loadSupplierSeed(env, request, degraded) {
  try {
    const resp = await env.ASSETS.fetch(new URL('/api/suppliers_seed.json', request.url));
    if (!resp.ok) { markSupplierDegraded(degraded, 'seed', 'upstream_status_' + resp.status); return { by_category: {}, by_keyword: {}, degraded: true }; }
    const j = await resp.json();
    return { by_category: j.by_category || {}, by_keyword: j.by_keyword || {}, degraded: false };
  } catch (e) { markSupplierDegraded(degraded, 'seed', 'fetch_failed: ' + e.message); return { by_category: {}, by_keyword: {}, degraded: true }; }
}
async function loadKvSuppliers(env, degraded) {
  if (!env.SUPPLIERS) { markSupplierDegraded(degraded, 'kv', 'no_suppliers_binding'); return []; }
  try {
    const all = [];
    let cursor = undefined, done = false;
    while (!done) {
      const opts = { prefix: 'SUP', limit: 1000 };
      if (cursor) opts.cursor = cursor;
      const res = await env.SUPPLIERS.list(opts);
      if (res.keys && res.keys.length) {
        const vals = await Promise.all(res.keys.map(k => env.SUPPLIERS.get(k.name)));
        vals.forEach(v => { if (v) { try { const s = JSON.parse(v); if (s.review_status !== 'rejected' && s.company_name) all.push(s); } catch (e) {} } });
      }
      done = res.list_complete; cursor = res.cursor;
    }
    return all;
  } catch (e) { markSupplierDegraded(degraded, 'kv', 'list_failed: ' + e.message); return []; }
}
function getPurchaseOptions(component, seed, kvByCat) {
  const cat = normalizeCategory(component.category);
  const opts = new Map();
  (seed.by_category[cat] || []).forEach(s => opts.set(s.name, s));
  const hay = [component.name, component.protocol, component.interface, component.ref].filter(Boolean).join(' ').toUpperCase();
  for (const [kw, list] of Object.entries(seed.by_keyword || {})) {
    if (hay.includes(kw.toUpperCase())) list.forEach(s => opts.set(s.name, s));
  }
  (kvByCat[cat] || []).forEach(s => {
    if (s.company_name) opts.set(s.company_name, { name: s.company_name, url: s.company_website || '', note: '已注册供应商', registered: true });
  });
  return [...opts.values()];
}

// ============ GRASP 借鉴：BOM → 有序装配步骤 ============
// GRASP 的 bom-manager/checker 能产出"有序安装步骤"。本平台此前只给兼容性矩阵与可互换组，
// 缺安装次序。现从机械对接关系（mateable 对的方向：attachment.tool ∩ base.robot）构建挂载 DAG，
// Kahn 拓扑排序得安装次序；无挂载关系的组件按品类层级 fallback。
// 诚实边界：当前机械接口声明率 ~1.52%，绝大多数 BOM 无足够对接数据，此时次序纯为品类层级
// 推测，必须显式标注 basis=category_heuristic，不得伪装成由物理约束推导。
const CATEGORY_LAYER = {
  structures: 0, platforms: 0,
  controllers: 1,
  actuators: 2, 'flexible_actuators': 2,
  sensors: 3, 'data_acquisition': 3,
  chips: 4, llms: 4, 'robot_ai_models': 4,
  protocols: 5, interfaces: 5, communication: 5,
  '3d_printing': 6,
};
function catLayer(cat) { return CATEGORY_LAYER[String(cat || '').toLowerCase()] ?? 2; }

export function buildAssemblySequence(resolved, matrix) {
  const n = resolved.length;
  const mech = resolved.map(r => mechanicalEvidence(r));
  const edges = [];          // {base, attach}: base 先装，attach 装在 base 上
  const dataDerived = new Set();
  for (const m of matrix) {
    if (m.overall_compatible !== true) continue;
    const mechDim = m.dimensions.find(d => d.dimension === 'mechanical');
    if (!mechDim || mechDim.relation !== 'mateable') continue;   // 仅"可对接"能定方向；可互换不暗示堆叠
    const ia = resolved.findIndex(r => r.ref === m.a);
    const ib = resolved.findIndex(r => r.ref === m.b);
    if (ia < 0 || ib < 0) continue;
    const ea = mech[ia], eb = mech[ib];
    const aOnB = ea.tool.some(t => eb.robot.includes(t));
    const bOnA = eb.tool.some(t => ea.robot.includes(t));
    if (aOnB && !bOnA) { edges.push({ base: ib, attach: ia }); dataDerived.add(ia); dataDerived.add(ib); }
    else if (bOnA && !aOnB) { edges.push({ base: ia, attach: ib }); dataDerived.add(ia); dataDerived.add(ib); }
    // 双向或双向无（ambiguous）→ 跳过方向，避免编造装配约束
  }
  // Kahn 拓扑排序（队列按品类层级稳定排序，保证无约束时结构→控制→执行器→传感器）
  const indeg = new Array(n).fill(0);
  const adj = Array.from({ length: n }, () => []);
  for (const { base, attach } of edges) { adj[base].push(attach); indeg[attach]++; }
  const orderKey = i => catLayer(resolved[i].category) * 1000 + i;
  let q = [];
  for (let i = 0; i < n; i++) if (indeg[i] === 0) q.push(i);
  q.sort((a, b) => orderKey(a) - orderKey(b));
  const order = [];
  while (q.length) {
    const u = q.shift();
    order.push(u);
    for (const v of adj[u]) { indeg[v]--; if (indeg[v] === 0) { q.push(v); q.sort((a, b) => orderKey(a) - orderKey(b)); } }
  }
  const cyclic = order.length < n;
  if (cyclic) {
    const rest = [];
    for (let i = 0; i < n; i++) if (!order.includes(i)) rest.push(i);
    rest.sort((a, b) => orderKey(a) - orderKey(b));
    order.push(...rest);
  }
  const seq = order.map((idx, step) => {
    const r = resolved[idx];
    const mountsOn = edges.filter(e => e.attach === idx).map(e => resolved[e.base].ref);
    const basis = dataDerived.has(idx) ? 'mount_relation' : 'category_heuristic';
    const reason = basis === 'mount_relation'
      ? (mountsOn.length ? `依机械对接关系：安装在 ${mountsOn.join(' / ')} 之上` : '机械接口数据定位的基座件（无上游挂载）')
      : '无机械接口声明，按品类层级推测（结构/控制先于执行器/传感器）';
    return { step: step + 1, ref: r.ref, name: r.name, category: normalizeCategory(r.category), mounts_on: mountsOn, basis, reason };
  });
  const dataCount = dataDerived.size;
  const notes = {
    data_derived_steps: dataCount,
    heuristic_steps: n - dataCount,
    basis: dataCount > 0 ? 'partial_data_derived' : 'fully_heuristic',
    honesty: dataCount > 0
      ? '安装次序部分由真实机械对接关系（工具侧/安装侧）推导，其余按品类层级推测。'
      : '当前机械接口声明率极低（~1.52%），无足够对接数据，安装次序按品类层级推测（结构→控制→执行器→传感器），仅作排布参考，非物理装配约束。',
    cycle_detected: cyclic,
    method: '挂载 DAG 由 mateable 对方向（attachment.tool ∩ base.robot）构建，Kahn 拓扑排序；无挂载关系的组件按品类层级 fallback。',
  };
  return { sequence: seq, notes };
}

export async function onRequestOptions() { return new Response(null, { headers: corsHeaders }); }

export async function onRequestGet() {
  return new Response(JSON.stringify({
    endpoint: '/api/bom/check', method: 'POST',
    description: 'BOM 兼容性检查器：输入一组组件（库内 ID 或自定义规格），返回两两兼容性矩阵、可互换组、冲突告警，以及由机械对接关系推导的有序装配步骤（assembly_sequence / assembly_notes）。免费层 ≤12 组件，Pro 无限制。',
    request_body: { items: 'array - 组件列表，每项 {id} 或 {protocol,interface,voltage,ros_support,name}' },
    example: { items: [ { id: 'OSS-TIENKUNG-001' }, { id: 'OSS-UNITREE_G1-001' }, { protocol: 'EtherCAT', interface: 'EtherCAT', voltage: '48~48V', ros_support: true, name: '自定义 EtherCAT 关节' } ] },
  }, null, 2), { status: 200, headers: { ...corsHeaders, 'Cache-Control': 'public, max-age=3600' } });
}

export async function onRequestPost(context) {
  const { request, env } = context;
  try {
    const body = await request.json();
    const items = body.items || [];
    if (!Array.isArray(items) || items.length < 2) {
      return new Response(JSON.stringify({ error: 'items 需为至少 2 个组件的数组' }), { status: 400, headers: corsHeaders });
    }
    const authInfo = await resolveAuthState(request, env);
    const tier = authInfo.tier;
    // 免费额度拦截是一句「你不是 Pro」的断言。密钥校验链路故障（unverified）时
    // 我们并不知道用户是不是 Pro，此时若照旧回 402「升级 Pro」，就是指着付费用户说没付钱。
    // 让路：回 503 auth_unavailable，说明是我们验不了，而不是他没买。
    if (authInfo.auth_state === 'unverified' && items.length > FREE_ITEM_LIMIT) {
      return authUnavailableResponse(authInfo.auth_failure, corsHeaders);
    }
    if (tier === 'free' && items.length > FREE_ITEM_LIMIT) {
      return new Response(JSON.stringify({
        error: '免费层最多 ' + FREE_ITEM_LIMIT + ' 个组件',
        upgrade_url: UPGRADE_URL,
        message: '升级 Pro 解锁无限制 BOM 检查与完整规格导出。',
      }), { status: 402, headers: { ...corsHeaders, 'X-Upgrade-URL': UPGRADE_URL } });
    }

    const catalogFailures = newFailureCollector();
    const catalog = await loadAllEntities(env, request, catalogFailures);
    if (catalog.okCount === 0) {
      // 三个数据源全军覆没：此时任何「未声明 / 证据不足」的结论都是伪造的。
      return upstreamUnavailableResponse(catalogFailures, corsHeaders,
        '组件目录全部读取失败，无法区分「零件未声明规格」与「我们没读到目录」，已拒绝给出兼容性结论。');
    }
    const map = catalog.map;
    const supplierDegraded = newDegradedCollector();   // 按请求创建，不跨请求累积
    const seed = await loadSupplierSeed(env, request, supplierDegraded);
    const kvSuppliers = await loadKvSuppliers(env, supplierDegraded);
    const kvByCat = {};
    kvSuppliers.forEach(s => { (s.product_categories || []).forEach(c => { (kvByCat[c] = kvByCat[c] || []).push(s); }); });
    const resolved = items.map((it, i) => {
      if (it.id && map[it.id]) {
        const e = map[it.id];
        // interfaces / mechanical_interface 必须透传：引擎的 tokens() 与 declaredMechanical()
        // 依赖它们判断"是否有声明"，漏传会让有数据的实体被误判为未声明（假红）。
        // ros_support 同理且更隐蔽：旧写法 `=== true` 会在**进引擎之前**就把
        // undefined（未声明）压成 false（声明为不支持），引擎再三态也救不回来。原样透传。
        return { index: i, ref: it.id, name: e.name || it.id, category: e.category, protocol: e.protocol, interface: e.interface, interfaces: e.interfaces, mechanical_interface: e.mechanical_interface, voltage: e.voltage, ros_support: e.ros_support, compatibility: e.compatibility || [], lookup_state: 'catalog' };
      }
      // 目录部分降级时，「库里查不到这个 id」可能只是那一份源没读出来。
      // 标注 lookup_state，避免把「我们没读到」沉默地当成「这是个无声明的自定义件」。
      const lookupState = it.id
        ? (catalog.okCount < catalog.total ? 'not_found_catalog_degraded' : 'not_found_in_catalog')
        : 'user_supplied';
      return { index: i, ref: it.id || ('custom-' + i), name: it.name || it.id || ('自定义组件' + i), category: it.category || '', protocol: it.protocol || '', interface: it.interface || '', interfaces: it.interfaces, mechanical_interface: it.mechanical_interface, voltage: it.voltage || '', ros_support: typeof it.ros_support === 'boolean' ? it.ros_support : undefined, compatibility: it.compatibility || [], lookup_state: lookupState };
    });

    // 两两矩阵
    const matrix = [];
    for (let i = 0; i < resolved.length; i++) {
      for (let j = i + 1; j < resolved.length; j++) {
        const a = resolved[i], b = resolved[j];
        const dims = DIMENSIONS.map(d => ({ dimension: d, ...evalDimension(d, a, b) }));
        const decided = dims.filter(x => x.compatible !== null);
        const compatCount = decided.filter(x => x.compatible).length;
        const overall = decided.length ? (compatCount === decided.length) : null;
        matrix.push({
          a: a.ref, b: b.ref,
          dimensions: dims,
          overall_compatible: overall,
          // 【P0 · 20260815】分数走引擎的同一折算函数 scoreBreakdown，
          // 与 /api/compatibility、/mcp 三方共用一套加权逻辑，杜绝双份实现。
          compatibility_score: decided.length ? scoreBreakdown(dims).weighted_score : 0,
        });
      }
    }

    // 可互换组（并查集：两两全兼容则连通）
    const parent = resolved.map((_, i) => i);
    function find(x) { while (parent[x] !== x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; }
    function union(a, b) { parent[find(a)] = find(b); }
    // 【20260811-03】"可对接"不是"可互换"。引擎的 mechanical 维度现在会区分
    // relation=mateable（一方工具侧==另一方安装侧，能堆在一起）与
    // relation=interchangeable（安装侧相同，能替换）。前者是**串联**关系，
    // 把它并进"可互换选型"组等于建议用户拿力传感器替换夹爪。
    // 只有当机械维度不是"仅靠对接关系成立"时才允许连通。
    const mateableOnly = (m) => {
      const mech = m.dimensions.find(d => d.dimension === 'mechanical');
      return !!mech && mech.compatible === true && mech.relation === 'mateable';
    };
    for (const m of matrix) {
      if (m.overall_compatible === true && !mateableOnly(m)) {
        const ia = resolved.findIndex(r => r.ref === m.a);
        const ib = resolved.findIndex(r => r.ref === m.b);
        union(ia, ib);
      }
    }
    const groups = {};
    resolved.forEach((r, i) => { const g = find(i); (groups[g] = groups[g] || []).push(r.ref); });
    const interchangeable_groups = Object.values(groups).filter(g => g.length > 1);

    // 告警：仅针对**真冲突**（双方都有声明且不匹配），并指明是哪个维度。
    // 修复前"无数据"也会落进 overall=false，于是对用户弹出根本不存在的不兼容告警。
    const DIM_LABEL = { protocol: '协议', electrical: '电压', mechanical: '机械接口', software: 'ROS2 支持' };
    const warnings = matrix.filter(m => m.overall_compatible === false).map(m => {
      const bad = m.dimensions.filter(d => d.compatible === false).map(d => DIM_LABEL[d.dimension] || d.dimension);
      return `组件 ${m.a} 与 ${m.b} 在 ${bad.join('/')} 维度存在实际冲突（双方均有声明且不匹配）`;
    });

    // GRASP 借鉴：从兼容性矩阵推导有序装配步骤（挂载 DAG 拓扑排序）
    const assembly = buildAssemblySequence(resolved, matrix);

    // CL5：采购建议聚合（构建者「检查→采购」转化闭环）
    const sumMap = new Map();
    resolved.forEach(r => {
      getPurchaseOptions(r, seed, kvByCat).forEach(s => {
        if (!sumMap.has(s.name)) sumMap.set(s.name, { name: s.name, url: s.url, note: s.note, registered: !!s.registered, categories: new Set() });
        sumMap.get(s.name).categories.add(normalizeCategory(r.category));
      });
    });
    const purchase_summary = [...sumMap.values()].map(s => ({ name: s.name, url: s.url, note: s.note, registered: s.registered, categories: [...s.categories] }));

    return new Response(JSON.stringify({
      success: true, tier, auth_state: authInfo.auth_state,
      auth_failure: authInfo.auth_failure || undefined,
      // undecided_pairs 必须与 compatible/incompatible 并列透出：数据集里绝大多数
      // 组件未声明协议/机械接口，不透出会让调用方把"证据不足"误读成"不兼容"。
      summary: {
        components: resolved.length, pairs: matrix.length,
        compatible_pairs: matrix.filter(m => m.overall_compatible === true).length,
        incompatible_pairs: matrix.filter(m => m.overall_compatible === false).length,
        undecided_pairs: matrix.filter(m => m.overall_compatible === null).length,
        interchangeable_groups: interchangeable_groups.length, purchase_options: purchase_summary.length,
        evidence_note: 'undecided_pairs 为四个维度均无双方声明、无法判定的组合；不计入兼容也不计入冲突',
        // 目录源降级时必须声明：undecided/未命中可能是「没读到目录」而非「零件没声明」
        catalog_sources_ok: catalog.okCount + '/' + catalog.total,
        catalog_sources_degraded: catalogFailures.length ? catalogFailures : undefined,
        evidence_complete: catalog.okCount === catalog.total,
        // 供应商数据源降级时必须声明：purchase_options 为空可能是"没读到"而非"没有渠道"
        supplier_sources_degraded: supplierDegraded.length ? supplierDegraded : undefined,
        purchase_options_complete: supplierDegraded.length === 0,
      },
      components: resolved.map(r => ({
        ref: r.ref, name: r.name, category: normalizeCategory(r.category), protocol: r.protocol, interface: r.interface, voltage: r.voltage, ros_support: r.ros_support,
        purchase_options: getPurchaseOptions(r, seed, kvByCat),
      })),
      matrix,
      interchangeable_groups,
      warnings,
      assembly_sequence: assembly.sequence,
      assembly_notes: assembly.notes,
      purchase_summary,
    }, null, 2), {
      status: 200,
      headers: { ...corsHeaders, 'Cache-Control': 'no-store', 'X-API-Tier': tier, ...authHeaders(authInfo.auth_state, UPGRADE_URL) },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: 'Internal error', message: e.message }), { status: 500, headers: corsHeaders });
  }
}

// HEAD 探活：Pages 不把 HEAD 映射到 onRequestGet，缺此导出则一律 404 ——
// 对外声明过的地址被目录站/监控探成"不存在"。完整复盘见 functions/mcp.js 同名函数。
export async function onRequestHead(context) {
  const r = await onRequestGet(context);
  return new Response(null, { status: r.status, headers: r.headers });
}
