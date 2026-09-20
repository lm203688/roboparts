# Tnkr 增量深拆（2026-09-20）—— 相对 `ecosystem-integration-tnkr-202609.md`（09-05）的新增事实与可执行动作

> 上一份结论仍成立：Tnkr 是构建协作平台（整机项目包：CAD/代码/数据/模型），
> 我们是兼容性真相层，二者互补。本文件**只记新增**——09-05 已覆盖的四支柱拆解、
> Manifesto 商业模式、Mods/Builds/PRs 协作机制、7 个数据源清单、"不做清单"均不重复。
>
> 本文件全部结论基于一手探测，未凭记忆推断。探测方法与结果见 §1。

---

## 1. 一手探测（2026-09-20 当日）

| 探测对象 | 方法 | 结果 |
|---|---|---|
| `https://api.tnkr.ai/` | WebFetch | **仍是占位页**：*"The API that powers the Tnkr platform. You've reached an API endpoint — there's nothing to browse here. The app lives at tnkr.ai"* + 状态灯 "All systems operational"。**无 `/openapi.json`、无 `/docs`、无可调用端点。** |
| `tnkr.ai` 首页 | WebSearch 抓取 | 产品文案已更新（见 §2） |
| ToddlerBot 项目页 | 搜索结果截图 | 页脚 **"Powered by TnkrAI"**；文档含 HARDWARE / SOFTWARE / Community 三栏，链接 Onshape + MakerWorld |
| Onshape 官网 | WebSearch | **FeatureScript MCP 已上架 App Store**（"Text → Code → CAD"）；新增 Altium ECAD↔MCAD 双向连接器 |

**关键推论（可验证）**：Tnkr **没有公开 API 面**。09-05 记录过这一点，本次复核未变。
⇒ 一切合作路径只能是 **PR / 社交 / 表单**，不能假设"给他们一个端点就能集成"。

---

## 2. 09-05 之后的新增事实（4 条）

### 2.1 官方文案已把"供应商对接"写成核心能力——但无零件数据层

首页 HARDWARE 区原话：

> "Create step-by-step assembly instructions, **manage Bill of Materials, and connect directly with parts suppliers**. Transform complex builds into reproducible blueprints."

09-05 的判断是"其 BOM 只是管理功能，无兼容性推理"。**本次更明确了：他们把"connect with parts suppliers"作为卖点写进了产品文案**，却没有支撑这一层的零件数据源。

⇒ 这正是我们的挂载面，且比 09-05 时暴露得更清楚。**缺口是他们文案承诺了但没建的那一层。**

### 2.2 影响指标全是占位符 ⇒ 平台自身未验证

首页 Impact Metrics 三项全部显示 `0% 0%`（更多真实数据 / 项目复现率 / 文档时间下降）。

⇒ 双面解读：
- **机会**：他们自己还没跑出数字，先给一个能算出真数字的兼容层，我们就是"第一个把指标算出来的人"；
- **风险**：依赖一个指标全是 0 的平台做分发，传播价值存疑。不要把 roadmap 建立在它身上。

### 2.3 ToddlerBot 是比 Open Duck Mini 更好的切入点

09-05 记录的最热项目是 Open Duck Mini V2（97★ / 5 builds / 3 PRs）。
本次发现 **ToddlerBot**（同系列人形）文档页脚标注 **"Powered by TnkrAI"**，文档结构完整
（Getting Started → Assembly Instructions → SOFTWARE → Community），且 BOM 侧栏可见
**"Bill of Materials / No materials added"** 状态。

⇒ 这是**可直接投 PR 的具体目标**：一个真实在用的 Tnkr 承载项目，BOM 栏位已存在，
只差内容。比"等 Tnkr 官方开放集成"快一个量级。

### 2.4 CAD 厂商在向 MCP 走（新信号，09-05 时不存在）

Onshape 官网首页现推 **FeatureScript MCP**（"The Fastest Path to AI-Driven Design. Text → Code → CAD"），
已上架 App Store；另有 Altium ECAD↔MCAD 双向连接器；REST API 覆盖 50+ apps。

⇒ 我们已经有 MCP server（1.1.1，10 工具，已上 npm/Glama/LobeHub）。
当 CAD 侧开始 MCP 化，**"CAD 出的几何 → 谁来判能不能装"就成了一个明确的空缺**。
我们正好在空缺的那一层。这是一条 09-05 时还不存在的通道。

---

## 3. 拿来用（Borrow）——按可落地性排序

| # | 借什么 | 我们现状 | 动作 |
|---|---|---|---|
| **B1** | **BOM 侧栏 + 3D 展开视图心智**（rotate / zoom / explode，官方文案"makes assembly come alive"） | 兼容性查看器尚未动工（three.js 法兰+转接盘 PoC 仍 pending） | 对齐该交互心智：双侧法兰并列 + 转接盘居中 + 可展开看螺栓孔。这是**已被验证的用户预期**，不必自创 |
| **B2** | **装配指令作为一等公民**（"Assembly Instructions Are a Programming Language"） | 转接盘的螺栓规格/扭矩/止口对位目前是散文 | 做成结构化字段（`assembly_steps[]`，每步含 `part_ref` / `tool` / `torque_nm` / `alignment`），实体卡里独立成区段。09-05 已提，**仍未做** |
| **B3** | **Mods 心智** | 适配器生成器本质就是"给不兼容零件打 Mod" | 文案与交互借其心智，把"生成转接盘"改述为"给这组零件加一个 Mod"。零成本，只改措辞 |
| **B4** | **数据回灌飞轮**（贡献者把运行数据喂回原作者） | 我们有贡献闭环设计（`contribution-loop-design.md`）但未落地 | 不必复刻其"运行数据"，复刻**机制**：贡献者提交 → 闸门审核 → 进真相源 → 署名。差别在于我们收的是**机械声明**不是遥测 |

