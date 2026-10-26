# RoboParts MCP 工具文档

**端点：** `https://roboparts.cc/mcp`
**协议：** MCP（Model Context Protocol），stdio 与 streamable HTTP 均支持
**鉴权：** 只读、免鉴权
**当前工具数：** 26（11 业务 + 9 桥接 + 6 双版本/Trace 层，v1.2.0 新增）

> **本文档由 `functions/mcp.js` 的 TOOLS 定义生成对应。**
> 任何工具新增、改名或参数变更，都必须同步：
> ① `functions/mcp.js` TOOLS 数组 ② `mcp-server/index.js` TOOLS 数组
> ③ `scripts/read_metrics.py` 的 `BUSINESS_TOOLS` 元组
> ④ `agent-architecture.html` / `agent-discovery.json`
> ⑤ 本文件。闸门 G-L1.19 会交叉核对，漏一处即红灯。

---

## 使用方式

### 远程接入（推荐，零安装）

```json
{
  "mcpServers": {
    "roboparts": { "url": "https://roboparts.cc/mcp" }
  }
}
```

### Claude Desktop（经桥接）

```bash
npx -y mcp-remote https://roboparts.cc/mcp
```

### 从源码运行（离线/二次开发）

```bash
git clone https://github.com/lm203688/roboparts.git
cd roboparts/mcp-server && node index.js
```

> ⚠️ 本地 `mcp-server/index.js` 是子集（10 个工具），完整 20 个工具在生产 `functions/mcp.js`。
> 需要桥接层工具（`explain_*` / `check_co_mount` / 等）请走远程端点。

---

## 一、业务工具（11 个）

面向工程师与 Agent 直接查询实体、判定兼容性、导出交付物。

### 1. `search_components` — 搜索零部件

```json
{
  "category": "actuators",       // 可选：ALL_CATEGORIES 之一
  "keyword": "DYNAMIXEL",         // 可选：匹配 name/manufacturer/type/desc
  "limit": 10                     // 可选：默认 10
}
```

返回：`[{id, name, category, manufacturer, key_specs}, ...]`

> `category` 枚举由 `ALL_CATEGORIES` 现算，随新增品类自动扩展。

### 2. `get_component_detail` — 单条详情

```json
{ "id": "ACT-001", "category": "actuators" }
```

返回：完整实体对象（含 `mechanical_interface` / `electrical_interface` / `evidence` 等）。

### 3. `check_compatibility` — 两两四维裁决

```json
{
  "component1_id": "ACT-001",
  "component1_category": "actuators",
  "component2_id": "CHIP-001",
  "component2_category": "chips"
}
```

判定维度：`protocol` / `electrical` / `mechanical` / `software`。
返回 `{compatible, reasons[], warnings[], verdict_reason}`。
`verdict_reason=null` 表示**证据不足**，不等于不兼容。

### 4. `compare_components` — 并排对比（2–6 个）

```json
{ "ids": ["ACT-001", "ACT-002", "ACT-028"] }
```

返回：规格键并集表；相同值自动标注，替代为同一目的连发多次 `get_component_detail`。

### 5. `recommend_for_application` — 应用推荐

```json
{
  "application": "humanoid",      // humanoid/quadruped/robot_arm/amr/industrial
  "budget": 50000,                // 可选：CNY
  "count": 3                       // 可选：每类推荐数，默认 3
}
```

返回：`{actuators, sensors, chips, controllers}` 各 top-N。

### 6. `get_parameter_semantics` — 参数口径规范

无参。返回：torque/speed 等字段的**厂商口径差异表**（库内 torque 19 种、speed 37 种）、物理红线、单位换算、可比性分级。

**用途：** 判断两份参数表能不能直接比较。**在按参数做选型决策前必须先查这个。**

### 7. `bom_compatibility_check` — BOM 两两矩阵

```json
{ "component_ids": ["ACT-001", "SENS-001", "PROTO-012"] }
```

返回：n×n 四维判定矩阵；`verdict_reason=null` = 证据不足，**不会为了填满矩阵编造结论**。

### 8. `semantic_search` — 语义召回

```json
{ "query": "六维力传感器 防水", "k": 5 }   // k 取值 1-30
```

索引由**离线哈希 TF-IDF** 生成（构建时预计算、零外发、零外部模型）。索引不可用时自动降级为关键词并明确告知。

### 9. `get_standard_audit` — 标准交叉校验

```json
{ "scope": "all" }   // 或 "conflicts"（仅数据质量冲突）
```

