# RoboParts 长期约定（跨会话有效）

> 压缩原则：保留「判据源在哪 / 纪律为何存在」，过程细节见 `.workbuddy/memory/YYYY-MM-DD.md` 与 `docs/`。

## 一、定位（唯一口径）
- 机器人零件兼容性判定层（vendor-neutral）。代码 MIT / 数据 CC BY 4.0。
- UVP 三态诚实——唯一会告诉你"我不知道"的数据层。
- 机器可读四件套（server.json/smithery.yaml/lhm.plugin.json/.well-known/mcp.json）比人类页面准 ⇒ 用生成器反向同步页面，不手改页面数字。
- 全站数字唯一真相源 `onboarding_block.facts()`。三层保鲜：data-rp 锚点 / 裸文本 / 子集现算。
- 受众：T1 开源构建者 / T2 集成商接口工程师（唯一付费动机）/ T3 AI Agent。

## 二、核心目标完成度判据（勿自己拍）
- `api/research_progress.json`：核心目标=锚点§1，拆 体/脑/智/链 4 维，每项带分子分母口径。
- 当前自评门控加权 63.2%（体 48.5/脑 100/智 88.2/链 50.0），权重 body40/chain30/neuron20/policy10（可争议）。
- 门控口径：核心判据为 0 ⇒ 该维度记 0 不参与平均。两个口径都报，不藏。
- 敏感性反向对照：composed 0→1000 时完成度必须上升，否则指标废。
- body→policy 链闭合（links_satisfied 0/4→1/4）：只做开源 VLA 绑定，强度三档 family/adaptable/category_only，把 adaptable 当 validated 会过度声称。

## 三、两套引擎断层 + 取证判据
- 产品面 `functions/_lib/compat_engine.js`=四维（protocol/electrical/mechanical/software）；研究层 `scripts/compose_engine.py`=三轴（mechanical/electrical/signal）。交集仅 electrical+mechanical，不互为子集 ⇒ 不能取并集合并。
- 资产没接线类故障靠显式扫引用发现，算术守卫抓不到。
- T2 单声明零收益定理：k≥2 轴 AND 收敛下，单条声明边际收益恒为 0 ⇒ "补哪条最值"是错误提法。
- 正确判据=最小可行同质集 MVC（`cohort_feasibility.json`）：K=2 即可；取证按同质集批量推送。
- 旧 P0"机械声明率→30%"已证贡献 0，降级为不做。
- 自我纠正：联合上界误标成单条边际值 ⇒ 产物自洽≠判据正确，端到端验证才暴露。

## 四、co_mount 第三种关系（composed=0 修复）
- 三段关系 A↔宿主↔B：mount_fit（法兰同型非互插）+ port_budget（位数有限）+ signal_complementary。
- 位数/针数/器件数是三个不同量；port_exhausted（装不下）与 unknown（不知道）严格区分。
- 判据扩展须配反向对照：co_mount 归零⇒门控重新生效⇒完成度回落。门控双向（不虚高不虚低）。

## 五、neuron 维曾惩罚正确行为（纠正）
- 锚点§3 负向边界禁止造脑/仿真器；neuron 改量"溯源是否诚实"（外部连接组已登记且出处可追 + 契约躯体如实标注），0%→100%。
- 不能补真躯体契约拿分（连接组→躯体映射是工程选择，非可校验事实）。判据从原始产物现算，加变异自证非永远满分。

## 六、闸门与收口纪律（★高频教训）
- 只测绿路径=没闸门。范式：阳性+阴性+变异三对照。
- ★ 一致性守卫+自称状态=自欺型闸门。须加"最坏状态必须红"+反向对照（好的改坏须判红）。
- 判据不许信产物自我声明——必须现算（子串包含会跨语义边界命中）。
- 合法≠自洽：只查取值域对"换合法值冒充语义"无效，须跨字段自洽+现算。
- 某轴长期 Tier B 且补数据升不上去 ⇒ 先疑格式表达力再疑数据量（拿真实设备逐字段试写 schema）。
- 口径对齐含字段位置；跨源标识归一须吃掉命名空间前缀。
- 两个不同问题用两个计数器；构造脚本读错字段名须 fail-fast（退出码 0 不报错最危险）。
- 删除文件禁后缀白名单反选，用精确文件名 + git status 确认。
- 诊断性结论须带口径守卫，被过度声称的诊断比没有更坏。
- 判据由本地源给出，不手写期望值（手写期望曾 4 处 FAIL 全是探针自己错）。
- 收口前跑 `scripts/check_pure_drift.py`；CI 只跑自证，审计挂收口路径。

## 七、数据层
- 机械声明出处 source_url 主机名须落 MECH_SOURCE_HOSTS 白名单。
- 单值写标量字符串、多值 Array.isArray；pinout:null 必须登记 evidence_gap（"不知道"须显式可见）。
- 合法补数据四通道：厂商 datasheet / ISO 9409-1 查表 / 用户提交带出处 / 上游开源仓 ingestion。
- 模型不能读图；用户贴图须声明无法读。

