# RoboParts — 机器人零件兼容性判定层

## 1. 项目概述
- **名称**: RoboParts — 机器人零件兼容性判定层
- **定位**: 跨厂商机器人零件接口兼容性判定与开源数据层（vendor-neutral）
- **域名**: roboparts.cc
- **线上地址**: https://roboparts.cc
- **预览域（Cloudflare Pages 默认域，非正式入口，勿对外引用）**: https://robotparts-924.pages.dev
<!-- RP-STATS:START 由 scripts/inject_readme_stats.py 生成，勿手改 -->
- **数据量**：802 实体（589 实物零部件 / 101 接口规范 / 81 AI 模型软件 / 10 企业主体 / 17 市场情报）；机械接口声明率 5.69%（25/439）；开源组件 325
- **最后更新**：2026-09-21
<!-- RP-STATS:END -->

## 2. 核心目标
1. **配件模块化** — 标准化模块参数库，支持按自由度/扭矩/尺寸/协议筛选与组合
2. **接口标准化** — 对接《人形机器人模块化通用技术要求》国标，建立兼容性数据库
3. **协议标准化** — EtherCAT/CANopen/ROS2/MQTT协议栈对比、实时性能基准、跨协议桥接
4. **大模型产业化** — VLA模型（RT-2/OpenVLA/π0/GR00T N1.7/SmolVLA/π0.5/τ(0)-VLA/InternVLA-A1.5/Gemini Robotics 2）部署硬件需求与推理性能对比
5. **用户数据集成化** — 选型方案/BOM/设计文件端到端加密，保护用户习惯与隐私

## 3. 三大原则
- **自动化** — 智能选型引擎、自动BOM生成、AI兼容性匹配、一键导出采购清单
- **生态化** — 连接厂商/开发者/用户形成闭环
- **盈利化** — API 数据订阅、选型工具 SaaS、企业定制（**不做交易抽佣**：一旦抽佣，判定就不中立了）

## 4. 核心功能
- 🔧 **智能选型引擎** — 五维度评分（扭矩/速度/精度/重量/成本）多因子选型 + 多结果对比表格
- 📋 **数据质量标注** — 每个实体标注 source / confidence / last_verified
- ✅ **标准符合度** — GB模块化通用技术 / ISO 8373 / IEC 61508 / ROS2兼容状态
- 🧬 **仿生品类** — SEA串联弹性驱动器、柔性驱动器、仿生脊柱、灵巧手、人工肌肉
- 🔗 **兼容性矩阵** — 电气/机械/协议/软件四维兼容检测

## 5. 数据分类
<!-- RP-CATS:START 由 scripts/inject_readme_stats.py 生成，勿手改 -->
- **actuators**: 220 条 — 执行器（电机、谐波减速器、行星滚柱丝杠、无框力矩电机、驱动器、关节模组、灵巧手、腱绳驱动手、开源力控关节、SEA、柔性驱动器）
- **chips**: 108 条 — 芯片（AI 芯片、边缘推理加速器、MCU、FPGA、通信芯片）
- **sensors**: 95 条 — 传感器（视觉相机、六维力/力矩传感器、关节扭矩传感器、触觉传感器、磁性电子皮肤、激光雷达、IMU）
- **protocols**: 64 条 — 通信协议（EtherCAT、CANopen、ROS2、MQTT 等）
- **data_acquisition**: 46 条 — 数据采集设备（遥操作、外骨骼采集、动作捕捉、数据手套、开源具身数据集平台）
- **robot_ai_models**: 46 条 — 机器人 AI 模型（VLA 模型、世界模型、机器人基础模型）
- **interfaces**: 44 条 — 接口标准（法兰、总线、连接器标准文本）
- **llms**: 42 条 — 大模型（VLA 模型、机器人基础模型）
- **platforms**: 41 条 — 机器人平台（含开源可复现整机）
- **grippers**: 23 条 — 夹爪与末端执行器
- **flexible_actuators**: 22 条 — 柔性执行器（人工肌肉、柔性驱动器、仿生脊柱）
- **bionic_mechanisms**: 17 条 — 仿生机构（仿生关节、仿生驱动器、仿生传感器）
- **reducers**: 14 条 — 减速器（谐波、行星、RV）
- **controllers**: 4 条 — 控制器
- **structural**: 3 条 — 结构件
- **cables**: 2 条 — 线缆
- **connectors**: 2 条 — 连接器
- **pcb**: 2 条 — PCB
- **power**: 2 条 — 电源
- **integrated_joints**: 1 条 — 一体化关节模组
<!-- RP-CATS:END -->

> 本节计数由 `scripts/inject_readme_stats.py` 从 `api/entities.json` 现算注入，
> 不手写。此前它停在 8 月初快照（actuators 写 217 实 220，且 10 个品类整类缺失）
> 长达 7 周而无人发现 —— 因为总数有闸门盯着，分项没有。

