# 外部借鉴清单：7 个项目对 RoboParts 的处置（2026-09-19）

本轮对 pyroki / ego-mc-bench / connexus / modar / ericbuess / inverse kinematics / mecka
逐一联网核实出处，并给出处置。**已落地的只有 Tier 1 中的 pyroki（数据模型层）**，
其余为模式借鉴与观察项，登记在此避免丢失。

## Tier 1 · 已落地

### pyroki / inverse kinematics
- **出处**：PyRoki，UC Berkeley（Chung Min Kim, Brent Yi, Hongsuk Choi, Yi Ma,
  Ken Goldberg, Angjoo Kanazawa），MIT，IROS 2025，arXiv 2505.03728，1.4k★。
- **借鉴点**：URDF 优先的数据模型 —— 零件不带运动学元数据，任何 IK 判定都无从谈起。
- **落地**：见 `docs/kinematics-layer-20260919.md`（SoT + fail-closed 引擎 + 阴阳自测闸门）。
- **刻意不做**：搬 pyroki 本体。它是 Python + JAX，**跑不进 Cloudflare Workers**；
  真要完整 IK 只能旁挂 ECS 上的 Python 服务，边缘读预计算产物。

## Tier 2 · 模式与叙事借鉴（价值最高，但非代码）

### connexus（两个不同物，勿混）
1. `@agentic-conexus/mcp` / `@coderampart/conexus`：Go 写的「agentic context engine」MCP，
   语义 + BM25 混合检索、evidence-backed validation、`context_search` 等工具。
2. **RTI Connext MCP**：厂商把自家权威知识做成 MCP server 喂给 AI 编码 agent，
   实测 **快 17%、省约 66k token**（对比无 MCP 的 trial-and-error）。

**第 2 个是 RoboParts 的直接样板**：一家做中间件的公司，把「权威领域知识」封装成 MCP
给 agent 用。RoboParts 干的是同一件事（把零件与兼容判定做成权威知识喂 agent）。可抄两点：
- **量化收益做卖点**：做 A/B，证明装了 RoboParts MCP 的 agent 选型/建 BOM 更准更快。
  这是可对外讲的销售叙事，目前**尚缺**。
- **evidence-backed 输出**：它强调证据可追溯；我们已有「机械声明必须挂白名单出处」
  的纪律，应把它从内部纪律**升级为对外产品特性**去讲。

### ericbuess（分发打法）
- Eric Buess，Claude Code / MCP 社区个人开发者：`claude-code-docs`（文档镜像，≈947★）、
  `claude-code-project-index`、`limitless-ai-mcp-server`。
- **打法**：做「所有人都链接的 canonical 索引/镜像」。翻译过来 = 成为**人形零件索引 +
  ISO 9409-1 / 厂商 datasheet 的权威镜像源**。
- **注意**：这是个人不是项目，借的是**分发战术**，不是代码。

## Tier 3 · 战略相邻与情报（不做技术对接）

### mecka（Mecka AI）
- 2024 年成立，众包**自我中心（egocentric）人体动作数据**训练人形机器人；
  Framework 领投 $60M，传红杉领投 ~$500M 估值；`Egoverse` 开放数据集；
  自我定位「physical AI 的数据与部署层」。
- **关系**：他们收**动作数据**，我们收**零件数据**——同一条 physical AI 栈上的相邻层。
  真实价值在**商务层**（潜在合作/客户），不是技术接口。
- **可抄**：「开放数据集当名片」（我们已在做）。
- **⚠ 观察项**：相邻也可能反向侵入，纳入竞品观察。另：`mecka.com` 是无关的汽配电商 SaaS。

### modar（ModAR）
- CMU，Modality-Autoregressive World-Action 模型，30.1M 参数胜过 6B 视频模型；
  预测点轨迹 / DINO 特征 / 深度优于 RGB（arXiv 2609.17524）。
- **处置**：无集成。只作**前沿情报信号**——可用于推断「哪类零部件（深度相机、灵巧手等）
  会变热」，喂情报飞轮。

### ego-mc-bench（Ego-MC-Bench / Ego-CoMist）
- Qualcomm，厨房第一视角视频「即时纠错」基准，区分**预判式（anticipatory）**与
  **事后式（post-error）**反馈；SOTA 视频 LLM 干预 F1 仅 0.18（arXiv 2606.09547）。
- **处置**：无集成。只借其框法讲我们的兼容检查：
  **下单前预警（预判式）vs 装完才报错（事后式）**——是个可用的文案角度。

## 结论：能不能对接

**MCP 是开放协议 ⇒ 协议层天然可对接，不绑死任何平台。** 真正卡住的从来不是「接不接得上」：

| 卡点 | 实情 |
|---|---|
| pyroki | 要 Python 运行时，边缘跑不了 → 只能旁挂服务或离线预计算 |
| IK 判定 | 要 URDF 元数据（link_mm / 限位），当前**声明率不足** → 先补数据 |
| connexus | 是模式借鉴，不是代码依赖 |
| ericbuess | 是分发战术，不是项目 |
| mecka | 商务层，不是技术接口 |
| modar / ego-mc-bench | 无可对接接口，仅情报/文案 |
