# 2026 验证反模式档案

> **用途**：把本项目 `ops/results/_SUMMARY.md` 中记录的假绿/假红/静默失效事故，提炼为可复用规则 + 可运行阴性测试。
> **性质**：工程事故案例集，非标准符合性声明。每条规则均可由 CI 闸门 `ci_gate.py` 自动验证。
> **更新规则**：新增事故 → 追加到本文件 → 同步到对应 `verify_*.py` 的自证模式 → CI 全绿后方可部署。

---

## 索引

| # | 反模式 | 失效类型 | 首次事故 | CI 闸门 |
|---|---|---|---|---|
| AP-01 | 无价格冒充在预算内 | 假绿 | L1.22 | `verify_compat_semantics.py` |
| AP-02 | null 守卫缺失致假红 | 假红 | L1.23 | `verify_compat_semantics.py` |
| AP-03 | 数据层伪造声明 | 假绿 | L1.30 | `verify_l130_injections.py` |
| AP-04 | 遥测 flush 竞态丢写 | 静默失效 | L1.31 | `verify_flush_race.mjs` |
| AP-05 | 接入路径断裂（文档 ≠ 端点） | 假绿 | L1.36 | `verify_l136_injections.py` |
| AP-06 | 补写声称不存在的哈希 | 留痕造假 | L1.40 | `verify_hashclaim_injections.py` |
| AP-07 | 机读契约手抄漂移 | 假绿 | L1.43 | `verify_l143_injections.py` |
| AP-08 | 非幂等注入器膨胀 | 静默膨胀 | L1.55 | `verify_l155_injections.py` |
| AP-09 | 正文规模数字硬编码 | 假绿 | L1.61 | `verify_l161_injections.py` |
| AP-10 | mount_type 当身份键 | 假绿 | L1.64 | `verify_l164_injections.py` |
| AP-11 | 类型错误说成数据缺口 | 假红 | L1.68 | `verify_l168_injections.py` |
| AP-12 | truthy 判断压三态 | 假红 | L1.28 | `verify_l128_injections.py` |

---

## AP-01：无价格冒充在预算内

**事故**（L1.22）：MCP `recommend_components` 工具在 `budget` 过滤中写 `p==null || p<=budget`，使 688 条中 494 条（71.8%）无价格条目无条件放行。结果：预算 $50 返回数万美元整机，用户被误导认为系统推荐了"便宜零件"。

**失效模式**：`unknown`（无价格）被当作 `true`（在预算内）处理。系统把"不知道"说成了"可以"。

**根因**：过滤逻辑把"数据缺失"和"满足条件"合并为同一分支。这是本项目最核心的反模式——**fail-open on unknown**。

**判据修正**：引入 `priceBounds` 解析上下界 + `priceFit` 四分类（`fit`/`over`/`under`/`unknown`），只剔 `over`，`unknown` 保留但打标计数。

**可复用规则**：

> **规则 R-01**：任何过滤/排序判据中，`null`/`undefined`/`missing` 必须走独立分支，不得与"满足条件"合并。
>
> **可验证性**：注入 `p==null || p<=budget` 写法 → CI 必须判红。
>
> **闸门实现**：`verify_compat_semantics.py` 自证模式中 `budget_filter_unknown_as_fit` 变异体。

---

## AP-02：null 守卫缺失致假红

**事故**（L1.23）：兼容引擎 `compatible = shared.length > 0` 无 null 分支。348 条 `not_declared` + 338 条 `n_a` 的机械接口被判成"不兼容"，BOM 检查器据此弹告警。全库 A/B 测试：120 实体 7140 组合中 83.6% 假红。

**失效模式**：`null`（未知）被当作 `false`（不兼容）处理。系统把"不知道"说成了"不行"。

**根因**：这是 AP-01 的镜像——**fail-closed on unknown**。AP-01 是 fail-open，AP-02 是 fail-closed。同一教义的两半。

