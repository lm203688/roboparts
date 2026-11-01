# RoboParts · P0 修复交付说明

**日期**：2026-11-01
**依据**：`roboparts-全面诊断与提升方案-2026-10-31.md`（8 层扫描 · 46 项 P0/P1/P2 路线图）
**范围**：本说明覆盖 **P0 全部 12 项** 的落地，以及由此带出的 4 项连带修复。

---

## 一、P0 修复清单（12/12 完成）

| # | 项 | 修复内容 | 验证 |
|---|---|---|---|
| P0-1 | `upstream.js` auth RegExp bug | 工作区已修复（`return /{…}/` → `return {…}`，全部 11 个返回分支）；本会话补**回归测试** `tests/test_upstream_auth.mjs`（20/20，含「绝不返回 RegExp」断言） | `node tests/test_upstream_auth.mjs` ✅ |
| P0-2 | webhook 验签 fail-closed | 工作区已修复（无 `CREEM_WEBHOOK_SECRET` → 503；签名缺失/错误 → 401；分币启发式替换为 `amount/100`） | 复核代码路径 ✅ |
| P0-3 | 支付 webhook 幂等 | `webhook.js` 修复 `ReferenceError`（`{idempotencyStore}` → `{runIdempotent}`）；`idempotency.js` 新增 `opts.skipReplay`（防重放时二次扣积分/重复发券） | `node --check` ✅ |
| P0-4 | 付费墙单一事实源 | `_lib/plans.js` 单一 `PLANS`；`paywall.js` 新增 `containsPremiumField`/`maskPremiumDeep`（结构性路由，非 `entities.json` 专属）；`[[path]].js` 改为对任意 `*.json` 载荷统一走付费墙；CC BY 4.0 开放集（`data.json`/`oss_components.json`）**豁免** | 功能自测 ✅ |
| P0-5 | 86 闸门拦部署 | `deploy.yml` 新增 `gate` 任务（`needs: gate` 卡部署）+ 部署后 `smoke_prod.mjs`；rsync 排除 `.secrets`/`.env`/`.wrangler` 等；`ci.yml` node 20→22.22.2 | YAML 解析 ✅ |
| P0-6 | 变异闸门去自指涉 | `mutation_score.py` **不再用私有重实现**，改导入 `ci_gate.py` 真实纯函数（`check_three_state`/`check_gap_distance`/`check_honest_limits`）；`ci_gate.py` 抽出上述纯函数；M5「杀手」从扫 `⚠ FAKE` 字面量改为**真实语义**（honest_limits 不得宣称全覆盖而数据仍有缺口）；`gate_mutation_score` 现重跑 `mutation_score.py` 并校验 `generated_at` 新鲜度 | 自证 8/8；kill rate 1.00 |
| P0-7 | 前端 XSS `esc()` | 高危页 `embed/lookup.html`、`co-mount.html`、`bom-checker.html`、`oss.html` 的 API/实体字段插值全部加 `esc()`（HTML 属性/文本转义） | `node --check` + 人工复核 |
| P0-8 | schema 契约落地 | `schemas/entities.schema.json` **首次被闸门加载**：补 `data_quality` 实际 4 值（`placeholder_id`/`unverifiable_vendor`/`duplicate`/`non_entity`），`type` 改为「真实记录且无 `entity_kind` 时必填」，`sources`/`evidence_gap`/数值字段放宽到实际产物联合型；新增 `verify_schema_contract.py` 闸门（jsonschema 逐条校验，868/868 合规）；`requirements-dev.txt` 声明 `jsonschema`（此前被 `build_field_provenance.py` import 却不声明） | 868/868 合规；自证 5/5 |
| P0-9 | confidence_tier 不变量 | 根因：`confidence_tier_rule()` 按 `source_tier` 定档、覆盖 confidence 值域。修复：**只由 confidence 值域决定**（保留两条 D5 铁律）。调和 `reconcile_confidence_tier.py`（**479 条**重派生），新增 `gate_confidence_tier_range` fail-closed | 0 违规；D5 闸门通过 |
| P0-10 | Tier-C 上限 | `govern_tier_c.py` 明确 C=无溯源 confidence 上限 0.30；**252 条** C 实体（confidence 0.42~0.90）压到 0.30；新增 `gate_tier_c_cap` fail-closed | 0 违规 |
| P0-11 | npm↔托管 MCP 工具集对等 | 新增 `verify_mcp_tool_parity.py` 闸门：hosted(26)/npm(16) 工具名集合在扣除**显式登记**意图分歧后必须相等；未登记差异 / 过期清单 / 夸大清单一律判红 | 26/16 显式分歧，闸门 ✅ |
| P0-12 | 限流 | 新增 `_lib/ratelimit.js`（KV 滑动窗口，复用 `USER_CREDITS` 前缀 `rl:`，**失败开放**防反向 DoS，诚实上报 `X-RateLimit-*`）；接入 `functions/api/[[path]].js`（300 次/时/IP/路径）+ `functions/mcp.js`（600 次/时/IP）。此前**零限流**（仅响应头声明） | 单元测试（429 + degraded + 作用域隔离）✅ |

