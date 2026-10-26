# Project v2 设计文档（P1-1）

> **状态**：设计草案，待评审。**尚未实现**。
> **对应 backlog**：审计 `docs/RoboParts-全面提升与前沿演进报告-20261026.md § 9.2 P1-1`
> **前置依赖**：P0（已收口 12/13）
> **后置依赖**：P1-2 Composition IR v1、P1-7 浏览器 E2E
> **验收指标（审计口径）**：五步全链保存/恢复/复算/回放；冲突不静默覆盖
> **工作量估算**：10-15 天

---

## 0. 一句话设计

**Project v2 = 事件溯源（Event Sourcing）的项目模型**：任何用户操作追加为一条不可变事件，当前状态 = 事件回放 + 快照覆盖。**没有"保存按钮"**——每次点击都追加事件。

这个设计不是"更好用的 Project 页面"，而是**把当前静态 JSON 单向查询的架构升级为可写、可回滚、可分享、可复算的事件流**。P1-2（Composition IR）、P1-7（E2E）、P2-1（Evidence Graph）、P2-6（MCP 任务句柄与 Trace）、P2-7（AG-UI 事件流工作台）都建立在这层之上。

---

## 1. 当前状态（现状盘点，2026-10-26 实测）

| 页 | 数据存哪 | 能否恢复 | 能否复算 |
|---|---|---|---|
| `selection.html` | 内存 + URL query | ❌ 刷新丢 | ❌ |
| `build-planner.html` | 内存 + URL query | ❌ | ❌ |
| `designer.html` | 内存 | ❌ | ❌ |
| `bom-checker.html` | 内存 | ❌ | ❌ |
| `adapter-generator.html` | 内存 | ❌ | ❌ |
| `bom-manager.html` | localStorage + BOM store | ✅ 单机 | ❌ 云端版本无 revision |
| 其余页面 | stateless 单向查询 | — | — |

**关键事实**：**当前系统没有"项目"这个概念**。BOM manager 是唯一有持久化的页面，但那是"BOM 表"而不是"项目快照"——不记录 revision、不记录操作来源、不记录冲突。

审计报告的 P1-1 说"五步全链保存/恢复/复算/回放"——**当前五步之间没有链路**，每一步都是独立页 + 独立存储（或没存储）。

---

## 2. 架构决策

### 2.1 为什么事件溯源，不是 CRUD

CRUD（保存/加载/覆盖）的三种致命缺陷，恰好命中审计报告的四条验收指标：

| 审计指标 | CRUD 做得到吗 |
|---|---|
| 保存/恢复 | ✅ 但恢复的是"最后一次保存"，中间步骤全丢 |
| 复算 | ❌ 无法从"事件序列"重放得到当前状态，因为事件序列不存在 |
| 回放 | ❌ 无事件、无时间轴 |
| 冲突不静默覆盖 | ❌ CRUD 天然"后来者覆盖"，静默是默认行为 |

**事件溯源是审计唯一能同时满足四项的模型。** 这个选择没有争议，只是要承认：**这是一次架构升级，不是加个"保存按钮"。**

### 2.2 为什么在 Server 端，不是客户端

| 方案 | 冲突检测 | 只读分享 | 审计追溯 | 离线可用 |
|---|---|---|---|---|
| 纯客户端（localStorage + IndexedDB） | ❌ 无 | ❌ URL 塞事件流太长 | ❌ | ✅ |
| **纯 Server 端（Cloudflare KV + D1）** | ✅ | ✅（分享 token） | ✅ | ❌（需本地缓存） |
| 混合（Server 主 + Client 缓存） | ✅ | ✅ | ✅ | ✅ |

审计 P1-1 明确要"服务端快照"，选纯 Server 端。Cloudflare Pages 已有 KV（`functions/kv/`）和可接入 D1（Postgres on Edge）。

**诚实边界**：Cloudflare KV 的写吞吐上限 1 req/ms，D1 的并发上限更严。**不做"高频实时更新"的承诺**——项目是**低频写**（用户操作间隔 30 秒-数分钟），事件追加是秒级操作，配额宽松。

### 2.3 不做重微服务

审计报告 § 8.3 明确说"不必立即上重型微服务"。Project v2 不引入：
- ❌ 独立后端服务（继续跑在 Cloudflare Functions 里）
- ❌ 消息队列（Cloudflare Durable Objects 内部处理）
- ❌ 独立的"项目管理服务"（就是几个 `/api/project/*` 端点）

**只引入**：Cloudflare D1 一个表（events 表）+ KV 一个 namespace（snapshots）。

---

## 3. 数据模型

### 3.1 事件（Event）

事件是 Project v2 的核心抽象。**不可变、追加写、可序列化。**

