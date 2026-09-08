# 开源平台扫描与借鉴研发报告（四目标深化）· 2026-09-08

> 延续 `docs/opensource-scan-20260907.md`（step.parts 互补落地）。本次按用户指定深挖四个目标：
> **CLAP（共享世界模型）/ Robotis OMY（OpenManipulator）/ Open Duck Mini + viewer / Tnkr 深化**。
> 全部结论基于一手 Web 核实（2026-09-08），不臆造。

---

## 0. 一句话结论

| 目标 | 真实定位（核实） | 与 RoboParts 关系 | 处置 |
|---|---|---|---|
| **CLAP** | Princeton 跨本体动作条件视频世界模型（arXiv 2608.27406，已开源） | 策略/感知基础模型，**非零件库** | 概念启发层（学习层），不研发进来 |
| **Robotis OMY** | 基于 Dynamixel X 系列智能执行器的教育/研究机械臂 | 执行器已在库，机械接口待补 | **做衔接**：升 partial + 新增 horn→ISO 接口对 |
| **Open Duck Mini** | ~$400 双足，14× Feetech STS3215 + 2× SG90 | 核心执行器已在库（feetech 69 条） | **做衔接**：作为参考构型样板 |
| **Tnkr** | 机器人界 GitHub（统一项目包 + remix + 数据贡献闭环 + Leonardo） | 缺「机械接口兼容性判定」层 | **成为生态一环**：参考构型即接入内容 |

**核心判断**：四个目标里，真正能"研发过来"的是 **Robotis OMY 的机械接口补录** 与 **Open Duck Mini / OMY 作为参考构型样板**；**Tnkr 是 RoboParts 应主动衔接的下游生态**（而非对手）；**CLAP 与零件兼容平台正交**，仅作概念参考。

---

## 1. CLAP —— 共享世界模型（概念启发，不借鉴研发）

- **出处**：omni-CLAP/CLAP，Princeton（Kechen Liu、Ola Shorinwa），arXiv:2608.27406（2026-08-27），代码/模型全开源，项目站 omni-clap.github.io。
- **做了什么**：用「末端执行器位姿 / 语言 / 潜动作」三套动作表示把人类视频、单臂、双臂、人形（DROID/Bridge/YAM/G1）训进**同一个动作条件视频世界模型**，先学潜动作物理先验、再落到末端执行器坐标，实现跨本体零样本泛化（RTX 3060 即可本地推理，<12GB VRAM）。
- **与我们的关系**：RoboParts 解决的是**机械层跨本体接口**（让不同机器人共用同一套螺栓/法兰标准）；CLAP 解决的是**学习层跨本体接口**（让不同机器人共用同一套运动物理先验）。二者正交、互补，**没有直接可复用的代码/数据**进入一个零件兼容平台。
- **结论**：**不研发进来**。仅作为"跨本体归一化"这一产品哲学的佐证——我们做机械接口归一化，CLAP 做策略接口归一化，叙事上可并提，但不投入工程。

---

## 2. Robotis OMY / OpenManipulator —— 执行器已在库，机械接口待补

- **核实事实**（emanual.robotis.com / en.robotis.com，2026-09-08）：
  - OpenManipulator 家族（P/X/Y）均基于 **Dynamixel X 系列智能执行器**（集成电机+控制器+编码器+总线）。
  - 代表型号 **XM430-W350-T**：4.1 N·m@12V、82g、28.5×46.5×34mm、TTL/RS485、DYNAMIXEL Protocol 2.0；**XL430-W250-T**：1.5 N·m@12V、57g、同尺寸。
  - **前法兰经 horn（X430 标准 horn HN12-N101）输出**；X/XL/XH430 采用**相同机械结构**；空心背壳走线，JST 连接器（区别于旧款 Molex）。
  - horn 螺栓圈为 **Robotis 私有尺寸，非 ISO 9409-1**。
- **我们库现状**：`api/actuators.json`（220 条策展库）**已含 4 个 ROBOTIS 条目**（XM540 / XM430-W350 / PH54 / 20-DOF 手），但它们的 `mechanical_interface` 全是 `not_declared`。
  - 反观外部 `step.parts` 索引（339 条）**Robotis/Dynamixel = 0**——这是 step.parts 的覆盖盲区，不是我们库的缺口。
