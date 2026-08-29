/**
 * 积分账本读写 —— 唯一入口
 *
 * 【为什么存在这个文件】
 * 此前 4 处代码各自写 `if (env.USER_CREDIT_HISTORY) { ... }`，
 * 而该 KV 命名空间**从未在 wrangler.toml 绑定过**（只绑了 USER_CREDITS /
 * API_KEYS / SUPPLIERS / SUPPLIER_INQUIRIES / URDF_LIBRARY）。于是生产环境里：
 *   - register.js  注册赠送 100 积分  → 账本条目静默不写
 *   - webhook.js   真实付款到账      → 账本条目静默不写
 *   - history.js   查询              → history=[] 且 success:true
 *   - credits-history.html           → 「暂无消费记录，您的账户暂无积分变动记录」
 * 也就是把「账本从来没被记过 / 读不出来」渲染成「你没有交易」。
 * 这是对用户账户的**事实断言**，而真相是关于**我们自己的存储**——在钱上撒谎。
 *
 * 【两条硬规矩】
 *   1. 不可读 ≠ 空。只有确认后端可用、且记录确实不存在，才允许 status='empty'。
 *   2. 不可读时汇总数必须是 null，不能是 0。给 0 会被上层原样渲染成
 *      「消费 0 / 充值 0」，读者无法分辨"确实没花过"和"我们不知道"。
 *      （同 compat_engine 里 overall=null 时 score 返 null，不给 0 也不给 100。）
 *
 * 【存储后端】
 * 优先用 USER_CREDIT_HISTORY（若将来真的绑定了）；否则回落到已绑定且工作正常的
 * USER_CREDITS，以 'hist:' 前缀存放。回落是安全的：全仓无任何 USER_CREDITS.list()
 * 遍历，且 'stat:' 前缀早已是该命名空间的既有惯例。
 */

export const LEDGER_FALLBACK_PREFIX = 'hist:';
export const LEDGER_CAP = 100;

/** 解析当前可用的账本后端；都不可用返回 null（≠ 空账本） */
export function ledgerStore(env) {
  if (env && env.USER_CREDIT_HISTORY) {
    return { kv: env.USER_CREDIT_HISTORY, mapKey: (k) => k, backend: 'USER_CREDIT_HISTORY' };
  }
  if (env && env.USER_CREDITS) {
    return { kv: env.USER_CREDITS, mapKey: (k) => LEDGER_FALLBACK_PREFIX + k, backend: 'USER_CREDITS:hist' };
  }
  return null;
}

/**
 * 读账本。返回四态，调用方必须分辨：
 *   ok          有记录
 *   empty       后端可用且确认无记录（唯一允许对外说"暂无记录"的情形）
 *   unavailable 没有后端 / KV 读失败 —— 我们不知道
 *   corrupt     记录存在但解析不出 —— 我们读不懂，绝不当成空
 */
export async function readLedger(env, apiKey) {
  const store = ledgerStore(env);
  if (!store) {
    return { status: 'unavailable', reason: 'no_ledger_binding', records: null, backend: null };
  }
  let raw;
  try {
    raw = await store.kv.get(store.mapKey(apiKey));
  } catch (e) {
    return { status: 'unavailable', reason: 'kv_read_failed: ' + e.message, records: null, backend: store.backend };
  }
  if (raw === null || raw === undefined) {
    return { status: 'empty', records: [], backend: store.backend };
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    return { status: 'corrupt', reason: 'invalid_json', records: null, backend: store.backend };
  }
  if (!Array.isArray(parsed)) {
    return { status: 'corrupt', reason: 'not_an_array', records: null, backend: store.backend };
  }
  return { status: parsed.length ? 'ok' : 'empty', records: parsed, backend: store.backend };
}

/**
 * 追加一条账本记录。
 * 返回 { ok, reason, backend, degraded? }。调用方**不得忽略 ok=false**——
 * 钱已经动了却没留痕，必须让上层可见（响应里标注 + console.error）。
 *
 * 遇到 corrupt：不销毁旧值（可能可人工抢救），先把原始内容隔离到
 * <key>:quarantine:<ts>，再以新条目重建账本，并回报 degraded。
 * 这样"钱进来了"这件事一定被记下，同时旧数据没丢。
 */
export async function appendLedger(env, apiKey, entry) {
  const store = ledgerStore(env);
  if (!store) return { ok: false, reason: 'no_ledger_binding', backend: null };

  const cur = await readLedger(env, apiKey);
  if (cur.status === 'unavailable') {
    return { ok: false, reason: cur.reason, backend: cur.backend };
  }

  let records;
  let degraded;
  if (cur.status === 'corrupt') {
    try {
      const raw = await store.kv.get(store.mapKey(apiKey));
      await store.kv.put(store.mapKey(apiKey) + ':quarantine:' + Date.now(), raw == null ? '' : raw);
      degraded = 'previous_ledger_quarantined:' + cur.reason;
    } catch (e) {
      return { ok: false, reason: 'quarantine_failed: ' + e.message, backend: store.backend };
    }
    records = [];
  } else {
    records = cur.records.slice();
  }

  records.push(entry);
  if (records.length > LEDGER_CAP) records.splice(0, records.length - LEDGER_CAP);

  try {
    await store.kv.put(store.mapKey(apiKey), JSON.stringify(records));
  } catch (e) {
    return { ok: false, reason: 'kv_write_failed: ' + e.message, backend: store.backend };
  }
  const out = { ok: true, backend: store.backend, total: records.length };
  if (degraded) out.degraded = degraded;
  return out;
}

/**
 * 汇总。不可读时全部返回 null——不是 0。
 *
 * 注意 recharge 侧要涵盖 'grant'（注册赠送）与 'creem_payment'（真实付款）：
 * 旧实现只认 type==='recharge'，即便账本能读，一笔真实 Creem 付款也会
 * 在列表里看得见、却不计入 total_recharged，页面照样显示"充值 0"。
 */
export const CONSUME_TYPES = ['consume'];
export const RECHARGE_TYPES = ['recharge', 'grant', 'creem_payment', 'refund'];

export function summarizeLedger(read) {
  if (!read || (read.status !== 'ok' && read.status !== 'empty')) {
    return { total: null, total_consumed: null, total_recharged: null };
  }
  let consumed = 0;
  let recharged = 0;
  for (const r of read.records) {
    if (!r || typeof r !== 'object') continue;
    const amt = Math.abs(Number(r.amount) || 0);
    if (CONSUME_TYPES.includes(r.type)) consumed += amt;
    else if (RECHARGE_TYPES.includes(r.type)) recharged += amt;
  }
  return { total: read.records.length, total_consumed: consumed, total_recharged: recharged };
}

/** 把 readLedger 的状态映射为 HTTP 语义，供接口层统一口径 */
export function ledgerHttp(read) {
  if (read.status === 'unavailable') {
    return { status: 503, error_kind: 'ledger_unavailable', error: '积分账本当前不可读，无法确认你的交易记录（这不代表你没有交易）。请稍后重试或联系支持。' };
  }
  if (read.status === 'corrupt') {
    return { status: 500, error_kind: 'ledger_corrupt', error: '积分账本存在但无法解析，已隔离留痕待人工核查（这不代表你没有交易）。' };
  }
  return null;
}