## 6. 最新更新（2026-08-05）
- **开源硬件上游缺口补齐（+10，全部 Tier A 实证）** — 按语料缺口探测（而非重复灌注优先品类）定位结构性空白：腱绳传动仅 1 条、电子皮肤仅 2 条、开源力控关节模组缺失。新增灵巧手 LEAP Hand（CMU，16DoF 直驱）/ RUKA Hand（NYU，腱绳驱动），开源力控关节 ODRI Actuator（准直驱免力矩传感器）、驱动器 mjbots moteus（CAN-FD）与 VESC，磁性电子皮肤 AnySkin / ReSkin（免重标定可更换），智元 AgiBot World 具身数据集平台（对应 direction-202608 P0「智元供应链」），开源整机 Open Duck Mini / Reachy 2。**10 条全部经 scripts/verify_vendor_sources.py 真实 HTTP 实证（200 + 页面命中）升 Tier A**，可追溯率 54.42%→55.20%，实体总数 577→587
- **具身数据采集 / 边缘算力 / 国产传感器三线扩充（+33）** — 补齐月度方向中尚未兑现的 P1/P2 缺口：具身数据采集设备 15→26 条（Mobile ALOHA、Open-TeleVision、AirExo-2、Bunny-VisionPro、ACE、DOGlove、HumanPlus、FastUMI、Manus、Rokoko、诺亦腾），VLA/边缘推理加速器 +12 条（Axelera Metis、爱芯 AX650N/AX8850、黑芝麻华山 A2000、算能 BM1684X、寒武纪 MLU370-S4、瑞芯微 RK3576、SiMa.ai Modalix、Ambarella N1-655、TI AM69A、DEEPX DX-M1、后摩 M30），国产替代传感器 +10 条（柯力、安培龙、千分一、中航电测、芯动联科、华依、奥比中光 Gemini 335、图漾 FM851、禾赛 FT120、速腾 AC1），实体总数 544→577
- **国产替代索引** — 新增 import_substitution_for 字段，可直接回答「这个海外器件的国产平替是谁」
- **人形机器人供应链实体扩充（+51）** — 首次系统覆盖谐波减速器（绿的谐波 LCS/LCD/CSG、哈默纳科、来福、同川、杉川）、行星滚柱丝杠（五洲新春、恒立液压、贝斯特、秦川机床、北特、鼎智、双林、Rollvis、GSA、Ewellix、SKF、力士乐）、无框力矩电机（步科 FMK/FMC、雷赛 FM1/FM2、禾川 Hu-MDB、汇川 MX/TMB、昊志、伟创、卧龙、大族、强和、鸣志）、六维力/关节扭矩传感器（宇立 M35XX/C025XX/C075XX/M221X/M37XX、坤维 KWR-N、海伯森、鑫精诚、神源生、ME K3D、昊志）、一体化关节模组（绿的谐波、昊志、步科、雷赛、拓普、三花、兆威、拓邦），实体总数 493→544，超额完成 8 月「500+」目标
- **供应链字段体系** — 新增 supply_chain 结构化字段（tier / customers / capacity / domestic_share），支持按 Tier1/Tier2 层级与国产化率检索

## 7. 历史更新（2026-08-03）
- **Gemini Robotics 2录入** — 新增Google DeepMind Gemini Robotics 2（1.2T参数，全身智能VLA，22-DOF灵巧手操作，三件套：GR2+ER2+On-Device 2），robot_ai_models达21条
- **数据规模扩充** — 芯片95→103、传感器46→62、数据采集设备15条新增，总计493实体覆盖10大品类
- **7月VLA模型补充录入** — 新增 τ(0)-VLA（上海创智学院/智元机器人，慢思考-快执行分层架构）、InternVLA-A1.5（上海AI实验室，组合泛化）、Evo-Depth（上海交大MINT，轻量化0.9B）
- **WAIC 2026模型录入** — 新增 Hy-Embodied VLA-0.5、MiniCPM-Robot、Kairos 3.1、LingBot-VLA 2.0、Qwen-RobotManip 等5个WAIC 2026新模型
- **数据分类完善** — 新增 flexible_actuators(6条)、robot_ai_models(21条) 和 data_acquisition(15条) 独立分类，总计10大品类493实体
- **仿生机械品类** — 新增 bionic_mechanisms(9条) 独立分类，覆盖仿生关节、仿生驱动器、仿生传感器等
- **VLA模型更新** — 新增 GR00T N1.7、SmolVLA、π0.5，LLM总数达30个
- **设计画布升级** — 集成URDF Loader，支持导入URDF文件实时渲染与关节控制
- **搜索引擎升级** — 加权模糊搜索，多字段权重排序 + 匹配高亮
- **选型引擎升级** — 五维度评分系统（扭矩/速度/精度/重量/成本）+ 多结果对比表格
- **数据管线自动化** — 创建数据爬取与更新自动化脚本
- **SEO自动化** — 实现SEO元数据自动生成与管理

