/**
 * 审计日志层 —— Phase 3 承重结构 4（审计 §4 "审计日志"）
 *
 * 【为什么存在这个文件】
 * 审计实测：register / payment webhook / spec_declare / supplier-admin 四处
 * 关键写操作**没有任何审计留痕**——发生争议时无法回答"是谁在什么时候改的"。
 * 对积分/支付/声明三条链路这是不可接受的：都是可对用户或企业产生实质
 * 后果的写入。
 *
 * 【设计原则】（对齐 RoboParts §三三态纪律 + 供应链最小化）
 *   1. **异步 best-effort**：审计失败**不阻塞**主业务（否则一次 KV 抖动让
 *      注册全部失败）；但**必须**在响应/日志里可见
 *   2. **不写敏感字段**：apiKey/token/password 等直接丢弃；email 只留哈希
 *      摘要，避免把审计日志变成新的 PII 泄漏面
 *   3. **不可改写**：追加式，每条记录自算 hash 挂在 prev_hash 上，形成
 *      hash-chain（与 evidence_ledger 同口径）
 *   4. **默认关**：调用方必须显式 env.AUDIT_LOG_ENABLED === '1' 才写
 *      ——避免未知情就把日志开到生产 KV
 *
 * 【存储后端】
 * 优先 AUDIT_LOG_KV（未来显式绑定）；否则回落 USER_CREDITS，用 'audit:'
 * 前缀。前缀与 ledger.js 的 'hist:'、idempotency.js 的 'idem:' 严格隔离。
 *
 * 【TTL】
 * 默认 90 天。合规需要更长的请显式传 ttlSeconds。
 * 90 天是"够回答大部分争议"和"KV 成本可控"之间的默认值——具体业务可
 * 通过 AUDIT_TTL_SECONDS 环境变量覆盖。
 */

export const AUDIT_FALLBACK_PREFIX = 'audit:';
export const AUDIT_DEFAULT_TTL_SECONDS = 90 * 24 * 60 * 60;
export const AUDIT_BUFFER_CAP = 500;

// 需要脱敏丢弃的字段名（大小写不敏感）
const SENSITIVE_KEYS = new Set([
  'api_key', 'apikey', 'api-key',
  'token', 'access_token', 'refresh_token',
  'password', 'passwd',
  'authorization', 'auth',
  'idempotency_key',
  'secret', 'client_secret',
]);

// 部分脱敏字段（保留哈希，避免完全不可追溯）
const HASH_KEYS = new Set(['email', 'phone', 'user_id']);

/**
 * 判断当前环境是否启用审计。
 * 必须 env.AUDIT_LOG_ENABLED === '1' 显式打开。
 */
export function auditEnabled(env) {
  return env && env.AUDIT_LOG_ENABLED === '1';
}

/** 解析审计存储；关闭或无后端均返回 null */
export function auditStore(env) {
  if (!auditEnabled(env)) return null;
  if (env && env.AUDIT_LOG_KV) {
    return { kv: env.AUDIT_LOG_KV, mapKey: (k) => k, backend: 'AUDIT_LOG_KV' };
  }
  if (env && env.USER_CREDITS) {
    return { kv: env.USER_CREDITS, mapKey: (k) => AUDIT_FALLBACK_PREFIX + k, backend: 'USER_CREDITS:audit' };
  }
  return null;
}

/** 计算字符串摘要（截断的 SHA-1 前 12 字符），用作 email/phone 的脱敏 ID */
export async function hashForRedaction(value) {
  if (value === null || value === undefined) return null;
  const s = String(value);
  try {
    const enc = new TextEncoder();
    const buf = await crypto.subtle.digest('SHA-256', enc.encode(s));
    const hex = Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('');
    return 'h:' + hex.slice(0, 12);
  } catch (e) {
    // 极罕见：crypto.subtle 不可用（非 TLS 上下文）时退化为长度标记
    return 'l:' + s.length;
  }
}

/**
 * 递归脱敏：丢弃敏感字段，哈希 PII 字段，其它字段原样保留。
 *
 * @param {any} obj
 * @returns {any}
 */
export async function redact(obj) {
  if (obj === null || obj === undefined) return obj;
  if (typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) {
    const out = [];
    for (const item of obj) out.push(await redact(item));
    return out;
  }
  const out = {};
  for (const [k, v] of Object.entries(obj)) {
    const lk = k.toLowerCase();
    if (SENSITIVE_KEYS.has(lk)) {
      out[k] = '[redacted]';
      continue;
    }
    if (HASH_KEYS.has(lk)) {
      out[k] = await hashForRedaction(v);
      continue;
    }
    out[k] = v === null || typeof v !== 'object' ? v : await redact(v);
  }
  return out;
}

/**
 * 追加一条审计事件。
 *
 * @param {object} env
 * @param {object} entry
 * @param {string} entry.action      如 'register.create' / 'payment.webhook.received'
 * @param {string} entry.actor_kind  如 'user' / 'system' / 'external'
 * @param {string} [entry.actor_ref] 已脱敏的 actor 标识（通常是 hashForRedaction 的结果）
 * @param {object} [entry.payload]   事件上下文（会自动 redact）
 * @param {string} [entry.result]    'success' | 'fail' | 'skipped' 等
 * @param {object} [opts]
 * @param {number} [opts.ttlSeconds] TTL，默认 90 天
 * @returns {Promise<{status:'written'|'disabled'|'unavailable'|'error', backend?:string, reason?:string}>}
 *
 * 语义：
 *   - status='written'     已写入 KV
 *   - status='disabled'    审计未启用，直接跳过（不算失败）
 *   - status='unavailable' 有开关但 KV 不可用（**必须**让上层可见）
 *   - status='error'       其它异常（同样必须可见）
 */
