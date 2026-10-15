# 板块 6：Agent 与 MCP 基础设施 — 提升评估报告

> **生成日期**：2026-10-14 ｜ **板块编号**：M6 ｜ **成熟度**：B 档（机制完整但未闭环）
> **证据来源**：`functions/mcp.js`（1814 行 / 21 工具）、`functions/a2a.js`（166 行）、`functions/api/copilot.js`（412 行）、`functions/api/discover.js`、`agent-discovery.json`、`.well-known/`（agent-card.json / agent.json / mcp.json）、`server.json`、`llms.txt`、`agenticros-skill-roboparts/`、页面 `copilot.html` / `agent-architecture.html` / `mcp-guide.html` / `geo-dashboard.html`

---

## 一、板块定位与边界

**一句话**：让 AI Agent 能「发现、接入、调用」RoboParts——把判定能力做成 Agent 可用的基础设施。

**四层协议面**：

| 面 | 资产 | 实测状态 |
|---|---|---|
| **MCP（hosted）** | `POST /mcp`（Streamable HTTP，协议版本 2025-06-18 / 2025-03-26 / 2024-11-05） | ✅ 线上 200；**21 个工具** |
| **MCP（stdio/npm）** | `server.json`（官方 schema）+ npm 包 | ⚠️ 见下 |
| **A2A** | `POST /a2a`（JSON-RPC 2.0，映射 `message/send` → MCP `tools/call`） | ✅ 已实现 |
| **发现清单** | `agent-discovery.json` / `.well-known/agent-card.json` / `.well-known/mcp.json` / `llms.txt` | ✅ 线上 200 |

**21 个 MCP 工具**：`check_compatibility` / `check_co_mount` / `bom_compatibility_check` / `search_components` / `semantic_search` / `get_component_detail` / `compare_components` / `recommend_for_application` / `review_compatibility` / `lint_urdf` / `get_research_progress` / `explain_compose_frontier` / `explain_evidence_mdv` / `explain_evidence_cohort` / `explain_connector_types` / `get_parameter_semantics` / `get_standard_audit` / `get_robot_tool_side` / `get_body_binding` / `get_behavior_evidence` / `keyword`

---

## 二、流程审计

### 2.1 流程是否合理

**这是全仓「自我诊断最诚实」的一个板块。** `mcp.js` 文件头完整记录了三次失败实验：

> 「连续三轮我们都在修『AI 找不到接入入口』……20:00 llms.txt 加指令 → `stat:src:agent = 0`；21:00 下沉到 18 个页面 → 仍 0；22:00 注入 meta.access 到 25 个 JSON → 仍 0。与此同时 `/api/*` 抓取占比 16% → 36.6% → 71.1%。」
> 结论：「**AI 大量地读我们，从不注册我们。**『位置』这条线已被三次实验证伪……瓶颈在入口本身要求的动作太重：领 key → 存 key → 装包 → 起进程 → 才能问第一个问题。」

| 设计决策 | 是否合理 | 证据 |
|---|---|---|
| 免鉴权只读托管端点 | ✅ 极合理 | 把用户侧成本从「装包+领 key+起进程」降到「粘贴一个 URL」 |
| 与 MCP 共用同一工具表 | ✅ 强 | `a2a.js` 从 `mcp.js` 导入 `TOOLS`，「避免两处各写一份工具名」 |
| A2A 不做自然语言意图解析 | ✅ 诚实 | 注释明确「那需要 LLM，本层不引入」；未给 tool 时返回能力清单，不猜意图 |
| 遥测与端点同生共死 | ✅ 合理 | 避免「指标看不见 = 以为没人用」 |
| copilot 多后端降级 | ✅ 合理 | ECS → Agnes → 结构化「维护中」，不再 504 挂死 |

> **判断**：流程**合理**，且是本项目「用实验否定假设」方法论的典范。

### 2.2 是否全面走通

| 子链路 | 状态 |
|---|---|
| Agent → `/mcp` → 工具 → 结果 | ✅ 通（线上 200） |
| Agent → `/a2a` → MCP 工具 | ✅ 通 |
| Agent → 发现清单 → 接入 | ✅ 通（清单齐全） |
| copilot 页面 → LLM 解释 | ✅ 通（依赖外部后端可用性） |
| **npm stdio 包** | ⚠️ 卡在「人工换发 Granular Token」——**别人的日程**（项目自述） |
| **Agent 真实调用量** | ❌ **无证据**：`demand-signal` 的 `cross_brand_compat_engine_users: 0` |
| **清单口径一致** | ⚠️ `agent-discovery.json` 已改为新定位（✅），但 tagline 仍写「**43 项 CI 闸门**」（实为 **49**） |

> **结论**：**接入面全部走通**（这是本项目做得最好的分发工程），但**「接入」不等于「被用」**——没有任何证据显示有 Agent 真实调用了这些工具。

### 2.3 是否符合人类使用习惯

本板块的用户是 **Agent**（不是人），所以「人类使用习惯」应读作「**Agent 使用习惯**」：

| Agent 的真实行为 | 本板块支持 | 契合度 |
|---|---|---|
| 「我先抓你的 JSON 自己猜」 | 71% 的 `/api/*` 抓取就是这行为 | ⚠️ 说明 Agent 宁可自己猜也不调工具 |
| 「粘贴 URL 就能用」 | ✅ 托管 MCP | ✅ 已解决 |
| 「按 A2A 委派」 | ✅ `/a2a` | ✅ 已解决 |
| 「从发现清单了解你能干什么」 | ✅ 清单齐全 | ✅ |
| 「工具返回的东西我要能直接用」 | ✅ 三态 + 证据链 | ✅ |
| **「我为什么要用你而不是自己猜」** | ❌ **未回答** | ❌ **核心缺口** |