## 8. API
- `GET /api/entities.json` — 全部实体列表
- `GET /api/compatibility_matrix.json` — 兼容性矩阵
- `GET /api/entity/{id}` — 单个实体详情（免费层字段 + 明列被锁付费字段）
- `GET /api/search?q=keyword` — 关键词检索（可选 `category` / `limit` / `include_quarantine`）

## 9. 部署
- **平台**: Cloudflare Pages
- **项目名**: robotparts
- **线上地址（正式，对外一律引用此域）**: https://roboparts.cc
- **预览域（Cloudflare Pages 默认域，非正式入口，勿对外引用）**: https://robotparts-924.pages.dev

## 10. 安全
- API Token 已从文档中移除，请通过环境变量管理
- 旧Token已泄露，请务必在Cloudflare Dashboard轮换

## 11. 质量闸门
本仓的数字与对外发布物由脚本从唯一真相源 `api/entities.json` 现算，禁止手改。

```bash
python scripts/ci_gate.py --list   # 列出全部闸门
python scripts/ci_gate.py          # 跑全部闸门（GitHub Actions 跑的就是这套）
```

共 <!-- RP-GATES:START 由 scripts/inject_readme_stats.py 生成，勿手改 -->23<!-- RP-GATES:END --> 项：

语义索引覆盖全部实体 · 实体 schema 契约 · `mount_type` 枚举契约 ·
`standard_conformance` 覆盖率一致 · 对外数据集分发一致性 · agent-discovery 技能清单一致性 ·
MCP 品类覆盖（stdio + hosted ↔ entities.json）· MCP 包完整性 · 公开清单数字现算 ·
运动学可达性（阴阳自测 + 漂移）· 需求信号判别层（三态 fail-closed + 对外口径）·
对外 JSON 可解析 · `entities.json` meta 一致 · meta 单一真相源 · Functions 顶层安全 ·
GitHub 配置 YAML 可解析 · 无凭据泄漏 · BOM 装配次序拓扑排序 · 反馈信号回流聚合 ·
飞轮幂等 / 可恢复。

> 项数由 `scripts/inject_readme_stats.py` 现读 `ci_gate.py --list` 的实际输出行数注入。
> 此前手写「8 项」，真值已是 20 —— 少报的 12 项不是"没做"，是**没人数的**。

完整的跨文件一致性回归（七处数字同源、全站数量断言、对外表面口径）见
`python scripts/regression.py`。

改完数据需重生成派生文件：`python scripts/regen_derived.py`。

## 12. 贡献
本项目最大的缺口是**机械接口声明率**——「两个零件能不能拧到一起」多数情况答不了。
这个数字不在这里手写（见本文顶部「数据量」一行的现算值）；
补一条带出处的孔位数据，比重构算法有用得多。

- [补机械接口声明](https://github.com/lm203688/roboparts/issues/new?template=mechanical-interface.yml)（不必会写 JSON，贴出处链接即可）
- [报数据错误](https://github.com/lm203688/roboparts/issues/new?template=data-correction.yml)
- 详细规矩与最小可核验格式：[`CONTRIBUTING.md`](./CONTRIBUTING.md)
- 零件实体权威格式规范（字段表 + 可复制模板 + 闸门清单）：[`docs/part-annotation-spec.md`](./docs/part-annotation-spec.md)

唯一的硬规矩：**无出处不收**。我们宁可留着 `not_declared`，也不猜。

## 13. 许可
双轨许可：

| 对象 | 许可 | 文件 |
|---|---|---|
| 代码（`scripts/`、`functions/`、`*.js`/`*.py`/`*.mjs`、页面模板） | **MIT** | [`LICENSE`](./LICENSE) |
| 数据（`api/`、`roboparts-dataset-github/`、`/api/` 同源数据） | **CC BY 4.0** | [`DATA-LICENSE.md`](./DATA-LICENSE.md) |

两条此前写在同一个 `LICENSE` 里，GitHub 的识别器读不懂混排文本 ⇒ 仓库页
`license` 字段长期显示 `NOASSERTION`。现已拆分：`LICENSE` 只放逐字 MIT 全文
（可被识别），数据那条挪到 `DATA-LICENSE.md`。

引用数据前请知悉：本库参数为厂商公开声明值，**未经我方实测复现**；
跨厂商可直接横向比较的 A 级条目为 0 条。每条数据带 `source_tier`(A/B/C)
与 `confidence`，请据此判断可信度。

---
生成时间: 2026-08-03（章节 11–13 于 2026-08-31 补充）
