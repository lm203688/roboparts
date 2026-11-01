# RoboParts 全面诊断与提升方案

> 扫描范围：`C:\Users\xing\Desktop\robopart`（全部 624 提交 / 868 实体 / 42 根页面 + 22 篇文章 / 288 个脚本 / 1009 个 ops 文件 / 86 项 CI 闸门 / MCP 服务 / Agent 技能包 / 学术论文）
> 方法：8 路并行深度扫描（数据层 / 管线与闸门 / 后端与 MCP / 前端与 SEO / 科学内核 / 文档与论文 / CI 与部署 / AI 与 Agent 生态）+ 闸门可靠性专项审计 + 关键缺陷人工复核。
> 结论基调：**这是一个"诚实、可追溯、fail-closed"的罕见好项目**——但它正在被一批"能骗过自己"的闸门、两套分叉的引擎/管线、一条绕过所有安全控制的部署路径，以及大量"文档声称 ≠ 实际产物"的数字漂移所侵蚀。真正的提升点不是"加功能"，而是**把已经宣称的可信度变成机器可验证的事实**。

---

## 0. 执行摘要

RoboParts 的产品内核（三态 fail-closed 组合代数 + 共装第三关系 + 转接件生成 + 开源中立定位）是**真实且罕见**的：`compose_core.py` 的 R0–R5 规则与四条形式化代数律有性质测试；`co_mount` 是真正被明确定义的第三种关系（`port_exhausted` 与 `unknown` 被严格区分）；运动学"阴阳自检"是有正负对照的真实 CI 闸门；MCP 端点是真实的 streamable-http（26 个工具）；Agent 技能包可安装、MIT、可发布；18.7MB 训练集 + schema 合法的 Croissant 导出；llms.txt / agent-discovery.json 是带溯源层级的真实工件，不是"AI 标签"。

但深度扫描暴露了 **5 类"可信度被自我削弱"的结构性缺陷**，它们恰好都是这个项目最珍视的价值：

| # | 类别 | 核心事实（已复核） | 后果 |
|---|------|--------------------|------|
| 1 | **生产环境真实 bug** | `functions/_lib/upstream.js:98/101/122/128/129` 五个 `return /{...};/` 是 **RegExp 字面量**而非对象 → `.tier/.auth_state` 全为 `undefined` | Pro 用户被静默降级为 free；`X-Auth-State: undefined`；付费层在 oss/bom-check/contributors 上形同虚设 |
| 2 | **付费墙可绕过** | `functions/api/[[path]].js:102` 只对 `entities.json` 加 paywall；`compatibility_matrix.json / co_mount.json / compose_semantics.json / standard-audit.json / training_dataset.json / gap_classification.json / reachability_gap.json` 全部裸奔 | 承载 PREMIUM_FIELDS 的付费数据可免费直取；"premium" 层级自相矛盾 |
| 3 | **资金链路 fail-open** | `creem webhook.js:78-79` 在 `CREEM_WEBHOOK_SECRET` 未配置时跳过签名校验；`:109` 的分币启发式把"恰好 $10（1000 分）"当成 $1000 → Lifetime；`notify.js:134-181` 无幂等 → 并发双计 | 未认证即可铸积分；重复投递双倍入账；$10 误判为终身授权 |
| 4 | **闸门自我指涉** | `gate_mutation_score`（ci_gate.py:2338）只读预生成 `mutation-score.json`，从不把 M1–M6 变异体跑在**真实**闸门上；`mutation_score.py:172-192` 用私有重实现谓词评分；M5 变异体注入 `⚠ FAKE`（:105），杀手只查该字符串（:157） | **"变异体杀死率 1.00"不可信**——删除真实闸门后它仍报 1.00 |
| 5 | **86 项闸门不拦部署** | `.github/workflows/deploy.yml` 是独立 workflow，无 `needs: gate`；`ci.yml` 的 `gate` job 与 deploy 可并发 | 所有安全控制只在本地 `npm run deploy`（deploy.mjs）里生效；GitHub 生产部署绕过全部检查 |

**数据层**同样存在"声称 ≠ 契约"的分叉：`schemas/entities.schema.json` **从未被任何脚本或闸门加载校验**；`confidence_tier↔区间` 不变量被违反 **476/868（54.8%）**；"Tier C 置信度上限 0.30" 被 252/299 条 Tier-C 实体违反（其中 39 条还被标 `verified`、置信度高达 0.9）；163 条实体的唯一"来源"是搜索引擎查询；101 条实体的 `data_quality` 不在 schema 枚举里（4 个枚举值从未使用，4 个被用值却缺失）。

**发布面**的数字漂移是"错值被 Registry/Glama 二次分发"的教科书案例：`.well-known/mcp.json`/`smithery.yaml` 硬编码"46 项 CI 闸门"（实际 86）；`lhm.plugin.json` 硬编码"852 parts"（实际 868）；`croissant.json` 说 5.69%、其余 6 处说 16.2%；`llms.txt:135` 说"49 闸门/100 checks"而同行 `:2/:10` 说 86；**npm 包只注册 16/26 个 MCP 工具**（README/package.json 却宣称 26）。论文与产物**自相矛盾**：`papers/paper1-three-state-honesty.md` 仍断言"802 实体 / 351,649 对 / 5.69% / 112 对 100% 电气轴"，而仓库自身数据是"868 / 430,336 / 16.2% / 61 对 = 32 电气 + 29 信号"。

**一句话**：这个项目最值钱的资产是"诚实"，但当前最需要修复的恰恰是**一批让不诚实/不一致能通过验证的漏洞**。以下方案把"修复可信度漏洞"列为 P0，把"前沿技术融合"列为 P2，避免本末倒置。

---

## 1. 项目画像（已核实的硬事实）

- **定位**：面向开源机器人构建者的中立组合校验层——判定零件能否装配/共装/互换，输出可核验三态结论（能/不能/不知道），生成可打印转接件。**不卖零件 ⇒ 无理由骗你选错**。
- **数据**：868 实体（659 物理件 / 101 接口规范 / 81 AI 模型软件 / 10 组织 / 17 市场情报）；20 大类；机械接口声明率 **16.2%**（81/500）；开源组件 325。
- **判定规模**：`compose_semantics.json` 实测 **430,336 对**；`composed=0`、`type_error=262`、`unknown=430,074`；`gap_distance: {0:0, 1:61, 2:60,705, 3:369,308}`；**d=1 瓶颈 = 61 对（电气 32 + 信号 29，机械 0）**——注意：这**反驳**了论文旧稿"112 对 100% 电气轴"，真实故事是"双轴数据瓶颈"，且是更诚实、更强的叙事。
- **质量闸门**：`ci_gate.py` 的 `GATES` 列表恰为 **86 项**（71 个直接函数 + 15 个 `run_sub` 子进程闸门），已用 UTF-8 复核行数 = 86。
- **部署**：Cloudflare Pages + Cloudflare Functions（60 个 route 文件）；`_routes.json include=["/*"]` 强制全流量过 `_middleware.js` 私有路径黑名单（S-01 事件后修复）。
- **AI 面**：MCP 托管端点 26 工具（streamable-http）；`mcp-server` npm 包（注册 16 工具）；`agenticros-skill-roboparts` 技能包（11 工具、MIT、可发布）；18.7MB `training_dataset.json` + schema 合法 `croissant.json`；`llms.txt`（205 行）/`agent-discovery.json`/`.well-known/mcp.json`/`smithery.yaml`。
- **科研面**：`papers/` 含 kbs/mechatronics/arxiv 提交 + `paper1-three-state-honesty.md`；`docs/negative-results.md`（NR-001..005）与 `docs/verification-antipatterns-2026.md`（AP-001..010）是罕见而真实的"负结果/反模式"纪律。