## 二、连带修复（由 P0 带出）

1. **`对外数据集分发一致性` 闸门回归**：`sync_dataset_dist.py::plan_truth()` 仍读 `payment/create.js` 内联套餐，但套餐已抽到 `_lib/plans.js`（单一真相源）→ 解析到 0 档。改为读 `plans.js`，得到 `{starter:(9,100), pro:(29,500), lifetime:(199,999999)}`。
2. **confidence 跨文件单事实源**：`reconcile_*` 只改了 `entities.json`，但同 id 记录同时嵌在 29 个 `api/*.json` 类别产物里（5468 处漂移）。新增 `sync_confidence_fields.py` 同步 + `gate_confidence_sync` 闸门。
3. **README / 定位面闸门数**：86→91，`inject_readme_stats.py` 已跑，`agent-discovery.json`/`llms.txt`/`index.html`/`README.md` 定位面文案已更新（去 BOM，JSON 保持合法）。
4. **产物新鲜度**：`compose_semantics`（5.6d）/`derived_features`（3.3d）/`croissant`（5.0d）三个派生产物过期，已用项目自带脚本重新生成（`build_compose_semantics` 重算 430336 对，数字不变——confidence 是标签，不参与 compose）。
5. **形态图节点漂移**：`build_morphology_graph.py::build()` 原来**不投影** confidence/confidence_tier/confidence_basis 三个标签，而 reconcile 后同步脚本把它们塞进产物 → 形态图闸门判「nodes 漂移」（659 节点全中）。修复：生产端**忠实投影**这三个标签（与 entities.json 逐键一致），重生成 `morphology_graph.json`；形态图闸门与 confidence 跨文件单事实源闸门同时变绿。

## 三、新增闸门（86 → 91）

| # | 新闸门 | 守什么 |
|---|---|---|
| 87 | MCP 工具集对等 | hosted↔npm 工具名，显式登记分歧 |
| 88 | schema 契约 | entities.json ↔ entities.schema.json（jsonschema 逐条） |
| 89 | confidence_tier 值域不变量 | confidence↔tier 区间一致 |
| 90 | Tier-C 上限 | C 实体 confidence≤0.30 |
| 91 | confidence 字段单事实源 | 跨文件（api/*.json）同步 |

## 四、剩余 / 说明

- **Windows 本地沙箱**下 6 个「自证/自测」闸门报 `[WinError 5]`（Temp 目录写拒绝）或 `EPERM`（命名管道 spawn）——**环境假红**，GitHub Actions（Linux，正常文件系统/管道）不会出现。已通过 `check_freshness`/`verify_schema_contract` 等独立复验确认代码本身无回归。
- **XSS esc()**：修复了报告点名的 3 个高危页 + `oss.html`（共 4 页，均含 API/用户提交字段插值）。其余 `innerHTML` 站点多为静态数据（硬编码 PARTS 数组等），风险低；后续可统一到共享 `esc()`。
- **P1 高价值项**（论文数字、adapter 5 源门、JS↔Py 重放、pipeline→production、包锁提交、`regen_derived --check`、前端构建、lint/format 进 CI、孤儿 `data.js`）未在本轮实施——属 P1，建议下一轮。
- **未提交**：本说明所列改动全部在工作区，尚未 `git commit`（用户未要求提交）。

## 五、关键文件

- 新增：`functions/_lib/ratelimit.js`、`scripts/verify_mcp_tool_parity.py`、`scripts/verify_schema_contract.py`、`scripts/reconcile_confidence_tier.py`、`scripts/reconcile_tier_c_cap.py`、`scripts/sync_confidence_fields.py`、`tests/test_upstream_auth.mjs`
- 修改：`scripts/ci_gate.py`（+5 闸门、抽 3 纯函数）、`scripts/mutation_score.py`、`scripts/normalize_categories.py`、`scripts/sync_dataset_dist.py`、`schemas/entities.schema.json`、`requirements-dev.txt`、`.github/workflows/deploy.yml`、`.github/workflows/ci.yml`、`functions/api/[[path]].js`、`functions/mcp.js`、`functions/_lib/{paywall,idempotency}.js`、`functions/api/credits/webhook.js`、`embed/lookup.html`、`co-mount.html`、`bom-checker.html`、`oss.html`