**判据修正**：三态 `compatible: true | false | null`。`null` 意味着"无法判定"，不给 0 分（被读成完全不兼容）也不给 100 分（被读成完美兼容）。

**可复用规则**：

> **规则 R-02**：二元判据（兼容/不兼容）遇到 `null` 输入时必须返回 `null`（第三态），不得坍缩为 `true` 或 `false`。
>
> **可验证性**：注入 `shared.length > 0` 无 null 守卫 → CI 必须判红。
>
> **闸门实现**：`verify_compat_semantics.py` 自证模式中 `null_guard_removed` 变异体。

---

## AP-03：数据层伪造声明

**事故**（L1.30）：OSS 摄取管道按"哪个抽取器抓的"伪造 `ros_support` 字段——`urdf` 抽取器一律写 `true`（125 条），`bom_md` 抽取器一律写 `false`（63 条），`readme` 按名字含 `ros` 子串猜。无一条来自厂商声明。且该字段是 `/api/oss` 付费字段，未声明数为 0 使 L1.27/28 的 `unknown` 分支成死代码。

**失效模式**：抽取器把"出处类型"当作"能力声明"。`urdf` 只证明数据来源，不证明 ROS 兼容性。给侧板、电池、底盖写 `false` 属于范畴错误。

**根因**：数据层把"我能从这个格式推断"当成了"厂商声明了这个能力"。这是**证据链断裂**——从出处到结论之间缺少了声明环节。

**判据修正**：三个抽取器不声明 `ros_support`；`makeEntity` 三态透传；存量 189 条迁移；`urdf` 补 `ros_ecosystem_origin` 记出处（不记能力）。

**可复用规则**：

> **规则 R-03**：数据层不得从数据来源类型推断能力声明。出处 ≠ 能力。若需记录"来源于某格式"，使用独立字段（如 `origin`），不得混入能力字段。
>
> **可验证性**：注入"按抽取器类型写 `ros_support`"写法 → CI 必须判红。
>
> **闸门实现**：`verify_l130_injections.py` 中 `fabricated_ros_support` 变异体。

---

## AP-04：遥测 flush 竞态丢写

**事故**（L1.31）：一次 `tools/call` 连续两次 `recordMcp`，两个 flush 各自 `await kv.get` 读到同一份旧值，后写覆盖先写。要害在于 `toolsrc:*` 正是判定 MCP 真实需求的唯一判据——带丢写跑一天会系统性偏低，把结论推向"没人用别投入"。

**失效模式**：并发写覆盖。两个 async flush 读到同一份旧值，后写者赢。丢写是**系统性偏低**而非随机——方向固定。

**根因**：flush 未串行化。在 isolate 内，多个异步写入操作共享同一个 KV key，无锁机制。

**判据修正**：`_flushChain` + `scheduleFlush` 在 isolate 内串行化。`read_metrics.py` 读数明示为下界。

**可复用规则**：

> **规则 R-04**：KV/持久化写入必须在同一 key 上串行化。若无法串行，必须使用 CAS（compare-and-swap）或乐观锁。读数端必须标注"下界"。
>
> **可验证性**：注入并发 flush 场景 → 实测必须检测到丢写。
>
> **闸门实现**：`verify_flush_race.mjs` 切真实源码 + mockKV 实跑竞态窗口。

---

## AP-05：接入路径断裂（文档 ≠ 端点）

**事故**（L1.36）：README 教用户 `npx roboparts-mcp-server`，实测 npm 404（从未发布）；`mcp-guide` 三份配置全指本地路径占位，全文 `git clone` 出现 0 次；唯一零门槛可用的远程直连 `roboparts.cc/mcp` 实测无需 API Key 即可 `tools/call` 成功，但两份文档只字未提。`server.json` remotes 声明正确，故目录站能发现（`/mcp` 访问 781 次），而人照文档接不进来。