**不建议照搬**：Leonardo（POV 视频→文档，宣称省 95%）。那是内容生成引擎，与我们的
数据裁决定位无关，且 95% 这个数本身未验证（指标全是 0%）。

---

## 4. 合作路径（Integrate）——按"成本/风险"排序

### P0 · 给 ToddlerBot 提一个 PR（最便宜，零账号风险）
- 目标：在 ToddlerBot 的硬件文档 BOM 区，加一条"兼容性核对"外链指向
  `roboparts.cc` 的实体卡或兼容裁决端点。
- 成本：一次 PR，无需登录 Tnkr（项目文档在公开仓库侧，Tnkr 只是承载层）。
- 验证价值：**如果 Tnkr 侧愿意合，说明"供应商/兼容层外链"这条路他们真会放行**。
  这是整个合作提案的最低成本验证点。
- 前提：我们的裁决端点得能判出至少一个 ToddlerBot 真实零件对。
  **这是当前真正的阻塞**——机械声明率 5.75%，多数判定会返回 `insufficient_data`。

### P1 · 做 200 行的兼容性徽章端点（唯一需要写代码的一项）
- `GET /api/compat-badge.json?from=<entity_id>&to=<entity_id>`
  → `{ "verdict": "adapter_required", "iso": "ISO 9409-1 A50", "adapter": {...}, "svg": "https://roboparts.cc/badge.svg?..." }`
- 为什么是徽章而不是完整 widget：Tnkr BOM 条目是静态文档，**一个外链 + 一张图就能被消费**，
  不需要 iframe、不需要账号、不需要 SDK。
- 这是 09-05 提过的"兼容检查徽章/iframe widget"，本次降级为纯静态版——
  因为 §1 已确认 Tnkr 无 API 面，做 iframe 没人调。

### P2 · 向 Tnkr 官方提"parts supplier"对接提案
- 依据：§2.1 他们官方文案承诺了 "connect directly with parts suppliers"。
- 通道：tally.so 邀请表单（09-05 已确认 beta 邀请制）。
- 提案内容三句：我们有 798 条零件实体的机械接口数据、ISO 9409-1 标号与兼容裁决、
  零集成成本的徽章端点。**不要提"API 集成"**——他们还没有 API。
- 风险：beta 期回复率低。低成本，值得发，但别等。

### P3 · MCP 通道（§2.4 的新机会，只做内容不做集成）
- Onshape FeatureScript MCP 已上架 ⇒ 写一篇文章：
  "用 Onshape 导出 PCD 标注 → RoboParts MCP 判兼容 → 生成转接盘"。
- 目的不是"被 Onshape 集成"，是**占住"CAD→兼容"这个搜索意图**（GEO 收益）。
- 成本：一篇文章。不写代码。

---

## 5. 阻塞（这一项比任何技术选择都重要）

**我们自己的 P0 没解，徽章端点判出 94% `insufficient_data` 会难看。**

机械声明率 5.75%（25/435），意味着 Tnkr BOM 里 100 个零件对，我们能判的不到 6 个。
一个对外挂着"95% 无法判定"的徽章端点，比没有徽章更伤——
它把"我们数据不够"这件事变成了**对方可见的负面证据**。

⇒ 顺序不能反：
1. 先解 P0（合法通道只有厂商 datasheet / ISO 9409-1 查表 / 用户提交；
   "开源 BOM 反喂"已证做不到位，见 `api/demand-signal.json` 的 `actionable_fixes`）；
2. 再挑 **1 个品类**做到 >50% 可答率（例如 actuators 217 条里挑谐波减速器，
   ISO 9409-1 A35/A50/A65/A100 四档是公开标准，可批量查表补 `A{n}`）；
3. 然后才做徽章端点 + 提 PR。

---

## 6. 不做清单（增量，09-05 的仍有效）

- **不做 VLA 模型部署**：Tnkr 已把 Models 支柱升级为"VLA models optimized for your
  specific hardware / deploy in clicks"，他们往 AI 行为走，我们往零件数据走，边界更清晰了。
- **不指望 API 集成**：`api.tnkr.ai` 2026-09-20 复核仍是占位页，无 OpenAPI 面。
- **不把 roadmap 建立在 Tnkr 上**：其 Impact Metrics 全为 `0%` 占位，平台自身未验证。
- **不做整机构建/混改/皮肤系统**（09-05 已定，Tnkr 层位）。

---

## 7. 一句话结论

> 09-05 说的"互补、衔接对象"没变，但**挂载点现在比当时清楚**：
> Tnkr 官方文案已承诺"connect directly with parts suppliers"，而它缺的正是零件数据层。
> 最便宜的真实验证是**给 ToddlerBot 提一个外链 PR**（P0）；
> 唯一需要写代码的是**一个 200 行的纯静态徽章端点**（P1）；
> 而**真正的阻塞是我们自己的 5.75%**——先在一个品类做到 >50% 可答率，
> 再谈对外挂载，否则挂出去的是"95% 无法判定"的负面证据。
