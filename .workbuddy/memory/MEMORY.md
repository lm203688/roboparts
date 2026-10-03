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

## 二 ★ 2026-10-03 最重要的发现（改变了项目取证方向）
- **单声明零收益定理（T2）**：k≥2 轴 AND 收敛下，若每个配对至少有一侧在某轴无端口，
  则**单条声明的边际可判定收益恒为 0**。实测全库三轴 1,484 条未声明节点无一例外。
- **正确判据 = 最小可行同质集（MVC）**：`api/cohort_feasibility.json`。
  K=1 不可能，**K=2 即可**——两节点缺同一组轴，各自补齐即构成见证配对。
  同质可行对 **46,149 对 / 636 节点**。
- **工程纪律**：取证**必须按同质集批量推送**，零散补单个器件永远不产生效果。
- **已否掉的旧 P0**：机械声明率 5.69%→30% 对可判定配对数贡献 **0**（严格证明）。
  mechanical / signal 轴 573 / 261 个未声明节点零贡献率 **100%**。
- **产物角色划分**：`evidence_valuation.json` = 候选节点筛选器（**已降级**）；
  `cohort_feasibility.json` = 真正的取证判据；`electrical_evidence.json` = 落地产物。

### 这次自我纠正的教训（同等重要）
1. 我先算出「16 个单条高收益目标」并给了取证清单，**端到端验证发现是错的**：
   单独注入后电气可判定对数 1→1 持平。根因：MDV 把「联合上界」（对端用类型全集兜底）
   误标成「单条边际值」。
2. **产物自洽 ≠ 判据正确**。语义标签错不会表现为数字异常，算术守卫抓不住，
   必须靠端到端行为验证。
3. **闸门断言强度不看它抓不抓得住「错误」，要看抓不抓得住「缺失」**。
   实测：删掉一个已核实器件，闸门竟未判红（剩 3 条仍满足「每条都有出处」）。
   已修：加 `coverage.evidenced_now` 现算校验。
4. **任何"补一条最值"的问题提法，先验证它是否真能兑现，再往外说。**

## 三 闸门与收口纪律
- **只测绿路径的闸门等于没闸门**。范式：阳性 + 阴性 + 变异三对照。
  **空闸门与空产物是两种故障，都要阳性对照**。
- 变异走**内存级注入**（不改磁盘——ci_gate 先跑 builder 会洗掉文件级篡改）。
- 变异触发的失败走**独立收集器**，混进主失败列表就是假红灯。
- ci_gate 现 **61 项全绿**。本轮新增 3 项：MDV / cohort / 电气取证，
  含跨层不变量（MDV 16 个候选 ⟷ cohort 可行集，16/16 命中）。
- 收口提交前必须跑 `scripts/check_pure_drift.py` 逐文件判 空白/时间戳/内容。
- 闸门放哪：**CI 只跑自证**，审计只挂收口路径（CI 恒"无改动"=无信号）。
- 判据由本地源给出，**不手写期望值**。手写期望的下场：探针报 4 处 FAIL 全是探针自己错。
- 短语判据必须**族匹配**，单锚点会把合法变体判假红。
- `verify_live_numbers.py` 四条轴：页面数字 / llms.txt 子集 / 接口总数 / 定位口径。

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
- 瓶颈实测：electrical 轴可判定对 **1 对 / 213,531**（密度 0.0005%），是三轴 AND 的收敛点。
- **「M8」不是一个类型，是一个家族**（本轮核心发现，已写入产物 headline）：
  ATI Axia80 = 6-pin ZC22（24V+100BASE-TX）/ Robotiq 2F-85 = 5-pole（24V+RS-485）/
  OnRobot HEX = 5-pin。三者针数针序全不同，**物理不可互插**。
  ⇒ 类型系统必须用 `(family, pins, pinout)` 三元组，按 family 匹配必误判。
- **取证前置条件**：只补证据**不**登记 `type_compat` ⇒ 可判定对数持平（探针 7 实测）。
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
- **11 个工具**已上线。新增工具四处必同步：`mcp.js` TOOLS（真相源）→
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
- **H1** 电气取证（唯一有效方向，cohort 清单现成）→ 进行中，本轮 4/16
- **H2** 电气连接器类型系统扩容（family+pins+pinout 三元组）→ 未动，**是 H1 的前置**
- **H3** 转接件几何可打印可信（81 条判例已就位，差真实 STEP 导出）
- **H4** 三层接口契约级联（signal 契约已通；完整链数 = 0，连接条件 0/4）
- 旧 H1「机械声明率→30%」已**降级为不做**（严格证明贡献为 0）。

## 十 论文
- 投稿版就绪：`papers/mechatronics_submission/`（main.tex 1088 行 / 19 refs / 4 张矢量图）。
- **仅剩用户手动 2 项**：`TODO_email` + `TODO_affiliation` → 编译 3 次 → Editorial Manager。
- 首选 Mechatronics（Elsevier，明确 no publication fee）→ RAS → KIS → arXiv 预印本。
- 纪律：数字现算 / 参考文献免费优先 / **不夸大贡献**（`composed=0` 是诚实画像非失败）。
- **本轮新增可用 contribution**：T1（AND 收敛下界）+ T2（单声明零收益定理）+ MVC 判据。
