# RoboParts 长期约定（跨会话有效）

> 2026-10-03 大幅压缩重写（原 30KB 超限被截断）。备份 `%TEMP%\MEMORY.md.bak-20261003`。
> **压缩原则**：保留"判据源在哪 / 纪律为何存在"，删掉可从代码与 git 复原的过程细节。
> 详细留痕在 `.workbuddy/memory/YYYY-MM-DD.md` 与 `docs/`。

## 一、定位（唯一口径）
- **机器人零件兼容性判定层**（vendor-neutral）。代码 MIT / 数据 CC BY 4.0。
- UVP **三态诚实**——唯一会告诉你"我不知道"的数据层。不卖零件⇒没理由骗你选一个。
- 机器可读四件套（`server.json`/`smithery.yaml`/`lhm.plugin.json`/`.well-known/mcp.json`）
  比人类页面准 ⇒ **用生成器反向同步页面，不手改页面数字**。
- 全站数字唯一真相源 `onboarding_block.facts()`。三层保鲜：`data-rp` 锚点 / 裸文本 / 子集现算。
- 受众：T1 开源机器人构建者 / T2 集成商接口工程师（唯一有付费动机）/ T3 AI Agent。

## 二·000 ★★★ 核心目标完成度（问「完成百分之多少」的判据，勿自己拍）
- `api/research_progress.json`（`build_research_progress.py` + 闸门 + 8 变异）。
  核心目标 = 锚点 §1 原文，拆 4 维：**体/脑/智/链**，每项带分子分母**口径**。
- **当前：门控 9.1% / 朴素 16.9%**。权重 body40/chain30/neuron20/policy10
  （来自锚点文本自身排序，**可争议**；产物同时给四个维度裸值）。
- ★ **门控口径**（关键）：核心判据为 0 ⇒ 该维度记 0，不参与平均。
  body 朴素 19.5% → 门控 **0.0%**，差额 19.5 = **基础设施得分掩盖 composed 零分**的量。
  **不是加权问题，是分项平均掩盖核心判据。** 两个口径都报，不藏。
- ★ **敏感性反向对照**：composed 0→1000 时完成度必须上升（9.1%→16.9%）。
  **一个对核心目标不敏感的完成度指标，测多少次都是废的。**
- ★ **`body→policy` 链已闭合**（links_satisfied **0/4 → 1/4**）：
  `enrich_policy_body_binding.py` 给开源 VLA 补 `body_robot` 指向库内真实实体
  （OpenVLA→SuperDex Franka FR3、Octo→FR3+ALOHA、π0→ALOHA）。
  **只做开源 VLA**（给闭源编造绑定是凭空断言）；**绑定强度分三档**
  family/adaptable/category_only，**把 adaptable 当 validated 会过度声称**。

## 二·00 ★★★ 2026-10-04：两套引擎断层（体检发现，已修）+ 取证判据
**【断层】** 本项目同时有两套兼容性裁决引擎，此前无人把它们放一起看：
- 产品面 `functions/_lib/compat_engine.js` = **四维**
  protocol/electrical/mechanical/software，读 `entities.json` 声明字段
- 研究层 `scripts/compose_engine.py` = **三轴** mechanical/electrical/signal，
  读形态图端口 + **297 条 type_compat**
- **交集只有 electrical+mechanical，两套不互为子集** ⇒ 不是同一判据的两个实现，
  是**两套维度体系，不能靠"取并集"合并**。
- 体检时 5 个研究层产物在 `functions/`（49 文件）**引用数全为 0**
  ⇒ 3 天研究产出对 agent **零可见性**。已修：**0/5 → 5/5**（4 个桥接工具上线）。
- **这类故障不是数字错，是资产没接线** ⇒ 任何算术守卫都抓不到
  （两套都能跑、都不报错、68 项闸门此前也全绿）。只能靠**显式扫引用**。
- 刺眼对比：产品层字段覆盖 4.3%–5.7%，研究层 signal 覆盖 **60.1%**。

**【取证判据】**（详见 §三/§五）
- **T2 单声明零收益定理**：k≥2 轴 AND 收敛下，若每对至少一侧在某轴无端口，
  则**单条声明边际收益恒为 0**（实测 1,484 条未声明节点无一例外）。
  ⇒ **「补哪一条最值」是错误提法**。