```ts
// 一个事件
type ProjectEvent = {
  eventId: string;       // UUIDv7（时间有序）
  projectId: string;     // 项目 ID
  revision: number;      // 从 1 开始递增
  actor: string;         // 用户 ID / 匿名 session ID
  timestamp: string;     // ISO 8601 UTC
  action: ActionType;    // 事件类型（见 § 3.2）
  payload: JSON;         // 事件体（每 action 不同 schema）
  parentEventId?: string; // 上一个事件的 ID（构成事件链）
  hash: string;          // SHA-256(eventId + payload + parentEventId)，链式校验
};
```

**为什么加 hash 链**：审计 § 4.5 要求"AI 项目的双层评估"包含可信链验证。**每条事件都自证未被篡改**——攻击者改一个 payload 需要重算所有后续事件的 hash，成本远超价值。

**为什么不用数据库自增 ID 做 revision**：并发冲突检测必须靠 revision，但 revision 是**逻辑序号**不是物理存储行号——D1 的行 ID 不稳定，revision 必须显式。

### 3.2 ActionType 枚举（v1 覆盖五步主链）

```ts
type ActionType =
  // Selection step
  | 'selection.add_part'    // { entityId, quantity }
  | 'selection.remove_part' // { entityId }
  | 'selection.update_qty'  // { entityId, newQty }
  // Build planner step
  | 'buildplanner.set_power_budget'  // { watts }
  | 'buildplanner.add_constraint'    // { axis, key, value }
  // Designer step
  | 'designer.set_mechanism'   // { id, type, target }
  | 'designer.set_mechanism_params' // { id, params }
  // BOM checker step
  | 'bomchecker.run_check'     // { } — 触发一次检查（结果不算事件）
  | 'bomchecker.accept_result' // { checkId, decisions }
  // Adapter generator step
  | 'adaptergen.generate'      // { fromInterface, toInterface, params }
  | 'adaptergen.accept_model'  // { fromId, modelId }
  // Meta actions
  | 'project.create'           // { title, description }
  | 'project.rename'           // { title }
  | 'project.snapshot'         // { label } — 打一个快照点
  | 'project.branch'           // { fromRevision, newTitle } — 分叉
```

**关键约束**：所有 payload 字段都要**幂等**——重复应用不能改变状态。`selection.add_part` 用 `entityId` 做 upsert 语义。

### 3.3 快照（Snapshot）

事件多了以后，从事件 0 重放成本高。快照是**当前状态的全量导出**：

```ts
type ProjectSnapshot = {
  projectId: string;
  snapshotRevision: number;  // 对应到哪个 revision
  data: CompositionState;    // § 3.4
  hash: string;              // SHA-256(data)
};
```

**快照频率**：默认每 50 个事件打一个快照，或每次显式 `project.snapshot` 动作时打。用户也可以手动"打快照点"作为里程碑。

### 3.4 CompositionState（Composition IR 雏形，供 P1-2 演进）

```ts
type CompositionState = {
  selection: { entityId: string; quantity: number }[];
  powerBudget: { watts: number | null };
  constraints: { axis: string; key: string; value: any }[];
  mechanisms: { id: string; type: string; target: string; params: JSON }[];
  bomChecks: { checkId: string; decisions: JSON; timestamp: string }[];
  adapters: { fromId: string; fromInterface: string; toInterface: string;
             modelId: string; modelUrl: string }[];
  branchOf?: { projectId: string; revision: number };
};
```

**这已经是 Composition IR v1 的雏形**（P1-2 目标）。P1-2 会补上跨引擎语义（ROS Runtime Profile / OpenUSD / MJCF）——**本设计先只覆盖五步主链的语义**，避免 P1-2 一上就把范围撑爆。

### 3.5 D1 schema（SQLite）

```sql
CREATE TABLE IF NOT EXISTS project_events (
  event_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  revision INTEGER NOT NULL,
  actor TEXT NOT NULL,
  timestamp TEXT NOT NULL,
  action TEXT NOT NULL,
  payload TEXT NOT NULL,          -- JSON string
  parent_event_id TEXT,
  hash TEXT NOT NULL,
  FOREIGN KEY (parent_event_id) REFERENCES project_events(event_id)
);
CREATE INDEX IF NOT EXISTS idx_events_project ON project_events(project_id, revision);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON project_events(timestamp);

CREATE TABLE IF NOT EXISTS project_snapshots (
  project_id TEXT NOT NULL,
  snapshot_revision INTEGER NOT NULL,
  data TEXT NOT NULL,             -- JSON string
  hash TEXT NOT NULL,
  PRIMARY KEY (project_id, snapshot_revision)
);

CREATE TABLE IF NOT EXISTS project_metas (
  project_id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  latest_revision INTEGER NOT NULL DEFAULT 0,
  share_token TEXT,               -- 只读分享 token（可选）
  is_archived INTEGER NOT NULL DEFAULT 0
);
```

---

## 4. API 契约

