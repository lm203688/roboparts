# 机器人生态位调研：Tnkr 与同类项目的借鉴、衔接与生态定位（2026-09-05）

> 结论先行：Tnkr 与 RoboParts **不构成竞争**，是互补层位——Tnkr 是「机器人界的 GitHub」（构建协作平台），
> 其商业本质（据官方 Manifesto）是**开发者工具引流 → frontier labs 数据采集市场抽成**，不碰零件交易。
> RoboParts 的生态一环定位 = **兼容性真相层（compatibility truth layer）**，类比 npm registry 之于 GitHub：
> Tnkr 们负责「造」，我们负责「装得上」。

## 1. 调研方法与一手探测结果

- 公开面：tnkr.ai 首页/博客（Manifesto、Assembly-is-code）/explore/项目页逐页抓取。
- API 面：`api.tnkr.ai` 存在（FastAPI 风格 404 响应），但 `/openapi.json`、`/docs` 均关闭，
  根路径为占位页（"nothing to browse here" + 状态灯 "All systems operational"）。
- 鉴权探测：用户提供的 `cfut_*` token 以 `Authorization: Bearer`、`X-Api-Key`、Cookie、POST verify
  四种姿势打 `tnkr.ai/api/*` 与 `api.tnkr.ai/*`，全部 307→/login 或 404——**token 未能在公开 API 面认证**，
  疑为网页会话邀请码（beta 通过 tally.so 表单发放）。如需登录态深拆需用户提供会话 cookie。
  token 未写入任何仓库文件（已核验）。
- 项目页（`tnkr.ai/{workspace}/{slug}`，如 `open-duck-mini/open-duck-mini-v2`）结构：
  **Files / Pull Requests / Mods（混改）/ Skins / Builds（agents 实机）/ Stats（stars/agents/PRs/mods）/ Leo（AI 助手）**。

## 2. Tnkr 拆解要点

| 维度 | 事实 |
|---|---|
| 产品 | 四支柱一体：Hardware（装配指南+BOM+对接供应商）、Software、Data（运行数据回灌）、Models（VLA 部署） |
| 协作机制 | stars / PRs / **Mods（remix 硬件）** / Builds（社区实机代建,Verified 标） |
| AI | Leonardo：POV 装配视频+CAD+代码 → 自动生成分步文档（官方宣称省 95% 文档时间）；Leo 项目内助手 |
| 商业模式 | Manifesto 原文：顶部开发者工具（GitHub for Robots）→ 底部**数据采集市场**（"Uber for Devs & Robots"），frontier labs 付费，Tnkr 抽成 |
| 规模信号 | Open Duck Mini V2 97★/5 builds/3 PRs；form factor 分布：arms 10、humanoids 7、hands 6、quadrupeds 4、drones 2、bipeds 0；背书：Stanford 博士、Gradient Robotics 联创 |
| 关键理念 | 博客《Assembly Instructions Are a Programming Language》（装配指令=一等公民语言）、《Annotations》（硬件世界的 code review 评论） |
| 短板 | 自认质量管控未解（开源资源可靠性）；BOM 只是管理功能，**无兼容性推理**；beta 期邀请制 |

## 3. 生态位对照

| 平台 | 层位 | 与我们关系 |
|---|---|---|
| **Tnkr** | 构建协作平台（整机项目包：CAD/代码/数据/模型） | **互补·衔接对象**：其 BOM「connect with parts suppliers」正是我们的挂载点 |
| **LeRobot (HF)** | 运行时+数据+硬件配置（SO-101/Koch 等机型定义） | 互补：其 hardware config 的执行器/电机选型可引我们的兼容裁决 |
| **XLeRobot** | 明星开源整机（基于 LeRobot/SO-101/IKEA 车） | **真实 BOM 数据源**：官方 docs 有结构化 BOM（部件/数量/US/EU/CN/IN 四区域单价+购买链接，如 STS3215×17） |
| **AgiBot X1 / Fourier N1 / OpenLoong 青龙 / 天工** | 厂商级开源整机（BOM+STEP+SolidWorks 图纸+装机 SOP） | **真实 BOM 数据源（最高证据等级：官方仓库）** |
| **GrabCAD / Printables / Thingiverse** | CAD 模型库 | 反向分发渠道：我们生成的转接盘 STEP/STL 上架引流 |
| **URDF Hub / vendor URDF repos** | 机器人描述文件目录 | 数据源：URDF fixed joint 变换可程序化抽取安装接口候选 |
| **orobot.io** | 联盟分成零件市场（BOM 分销页，已覆盖 XLeRobot） | **竞争，不衔接**：它做分销无兼容引擎；反向印证我们差异化 |