返回：标准登记表 ↔ 实体声明的自动交叉校验。**这是数据质量自检，不是兼容性裁决。**

### 10. `review_compatibility` — 多 Agent 质保复核

```json
{ "component1_id": "ACT-001", "component2_id": "CHIP-001" }
```

Worker 层做标准四维裁决 + Governor 层独立复核。证据不足 2 条时把"兼容"降级为"需人工确认"。返回四维细节 + 证据契约 + `governor_review`（含 L0-L3 风险分级）。

### 11. `lint_urdf` — URDF 静态检查

```json
{
  "urdf_xml": "<?xml ...?><robot>...</robot>",
  "check_level": "all"   // all / errors_only / warnings_and_errors
}
```

检查 10 类问题：XML 解析、根 link、关节限位、关节类型、重复 link、运动学循环、ROS 帧（flange/tool0/base）、origin、inertial、mesh 路径。最大 512KB。

---

## 二、桥接层工具（9 个）

**只读、免鉴权**，把**研究层**（`compose_engine.py` 三轴：mechanical/electrical/signal）的产物对 Agent 暴露。**注意口径差异**：桥接层返回带 `caliber` 字段，**不可**与业务层的四维结论混用。

### 12. `explain_compose_frontier` — 三轴组合裁决

```json
{ "component1_id": "ACT-028", "component2_id": "SENS-047" }   // 均省略 = 库级概览
```

返回：`composed` / `type_error` / `unknown` 计数、逐轴裁决与理由、`composed=0` 的三层归因（L1 跨角色 → L2 机械可判定 → L3 全轴可判定）。

**注意口径：** 桥接层用 `signal` 角色互补（执行器↔传感器），`check_compatibility` 用 `protocol` 总线 + ROS2 支持。

### 13. `explain_evidence_cohort` — MVC 取证判据

无参。返回：最小可行同质集判据、单条声明零收益定理、按缺口画像批量取证顺序。回答"取证该从哪开始"。

### 14. `explain_evidence_mdv` — 边际声明价值

无参。返回：各轴未声明节点的零贡献率、瓶颈轴识别、哪些方向边际收益恒为 0。回答"补哪个轴最划算"。

### 15. `explain_connector_types` — 连接器取证

无参。返回：已核实的连接器（针数/针序/供电）、同族不同变体的不可互插案例、`(family, pins, pinout)` 三元组判据。回答"同为 M8 为什么判不兼容"、"pinout 为 null 是什么意思"。

### 16. `get_research_progress` — 核心目标完成度

无参。返回：4 维分解（体/脑/智/链）的分子/分母/口径/缺口、门控与朴素两个加权口径。

> **口径警告**：这是**一个口径**下的数字，权重可争议。采用门控口径：核心判据 `composed=0` 时 body 维记 0。

### 17. `check_co_mount` — 共装关系（第三种关系类型）

```json
{ "host": "HUB-031", "a": "ACT-028", "b": "SENS-047" }   // 三段裁决
{ "host": "HUB-031" }                                        // 单件可装性
{}                                                          // 全层摘要
```

判"这台 UR5e 能不能**同时**装夹爪和六轴力传感器"。三段判据：机械同型 + 宿主工具侧位数预算 + 信号角色互补。

**关键区分：**
- `port_exhausted` = **装不下**（工程约束，需转接/换本体）
- `unknown` = 数据不足（不是装不下，是不知道）

### 18. `get_robot_tool_side` — 工具侧接口取证

无参。返回：机器人本体的工具法兰（ISO 9409-1）、工具 I/O 位数、连接器型号与承载信号。

`tool_io_ports` 是**一手取证的整数位计数**（不是针数）；未取证者留 `null`，判据据此走 `unknown`，**不按型号名推断**。

### 19. `get_behavior_evidence` — 行为证据（VLA benchmark）

无参。返回：开源 VLA 在**真机**上的 benchmark 成功率（引用论文/官方报告）。

三条纪律：
1. 仿真（`sim`）与真机（`real`）**严格分列**，不可合并统计
2. 只收录**有对照组**的数字（孤证可能是 cherry-pick）
3. 官方未报告的指标 `value=null`，不折算

### 20. `get_body_binding` — VLA → 本体绑定强度

无参。返回：开源 VLA → 机器人本体的绑定及其强度分档。

四档强度：
- `validated`：论文明写真机评测跑在该本体
- `family`：论文列该族
- `adaptable`：官方称可微调，非特定硬件验证
- `category_only`：只登记类别