### 4.1 端点（v1）

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/project/` | 创建项目，返回 `{ projectId, revision: 0 }` |
| GET | `/api/project/:id` | 获取当前状态（含 latest_revision, meta） |
| GET | `/api/project/:id/revision/:n` | 获取指定 revision 的状态（回放） |
| GET | `/api/project/:id/events` | 获取事件流（分页，`?from=&limit=`） |
| POST | `/api/project/:id/events` | 追加事件（body: `ProjectEvent`，无 hash 则服务端补） |
| POST | `/api/project/:id/events/append` | 便捷追加（body 只传 `{action, payload}`，服务端自动填元数据） |
| POST | `/api/project/:id/snapshot` | 强制打快照 |
| POST | `/api/project/:id/branch` | 从当前 revision 分叉新分支 |
| POST | `/api/project/:id/share` | 生成只读分享 token |
| GET | `/api/project/:id/share/:token` | 只读访问（无需鉴权，token 是自签 token） |
| PATCH | `/api/project/:id` | 修改 meta（title/description） |
| DELETE | `/api/project/:id` | 归档（软删，`is_archived=1`） |

### 4.2 冲突检测

**乐观并发**：客户端追加事件时必须在 header 里带 `X-Expected-Revision`。

```
POST /api/project/:id/events/append
X-Expected-Revision: 42
Body: { "action": "selection.add_part", "payload": { "entityId": "kuka_kr210" } }
```

服务端逻辑：
1. 读 `project_metas.latest_revision`
2. 若 `latest_revision !== X-Expected-Revision` → **409 Conflict**，返回 `{ currentRevision, expectedRevision, currentEvents: [recent 3 events] }` 让客户端可以合并
3. 否则追加新事件，返回 `{ projectId, revision: latest_revision + 1 }`

**冲突不静默覆盖** = 客户端必须显式决定：放弃、覆盖（force 参数）、还是合并。API 层不允许默认覆盖。

### 4.3 版本头

延续 `docs/api-versioning.md` 的版本化契约：

```
X-API-Version: v1
X-Data-Version: 2026-10-26    -- 与 CompositionState schema 版本挂钩
Cache-Control: no-store        -- 项目端点永远不缓存
```

### 4.4 错误码

| HTTP | 语义 |
|---|---|
| 201 | 事件追加成功 |
| 200 | 读取成功 |
| 400 | payload schema 校验失败 |
| 401 | 未鉴权（写操作必须带 `Authorization`） |
| 403 | 无写权限（只读 token 访问写端点） |
| 404 | 项目不存在（或已归档） |
| 409 | revision 冲突 |
| 422 | hash 链断裂（重放校验失败） |
| 429 | 速率限制 |
| 500 | 服务端错误 |

---

## 5. 冲突解决与 UX

审计明确要求"冲突不静默覆盖"。**默认行为是拒绝**，用户在客户端看到冲突后必须显式决定。

### 5.1 客户端冲突 UI（v1 最小可行）

```
⚠️ 项目已被他人修改（第 43 版 → 第 45 版）
冲突事件：
  44  by user-A  selection.add_part  { entityId: "kuka_kr210" }
  45  by user-B  selection.remove_part { entityId: "kuka_kr210" }

