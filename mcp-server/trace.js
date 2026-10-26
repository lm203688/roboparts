/**
 * RoboParts MCP — Trace 记录 / 长任务句柄 / 协议版本协商辅助
 *
 * 背景（2026-10-27 P2-6，审计报告 §4.4）：
 *   "MCP 要做双版本适配与可回放任务……工具输入输出全部引用
 *    project_id + revision + evidence_version；长任务返回任务句柄、
 *    进度、可取消状态和最终结果；为每次外部 Agent 调用保存可去敏
 *    回放的评估轨迹。"
 *
 * 三态诚实边界（stdio MCP 的进程模型决定的）：
 *   1. **服务端持久化做不到**：stdio 是每进程一份内存，客户端断线即丢。
 *      本模块默认纯内存环形缓冲；可用 `ROBOPARTS_TRACE_FILE` 环境变量
 *      追加写入 JSONL 文件供事后分析（不是"真持久化"，是"离线回放源"）。
 *   2. **真取消做不到**：MCP 调用是同步 JSON-RPC，没有中断通道。
 *      `cancel_task` 只置标志位，被取消的长任务在下一 checkpoint 退出。
 *   3. **多租户隔离做不到**：单进程单会话，trace 不带 user_id；调用方
 *      自己去敏（`redact` 提供默认白名单）。
 *   4. **双版本能力协商**：SDK 已支持 SUPPORTED_PROTOCOL_VERSIONS 数组
 *      （含 2024-11-05 / 2025-03-26 / 2025-11-25）。本模块在 initialize
 *      之外补一张"能力映射表"，让调用方按版本判断功能可用性，而不是
 *      猜 SDK 实现。
 */

// ------------------------------------------------------------
// 协议版本协商：能力映射表
// ------------------------------------------------------------
// 每个协议版本支持的特性集合。SDK 会自动协商，这里只暴露"这份
// RoboParts server 声明它支持哪些版本 + 各版本对应哪些能力"。
// 客户端可以据此决定要不要用新工具。

export const PROTOCOL_VERSIONS = [
  '2024-11-05', // 旧客户端最小基线（Claude Desktop 早期版本）
  '2025-03-26', // 中间版本
  '2025-11-25', // 当前 SDK 最新（LATEST_PROTOCOL_VERSION）
];

// 各版本新增的能力（相对旧版增量）。用于"新客户端看到工具列表时
// 判断哪些工具是新增的，哪些是历史兼容的"。
export const CAPABILITIES_BY_VERSION = {
  '2024-11-05': [
    'search_components', 'get_component_detail', 'check_compatibility',
    'compare_components', 'dialects_list', 'dialects_evaluate',
    'recommend_for_application', 'export_bom', 'plan_assembly',
    'preflight_check',
  ],
  // 2026-10-27 P2-6 新增
  '2025-11-25': [
    'explain_unknown', 'start_long_task', 'get_task_status',
    'cancel_task', 'trace_export', 'trace_replay',
  ],
};

/**
 * 判断某个 tool name 在指定协议版本上是否可用。
 * 未登记 → 视为"该版本及之后所有版本都可用"。
 */
export function toolAvailableAt(toolName, protocolVersion) {
  if (protocolVersion === undefined || protocolVersion === null) return true;
  // 旧版基础工具：任何版本都可用
  const base = CAPABILITIES_BY_VERSION['2024-11-05'] || [];
  if (base.includes(toolName)) return true;
  // 新版扩展工具：需要客户端声明 2025-11-25+
  const extended = CAPABILITIES_BY_VERSION['2025-11-25'] || [];
  if (extended.includes(toolName)) {
    return protocolVersion >= '2025-11-25';
  }
  // 未登记 → 默认可用（防新增工具被误判为不可用）
  return true;
}

