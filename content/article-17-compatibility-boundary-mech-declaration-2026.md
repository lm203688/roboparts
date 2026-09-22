---
title: "5.69% 的诚实：RoboParts 声明率暴露的兼容层边界"
description: "RoboParts 机械声明率这个数字难看，但把分子分母拆开看，是收录品类先天不在 ISO 9409-1 覆盖范围内，不是数据缺失。本文用 declared 的全部分布、not_declared actuators 的真实身份、reBot 的开源自研接口做证据，回答：兼容判定层要的不是扩张 ISO 9409-1，而是分层。数字取自 onboarding_block.facts() 现算。"
keywords: ["机械声明率", "ISO 9409-1", "机械兼容判定层", "关节电机接口", "末端法兰", "Damiao43", "RobStride", "reBot", "Damiao", "自研接口", "分层判定", "开源机器人", "人形机器人", "开源BOM", "Damiao43 4340P", "roboparts"]
tags: ["standards", "sourcing", "humanoid", "open-source-robotics", "iso9409"]
slug: "compatibility-boundary-mech-declaration-2026"
date: "2026-09-22"
author: "RoboParts Research"
canonical: "https://roboparts.cc/content/article-17-compatibility-boundary-mech-declaration-2026.md"
---

# 5.69% 的诚实：RoboParts 声明率暴露的兼容层边界