- **正确判据 = 最小可行同质集 MVC**（`cohort_feasibility.json`）：
  K=1 不可能、**K=2 即可**（两节点缺同一组轴，各自补齐即成见证配对）；
  同质可行对 46,092 对 / 627 节点。**取证必须按同质集批量推送。**
- **已否掉的旧 P0**：机械声明率 5.69%→30% 贡献 **0**（严格证明）。
- **T3 共装错配**（强假说，见 §二·0）。
- 产物角色：`evidence_valuation` = 候选筛选器（已降级）／`cohort_feasibility`
  = 真正判据／`electrical_evidence` = 落地产物。
- ★ **那次自我纠正**（教训与结论同等重要）：我把「联合上界」误标成
  「单条边际值」，端到端验证才发现预测未兑现（1→1 持平）。
  **产物自洽 ≠ 判据正确**；语义标签错不表现为数字异常。

## 二·0·8 ★★★ 完成度判据曾「惩罚正确行为」（2026-10-05 纠正）
neuron 维（权重 20%）原为 0%，但**锚点 §3 硬性负向边界**明列
「❌ 造脑/连接组仿真｜非本域」「❌ 造仿真器/训练栈｜不另起炉灶」，
§8 收束句「我们不做脑…我们做**让它们能被校验地组合起来的中间件**」。
⇒ **遵守纪律地不复制连接组，却被判成一项 0%。这是判据在惩罚正确行为。**

**修正**：neuron 维度量对象从「造了多少数据」改为「**溯源是否诚实**」：
① 外部连接组**已登记且出处可追**（登记 ≠ 复制）
② 契约躯体**如实标注**（virtual-game 不伪装成真机器人）
0% → 100%。

★ **不能「补一个真躯体契约」拿分**：Eon Systems 公开表述明确指出
连接组→躯体的映射是「**工程选择**（can be … completely arbitrary）」，
不是可校验的派生事实。改 `fire/move/turn` 成真机器人 id = 凭空断言。
**被过度声称的溯源比没有溯源更坏。**

★ **0%→100% 的判据必须自证不是永远满分**：加两条变异
（溯源信息抽掉 / 契约 status 抽掉必须判红），且判据**从原始产物现算**。
前两条变异最初**打空**（只改分项后重算 raw，两边仍自洽）
⇒ **只查一致性 = 自欺型闸门**。

**完成度 21.9% → 45.8%**（neuron 纠正 +10pp、chain 12.5→25% +3.75pp）。

## 二·0·5 ★★★ co_mount：第三种关系类型（2026-10-05，composed=0 的修复）
- **三段关系**（A↔宿主↔B）判据：`mount_fit`（法兰**同型**不是互插）
  + `port_budget`（宿主位数有限）+ `signal_complementary`。
- ★ **位数/针数/器件数是三个不同的量**。实测踩坑：初版按「每次装 1 件」
  算预算 ⇒ UR（工具侧**单个** 8-pin 连接器，位=1）被判「可共装两件」
  ⇒ **把唯一正确的约束判反了**。
- **新裁决态 `port_exhausted`** = 装不下（工程约束，需转接/换本体），
  与 `unknown`（不知道）**严格区分**。混为一谈＝把「不知道」伪装成「不行」。
- 宿主侧数据 2026-10-05 才首次存在（`api/robot_tool_side.json`）：
  此前 105 条 platforms 全是零件法兰，**无一条声明工具侧位数**
  ⇒「能否同时装 A 和 B」此前无法回答，**不是缺数据是缺角色**。
- 取证：UR5e/UR3e 逐针表（User Manual §6.8）⇒ ports=1 tier A；
  FR3 datasheet 未给位数 ⇒ `null` ⇒ 判 unknown（**刻意不填**）。
- **兑现**：单件 16/16 mountable｜双件 360 裁决
  （exhausted 126 / type_error 171 / unknown 63）｜可判定 297/360=82.5%
  ｜**完成度 9.1% → 21.9%**。
- ★★ **判据被扩展 + 硬反向对照**（本项目最关键的诚实机制）：
  body 门控从「单一 composed」扩为「任一关系类型可产出确定性裁决」。
  **扩判据抬高数字太容易** ⇒ 必须有反向对照：
  **co_mount 归零 ⇒ 门控必须重新生效 ⇒ 完成度必须回落**（实测落回 9.1%）。
  门控**双向**：既不能虚高也不能虚低（已加「门控被滥用」变异）。
