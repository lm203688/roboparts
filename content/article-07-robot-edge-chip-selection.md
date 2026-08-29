---
title: "为你的开源机器人选算力板卡：Jetson Thor / Orin Nano / Dragonwing IQ10 全对比"
description: "2026年机器人端侧AI芯片形成三强格局。本文面向开源机器人构建者，基于NVIDIA、高通、Intel官方规格，系统对比Jetson Thor T5000/T3000/T2000、Dragonwing IQ10、Jetson Orin Nano/NX、Intel Core Ultra Series 3的AI算力、功耗、内存、生态工具链与实际部署案例，给出从0.5B到30B VLA模型的芯片匹配建议、开源平台适配提示和选型决策树。"
keywords: ["机器人芯片", "开源机器人", "Jetson Thor", "Dragonwing IQ10", "Jetson Orin Nano", "Intel Core Ultra", "端侧AI芯片", "VLA模型部署", "机器人算力选型", "Blackwell架构", "ROS 2兼容", "具身智能芯片", "LeRobot", "Unitree G1"]
tags: ["open-source-robotics", "humanoid", "sourcing", "edge-compute", "bom"]
slug: robot-edge-chip-selection-2026
date: 2026-07-27
author: RoboParts Research
canonical: https://roboparts.cc/articles/robot-edge-chip-selection-2026
---

# 为你的开源机器人选算力板卡：算力、功耗、生态全对比