---

## 2. 八大层扫描发现（含证据定位）

### 2.1 数据层与 Schema（A）

**强**：单一事实源（`normalize_categories.py:245-300` 由 `api/entities.json` 再生成分类文件/`data.js`/`api/data.json`）；id 唯一（0 重复/868）；"无来源不入库"对**空来源**真实生效（47/47 quarantine=true）；去重受控（0 个干净重复组）；许可拆分正确（`LICENSE` 纯 MIT、`DATA-LICENSE.md` CC BY 4.0）；分发为生成而非手写（868/868 id 全等 + 字节级闸门）；自曝"16.2% 声明率 / 0 条 A 级可比 / Tier 定义"。

**弱 / 风险**：
- `schemas/entities.schema.json` **从未被加载校验**——全仓仅注释/文档引用；真正跑的 `schema_contract.py` 只查 5 个核心字段（id/rp_id/entity_kind/name/category）+ mount_type + rp_id 唯一性，**不查** type（28/868 缺失）、confidence 区间、data_quality 枚举、source_tier 枚举。
- **confidence_tier↔区间矛盾（476/868=54.8%）**：schema（:36-40/:69-74）规定 verified=1.0/observed 0.7-0.9/derived 0.5-0.7/inferred 0.3-0.5，但 `normalize_categories.confidence_tier_rule()`（:132-165）**先按 source_tier 定级、无视数值** → 存储数据与规则 0 差异，却违反文档区间 476 次。
- **Tier C 置信度上限 0.30 文档化但未执行**：`DATA-LICENSE.md:47` + 分发 README 声称该上限，实际 252/299 条 Tier-C 置信度 >0.3（最高 0.72），39 条甚至 `confidence_tier='verified'`（如 LLM-028 conf 0.9）——语义上不可能（verified 要求一手数据表，Tier C = 无溯源）。
- **163 条实体唯一"来源"是搜索引擎查询**（`govern_source_tier.py:93-117`，全部 quarantine=false/data_quality=ok，置信度至 0.72）；加上 aggregation 61 / unattributable 25 / self_authored 3 = **224/868（25.8%）非锚点来源**却标 `ok`。
- **data_quality 枚举双向失配**：schema 6 值中 4 个从未使用（partial/quarantined_*），4 个被用值缺失（placeholder_id×51、unverifiable_vendor×30、non_entity×14、duplicate×6 = 101/868）；"quarantine=true→data_quality 前缀 quarantined_" 规则被违反 101/113 次。
- **字段级溯源生成但未交付**：`build_field_provenance.py:118-120` 产出 `api/field_provenance.json`，但该文件**不存在**；`field_provenance.schema.json` 用 draft-07 而其余 4 个 schema 用 2020-12。
- **contrib 层在事实源之外**：`entities.contrib.json` 142 条（均 OSS-*）不在 `entities.json`，运行时由 `compat_engine` 合并 → 发布数 868 ≠ 运行时可见池（约 1010），消费者少看约 14%。

### 2.2 Python 管线与质量闸门（B）

**强**：`dag.py` fail-fast + 逐步 trace + 最长前缀引用解析；`verify_pipeline.py:124/376` 是**真实**的"重构分叉守卫"（逐字段等价，仅排除 generated_at/by）；`gap.crosscheck`/`compose.crosscheck` 失败即停；`schema_contract.py:91-122` 的 rp_id 唯一性真抓到过 RP-GRI-0002 跨厂碰撞；`gate_gap_classification`（ci_gate.py:1134-1150）会**变异产物并断言其变红**（反装饰）；`regen_derived.py:56-98` 有文档化顺序约束；审计驱动闸门（零测试绿、死链、硬编码数漂移、Tier-A URL 黑名单）真实有效。

**弱 / 风险**：
- **变异闸门自我指涉**（最重）：`gate_mutation_score`（ci_gate.py:2338-2412）只读 `api/mutation-score.json`（generated_at **2026-10-13**，CI 不再派生）+ 自测，**从不重跑变异体**；M1–M6 变异的是**产物**（compose_semantics.json）而非引擎，且被 `mutation_score.py` 的**私有**谓词杀死（:137/:152/:162），非真实闸门；**M5 杀死是字面量恒真**——变异体注入 `⚠ FAKE`（:105），杀手扫 `'FAKE' in line`（:157）。→ **杀死率 1.00 不能作为"86 闸门能抓这些失败模式"的证据**。
- **管线不是真 DAG 也不是生产路径**：`dag.py:7-10` 明文"顺序执行、不做拓扑排序"；产物来自 `build_gap_classification.py`/`build_compose_semantics.py`，管线只在 `verify_pipeline.py` 里作为**影子回放**存在 → 双实现需手工同步。
- **regression.py 刻意不进 CI**：`ci.yml:7-9`（"那些断言依赖 ops/"）；约 96 个 layer1_N 函数、11,430 行、1000+ 断言全部本地-only → CI 可绿而本地红，且无交叉校验。
- **`regen_derived.py --check` 不是纯检查**：15/18 步 `supports_check=False`，在 `--check` 模式下**仍执行写**（:131-136）；且 `--check` 本身未接入 GATES。
- **Python 版本未固定**：`__pycache__` 同时出现 cpython-**312/313/314** pyc；CI 锁 3.12（ci.yml:43）但无 `.python-version`/`pyproject`。
- **子进程扇出大**：约 74 个 `run_sub` 调用点 + 13 个直接 `subprocess.run` ≈ 每轮 80-100 次解释器冷启 → 15 分钟 CI 预算（ci.yml:33）余量紧。

### 2.3 后端 API 与 MCP（C）

**强**：密钥正确置于 Pages Secrets（`wrangler.toml` [vars] 仅非密 CREEM_API_URL+产品 ID）；`_routes.json ["/*"]` 不变量成立 → `_middleware.js:29-69` 私有黑名单真实执行；`compat_engine.js:665-696/482` 三态诚实（undecided→null、无数据≠不兼容）；MCP 托管端点真实 streamable-http（batch、202、405-for-SSE、协议版本协商、hosted-vs-stdio 诚实边界）；供应商审批/报价 fail-closed（`approve.js:82-93`）；`idempotency.js`/`ledger.js` 实现"不可读≠空、故障→503"。