/**
 * 协商：给客户端声明的 protocolVersion，返回它能看到哪些工具。
 * 兼容层策略：客户端没声明版本 → 全部工具（最大兼容面）；
 * 声明旧版本 → 只暴露该版本支持的工具。
 */
export function filterToolsByVersion(toolNames, protocolVersion) {
  if (!protocolVersion) return toolNames.slice();
  return toolNames.filter(n => toolAvailableAt(n, protocolVersion));
}

// ------------------------------------------------------------
// Trace 环形缓冲（内存）+ 可选 JSONL 落盘
// ------------------------------------------------------------

const TRACE_CAPACITY = 1000; // 内存环形缓冲最大条数
let traceBuf = [];           // [{trace_id, ts, tool, args_summary, result_summary, evidence_version, project_id, revision, duration_ms, status}]
let traceCounter = 0;

/**
 * 生成 trace_id：`tr_<epoch_ms>_<counter>` — 单调、可读、可排序。
 */
function makeTraceId() {
  traceCounter += 1;
  return `tr_${Date.now().toString(36)}_${String(traceCounter).padStart(6, '0')}`;
}

/**
 * 参数摘要：只留白名单字段 + 类型 + 长度，防止 PII / 凭据落 trace。
 * 白名单是**默认去敏**，不承诺完整覆盖——调用方仍需自检。
 */
export function summarizeArgs(args) {
  if (!args || typeof args !== 'object') return { type: typeof args, size: 0 };
  const summary = {};
  for (const [k, v] of Object.entries(args)) {
    if (v === null || v === undefined) { summary[k] = `null`; continue; }
    if (Array.isArray(v)) {
      summary[k] = { type: 'array', length: v.length, sample_types: Array.from(new Set(v.map(x => typeof x))).slice(0, 3) };
    } else if (typeof v === 'object') {
      // 对象：只报 keys，不透传值（防 API key / 邮箱等泄漏）
      summary[k] = { type: 'object', keys: Object.keys(v).slice(0, 10) };
    } else if (typeof v === 'string') {
      // 字符串：只留长度和 hash，防止长文本 / PII 落盘
      summary[k] = { type: 'string', length: v.length, hash8: hash8(v) };
    } else {
      summary[k] = { type: typeof v, value: v };
    }
  }
  return summary;
}

/**
 * 结果摘要：只保留判定结论 + 关键字段，不透传全量返回。
 * 结果里常见的敏感字段（价格、URL、邮箱）不登记。
 */
export function summarizeResult(result) {
  if (!result || typeof result !== 'object') return { type: typeof result };
  const interesting = ['compatible', 'verdict', 'well_typed', 'ill_typed', 'status',
                       'task_id', 'trace_id', 'evidence_version', 'revision',
                       'error', 'isError', 'reason', 'total_found'];
  const summary = {};
  for (const k of interesting) {
    if (k in result) summary[k] = result[k];
  }
  // 数组结果：报长度即可
  if (Array.isArray(result.results)) summary.results_length = result.results.length;
  if (Array.isArray(result.items)) summary.items_length = result.items.length;
  return summary;
}

/**
 * 去敏（可选）：对整份 trace 做二次去敏。
 * 目前只处理显式敏感字段名；未命中就原样透传。
 */
export function redact(trace) {
  const redacted = { ...trace };
  const sensitiveKeys = new Set([
    'api_key', 'token', 'password', 'secret', 'email',
    'authorization', 'cookie', 'session_id'
  ]);
  function walk(obj) {
    if (!obj || typeof obj !== 'object') return obj;
    if (Array.isArray(obj)) return obj.map(walk);
    const out = {};
    for (const [k, v] of Object.entries(obj)) {
      if (sensitiveKeys.has(k.toLowerCase())) out[k] = '<redacted>';
      else out[k] = walk(v);
    }
    return out;
  }
  return walk(redacted);
}

