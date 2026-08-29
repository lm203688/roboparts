# RoboParts — 仿生机器人生态平台

## 1. 项目概述
- **名称**: RoboParts — 仿生机器人生态平台
- **定位**: 仿生机器人模块化选型与设计生态平台
- **域名**: roboparts.cc
- **线上地址**: https://roboparts.cc
- **预览域（Cloudflare Pages 默认域，非正式入口，勿对外引用）**: https://robotparts-924.pages.dev
- **数据量**: 747实体（217执行器 · 90传感器 · 108芯片 · 64协议 · 37接口 · 42大模型（含VLA） · 46机器人AI模型 · 41平台 · 46数据采集设备 · 21柔性执行器 · 9仿生机械 · 8夹爪 · 2连接器 · 1一体化关节模组 · 3减速器 · 3控制器 · 3结构件 · 2线缆 · 2电源 · 2PCB）
- **最后更新**: 2026-08-05

## 2. 核心目标
1. **配件模块化** — 标准化模块参数库，支持按自由度/扭矩/尺寸/协议筛选与组合
2. **接口标准化** — 对接《人形机器人模块化通用技术要求》国标，建立兼容性数据库
3. **协议标准化** — EtherCAT/CANopen/ROS2/MQTT协议栈对比、实时性能基准、跨协议桥接
4. **大模型产业化** — VLA模型（RT-2/OpenVLA/π0/GR00T N1.7/SmolVLA/π0.5/τ(0)-VLA/InternVLA-A1.5/Gemini Robotics 2）部署硬件需求与推理性能对比
5. **用户数据集成化** — 选型方案/BOM/设计文件端到端加密，保护用户习惯与隐私

## 3. 三大原则
- **自动化** — 智能选型引擎、自动BOM生成、AI兼容性匹配、一键导出采购清单
- **生态化** — 连接厂商/开发者/用户形成闭环
- **盈利化** — API订阅、选型工具SaaS、模块交易佣金、企业定制

## 4. 核心功能
- 🔧 **智能选型引擎** — 五维度评分（扭矩/速度/精度/重量/成本）多因子选型 + 多结果对比表格
- 📋 **数据质量标注** — 每个实体标注 source / confidence / last_verified
- ✅ **标准符合度** — GB模块化通用技术 / ISO 8373 / IEC 61508 / ROS2兼容状态
- 🧬 **仿生品类** — SEA串联弹性驱动器、柔性驱动器、仿生脊柱、灵巧手、人工肌肉
- 🔗 **兼容性矩阵** — 电气/机械/协议/软件四维兼容检测

## 5. 数据分类
- **actuators**: 217条 — 执行器（电机、谐波减速器、行星滚柱丝杠、无框力矩电机、驱动器、关节模组、灵巧手、腱绳驱动手、开源力控关节、SEA、柔性驱动器）
- **sensors**: 90条 — 传感器（视觉相机、六维力/力矩传感器、关节扭矩传感器、触觉传感器、磁性电子皮肤、激光雷达、IMU）
- **chips**: 108条 — 芯片（AI芯片、边缘推理加速器、MCU、FPGA、通信芯片）
- **protocols**: 64条 — 通信协议（EtherCAT、CANopen、ROS2、MQTT等）
- **interfaces**: 14条 — 接口标准
- **llms**: 23条 — 大模型（VLA模型、机器人基础模型）
- **platforms**: 26条 — 机器人平台（含开源可复现整机）
- **flexible_actuators**: 6条 — 柔性执行器（人工肌肉、柔性驱动器、仿生脊柱）
- **robot_ai_models**: 30条 — 机器人AI模型（VLA模型、世界模型、机器人基础模型）
- **data_acquisition**: 27条 — 数据采集设备（遥操作、外骨骼采集、动作捕捉、数据手套、触觉传感器、开源具身数据集平台）

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

## 7. API
- `GET /api/entities.json` — 全部实体列表
- `GET /api/compatibility_matrix.json` — 兼容性矩阵
- `GET /api/entity/{id}` — 单个实体详情（免费层字段 + 明列被锁付费字段）
- `GET /api/search?q=keyword` — 关键词检索（可选 `category` / `limit` / `include_quarantine`）

## 8. 部署
- **平台**: Cloudflare Pages
- **项目名**: robotparts
- **线上地址（正式，对外一律引用此域）**: https://roboparts.cc
- **预览域（Cloudflare Pages 默认域，非正式入口，勿对外引用）**: https://robotparts-924.pages.dev

## 9. 安全
- API Token 已从文档中移除，请通过环境变量管理
- 旧Token已泄露，请务必在Cloudflare Dashboard轮换

---
生成时间: 2026-08-03