**弱 / 风险**（含已复核的 P0）：
- **CRITICAL**：`upstream.js:98/101/122/128/129` 五个 `return /{...};/` 是 **RegExp 字面量**（我已逐行复核）→ `resolveAuthState` 返回 RegExp，`.tier/.auth_state` 为 undefined → Pro 用户被降级 free、`X-Auth-State: undefined`。`oss.js:104`/`bom/check.js:230`/`contributors.js` 受影响。
- **付费墙可绕过**：`[[path]].js:102` 只挡 `entities.json`；其余 7+ 个承载 PREMIUM_FIELDS 的 JSON 裸奔。
- **幂等层是死代码**：`runIdempotent`（idempotency.js:72）**零调用方**；支付 webhook 做竞态读-改-写（`notify.js:134-181` 无并发守卫；`creem webhook.js` 无重复事件守卫）。
- **webhook fail-open**：`creem webhook.js:78-79` 在密钥缺失时跳过验签（"dev mode"无环境守卫）；`:109` 分币启发式把 $10（1000 分）→ $1000 → Lifetime。
- **零限流**：无任何 429 逻辑；`register.js:168` 存了 `rate_limit:30` 但从不执行。
- **OpenAPI 不完整**：`openapi.yaml` 只文档 6/约 60 个 route，且**未含旗舰 /mcp**、无 securitySchemes（尽管基于 key 鉴权）。
- **MCP 版本门控"宣传但未执行"**：`mcp.js` 引入 `filterToolsByVersion/toolAvailableAt`，但 `tools/list`（:1847）无视协商版本返回全部 26 工具。
- **`validateLicense` fail-open**：`[[path]].js:331-333` catch→false，Creem 故障时把有效 Pro 静默降级（正是 repo 自己 `upstream.js:116-120` 警告的"把裁决渲染成故障"）。

### 2.4 前端 / 网页 / SEO（D）

**强**：三态判定 UI **诚实呈现**（`co-mount.html:155-168` 四态独立语义 + 颜色，`v-mountable` 绿/`v-port_exhausted` 琥珀/`v-type_error` 红/`v-unknown` 灰；`:97-98` 明确"装不下（工程约束）"≠"未知（数据不足）"）；真代码共享（`_shell.js` 698 行幂等 IIFE 注入 43 页；`_shell.css` @900/560 响应式 + 汉堡）；SEO 头部成熟（index 有 WebSite+Dataset JSON-LD；22 篇文章全带 TechArticle JSON-LD；`llms.txt` 205 行 11 节；robots.txt 明确欢迎 GPTBot/ClaudeBot/CCBot）；`rp-project.js` 干净 314 行无全局泄漏；根 `_headers` 有 HSTS/nosniff/frame SAMEORIGIN/Permissions-Policy/rate-limit。

**弱 / 风险**：
- **1.8MB 孤儿 `data.js`**（1,832,038B/49,364 行）：生成自 `scripts/_archive/fix_entity_kinds.js:247`，**零页面引用**（已复核），未压缩、裸奔站点根。
- **无构建管线**：无 vite/webpack/rollup；0 页用 `defer`/`async`；`designer.html` 125KB 原始、`data-hub.html` 48KB、`compose-workbench.html` 43KB → 可避免的 TBT/LCP。
- **250 个内联 `onclick/onchange/oninput`**（约 30 页）→ CSP 被迫 `script-src 'unsafe-inline'` + `style-src 'unsafe-inline'`；`X-XSS-Protection: 1; mode=block` 是已废弃 no-op；缺 `frame-ancestors`。
- **sitemap.xml 漏 15 个可导航根页面**（assembly/bionic/bom-import/compatibility-viewer/compatibility-viz/contributors/demo-flow/funnel/order/reference-builds/scoreboard/spec-declare/standard-audit/supplier-admin/waitlist + articles/index）——42 页中约 36% 未提交。
- **42 页全站 0 个 `og:image`**（已复核）→ 无社交/链接预览。
- **XSS 链**：`embed/lookup.html:50-52` 与 `co-mount.html:167-181` 把 API/实体字段**未转义**插入 innerHTML（`x.name/x.category/x.manufacturer/j.host_name/j.interpretation/e.kind/e.claim/e.source`）——因 CSP 仍含 `unsafe-inline`，注入 `<script>/onerror` 会执行；实体数据部分用户提交（spec-declare）→ **潜在存储型 XSS**。
- **`.deploy-staging/_headers`（915B）仍带 `'unsafe-eval'` + `Access-Control-Allow-Origin: *`**（:7/:13），而根 `_headers`（3.9KB）已移除/收窄——若 staging 是部署工件，更弱策略上线（已复核二者分歧）。
- **co-mount.html:172 死变量 `cls`**：算出但从未应用 → 阶段判定（mount_fit/port_budget/signal_complementary）无 OK/不 OK 颜色，且原始英文 token（`fit/not_fit/unknown`）直出给中文用户。
- `index.html:25` `<head>` 内有未闭合 SVG 残片 `<text ...>🤖</text></svg>">`；a11y 缺 `for/id`、`aria-label`（co-mount.html:69）、点击元素无 `role/tabindex`。

### 2.5 科学内核：运动学 / 组合引擎 / 转接件 / 神经机器人（E）

**强**：三态代数**真实 fail-closed 且单一来源**（`compose_core.py` R0-R5：not_declared 永不出 compatible；缺 type_compat 键=unknown；incompatible>unknown>composed 优先 + ALGEBRAIC_LAWS 四条 + 性质测试；`compose_engine.py:5-24` 为薄 IO 壳）；**共装是真第三关系**（四态：mountable/port_exhausted/type_error/unknown + 唯一 port_budget 阶段，`co_mount_engine.py:43-45/281-288`，port_exhausted 正确区别于 unknown）；运动学阴阳自检**真实**（`verify_kinematics.py` 正对照 + fail-closed 负对照，接 CI 闸门 ci_gate.py:4596）；转接件是**真参数化 CAD**（CadQuery STEP+STL，STL 容差 0.01mm，干涉/壁厚检查，`bolting.py` 真实紧固件 BOM，单位一致 mm）；**不确定性被承载**（JS 暴露 evidence_strength/missing_evidence/data_evidence_tier、undecided 时 score=null；神经机器人带 confidence 0.82-0.95 + source_tier + 明确"未经实测复现"；运动学用保守 not_ruled_out）；**双引擎分叉已登记并被门控**（`reachability_gap.json` + `gate_reachability_gap` ci_gate.py:1452）。