**失效模式**：对外文档声明的接入方式与真实可用端点不一致。系统"能被发现但不能被使用"。

**根因**：文档与端点分离维护，无自动对账。每新增一个端点，文档需要手工同步——而人总会忘。

**判据修正**：改为远程直连优先 + 补 `mcp-remote` 桥接 + 补 clone 指引。新增 L1.36 闸门：未发布包名不得进可执行配置 / 本地路径占位必配获取指引 / 远程直连必须提及。

**可复用规则**：

> **规则 R-05**：对外文档中出现的可执行命令/配置，必须在部署前实测可达。"能被发现"（目录站索引）≠"能被使用"（人照文档操作成功）。
>
> **可验证性**：注入"文档指向未发布包名"→ CI 必须判红。
>
> **闸门实现**：`verify_l136_injections.py` 中 `unpublished_package_in_config` 变异体。

---

## AP-06：补写声称不存在的哈希

**事故**（L1.40）：21:43 报告声称提交哈希 `4ea6d47`，但该哈希根本不存在。23 个文件滞留工作区，仓库停在 `de8ecdf` 而线上已部署——**线上领先仓库，本机回滚即不可重建**。

**失效模式**：留痕造假。报告声称的提交哈希不存在，导致审计链断裂。更严重的是"线上领先仓库"状态——若本机磁盘故障，线上版本不可重建。

**根因**：占位机制（`AUTO-STUB`）在运行未填写报告时落占位，但未验证"该轮是否真的有提交"。占位断言"该轮运行异常中断"为假——唯一变绿方式是编造第一人称报告。

**判据修正**：新增第 6 条留痕不变式（报告声称的哈希必须真实存在）+ `verify_hashclaim_injections.py` 5 类注入。`deploy.mjs` 部署前无报告则落 AUTO-STUB 占位（含 git HEAD + 未提交清单），但占位不得声称"异常中断"。

**可复用规则**：

> **规则 R-06**：报告/日志中声称的 commit 哈希必须真实存在于仓库。"线上领先仓库"状态禁止超过一个部署周期。
>
> **可验证性**：注入"不存在的哈希"→ CI 必须判红。
>
> **闸门实现**：`verify_hashclaim_injections.py` 中 `nonexistent_hash` 变异体。

---

## AP-07：机读契约手抄漂移

**事故**（L1.43）：`skills/manifest.json`（请外部 Agent 框架解析后自动注册工具的机读契约，线上 200）声明的 5 个 `mcp_tool` 技能实跑 0 个可用：`query` 未知参数（真名 `keyword`）/ `components` 数组缺 `component1_id,component2_id` / `count_per_category` 真名 `count` / `parameter_semantics` 与 `dataset_discovery` 两个工具端点根本不存在。

**根因**：08:00 刚在 `mcp.js` 内把白名单改成从 schema 推导（理由：杜绝两处各写一份而漂移），三小时后就在另外三处手抄了新副本。**闸门作用域被自己定小**——只锁了 schema 推导，没锁手抄副本。

**判据修正**：`mcp.js` 导出 `TOOLS` 为唯一真相源 + `gen_skills_manifest.mjs` 一次生成三处对外复述（manifest/README 表格/agent-discovery.skills.items）+ 散文单放 `skills.meta.json`（写不存在的工具即报错退出）。

**可复用规则**：

> **规则 R-07**：机读契约的参数名、端点名、schema 必须从单一真相源自动生成，不得手抄副本。若必须手抄，必须在 CI 中逐字对账。
>
> **可验证性**：注入"手抄副本参数名与真相源不一致"→ CI 必须判红。
>
> **闸门实现**：`verify_l143_injections.py` 中 `manifest_param_drift` 变异体。

---

## AP-08：非幂等注入器膨胀

**事故**（L1.55）：接入区块注入器非幂等——`STYLE` 常量发在幂等标记之外，`strip_marked` 剥不掉。每跑一次净增一份，全站 17 页已堆 107 份死重复 CSS 且正在线上。上轮把它挂进 deploy 后升级为每小时自动膨胀。