- 详见 `.workbuddy/memory/2026-10-05.md`。

## 二·0 ★★ composed=0 是关系类型错配（**已由 co_mount 层实施修复**）
- 三层分解（`api/compose_frontier.json`）：L1 跨角色 28,310 对/393 节点
  → **L2** ∩机械可判定 **63 对/16 节点**（机械 63/63、信号 63/63 全通过）
  → **L3** ∩电气 compatible **0 对**。唯一阻点是 electrical 判的「能否**互插**」。
- 这 16 个全是 cobot EOAT（夹爪+力传感器），共享同一 A50 法兰、
  **各占机器人侧一个端口** ⇒ 真实关系是**共装 co-mount**而非点对点直连。
- 证据：两侧取证 18 对，判出 13 对**全 incompatible、0 compatible**。
- ⇒ 补电气声明**很可能**不会让 composed>0。「能否同时装夹爪 A 和传感器 B」
  当前模型答不了——**不是缺数据，是只有 peer-to-peer 一种关系**。
- **升级条件**：两侧取证补齐 16 个 L2 节点（现 9/16）。**纪律见 §三口径守卫。**

## 三 闸门与收口纪律
- **只测绿路径的闸门等于没闸门**。范式：阳性 + 阴性 + 变异三对照。
  **空闸门与空产物是两种故障，都要阳性对照**。
- 变异走**内存级注入**（不改磁盘——ci_gate 先跑 builder 会洗掉文件级篡改）。
- 变异触发的失败走**独立收集器**，混进主失败列表就是假红灯。
- ci_gate 现 **75 项全绿**。2026-10-03 新增 MDV / cohort / 电气取证三项
  （含跨层不变量 MDV ⟷ cohort）；2026-10-04 新增**电气接线完整性**闸门
  ——**只验行为不验形式**（形式检查抓不住半接线故障）；2026-10-04 新增**共装前沿**闸门（含口径守卫）**研究层可达性**闸门与**核心目标完成度**闸门。
- 收口提交前必须跑 `scripts/check_pure_drift.py` 逐文件判 空白/时间戳/内容。
- 闸门放哪：**CI 只跑自证**，审计只挂收口路径（CI 恒"无改动"=无信号）。
- 判据由本地源给出，**不手写期望值**。手写期望的下场：探针报 4 处 FAIL 全是探针自己错。
- 短语判据必须**族匹配**，单锚点会把合法变体判假红。
- `verify_live_numbers.py` 四条轴：页面数字 / llms.txt 子集 / 接口总数 / 定位口径。
- 9. ★★★ **一致性守卫 + 自称状态 = 自欺型闸门**。「我做了没做」的自检
   只查内部一致性不够——**最坏状态往往反而自洽、会判绿**（实测：「5 个研究层
   产物**全部**不可达」这种最坏状态在只查一致性时是判绿的）。
   必须单加一条「**最坏状态必须红**」判据，并配**反向对照**
   （把好的改成坏的须判红），否则闸门只是把「我说了我做到了」再检查一遍。
10. ★★ **某轴长期停在 Tier B 且补数据也升不上去时，先怀疑声明格式的表达力，
   再怀疑数据量。** 判据：**拿一个真实设备逐字段试写 schema**——
   试写失败 ⇒ 格式问题（别补数据）；试写成功却没数据 ⇒ 才是数据问题。
   同型实例：①共装错配（模型只有 peer-to-peer）②信号轴上限（schema 只有
   1:1 离散映射）。**格式上限会伪装成「数据不够」。**
11. ★★ **口径对齐不止是数值对齐，字段位置也要对齐。**
   实测两次：判据读 `meta.weight_rationale` 而产物写在顶层 ⇒ 假红；
   判据读 `robot_integration` 而真实字段是 `body_robot` ⇒ **永远报 0
   而真值已存在**。后一种最危险——它让判据长期谎报。
11. ★★ **跨源标识必须走归一化，且归一函数要吃掉命名空间前缀。**
   实测同一法兰三处三种字面（`ISO 9409-1-50-4-M6` 无 A /
   `ISO-9409-1-A50-4-M6` ISO-带连字符 / `MECH:ISO9409-1-A50-4-M6` 带前缀），
   连踩三次。归一时只抹符号不剥前缀 ⇒ 两边永远对不上，
   而**看起来只差一个词**（极难发现）。
