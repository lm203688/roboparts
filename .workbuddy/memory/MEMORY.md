# RoboParts 长期约定（跨会话有效）

## 一、定位与方向（唯一口径）
- 定位：**机器人零件兼容性判定层**（vendor-neutral）。代码 MIT / 数据 CC BY 4.0。
- 病症史：曾同时说 6 套口径且 0 套被验证。**机器可读四件套（`server.json`/`smithery.yaml`/`lhm.plugin.json`/`.well-known/mcp.json`）比人类页面更准**，是定位真相源 ⇒ 用它反向同步人类页面，不重新发明定位。通则：生成器治理过的产物总比手写页面准。
- UVP：**三态诚实**——唯一会告诉你"我不知道"的数据层（机械接口公开登记答不出 94.25%）；不卖零件所以没理由骗你选一个。
- 受众：T1 开源机器人构建者（ROS/URDF 圈）/ T2 集成商接口工程师（唯一有付费动机）/ T3 AI Agent（零边际成本）。**排除**：消费者、大型 OEM 采购、投资人、供应商（29 次调用 0 注册已证无效）。
- 不做：造脑/造芯片、整机构建、佣金中介（抽佣=立场崩塌）、Tnkr 提案（不主动发，`api.tnkr.ai` 无 API 面）、star 竞赛、GOAI。
- 全站数字唯一真相源 `onboarding_block.facts()`，**禁手改页面数字**。三层保鲜：①`data-rp` 锚点 ②裸文本 ③子集口径（子集数必现算，比总数更危险）。
  **生成器模板里的裸数字是双盲区**：`build_articles.py` 曾硬编码 688（真值 798），无锚点 ⇒ 锚点扫描与回归都不覆盖。改生成器源串一律 `facts()` 现算。

## 二、飞轮与留痕
- 每轮落盘 `ops/results/_LATEST.md` + `_NEEDS_USER.md` + `_SUMMARY.md` + `roboparts-YYYYMMDD-HH.md`；"汇报"读前两份。
- 日报 `_last_digest.txt` 节流 >24h；到期须**手写** `_DAILY_DIGEST-*.md` 后 `--stamp`；`DIGEST-CLAIM` 只走 `digest_due.py`。
- 飞轮首 `run_lock.py acquire`、末 `release`。
- 占位补写不删（删=孤儿红灯）；**历史时段**补写用 RECONCILED + 免责 + 真 commit 哈希，`by=` 须晚于被补写时段。
  **当前小时不适用 RECONCILED**（L1.40 判据 `slot < by <= cur`，slot==cur 时区间为空）；本轮确有完整运行就走第一人称删 AUTO-STUB。
  瞬态升级项（自愈器误报）核销后**不删原条目**，给关闭项加机读 assert（关闭项 assert 不校验，留审计痕迹）。
- **幽灵哈希四态**（`scripts/lib/hash_history.py`）：`current` / `rewritten`（台账 old→new）/ `deleted_by_rewrite`（台账 old→全 0，filter-repo 亲证，**非伪造**）/ `unknown`=幽灵。
  本地 commit 加反引号，**远端 ref/tree 一律裸写**（加反引号会被 HASH_CTX 当本地 commit 解析）。正则 `HASH_CTX=(提交|commit|推送|push|HEAD)[^`；;。，,、\n]{0,24}`([0-9a-f]{7,10})``。否定语境（不存在/幽灵/伪造/订正）豁免。**不得**把全 0 并入 `_mapping()`（台账守卫要求映射目标真实存在）。
- 门禁探针会假红假绿（L1.74 idset 曾两 bug 致 56 对误判）。异常数量必须能用手算组合数逐位对账。

## 三、部署与 GitHub
- 铁律：提交→推送→部署。**推 GitHub ≠ 上线**；deploy 后必跑 `verify_live_numbers.py` 回探 + 漂移收口 commit。
- `ops/` 在 .gitignore。token 在 `~/.git-credentials`（`https://x-access-token:<tok>@github.com`，正则 `x-access-token:([^@]+)@`）。
  `curl --tlsv1.3 --ssl-no-revoke` 为 api.github.com / cloudflare **必需**；**npm registry 相反——会 HTTP 000**。
  Contents API 头写 `Authorization: Bearer <tok>`（不是 `token`）。