[放弃本次修改]  [合并（追加到 45 之后）]  [强制覆盖（清空 44-45，从 43 重走）]
```

**不允许**"自动覆盖"作为默认。用户必须点按钮。

### 5.2 冲突解决策略（AI/Agent 侧）

对 MCP 调用场景（P2-6 会用到）：Agent 拿到 409 后应该**停下来问用户**，而不是自作主张合并。这也是 P1-1 给 P2-6 埋的钩子——**任务句柄 = (projectId, revision) 对**，Agent 每次操作都带 revision。

---

## 6. 迁移路径

### 6.1 阶段划分

**阶段 1（MVP，5 天）**：只做 `/api/project/` + `/api/project/:id/events/append` + `/api/project/:id` 三个端点。D1 三张表建好，KV 用于快照。前端暂不改——只提供 REST 接口，让测试脚本可以先验证事件流正确性。

**阶段 2（Selection 接入，2 天）**：`selection.html` 接入 Project v2 API。用户点"保存"→ POST 一个 `project.create` + 所有 `selection.add_part` 事件。点"打开"→ GET 项目 → 重放事件。这是**唯一接入 Project v2 的页面**，作为金丝雀验证。

**阶段 3（其余 4 页接入，5 天）**：build-planner / designer / bom-checker / adapter-generator 依次接入。每接入一页跑一遍 E2E。**五页都接入后，用户"选件 → 规划 → 设计 → 检查 → 生成"五步可以跨页保存/恢复**——这是审计"打通真实任务闭环"的达成点。

**阶段 4（分享/分支/快照 UI，3 天）**：加只读分享、分支、手动快照按钮。用户可以在 `project.snapshot` 动作后得到一个里程碑 URL。

### 6.2 与 P0 兼容

**不修改**任何现有端点（`/api/search`、`/api/compat`、`/api/bom/*` 保持 stateless）。Project v2 是**新增**端点族，不替换。用户可以选择：
- 只查不建（当前行为，stateless）
- 建项目（v2 行为，事件流）

**两种模式共存**，无强制迁移。

### 6.3 弃用策略

Project v2 落地并稳定运行 30 天后，`bom-manager.html` 的 localStorage BOM 存储可以迁移到 Project v2。届时 `bom-manager` 的"BOM 表"就是一个 `compositionState.selection`。

---

## 7. 与后续 P1/P2 项的关系

| 项 | 依赖 Project v2 什么 |
|---|---|
| P1-2 Composition IR v1 | 从 `CompositionState` (§ 3.4) 演进 |
| P1-7 浏览器 E2E | 五步全链保存/恢复 是 E2E 的 20 条用例基础 |
| P2-1 Evidence Graph | 每条事件都可挂 evidence 引用，追溯原始来源 |
| P2-4 CIM Module Passport | 项目状态 → 模块护照的自然输入 |
| P2-6 MCP 任务句柄 | 任务句柄 = `{ projectId, revision }` 对 |
| P2-7 AG-UI 事件流工作台 | 事件流即 AG-UI 的核心数据流 |

**Project v2 不做的话，后面 6 项全部没有地基。**

---

## 8. 成本估算（诚实账）

| 项 | 成本 |
|---|---|
| Cloudflare D1（10 GB） | **$0**（免费额度内） |
| Cloudflare KV（1 GB 读/月） | **$0**（免费额度内） |
| Cloudflare Pages 部署 | **$0**（沿用现有） |
| 开发时间（10-15 天） | 人力成本 |

**运行成本 = $0**（免费额度内）。这是选 Cloudflare D1/KV 而不是 Postgres/Vercel 的直接原因——**项目当前商业验证阶段 29 调用 0 注册，运行成本必须为 0**。

---

## 9. 未决问题（等评审拍板）

1. **匿名项目怎么存？** Cloudflare KV 无账号体系，v1 用匿名 session ID 当 `actor`。等付费用户出现再上账号。**代价**：匿名项目无法跨设备恢复，只能同一浏览器同 session。
2. **是否限制项目数量？** 匿名项目可能泛滥。v1 不做限制，v2 用 Cloudflare R2 加配额。
3. **事件保留期？** v1 永久保留，除非用户 DELETE。等数据量到 100 MB 再谈归档策略。
4. **快照压缩？** v1 不压缩。等 snapshot 数量 > 500 再上 gzip。
5. **签名密钥管理？** 分享 token 用 HMAC-SHA256 自签，密钥放 `env.PROJECT_TOKEN_SECRET`。**需要用户从 env_contract.json 登记**（P0-4 部署指纹的契约纪律）。

---

## 10. 落地检查清单（评审通过后执行）

- [ ] 建 D1 数据库 `roboparts_projects`，导入 § 3.5 SQL
- [ ] 建 KV namespace `PROJECTS`
- [ ] 建 `functions/api/project/index.js`（POST 创建 + PATCH meta + DELETE 归档）
- [ ] 建 `functions/api/project/[id].js`（GET 状态/revision/events/branch/snapshot/share）
- [ ] 建 `functions/api/project/[id]/events/append.js`（POST 追加，冲突检测）
- [ ] 建 `functions/api/project/[id]/share/[token].js`（GET 只读）
- [ ] 更新 `env_contract.json`（新增 `PROJECT_TOKEN_SECRET`）
- [ ] 更新 `_routes.json`（`/api/project/*` 路由）
- [ ] 更新 `_headers`（版本头）
- [ ] 写 `scripts/verify_project_events.py`（事件流回放正确性测试）
- [ ] 建 CI 闸门 `gate_project_events_integrity`（hash 链完整性）
- [ ] 更新 `docs/api-versioning.md`（新增 v1 章节）
- [ ] 更新 `docs/mcp-tools.md`（如果 P2-6 加 project 相关工具，先占位）
- [ ] 阶段 1 完成后跑冒烟测试 + 部署
- [ ] 阶段 2 完成后 `selection.html` 接入 E2E

---

## 11. 一句话收束

Project v2 不是"给项目加保存按钮"——是把 RoboParts 从**只读零件库**升级为**可写、可回滚、可分享、可复算的组合工作台**。事件溯源是唯一同时满足审计四项验收的模型；Cloudflare D1+KV 是零运行成本的技术选型；分 4 阶段 15 天落地，每阶段都可以独立验收。**这份文档是评审材料，不是完工报告——实现需要用户拍板 § 9 未决问题后再动手。**