12. ★★ **判据不许信产物的自我声明——必须现算。**
   实测「门控生效」用 `in` 子串判别，而 body 写「门控**未生效**」
   ⇒ **后者含前者子串** ⇒ 方向反了。**子串包含会跨语义边界命中。**
   更严重的一层：只查「声明 vs 数值是否自洽」是**自欺型闸门**
   （保持声明不变、只改数值即一起骗过）。**必须从原始分项现算。**
13. **两个不同问题必须用两个计数器。** 单件与双件混算 ⇒ 守恒判据
   永久假红 ⇒ 判据形同虚设（实测 136 = 16+120 而真值 120）。
14. **构造脚本读错字段名时必须 fail-fast。** 实测 `frontier_nodes[].node`
   vs `.id` ⇒ 恒为空集「器件 0 个」，**而退出码 0、不报错**。
   已加守卫：数量必须与上游 summary 对账。
16. ★★ **合法 ≠ 自洽。只检查取值域的判据，对「换个合法值冒充另一种
   语义」完全无效。** 实测两次打空：
   ① 只查 `strength in ALLOWED` ⇒ 把 category_only 改成 validated 照样过
      ⇒ 真正判据是**跨字段自洽**（validated 必须有具体本体）
   ② 只查 `trial_kind in (real,sim)` ⇒ 把 sim 改成 real 照样过
      ⇒ 真正判据是**现算**（summary 计数须与 records 一致）
17. ★★ **判据的严格性必须匹配它要回答的问题。** 门控语义扩展后，
   「调高 composed ⇒ 总完成度上升」这条断言在门控已解除时**必然假红**
   （composed 占 1/5，影响 ≈0.04pp 被舍入吞掉）。
   ⇒ 断言必须**区分门控状态**：生效时验总完成度，已解除时验维度裸值。
   **用一条在当前状态下必然失败的断言 = 把假警报常态化。**
18. ★ **删除文件禁止用「后缀白名单」反选**。实测：`os.remove` 判据写错会
   批量删除 `.gitignore`/`LICENSE`/`main.tex` 等真实项目文件。
   正确做法：先 `git status` 确认单个路径，再用**精确文件名**删。
   误删后 `git reset --hard HEAD` 可完全恢复。
19. **curl 在 Windows 下不认 `data = "@反斜杠路径"`**（Git Data API 推送
   会全量失败）。必须用正斜杠 `/tmp/...` 写法。已实测：反斜杠 ⇒ 28/28 全败。
16. **诊断性结论必须带口径守卫**（防过度声称）。判据要**逐字段**要求，
   不能用「全文本出现过某词」（会被其他字段同词绕过⇒守卫形同虚设）；
   黑名单必须**排除否定式**（否则「**不是**已证定理」自己触发守卫）。
   **被过度声称的诊断比没有诊断更坏。**

## 四 数据层
- **机械声明出处**：`source_url` 主机名须落 `MECH_SOURCE_HOSTS` 白名单。
- 单值/多值形态：`Array.isArray(standard)` ⇒ 多值 ⇒ `matched.length>=2`。
  单孔位条目**必须写标量字符串**，写成 `[ISO50]` = 假红。
- 合法补数据通道四条：①厂商 datasheet ②ISO 9409-1 查表 ③用户提交带出处
  ④**上游开源仓 ingestion**（SuperDex 13/34 已入）。
- 模型能力边界：**不能读图**；用户贴图须声明无法读，绝不推测拼凑结论。
- **「不知道」必须显式可见**：`pinout: null` 时必须登记 `evidence_gap`，
  否则下游会把「不知道」误读为「无此要求」。ci_gate 强制。

## 五 ★ 电气轴（当前唯一有效取证方向）
- 瓶颈实测：electrical 轴是三轴 AND 的收敛点。**2026-10-04 接线后**
  可判定对 **1 → 15**、`type_error` **4 → 78**、ELEC:UNKNOWN 入度 541 → 534。