- deploy.mjs 挂死根因：不读 `.env.local` ⇒ 回退过期 OAuth。修法：加载 `.env.local` + 无 `WRANGLER_BIN` 时走全局 npm wrangler + `spawnSync` 8min 超时。
- `pre_deploy_check.py` 两级闸门：源改动拒、派生纯时间戳 diff 放行。**护栏报数先核口径**（检测器只是提醒非判决）。
- **Git Bash 两坑**：① `git commit` 不自动 stage 工作树删除，须显式 `git add -A`，判定用 `git ls-tree -r HEAD --name-only`；② `--message="..."` 被当 pathspec ⇒ 用 `git commit -F -` + subprocess stdin。
- **本机沙箱 Bash 的 PATH 被 shim 破坏**（`ls/cat/head/tail/grep` 全 command not found，且 SIGTERM 长命令）⇒ 用 Python `subprocess` 显式拼 PATH 驱动 `node.exe`，或直接用 `os.walk`/`re`。
- **Node spawnSync 在本沙箱对所有可执行（git/cmd/node 自身）都 EBUSY errno -4082**（Node 22.22.2 + 24.18.0 均复现；`spawn` 异步可用，`spawnSync` 全灭）⇒ `scripts/push-gitdata.mjs`（Contents API 推送）在本机跑不通，临时用 **`push_gitdata.py`**（Python 等价，纯 urllib+subprocess+curl，330 行，放 `%TEMP%`，Token 走 `--config` 头不污染 argv）替代。别信"换 Node 版本能修"。
- 临时驱动脚本一律放**仓库外**（`%TEMP%\roboparts-helpers\` 或 `%TEMP%`），否则 `pre_deploy_check.py` 拒。
- 新增 env 键必须在 `scripts/env_contract.json` 登记（L1.94 会拦）；**测试钩子优先用 CLI 参数而非 env 旋钮**。

## 四、闸门与收口纪律
- **收口提交前必须有机械证据**：跑 `scripts/check_pure_drift.py` 逐文件判 空白/时间戳/内容。起因：`auto_drift_heal.py` 原只看 `git status` 有无改动就提交成 "drift remediation" ⇒ 真内容改动被贴 drift 标签静默入库。
- **闸门放哪**：审计模式在 CI 恒"无改动"=无信号，在工作树恒把正常源改动报红=假警报 ⇒ **CI 只跑自证**，审计只挂收口路径。自证须含**真实临时 git 仓库端到端**。
- **只测绿路径的闸门等于没闸门**。范式：阳性 + 阴性 + 变异三对照（`_mutprobe.py` 7 变异全红 + 还原校验；`_gate_probe.py` 6 注入 + baseline + 1 反向误报）。**空闸门与空产物是两种故障，都要阳性对照**。
- **一个"永远 fail-closed"的引擎与写坏的引擎输出完全一致** ⇒ 只比产物必假绿。
- **同一主张要有一份判据源 + 多个消费端**：`scripts/positioning_contract.py` 是"对外自称什么"的唯一判据，两个消费者 = `ci_gate` 离线闸门 + `verify_live_numbers.py` 第四轴。
- **判据由本地源给出，不手写期望值**：手写期望的下场——临时探针报 4 处 FAIL 全是探针自己错（URL 猜错 ×2、判据过窄 ×2）。**短语判据必须族匹配**，单锚点会把合法变体判假红。
- 闸门项数一律经 `inject_readme_stats.py` 现算（`ci_gate.py --list` 行数），勿手写。**20260924 起 44 项**（新增 Pipeline 骨架+等价性+17 自证）。
- **内联在 ci_gate 里的判据也要变异自证**：先抽成纯函数（如 `_gap_doc_errors`），再对产物做
  内存级变异（不改文件——闸门先跑 builder 会洗掉文件级篡改），逐变异确认判红。
  20260924 给缺口成因分类加了 3 项变异（与 facts 漂移 / 分类不完备 / signal_axis 退回硬编码）。
- **「同型必配」只对几何规格型类型成立**（20260924）：机械法兰同标号必配；但方向性角色型
  （OUTPUT_SPIKE）同类不是「必然可装」而是「不构成互补」。`type_compat` 里**显式登记的自配对
  裁决必须优先于 reflexivity 公理**，否则登记等于没登记。
- **`verify_live_numbers.py` 四条轴**：页面数字 / llms.txt 子集口径 / 对外接口总数 / 定位口径自称面。新增对外口径须同时接进该脚本。
- **漂移核验口径**：除 `updated`/`audited_at` 外，还须认日期型值、别名键（`upstream_time`/`verified_at`）、时间戳派生摘要（`source_digest`/`entities_sha256`）、README 日期标题行。

## 五、数据层
- `meta.access` 是注入器受管区；顶层副本会失修须对账。OSS 325 缩水 >10% 拒写；verify 三态 UNKNOWN **非绿灯**。
- 机械声明率现算 **5.69%**（declared 15 + partial 10 / applicable 439）；历史 1.52%/2.76%/5.75% 三套口径已作废，**以现算为准**。
- **机械声明出处**：`source_url` 主机名必须落 `MECH_SOURCE_HOSTS` 厂商官域白名单；第三方实读出处降级写进 `source` 文本留痕。
- **单值/多值形态**：`Array.isArray(standard)` ⇒ 多值 ⇒ `matched.length>=2`。单孔位条目**必须写标量字符串**，写成 `[ISO50]` 单元素数组 = 假红。
- 标准唯一源 `govern_standard_conformance.py`；带日期/状态断言须挂 evidence + evidence_tier（白名单 host）。
- 电气：`api/electrical_interfaces.json`（EXEMPT）；免责「协议兼容 ≠ 电气兼容」已上线。actuators connector 4/220=1.8%（余不臆造）。CIS 不接。
- 合法补数据通道三条：厂商 datasheet / ISO 9409-1 查表补 `A{n}` / 用户提交带出处（`add_mechanical_interface.py` 的 `_curated()` 只留带 `source_url` 的）。
  **「开源 BOM 反喂 ingestion」做不到位**——`ingest_oss_bom.mjs` 写 `oss_components.json`，与声明率分母 `entities.json` 不相通。
- 模型能力边界：**不能读图**；用户贴图须声明无法读并请文本贴内容，绝不推测拼凑结论。

## 六、MCP 工具面
- 新增工具三处必同步：`mcp.js` TOOLS（真相源）→ `skills.meta.json` → `read_metrics.py` BUSINESS_TOOLS 白名单，再跑 `gen_skills_manifest.mjs`。工具数展示走 `_mcp_tool_names()` 现算。
- `verify_mcp_package.py`（本地 import ⊆ package.json.files ⊆ git ls-files）+ `verify_mcp_coverage.py`（stdio FILE_MAP 对账 hosted CATEGORIES）已挂 ci_gate。
  **hosted CATEGORIES 直接当 tool schema enum 用**——少列品类，凡守 JSON Schema 的客户端根本传不进。
- 公开清单三份全由 `scripts/gen_public_manifests.py` 生成，`--check` 已挂 ci_gate。Registry schema 限 description ≤ 100 字符（超了 422）。
- `.gitignore` 有 `mcp-server/` 但部分文件已跟踪 ⇒ 改/加文件用 `git add -f`；普通 `git add` 会 exit 1 但**文件其实已暂存**——别信 exit code，用 `git diff --cached --name-only` 复核。
- 官方 MCP Registry 是**快照非同步**：改仓库不更新它，须 `./.tools/mcp-publisher.exe` 发布；Ed25519 原私钥已丢失（仅公钥托管 `/.well-known/mcp-registry-auth`）⇒ 需轮换公钥后 `login http`（遇 429 未跑完）。
- npm `1.1.1` 已发（`~/.npmrc` 账号 `61960005qq`）。返 202 + 立刻 `npm view` 读旧版是 CDN 滞后（非失败）；验证要 `--cache <新目录> --prefer-online`。

## 七、计量与后端
- 边缘遥测 `_middleware.js`→KV `USER_CREDITS`，读 `read_metrics.py`；读数是**下界**（分片写互盖），只能证"至少"。
- 渠道漏斗 `?via=` + `stat:via:<src>:<detail>`，`channel_report.py` 读；非渠道注册不混入 ROI。
- `functions/api/copilot.js` 多后端路由（ECS 优先 / Agnes 次之 / 全败降级）。ECS `150.158.119.19:8420/v1` 待用户给 `ECS_API_KEY` + 定 `ECS_MODEL`（P2）。
- 支付纯虎皮椒：`/api/payment/create` → notify 验签 → 加积分 + 置 `plan=pro`。套餐唯一扣费源 `functions/api/payment/create.js`。
- agent-mail：GetMe=`alxealxe3329@agent.qq.com`，未启用自动发信。

## 八、领域数据层（各自 SoT → build → api）
- **神经控制域**：定位=不造脑不造芯片，做**脑×体之间的标准与情报层**；`neurorobotics/source.json` → `build_neurorobotics.py` → `api/neurorobotics.json`；`signal_interface.schema.json` 把机械兼容延伸到信号契约（GAP-G2）。
  诚实边界：LIF 无可塑性=无长期记忆；SNN 训练难 + 生态碎片；规模墙；连接组是死脑快照。
- **运动学域**：借鉴 PyRoki **URDF 优先数据模型**，不搬代码（Python+JAX 跑不进 Workers）。`kinematics/source.json` → `build_kinematics.py` → `api/kinematics.json`；`verify_kinematics.py` 阴阳自测挂 ci_gate。
  铁律：`max_reach_mm = Σ link_mm` 是**上界**（忽略限位/自碰撞）⇒ `unreachable` 可靠、`not_ruled_out` 保守，**禁对 not_ruled_out 宣称"可达"**。computed=0/2 属**数据缺口非算法缺陷**。
- **需求信号域**：曾对外宣称"10 条真实兼容性提问"实为 AI/LLM 软件 PR。根因三连：正则无领域锚定 + `real_signal` 写死 true + `relevance` 写死 ⇒ **fail-open**。
  判据唯一入口 `scripts/lib/demand_signal_rules.mjs`：`classifySignal()` 三态 `confirmed/unclassified/noise`，仅 confirmed 计入 `real_query_count`；`demand_scan.mjs` 与 `reflow_demand_signal.mjs` 共用，`buildActionableFixes(declRate)` 也在此（**别在消费方手写第二份**）。
  reflow 按判别层**重判 sources[]**，绝不沿用旧快照计数；旧快照靠"缺 `signal_state`"识别；`real_signal === (signal_state === 'confirmed')` 恒成立。
  **负向语境豁免铁律**：全量搜关键词会把 `reflow_note` 里"…已作废"的历史引述误判成假陈述 ⇒ 判据必须做**字段级 + 断言形态**，豁免留痕字段。
  **静默补偿陷阱**：只加下游防御会让上游回归后自测仍绿（两处 bug 互相掩盖）⇒ 入口用 `barePct()` **fail-fast 抛错**，宁可崩不可假绿。
- **build_ 脚本的算子+DAG 骨架**（20260924 落地 `scripts/pipeline/`）：借鉴 GOAI 2026 冠军 DataFlow-Agent 的建模思想（不搬依赖——它是 vLLM 重栈，进不了 Workers），零依赖纯 stdlib。
  四件套：`registry.py`（`@operator(name, stage, description)` 装饰器，重名/格式 fail-fast）/ `dag.py`（声明式步骤 + 输入引用解析 + trace）/ `stages/*.py`（每 build_ 脚本一个 stage）/ `run.py`（CLI：`list`/`ops`/`run <name>`，`--trace`/`--dry-run`/`--out`）。
  **两条硬约束**：① 算子名含 `.`（如 `gap.load_entities`），`resolve_input` 必须做「按长度降序的前缀匹配」找最长匹配的 context key——naive `str.split('.')` 会把 `gap.load_entities.items` 中的 head 判成 `gap` 而非 `gap.load_entities`；② `_summarize` 对 dict/list/set 只做「形状摘要」（keys 长度），不 dump 全量 ⇒ trace 里不会出现 PII 或大对象。
  **等价性证明是骨架价值的唯一定义**：`scripts/verify_pipeline.py` 逐字段对账 `build_X.build()` 与 `Pipeline.run('X')` 的输出——只允许 `meta.generated_at`/`meta.generated_by` 差异，其余字段全相等。**只比产物必假绿**的通用原则在这里得到实操：变异测试断言 crosscheck 能拦下聚合与 facts 的漂移。
  **已迁移**（20260924）：`gap_classification`（7 算子，样板）+ `compose_semantics`（6 算子）。verify_pipeline 23 项自测全绿。
  **未迁移**：`build_morphology_graph.py`（741 行最复杂）、`build_kinematics.py`、`build_neurorobotics.py`、`build_negative_compat.py`、`build_standard_audit.py`、`build_external_signals.py`、`build_provenance.py`、`build_derived_features.py`、`build_parameter_semantics.py`、`build_croissant.py`、`build_flange_page.py`、`build_param_page.py`、`build_articles.py`。下一批候选：`build_provenance.py` 与 `build_derived_features.py`（结构最接近 gap_classification 样板）。
  **踩坑备忘**：`registry.reset` 后 `importlib.reload` 必须覆盖**所有已注册 stage**——Python module cache 让单纯 `import` 是 no-op，多 stage 时漏一个就会丢一批算子。

## 九、外部数据源与竞品
- SwarmLabs 14 站**不接入**：`embodied-ai/entities.json` 100% 论文层（id 全 doi/arxiv/oa/pmid，part 级 0 命中）⇒ 填不上机械声明率与运动学计算；`api.swarmlabs.tools` 522；规模口径乱（子站 10k / 首页 30 万 / 推广 47k），对外引用前先核口径。
  可借鉴：记录自带 `source` + `confidence` + `tagConfidence` + `tagGap12`（缺口纪律结构化成字段），`tagGap12` 可映射为本项目 `declaration_gap`。
- 竞品：Allonic 2026-02 融资 $7.2M 后已转 3D Tissue Braiding，**不再是竞品**；Tnkr 推 Leonardo 属互补；**URDF 工具群（RoboInfra / urdf_validator / UrdfArchitect）正从相邻象限挤压**——"零件级+判定象限无人占"是 2026-08 旧判断，已过时。
- **2026-09 外部浪潮**（TrAct / Reward AI OM-1 / Seeed reBot；Flexiv MICO / ForceDelta-VLA / RAI AthenaZero / NVIDIA SONIC）：行业整体向「脑×体解耦」迁移，RoboParts 卡的兼容判定层是这条栈里**缺失的中间件**——四者全在脑/体/控制层。均非竞品，是战略顺风。落盘 `ops/results/competitive-intel-20260921.md` + `neurorobotics/GAP_MAP.md` §6（REF-8~11）+ 第 16 篇 GEO 长文。

## 十、硬骨头与保留清单
- 判据三条：**无人占位 / 我们已有半成品 / 失败可判定** → `docs/hardcore-roadmap-20260921.md`。
- 改判为做：X4 → "不抽佣"的来源引用层；X6 开源 BOM 反喂 → **缺口清单驱动的双向贡献闭环**。X2 收窄（不做 VLA 部署，但 VLA↔硬件**信号契约**归 H4）。
- 四块硬骨头：**H1** 声明率 → 30%+（数据护城河）· **H2** 来源引用层 · **H3** 转接件几何可打印可信 · **H4** 三层接口契约（机械/电气/信号级联判定）。
- **保留清单**（勿误删）：`ops/`（脚本 399 处引用）、`articles/` `content/` `3d/` `cad/` `embed/`（在线功能）、`roboparts-dataset-github/`（`sync_dataset_dist.py` 分发真相源）、`kinematics/` `neurorobotics/`（数据层）、`tasks/`（`regression.py` 白名单引用）、`.opencode/`（第三方 IDE 状态，不越界）、`.chk/` `.secrets/` `.tools/` `.uploads/`。
  20260920 已删 29 文件 / 6199 行，备份 `../cleanup-backup-robopart-20260920`（19.3 MB，不在部署面内）。

## 十一、未解 / 待办
- ops 快照混两类来源（脚本抓取 vs 人工情报笔记 20260814），reflow 按 mtime 取最新 ⇒ **机器快照会覆盖人工情报**，需加来源优先级。
- P0 真实 BOM 机械声明（applicable 439 / declared 25（declared 15 + partial 10）/ not_declared 414，现算 5.69%）。
  **20260924 缺口成因已分类**（`api/gap_classification.json`）：unpublished 350 / proprietary 5 / ambiguous 59。
  **负证据**：242 家制造商、头部 10 家仅 28.5%、14.3% 无制造商 ⇒ 抓少数厂商 datasheet **不足以解主缺口**，
  须靠用户提交 / OSS BOM 反喂 / 社区 PR。unpublished 是排除法嫌疑，非「厂商拒绝公开」的实证。
- **组合 composed=0 的真瓶颈在电气轴**（20260924 起）：351,649 对里 112 对 d=1，
  d1_bottleneck 100% 电气（判例 ACT-028 × SENS-0xx）。**旧说法「SIG 全未声明」已作废**——
  信号轴已按品类定向声明 392 条。归因一律现读 `compose_semantics.json` 的
  `aggregates.gap_distance` / `d1_bottleneck`，勿复述历史结论。
- P1 形态图 / 跨层溯源（20260923 落地）；**锚点已升 v2.2**（20260924，信号轴定向 + 缺口距离 + reflexivity 边界）。
  方向锚点是**手写文档**（无生成器写它），可直接编辑；但产物的 `anchor` 字段在生成器源串里，须改生成器。
- 已执行定位收口：6 套→1 套（`03eed33`）、LICENSE 拆 MIT + DATA-LICENSE.md（消 NOASSERTION）、GitHub description 经 API 改现算值。
  **关键坑：README 标题行与分发徽章由生成器重写（`inject_readme_stats.py`/`sync_dataset_dist.py`），手改必被覆盖 ⇒ 一律改生成器源串。** 已发布 SDK（PyPI/HF）自称 688 实体/10 品类/套餐积分全错 → 已纳入生成器重写面 + `--check`。

## 十二、研发产出（20260924 起，方向转向 R&D）

- 论文产出目录 `papers/`（20260924 建立）：
  - `papers/README.md` — 论文计划索引（P1 草稿完成 / P2 P3 大纲待写）。
  - `papers/refs-free-sci-20260924.md` — 16 篇免费/开放获取论文清单。
  - `papers/paper1-three-state-honesty.md` — P1 完整草稿（502 行）。
- **P1 核心主张**：`compose(a,b) ∈ {composed, type_error, unknown}`，
  三态裁决 + fail-closed 优先级（`unknown` 高于 `composed`）+
  reflexivity 公理边界（几何规格型 vs 方向性角色型）。
- **P1 必引 5 篇**（覆盖 5 维度）：
  [R1] Linkify（接口几何）· [R2] CAD 关系学习（装配符号）·
  [R5] ExtruOnt（工程本体）· [R7] 操作 KG · **[R10] ReconVLA（不确定性）**。
  **R10 与 RoboParts 哲学同构**：ReconVLA 让决策层显式表达「不知道」，
  RoboParts 让数据层显式表达「不知道」，两者互补成三层栈
  （数据层三态 / 推理层 KG / 决策层 UQ）。
- **P2**（大纲，待写）：缺口成因三分类 + 杠杆分析的负向证据
  （unpublished 350 / proprietary 5 / ambiguous 59；242 家制造商头部 10 家仅 28.5%）。
- **P3**（大纲，待写）：算子+DAG 骨架（借鉴 GOAI 2026 冠军 DataFlow-Agent 思想，
  零依赖纯 stdlib）+ 等价性证明作为闸门（`verify_pipeline.py` 23 项自测）。
- **论文通用纪律**：
  1. 数字现算（`facts()` / `api/*.json`），禁手写（沿用 §四纪律）；
  2. 参考文献免费优先（arXiv / MDPI / PLOS）；
  3. 不夸大贡献（`composed=0` 是诚实画像非失败；5.69% 是覆盖率地图非 benchmark）；
  4. 投稿前走锚点 §2 三问闸门（真数据 / 独特贡献 / 可复现代码）。

- **投稿路径（20260924 更新，真免费 SCIE 优先）**：用户明确「真正免费 =
  无 APC/版面费/印刷费」⇒ 排除所有强制 OA 出版商（MDPI / Frontiers / PLOS /
  Nature 系 / Hindawi 全线）；**「arXiv 预印本免费占时间戳」+「订阅制 SCIE 正式发表」
  双通道**：
  - ① **首选 Mechatronics**（Elsevier, IF 3.2 / CAS 计算机 3 区 / 机械 2 区 / 机器人 3 区；
    153 天审稿；elsarticle-num 模板；10,000 词 / 15 页；明确 "No publication fee charged to authors"）
  - ② 高影响备份 Robotics and Autonomous Systems（Elsevier, IF 5.2 / CAS 计算机 2 区；
    4-8 周审稿；Q1 竞争极激烈）
  - ③ 主题对味备份 Knowledge and Information Systems（Springer, IF 3.1 / CAS 计算机 2 区；
    KG/Ontology 方向；5 月审稿）
  - 转投顺序：Mechatronics → 6 月内无决定 → RAS → KIS → arXiv 预印本同步占时间戳。
  - **投稿版已产出**：`papers/mechatronics_submission/`（main.tex 1088 行 ~5800 词 /
    references.bib 19 条 / highlights.txt 5 bullets / cover_letter.tex / README.md），
    commit `a5bbc8b` → 远端 `e15c71e4`。所有 TODO 用 `TODO:` 前缀标记
    （作者/单位/ORCID/基金号/图表/推荐审稿人）。
  - **投稿前必做**：填 TODO → 下载 elsarticle 包 → 编译 3 次（pdflatex + bibtex + pdflatex × 2）
    → PDF 检查 → Editorial Manager 提交 Regular Article → 上传 PDF + 源文件 +
    highlights.txt + cover_letter.pdf。

- **pipeline 迁移暂缓**：2 个样板（gap_classification / compose_semantics）已够，
  剩余 13 个 build_ 脚本留待 R&D 主线定稿后再收口。