// 简单 hash（非加密用途）：防摘要里带原文，同时保留可对比性
function hash8(s) {
  let h = 0;
  const str = String(s).slice(0, 64);
  for (let i = 0; i < str.length; i++) {
    h = ((h << 5) - h + str.charCodeAt(i)) | 0;
  }
  return Math.abs(h).toString(16).padStart(8, '0').slice(0, 8);
}

/**
 * 记录一条 trace。返回 trace 对象（含 trace_id）。
 */
export function recordTrace({ tool, args, result, duration_ms, status, evidence_version, project_id, revision }) {
  const trace = {
    trace_id: makeTraceId(),
    ts: new Date().toISOString(),
    tool,
    args_summary: summarizeArgs(args),
    result_summary: summarizeResult(result),
    evidence_version: evidence_version || null,
    project_id: project_id || null,
    revision: revision || null,
    duration_ms: typeof duration_ms === 'number' ? Math.round(duration_ms) : null,
    status: status || 'ok',
  };
  traceBuf.push(trace);
  if (traceBuf.length > TRACE_CAPACITY) traceBuf.shift();
  // 可选落盘：ROBOPARTS_TRACE_FILE=/path/to/file.jsonl
  const file = process.env.ROBOPARTS_TRACE_FILE;
  if (file) {
    try {
      // 用 append 语义，不 import fs（trace.js 不依赖 fs，保持可移植）
      const fs = globalThis.__rp_fs__;
      if (fs && typeof fs.appendFileSync === 'function') {
        fs.appendFileSync(file, JSON.stringify(trace) + '\n');
      }
    } catch {
      // 落盘失败不影响主流程
    }
  }
  return trace;
}

/**
 * 导出 trace（按 filter 过滤）。
 */
export function exportTraces({ limit, tool, since, redactEnabled } = {}) {
  let out = traceBuf.slice();
  if (tool) out = out.filter(t => t.tool === tool);
  if (since) {
    const ts = new Date(since).getTime();
    out = out.filter(t => new Date(t.ts).getTime() >= ts);
  }
  if (typeof limit === 'number' && limit > 0) out = out.slice(-limit);
  if (redactEnabled !== false) out = out.map(redact);
  return out;
}

/**
 * 从 JSONL 文件重放：逐行 JSON.parse，做结构校验 + 计数。
 * 不做"重算 verdict"——那需要完整输入，回放只验证"记录本身可解析、
 * 结构完整、字段一致"。真·语义重放属于 P3 范畴。
 */
export function replayTrace(jsonLines, { strict } = {}) {
  const events = [];
  const errors = [];
  for (const [idx, line] of jsonLines.entries()) {
    if (!line || !line.trim()) continue;
    try {
      const obj = JSON.parse(line);
      // 结构完整性检查：至少要有 trace_id / tool / ts
      const missing = ['trace_id', 'tool', 'ts'].filter(k => !(k in obj));
      if (missing.length > 0) {
        errors.push({ line: idx, error: `missing_field`, missing });
        if (strict) break;
        continue;
      }
      events.push(obj);
    } catch (e) {
      errors.push({ line: idx, error: 'parse_failed', message: e.message });
      if (strict) break;
    }
  }
  return {
    replayed: events.length,
    total_lines: jsonLines.length,
    errors: errors.length,
    error_detail: errors.slice(0, 10),
    unique_tools: Array.from(new Set(events.map(e => e.tool))),
    unique_traces: new Set(events.map(e => e.trace_id)).size,
  };
}

/**
 * 清空 trace（主要用于自证测试）。
 */
export function clearTraces() {
  traceBuf = [];
  traceCounter = 0;
}

// ------------------------------------------------------------
// 长任务句柄（内存版；真取消做不到，见文件顶部诚实边界）
// ------------------------------------------------------------

const TASK_CAPACITY = 200;
const taskStore = new Map(); // task_id → {id, name, status, progress, cancelled, result, error, ts, duration_ms}
let taskCounter = 0;

const TASK_STATUSES = ['queued', 'running', 'done', 'failed', 'cancelled'];

