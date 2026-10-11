# RoboParts Agent 生态位地图（2026-10-08）

> **核心目标对齐**：RoboParts 是具身系统「组合」的形式化底座（脑 × 体 × 智），
> 一句话检验法是「让组合变得可校验」。本文档不追求完成度指标，只回答一个问题：
> **在 agent 生态的 6 层里，我们占据哪些位置，缺哪些，补齐的成本和优先级是什么。**

## 一、Agent 生态 6 层

Agent 生态不是「一个平台」，而是 6 个可组合的层。任何一层缺失，agent 都无法在
完整的调用链里被有效利用。

```
┌──────────────────────────────────────────────────────┐
│ L1 协议层        JSON-RPC 2.0 / MCP / A2A / A1        │
├──────────────────────────────────────────────────────┤
│ L2 发现层        官方 MCP Registry / Agent Card 索引   │
├──────────────────────────────────────────────────────┤
│ L3 上架层        Claude Connectors / OpenAI / Coze ... │
├──────────────────────────────────────────────────────┤
│ L4 编排层        LangChain / CrewAI / n8n / Agno      │
├──────────────────────────────────────────────────────┤
│ L5 评估/安全层    LangSmith / promptfoo / eval 集      │
├──────────────────────────────────────────────────────┤
│ L6 分发层        内容营销 / 竞赛 / GEO / 学术引用       │
└──────────────────────────────────────────────────────┘
```

## 二、RoboParts 现状盘点（按层）

### L1 协议层

| 协议 | 现状 | 位置 |
|---|---|---|
| MCP Streamable HTTP | ✅ 20 tools 在线 | `functions/mcp.js` → `https://roboparts.cc/mcp` |
| MCP stdio | ✅ npm 包可本地装 | `mcp-server/`（v1.1.1）|
| A2A JSON-RPC | ⚠️ 端点为 MCP（共享 JSON-RPC 2.0 底层） | `agent-card.json` 已声明 |
| A2A SendMessage 桥接 | ❌ 未上线 | 计划 v0.2 |
| A1（Anthropic 私有） | ❌ 未接入 | 无需（Anthropic 走 MCP）|

**判断**：L1 覆盖度 60%。A2A SendMessage 语义桥接是最大缺口——目前其他 agent 想按
A2A 语义委派任务给我们，只能通过 MCP `tools/call` 迂回。技术上可行但语义不符。

### L2 发现层

| 目录 | 状态 | 位置 |
|---|---|---|
| Official MCP Registry（MCP 项目官方）| ✅ 已发布 | `cc.roboparts/roboparts`（`.well-known/mcp.json`）|
| Smithery | ✅ 已上架 | `smithery.yaml` |
| Glama | ✅ 已上架 | `.well-known/glama.json` |
| LHM（Longhorn MCP Hub） | ✅ 已上架 | `lhm.plugin.json` |
| Agent Card（A2A v1.0） | ✅ **本次新增** | `.well-known/agent-card.json` |
| A2A 联合发现索引 | ❌ 未加入 | Linux Foundation 尚无聚合索引 |
| PulseMCP | ❌ 未上架 | 手动提交（5 分钟）|
| awesome-mcp-servers | ❌ 未收录 | GitHub PR |
| HuggingFace MCP Marketplace | ❌ 未上架 | 需 HF 账号 |

**判断**：L2 覆盖度 55%。MCP 目录侧基本齐全，A2A 目录侧刚起步。PulseMCP 和
awesome-mcp-servers 是免费、快速的上架机会，但收益是长尾曝光不是冷启动爆发。

### L3 上架层（大平台原生市场）