两个**非绑定态**：`blocked_missing_body`（本体不在库内）、`category_only`。

**只绑开源 VLA**——闭源模型无公开验证栈，不编造绑定。

---

## 三、口径分层（关键纪律）

RoboParts 内部有**两套兼容性裁决引擎**，MCP 工具按层暴露：

| 层 | 引擎 | 维度 | 工具 |
|---|---|---|---|
| **产品面** | `functions/_lib/compat_engine.js` | protocol / electrical / mechanical / software（4 维） | 1–11 |
| **研究层** | `scripts/compose_engine.py` | mechanical / electrical / signal（3 轴） | 12–20 |

两套维度**不互为子集**（产品层有 protocol/software，研究层有 signal）。
返回结果都带 `caliber` 字段标明来源层，**跨层合并是产品决策，不是工具职责**。

---

## 四、三态诚实纪律

所有工具**遵循相同的诚实纪律**：

1. **证据不足返回 `null` + 显式 `reason`**，不猜。
2. **不为了填满矩阵编造结论**（`bom_compatibility_check`）。
3. **仿真与真机严格分列**（`get_behavior_evidence`）。
4. **口径差异不隐藏**（`caliber` 字段 + 文档明示）。
5. **权重可争议**（`get_research_progress` 报门控与朴素两个口径）。

---

## 五、常见组合用法

### 场景 A：为参考任务做选型

```
search_components  →  get_component_detail  →  check_compatibility
       ↓                                        ↓
    compare_components                 review_compatibility（加质保复核）
       ↓                                        ↓
recommend_for_application            preflight_check（BOM 前守门人）
```

### 场景 B：Agent 工具循环里的守门人

```
任何 BOM 生成 → preflight_check → 通过？→ 出单 / 拦截 ill_typed
```

### 场景 C：解释 composed=0

```
explain_compose_frontier（看整体）
   → explain_evidence_mdv（哪个轴是瓶颈）
   → explain_evidence_cohort（先补哪一类）
   → explain_connector_types（具体到连接器）
```

---

## 六、变更历史

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-10-04 | +5 桥接层 | `explain_compose_frontier` / `explain_evidence_cohort` / `explain_evidence_mdv` / `explain_connector_types` / `get_research_progress` |
| 2026-10-15 | Phase A·A4 | +2 装配级：`plan_assembly` / `preflight_check` |
| 2026-10-19 | +1 桥接 | `check_co_mount`（共装关系） |
| 2026-10-26 | 桥接层扩展 | +3 桥接：`get_robot_tool_side` / `get_behavior_evidence` / `get_body_binding`；文档首次全量撰写 |
| **2026-10-27** | **v1.2.0 · MCP 双版本 + Trace 回放** | **+6 工具**：`explain_unknown` / `start_long_task` / `get_task_status` / `cancel_task` / `trace_export` / `trace_replay`；Server 声明 `2024-11-05` / `2025-03-26` / `2025-11-25` 三版本协商；每次调用自动注入 `trace_id` + `evidence_version` |

---

## 三·五、双版本 / Trace 层（6 个 · v1.2.0 新增）

审计报告 §4.4 明确点名：「MCP 要做双版本适配与可回放任务……工具输入输出全部引用
project_id + revision + evidence_version；长任务返回任务句柄、进度、可取消状态和
最终结果；把'为什么 unknown''哪条证据导致冲突'作为标准工具，而非仅靠自然语言解释；
为每次外部 Agent 调用保存可去敏回放的评估轨迹」。本节对应落地。

### 21. `explain_unknown` — 结构化解释「为什么 unknown」

```json
{
  "component_id": "ACT-001",      // 与 verdict_id 二选一
  "category": "actuators",        // 给 component_id 时必填
  "verdict_id": "v_abc",          // 反查当前会话内的 verdict
  "max_gaps": 20                  // 可选：默认 20，上限 100
}
```

三种模式（互斥）：

- **`component_id` 模式**：返回该实体的 `evidence_gaps` / `gap_cause` / `null_or_unknown_fields` / `gap_count`。**字段级扫描**，非因果归因（后者属 `gap_classification` 研究层）。
- **`verdict_id` 反查模式**：仅查当前 stdio 会话的 trace 环形缓冲；跨会话请先 `trace_export` 落盘后 `trace_replay`。
- **无参降级模式**：返回全库 `total_entities` / `null_or_unknown_rate` / `evidence_gap_rate` / 按品类拆解。

**口径纪律**：字段级 vs 因果级是两个维度，不能混用（详见 §四 三态诚实纪律第 1 条）。