**失效模式**：注入器每执行一次增加冗余内容。幂等标记范围错误导致 `strip_marked` 无法剥离。

**根因**：幂等标记（HTML 注释标记）未包裹全部内容。`STYLE` 常量在标记之外，每跑一次就追加一份。

**判据修正**：按签名自愈剥离 + 对称吃空行修根因。124→17 份，`index.html` 22.7KB→14.3KB（-37%），全站约减 90KB。

**可复用规则**：

> **规则 R-08**：所有注入器必须是幂等的——`inject(inject(x)) === inject(x)`。幂等标记必须包裹全部内容，包括 CSS/JS 常量。
>
> **可验证性**：注入"非幂等常量在标记外"→ CI 必须判红。
>
> **闸门实现**：`verify_l155_injections.py` 中 `non_idempotent_injector` 变异体。

---

## AP-09：正文规模数字硬编码

**事故**（L1.61）：14 篇长文正文写死规模数字（427/493 实体、155 执行器、95/103 芯片、62 传感器、17/21 AI 模型），全部过期且自相矛盾。线上实测 11/17 页对外数字失真。

**失效模式**：正文中的数字与真相源不同步。上一轮"已修复"只改本地，两个假设均不成立——"推 GitHub = 会自动上线"（Pages 未接 GitHub 构建）与"本机无 CF 凭据跑不了 deploy"（wrangler OAuth 实跑即自动续期，"跑不了"是猜的）。

**根因**：正文中的数字是手工写入的，无构建时替换机制。每次实体数变化，14 篇文章都需手工更新——人总会忘。

**判据修正**：正文规模数字改为 `{{RP:TOTAL}}` / `{{RP:CAT:xxx}}` / `{{RP:CATEGORIES}}` 占位符，`build_articles.py` 新增 `render_tokens` 构建时从 `onboarding_block.facts()` 现取。未渲染泄漏即中断。

**可复用规则**：

> **规则 R-09**：正文/文档中出现的规模数字必须从真相源构建时注入，不得硬编码。硬编码的数字是"未来的 bug"——每增加一个实体都会过期。
>
> **可验证性**：注入"正文包含硬编码实体数"→ CI 必须判红。
>
> **闸门实现**：`verify_l161_injections.py` 中 `hardcoded_entity_count` 变异体。

---

## AP-10：mount_type 当身份键

**事故**（L1.64）：兼容引擎用 `mount_type` 作为接口身份键。宇立两个传感器被判 `compatible: true`，而其 `gap` 字段自陈判不了。

**失效模式**：`mount_type` 是分类标签，不是身份键。两个不同类型的传感器可能共享同一 `mount_type` 但物理上不兼容。系统把"同类型"说成了"可互换"。

**根因**：身份键选择错误。`mount_type` 粒度太粗，无法区分同类型下的不同物理规格。

**判据修正**：使用 `mount_type` + 具体尺寸参数（孔位/法兰规格）作为复合身份键。

**可复用规则**：

> **规则 R-10**：接口身份键必须包含所有影响物理兼容性的维度。分类标签（如 `mount_type`）粒度不够细时，必须叠加具体规格参数。
>
> **可验证性**：注入"仅用 `mount_type` 判兼容"→ CI 必须判红。
>
> **闸门实现**：`verify_l164_injections.py` 中 `mount_type_as_identity` 变异体。

---

## AP-11：类型错误说成数据缺口

**事故**（L1.68）：`protocols` + `interfaces` 是规范本身、`llms` + `robot_ai_models` 是软件模型，共 187 条占旧口径 27%。旧引擎答"EtherCAT 未声明通信协议"——它就是协议。把类型错误说成数据缺口。

**失效模式**：非零件实体被当作零件处理。引擎对规范/模型/企业/情报四类实体执行零件兼容判定，产生大量假红。