| 平台 | 状态 | 备注 |
|---|---|---|
| Anthropic Claude Connectors（官方审核）| ❌ 未上架 | 需开发者账号 + 人工审核 |
| OpenAI ChatGPT Apps / API MCP | ❌ 未上架 | 需 OpenAI 开发者账号 |
| Google Gemini Function Calling / Vertex AI | ❌ 未上架 | 需 Google Cloud 项目 |
| AWS Bedrock Marketplace | ❌ 未上架 | 需 AWS 账号 + 企业级审核 |
| Azure AI Foundry | ❌ 未上架 | 需 Azure 订阅 |
| Coze 商店 | ❌ 未上架 | 需国内手机号 + Coze 账号 |
| Dify 插件市场 | ❌ 未上架 | 开放 API 即可 |
| LangChain Hub | ❌ 未上架 | 免费开放 |
| Cursor Marketplace | ❌ 未上架 | 需 Cursor 开发者账号 |
| GitHub Marketplace | ❌ 未上架 | 需 GitHub Marketplace 授权 |

**判断**：L3 是最大缺口，也是收益潜力最大的层。RoboParts 作为数据/工具型 agent
恰好是这些平台的目标用户画像。但**每一次上架都需要用户账户**——AI 无法自主完成
任何一次上架动作。

### L4 编排层

| 框架 | 现状 | 位置 |
|---|---|---|
| LangChain / LangGraph | ❌ 未提供官方集成代码 | MCP 自动兼容 |
| CrewAI | ❌ 未提供官方集成代码 | MCP 自动兼容 |
| n8n | ❌ 未提供官方集成代码 | MCP 自动兼容 |
| Agno | ❌ 未提供官方集成代码 | MCP 自动兼容 |
| AutoGen | ❌ 未提供官方集成代码 | MCP 自动兼容 |

**判断**：L4 覆盖度 0%，但**技术上已被 MCP 覆盖**——所有主流框架都能直接连
`https://roboparts.cc/mcp`。真正缺的是一份「在 X 框架里 3 行代码接入」的示例文档，
这是 AI 可直接补齐的。

### L5 评估 / 安全层

| 工具 | 现状 | 位置 |
|---|---|---|
| LangSmith | ❌ 未接入 | 需 API Key |
| promptfoo | ❌ 未集成 | 可本地跑 |
| 内部评估集（compatibility-golden.json） | ⚠️ 规划中未落地 | `docs/agent-orchestration.md §4.2` |
| L0-L3 风险矩阵 | ✅ 已定义 | `docs/risk-matrix.md` |
| 反向注入验证（mutation tests） | ✅ 14 个 verify_l*_injections | `scripts/verify_l*_injections.*` |

**判断**：L5 是核心目标"可校验"的直接体现。反向注入是本仓最领先的实践（历史栽过
3 次假绿），Golden 评估集是下一个必须补的环。

### L6 分发层

| 渠道 | 现状 |
|---|---|
| GEO 博客（12 篇） | ✅ |
| 竞赛曝光 | ✅ 已备 AI Future Design 2026 资料 |
| 学术引用（CITATION.cff） | ✅ |
| arXiv / 论文 | ⚠️ compose-calculus outline 已有 |
| LinkedIn / X 品牌 | ❌ 用户无 X 账号 |

## 三、缺口分级：AI 直接可做 vs 用户配合

### ✅ AI 直接可补（无需用户配合，可在本次或后续迭代完成）

1. **L4 集成示例文档** —— LangChain / CrewAI / n8n / Agno 四份接入教程，每份 20 行代码
2. **L5 Golden 评估集** —— `api/eval/compatibility-golden.json` + `scripts/eval_compat.mjs`
3. **PulseMCP / awesome-mcp-servers 提交材料** —— 生成一份可直接提交的 PR/提交描述
4. **A2A SendMessage 桥接端点** —— `functions/a2a.js`，最小 50 行，把 MCP tools 包装成 A2A SendMessage

### ⚠️ 需要你配合（AI 无法自主完成，但步骤明确）

1. **Claude Connectors 上架**（最高优先级）
   - 需要：Anthropic 开发者账号（用 GitHub 登录即可）
   - 步骤：申请入口 → 提交 MCP endpoint → 通过 5-15 个工作日审核
   - 收益：Anthropic 官方审核徽章 + Claude 桌面端用户可见
   - 链接：https://claude.com/connectors（提交入口在开发者页）

