# RoboParts 编排架构 (Agent Orchestration)

> 【GOAI 对齐 · P1】把 GOAI Agent Infra 赛道的 **AgentTeams（Manager–Team Leader–Worker 分层）+ AgentLoop（观测评估飞轮）** 映射到 RoboParts 现状，明确已对齐的部分与待补齐的环节。

## 一、当前架构（2026-08-25 快照）

```
  用户 / Agent / 目录站
        │
        ▼
 ┌─────────────────┐
 │ copilot.html    │  单入口 Copilot，Agnes AI 后端子代理推理
 │ (单 Agent)      │
 └──────┬──────────┘
        │
        ▼
 ┌─────────────────────────────────────────┐
 │ functions/mcp.js    (MCP Streamable HTTP) │
 │                                           │
 │  9 个只读 MCP 工具：                      │
 │   · search_components       L0 查询        │
 │   · get_component_detail    L0 查询        │
 │   · check_compatibility     L0 规则裁决    │
 │   · recommend_for_application L0 推荐      │
 │   · get_parameter_semantics L0 语义        │
 │   · bom_compatibility_check L0 BOM 矩阵   │
 │   · semantic_search         L0 语义召回    │
 │   · get_standard_audit      L0 审计        │
 │   · review_compatibility    L0 Governor    │  ← 新（J2+J3+J9）
 └──────┬──────────────────────┬──────────────┘
        │                      │
        ▼                      ▼
 ┌──────────────┐     ┌───────────────────┐
 │ compat_engine│     │ api/entities.json │
 │ (纯规则裁决) │     │ api/data.json     │
 │              │     │ api/*.json        │
 └──────────────┘     └───────────────────┘
```

**现状核心特征**：单 Agent + 9 个 MCP 只读工具 + 强数据纪律。已具备"可治理"雏形（数据层有 `evidence_tier`、`quarantine`、标准白名单），但缺"多 Agent 分层"和"评估飞轮"。

## 二、GOAI 框架映射

| GOAI 组件 | RoboParts 对应 | 成熟度 | 备注 |
|---|---|---|---|
| **Manager（编排层）** | 缺 | ❌ 待补 | copilot 现在直连工具，无任务分解 |
| **Team Leader（协调层）** | 缺 | ❌ 待补 | 可由 Governor 角色承担 |
| **Worker（执行层）** | `compat_engine.js` 的 `judgePair` / MCP 9 工具 | ✅ 成熟 | 单一真相源，规则裁决 |
| **Governor（审查层）** | `review_compatibility` 工具 | ✅ 新增 | 独立复核 judgePair 结论，强制证据≥2、降级不确定 |
| **AgentLoop（观测飞轮）** | `probe.mjs` + `verify_live_numbers.py` + OSS 摄取 + 数字保鲜三层 | ✅ 成熟 | 每日巡检 + 数字保鲜 + 内容指纹，等价于观测飞轮 |
| **AgentSpec Registry** | `skills/skills.meta.json` → `gen_skills_manifest.mjs` 自动导出 → `manifest.json` / `agent-discovery.json` / `.well-known/agent.json` | ✅ 领先多数参赛队 | 单一真相源，零漂移 |
| **评估集 / Golden** | 缺 | ❌ 待补 | 需 `api/eval/compatibility-golden.json` + `scripts/eval_compat.mjs` |
| **风险矩阵** | `docs/risk-matrix.md` L0–L3 | ✅ 新增 | 动作级风险分级 |
| **证据契约** | `judgePair` 的 `evidence_sources` / `evidence_count` / `evidence_strength` / `missing_evidence` | ✅ 新增 | ≥2 独立证据才给强结论；附"缺失证据段" |
| **Skill Guardrail** | `skills.meta.json` 每项的 `guardrails` | ✅ 新增 | 显式拒绝条件（不兼容、缺字段、证据<2 等） |

## 三、9 条工程判断落地映射

