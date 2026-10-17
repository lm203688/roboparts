/**
 * 幂等事务层 —— Phase 3 承重结构 2（审计 §4 "幂等与事务"）
 *
 * 【为什么存在这个文件】
 * 当前 evidence_ledger / 积分账本 / 订阅支付 三处写操作都是**读-改-写**：
 *   read → mutate → write
 * 在网络抖动、Cloudflare retry、用户双击提交三种情形下会：
 *   1. 重复追加（同一 contribution_id 出现两次）
 *   2. 重复扣积分（同一笔付款被记 2 次）
 *   3. 半写入（KV put 成功一半就中断，读回不一致）
 *
 * 本层提供**通用幂等包装**：调用方把 idempotency_key 传进来，本层负责
 * "如果这个 key 已处理过就直接回放结果，不重复执行"。
 *
 * 【设计原则】（对齐 RoboParts §三三态纪律）
 *   1. 未登记 key ⇒ 执行 fn 并记录
 *   2. 已登记 key + fn 结果一致 ⇒ 直接返回缓存（幂等成功）
 *   3. 已登记 key + fn 结果不一致 ⇒ 返回 conflict（不可静默覆盖）
 *   4. KV 不可读 ⇒ 返回 status='unavailable'，**不做写**（fail-closed，与 ledger.js 同口径）
 *   5. 不做重试 —— 幂等是调用方的责任，本层只保证"同一 key 的写入副作用不重复"
 *
 * 【存储后端】
 * 优先 IDEMPOTENCY_KV（未来显式绑定）；否则回落 USER_CREDITS，用 'idem:' 前缀。
 * 前缀与 ledger.js 的 'hist:' 前缀严格隔离，防止跨命名空间污染。
 *
 * 【TTL】
 * 默认 30 天 —— 覆盖支付网关最长重试窗口 + 常见用户重复提交场景。
 * 需要更长保留的证据账本场景请显式传 ttlSeconds。
 */

export const IDEMPOTENCY_FALLBACK_PREFIX = 'idem:';
export const IDEMPOTENCY_DEFAULT_TTL_SECONDS = 30 * 24 * 60 * 60;

/** 解析当前可用的幂等存储；无后端返回 null（≠ 空存储，见文件头原则 4） */
export function idempotencyStore(env) {
  if (env && env.IDEMPOTENCY_KV) {
    return {
      kv: env.IDEMPOTENCY_KV,
      mapKey: (k) => k,
      backend: 'IDEMPOTENCY_KV',
    };
  }
  if (env && env.USER_CREDITS) {
    return {
      kv: env.USER_CREDITS,
      mapKey: (k) => IDEMPOTENCY_FALLBACK_PREFIX + k,
      backend: 'USER_CREDITS:idem',
    };
  }
  return null;
}

/**
 * 执行一次幂等事务。
 *
 * @param {object} env      Cloudflare worker env
 * @param {string} key      幂等键（调用方保证语义唯一，如 contribution_id / order_id）
 * @param {Function} fn     无参数异步函数，返回本次事务的**规范化结果**
 *                          （同一 key 必须返回**结构化等值**的结果；调用方负责规范化）
 * @param {object} [opts]
 * @param {number} [opts.ttlSeconds]         TTL，默认 30 天
 * @param {string} [opts.requested_at]       记录首次请求时间（默认当前 UTC ISO）
 * @param {object} [opts.metadata]           附加元数据（如 actor / origin）
 * @returns {Promise<{
 *   status: 'created'|'replayed'|'conflict'|'unavailable'|'error',
 *   result?: any,
 *   previous?: any,
 *   backend?: string,
 *   reason?: string
 * }>}
 */