- **已落地动作**：
  1. 将 **ACT-002（XM430-W350-T）** 的 `mechanical_interface` 由 `not_declared` 升为 **`partial`**，注入 emanual 公开事实（horn HN12-N101、X 系列同结构、28.5×46.5×34mm、空心背壳 JST），**PCD/孔径如实留待实物确认**（不臆造）。
  2. 在 `api/reference_builds.json` 标注 **adapter 机会**：adapter-generator 现有 A20–A250 九档之外，可新增「**X-series horn ↔ ISO 9409-1 法兰**」第十类接口对，解锁「Dynamixel 臂 + 标准工具快换」场景。

---

## 3. Open Duck Mini + viewer —— 参考构型样板

- **核实事实**（apirrone/Open_Duck_Mini GitHub、orobot.io、deepwiki，2026-09-08）：
  - ~42cm 双足，BOM < $400，Onshape 参数化 CAD，44+ 个 3D 打印件（PLA 15% / 脚 TPU）。
  - **14× Feetech STS3215 串行总线伺服**（7.4V、19.5 kg·cm）+ **2× SG90/FS90 微型舵机**。
  - 电子：Raspberry Pi Zero 2W、BNO055 IMU、Waveshare 总线伺服驱动板、2×18650、5V UBEC、4× SS-10 微动开关。
  - 机构：**M3 热熔嵌件**全机模块化、**3× 608ZZ 轴承**（8×22×7，ISO 15 尺寸系列）、M3 螺丝 + 螺纹胶。
  - **viewer**：orobot.io 提供 three.js 式 STL 在线查看器（"View in 3D"）；社区已有 Tnkr build guide。
- **与我们的关系（强）**：
  - 核心执行器 **Feetech STS3215 已在库**（step.parts 的 `feetech` 家族 69 条）；SG90 属通用舵机已收录 → **参考构型可直接映射到我们的零件库**。
  - 608ZZ 是 ISO 标准轴承，M3 嵌件/螺丝属 step.parts 白名单（2,118 紧固件）→ 紧固/轴承类覆盖良好。
  - viewer 技术（three.js STL）与我们的 `compatibility-viewer.html` 同源，可复用范式（已记录，未重复造轮子）。
- **已落地动作**：将 Open Duck Mini v2 写入 `api/reference_builds.json` 作为第二条参考构型，逐件映射 RoboParts 分类并标注机械接口 partial。

---

## 4. Tnkr 深化 —— 从"互补"升级为"成为生态一环"

- **深化事实**（tnkr.ai，2026-09-08 核实）：
  - 定位"机器人界 GitHub / Where the World Builds Robots"，统一**硬件+软件+数据+模型**四类要素于一个项目包。
  - 核心机制：**remix 重建**（一键复现他人机器人并改进）+ **数据贡献闭环**（部署机器人→回收运行数据→训练更好模型）+ **Leonardo AI**（把装配 POV 视频+CAD+代码转成逐步文档）+ **BOM 管理与零件供应商直连** + Onshape/SolidWorks/GitHub 集成。
  - 已聚集四足/双足/机械臂等开源项目（含 CubeBot、Open Duck Mini 社区 build guide）。
- **关键判断（升级）**：Tnkr 的 **BOM 管理缺「机械接口兼容性判定」这一层**——它管"清单与供应商"，不管"这个零件能不能接到那个法兰上"。这**恰好是 RoboParts 的定位**。因此 Tnkr 不是对手，而是 RoboParts 应主动衔接、并成为其生态一环的**下游协作网络**。
- **对 RoboParts 的三条加持路径**：
  1. **参考构型即接入内容（做衔接→成为一环）**：把 OpenManipulator / Open Duck Mini 这类 Tnkr 社区热门构型，做成**带 RoboParts 兼容性判定的可重建包**（即本次 `reference_builds.json`），作为进入 Tnkr 式贡献工作流的入口内容。
  2. **数据贡献闭环对齐（机制借鉴）**：Tnkr 验证了"部署→回收数据→训练"的社区飞轮。RoboParts 既有 `docs/contribution-loop-design.md`（GitHub PR 流 + evidence_tier 四级闸门），可直接采用 Tnkr 的"数据贡献指南（data contribution guidelines）"范式，把"真实 BOM 机械声明"包装成社区可贡献任务（直击 P0 缺口）。
  3. **Agent-native 差异点（我们独有）**：Tnkr 是"人/Web 协作"，RoboParts 已有 MCP server + copilot（`functions/api/copilot.js`）。以"兼容性判定 MCP 工具"作为 Tnkr 类平台的机器可读接口层——这是 Tnkr 没有、我们已有的护城河。