| # | GOAI 判断 | RoboParts 落地 | 位置 |
|---|---|---|---|
| J1 | Skill 有 Guardrail（拒绝条件） | 12 项 Skill 全有 `guardrails` 字段 | `skills/skills.meta.json` → 全部清单 |
| J2 | ≥2 独立证据才给结论 | `buildEvidenceBlock` 计算 evidence_sources/evidence_count，Governor 强制 ≥2 | `compat_engine.js` + `review_compatibility` |
| J3 | L0–L3 四档风险 | 风险矩阵 + 部署回滚锚点 | `docs/risk-matrix.md` + `scripts/deploy.mjs` |
| J4 | Mock 与真实共用 Schema | 数据层统一 JSON Schema，`data-rp` 锚点 | `data.js` + `_lib/` |
| J5 | Registry 而非内联 | AgentSpec Registry 自动生成 | `skills/skills.meta.json` |
| J6 | 报告有"缺失证据"段 | `missing_evidence` 字段 | `compat_engine.js` |
| J7 | 评估集 + 稳定性 + 幂等 | Golden/Badcase 集 + eval_compat 脚本 | `api/eval/compatibility-golden.json` + `scripts/eval_compat.mjs` |
| J8 | 可回滚性 > 自动化率 | deploy 前 git tag 回滚锚点 | `scripts/deploy.mjs` |
| J9 | 承认局限 | `evidence_tier` + `quarantine` + `overall=null` + Governor 降级 | 全站 |

## 四、待补齐的环节（P1 架构改造）

### 4.1 编排层 Manager

**目标**：把 copilot 从"单 Agent 直连工具"升级为"Manager–Worker 编排"。

**建议架构**：

```
copilot.html
    │
    ▼
┌────────────┐
│ Manager    │  解析用户需求 → 拆成子任务
│ (Agnes AI) │
└─────┬──────┘
      │
      ├──► Worker 1: check_compatibility / recommend / search
      ├──► Worker 2: adapter_gen (若需要生成转接件)
      ├──► Worker 3: supplier_risk (若需要供应商研判)
      └──► Governor: review_compatibility (复核所有 Worker 的兼容性结论)
              │
              ▼
         汇总 + 不确定项标注 → 返回用户
```

**关键点**：
- Manager 不直接裁决，只做任务分解与汇总
- Worker 分工明确（不共享上下文）
- Governor 强制复核，独立于裁决 Agent
- 参考 `~/.workbuddy/skills/agent-boost/SKILL.md` 的 Governor 模板

### 4.2 AgentSpec Registry 灰度/审计

**目标**：给 AgentSpec 加版本号 + 灰度开关 + 变更审计。

**步骤**：
1. `skills.meta.json` 每项加 `version` 字段
2. `gen_skills_manifest.mjs` 输出时携带版本号
3. 变更时写审计日志（`.workbuddy/memory/`）

### 4.3 AgentLoop 增强

**现状**：`probe.mjs` + `verify_live_numbers.py` + OSS 摄取已构成观测飞轮。

**待补**：
- 兼容性断言的持续验证（`eval_compat.mjs`）
- 评估集随数据集发布（ModelScope）

## 五、与相关文档的关系

- 风险矩阵：`docs/risk-matrix.md`
- 证据契约：`functions/_lib/compat_engine.js` 的 `buildEvidenceBlock`
- Governor 工具：`functions/mcp.js` 的 `review_compatibility`
- Skill 清单：`skills/manifest.json`
- 评估集：`api/eval/compatibility-golden.json`
- 5 分钟 Demo：`demo-flow.html`
- 供应商异常研判：`docs/supplier-risk.html`

## 六、诚实边界

本架构仍处"单 Agent + 强数据纪律"阶段。GOAI 评审看重"可治理、可观测、可进化"——RoboParts 在前两项已对齐，第三项（进化）需靠评估集 + 用户行为数据 + AgentLoop 反馈闭环，当前是真实短板（机械接口声明率 1.68%、无行为日志）。**不要假装已经多 Agent，如实标注架构层级与缺口**是 J9 的核心要求。