**根因**：实体类型分档不足。旧引擎只区分"零件 vs 非零件"，未细分零件内部的规范/模型/企业/情报。

**判据修正**：新增 `organization` 第三档 + 判定入口类型闸（L1.65）。`mcp.js` 黑名单过滤改为白名单 `isSelectableComponent`。

**可复用规则**：

> **规则 R-11**：兼容判定引擎必须在入口处做类型校验。非零件实体（规范/模型/企业/情报）不得进入零件兼容判定流程。类型错误 ≠ 数据缺口。
>
> **可验证性**：注入"非零件实体进入兼容判定"→ CI 必须判红。
>
> **闸门实现**：`verify_l168_injections.py` 中 `type_error_as_data_gap` 变异体。

---

## AP-12：truthy 判断压三态

**事故**（L1.28）：选型引擎 `/designer` 的 ROS 假红四处——`truthy` 判断把"未声明"压成"不支持"，执行器 167/199=84% 被写"原生不支持 ROS"。与 L1.23 同型漏网。

**失效模式**：`if (value)` 把 `null`/`false`/`undefined` 全部压成 `false`（不支持）。三态坍缩为二元。

**根因**：JavaScript 的 truthy 语义与三态判据冲突。`null`（未知）和 `false`（不支持）在 truthy 判断中等价。

**判据修正**：`rosState()` 三态函数 + L1.28 全文件级禁 truthy（10 断言）。

**可复用规则**：

> **规则 R-12**：涉及三态判据的代码不得使用 truthy/falsy 判断（`if (value)` / `value ? ... : ...`）。必须使用显式比较（`=== true` / `=== false` / `=== null`）。
>
> **可验证性**：注入"truthy 判断替代三态比较"→ CI 必须判红。
>
> **闸门实现**：`verify_l128_injections.py` 中 `truthy_collapse` 变异体。

---

## 元模式：AP-01 与 AP-02 的镜像关系

本项目最核心的反模式对是 **AP-01（fail-open on unknown）** 与 **AP-02（fail-closed on unknown）**。它们互为镜像：

| 维度 | AP-01（fail-open） | AP-02（fail-closed） |
|---|---|---|
| unknown 处理 | 当作满足条件 | 当作不满足条件 |
| 用户感知 | 系统推荐了"便宜零件"（实为无价格） | 系统拒绝"兼容零件"（实为未声明） |
| 方向 | 过度乐观 | 过度悲观 |
| 修复 | 三态 + `unknown` 打标 | 三态 + `null` 守卫 |
| 教训 | **不要为了"可用"而假设 unknown=true** | **不要为了"安全"而假设 unknown=false** |

> **核心纪律**：本项目承诺的三态（`true` / `false` / `null`）不是设计选择，而是**对 unknown 的诚实处理**。任何把三态坍缩为二元的做法——无论是 fail-open 还是 fail-closed——都是同一类错误：**把"不知道"说成"知道"**。

---

## 使用方式

1. **新增事故**：记录到 `ops/results/_SUMMARY.md` → 提炼为 AP 条目追加到本文件 → 同步到 `ci_gate.py` 对应闸门
2. **新增规则**：每条规则必须配一个可运行的阴性测试（注入违规 → 断言被拦）
3. **对外发布**：本文件可作为 arXiv 短文 / ROS Discourse / HN 素材发布。ROI：这是"怎么保证 AI 生成的东西是对的"的一手案例集
4. **与 mutation_score.py 的关系**：本文件是"已知失效模式"，`mutation_score.py` 是"已知失效模式的自动化覆盖度量"。前者是规则，后者是评分。

---

*本档案基于 2026-08-05 至 2026-10-13 期间 `ops/results/_SUMMARY.md` 中记录的 170+ 条运行流水提炼。所有事故均可通过 `git log` + `ci_gate.py --list` 复现。*