function makeTaskId() {
  taskCounter += 1;
  return `tsk_${Date.now().toString(36)}_${String(taskCounter).padStart(6, '0')}`;
}

/**
 * 启动长任务：立刻返回 task_id，任务体是外部提供的 async function。
 * 任务体每 checkpoint 应调用 task._checkCancel() 检查是否被取消。
 */
export function startLongTask({ name, body, args }) {
  const id = makeTaskId();
  const startedAt = Date.now();
  const task = {
    id,
    name: name || 'unnamed_task',
    status: 'running',
    progress: 0,
    cancelled: false,
    result: null,
    error: null,
    ts: new Date().toISOString(),
    duration_ms: null,
    _checkCancel: () => {
      if (task.cancelled) {
        const e = new Error('task_cancelled');
        e.code = 'CANCELLED';
        throw e;
      }
    },
    _updateProgress: (p) => { task.progress = Math.max(0, Math.min(100, Number(p) || 0)); },
  };
  taskStore.set(id, task);
  if (taskStore.size > TASK_CAPACITY) {
    // 环形：淘汰最老的
    const oldest = taskStore.keys().next().value;
    taskStore.delete(oldest);
  }
  // 异步执行，不阻塞返回
  (async () => {
    try {
      if (typeof body !== 'function') throw new Error('body_must_be_function');
      const result = await body(task, args || {});
      task.result = result;
      task.progress = 100;
      task.status = task.cancelled ? 'cancelled' : 'done';
    } catch (e) {
      if (e && e.code === 'CANCELLED') {
        task.status = 'cancelled';
        task.error = 'cancelled_by_user';
      } else {
        task.status = 'failed';
        task.error = (e && e.message) || String(e);
      }
    } finally {
      task.duration_ms = Date.now() - startedAt;
    }
  })();
  return { task_id: id, status: task.status, name: task.name };
}

/**
 * 查询任务状态。
 */
export function getTaskStatus(task_id) {
  const t = taskStore.get(task_id);
  if (!t) {
    return {
      task_id,
      found: false,
      error: 'task_not_found',
      hint: '任务已被淘汰（环形缓冲超限）或从未来自的客户端',
      available_statuses: TASK_STATUSES,
    };
  }
  return {
    task_id,
    found: true,
    name: t.name,
    status: t.status,
    progress: t.progress,
    cancelled: t.cancelled,
    result: t.result,
    error: t.error,
    ts: t.ts,
    duration_ms: t.duration_ms,
  };
}

/**
 * 取消任务：置标志位。真正终止依赖任务体在 checkpoint 检查。
 */
export function cancelTask(task_id) {
  const t = taskStore.get(task_id);
  if (!t) return { task_id, cancelled: false, error: 'task_not_found' };
  if (t.status === 'done' || t.status === 'failed' || t.status === 'cancelled') {
    return {
      task_id,
      cancelled: false,
      error: `task_already_${t.status}`,
      hint: '已结束的任务无法取消；取消只对 queued / running 生效'
    };
  }
  t.cancelled = true;
  // 立即可观察的副作用：如果任务体还没跑起来就置状态
  if (t.status === 'queued') t.status = 'cancelled';
  return {
    task_id,
    cancelled: true,
    hint: '取消标志已置位；任务将在下一个 checkpoint 退出。stdio MCP 无中断通道，此非硬终止。'
  };
}

/**
 * 列出所有任务（用于诊断）。
 */
export function listTasks() {
  return Array.from(taskStore.values()).map(t => ({
    task_id: t.id,
    name: t.name,
    status: t.status,
    progress: t.progress,
    duration_ms: t.duration_ms,
    ts: t.ts,
  }));
}

export function clearTasks() {
  taskStore.clear();
  taskCounter = 0;
}

export { TASK_STATUSES, TRACE_CAPACITY, TASK_CAPACITY };