**弱 / 风险**：
- **转接件几何四处来源已分叉**：发货的 `adapters/example_adapter.scad` 用 **4 孔 / pin-PCD 22/38**，而权威 `adapters/gen_adapter.py` 用 **6-M8 / 63/100**；`check_adapter_geometry.py`"三方一致"闸门只扫 `adapter-generator.html` + `gen_adapter.py`，**漏掉** `example_adapter.scad` 与 `roboparts-dataset/scripts/gen_adapter.py`（后者也分叉：A100 4-M8 vs 6-M10；A160 4-M12 vs 8-M16）→ 打印发货样例可能复现历史 A100 "销钉落在螺栓圆"故障。
- **双引擎（JS 4 维 vs Py 3 轴）漂移已登记但从未逐对调和**：`reachability_gap.json` honest_limits（:14）拒绝在 Python 里模拟 JS → 分歧只被静态量化（656 节点、composed=0 vs 产品字段覆盖 4-6%），无门控强制同对一致。
- **运动学是脚手架非结果**：`kinematics/source.json` 2 条链均 `topology_only/joints=[]`、computed=0/2。
- **ISO 9409-1 映射是主张非几何**：`compat_engine.js:437` + `build_derived_features.py:35/480` 承认平台**不持有 ISO 9409-1:2004 文本**；法兰表来自第三方查询（industrialroboticshub.com）+ 厂商数据表；A100/A160/A250 承认 pin=0。
- **ISO 22166-1 是条款级人工维护且指向草案**：`conformance_test.py:277`"映射表人工维护，原文条款解释存在主观性"；ISO 22166-1:2021 stage 90.92 修订中，继任 ISO/AWI 22166-1 FDIS 2026-04-05。
- **内部 docstring/产物漂移**：`build_compose_frontier.py:219-295` 自称"12 对里 9/9"，产物 `compose_frontier.json` 实为 both_sides_evidenced_pairs=56/incompatible=47；`reachability_gap.json:10` 标题"0/10 零引用"而自身 verdict 说 10/10 可达。
- **主张越过证据**：`compatible_via_adapter` 存在但 `build_compose_semantics.py:106-107` 承认"转接件几何可打印可信尚未做（H3 硬骨头）"；共装/转接链形式化"本轮不做"（`build_compose_frontier.py:60-62`）；完整 IK/自碰撞未建；`signal_interface.schema.json` 无法表达连续多通道信号（$comment，扩展"本轮明确不做"）。

### 2.6 文档 / 论文 / 运营 / 战略（F）

**强**：`negative-results.md` 是真实负结果日志（NR-001..005，每项含假设/方法/结果/根因/下次避免，正确记录了证伪）；`verification-antipatterns-2026.md` 十条 AP 各配事故/根因/规则/负测试；论文纪律**真实**（README 明文"数字由 onboarding_block.facts() 现算，禁手写"，相关脚本齐全）；arxiv/mechatronics 提交**已诚实更新**到 868/430,336/16.2%/61 对（arxiv 明确纠正旧"100% 电气"→"双轴瓶颈，非单轴" main.tex L76-79）；fail-closed 诚实贯穿（compose_semantics meta.honest_limits、promptfooconfig 元数据、evaluation/README 三态契约一致）。

**弱 / 风险**：
- **论文→产物矛盾**（最重）：`papers/paper1-three-state-honesty.md:36-42` + `papers/README.md:14/32-34/100` 仍断言旧基线"802/351,649/5.69%/112 对 100% 电气"；同目录 arxiv/mechatronics 已更新为新数 → **同一文件夹里"规范稿"与"提交稿"互相矛盾**，审稿人必抓。
- **可复现缺口**：NR-001/NR-002 命名方法为"运行 evidence_valuation.py"，但该脚本**不存在**（只有 `api/evidence_valuation.json` + ci_gate 的 gate_evidence_valuation）。
- **空洞/重复提交**：`papers/tii_submission/` 存在但 **0 文件**；`sci_full_package/` 38 文件是 kbs/mechatronics 的近重复（同 main.tex/cover_letter/figures）→ 74 文件里大量副本而非独立工作。
- **专业性问题**：arxiv（L38）+ mechatronics（L30）通讯作者为个人 QQ 邮箱且作者块无单位。
- **ops 倾倒场**：1009 文件；根目录 82 个散文件 + 24 个 `_probe_*.py` 临时脚本；7 个空子目录（含 `strategy/`——**字面的"战略"层目录为空**）；`ops/results/` 361 文件扁平无子目录；`ops/results/negative-results.md` 与 `docs/negative-results.md` 重复；`docs/runbook/disaster-recovery.md` 与 `docs/disaster-recovery.md` 重复（违反单一事实源）。
- **决策文档漂移**：`PROJECT_DIRECTIONS_V2.md`（v2.2，2026-09-24）宣称锚点，但 `strategy-decision-20261011.md`/`technical-decisions-20261014.md` 在其后且未折入/未标取代；`direction-change-feasibility-20260923.md` 仍说"802/5.69%"；无 ADR 索引。
- **MCP 工具数漂移**：`agent-ecosystem-map-20261008.md:34` 说"20 工具"，README 说"21"，`functions/mcp.js` 实际 **26**。

### 2.7 CI / 部署 / Git 卫生（G）

**强**：`deploy.mjs` 真稳健（preflight 拒脏树/陈旧数、`deploy_snapshot.mjs:296` 快照回滚、deploy 后 `verify()` :551-636 重试 5 次并查私有 404/实体总数/ID+类别+深字段指纹/OSS 层/21 页/8 个 HEAD、硬 8 分钟 wrangler 超时防历史 CPU=0 挂死）；`_routes.json ["/*"]` + `_middleware.js` 私有黑名单（含 `/.env.local`、`/.env`、`/wrangler.toml`、`/package.json`）在边缘 404；CI `cancel-in-progress:false`（:22-27）防批量推送互相取消；Dockerfile 正确（node:22-slim 对齐 engines、非 root、依赖层缓存、--omit=dev）；根 `_headers` CSP 严格（无 unsafe-eval、HSTS preload）且 CORS 收窄为白名单。

**弱 / 风险**：
- **86 闸门不拦部署**（已复核）：`deploy.yml`（:13-31）独立单 job、无 `needs: gate`；`ci.yml` 的 `gate` 与 deploy 可并发。
- **生产部署路径绕过全部安全**：`deploy.yml:19-31` 裸 rsync 到 `.deploy-staging` + `wrangler-action@v3`，**无** pre_deploy_check、**无** snapshot 回滚、**无** verify_deploy_snapshot/verify_host_parity/smoke_prod、**无** post-deploy 校验、**无** 超时；`deploy.mjs` 的稳健 `verify()` 只在本地 `npm run deploy` 才被触发。**两条分叉部署路径**（deploy.mjs 部署 git 根 `.`；deploy.yml 部署 `.deploy-staging`）。
- **供应链闸门 CI 空转**：`package-lock.json` 被 gitignore（已复核 `git check-ignore` 命中、`git ls-files` 为空）→ `gate_lockfile_and_sbom`（ci_gate.py:3437-3439）软通过；`gen_sbom.py --check` 在全新 checkout 不运行；devDependencies 浮动（prettier ^3.3.3、eslint ^9.11.1）。
- **lint/format 是死脚本**：ci.yml 只跑 `python scripts/ci_gate.py`；`ci_gate.py` 从不调 eslint/prettier → JS lint/格式不受约束。
- **CI 单一串行 job**：`ci.yml:30-60` 一个进程跑完 86 闸门（含子进程重的 verify_deploy_live/verify_pipeline/gen_sbom/git ls-files），15 分钟超时无并行。
- **版本不一致**：ci.yml 设 node **20**（:48），engines ≥22.22.0、.nvmrc 22.22.2；`action.yml:61` 用 node20。
- **`ci_gate.py --list` 在 Windows 默认控制台崩溃**：`UnicodeEncodeError 'gbk'` 无法编码 `↔`（:4939），exit 1（**已实测**：默认控制台仅输出 6 行并 exit 1；强制 UTF-8 才输出 86 行）→ 本地 `npm run ci:list`/`doctor` 坏。
- **历史密钥泄漏仍可恢复**：`git log -S 'gtk_'` 仍命中 a32a288/1c24bc2/a743686（尽管 0753516 重建）；`README.md:101` 已记录"旧 token 泄漏，请轮换"；当前 HEAD 跟踪文件无泄漏（已复核 `git grep` 空）。
- **deploy.yml rsync 排除列表不含 `.secrets/.tools/.env.local/.env/.wrangler`**——仅靠 gitignore + 有限 `_middleware.js` 黑名单兜底（S-01 正是这么漏的）。
- **SBOM serialNumber 硬编码非唯一**：`gen_sbom.py:124` `urn:uuid:roboparts-fixed-1111...` 违反 CycloneDX 跨再生成唯一性。