---

## 5. 本次落地交付物

| 文件 | 类型 | 说明 |
|---|---|---|
| `api/reference_builds.json` | 新增 API | 两条参考构型（OMY + Open Duck Mini v2），逐件映射分类 + 机械接口 partial + Tnkr/CLAP 洞察 |
| `reference-builds.html` | 新增页面 | 参考构型查看器（同源拉取 JSON，展示 BOM→分类覆盖、兼容性、衔接洞察） |
| `api/actuators.json` (ACT-002) | 数据升级 | XM430-W350-T 机械接口 not_declared → partial（emanual 公开事实，PCD 留待实物） |
| `docs/opensource-scan-20260908.md` | 本文档 | 四目标分类与优先级 |

## 6. 优先级行动（收敛）

- **P1**：adapter-generator 新增「Dynamixel X-series horn ↔ ISO 9409-1 法兰」接口对（第十类），解锁 Dynamixel 臂+标准工具。
- **P1**：ACT-002 等 ROBOTIS 条目 mechanical_interface 升 partial（本次已做 1 条，余 3 条待补：XM540/PH54/20-DOF 手）。
- **P2**：参考构型沉淀为模板，发布到 Tnkr 式贡献社区作为 RoboParts 入口内容；采用"数据贡献指南"范式驱动 P0 真实 BOM 声明。
- **P3**：608ZZ 等标准轴承纳入 bearings 子类覆盖核查；Open Duck Mini 的 608ZZ 是否本库收录需确认。

## 7. 诚实边界（不臆造项）

- HN12-N101 的精确 PCD/孔径：公开 emanual 未列，**未填入数值**，仅标 partial + gap。
- Open Duck Mini 舵机选型存在多方案（Feetech STS3215 / MG996R），本文取 v2 主流 Feetech 方案并标注来源快照日期。
- CLAP 不进入工程；仅作产品哲学佐证。

---

## 8. 实施记录（2026-09-08 追加）

用户授权"全面实施"后当轮落地：

- **P1✅ mi 升级**：ACT-001 / ACT-002 / ACT-003 / CTRL-005 / GRIP-015 五条 ROBOTIS 条目
  mechanical_interface 由 not_declared 升 partial（`scripts/upgrade_robotis_mi_20260908.py`，
  官方商店页 / e-Manual / UR 版手册一手核实）。**ACT-robotis-20dof-hand 无公开安装声明，
  保持 not_declared（不臆造）**——修正本文 §6 中"余 3 条待补"的估算：逐条核实后为 5 条可升、1 条不可升。
- **P1✅ 第十类接口**：`mechanical_interfaces.json` 新增 `robotis_x_horn` 专有接口段
  （PROPRIETARY-ROBOTIS-XHORN），登记 X 系列 horn / P 系列 FRP54 框架一手事实与
  adapter_required 判定；horn PCD 官方未公开，标 `pending_verification`。
  `adapter-generator.html` 新增第 10 档「ROBOTIS Horn（专有·几何待实测）」引导项
  （不预填几何，选中提示按官方图纸实测）。`negative_compat` 几何穷举（9 档 ISO）不受影响。
- **声明率更新**：机械接口有线索率由 1.67% → **2.76%**（12/435，declared 2 + partial 10），
  经 `regen_derived.py` 全量再生，meta.access honest_limits 全站同步。
- **P2 启动**：Tnkr 式贡献发布包已沉淀为 `docs/tnkr-publish-kit.md`（RB-OMY / RB-ODM
  双包 + 投递 runbook）；tnkr.ai 实际发布需用户账号（硬阻塞）。