> 本文首发于 [RoboParts 开源机器人兼容性平台](https://roboparts.cc)。芯片规格数据交叉引用：[roboparts.cc/api/data.json](https://roboparts.cc/api/data.json)。

选一颗机器人主控芯片，过去是在NVIDIA Jetson家族里挑算力档位。2026年这个选择题变了——NVIDIA Jetson Thor系列覆盖了2070到400 FP4 TFLOPS的宽区间，高通带着700 TOPS和SIL3功能安全的Dragonwing IQ10杀入工业AMR和全尺寸人形机器人，Intel用Core Ultra Series 3的异构SoC主打成本敏感型服务机器人。三家之外，Jetson Orin Nano/NX仍是入门级边缘AI的成熟基准。

**如果你是在自己搭机器人**——给 LeRobot-Humanoid 换个更强的脑子、给 Trossen OpenArm 加视觉、或者给天工 TienKung 复刻机配主控——这个决策比看起来更难回退。算力板卡不是一个"插上就能换"的零件：它牵动供电、散热、结构件孔位、相机接口数量，还牵动你整套软件栈能不能编译通过。

芯片选型不再只是"算力够不够"的问题。算力决定了你能跑多大的VLA模型，功耗决定了散热设计和电池续航，生态工具链决定了开发周期，功能安全等级决定了能否进工业产线，供货周期决定了产品生命周期。这五个维度交叉在一起，才是真实的选型决策。

本文基于NVIDIA官网、高通OnQ博客、Intel新闻室的官方规格数据，对五款代表性芯片做系统对比，给出从0.5B到30B VLA模型的芯片匹配建议，并在每一节标出**开源项目最常踩的适配坑**。

---

## 一、五款芯片核心规格总表

先看硬数据。以下规格均来自厂商官方，无法查证的数据标注"未公开"。

| 维度 | Jetson Thor T5000 | Jetson Thor T3000 | Dragonwing IQ10 | Jetson Orin NX 16GB | Intel Core Ultra Series 3 |
|:---|---|---|---|---|---|
| **AI算力** | 2070 FP4 TFLOPS | 865 FP4 TFLOPS | 700 TOPS | 100 INT8 TOPS（稀疏） | 约180 TOPS |
| **GPU架构** | Blackwell（2560核） | Blackwell | 高通自研GPU+多核NPU | Ampere（1024核CUDA） | Intel Xe（集成） |
| **CPU** | 14核 Arm Neoverse-V3AE | 8核 Neoverse Arm | 18核 Oryon | 8核 Arm Cortex-A78AE | x86（核数未公开） |
| **内存** | 128GB LPDDR5X | 32GB LPDDR5X | 未公开 | 16GB LPDDR5 | 未公开（共享） |
| **内存带宽** | 273 GB/s | 273 GB/s | 未公开 | 102.4 GB/s | 未公开 |
| **功耗** | 40-130W | T5000的一半 | 未公开（强调低功耗） | 10-25W | 未公开 |
| **功能安全** | IGX版本支持Halos | IGX版本支持 | SIL3 | 未特别强调 | PMDF安全框架 |
| **网络** | 4× 25GbE | 25GbE | PCIe/TSN/EtherCAT/CAN | 最多3× 10GbE | 未公开 |
| **价格** | 套件$3,499/模块$2,999 | 未公布 | 未披露 | 模块约¥3,418-5,036 | 未公开 |
| **制程** | 未公开（Blackwell） | 未公开 | 未公开 | 8nm | Intel 18A |
| **SDK** | JetPack 7.x | JetPack 7.2.1+ | Qualcomm AI Hub/ROS 2 | JetPack 6.x | OpenVINO/ROS 2 |
| **发布/供货** | 2025年已上市 | 2026.7发布/2027 Q1供货 | 2026.1 CES/2026.6 Computex | 已上市（成熟） | 2026.5发布 |

几个值得注意的细节。Jetson Thor T5000的2070 FP4 TFLOPS是稀疏峰值，实际部署FP8/INT8精度时有效算力会缩水，NVIDIA官方未公布具体FP8/INT8 TOPS。Dragonwing IQ10的700 TOPS是NPU+GPU总算力，无需外置加速器。Intel Core Ultra Series 3的180 TOPS来自CPU（约10）+NPU（约50）+GPU（约120）的异构加总。不同厂商的算力标定口径不完全一致，跨厂商比大小时要留有余量。

---

## 二、NVIDIA Jetson Thor：Blackwell架构的算力天花板

### 2.1 产品矩阵：四档覆盖全场景

Jetson Thor系列在2026年7月15日补齐了产品线，形成T5000/T4000/T3000/T2000四档：

- **T5000**：2070 FP4 TFLOPS，128GB LPDDR5X，14核Arm Neoverse-V3AE，4× 25GbE。开发者套件$3,499，量产模块（1000片以上）约$2,999。已为1X、Agile Robots、Amazon Robotics、波士顿动力、FANUC等新一代人形机器人提供算力。
- **T4000**：1200 FP4 TFLOPS，64GB LPDDR5X，12核CPU，3× 25GbE。已上市。
- **T3000**：865 FP4 TFLOPS，32GB LPDDR5X，8核CPU，尺寸功耗为T5000的一半。2026年7月发布，**2027年第一季度正式供货**。JetPack 7.2.1起支持T3000仿真模式。
- **T2000**：400 FP4 TFLOPS，16GB内存，入门级。2027年第一季度供货。

相比Jetson AGX Orin，Thor系列AI计算性能提升7.5倍，能效提升3.5倍，CPU性能增强3.1倍，内存翻倍。

### 2.2 生态工具链：CUDA护城河

Jetson Thor的真正护城河不是算力数字，而是CUDA生态的成熟度：

- **CUDA + TensorRT**：业界最成熟的GPU加速栈，几乎所有主流VLA模型都有CUDA优化路径
- **Isaac平台**：机器人仿真与感知全套件，Isaac Sim支持物理级仿真，Isaac GR00T提供人形机器人参考设计
- **Holoscan**：边缘AI传感器处理流水线，Holoscan Sensor Bridge支持实时数据流
- **Jetson AI Lab**：支持广泛开源模型，包括GR00T、Cosmos 3 Edge（40亿参数世界基础模型）、NVIDIA Nemotron等
- **Jetson智能体技能 + NemoClaw**：AI辅助内存优化、系统配置、部署自动化，官方称"数天完成原需数周的优化"
- **JetPack 7.2**：全新软件内存优化技术，支持Agentic-ready AI部署，MOVE X利用异构AI加速器优化工作负载分配
- **ROS 2兼容**：完整支持，ros2_control可直接调用

硬件生态方面，凌华科技、研华、AAEON、Connect Tech、矽递科技等十余家厂商提供工业级载板方案，供货周期覆盖工业级长生命周期需求。

### 2.3 实际部署案例

- **NVIDIA Isaac GR00T参考设计**：搭载T5000，3B参数VLA模型原生优化
- **1X、Agile Robots、Amazon Robotics**：新一代人形机器人基于Thor开发
- **优必选、Agile Robots**：人形机器人，内存优化后从64GB方案迁移至32GB
- **大晓Kairos 3.1**：8B世界模型在Thor平台BF16精度下125ms推理延迟（Cosmos 3 Nano为6486ms）

RoboParts数据集的 `chips` 实体库收录了Jetson全系列规格参数，包括AI算力、内存带宽、功耗曲线、支持的通信协议，可通过[选型引擎](https://roboparts.cc/selection.html)在线查询。

> **开源项目适配坑**：Thor 系列走的是 JetPack 7.x，而目前多数开源机器人控制栈（含大量 LeRobot 社区方案）是在 JetPack 6.x + Ubuntu 22.04 + ROS2 Humble 上验证的。升级到 Thor 意味着 CUDA 版本、Python 版本、ROS2 发行版可能同时变动，第三方驱动（尤其是国产相机和 CAN 转接卡）不一定有对应版本。**动手前先确认你依赖的每个驱动是否有 JetPack 7 版本**——这是 Thor 迁移中最常见的返工原因。

---

## 三、高通 Dragonwing IQ10：车载级安全切入工业机器人

### 3.1 核心规格

高通Dragonwing IQ10于2026年1月CES发布芯片，6月Computex发布机器人参考设计（RRD）：

- **AI算力**：700 TOPS，多核NPU+GPU架构，无需外置加速器
- **CPU**：18核Qualcomm Oryon，性能为上一代5倍
- **功能安全**：SIL3等级——这是机器人芯片中罕见的车规级安全认证
- **传感器支持**：最多12路GMSL2摄像头、LiDAR、ToF、IMU
- **实时接口**：PCIe、TSN、USB、CAN、Ethernet、EtherCAT、CAN-FD
- **工作温度**：-40°C至70°C
- **供电**：12V/24V工业输入
- **软件栈**：ROS 2原生支持、Qualcomm AI Hub、MLOps/DevOps工具链、端侧AI运行时

### 3.2 技术特色：车载经验移植

Dragonwing IQ10的核心差异化在于复用了高通40年移动芯片和10年汽车电子的技术积累。车载感知、芯片架构、温控及安全体系被整体移植到机器人赛道：

- **GMSL2传感器直连**：12路摄像头通过GSML2协议直连主芯片，减少桥接组件，降低延迟和集成成本。这是车载ADAS方案的成熟技术，移植到机器人后大幅简化了多相机系统的布线
- **以太网连接激光雷达**：LiDAR通过以太网接入，IMU与主芯片直连
- **SIL3功能安全**：达到汽车电子最高安全等级，意味着可以进入工业产线、协作机器人等有安全要求的场景
- **端到端架构**：整合边缘计算、边缘AI、混合关键系统和MLOps，形成完整能力

### 3.3 合作伙伴与部署

- **Figure AI**：基于IQ10开发下一代人形机器人
- **Kuka（库卡）**：工业机器人集成
- **NEURA Robotics**：协作机器人
- **VinMotion**：越南Motion 2人形机器人，前代IQ9已演示
- **Booster**：人形机器人

Figure AI的选择值得重点关注——作为估值最高的美国人形机器人初创，它放弃Jetson生态转向高通，说明Dragonwing IQ10在某些维度（可能是功耗效率、GMSL2传感器集成、车规可靠性）上对Figure的场景更有吸引力。

---

## 四、Jetson Orin Nano/NX：成熟的中低端基准

Jetson Orin系列虽然不是2026年的新品，但作为成本敏感型边缘AI的事实标准，仍是大多数入门级机器人项目的起点。

| 型号 | AI算力（INT8稀疏） | GPU | 内存 | 功耗 | 参考价格 |
|------|:---:|-----|------|:---:|------|
| Orin Nano 4GB | 20 TOPS | 1024核CUDA | 4GB LPDDR5 | 7-15W | 约¥823 |
| Orin Nano 8GB | 40 TOPS | 1024核CUDA | 8GB LPDDR5 | 7-25W | 约¥1,159-1,490 |
| Orin NX 8GB | 70 TOPS | 1024核CUDA | 8GB LPDDR5 | 10-25W | 约¥3,418-5,036 |
| Orin NX 16GB | 100 TOPS | 1024核CUDA | 16GB LPDDR5 | 10-25W | 约¥3,418-5,036 |

JetPack 6.2引入的"Super Mode"可提升算力——Orin Nano 8GB从33 TOPS提升至40 TOPS Sparse。这颗芯片的定位很清晰：覆盖40-100 TOPS区间，是Thor系列（865-2070 TFLOPS）的成本敏感型替代方案。

实际部署案例包括优必选人形机器人、SandStar智慧零售、GROOVE LOVOT陪伴机器人、NoTraffic智能交通等。对于跑0.5B-1B轻量级VLA模型（如SmolVLA、FabriVLA）的开发者，Orin Nano 8GB是性价比最优的选择。

> **这一档是开源构建者的主力区间**。LeRobot-Humanoid、roboto_origin、Trossen OpenArm 的社区方案绝大多数默认基于 Orin Nano/NX，意味着：驱动是现成的、教程是对得上的、遇到问题在 issue 区能搜到。**对第一台自制机器人，"生态踩过坑"比"算力更高"重要得多。** 若确实要更强算力，优先考虑 Orin NX 16GB（100 TOPS）而非直接跳到 Thor——软件栈基本无痛，只需注意功耗从 15W 上升到 25W 时的供电和散热余量。

---

## 五、Intel Core Ultra Series 3：异构SoC的另一种思路

Intel于2026年5月20日正式发布Core Ultra Series 3 for Edge，定位边缘AI机器人计算：

- **总AI算力**：约180 TOPS（CPU约10 + NPU约50 + GPU约120）
- **架构**：单SoC集成CPU+GPU+NPU，Intel 18A制程
- **核心差异化**：以单SoC替代"CPU+独立GPU"分离架构，降低成本、功耗和散热压力
- **工业级特性**：宽温适应、10年可靠性、高实时性、高确定性精度
- **软件生态**：OpenVINO、ROS 2中间件驱动分层架构SDK、机器人硬件开发套件
- **安全框架**：2025年12月联合发布《具身智能机器人安全子系统白皮书》，提出PMDF解决框架（自主监控+备用系统）
- **Computex 2026新推出**：OpenVINO Physical AI开源机器人框架

Intel宣称在LLM、图像分类、VLA及每瓦成本上领先于Jetson Orin。130家公司正在采用和测试，典型合作伙伴包括Sensory AI（Ella咖啡机器人，完全弃用独立GPU，200杯/小时）、Trossen Robotics（机械臂）、Circulus（韩国人形机器人Pibo）、Oversonic Robotics（意大利RoBee人形/半人马机器人，康复医疗场景）。

x86架构的优势在于最广泛的开发者采用和框架兼容性——Trossen Robotics的评价是"开发便利性是选择Intel的关键原因"。

> **对开源构建者的含义**：Trossen 正是 OpenArm 的团队。如果你在做的是桌面级机械臂或固定式操作平台，不受电池和重量约束，x86 方案（Intel NUC 类）往往比 Jetson 更省心——pip 装包不用找 aarch64 轮子，仿真环境和训练环境可以是同一台机器。**移动型机器人选 Jetson，固定型平台不妨考虑 x86。**

---

## 六、三个维度的深度对比

### 6.1 算力效率：TOPS不等于一切

单纯比算力数字容易误导。Jetson Thor T5000的2070 FP4 TFLOPS是FP4稀疏峰值，实际跑FP8或INT8精度时有效算力会打折。Dragonwing IQ10的700 TOPS是NPU+GPU总算力，高通强调"无需外置加速器"，意味着这700 TOPS是芯片内可用的。Intel的180 TOPS来自三个异构单元加总，实际能调用多少取决于工作负载分配。

更真实的对比维度是"能跑多大的VLA模型"和"推理延迟多少"。根据2026年工程实践：

| 芯片 | 可端侧跑的VLA模型规模 | 典型推理延迟 | 能效比参考 |
|------|:---:|:---:|------|
| Jetson Thor T5000 | 30B+（MoE激活3B）、8B | 125-200ms（8B BF16） | 高（Blackwell架构+5代Tensor Core） |
| Jetson Thor T3000 | 6B-8B | 150-250ms | 高（T5000的一半功耗） |
| Dragonwing IQ10 | 6B-8B | 未公开（700 TOPS理论支撑） | 强调低功耗，具体数值未公开 |
| Jetson Orin NX 16GB | 1.5B-3B | 80-150ms | 中（8nm制程，10-25W） |
| Intel Core Ultra Series 3 | 1.5B-3B | 未公开 | 强调每瓦成本优于Orin |

### 6.2 生态工具链：成熟度差距明显

| 维度 | NVIDIA | 高通 | Intel |
|------|--------|------|-------|
| AI加速栈 | CUDA+TensorRT（最成熟） | Qualcomm AI Hub | OpenVINO |
| 机器人框架 | Isaac Sim/GR00T/Holoscan | ROS 2原生 | OpenVINO Physical AI（新推出） |
| 仿真环境 | Isaac Sim（物理级） | 依赖第三方 | 依赖第三方 |
| 模型支持 | GR00T/Cosmos 3/Nemotron原生 | VLM/VLA边缘部署 | VLA支持 |
| 社区规模 | 300万开发者（最大） | 车载+移动开发者迁移 | x86开发者（最广泛） |
| 工业级载板 | 10+家厂商 | 研华/APLUX/Thundercomm等 | 待生态成熟 |

NVIDIA的生态优势是压倒性的。Isaac Sim的物理级仿真能力、GR00T参考设计的开箱即用、300万开发者的社区规模，构成了很高的切换成本。高通和Intel的切入点不是正面竞争生态，而是用功能安全（高通SIL3）或架构优势（Intel单SoC）切入NVIDIA覆盖不到的场景。

### 6.3 功能安全与工业适用性

这是高通Dragonwing IQ10最大的差异化点。SIL3是汽车电子最高安全等级，意味着芯片通过了严格的功能安全认证，可以用于有人机协作场景。Jetson Thor的IGX版本支持Halos安全框架，但NVIDIA的功能安全定位更偏自动驾驶而非工业协作。Intel的PMDF框架是2025年底刚提出的，成熟度待验证。

对于需要进入工业产线、协作机器人、医疗康复等有安全认证要求的场景，Dragonwing IQ10的SIL3是目前机器人芯片中最硬的凭证。这也是Kuka、NEURA Robotics等工业机器人厂商选择高通的原因。

---

## 七、VLA模型规模与芯片匹配

VLA模型的参数规模直接决定了芯片选型。以下是2026年工程实践中的匹配关系。

| VLA模型规模 | 代表模型 | 推荐芯片 | 算力门槛 | 部署方式 |
|:---:|------|------|:---:|------|
| 0.5B-1B | SmolVLA（0.45B）、FabriVLA（0.89B） | Jetson Orin Nano 8GB（40 TOPS）、RK3588 | 20 TOPS | 端侧原生 |
| 1.5B-3B | MiniCPM-RobotManip（1.5B）、GR00T 1.7（3B）、ZR-0（2.6B） | Jetson Orin NX 16GB（100 TOPS）、Jetson Thor T2000、Intel Core Ultra Series 3 | 100 TOPS | 端侧为主 |
| 6B-8B | LingBot-VLA 2.0、Kairos 3.1（8B） | Jetson Thor T3000（865 FP4 TFLOPS）、Dragonwing IQ10（700 TOPS） | 500 TOPS | 端侧需高算力或端云协同 |
| 30B+（MoE激活3B） | Hy-Embodied-VLM-1.0、AstraBrain旗舰版 | Jetson Thor T5000（2070 FP4 TFLOPS） | 1000+ TOPS | 端侧（MoE激活3B）或云端 |

一个关键工程经验：超过8B的模型通常更适合云端部署或端云协同。将必须低延迟的控制闭环（50Hz）留在本地，将需要大算力的复杂推理放到云端，是2026年人形机器人部署的主流路线。Kairos 3.1把8B模型延迟压到125ms是例外——它依赖KairosRT计算引擎对Thor平台的深度优化，不是所有8B模型都能做到。

RoboParts数据集收录了 {{RP:CAT:chips}} 款芯片的结构化规格，包括AI算力、内存带宽、功耗、支持的通信协议。通过[选型引擎](https://roboparts.cc/selection.html)可以交叉查询"某款VLA模型需要哪类芯片"以及"某款芯片能跑哪些模型"；若你已经有一份开源项目的 BOM，直接用 [BOM 兼容性检查](https://roboparts.cc/bom-checker.html)把板卡型号一起提交，可同时校验供电余量、接口数量、结构孔位和驱动可用性四类冲突。

```python
# 查询能跑6B VLA模型的芯片
import requests
db = requests.get("https://roboparts.cc/api/data.json").json()

chips_for_6b = [
    c for c in db["chips"]
    if c.get("specs", {}).get("ai_tops", 0) >= 500
    or c.get("specs", {}).get("fp4_tflops", 0) >= 500
]

for chip in chips_for_6b:
    print(f"{chip['name']}: {chip['specs'].get('ai_tops', 'N/A')} TOPS, "
          f"{chip['specs'].get('power', 'N/A')}W, "
          f"{chip['specs'].get('price_range', 'N/A')}")
```

---

## 八、选型决策树

不同场景的选型逻辑差异很大。以下决策树覆盖了从个人开发者到工业产线的主要场景。

```
你的机器人需要跑多大的VLA模型？
│
├─ ≤1B（轻量级，如SmolVLA、FabriVLA）
│   ├─ 预算<¥2000 → Jetson Orin Nano 8GB（40 TOPS，¥1490）
│   ├─ 预算<¥500 → RK3588方案
│   └─ 需要x86生态 → Intel Core Ultra Series 3
│
├─ 1.5B-3B（主流端侧，如MiniCPM-Robot、GR00T 1.7）
│   ├─ 需要CUDA生态 → Jetson Orin NX 16GB（100 TOPS）
│   ├─ 需要Thor级能效 → Jetson Thor T2000（400 FP4 TFLOPS，2027 Q1）
│   └─ 成本敏感，x86可接受 → Intel Core Ultra Series 3（180 TOPS）
│
├─ 6B-8B（中型，如LingBot-VLA 2.0、Kairos 3.1）
│   ├─ 需要CUDA+Isaac生态 → Jetson Thor T3000（865 FP4 TFLOPS）
│   ├─ 需要SIL3功能安全 → Dragonwing IQ10（700 TOPS）
│   └─ 端云协同（端侧跑感知，云端跑推理） → Jetson Orin NX + 云端GPU
│
└─ 30B+（大型/云端，如Hy-Embodied-VLM-1.0）
    ├─ MoE激活3B可端侧 → Jetson Thor T5000（2070 FP4 TFLOPS，128GB）
    └─ 纯云端推理 → H100/H200集群
```

### 场景化补充

**人形机器人全身控制**：首选Jetson Thor T5000。128GB统一内存可以同时跑VLA模型+感知+规划，2070 FP4 TFLOPS支撑8B以上模型。1X、Agile Robots、波士顿动力都选了这条路。

**工业AMR/协作机器人**：首选Dragonwing IQ10。SIL3功能安全是进产线的硬门槛，12路GMSL2摄像头直连简化多传感器集成，Figure AI和Kuka的选择印证了这条路。

**服务机器人/零售/餐饮**：首选Intel Core Ultra Series 3。单SoC弃用独立GPU降低TCO，x86生态开发便利，Sensory AI的Ella咖啡机器人（200杯/小时）是成功案例。

**个人开发者/教育**：首选Jetson Orin Nano 8GB。40 TOPS跑0.5B-1B模型足够，¥1490的价格友好，CUDA生态学习资源最丰富。

**开源机器人构建者（按平台）**：

| 你在搭什么 | 推荐板卡 | 理由 |
|---|---|---|
| Trossen OpenArm / 桌面机械臂 | Intel NUC 类 x86 或 Orin Nano 8GB | 不受重量约束，开发便利优先 |
| LeRobot-Humanoid / roboto_origin | Jetson Orin Nano 8GB | 社区驱动最全，教程可直接复用 |
| Unitree Go2 / G1 二次开发 | 沿用原厂算力 + 外挂 Orin NX | 别动原控制栈，把 VLA 放在外挂板上跑 |
| 天工 TienKung 全尺寸复刻 | Jetson Thor T3000/T5000 | 全身自由度多，需算力+内存同时富余 |

**通用建议**：**先按你要跑的模型定档位，再按供电和结构定型号，最后才看价格。** 反过来做（先看价格）几乎必然返工——因为算力不够时你没法靠软件补，而供电不够时你要重做整个电源系统。

---

## 九、趋势判断

**第一，Jetson Thor正在确立机器人端侧计算的绝对标准。** NVIDIA通过"开源模型（GR00T 1.7）+ 封闭硬件（Jetson Thor）+ 仿真平台（Isaac Sim）+ 开发者生态（300万）"的飞轮锁定生态。LeRobot v0.6.0默认推荐GR00T 1.7且Jetson Thor完成集成验证，意味着选择LeRobot的开发者会自然向Thor平台倾斜。这种"软件开源、硬件锁定"的策略和当年CUDA GPU的路径如出一辙。

**第二，高通的切入点是NVIDIA覆盖不到的场景。** SIL3功能安全、GMSL2传感器直连、车规级可靠性——这些是Jetson生态的弱项。Figure AI转向高通说明，在人形机器人量产阶段，功能安全认证和传感器集成效率可能比纯算力更重要。高通不需要在CUDA生态上正面竞争，只要把"需要安全认证的机器人"这个细分市场吃下来就够了。

**第三，算力标定口径需要行业标准化。** 2070 FP4 TFLOPS、700 TOPS、180 TOPS——这三组数字来自不同精度、不同架构、不同标定方式，直接比大小会误导选型。RoboParts数据集在 `chips` 实体中用结构化字段区分 `fp4_tflops`、`int8_tops`、`fp8_tflops`，就是为了解决这个问题。当芯片选型从"比数字"走向"比场景适配"，结构化数据的价值才会真正显现。

2026年机器人端侧芯片的竞争才刚开始。Jetson Thor T3000/T2000要到2027年第一季度才供货，Dragonwing IQ10的商用可用性"后续公布"，Intel Core Ultra Series 3的130家合作伙伴还在测试阶段。对于正在做选型决策的团队，现在不是下最终结论的时候，而是把芯片选型和VLA模型选型绑定在一起做原型验证的时候——因为这两件事，已经分不开了。

**对开源构建者的最后一条建议**：供货周期是最容易被忽视、也最能拖垮项目的变量。Thor T3000 要等到 2027 Q1，IQ10 商用时间未定——如果你的项目要在半年内跑起来，现在能稳定买到的 Orin 系列才是唯一现实选项。下单前用[供应商寻源](https://roboparts.cc/suppliers.html)确认真实交期，比看规格表更重要。

---

*本文芯片规格数据截至2026年7月27日，来源为NVIDIA官网/博客、高通OnQ博客、Intel新闻室官方发布。部分厂商未公开的数据（功耗、价格、FP8/INT8精确TOPS等）已标注。*

*RoboParts数据集收录 {{RP:CAT:chips}} 款芯片结构化规格，访问 [roboparts.cc](https://roboparts.cc) 获取最新芯片选型数据。GitHub：[github.com/roboparts/roboparts-dataset](https://github.com/roboparts/roboparts-dataset)*

---

**RoboParts · 开源机器人构建者资源**

- 🔧 免费 BOM 兼容性检查：https://roboparts.cc/bom-checker.html
- 📦 开源组件兼容性数据层：https://roboparts.cc/oss.html
- 🔌 兼容性数据 API（Pro）：https://roboparts.cc/data-hub.html
- 🛒 供应商寻源：https://roboparts.cc/suppliers.html

正在构建或维修开源机器人？用 RoboParts 把零件兼容性一次性查清。

---