### 2.8 AI / Agent 生态（H）

**强**：技能包合规可装（`agenticros-skill-roboparts/package.json` v0.1.0、type:module、files 白名单、MIT、publishConfig public；`index.js` 导出 11 工具 + registerSkill；`lib/mcp-client.js` 真实零依赖 fetch JSON-RPC；有自测 `node --check`）；托管 MCP 端点真实（`functions/mcp.js` TOOLS=26、transport:streamable-http、endpoint、protocol_versions、26 个工具描述、onRequestHead、405-for-SSE；`server.json`/`smithery.yaml`/`.well-known/mcp.json` 一致）；三态诚实纪律贯穿 AI 面（manifest guardrails：overall=null 绝不报 incompatible、port_exhausted≠unknown；llms.txt:4-12 明示 agent 应调 MCP 而非猜 JSON；trace 脱敏）；数据即 AI 资产真实（18.7MB training_dataset.json、`export_training_dataset.mjs` v2 多模态、declared:false 诚实、复用 compat_engine.judgePair 为 SSOT；`croissant.json` schema 合法 Croissant 1.0 + `verify_croissant.py` 阴阳变异闸门）；多层 RAG/GEO 就绪（llms.txt/agent-discovery.json/docs/mcp-tools.md 440 行/agent-ecosystem-map）；`.workbuddy/automations` 真实每日 RED/GREEN 数字新鲜度自动化 + 只读不写 + 独立复核。