export async function runIdempotent(env, key, fn, opts = {}) {
  const store = idempotencyStore(env);
  if (!store) {
    return {
      status: 'unavailable',
      reason: 'no_idempotency_binding',
      backend: null,
    };
  }
  if (!key || typeof key !== 'string' || key.length > 512) {
    return {
      status: 'error',
      reason: 'invalid_idempotency_key',
      backend: store.backend,
    };
  }

  const ttl = opts.ttlSeconds || IDEMPOTENCY_DEFAULT_TTL_SECONDS;
  const kvKey = store.mapKey(key);

  // 1) 读已存在记录
  let raw;
  try {
    raw = await store.kv.get(kvKey);
  } catch (e) {
    return {
      status: 'unavailable',
      reason: 'kv_read_failed: ' + e.message,
      backend: store.backend,
    };
  }

  if (raw !== null && raw !== undefined) {
    let prev;
    try {
      prev = JSON.parse(raw);
    } catch (e) {
      // 记录存在但解析不出 —— fail-closed，不覆盖
      return {
        status: 'conflict',
        reason: 'previous_record_corrupt',
        previous: null,
        backend: store.backend,
      };
    }
    if (typeof prev !== 'object' || prev === null || prev._result === undefined) {
      return {
        status: 'conflict',
        reason: 'previous_record_malformed',
        previous: prev,
        backend: store.backend,
      };
    }
    // 2) 重新执行 fn（对"业务结果"做真等值比较，不靠 JSON.stringify 的字节顺序）
    let cur;
    try {
      cur = await fn();
    } catch (e) {
      return {
        status: 'error',
        reason: 'fn_threw_on_replay: ' + e.message,
        previous: prev,
        backend: store.backend,
      };
    }
    if (deepEqual(cur, prev._result)) {
      return {
        status: 'replayed',
        result: prev._result,
        backend: store.backend,
      };
    }
    return {
      status: 'conflict',
      reason: 'result_mismatch_same_key',
      result: cur,
      previous: prev._result,
      backend: store.backend,
    };
  }

  // 3) 首次请求 —— 执行 fn 并落 KV
  let result;
  try {
    result = await fn();
  } catch (e) {
    return {
      status: 'error',
      reason: 'fn_threw_on_create: ' + e.message,
      backend: store.backend,
    };
  }
  const record = {
    _result: result,
    _created_at: opts.requested_at || new Date().toISOString(),
    _metadata: opts.metadata || null,
    _schema_version: 1,
  };
  try {
    await store.kv.put(
      kvKey,
      JSON.stringify(record),
      { expirationTtl: ttl }
    );
  } catch (e) {
    // 副作用已发生、KV 未落 —— 这是最坏情况，必须让上层可见
    return {
      status: 'error',
      reason: 'kv_write_failed: ' + e.message,
      result,
      backend: store.backend,
    };
  }
  return {
    status: 'created',
    result,
    backend: store.backend,
  };
}

/**
 * 删除一条幂等记录（人工补救用，不用于正常业务流）。
 * 调用方必须在审计日志里留痕（见 audit_log.js）。
 */
export async function forgetIdempotent(env, key) {
  const store = idempotencyStore(env);
  if (!store) return { ok: false, reason: 'no_idempotency_binding' };
  try {
    await store.kv.delete(store.mapKey(key));
    return { ok: true, backend: store.backend };
  } catch (e) {
    return { ok: false, reason: 'kv_delete_failed: ' + e.message, backend: store.backend };
  }
}

/**
 * 深度等值比较，用于幂等回放的"结果一致性"判定。
 * 只处理 JSON 可序列化类型；对 undefined 与 key 缺失视为等值。
 *
 * 顺序不敏感（对象）—— 因为同一业务对象在不同时刻可能字段顺序不同，
 * 但语义相同。数组顺序**敏感**（业务序列号是语义的一部分）。
 */
export function deepEqual(a, b) {
  if (a === b) return true;
  if (a === undefined && b === undefined) return true;
  if (a === null || b === null) return a === b;
  if (typeof a !== typeof b) return false;
  if (typeof a !== 'object') return a === b;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  if (Array.isArray(a)) {
    if (a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
      if (!deepEqual(a[i], b[i])) return false;
    }
    return true;
  }
  const ak = Object.keys(a).filter((k) => a[k] !== undefined).sort();
  const bk = Object.keys(b).filter((k) => b[k] !== undefined).sort();
  if (ak.length !== bk.length) return false;
  for (let i = 0; i < ak.length; i++) {
    if (ak[i] !== bk[i]) return false;
    if (!deepEqual(a[ak[i]], b[bk[i]])) return false;
  }
  return true;
}