> 本文首发于 [RoboParts 机器人零件兼容性判定层](https://roboparts.cc)。声明率数字直接取自 `onboarding_block.facts()` 的现算值，不做美化；品类分布全部可回溯到 `api/entities.json`。

上一篇讲「脑×体解耦为什么让机械兼容层变刚需」，读者问得最多的不是那件事，而是：**你自己家的机械声明率只有 5.69%，那你凭什么说有兼容判定层？**

好问题。今天不回避，把这个数字拆开，讲清楚它到底说明什么、不说明什么。

---

## 一、先把分子分母摆出来

RoboParts 目前收录 {{RP:TOTAL}} 个实体、20 个品类，其中：

| 口径 | 数量 | 说明 |
|---|---|---|
| 有机械接口判定适用性 | 439 | 排除芯片、协议、大模型、数据集等天然不适用的 363 个 |
| 已完整声明（declared） | 15 | 有明确的 ISO 9409-1 designation 与来源 |
| 部分声明（partial） | 10 | 有厂商声明但缺孔位级参数 |
| 未声明（not_declared） | 414 | 大部分是接口非 ISO 9409-1 适用 |
| 声明率（含 partial） | 25 / 439 = **5.69%** | 分子是 declared + partial |

分子 25，分母 439，比率 5.69%。这个数字放到传统工业机械臂目录上，是「几乎没做」；放到 RoboParts 的收录范围上，含义完全不同。

---

## 二、declared 15 条的真实分布：无一例外都是末端执行器

把 15 条完整声明按品类拆开：

| 品类 | 数量 | 例子 |
|---|---|---|
| grippers（夹爪） | 7 | Robotiq 2F-85、OnRobot 2FG7、Schunk Co-act EGP 64 |
| sensors（力/力矩） | 7 | ATI Mini40/Mini45、OnRobot HEX-E、Robotiq FT 300 |
| actuators（含一款夹爪归类） | 1 | Robotiq 2F-85（品类标为 actuator） |
| bionic_mechanisms | 1 | Yeah Robotic Hand |

**15 条里 15 条是末端工具。0 条是关节电机，0 条是平台腕部。**

这不是巧合，是标准本身的适用范围：**ISO 9409-1 就是为「工具-腕部」法兰接口设计的**，50-4-M6、31.5-4-M5、40-4-M6 这些 designation 描述的是末端执行器拧到机器人腕部的孔位布局。关节电机的接口、人形躯干的装配关系、软体执行器的柔性结构——标准文本里根本没有对应条款。

所以「25 条声明」不是「只做了 5.69%」，而是「把该做的都做完了」。剩下 414 条不是数据缺口，是**品类的先天边界**。

---

## 三、215 个 not_declared actuators：接口本来就不在 ISO 9409-1 里

actuators 品类 222 条，其中 215 条 not_declared。挑三个典型看：

**DYNAMIXEL XM540-W270-T（partial，已挂来源）**

ROBOTIS 官方商店 HN12-N101 标准 horn 套装，经 WB M2.5×6 与 M2×3 螺栓装配于输出轴轮齿；官方明示不兼容 MX 系列与 XL430；对接标准法兰需转接盘。来源：en.robotis.com 产品页。

**reBot-DevArm B601-DM（not_declared，2026-09-22 新增）**

Damiao43 4340P 关节电机，直驱准直驱结构，机身与输出轴通过自研抱紧结构固定；BOM 40+ 种 3D 打印件、20+ 种金属件、精确到 M3/M4 螺丝规格。来源：github.com/Seeed-Projects/reBot-DevArm（4287 stars，CERN-OHL-W-2.0）。

**Damiao43 4340P / RobStride RSM（not_declared，2026-09-22 新增）**

两款关节电机的接口都是厂商专有（Damiao 与 RobStride 各自一套抱紧与线束方案），互不兼容，也没有厂商声明 ISO 9409-1 适配。

这三个例子里，**没有一个「应该」有 ISO 9409-1 声明却没有**。DYNAMIXEL 是智能电机（内置 MCU 与总线），reBot 和 Damiao/RobStride 是自研直驱关节——它们的存在本身就是「非 ISO 9409-1」的产物。硬把它们标成 declared，等于污染判定层的输入。

反过来看：如果 RoboParts 是 UR / Franka / KUKA 那样的传统工业臂目录，5.69% 会是异常低；但 RoboParts 收录的品类里，**没有一台传统工业臂**——222 个 actuators 全都是电机模组、智能关节、柔性驱动器、仿生机构。这些不是「没来得及声明」，是「本来就不该用这一把尺量」。

---

## 四、reBot 案例：一个 4287 stars 的项目把这件事说得最清楚

reBot-DevArm B601 是 Seeed Studio 在 2026-04 推出的开源机械臂，仓库 4287 stars，代码 CERN-OHL-W-2.0 许可，BOM 精确到每颗螺丝。同一个平台出两个电机版本：

| 版本 | 电机 | 电压 | 负载 | 臂展 |
|---|---|---|---|---|
| B601-DM | Damiao43 4340P | 24V | 1.5kg | 767mm |
| B601-RS | RobStride RSM | 48V | 2.5kg | 754mm |

**两个版本机械上不兼容**：Damiao43 与 RobStride 是两家厂商的专有抱紧结构，BOM 上的关节组件不通用。但两款都是「非 ISO 9409-1」的关节电机——它们压根不在 ISO 9409-1 讨论的范畴里，而是自研接口之间的不兼容。

这就是兼容判定层真正要回答的问题：**当两台机械臂都用自研接口时，判定兼容的锚点在哪里？**ISO 9409-1 帮不上忙，因为标准里就没有它们。真正起锚点的，是每款电机自己的安装体系（Damiao 一套、RobStride 一套、DYNAMIXEL 又一套）。

RoboParts 把两款电机分别入库（`ACT-damiao-4340p` 与 `ACT-robstride-rsm`），把不兼容写进条目字段而不是 `negative_compat`——因为 `negative_compat` 的 schema 是 ISO 9409-1 designation 对之间的裁决（当前 81 对裁决里 72 对判定需转接盘、0 对直接兼容），往里面塞「Damiao43 与 RobStride 不兼容」会污染 schema。

这个案例值得单独看：**兼容判定的边界，比「有没有兼容」更重要**。

---

## 五、43 个平台：品类先天的兼容性边界

RoboParts 收录的 43 个平台，逐个看清单：

- 人形机器人本体（Unitree G1/H1、Figure 02/03、Tesla Optimus、Agility Digit、Apptronik Apollo、Fourier GR-1/GR-2、1X NEO、Sanctuary Phoenix、Booster T1、PNDbotics Adam、UBTech Walker S、Xiaomi CyberOne、NVIDIA Isaac GR00T Reference、EngineAI T800、AgiBot 等）
- 协作 / 开源机械臂（reBot-DevArm B601-DM/RS、Open Duck Mini、Reachy 2）
- 组织名（Figure AI、Agility Robotics、优傲机器人、Unitree Robotics、AgiBot、波士顿动力、特斯拉、Apptronik、1X Technologies、矩阵超智 Matrix Robotics、LimX Dynamics）

**43 个平台里 0 个是传统工业机械臂**（UR e-Series、Franka Emika Panda、KUKA KR、ABB IRB 等）。这不是遗漏，是 RoboParts 的品类选择：覆盖人形 / 协作 / 开源，不覆盖传统工业臂。

传统工业臂目录的兼容判定，可以直接查 KUKA 与 UR 的腕部法兰对照表；RoboParts 面对的品类里，Figure 03 腕部是 Figure 自研接口、Unitree G1 关节是 Unitree 自研接口、reBot B601 关节是 Damiao/RobStride 自研接口——**没有一个共享 ISO 9409-1 法兰**。这就是 25/439 的物理来源。

---

## 六、诚实的声明率：分子分母都不能被污染

如果目标是「让声明率好看」，做法显而易见：把 DYNAMIXEL、Damiao43、RobStride、Unitree G1 关节都强行套上 ISO 9409-1 designation，分子瞬间翻几倍。这是任何一家想冲「兼容率」榜单的目录都会做的动作。

RoboParts 没这么做，理由很朴素：

**分子污染会骗自己**。把一个非 ISO 9409-1 的关节电机标成 declared，等于告诉判定层「这个接口的孔位布局是 50-4-M6」——但真实情况是它压根没有 ISO 9409-1 布局。任何后续判定都基于错误前提，越精确越错。

**分母污染会骗别人**。把 363 个天然不适用的实体（芯片、协议、LLM、数据集）算进分母，声明率会被压到三百分之一档，看似更保守，实则掩盖了「这三百六十余项本来就不属于机械兼容判定」这个事实。

现在 5.69% 的含义是：**分子是真声明（含 partial），分母是真适用**，剩下的 414 not_declared 里有大量条目属于「ISO 9409-1 不适用」而不是「数据缺失」。

---

## 七、兼容判定层需要什么：从「ISO 9409-1 单一标尺」到分层

结论不是「声明率不重要」，而是**「兼容判定」这个词被 ISO 9409-1 单一化得太久**：

- **末端执行器层**（grippers + 力传感器 + 末端工具）：ISO 9409-1 是唯一成熟标尺，RoboParts 已把这块做满（15 declared，覆盖 Robotiq / ATI / OnRobot / Schunk 主流）。
- **关节电机层**（DYNAMIXEL / Damiao / RobStride / Unitree 自研）：ISO 9409-1 完全不适用，判定锚点是**每款电机自己的安装体系 + 抱紧规格 + 线束接口**。RoboParts 用条目字段承载这条信息，不进 `negative_compat`。
- **平台腕部层**（人形 / 协作腕部法兰）：介于两者之间，部分产品（如 Yeah Robotic Hand 已挂 50mm 法兰）有 ISO 9409-1 兼容声明，多数自研接口（Figure、Unitree G1）没有。

RoboParts 现在的诚实版本是：**末端执行器层做满了，关节电机层与平台腕部层用条目信息承载而非套 ISO 9409-1 模板**。声明率 5.69% 是这个诚实版本的自然结果，不是「进度条」。

---

## 八、下一步的短板与不做的事

明写：

**下一步能推进的**：把关节电机层的抱紧规格、输出轴接口尺寸、线束接口定义结构化到条目字段（不是套 ISO 9409-1，是每款电机自己的 schema）。这需要厂商官域公开 datasheet，AI 不能代写。

**不会做的**：为把声明率抬到两成或三成，把 DYNAMIXEL / Damiao43 / RobStride 强行声明成 ISO 9409-1。那会让判定层的输入从「诚实但有限」变成「虚假但完整」，后者的后果是任何基于判定结果的下游决策都是错的。

**reBot 的贡献**：作为 G1 生态（开放躯体标准件）的第一个开源案例，它证明了一件事——**开源 BOM 到每颗螺丝，不等于开源机械兼容**。DM 与 RS 两个版本不兼容，恰恰需要兼容判定层去回答「我这台 reBot 的末端能不能拧上 Robotiq 2F-85」（答案是：能通过 ISO 9409-1 转接盘，因为夹爪是 declared 而 reBot 腕部是 not_declared，两者不在同一 schema 里，需第三方转接件判定）。

---

## 结语：兼容层不是「兼容率」的排名赛

行业里谈兼容率，常见做法是「我们把 N 个厂商的产品都收录了，兼容率 X%」。这句话隐含的假设是：**兼容率越高越好**。

RoboParts 的数据在反驳这个假设：439 条适用机械声明里，25 条有 ISO 9409-1 兼容声明，剩下 414 条里的绝大多数不是「等数据补上就会变成 declared」，而是「本来就不该用 ISO 9409-1 衡量」。声明率如果真涨到四分之一档，那说明分子被污染了；如果声明率保持在现算值，那说明它诚实。

这不是自谦，是兼容判定层的存在理由——**判定层的第一责任是分子分母都干净，第二责任才是分子变大**。当「脑×体解耦」把身体层推向极端分化（SONIC 跑 Unitree G1、Figure 有 Figure 自研腕、reBot 有 Damiao/RobStride 双版本），机械兼容判定的价值不是「兼容率多高」，而是「哪些兼容哪些不兼容判定得准」。

5.69% 是一个诚实数字。兼容判定层的边界，就在这个诚实里。

---

*本文所有数字取自 `onboarding_block.facts()` 现算；15 条 declared 明细可回溯 `api/entities.json`；reBot 数据源 `github.com/Seeed-Projects/reBot-DevArm`（4287 stars，CERN-OHL-W-2.0）。判定层短板已明写，本文不作为宣传材料使用。*
