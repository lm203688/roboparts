# RoboParts × Tnkr 式贡献发布包（RB-OMY / RB-ODM）

> 生成：2026-09-08 ｜ 数据唯一来源：`api/reference_builds.json`（一手核实，检索 2026-09-08）
> 用途：把 RoboParts 参考构型做成 Tnkr（tnkr.ai，「机器人界 GitHub」）风格的**可投递项目包**，
> 以「带兼容性判定的可重建包」进入其贡献生态——Tnkr 的 BOM 管理缺「机械接口兼容性判定」层，正是 RoboParts 定位。

---

## 包结构（对齐 Tnkr 统一项目包模型）

每个包四层：**hardware / software / data / models**，外加 RoboParts 独有的
**interface-judgement 附页**（本包区别于普通 BOM 清单的核心增量）。

---

## 包 1：RB-OMY — Robotis OpenManipulator（Dynamixel X 系列基座）

### hardware（BOM）
| 件 | 型号 | RoboParts 索引 | 关键规格 |
|---|---|---|---|
| 关节执行器 ×4 | DYNAMIXEL XM430-W350-T / XL430-W250-T | `ACT-002` | 4.1 / 1.5 N·m @12V；82g；28.5×46.5×34mm |
| 标准 horn | HN12-N101（X430 标配）×4 | 见 `mechanical_interfaces.json#robotis_x_horn` | 输出盘，Robotis 私有螺栓圈 |
| 紧固件 | WB M2.5×4 / M2.5×6 / M2×3 + 推力垫圈 | step.parts 白名单（2,118 紧固件） | 随包 |
| 主控 | OpenCR1.0 / OpenCM9.04 | 未纳入（非机械接口对象） | Dynamixel 总线桥接 |

### software
- Dynamixel Protocol 2.0（TTL/RS485 总线）；OpenManipulator 官方 ROS 包。
- RoboParts 侧：`/api/reference_builds.json`（本构型机读数据，CC-BY-4.0）、
  `/adapter-generator`（转接盘生成器，已含 ROBOTIS Horn 引导档）。

### data / models
- Onshape/官方 Drawing：horn 孔位 PCD **官方未公开**（见下「诚实边界」）。

### interface-judgement 附页（RoboParts 增量）
- 官方事实：X 系列 horn 体系（HN12-N101 兼容 XH/XM430，**不兼容** MX/XL430）；
  P 系列为 FRP54 专有框架（不兼容旧 PRO 铰接框架）——均已登记
  `mechanical_interfaces.json#robotis_x_horn`（PROPRIETARY-ROBOTIS-XHORN）。
- 裁决：**ROBOTIS horn ↔ 一切 ISO 9409-1 法兰 = adapter_required**（标准体系归属判定）。
- 待补：horn PCD/孔数/螺纹官方未公开 → `pending_verification`，实测后即可在
  adapter-generator 一键生成「horn ↔ ISO 9409-1」转接盘。

---

## 包 2：RB-ODM — Open Duck Mini v2（BDX 风格双足）

### hardware（BOM，<$400）
| 件 | 型号 | RoboParts 索引 | 关键规格 |
|---|---|---|---|
| 总线伺服 ×14 | Feetech STS3215 | step.parts feetech 家族（69 条） | 7.4V，19.5 kg·cm，半双工串行 |
| 微型舵机 ×2 | SG90 / FS90 | generic-servo 等（已收录） | PWM，~1.8 kg·cm |
| 机载计算 | Raspberry Pi Zero 2 W ×1 | — | — |
| 姿态 | BNO055 IMU ×1 | — | I²C |
| 供电 | 18650 ×2 + 2S BMS + 5V UBEC | — | — |
| 触地检测 | SS-10 微动开关 ×4 | — | — |
| 轴承 | 608ZZ ×3（8×22×7） | ISO 标准件 | 髋部枢轴 |
| 紧固件 | M3 热熔嵌件 + M3 螺丝 + Loctite 243 | step.parts 白名单 | 全机模块化 |

### software / data / models
- 官方仓 `apirrone/Open_Duck_Mini`（Onshape CAD，44+ 打印件）；orobot.io 提供 STL 在线查看。
- RoboParts 侧：同上机读数据 + 兼容判定。

### interface-judgement 附页（RoboParts 增量）
- 伺服→连杆输出盘螺栓圈为 Feetech/厂商私有；「伺服私有盘 ↔ 标准连杆孔位」
  是低成本人形最高频适配点——可沉淀为第二批 adapter 模板。
- 608ZZ 为 ISO 标准轴承，step.parts 供应链可直供。

---

## 发布 Runbook（tnkr.ai 实际投递）

> ⚠️ 账号与发布动作需用户本人完成（硬阻塞：无 tnkr.ai 账号/登录态）。以下为可直接照做的步骤。

1. **注册/登录** https://tnkr.ai （建议与 GitHub 关联，便于同步 Open_Duck_Mini 上游）。
2. **新建项目**：Create Project → 名称建议 `roboparts-rb-omy` / `roboparts-rb-odm`。
3. **粘贴本文件对应包的 hardware/software/data/models 四节**；上游链接填
   `https://emanual.robotis.com/docs/en/platform/openmanipulator/` 与
   `https://github.com/apirrone/Open_Duck_Mini`。
4. **附 interface-judgement 附页**：这是与站内其他 remix 包的差异点，说明里注明
   「兼容性判定数据来自 roboparts.cc（CC-BY-4.0）」并附 `/api/reference_builds.json` 链接。
5. **数据回传钩子**：在项目描述中引导 remix 者把实测 horn/伺服盘 PCD 回传至
   RoboParts（api/reference_builds.json 的 gap 字段即回传目标）——对应 Tnkr
   「部署→回收数据→训练」闭环的机械层版本。
6. **发布后**：把项目链接贴回本项目 `ops/` 留痕，纳入下一轮巡检。

## 诚实边界
- 所有数字来自一手公开来源（Robotis 官方页 / Open_Duck_Mini 官方仓与 orobot 快照），检索日 2026-09-08。
- ROBOTIS horn PCD、Feetech 输出盘螺栓圈几何均**未公开**，本包不臆造，显式标 `pending_verification`。
- 本包为「发布就绪资产」；tnkr.ai 实际发布依赖用户账号，AI 不代注册、不代发。