## 八、电气轴（当前唯一有效取证方向）
- electrical 是三轴 AND 收敛点。可判定对 1→15、type_error 4→78。
- 连接器类型键=(family,pins,pinout) 三元组，family 不可省（M8 是家族非类型；同针数针序可因螺纹不同不可插）。
- 取证链路缺一步白干：补证据须登记 type_compat；形态图须读它；接线键用 rp_id 非本地 id。
- rp_id 须唯一（schema_contract 唯一性校验防撞号污染）。
- 诚实缺口：一手 datasheet 未公开针序 ⇒ pinout:null+evidence_gap，不按同类推断。

## 九、部署与 GitHub
- 铁律：提交→推送→部署；推 GitHub≠上线，deploy 后必线上回探+漂移收口。
- Node spawnSync 沙箱全 EBUSY ⇒ 用 Python Git Data API（`%TEMP%\push_gitdata.py`）。curl 须 `--tlsv1.3 --ssl-no-revoke`（api.github.com/cloudflare）；npm registry 相反。
- Contents API 头 `Authorization: Bearer`；token 在 `~/.git-credentials`。
- Git Bash：须显式 `git add -A`；`--message=` 被当 pathspec ⇒ `git commit -F -` + stdin。
- 沙箱 PATH 被 shim 破坏 ⇒ 用 Python subprocess 显式拼 PATH。
- 临时驱动脚本放仓库外（%TEMP%），否则 pre_deploy_check 拒；新增 env 键须登记 env_contract.json。

## 十、MCP 与分发
- 16 工具（11 业务+5 桥接，含 get_research_progress）。新增工具四处同步：mcp.js TOOLS→skills.meta.json→read_metrics.py BUSINESS_TOOLS→agent-discovery.json。
- 分发 4 家全绿：MCP Registry/Smithery/LobeHub/Glama。判定未上架须直接 GET 详情页。
- Registry 快照非同步，须 publisher 重发；Ed25519 私钥纯 hex 64 字符。
- LobeHub 走 M2M auth 绕 OAuth。分发≠增长（29 调用 0 注册⇒别再加平台）。

## 十一、生态与目标客户
- 目标客户 Feather Robotics（feather.dev，$29,990 轮式双臂人形，Python+ROS2 Open SDK，无公开 repo）。
- 生态接入点 AgenticROS（agenticros.com，RealSense 赞助）：`npx agenticros skills install lm203688/roboparts`。
- 哲学背书 Isaac ROS 5.0 rosidl::buffer ⇒ RoboParts=零件兼容性层的 rosidl::buffer（类比非绑定）。
- 竞品：roboxdb.com（source-backed 零件数据，最像）；URDF 工具群从相邻象限挤压。Scaling：多样性>数量，P0 是加品牌不加 SKU。

## 十二、硬骨头 ROI 排序
- H1 电气取证进行中 9/16（价值转"让 co-mount 可表达"）。H2 电气类型系统扩容（H1 前置）未动。
- H3 转接件几何可信（81 判例，差真实 STEP）。H4 三层契约级联（完整链数=0）。
- H5 信号轴 schema 表达力（格式上限非数据缺口，本轮不做）。H6 商业验证（29 调用 0 注册，资源配置失衡）。
- H7 机械轴证据深度（105/126 含 proprietary，须先算 MDV 再取证）。

## 十三、论文
- 投稿版 `papers/mechatronics_submission/`（main.tex 1088 行）。仅剩用户手动 2 项 TODO_email/TODO_affiliation。
- 首选 Mechatronics（Elsevier no fee）→RAS→KIS→arXiv。纪律：数字现算/不夸大（composed=0 是诚实画像）。
- 可用 contribution：T1（AND 收敛下界）+T2（单声明零收益定理）+MVC 判据。

## 十四、2026-10-08 全面提升报告要点
- 核心判断：技术/研究完成度远高于产品/商业（L1~63% / L2~30% / L3~10%）。不是能力问题是价值主张没对齐。
- 三条战略：①完成度指标已到边际，停止继续调口径，拆三层分别度量；②最大机会=国标接口标准时间窗（一体化关节接口/模块通用信息模型国标）；③产品必须从"零件库"升级为"集成决策器"（共装查询）。
- P0 自主可执行：修 README/count 漂移+纳入 verify_live_numbers 闸门；建 golden 评估集；落 A2A SendMessage 端点；判定结果带 evidence 链；国标映射层。
- P0 需用户配合：论文投出（补邮箱+单位）；商业形态拍板（按查询/按方案收费）；接触 Feather Robotics。
- 一句话检验法沿用："这件事是在让组合变得可校验，还是在让列表变得更好看？"