> **关键缺口**：**没有回答「Agent 为什么该调用工具而不是自己猜」**。项目自己实测：Agent 大量抓 `/api/*` 自己猜。原因是「抓 JSON 自己猜」的成本**低于**「调工具」——哪怕工具已经零门槛。**这是本板块最深的战略问题。**

---

## 三、市场竞品与市场需求比较

### 3.1 竞品对照

| 竞品 | 定位 | 强项 | RoboParts 的差异 |
|---|---|---|---|
| **官方 MCP Registry** | MCP 服务器目录 | 官方分发 | RoboParts 已上架，但**目录本身不带来使用** |
| **Nacos 3.0 / Dify A2A 插件** | Agent 互操作基础设施 | 双向多智能体协作 | 基础设施层；RoboParts 是**垂直能力提供方** |
| **glama / Smithery** | MCP 市场 | 分发 | RoboParts 已提交，但**曝光 ≠ 使用** |
| **各机器人公司的 API** | 单厂能力 | 官方 | 不跨品牌 |
| **roboxdb** | 有 MCP 吗？ | — | 竞品是否提供 MCP 需核实 |

> **生态位**：RoboParts 的 MCP 面在「机器人零件判定」这个垂直领域**几乎没有对手**——但「没有对手」不等于「有需求」。

### 3.2 市场需求实测

- **本项目自己记录的三次实验全部为 0**：`stat:src:agent = 0`（连续三轮）。
- `demand-signal.json`：`cross_brand_compat_engine_users: 0`。
- `negative-results.md` 的 **NR-03「MCP 端点获客（被点开而非曝光）」状态：未达成**；**NR-04「npm 包发布作为 MCP 分发主渠道」状态：降级**。

> **判断**：**这是全仓最诚实也最残酷的一个板块**——项目已经把「接入门槛」降到接近零，但仍然没有人/Agent 用。**说明瓶颈不在接入层，在需求层。**

---

## 四、最新开源技术融合评估

| 开源技术 | 2026 状态 | 接入点 | 融合形态 | 拒绝条件 |
|---|---|---|---|---|
| **MCP Registry（官方）** | 2026 主流 | 已有清单 | 保持上架；补 MCP Registry 元数据 | — |
| **A2A 协议 v1.0** | 2026 主流 | `a2a.js` 已实现 | 保持；跟进 A2A 新版本 | — |
| **Agent Skills（Claude / Codex 生态）** | 2026 爆发（text-to-cad 8.3K star 即此形态） | `agenticros-skill-roboparts/` | **把「判定方法论」而非「查询」做成 skill** | skill 输出不得绕过 fail-closed |
| **RxDB 17 WebMCP** | 2026 新增 | 数据层 | 浏览器内 Agent 直连数据集合 | 不得绕过付费墙 |
| **MCP workflow-as-tool** | 2026 趋势 | 已有 21 工具 | 增加「流程型」工具（如 `plan_assembly`） | 不得另写判定逻辑 |
| **LLM-as-judge** | 2026 工程化 | `evaluation/promptfoo/` | 把 T1/T2/T3 定理做成 judge 评估面 | 不得替代确定性闸门 |
| **OpenAI Apps / ChatGPT Connectors** | 2026 新形态 | 已有 REST | 评估接入 OpenAI 应用目录 | 需评估生态依赖 |

> **首选融合**：**把「判定方法论」做成 Agent Skill**。当前 `agenticros-skill-roboparts/` 偏「怎么调工具」；2026 的趋势是 skill 承载**方法论**——本项目最有价值的正是「怎么诚实判定」这套方法论。

---

## 五、提升方案

### P0（不做则板块不成立）

| # | 动作 | 验收判据 |
|---|---|---|
| 1 | **回答「Agent 为什么该调工具而不是自己猜」**：在 `llms.txt` / `agent-discovery.json` 顶部给出「调工具 vs 自己猜」的明确对比（工具能给出**三态 + 证据链 + 可核验**，自己猜只能给「看起来对」） | 清单首屏含该对比；`stat:src:agent` 从 0 上升 |
| 2 | **修清单陈旧数字**：`agent-discovery.json` tagline 的「43 项 CI 闸门」改为现算值（49） | 挂闸门断言机器可读面数字与 `ci_gate.py --list` 一致 |
| 3 | **首次真实 Agent 调用留痕**：至少记录一次外部 Agent 的真实工具调用（非自检） | `ops/` 内有非自检调用记录 |

### P1（不做则板块无竞争力）

| # | 动作 | 验收判据 |
|---|---|---|
| 4 | 增加 workflow-as-tool（`plan_assembly`） | 工具可调，返回 BOM 判定 + 拓扑 + 缺口 |
| 5 | 把判定方法论做成 Agent Skill（不只「怎么调」） | skill 含方法论章节 |
| 6 | copilot 后端降级链可观测（当前 ECS→Agnes 静默） | 暴露实际使用的后端 |

### P2

| # | 动作 |
|---|---|
| 7 | 评估 OpenAI Apps / ChatGPT Connectors 接入 |
| 8 | MCP Registry 元数据补全 |

---

## 六、诚实边界

1. **本板块的接入工程做得极好，但零真实使用**——这是项目自己记录的三次实验结论（`stat:src:agent = 0`），本报告予以确认而非美化。
2. `npm stdio` 渠道卡在人工换发 token，属外部阻塞。
3. `copilot` 依赖外部 LLM 后端（ECS / Agnes），可用性不受本仓控制。
4. 竞品是否提供对等 MCP 面，未逐一实测。
