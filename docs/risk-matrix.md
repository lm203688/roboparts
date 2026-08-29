# RoboParts 动作风险矩阵 (Risk Matrix)

> 【GOAI 对齐 · J3】把"风险二档"升级为 L0–L3 四档，让每个动作带明确的风险级、审批门槛与回滚路径。
> 来源：GOAI Agent Infra 赛道参赛作品复盘《一个多 Agent 零人工运维系统的设计复盘》第 3 条工程判断。

## 风险分级定义

| 级别 | 名称 | 可逆性 | 审批门槛 | 执行方式 |
|---|---|---|---|---|
| **L0** | 只读 / 查询 | 天然可逆 | 无需审批 | 任意 Agent/人可直接执行 |
| **L1** | 生成 / 可回滚 | 有快照或 git tag 可回滚 | 无需审批，但必须记录产物指纹 | Agent 可执行，产物需可回滚 |
| **L2** | 外部写入 / 影响线上 | 部分可回滚 | 人工审核（关键动作） | Agent 出方案，人确认后执行 |
| **L3** | 不可逆 / 外部公告 | 难以回滚 | 双人复核 | 只出方案，不自动执行 |

## RoboParts 动作映射

| 级别 | RoboParts 真实动作 | 现有保护 | 缺口 |
|---|---|---|---|
| L0 | 所有 MCP 只读工具（`search_components` / `get_component_detail` / `check_compatibility` / `recommend_for_application` / `get_parameter_semantics` / `bom_compatibility_check` / `semantic_search` / `get_standard_audit` / `review_compatibility`）；`/api/entities.json` / `/api/data.json` 读取 | 无认证但只读；`X-RoboParts-Selftest` 隔离头区分自测与真实调用 | 长期可能需限流 + API Key 归因（非强制鉴权） |
| L0 | 每日站点巡检（`probe.mjs`） | 隔离头 + 幂等 + 三态校验 | 已成熟 |
| L1 | `adapter-generator` 生成转接件 STL；`scripts/gen_adapter.py` | 只产出本地 STL，不自动提交 | 建议加产品物指纹记录 |
| L1 | `scripts/gen_skills_manifest.mjs` 重生成清单 | 幂等；`verify_skills_manifest.mjs` 校验；阳性对照 | 已成熟 |
| L1 | 数字保鲜注入（`inject_onboarding.py` / `inject_api_access.py`） | L1.55 幂等（"先剥离再写入"） | 已成熟 |
| L2 | `scripts/deploy.mjs` 部署到 Cloudflare Pages | L1.76 边缘 404 闸 + 内容指纹 + 头部注入器 + 5 次退避校验 + **git tag 回滚锚点（J8）** | 无灰度/蓝绿；建议后续加 |
| L2 | `scripts/ingest_oss.mjs` 摄取 OSS 数据 | 缩水 >10% 拒写 | 无逐条差异回放 |
| L2 | `scripts/govern_standard_conformance.py` 标准登记 | 白名单 + 证据锚点 | 已成熟 |
| L3 | 对外公告 / 数据集更新（ModelScope 发布） | 已发布版本不可撤（可重发） | 需双人复核文案 |
| L3 | 支付 / 积分发放 | 虎皮椒 + 账本审计 | 需对账/退款流程 |

## 执行原则（来自 J3 + J8）

1. **可回滚性 > 自动化率**：宁可慢一档，也要保证失败可回退。deploy 前必须打 git tag。
2. **风险随数据增长而升级**：某动作若处理的"高置信度数据"占比 <60%，应视同 L1 而非 L0（避免用低质数据自动决策）。
3. **L2 不自动**：任何写入外部状态的脚本（deploy / ingest / 支付回调）必须由 Agent 出方案 + 人确认执行。
4. **L3 只出方案**：对外公告、数据发布、退款——只产出建议与草案，不执行。

## 与相关文档的关系

- 证据契约：`functions/_lib/compat_engine.js` 的 `buildEvidenceBlock` / `judgePair`（J2 + J6）
- Governor 复核：`functions/mcp.js` 的 `review_compatibility` 工具（P1 + J9）
- 编排架构：`docs/agent-orchestration.md`
- Skill Guardrail：`skills/skills.meta.json` 中每项的 `guardrails` 字段（J1）