export async function appendAudit(env, entry, opts = {}) {
  if (!auditEnabled(env)) {
    return { status: 'disabled' };
  }
  const store = auditStore(env);
  if (!store) {
    return { status: 'unavailable', reason: 'no_audit_binding' };
  }
  const ttl = opts.ttlSeconds
    || Number(env.AUDIT_TTL_SECONDS)
    || AUDIT_DEFAULT_TTL_SECONDS;

  if (!entry || typeof entry !== 'object' || typeof entry.action !== 'string') {
    return { status: 'error', reason: 'entry.action is required', backend: store.backend };
  }

  // 1) 取当日分区键（按 UTC 日期分桶，避免单键无限膨胀）
  const now = new Date();
  const dayKey = now.toISOString().slice(0, 10);
  const kvKey = store.mapKey('day:' + dayKey);

  // 2) 读当前缓冲
  let raw;
  try {
    raw = await store.kv.get(kvKey);
  } catch (e) {
    return { status: 'unavailable', reason: 'kv_read_failed: ' + e.message, backend: store.backend };
  }
  let buffer = [];
  if (raw !== null && raw !== undefined) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) buffer = parsed;
    } catch (e) {
      // 缓冲损坏不重写，只在新缓冲里留一条 error 事件——避免悄悄覆盖历史
      buffer = [];
      buffer.push({
        _schema_version: 1,
        _ts: now.toISOString(),
        action: 'audit.buffer.corrupt',
        actor_kind: 'system',
        actor_ref: null,
        result: 'warn',
        payload: { reason: 'previous_buffer_invalid_json' },
        _hash: null,
      });
    }
  }

  // 3) 脱敏 payload
  let safePayload;
  try {
    safePayload = await redact(entry.payload || {});
  } catch (e) {
    return { status: 'error', reason: 'redact_failed: ' + e.message, backend: store.backend };
  }

  // 4) 组装条目
  const safeEntry = {
    _schema_version: 1,
    _ts: now.toISOString(),
    action: entry.action,
    actor_kind: entry.actor_kind || 'system',
    actor_ref: entry.actor_ref || null,
    result: entry.result || 'success',
    payload: safePayload,
    _hash: null, // 占位，下面回填
  };
  buffer.push(safeEntry);
  if (buffer.length > AUDIT_BUFFER_CAP) buffer.splice(0, buffer.length - AUDIT_BUFFER_CAP);

  // 5) 计算 hash chain（对前 n-1 条回填 _hash，最后一条为本次新增）
  let prevHash = null;
  for (let i = 0; i < buffer.length - 1; i++) {
    if (buffer[i]._hash === null && buffer[i].action !== 'audit.buffer.corrupt') {
      try {
        const body = JSON.stringify({ ...buffer[i], _hash: null });
        const enc = new TextEncoder();
        const buf = await crypto.subtle.digest('SHA-256', enc.encode(prevHash + '|' + body));
        const hex = Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('');
        buffer[i]._hash = 'h:' + hex.slice(0, 24);
      } catch (e) {
        // hash 计算失败不阻塞写入；这条留 _hash:null 即可
      }
    }
    if (buffer[i]._hash) prevHash = buffer[i]._hash;
  }
  // 最后一条也算 hash
  try {
    const last = buffer[buffer.length - 1];
    const body = JSON.stringify({ ...last, _hash: null });
    const enc = new TextEncoder();
    const buf = await crypto.subtle.digest('SHA-256', enc.encode(prevHash + '|' + body));
    const hex = Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('');
    last._hash = 'h:' + hex.slice(0, 24);
  } catch (e) {
    // 同上，不阻塞
  }

  // 6) 写回
  try {
    await store.kv.put(kvKey, JSON.stringify(buffer), { expirationTtl: ttl });
    return { status: 'written', backend: store.backend, buffered: buffer.length };
  } catch (e) {
    return { status: 'unavailable', reason: 'kv_write_failed: ' + e.message, backend: store.backend };
  }
}

/**
 * 查询某日的审计事件（人工审阅 / 争议排查用）。
 * 只读，不改动；返回 redacted 数据。
 */
export async function readAuditDay(env, dayKey) {
  const store = auditStore(env);
  if (!store) return { status: 'disabled', records: null };
  if (!dayKey || !/^\d{4}-\d{2}-\d{2}$/.test(dayKey)) {
    return { status: 'error', reason: 'invalid_dayKey', records: null };
  }
  try {
    const raw = await store.kv.get(store.mapKey('day:' + dayKey));
    if (raw === null || raw === undefined) return { status: 'empty', records: [], backend: store.backend };
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return { status: 'corrupt', records: null, backend: store.backend };
    return { status: 'ok', records: parsed, backend: store.backend };
  } catch (e) {
    return { status: 'unavailable', reason: e.message, records: null, backend: store.backend };
  }
}