## 4. 拿来用（Borrow）

1. **贡献闭环模式**（最高杠杆）：Tnkr 用社区贡献解决真实数据缺失，正解我们 P0（418 applicable 仅 2 declared+5 partial）。
   已出设计：`docs/contribution-loop-design.md`。
2. **BOM schema 参考**：XLeRobot 的「Part | Amount | 区域单价 | 区域购买链接」四区域表是当前开源圈事实标准，
   我们实体卡输出应兼容该心智模型。
3. **「装配指令是一等公民」**：把「转接盘怎么装」（螺栓规格/扭矩/止口对位）做成实体卡的一等区段，
   而非一段附注文字——对齐 Tnkr assembly-is-code 理念。
4. **Mods 心智**：我们的适配器生成器本质就是「给不兼容零件打 Mod」，文案与交互可借其心智。

## 5. 衔接（Integrate）

1. **对 Tnkr：成为其 BOM 的「parts supplier/compatibility 层」**
   - 输出：`api/entities.json`、`api/negative_compat.json` 已是干净 JSON——提供稳定 URL 即可被其 BOM 条目外链；
   - 嵌件：兼容检查徽章/iframe widget（给定两个 part 引用返回 direct/adapter_required + 转接盘规格）；
   - 路径：先在 Tnkr 上为 Open Duck Mini/XLeRobot 类项目提 PR（其 BOM 区引用我们的兼容数据），零门槛验证价值。
2. **对开源整机：BOM 摄取填 P0**（比等社区提交快一个量级）
   - 首批 6 源：AgiBot X1（github.com/AgibotTech/agibot_x1_hardware）、Fourier N1（fourier-grx-n1.github.io）、
     OpenLoong（openloong.org.cn / atomgit）、天工（x-humanoid.com）、XLeRobot（readthedocs BOM）、reBot Arm（Seeed）；
   - 实现：新增 `scripts/ingest_oss_bom.py`（模式对齐 ingest_oss.mjs：来源白名单+缩水拒写+evidence_tier=official_repo），
     从 STEP/BOM/手册抽取 ISO 9409-1 标号与接口声明，落 `status=declared, source=官方仓库 URL`。
3. **对 CAD 库：转接盘上架 GrabCAD/Printables**，实物反链 roboparts.cc 实体卡（GEO+外链双收益）。
4. **对 LeRobot：hardware config 选型页引用我们的裁决 JSON**（远期，待其生态对接窗口）。

## 6. 生态一环定位（战略一句话）

> 造机器人的流程 = Tnkr/GitHub（协作）→ LeRobot（运行时）→ **RoboParts（装得上：兼容裁决+转接盘）** → 上游供应商。
> 我们不抢「造」的场景，做所有「造」的玩家都绕不开的**接口真相与转接件基础设施**。

对应商业闭环：Tnkr 类平台的 BOM 条目与社区 PR 引流 → 实体卡（GEO+SEO）→ 兼容裁决 → 转接盘生成 → pro/厂商认证（虎皮椒）→ 供应商对接。

## 7. 不做清单（scope 纪律）

- 不做整机构建/混改平台（Tnkr 层位）；不做 VLA 部署；不做联盟分成分销（orobot 层位）。
- 不在无证据等级管控下开放社区声明（Tnkr 自认的质量坑，见贡献闭环设计的闸门矩阵）。

## 8. 本轮实施记录

- `docs/contribution-loop-design.md`：贡献闭环设计（#1）。
- `compatibility-viewer.html`：法兰+转接盘 3D 查看器 PoC（#3），几何数据镜像 `build_negative_compat.py` 的 9 档 canonical 表。
- token 一手探测结论见 §1；schema 对比见 §4.2 与贡献闭环设计 §3。
