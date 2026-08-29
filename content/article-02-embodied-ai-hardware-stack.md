---
title: "开源人形机器人硬件栈全景：构建者视角的 7 层架构与选型清单"
description: "从执行器到 VLA 模型，拆解开源人形机器人的完整硬件栈。结合天工 TienKung、Unitree G1、OpenArm、LeRobot-Humanoid 等真实开源项目，给出每一层的选型要点与兼容性校验方法。"
keywords: ["开源人形机器人", "具身智能硬件栈", "机器人选型", "执行器", "边缘算力", "EtherCAT", "CAN FD", "VLA", "LeRobot", "OpenArm"]
tags: ["open-source-robotics", "humanoid", "sourcing", "hardware-stack", "bom"]
slug: "open-source-humanoid-hardware-stack"
author: "RoboParts Research"
canonical: "https://roboparts.cc/content/article-02-embodied-ai-hardware-stack.md"
---

# 开源人形机器人硬件栈全景：构建者视角的 7 层架构与选型清单

> 本文首发于 [RoboParts 开源机器人兼容性平台](https://roboparts.cc)。

大模型让机器人"会思考"，但硬件决定了它"能不能动"。

对开源机器人构建者来说，问题往往不是"这个方案好不好"，而是**"我照着 GitHub 上的 BOM 买回来的这堆零件，到底能不能装到一起、能不能跑起来"**。天工 TienKung 的仓库给了图纸和物料表，Trossen OpenArm 有完整的机械设计，LeRobot-Humanoid 有社区维护的低成本方案——但当某个型号停产、超预算或者你所在地区买不到时，替换决策就得自己扛。

本文从实际构建视角，拆解开源人形机器人的完整硬件栈，给出每一层的选型要点、主流方案，以及**这一层最容易出现的兼容性坑**。

---

## 第一层：执行层（Actuators）

执行器是机器人的"肌肉"。人形机器人全身通常需要 **12-52 个执行器**，按关节分布：

| 部位 | DoF | 典型扭矩 | 执行器类型 |
|---|---|---|---|
| 髋关节 | 3×2 | 100-150Nm | 谐波/行星+力矩电机 |
| 膝关节 | 1×2 | 100-150Nm | 谐波/SEA |
| 踝关节 | 2×2 | 50-80Nm | 行星+无刷 |
| 肩关节 | 3×2 | 30-60Nm | 谐波 |
| 肘关节 | 1×2 | 20-40Nm | 行星 |
| 腕关节 | 2×2 | 5-15Nm | 微型谐波 |

**核心指标**：扭矩密度（Nm/kg）、峰值/额定比、惯量比、背隙。

**这一层的兼容性坑**：法兰孔位与中心孔径。同扭矩等级的两款模组，输出法兰的 PCD（节圆直径）差 2mm，你的结构件就全部报废。开源项目的 STEP 文件通常按原型号建模，换型必须同步改结构件——**换型前先量法兰**。

RoboParts 收录 {{RP:CAT:actuators}} 款执行器，覆盖谐波、行星、SEA、直线电机等全品类，并标注了法兰规格与可替代型号。

---

## 第二层：感知层（Sensors）

人形机器人至少需要三类传感器：

### 本体感知（Proprioception）
- **IMU**：躯干姿态估计，100-1000Hz，推荐 TDK ICM-42688-P 或 Bosch BMI270
- **关节编码器**：电机端（17-23bit）+ 输出端（14-19bit），双编码器消除背隙
- **力/力矩传感器**：SEA 内置或腕部/踝部外置，六维力传感器推荐 ATI Nano 系列

### 环境感知（Exteroception）
- **深度相机**：Intel RealSense D455、Azure Kinect、OAK-D
- **激光雷达**：Livox Mid-360（低成本）、Velodyne Puck（高性能）
- **触觉传感器**：视触觉（GelSight）、压力阵列（Tekscan）

### 语义感知
- **RGB 相机**：用于 VLA（Vision-Language-Action）模型输入
- **麦克风阵列**：语音指令接收

**这一层的兼容性坑**：驱动生态。Intel RealSense 在 ROS2 上有官方包，某些国产深度相机只提供 Windows SDK；Meta 开源的 DIGIT 触觉传感器有现成 Python 驱动，而工业级触觉阵列可能只给 CANopen 手册。**对开源项目，"有没有 ROS2 驱动"经常比参数更重要。**

---

## 第三层：通信层（Protocols）

机器人内部通信对实时性要求极高：

| 协议 | 带宽 | 实时性 | 典型用途 |
|---|---|---|---|
| EtherCAT | 100Mbps | 硬实时（μs级） | 全身关节同步控制 |
| CAN FD | 2-8Mbps | 软实时（ms级） | 下肢关节、轮式底盘 |
| RS-485 | 1-10Mbps | 非实时 | 低速外设、传感器 |
| SPI/I2C | 10-50Mbps | 芯片级 | IMU、编码器直连 |

**设计建议**：
- 主控 ↔ 关节驱动器：EtherCAT 或 CAN FD
- 关节驱动器 ↔ 电机：PWM/FOC 直驱
- 传感器：SPI（高带宽）或 I2C（简单外设）

**这一层的兼容性坑**：同为 "CAN"，帧格式和对象字典未必兼容。Unitree 的关节模组用私有 CAN 协议，Trossen OpenArm 的 Dynamixel 系列走的是自有串行总线，标准 CANopen 设备又是另一套。把三家的模组混在同一条总线上，几乎必然要写协议转换层。**混用不同厂商模组前，先确认协议栈是否同源。**

---

## 第四层：计算层（Chips）

具身智能的计算需求呈双峰分布：

### 边缘推理（Edge）
- **NVIDIA Jetson Orin**：70-275 TOPS，ROS2 生态完善，开源人形项目事实标准
- **Intel NUC / AMD V1000**：x86 架构，适合移植桌面级算法
- **地平线 J5 / 芯驰 V9**：国产替代，车规级可靠性

### 关节驱动（Motor Control）
- **STM32H7**：单关节 FOC 控制，200MHz，浮点单元
- **TI C2000**：工业级，双核锁步，功能安全
- **瑞萨 RA8**：Cortex-M85，Helium 矢量加速

### 通信处理
- **Beckhoff ET1100**：EtherCAT 从站芯片
- **TI TCAN4550**：CAN FD 控制器

**这一层的兼容性坑**：JetPack 版本与 ROS2 发行版的绑定关系。LeRobot 生态多在 Ubuntu 22.04 + ROS2 Humble 上验证，若你买的 Jetson 预装了不匹配的 JetPack，光是把驱动和 CUDA 版本对齐就能耗掉一周。**买板子前先查目标开源项目在哪个软件栈上验证过。**

RoboParts 收录 {{RP:CAT:chips}} 款芯片，按应用场景分类标注。

---

## 第五层：接口层（Interfaces）

物理连接器容易被忽视，但直接影响维护和可靠性：

| 接口 | 电流 | 场景 | 代表型号 |
|---|---|---|---|
| JST SM / PH | ≤ 3A | 低功率信号 | 传感器、LED |
| XT30 / XT60 | 15-60A | 动力电 | 电池-分电板 |
| Anderson Powerpole | 15-45A | 模块化连接 | 关节快拆 |
| M8/M12 防水 | ≤ 12A | 户外/工业 | IP67 传感器 |
| 航空插头 | ≥ 20A | 高功率关节 | 膝关节、髋关节 |

**这一层的兼容性坑**：也是开源项目文档里最常缺失的一层。BOM 通常写了执行器型号，却没写它出厂带的是哪种连接器。等零件到货才发现电机侧是航插、你的分电板是 XT60，只能现场重新压线。**下单时把连接器型号一并核对进 BOM。**

---

## 第六层：平台层（Platforms）

快速启动人形研发的仿真与实体平台：

| 平台 | 类型 | 开源程度 | 特点 |
|---|---|---|---|
| NVIDIA Isaac Sim | 仿真 | 免费闭源 | GPU 加速，PhysX，支持 ROS2 |
| MuJoCo | 仿真 | 开源 | 轻量，强化学习友好 |
| Gazebo (Ignition) | 仿真 | 开源 | ROS2 原生 |
| 天工 TienKung | 实体 | 开源整机 | 全尺寸人形，图纸与控制栈开放 |
| Unitree G1 / Go2 | 实体 | API/SDK 开放 | 国内领先，二次开发友好 |
| LeRobot-Humanoid | 实体 | 社区开源 | 低成本，HuggingFace 生态 |
| Trossen OpenArm | 实体 | 开源机械臂 | 模块化，教学与研究首选 |
| roboto_origin | 实体 | 开源整机 | 轻量化，入门构建 |

**选择建议**：
- 想学**全尺寸双足行走**→ 天工 TienKung
- 想快速跑通**VLA 数据采集与训练** → LeRobot-Humanoid 或 Unitree G1
- 只做**上肢操作/抓取** → Trossen OpenArm
- 预算极低、先跑通流程 → roboto_origin

---

## 第七层：智能层（LLMs）

VLA（Vision-Language-Action）模型正在改变机器人控制范式：

| 模型 | 参数量 | 开源 | 具身支持 |
|---|---|---|---|
| RT-2 (Google) | 55B | 否 | 端到端 VLA |
| OpenVLA | 7B | 是 | 通用抓取 |
| π0 (Physical Intelligence) | 3B | 否 | 流匹配动作 |
| RDT (清华) | 1B | 是 | 双臂协作 |
| Octo (Berkeley) | 93M | 是 | 多机器人迁移 |

**关键趋势**：小参数模型（< 10B）+ 高质量机器人数据 > 大参数通用模型。

**对构建者的实际含义**：模型层反过来会约束硬件层。若你打算跑 LeRobot 生态的策略模型，采集端最好沿用它支持的相机与关节接口格式，否则数据格式转换会成为长期负担。**先定模型生态，再定传感器和执行器接口**，比反过来省事得多。

---

## 一站式硬件选型

以上 7 层架构的完整数据已结构化收录：

- **{{RP:TOTAL}} 个实体**，覆盖执行器、柔性驱动器、传感器、芯片、协议、接口、平台、LLM、机器人AI模型、数据采集共 {{RP:CATEGORIES}} 大品类
- 每个实体包含规格参数、厂商、价格区间、标准合规、ROS2 兼容性
- 支持交叉引用（如：哪些芯片支持 CAN FD？哪些平台兼容 ROS2？）

**给开源构建者的推荐用法**：

1. 先在[开源组件兼容性数据层](https://roboparts.cc/oss.html)找到你要复刻的项目（天工、Go2、OpenArm、LeRobot-Humanoid、roboto_origin），拿到经过核对的组件清单
2. 把你实际能买到的型号填进 [BOM 兼容性检查](https://roboparts.cc/bom-checker.html)，一次性查出机械、电气、协议、软件四个维度的冲突
3. 有冲突的项，用[选型引擎](https://roboparts.cc/selection.html)找等效替代
4. 用[供应商寻源](https://roboparts.cc/suppliers.html)确认交期与可购性
5. 要把校验接进自己的工具链，用[兼容性数据 API](https://roboparts.cc/data-hub.html)

也可以直接在 GitHub 下载完整数据集：

- GitHub：https://github.com/roboparts/roboparts-dataset
- API：https://roboparts.cc/api/data.json

---

**RoboParts · 开源机器人构建者资源**

- 🔧 免费 BOM 兼容性检查：https://roboparts.cc/bom-checker.html
- 📦 开源组件兼容性数据层：https://roboparts.cc/oss.html
- 🔌 兼容性数据 API（Pro）：https://roboparts.cc/data-hub.html
- 🛒 供应商寻源：https://roboparts.cc/suppliers.html

正在构建或维修开源机器人？用 RoboParts 把零件兼容性一次性查清。

---