**弱 / 风险**：
- **工具目录分叉（AI 生态最大风险）**：npm `mcp-server/index.js` ListTools 只注册 **16** 工具，而 `package.json:4`/`README:20`/`docs/mcp-tools.md:6` 均宣称 **26**；npm 缺 15 个托管工具、另有 5 个非托管（dialects_list/dialects_evaluate/export_bom/plan_assembly/preflight_check）；`docs/mcp-tools.md:8-13` 明令"5 路同步 + 闸门 G-L1.19"，但 `verify_mcp_coverage.py` 只查类别 → **无闸门强制 npm↔托管工具集对等**。
- **`reputation.js`（9.8KB）是孤儿死代码**：从未被 index.js import（:16-17 注释"暂不接"），不在 files 白名单 → "reputation 层"在发布包里**不工作**。
- **公开清单硬编码过时数字**：`gen_public_manifests.py:215/246` 硬编码"46 项 CI 闸门"→ 落进 `.well-known/mcp.json:7`、`smithery.yaml:24`（实际 86）；`lhm.plugin.json:5` 硬编码"852 parts"（实际 868）、其工具列表 10 vs 托管 26。
- **数据集元数据自相矛盾**：`croissant.json:162` 说 5.69%，而 `croissant.json:45`/README:16/agent-discovery.json/llms.txt:75 都说 16.2%；`llms.txt:135` 说"49 闸门/100 checks"而同行 `:2/:10` 说 86。
- **技能包 files 白名单漏 docs/**：`package.json files=['index.js','lib/','README.md','LICENSE']` 但 `agenticros.screenshots=['docs/screenshot.svg']`（:57）→ npm publish 将缺失被引用的截图；且用自研 fetch JSON-RPC（lib/mcp-client.js）而非 MCP SDK → 无协议版本协商/能力握手。
- **`.opencode/`、`.workbuddy-ai/` 是工具生成状态**（node_modules、openwork/inbox chat-attachments 至 580KB、automations、cache、tmp，无配置）；若提交会膨胀仓库并可能泄漏会话/附件数据（`.opencode` 仅 63 字节 .gitignore 兜底）。

---

## 3. 三视角诊断

### 3.1 技术专家视角：正确性 > 速度，可信度 > 覆盖率

核心判断：**"宣称的可信度"与"机器可验证的可信度"之间存在系统性缺口**。这个项目把"诚实"当作产品，却在三处让不诚实能通过验证：

1. **闸门测自己**：变异测试用私有谓词 + 自我注入标记测自身 → "1.00 杀死率"是装饰性数字；`regression.py` 的 1000+ 断言被明确排除在 CI 之外。**可信度信号本身没有可信度**。
2. **契约不执行**：`entities.schema.json` 从未被加载；`confidence_tier` 区间、Tier-C 上限、"无来源"规则都在**文档里**而非**闸门里** → 476/868 违反、252 条破上限、224 条非锚点来源。
3. **分叉不调和**：JS 4 维 vs Py 3 轴引擎逐对不一致却无对拍；转接件 4 处几何来源分叉且 2 处无门控；npm 16 vs 托管 26 工具。**两套实现 + 一套影子管线 = 双倍维护、无对拍、必然漂移**。

技术债务的具体形态是"**影子系统**"：`scripts/pipeline/` 是验证过的影子回放，生产却仍用旧 `build_*.py`；`deploy.mjs` 是稳健的影子部署，GitHub 却用裸 `deploy.yml`；`idempotency.js`/`reputation.js` 是写好的影子层，零调用方。**建议原则：要么让影子成为生产，要么删掉影子**——最危险的是"影子存在但没人走"。

### 3.2 AI 专家视角：Agent 就绪度被"硬编码数字"与"目录分叉"卡住

这个项目的 AI 面在**架构上领先**（MCP + 技能包 + Croissant + llms.txt + RAG 就绪语料 + 诚实 guardrails），但在**一致性上被拖后腿**：

- **Agent 拿到的是矛盾的世界**：npm 包说 26 工具却只装到 16；`.well-known/mcp.json` 说 46 闸门而 README 说 86；`croissant.json` 说 5.69% 而其余 6 处说 16.2%；`llms.txt:135` 说 49 而 `:2/:10` 说 86。**下游 Agent / 目录站（Glama/Smithery/MCP.so）会逐字消费这些清单**——错值被"官方 Registry 二次分发"正是 repo 注释反复警告的失败模式。
- **缺的是"索引"而非"语料"**：868 实体 + 21 篇文章 + llms.txt + agent-discovery.json 已是强语料，缺一个**版本化、hash 固定的检索索引**（embeddings over 868 entities + 21 articles），并在索引上保留"别猜 JSON、去调 MCP"的纪律。
- **缺的是"评估"而非"生成"**：`scripts/eval_compat.mjs` + `api/eval/compatibility-golden.json` 已评估 compat 引擎，但 AI 面（MCP 往返、schema 遵循、诚实边界、npm↔托管对等）无 golden；`evaluation/promptfoo/` 三处对 `/api/co-mount` 状态自相矛盾且不跑 CI。

**AI 专家建议的优先级**：先做"目录一致性闸门"（工具集对等、数字 live 计算、诚实数调和），再做"RAG 索引 + AI 面 eval 金标准"，最后才是"Agent 数据更新自动化（auto-PR on drift）"。

### 3.3 互联网大拿视角：增长杠杆被"信任债"与"工程债"双重抑制

- **产品叙事是对的，但被自己打脸**：论文"112 对 100% 电气" vs 产物"61 对双轴瓶颈"；README/llms"86 闸门" vs mcp.json"46"。**一个把"诚实"当卖点的站，最忌讳的恰恰是数字自相矛盾**——搜索引擎/审稿人/Agent 都按"最差证据"给分。
- **SEO 有骨架无血肉**：JSON-LD/llms.txt/robots 都很好，但 sitemap 漏 36% 页面、全站 0 og:image、1.8MB 孤儿 data.js 裸奔、无构建/压缩。这是"内容强、抓取弱"的典型。
- **变现与中立可以共存，但当前漏洞是漏的**：付费墙可绕过 + webhook fail-open + 无限流 = **钱在漏**；而"Pro 被降级 + X-Auth-State: undefined"又同时**劝退真实付费用户**。两头都在流血。
- **信任债 = 增长债**：一个"vendor-neutral、fail-closed"的平台，如果连"Pro 用户是否真的 Pro"都不确定，那么企业定制/API 订阅（README 的三条变现路径）就没有地基。**先修信任债，再谈增长**。

---

## 4. 提升方案：P0 / P1 / P2 优先级路线图

> 影响 = 对"可信度 / 安全 / 资金 / 体验 / 增长"的综合权重；工作量 = S(半天)/M(1-3 天)/L(1-2 周)/XL(月级)。**P0 全是"让已有宣称变真"的修复，不是新功能。**

### P0 —— 止血：安全 · 资金 · 正确性（第 1 周）

| # | 动作 | 证据定位 | 影响 | 工作量 |
|---|------|----------|------|--------|
| 1 | **修复 auth 状态机 RegExp 返回**：5 处 `return /{...};/` → `return {...};`，并加回归测试断言 `resolveAuthState` 返回带 `.tier/.auth_state` 的对象 | `functions/_lib/upstream.js:98,101,122,128,129` | 高 | S |
| 2 | **webhook 验签 fail-closed + 修分币启发式**：`CREEM_WEBHOOK_SECRET` 未配置时 503（不"dev mode"跳过）；分币判断改为货币感知（消除 $10→Lifetime） | `functions/api/payment/creem/webhook.js:78-79,109` | 高 | S |
| 3 | **支付 webhook 接入 `runIdempotent`**（以 order_id/event id 为键），消除并发双计 | `functions/_lib/idempotency.js:72`；`notify.js:134-181`；`creem/webhook.js` | 高 | M |
| 4 | **付费墙单一事实源**：对承载 PREMIUM_FIELDS 的每个 `/api/*.json` 套 paywall，或明确标注为 free（与 /mcp 对齐） | `functions/api/[[path]].js:102-115` | 高 | M |
| 5 | **让 86 闸门真正拦部署**：`deploy.yml` 加 `needs: gate` + 部署后接入 `verify_deploy_snapshot.mjs`/`verify_host_parity.mjs`/`smoke_prod.mjs` + 8 分钟超时 | `.github/workflows/deploy.yml:13-31`；`scripts/deploy.mjs:551-636` | 高 | M |
| 6 | **修复变异闸门**：让 `gate_mutation_score` 把 M1–M6 跑在**真实** ci_gate 上（或 import 真实 `gate_three_state_conservation`），并加 `mutation-score.json` 新鲜度检查；删 M5 "FAKE" 字面量恒真 | `ci_gate.py:2338-2412`；`mutation_score.py:105,157,172-192` | 高 | M |
| 7 | **前端 XSS 修复**：引入共享 `esc()` 并在所有 innerHTML 插值处使用 | `embed/lookup.html:50-52`；`co-mount.html:167-181`；`bom-checker.html:209-219` | 高 | M |
| 8 | **Schema 契约落地**：把 `schemas/entities.schema.json` 接入 ci_gate；修 `data_quality` 枚举（补 placeholder_id/unverifiable_vendor/non_entity/duplicate，放松 quarantine 前缀规则） | `schemas/entities.schema.json`；`scripts/schema_contract.py:22` | 高 | S |
| 9 | **调和 confidence_tier 不变量**：统一 schema 区间与 `confidence_tier_rule()`，加"tier↔区间一致"闸门（当前 476/868 违反 → 0） | `normalize_categories.py:132-165`；`entities.schema.json:36-40,69-74` | 高 | M |
| 10 | **执行 Tier-C 置信度上限**：clamp ≤0.30 + quarantine，或删除文档声称的上限 | `DATA-LICENSE.md:47`；`sync_dataset_dist.py:308,338`；`govern_tier_c.py:34` | 高 | S |
| 11 | **统一 npm↔托管 MCP 工具集**：加"工具集对等"闸门，然后把 npm 同步到全部 26 托管工具（或降 README/package.json 声称） | `mcp-server/index.js`；`functions/mcp.js`；`docs/mcp-tools.md:8-13` | 高 | M |
| 12 | **付费/credits 限流**：按 key 计数（KV 或 CF Rate Limiting binding）在 payment/create、credits/webhook、catch-all 上执行 | `functions/api/register.js:168` | 中 | M |

### P1 —— 加固：工程可信度 · 架构一致（第 2–4 周）

| # | 动作 | 证据定位 | 影响 | 工作量 |
|---|------|----------|------|--------|
| 13 | **论文数字与产物对齐**：`paper1`/`README` 更新为 868/430,336/16.2%/61 对（32 电+29 信），标题改"双轴瓶颈"；加"论文数字 == facts()"闸门 | `papers/paper1-three-state-honesty.md:36-42`；`papers/README.md:14,32-34,100` | 高 | S |
| 14 | **转接件几何 4→5 源一致闸门**：把 `example_adapter.scad` + `roboparts-dataset` 副本纳入 `check_adapter_geometry.py`，任一 (pcd,holes,thread,pin_pcd) 分叉即红 | `adapters/example_adapter.scad`；`adapters/gen_adapter.py:116,122-123`；`check_adapter_geometry.py` | 高 | M |
| 15 | **JS↔Py 逐对引擎对拍闸门**：在共享机械+电气维度上同时驱动 `compat_engine.js` 与 `compose_core.py`，标记不一致对，并把对拍登记进 `reachability_gap.json` | `functions/_lib/compat_engine.js`；`scripts/compose_core.py`；`reachability_gap.json:14` | 高 | L |
| 16 | **管线升为生产路径**：`build_gap_classification.py`/`build_compose_semantics.py` 委托给已注册管线，等价闸门保留为回归绊线 | `scripts/pipeline/`；`verify_pipeline.py:124,376` | 高 | M |
| 17 | **公开清单数字 live 计算**：`gen_public_manifests.py` 从 `ci_gate.py GATES`/`facts()` 注入闸门数与声明率；加"公共清单无残留硬编码数"闸门 | `gen_public_manifests.py:215,246`；`.well-known/mcp.json:7`；`smithery.yaml:24`；`lhm.plugin.json:5` | 中 | S |
| 18 | **诚实数调和**：`croissant.json:162` 5.69%→16.2%、`llms.txt:135` 49→86；扩展 `verify_croissant.py` 审计 honesty_limits 字符串 | `api/croissant.json:162`；`llms.txt:135` | 中 | S |
| 19 | **提交 `package-lock.json`**（启用 npm ci + 激活 `gen_sbom.py --check` 供应链闸门），并改浮动依赖为锁定 | `.gitignore`（本仓忽略 lockfile）；`ci_gate.py:3437-3439` | 中 | S |
| 20 | **`regen_derived --check` 接入 CI 且只读**：补齐 15/18 步的只读检查，`--check` 加入 GATES | `regen_derived.py:131-136` | 中 | M |
| 21 | **前端最小构建 + 移除 `unsafe-inline`**：esbuild/vite 压缩+内容哈希 `_shell.js/_shell.css/rp-project.js` 与页面脚本；250 内联 handler → 事件委托；CSP 改 `script-src 'self'`（nonce/hash）+ `frame-ancestors 'none'`；删废弃 `X-XSS-Protection` | 根 `_headers:30`；`_shell.js`；约 30 页内联 onclick | 高 | M |
| 22 | **lint/format 进 CI**：`npm run lint` + `fmt:check` 作为并行 job（eslint 已限定 scripts/functions/mcp-server） | `.github/workflows/ci.yml`；`package.json:42-44` | 中 | S |
| 23 | **删/复用孤儿 `data.js`（1.8MB）**：零页面引用（已复核）→ 删除，或改为 gzip/br + 哈希 + 懒加载的按需投影 | 根 `data.js`（49,364 行） | 高 | S |
| 24 | **非锚点来源规则扩展**：把"空来源"闸门泛化为"非锚点来源"（search/aggregation → quarantine 或显式标 data_quality），覆盖 224 条 | `ci_gate.py:3213-3267`（D5）；`govern_source_tier.py:93-117` | 中 | M |
| 25 | **ADX/决策单一事实源**：建 `docs/ADR-INDEX.md`（含 strategy-decision-20261011、technical-decisions-20261014、DECISION_MUSE_20261004、PROJECT_DIRECTIONS_V2）+ 新鲜度闸门（基线晚于 facts() 即拒） | `docs/*.md`（约 12 个散落决策文档） | 中 | M |
| 26 | **ops 清理 + 索引**：归档 24 个 `_probe_*.py`、82 个根散文件；合并重复 negative-results/disaster-recovery；给空 `strategy/` 建真索引或删除 | `ops/`（1009 文件） | 中 | M |
| 27 | **`.deploy-staging/_headers` 与根对齐**：移除 staging 的 `unsafe-eval` + CORS `*`，保证部署策略与审计策略一致 | `.deploy-staging/_headers:7,13` vs 根 `_headers` | 中 | S |
| 28 | **补 sitemap + og:image**：脚本化比对实际 .html 文件（接入 ci_gate），补 15 个缺页 + `/articles/index`；全站加静态 og:image/og:url/twitter:card | `sitemap.xml`；42 页 `<head>` | 中 | S |
| 29 | **Python 版本固定**：`.python-version`(3.12) + `pyproject requires-python` + 清多版本 `__pycache__` | `__pycache__`（312/313/314）；`ci.yml:43` | 中 | S |
| 30 | **修复 `ci_gate.py --list` Windows GBK 崩溃**：输出强制 UTF-8（或 `errors='replace'`） | `ci_gate.py:4939`（↔） | 低 | S |
| 31 | **CI 拆并行 + 依赖缓存 + node 版本对齐**：静态数据 job 与子进程 job 分离；node 20→22；action runtime 对齐 | `ci.yml:30-60,48`；`action.yml:61` | 中 | M |
| 32 | **wire 或删 `reputation.js`**：接入 trace/dialect 层，或移除这个 9.8KB 孤儿 | `mcp-server/reputation.js`；`index.js:16-17` | 低 | S |

### P2 —— 增长：前沿技术融合 · 体验 · 生态（第 5–8 周）

| # | 动作 | 证据定位 | 影响 | 工作量 |
|---|------|----------|------|--------|
| 33 | **Agent 原生 RAG 索引**：生成版本化、hash 固定的检索索引（embeddings over 868 实体 + 21 文章 + llms.txt），经 `agent-discovery.json` 暴露，保留"别猜 JSON、去调 MCP"纪律 | `llms.txt:4-12`；`agent-discovery.json`；`api/entities.json` | 高 | L |
| 34 | **AI 面 eval 金标准**：复用 `eval_compat.mjs` 模式构建 MCP/技能层 golden（工具往返、schema 遵循、诚实边界、npm↔托管对等），接 CI；修复 `promptfooconfig.yaml` 三处 `/api/co-mount` 状态矛盾并升至 nightly | `scripts/eval_compat.mjs`；`evaluation/promptfooconfig.yaml:21,73,155-156` | 中 | M |
| 35 | **Agent 数据更新自动化**：把 `.workbuddy` 每日 freshness 自动化形式化为定时 CI job（verify_live_numbers + regen manifests + auto-PR on drift） | `.workbuddy/automations/*/memory.md` | 中 | M |
| 36 | **边缘缓存 + 静态壳资产**：`/_shell.js`、`/_shell.css`、`/rp-project.js` 加 `Cache-Control: public, max-age=31536000, immutable` | 根 `_headers` | 中 | S |
| 37 | **转接件容差模型**：给 SCAD/STEP 输出加 ISO 286 配合等级或"名义尺寸、未认证"诚实边界（当前 clearance=名义+0.5mm、README 的 g6 销配合未建模） | `adapters/gen_adapter.py`；`adapters/README.md:52` | 中 | S |
| 38 | **按 `d1_bottleneck` 精准补证据**：以 61 对 d=1（电气 32+信号 29）为优先采集队列，而不是追 composed>0 | `compose_semantics.json` gap_distance/d1_bottleneck | 中 | M |
| 39 | **运动学数据补链**：KC-OMY/KC-ODM 仅卡 link_mm/joint_axis/limits（拓扑已验证）→ 测一组 horn/link PCD 解锁 2 条真实可达链 | `kinematics/source.json` | 中 | M |
| 40 | **研究判定加可比置信信号**：给 compose/co_mount 判定加数值 confidence/evidence_strength，或显式文档化"三态 unknown + gap_distance 即所选编码" | `scripts/compose_core.py`；`co_mount_engine.py` | 中 | M |
| 41 | **字段级溯源交付 + schema 草案统一**：提交/生成 `api/field_provenance.json`；`field_provenance.schema.json` draft-07→2020-12 | `build_field_provenance.py:118-120`；`schemas/field_provenance.schema.json` | 中 | S |
| 42 | **贡献层边界澄清**：把 142 条 contrib 折入公开分发（带清晰溯源标记），或在 DATA-LICENSE/README 明示"公开集 868 不含运行时合并的 contrib 池" | `api/entities.contrib.json`；`DATA-LICENSE.md` | 中 | M |
| 43 | **历史密钥清洗 + gitleaks**：用 `git-filter-repo` 清 `gtk_` 历史（a32a288/1c24bc2/a743686），CI 加 gitleaks 扫描；把 `PRIVATE_FILES` 黑名单改为"默认拒绝 + 白名单"以防新敏感文件再漏 | `functions/_middleware.js:29-69`；`.github/workflows/ci.yml` | 高 | M |
| 44 | **a11y + 响应式 + 阶段色修复**：co-mount.html:172 应用 `cls` 并映射 token→中文；index 40 链接导航 @900 折叠；span/div 可点击加 role/tabindex；label 关联；aria-live；aria-current | `co-mount.html:69,172`；`index.html`；`urdf-library.html` 等 | 中 | M |
| 45 | **技能包 files 白名单补 docs/** 或删 screenshot 引用；升级到 MCP SDK**（替代自研 fetch JSON-RPC，获得协议版本协商/能力握手） | `agenticros-skill-roboparts/package.json:57`；`lib/mcp-client.js` | 低 | M |
| 46 | **供应商/企业级"验证即服务"**：把 26 工具 MCP 面 + honest_limits 字段包装为可售卖的"组合判定即服务"；`agent-ecosystem-map` 的 6 层 L1-L6 框架可作为唯一定位源（数字锚定到 mcp.js） | `docs/agent-ecosystem-map-20261008.md`；`mcp-server/index.js` | 中 | L |

---

## 5. 前沿技术 + 开源融合清单

把上面的动作落到**具体、可落地**的开源技术栈上（避免"AI 标签"式空谈）：

| 提升点 | 推荐开源/前沿技术 | 说明 |
|--------|-------------------|------|
| Schema 契约执行 | **JSON Schema 2020-12 + Pydantic v2 / jtd** | 把 `entities.schema.json` 变成 CI 强制契约；Pydantic 生成 typed 模型替代 `schema_contract.py` 手写 5 字段 |
| 前端构建 + 安全 | **esbuild / Vite + Tailwind**；**Playwright** | 压缩/哈希/代码分割，移除 `unsafe-inline`；Playwright 做 E2E + a11y + SEO 快照 + 死链检查（替换现有零散的 href 检查） |
| 后端 API 契约 | **OpenAPI 3.1 + openapi-typescript + Zod** | 从 route 文件生成 OpenAPI，typed client 防漂移；Zod 校验运行时输入 |
| 密钥/供应链安全 | **gitleaks / trufflehog**；**Renovate / Dependabot**；**Trivy / syft** | gitleaks 进 CI + `git-filter-repo` 清历史；Renovate 锁浮动依赖；SBOM 用 syft 生成唯一 serialNumber |
| 可观测性 | **OpenTelemetry + Cloudflare Workers Logs/Tail**；**Sentry** | 把 `upstream.js`/`compat_engine.js` 的关键路径埋点，捕获"Pro 被降级"这类静默故障 |
| 数据管线 | **Polars**；**uv + pyproject + .python-version**；**DuckDB** | 替代手写 CSV/JSON 循环；uv 固定解释器；DuckDB 做 430,336 对聚合分析（现为纯 Python 大循环） |
| 性质/变异测试 | **pytest + Hypothesis**；真实变异（**mutmut / cosmic-ray**） | 让变异体真跑真实闸门，消灭 M5 "FAKE" 恒真；Hypothesis 测 R0-R5 代数律 |
| 引擎对拍 | **双引擎 property-based 对拍 harness**（Hypothesis 生成 (a,b) 对） | JS↔Py 逐对一致，纳入 CI |
| 转接件几何 | **build123d / CadQuery（已在用）+ trimesh + ocp** | 补 ISO 286 配合、mesh 布尔校验；STEP/STL 一致性导出 |
| Agent 原生 RAG | **Cloudflare Vectorize / Workers AI**，或 **pgvector / LanceDB / Qdrant** | 版本化 hash 固定检索索引；保持"调 MCP 而非猜 JSON" |
| MCP/SDK | **@modelcontextprotocol/sdk**（替换自研 fetch JSON-RPC） | 获得协议版本协商/能力握手；技能包与托管端点共享工具注册表 |
| LLM 评估 | **promptfoo（已在用）→ 升 nightly + CI**；**DeepEval / Ragas** | 覆盖 MCP/技能层 golden，修复 co-mount 三处矛盾 |
| ML 数据资产 | **Croissant（已在用）+ Hugging Face Hub** | `roboparts-dataset-github` 已是分发面；补 field 级溯源与诚实边界 |
| 数据质量 | **Great Expectations / pandera** | 把"confidence_tier 区间、Tier-C 上限、非锚点来源"变成数据契约而非注释 |
| 决策/文档治理 | **ADR（已部分有）+ adr-tools / git-notes**；**MkDocs / Docusaurus** | 收敛 12 个散落决策文档为单一 ADR 索引；文档构建进 CI |
| 部署安全 | **GitHub Environments + 保护规则 + OIDC**；**Cloudflare Pages 预览/生产分支保护** | `deploy.yml` 加 `needs: gate` + 环境审批；用 OIDC 替代 `.env.local` 双凭据源 |

---

## 6. 结论

RoboParts 的**内核是真正可信的**，其最大风险不是"做得太少"，而是"**宣称得比验证的多**"：86 项闸门里有自我指涉的变异测试、有被守对象缺席即放行的软通过、有 1,233 条刻意不进 CI 的回归；Schema 契约从不执行；论文与产物数字矛盾；双引擎/双管线/双部署分叉未对拍；npm 与托管 MCP 工具集分叉；付费墙可绕过、webhook fail-open、Pro 被静默降级。

**最该做的一件事**：把"可信度"从**叙事**变成**机器可验证的事实**——优先修复 `upstream.js` RegExp bug、webhook fail-open、变异闸门自指涉、schema 契约不执行、部署不拦闸门，让"86 闸门"名副其实地拦住每一次生产部署、让"1.00 杀死率"真的由真实闸门杀死、让"476/868"的 tier 矛盾归零。

**其次**：让影子成为生产——管线升为生产路径、deploy.mjs 的验证接入 GitHub 部署、idempotency 接入 webhook、MCP 工具集对等；然后才是**前沿融合**（Agent 原生 RAG、AI 面 eval 金标准、OpenAPI 3.1 契约、gitleaks+OIDC、Playwright 前端验证、Polars/DuckDB 数据层、MCP SDK）。

一句话给团队：**你的诚实是产品，别让装饰性闸门和文档漂移把它变成营销话术。** 先修"验证的可信度"，再谈"数量的增长"。

---

*生成：2026-10-31 · 基于 8 路并行深度扫描 + 闸门可靠性专项审计 + 关键缺陷人工复核（含 `upstream.js:98/101/122/128/129`、`data.js` 零引用、`ci_gate.py --list` Windows 崩溃、`.deploy-staging/_headers` 分叉、`package-lock.json` gitignore、`compose_semantics.json` 430,336 对 / 61 d=1 / 16.2% 等均已在本次会话中实测确认）。*