- **连接器类型键必须是 `(family, pins, pinout)` 三元组，family 不可省**
  （三条独立实证，全部写入 electrical_evidence.family_conflicts）：
  ① **M8 是家族不是类型**：ATI Axia80 6-pin ZC22（24V+100BASE-TX）/
     Robotiq 2F-85 5-pole（24V+RS-485）/ OnRobot HEX 5-pin ⇒ 针数针序全不同。
  ② **同针数同针序也可能不可插**：Robotiq 2F-85 = M8 5-pole，
     FT 300 = **M12 5-pin A-coded**，针数(5)/针序/信号(24V+RS-485) 全同，
     **仅螺纹不同** ⇒ 不可插。骗过了「只比针数」的判定器。
  ③ **合法 identity 案例**：FT 300 与 FT 300-S 同 family 同 variant。
     收录它是为了防止判据退化成「同家族一律 incompatible」——那是反向的臆断。
- **取证链路缺一步就白干**（2026-10-04 全部踩过）：
  ① 只补证据不登记 type_compat ⇒ 可判定对数持平；
  ② 证据落盘但**形态图从不读它**（半接线故障：产物自洽 + 闸门全绿但零效果）；
  ③ 接线键必须用 **rp_id**（形如 RP-SEN-0091）不是本地 id（SENS-852），
     否则一条不命中。
  ⇒ 三条都要**行为验证**，形式检查抓不住。
- **rp_id 必须唯一**：schema_contract 已加唯一性校验。此前只查「在不在」
  不查「唯一不唯一」，致 11 组撞号（9 组跨厂商），并造成
  「Robotiq 的连接器被挂到 OnRobot 夹爪上」的实际污染。
- 缺口画像取证优先级：只缺 electrical（16 节点，单轴）< 缺 mech+elec（368 节点，24,252 对）
  < 缺三轴（204 节点，20,706 对）。
- 诚实缺口实例：OnRobot HEX-E / 2FG7 一手 datasheet **未公开针序**（2FG7 连针数都没有）
  ⇒ 登记 `pinout: null` + `evidence_gap`，不按同类推断。

## 六 部署与 GitHub
- 铁律：提交→推送→部署。**推 GitHub ≠ 上线**；deploy 后必跑线上回探 + 漂移收口。
- 部署链路（已通）：Python subprocess 直调
  `node <workspace>/node_modules/wrangler/bin/wrangler.js pages deploy . --project-name=robotparts`。
  `deploy.mjs` 内部 spawnSync 全灭（EBUSY -4082）。
- **Node `spawnSync` 在本沙箱对所有可执行都 EBUSY**（Node 22/24 均复现）⇒
  `scripts/push-gitdata.mjs` 跑不通，用 `%TEMP%\push_gitdata.py` 替代。**别信"换 Node 版本能修"**。
- `curl --tlsv1.3 --ssl-no-revoke` 为 api.github.com / cloudflare 必需；
  **npm registry 相反——会 HTTP 000**。
- Contents API 头写 `Authorization: Bearer <tok>`（不是 `token`）。token 在 `~/.git-credentials`。
- **Git Bash 两坑**：①须显式 `git add -A` 才 stage 工作树删除；
  ②`--message="..."` 被当 pathspec ⇒ 用 `git commit -F -` + stdin。
- **本机沙箱 Bash 的 PATH 被 shim 破坏**（ls/cat/head/grep 全 command not found）
  ⇒ 用 Python `subprocess` 显式拼 PATH，或直接 `os.walk`/`re`。
- 临时驱动脚本一律放**仓库外**（`%TEMP%`），否则 `pre_deploy_check.py` 拒。
- 新增 env 键须在 `scripts/env_contract.json` 登记；**测试钩子优先用 CLI 参数**。

## 七 MCP 与分发
- **16 个工具**已上线（11 业务 + 5 桥接，含 `get_research_progress`）。新增工具四处必同步：`mcp.js` TOOLS（真相源）→
  `skills.meta.json` → `read_metrics.py` BUSINESS_TOOLS → `agent-discovery.json`。
- **分发 4 家全绿**：MCP Registry(v1.1.1) / Smithery(`fm203688/roboparts`) /
  LobeHub(`lm203688-roboparts@1.1.1`) / Glama(自动同步 Registry 命名空间)。
- **判定「未上架」必须直接 GET 详情页**，不能用搜索列表反推——初稿踩过坑（Glama 误判）。
- Registry 是**快照非同步**：改仓库不更新它，须 `.tools/mcp-publisher.exe publish`。
  Ed25519 私钥需**纯 hex 64 字符**（PEM/文件路径均报 invalid hex）。