2. **OpenAI ChatGPT Apps 上架**
   - 需要：OpenAI 开发者账号（免费）
   - 步骤：Apps SDK → 提交 MCP 端点 → 审核
   - 收益：ChatGPT 用户可通过 @RoboParts 直接调用
   - 链接：https://openai.com/developers/apps

3. **Coze 商店上架**
   - 需要：Coze 账号（手机号 + 实名）
   - 步骤：商店 → 上架插件 → 云侧插件基于已有 API 创建
   - 收益：国内流量入口
   - 链接：https://coze.cn/store

4. **HuggingFace MCP Marketplace 上架**
   - 需要：HuggingFace 账号
   - 步骤：hub → 新建 MCP Server Space → 提交
   - 收益：开源社区入口
   - 链接：https://huggingface.co/mcp

5. **GitHub Marketplace 上架**
   - 需要：GitHub Marketplace 开发者权限
   - 步骤：org → Marketplace → 提交 listing
   - 收益：开发者生态入口
   - 链接：https://github.com/marketplace

6. **PAT 权限补齐** —— 当前 PAT 缺 Workflows:write，无法编辑 workflow YAML
   - 需要：用户到 GitHub 生成新 PAT
   - 步骤：Settings → Developer settings → Personal access tokens → Fine-grained token
   - 权限：Contents:write + Workflows:write

## 四、与核心目标的对齐判断

| 生态位补齐项 | 对"让组合变得可校验"的贡献 | 对"链路可溯源"的贡献 |
|---|---|---|
| A2A Agent Card（本次已做）| ⚪ 中立（可发现性，不改变校验能力）| ⚪ 中立 |
| Claude / OpenAI / Coze 上架 | ⚪ 中立 | ⚪ 中立 |
| Golden 评估集 | ✅ 直接推进 | ✅ 直接推进 |
| 反向注入验证（已有）| ✅✅ 已领先 | ✅ 直接推进 |
| 反向注入 + 评估集合并闸门 | ✅✅ 组合判定的最终保障 | ✅✅ |

**关键判断**：agent 生态上架**不推高完成度指标**，但它们**放大核心目标的可见性**。
一个 agent 生态位完整的数据层，比一个孤立的数据层更容易被下游 agent 调用、被下游
agent 验证、被下游 agent 溯源。这就是"链路可溯源"的延伸——不是我们内部可溯源，
而是**从任意外部 agent 出发都能溯源到我们**。

## 五、执行顺序建议

按"AI 可执行成本 / 用户收益比"排序：

1. **本次已落地**：A2A Agent Card（0 用户成本，AI 直接可维护）
2. **下一步（AI 直接做）**：LangChain / CrewAI / n8n / Agno 接入教程
3. **再下一步（AI 直接做）**：Golden 评估集 + promptfoo 集成
4. **用户配合 P0**：Claude Connectors 上架（收益最大）
5. **用户配合 P1**：Coze 商店上架（国内入口）
6. **用户配合 P2**：GitHub Marketplace 上架
7. **用户配合 P2**：PAT 权限补齐（解锁 CI 编辑权限）

## 六、边界与诚实

- 本文档**不修改**任何数据层字段、不修改 `api/research_progress.json` 的完成度指标
- A2A SendMessage 桥接端点未上线，`agent-card.json` 里如实标注（不谎报能力）
- Claude Connectors 等上架动作需人工审核，AI 无法代为完成
- MCP Registry 官方审核（若尚未通过）是本次上架的关键前置

参考：
- A2A v1.0 规范：https://a2acn.com/ 或 https://a2a-protocol.org/
- MCP Registry：https://registry.modelcontextprotocol.io/
- Agent Card 示例：https://specification.website/spec/agent-readiness/a2a-agent-cards