### 22. `start_long_task` — 启动长任务

```json
{
  "task_type": "batch_check_compatibility",
  "args": {
    "pairs": [
      { "component1_id": "ACT-001", "component1_category": "actuators",
        "component2_id": "CHIP-001", "component2_category": "chips" }
    ]
  }
}
```

`task_type` 三选一：`batch_check_compatibility` / `bulk_export_bom` / `deep_dialect_evaluate`。

**立即返回**：`{ task_id, status: "running", name }`。任务体异步执行，客户端通过
`get_task_status` 轮询。

**诚实边界**：stdio 无中断通道，`cancel_task` 只置标志位；任务体在下一个 checkpoint
调用 `task._checkCancel()` 时才会退出。

### 23. `get_task_status` — 查询任务

```json
{ "task_id": "tsk_..." }
```

返回 `{ status, progress, result, error, cancelled, ts, duration_ms }`。
环形缓冲 200 条上限，最老任务被淘汰（返回 `task_not_found`）。

### 24. `cancel_task` — 取消任务

```json
{ "task_id": "tsk_..." }
```

对已结束（`done` / `failed` / `cancelled`）任务返回 `task_already_<status>`。
对 `queued` / `running` 任务置 `cancelled=true`。

### 25. `trace_export` — 导出轨迹

```json
{
  "limit": 200,                   // 默认 200，上限 1000（环形缓冲容量）
  "tool": "check_compatibility",  // 按工具名过滤
  "since": "2026-10-27T00:00:00Z",// ISO 8601 起点
  "redact": true                   // 默认 true
}
```

**去敏规则**（`redact=true` 时）：

- 字符串 → `{ type: "string", length, hash8 }`（不透传原值）
- 对象 → `{ type: "object", keys: [...] }`（只留键名，防 API key / 邮箱泄漏）
- 数组 → `{ type: "array", length, sample_types }`
- 敏感字段名（`api_key` / `token` / `password` / `secret` / `email` / `authorization` / `cookie` / `session_id`）→ `<redacted>`

**服务端无持久化**：默认只回当前 stdio 会话。可选：设置环境变量
`ROBOPARTS_TRACE_FILE=/path/to/trace.jsonl`，每次调用会 appendFileSync 落盘。

### 26. `trace_replay` — 从 JSONL 重放

```json
{
  "json_lines": ["{...}", "{...}"],
  "strict": false                 // 默认 false，首个 parse 失败即中断
}
```

返回 `{ replayed, total_lines, errors, error_detail, unique_tools, unique_traces }`。

**只验证「记录可解析、字段完整」**（`trace_id` / `tool` / `ts` 至少齐全），
**不重算 verdict**——语义重放需要完整输入重演，属于 P3 范畴（跨会话、带 diff）。

### 协议版本协商

Server 在 `initialize` 响应里通过 `capabilities.experimental.roboparts` 显式暴露：

```json
{
  "protocol_versions_supported": ["2024-11-05", "2025-03-26", "2025-11-25"],
  "capabilities_by_version": {
    "2024-11-05": [ /* 基础 10 个工具 */ ],
    "2025-11-25": [ /* 6 个新工具 */ ]
  },
  "evidence_version": "1.2.0",
  "honest_limits": [
    "no_server_side_persistence",
    "no_hard_cancel",
    "no_multi_tenant_isolation"
  ]
}
```

SDK 会自动在 `initialize` 请求/响应里协商到共同 `protocolVersion`；本 server
额外暴露 `protocol_versions_supported` 数组，让新客户端能程序化判断可用性
（而不是靠猜 SDK 实现）。

**evidence_version 注入**：每次工具调用返回都挂 `trace_id` 和 `evidence_version`
（= 包版本），让调用方可以引用某个数据快照做对账。

### 三层能力对照

| 层 | 引擎 | 维度 | 工具 |
|---|---|---|---|
| **产品面** | `functions/_lib/compat_engine.js` | protocol / electrical / mechanical / software（4 维） | 1–11 |
| **研究层** | `scripts/compose_engine.py` | mechanical / electrical / signal（3 轴） | 12–20 |
| **双版本 / Trace 层** | `mcp-server/trace.js` | 元能力（协议协商 + 轨迹 + 长任务） | 21–26 |

Trace 层与兼容性判定**正交**：不改变任何 verdict，只提供"这次判定是怎么来的、
能不能事后回放"的元信息层。跨层合并是产品决策，不是工具职责（沿用 §四 第 4 条）。