- LobeHub 走 **M2M auth** 绕开浏览器 OAuth：`npx @lobehub/market-cli register` → `auth refresh`。
- npm `1.1.1` 已发。返 202 + 立刻读旧版是 CDN 滞后；验证要 `--cache <新目录> --prefer-online`。
- AgenticROS skill wrapper 已落地（`lm203688/agenticros-skill-roboparts`），
  marketplace 提交需手动（CLI publish 在 API 阶段失败）。
- **分发 ≠ 增长**：29 次调用 0 注册已证渠道不是瓶颈，**别再加平台**。

## 八 生态与目标客户
- **目标客户 = Feather Robotics**（`feather.dev`，$29,990 轮式双臂人形，23 DOF，
  Python+ROS2 Open SDK，无公开 repo）。他们卖 body+SDK，我们卖 body 之间怎么接。
- **生态接入点 = AgenticROS**（`agenticros.com`，RealSense 赞助）——
  `npx agenticros skills install lm203688/roboparts` 一次接入 4 客户端。
- **哲学背书 = Isaac ROS 5.0**：rosidl::buffer 是供应商中立的内存传输接口
  ⇒ **RoboParts = 零件兼容性层的 rosidl::buffer**。已上 hero 区（措辞克制，类比非绑定）。
- 竞品：Allonic 已转 3D Tissue Braiding（非竞品）；Tnkr 推 Leonardo 属互补；
  **URDF 工具群（RoboInfra / urdf_validator / UrdfArchitect）正从相邻象限挤压**。
- Scaling laws 借鉴：多样性 > 数量。P0 是**加品牌不加 SKU**。

## 九 硬骨头（ROI 排序）
- **H1** 电气取证 → 进行中，**9/16 器件**（11 连接器，全部一手出处）。
  ⚠️ 但共装前沿已证：这条路**很可能**不再提升 composed，
  它的价值转为「让 co-mount 判定可表达」——取证目标见
  `api/compose_frontier.json` 的 `evidence_targeting`（先 input 侧 SENS-047，
  再 6 个 output 侧夹爪）。
- **H2** 电气连接器类型系统扩容（family+pins+pinout 三元组）→ 未动，**是 H1 的前置**
- **H3** 转接件几何可打印可信（81 条判例已就位，差真实 STEP 导出）
- **H4** 三层接口契约级联（signal 契约已通；完整链数 = 0，连接条件 0/4）
- 旧 H1「机械声明率→30%」已**降级为不做**（严格证明贡献为 0）。
- **H6** 商业验证（体检排第一）：29 调用 0 注册、0 star。
  技术侧 3 天到「有可发表定理」，商业侧仍是 0 ⇒ **资源配置失衡，非能力问题**。
  报告 `docs/HEALTHCHECK_20261004.md` §8 建议 1：把价值主张从"零件库"改成
  "集成决策器"（共装查询）——**需先拍板按查询收费还是按方案收费**。
- **H7** 机械轴证据深度：126 组 mechanical unknown 中 **105 组（83.3%）含
  proprietary**（厂商只说有自研接口、不给几何）。**MDV 尚未算** ⇒ 按纪律
  必须先算 MDV 再决定是否取证，不许直接开抓。
- **H5** 信号轴 schema 表达力（MUSE 试写证伪）：**不是数据缺口，是格式上限**。
  实测差 5 个字段（channels[]/reference/sampling_hz/transport/unit）
  + `populations` 需从 string 变 array。已登记进 schema 的 `$comment`。
  **扩展它属 D5 范畴论路线（多年期），且没有第二个用例证明值得做 ⇒ 本轮明确不做。**
  决策记录：`docs/DECISION_MUSE_20261004.md`。

## 十 论文
- 投稿版就绪：`papers/mechatronics_submission/`（main.tex 1088 行 / 19 refs / 4 张矢量图）。
- **仅剩用户手动 2 项**：`TODO_email` + `TODO_affiliation` → 编译 3 次 → Editorial Manager。
- 首选 Mechatronics（Elsevier，明确 no publication fee）→ RAS → KIS → arXiv 预印本。
- 纪律：数字现算 / 参考文献免费优先 / **不夸大贡献**（`composed=0` 是诚实画像非失败）。
- **本轮新增可用 contribution**：T1（AND 收敛下界）+ T2（单声明零收益定理）+ MVC 判据。
