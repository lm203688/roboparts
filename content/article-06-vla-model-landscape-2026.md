---
title: "2026年VLA模型全景图：开源机器人构建者该给自己的机器人装哪个大脑？"
description: "WAIC 2026成为VLA模型爆发拐点。本文面向开源机器人构建者，系统对比腾讯Hy-Embodied、面壁MiniCPM-Robot、大晓Kairos 3.1、银河通用AstraBrain、蚂蚁LingBot-VLA 2.0、智平方NeuroVLA、智谱ZR-0、NVIDIA GR00T 1.7等10+款主流VLA模型的参数规模、基准表现、硬件需求与开源状态，并给出在天工TienKung、Unitree G1/Go2、OpenArm、LeRobot-Humanoid上的端侧部署选型建议。"
keywords: ["VLA模型", "视觉语言动作模型", "开源机器人", "Hy-Embodied", "MiniCPM-Robot", "Kairos 3.1", "AstraBrain", "LingBot-VLA", "NeuroVLA", "GR00T 1.7", "LeRobot", "具身智能", "WAIC 2026", "机器人AI模型", "端侧VLA部署", "天工机器人", "Unitree G1"]
tags: ["open-source-robotics", "humanoid", "sourcing", "vla", "lerobot", "edge-compute"]
slug: vla-model-landscape-2026
date: 2026-07-27
author: RoboParts Research
canonical: https://roboparts.cc/articles/vla-model-landscape-2026
---

# 2026年VLA模型全景图：开源机器人构建者该给自己的机器人装哪个大脑？

> 本文首发于 [RoboParts 开源机器人兼容性平台](https://roboparts.cc)。数据集引用入口：[roboparts.cc/api/data.json](https://roboparts.cc/api/data.json)。

2026年7月的WAIC会场，每隔几小时就有一款新的VLA模型发布。腾讯、面壁、大晓、银河通用、蚂蚁、智谱、智平方、阿里、NVIDIA——九家团队在四天内密集亮出各自的具身智能基座，参数从0.5B跨度到30B，架构从纯VLA延伸到世界模型、类脑分层，开源策略也从完全闭源到HuggingFace同步上传各不相同。

**但如果你是一个正在自己搭机器人的人——手上是一台 Unitree Go2、一套 Trossen OpenArm，或者一台照着天工 TienKung 图纸复刻的双足——这份"全景"真正要回答的问题只有三个：**

1. 哪些模型是**真开源**、权重能下载、许可证允许你用？
2. 我这台机器上的**算力板卡跑得动哪一档**？
3. 换模型之后，我的**相机、执行器、总线还对得上吗**？

这并非简单的"参数军备竞赛"。当一个0.89B的模型（FabriVLA）在Meta-World MT50上以90.0%的成绩登顶，超越Physical Intelligence的π₀，参数规模就不再是衡量VLA能力的唯一标尺。真正决定选型的，是**参数规模×架构路线×硬件门槛×开源程度**这四个维度的交叉。

本文基于WAIC 2026期间公开的技术报告、HuggingFace模型卡和GitHub仓库，对10款代表性VLA模型做系统对比，并给出面向不同部署场景的选型建议。文中每一处涉及硬件门槛的地方，都会回到"你手上这台开源机器人能不能跑"这个问题上。

---

## 一、参数规模梯队：从端侧0.5B到云端30B

VLA模型的参数规模直接决定了它能在什么硬件上跑。2026年上半年的发布潮让端侧可部署的门槛大幅下移，0.5B-3B区间成为最拥挤的赛道——**这个区间也正好是绝大多数开源机器人自带算力板卡的能力范围**。

| 梯队 | 参数规模 | 代表模型 | 典型硬件门槛 | 部署方式 |
|:---:|:---:|------|------|------|
| 轻量级 | 0.5B-1B | SmolVLA（0.45B）、FabriVLA（0.89B）、MiniCPM-RobotTrack（0.9B） | 消费级GPU、RK3588、Jetson Orin Nano | 端侧原生部署 |
| 主流端侧 | 1.5B-3B | MiniCPM-RobotManip（1.5B）、GR00T 1.7（3B）、ZR-0（2.6B）、LDA-1B（1.6B） | Jetson AGX Orin、Jetson Thor T2000 | 端侧为主，可量化压缩 |
| 中型 | 6B-8B | LingBot-VLA 2.0、Kairos 3.1（8B标准测试模型） | Jetson Thor T3000/T5000 | 端侧需高算力，或端云协同 |
| 大型/云端 | 30B+ | Hy-Embodied-VLM-1.0（MoE，激活约3B）、AstraBrain旗舰版 | 云端GPU集群 | 云端推理，端侧仅运行感知/控制 |

一个值得注意的现象：**MoE架构让"大参数、小激活"成为可能**。腾讯Hy-Embodied-VLM-1.0总参数约300亿，但每个Token仅激活约30亿，这意味着它的实际推理负载接近3B模型，却在能力上对标旗舰级。这种架构正在改写"参数规模=硬件需求"的传统等式。

RoboParts数据集的 `robot_ai_models` 实体库收录了 {{RP:CAT:robot_ai_models}} 个机器人AI模型条目，结构化记录了每款模型的参数量、推荐算力和开源地址，可通过[开源组件兼容性数据层](https://roboparts.cc/oss.html)在线查询。

**给构建者的快速对照**：如果你的机器上装的是 Jetson Orin Nano（LeRobot-Humanoid、roboto_origin 常见配置），你的可选范围基本就是第一档；Unitree Go2/G1 的标配算力大致落在第一到第二档之间；只有专门加装 Thor 级板卡的天工 TienKung 复刻机，才谈得上第三、四档。**先确认板卡，再挑模型，顺序反了会白折腾。**

---

## 二、十大模型逐一拆解

### 2.1 腾讯 Hy-Embodied：全栈三件套

腾讯Robotics X实验室与混元团队联合推出的Hy-Embodied是WAIC上少数以"全栈"姿态出现的方案，三款模型各司其职：

- **Hy-Embodied-VLM-1.0**：约30B参数的MoE架构，每Token激活约3B。定位"右脑感知"，负责场景理解、物理空间状态推理、动作变化理解、时序推理。官方称在同参数级模型上"看物知用/看景知变/看远知返"三项能力领先。
- **Hy-Embodied-RxBrain-1.0**：约6.2B参数，采用Mixture-of-Transformers架构，统一文本推理与视觉想象。GenEval得分82.4，CV-Bench 88.59，联合规划得分0.68（超Cosmos3-Nano的0.521），真机平均成功率87%（π₀为68%）。这是三件套里技术含量最高的一款，首次在单一模型内实现"推理+视觉生成"深度协同。
- **Hy-Embodied-VLA-0.5**：A3B规模（激活约3B），定位"小脑+身体"，负责连接感知与行动。已开源UMI数据格式版本，支持双臂操作。

技术亮点在于RxBrain的"大脑认知"层——它不只是理解指令，而是先生成对未来的视觉想象，再基于想象规划动作。这种"脑补结局"机制让模型在复杂长时序任务上表现突出。与越疆科技合作的化妆品产线案例显示，完整VLA训练-验证-部署链路任务成功率超95%。

### 2.2 面壁 MiniCPM-Robot：1.5B端侧破局者

面壁智能在WAIC 2026期间开源的MiniCPM-Robot系列，把"端侧可跑的VLA"这件事做到了新高度：

- **MiniCPM-RobotManip**：1.5B参数，基于MiniCPM-V 4.6训练。RMBench上下文记忆得分53.5，而π0.5仅10.4——差距来自面壁的视觉Token极致压缩技术，让模型具备1分钟具身原生记忆能力。在H100上单帧决策约120ms，比π0.5的234ms快一倍，流式推理成本减半。
- **MiniCPM-RobotTrack**：0.9B参数，与南京大学联合研发，业内首款面向目标跟踪的紧凑型VLA。在机器狗本地算力上即可5Hz+稳定跟踪，断网后可持续工作。
- **PhyAI推理框架**：配套发布的推理加速框架，延迟减半，部署效率提升，支持无网环境。

MiniCPM系列累计下载量已突破3800万，这意味着大量个人开发者已经在真实机器人上跑通。端侧小参数VLA的突破直接刺激了轻量化伺服电机、Jetson Nano级计算模组、低功耗传感器的需求。

GitHub：[github.com/OpenBMB/MiniCPM-Robot](https://github.com/OpenBMB/MiniCPM-Robot)

### 2.3 大晓 Kairos 3.1：世界模型的新标杆

大晓机器人发布的Kairos 3.1（开悟世界模型3.1）在世界模型赛道上拿出了压倒性数据：

- 全球世界模型视频生成+状态预测评测双第一，超越Cosmos 3、Physical Intelligence、MotuBrain等
- ACE-BRAIN-0.5获12项全球SOTA
- 8B标准测试模型在NVIDIA Jetson Thor平台上BF16精度推理延迟仅125ms——而Cosmos 3 Nano的延迟是6486ms，快了52倍

Kairos 3.1采用混合Transformer+共享混合注意力架构，把"理解-生成-预测"一体化，构建"理解-推演-执行-反思"自进化体系。输入机器人结构参数即可快速适配机械臂或人形机器人。已实现家庭洗衣全流程自主操作及错误自修正。

配套的KairosRT计算引擎是实现125ms延迟的关键——它针对Thor平台的异构AI加速器做了深度优化。大晓同步开源了L5级家居复杂任务数据集ACE-Data-0和具身数据标准底座Ego Matrix。

### 2.4 银河通用 AstraBrain：端到端三代演进

银河通用的AstraBrain（银河星脑）走的是"端到端VLA→增强型VLA→类脑VLA"三代演进路线：

- **AstraBrain旗舰版**：百亿级参数，采用"大脑-小脑-动作控制"三层统一架构，是全球首个统一该架构的端到端模型。驱动Galbot G1/S1全场景实时演示，无预设表演。
- **LDA-1B**：1.6B参数的跨本体隐式世界-动作基础模型，被RSS 2026收录。

Galbot S1已进入宁德时代和博世产线，四台机器人协同完成电芯箱体上料、堆叠、扫码、下线，稳定运行超3个月。零售款9万元在京东售罄。这个案例的意义在于：VLA模型不再是Demo演示，而是扛起了工业产线的真实负载。

需要特别澄清一个常见误区：**NeuroVLA并非银河通用的产品，而是智平方的类脑VLA**。两者架构思路相似（都采用分层），但归属不同，下文单独拆解NeuroVLA。

### 2.5 蚂蚁 LingBot-VLA 2.0：跨本体泛化

蚂蚁灵波科技于7月8日开源的LingBot-VLA 2.0，核心卖点是跨本体泛化：

- 6B参数多模态VLA，支持手臂、夹爪、灵巧手、腰部、头部及移动底盘全信号控制
- 适配17家机器人厂商20多种构型，模块化设计大幅降低二次开发门槛
- 预训练融入6万小时真实物理数据

跨本体能力是VLA落地的关键瓶颈——大多数模型只能在特定机器人上跑，换一个构型就要重新训练。LingBot-VLA 2.0的模块化接口协议有可能成为行业标准，这也是它获WAIC"镇馆之宝"的原因。HuggingFace、魔搭社区、GitHub三平台同步更新。

### 2.6 智平方 NeuroVLA：全球首个类脑架构VLA

智平方的NeuroVLA（2026年4月发布，WAIC期间展示）代表了VLA的第三条技术路线——类脑分层架构：

- **大脑层**：GPU运行，约10Hz，负责高级认知规划
- **小脑层**：自适应滤波器，约500Hz，负责运动协调
- **脊髓层**：神经形态芯片，仅0.4W功耗，事件驱动，负责反射

碰撞反射延迟20ms，传统方案>200ms，差了一个数量级。抖动抑制75%以上，碰撞后任务恢复率54.8%（传统方案为0）。AlphaBrain Platform已开源，单张4090即可运行。

NeuroVLA是AlphaBrain具身大模型四代迭代的最新成果（RoboMamba→FiS-VLA→Video2Act→NeuroVLA），搭载于AlphaBot 2。它的意义在于证明了"分层+专用硬件"可以突破纯Transformer架构的延迟瓶颈。

### 2.7 智谱 ZR-0：26亿参数+1000小时数据

智谱与中国人民大学联合发布的ZR-0（6月30日披露）：

- 26亿参数端到端VLA，采用"全身密集具身思维链"（ECoT）实现跨实体迁移
- 单臂/双臂/人形一键通用
- 配套开源6000万帧/近1000小时机器人数据集（ProcCorpus-60M）
- 覆盖LIBERO单臂仿真、RoboTwin 2双臂仿真、RoboCasa人形桌面仿真及真实xArm机械臂

智谱作为万亿估值大模型公司正式入局具身智能，标志行业进入"巨头混战"阶段。其开源数据集将加速社区数据标准化进程——RoboParts数据集的 `entities.json` 已开始对齐这种标准化格式。

### 2.8 NVIDIA GR00T 1.7：开源生态的锚点

NVIDIA的GR00T 1.7（GR00T N1.7）是整个VLA生态的关键基础设施：

- 3B参数，以Cosmos-Reason2-2B为VLM主干+Diffusion Transformer动作解码器
- 32000小时真实示范+8000小时仿真预训练
- 首个可商用开源人形机器人基础模型
- **已集成入LeRobot v0.6.0**，成为默认推荐模型
- Jetson Thor原生优化，2070 FP4 TFLOPS算力下流畅运行

NVIDIA与HuggingFace的合作把GR00T 1.7和Isaac Teleop遥操作框架同时引入LeRobot，连接了NVIDIA 300万机器人开发者与HuggingFace 1600万AI开发者生态。Cosmos 3物理世界模型后续也将接入，形成"世界模型+VLA"闭环。

### 2.9 阿里 Qwen-Robot：三大模型矩阵

阿里通义的Qwen-Robot系列覆盖三个维度：

- **Qwen-RobotManip**：VLA操作模型，"灵巧的手"，LIBERO成功率90%+
- **Qwen-RobotNav**：VLN移动模型，"认路的脚"
- **Qwen-RobotWorld**：世界模型，"会思考的大脑"

本体感知提示机制让模型无需改架构即可适配不同机器人。DOMINO动态操控零样本表现优异。Qwen-VLA于5月29日发布，Qwen-Robot系列于6月16日WAIC前发布。

### 2.10 优艾智合 FabriVLA：0.89B登顶Evo-SOTA

优艾智合FabriX团队的FabriVLA以0.89B参数登顶Evo-SOTA Meta-World MT50基准：

- tier-average成功率90.0%，超越π₀（47.9%）、SmolVLA（68.2%）、RoboTron-Mani（77.7%）
- 整体episode成功率92.0%
- 各难度梯度：简单95.0%、中等88.2%、困难86.7%

FabriVLA的技术路线是门控自注意力+深浅层视觉特征融合，单阶段联合训练，不依赖大规模预训练。1B级参数击败大模型，打破了工业具身智能"性能-成本-部署"不可能三角。这为边缘端部署提供了基础——0.89b的模型可以在Jetson Orin级别硬件上跑起来。

---

## 三、技术路线分化：三条路同时跑

把这十款模型放在一起看，2026年VLA赛道已经分化出三条清晰的技术路线，它们不是替代关系，而是解决不同层面的问题。

### 路线A：纯VLA——感知到动作的端到端映射

代表：MiniCPM-Robot、FabriVLA、GR00T 1.7、ZR-0

这是最主流的路线，输入视觉+语言，输出动作序列。优点是架构简洁、训练数据相对易得、开源生态成熟。缺点是缺乏对未来的"想象"能力，遇到训练分布外的场景容易失效。

### 路线B：世界模型——先想象未来再行动

代表：Kairos 3.1、Hy-Embodied-RxBrain、Sereact Cortex 2.0、DVA

世界模型（WAM）让机器人在行动前先在脑内"预演"结果，从结果反推最优动作。Kairos 3.1的"理解-推演-执行-反思"闭环、RxBrain的"视觉想象+推理协同"都属于这一路线。NVIDIA 6月发表的长文系统阐述了WAM范式崛起，业界共识是最终赢家可能是VLA与WAM的混合体。

### 路线C：类脑分层——专用硬件突破延迟瓶颈

代表：NeuroVLA（智平方）、AstraBrain（银河通用）

把大脑、小脑、脊髓的功能分工用不同硬件实现：大脑跑在GPU上做慢思考，小脑用自适应滤波器做高频协调，脊髓用神经形态芯片做微秒级反射。NeuroVLA的0.4W脊髓层实现了20ms碰撞反射，这是纯GPU方案很难达到的指标。

三条路线并非互斥。GR00T 1.7接入Cosmos 3世界模型，本质是路线A+B融合；NeuroVLA的大脑层也可以跑VLA模型。RoboParts数据集在 `robot_ai_models` 分类中已开始用 `architecture_type` 字段区分这三种路线，方便开发者按需筛选。

---

## 四、基准评测：数字背后的门道

不同模型常引用不同基准，直接对比容易误读。这里把可查证的公开数据整理如下。

| 模型 | 基准 | 得分 | 对比项 |
|------|------|------|------|
| FabriVLA（0.89B） | Meta-World MT50 tier-average | 90.0% | π₀ 47.9%、SmolVLA 68.2% |
| MiniCPM-RobotManip（1.5B） | RMBench上下文记忆 | 53.5 | π0.5 10.4 |
| Kairos 3.1（8B） | 世界模型视频生成+状态预测 | 双第一 | 超Cosmos 3、PI、MotuBrain |
| Hy-Embodied-RxBrain（6.2B） | 真机平均成功率 | 87% | π₀ 68% |
| Hy-Embodied-RxBrain | 联合规划 | 0.68 | Cosmos3-Nano 0.521 |
| 越疆DobotWAM | LIBERO平均成功率 | 99.25% | — |
| Qwen-RobotManip | LIBERO成功率 | 90%+ | — |
| NeuroVLA | 碰撞后任务恢复率 | 54.8% | 传统方案 0% |
| NeuroVLA | 碰撞反射延迟 | 20ms | 传统方案 >200ms |

阅读这些数字时要注意三点。第一，Meta-World MT50和LIBERO评测维度不同，前者考察多任务泛化，后者侧重空间关系与长时序，跨基准直接比大小没有意义。第二，RMBench专门考察上下文记忆，MiniCPM-Robot的53.5分领先π0.5十倍以上，但这只说明记忆能力，不代表整体操控更强。第三，Kairos 3.1的"双第一"是世界模型评测，不是VLA操控评测，它和FabriVLA不在同一赛道。

---

## 五、硬件需求映射：对开源机器人构建者而言，模型选型就是芯片选型

VLA模型的参数规模直接决定了端侧部署所需的芯片算力。根据2026年的工程实践，可以给出以下匹配关系。

| 模型规模 | 推荐芯片 | 算力门槛 | 典型推理延迟 |
|:---:|------|:---:|:---:|
| 0.5B-1B | Jetson Orin Nano（20-40 TOPS）、RK3588 | 20 TOPS | 30-80ms |
| 1.5B-3B | Jetson AGX Orin（275 TOPS）、Jetson Thor T2000 | 100 TOPS | 80-150ms |
| 6B-8B | Jetson Thor T3000（865 FP4 TFLOPS）、高通Dragonwing IQ10（700 TOPS） | 500 TOPS | 120-200ms |
| 30B+（MoE激活3B） | Jetson Thor T5000（2070 FP4 TFLOPS） | 1000+ TOPS | 200-500ms |

控制频率方面，端侧VLA需维持50Hz以上的实时控制闭环，S2任务意图层以7Hz运行即可。几十毫秒的推理滞后在控制闭环中可以接受，但超过200ms就会影响动态任务的稳定性。这也是为什么Kairos 3.1把8B模型的延迟从6486ms压到125ms——52倍的优化不只是数字好看，而是让8B世界模型首次具备了端侧实时部署的可行性。

RoboParts数据集收录了 {{RP:CAT:chips}} 款芯片的结构化规格数据，包括AI算力、内存带宽、功耗、支持的通信协议。通过[选型引擎](https://roboparts.cc/selection.html)可以交叉查询"某款VLA模型需要哪类芯片"以及"某款芯片能跑哪些模型"。

**换算力板卡时最容易被忽略的三件事**（这也是开源项目升级 VLA 时的典型返工点）：

1. **供电余量**。Orin Nano 到 AGX Orin，峰值功耗从 15W 跳到 60W。原来的分电板和电池可能直接不够，尤其是同时驱动 20+ 关节时。
2. **散热与安装孔位**。Thor 系列模块尺寸与 Orin 不同，开源整机的电子舱结构件往往要重开。
3. **接口数量**。多目相机 + 深度相机 + IMU 全接上去，USB3 带宽和 CSI 通道可能不够，需要加扩展板。

这三项都属于典型的"参数表上看不出来、装到一半才发现"的冲突。把新板卡型号和现有 BOM 一起丢进 [BOM 兼容性检查](https://roboparts.cc/bom-checker.html)，可以在下单前就把它们查出来。

---

## 六、LeRobot v0.6.0：开源生态的枢纽

HuggingFace于2026年7月初发布的LeRobot v0.6.0，正在成为机器人AI的"PyTorch时刻"。本次更新的核心：

- **三大世界模型策略**：VLA-JEPA、FastWAM、LingBot-VA，首次让开源机器人具备"想象未来"能力
- **五大新VLA架构**：GR00T N1.7、MolmoAct2、EO-1、EVO1、Multitask DiT
- **奖励模型集成**：Robometer、TOPReward，支持自主评估与迭代优化
- **lerobot-rollout CLI**：支持DAgger风格的人机协同纠错闭环
- **HF Jobs训练支持**：云端训练流水线大幅简化

GR00T 1.7已替代N1.5成为LeRobot默认推荐模型，NVIDIA Jetson Thor与LeRobot Reachy 2完成集成验证。这意味着选择LeRobot生态的开发者，硬件选型会自然向Thor平台倾斜。

LeRobot的25K+ Stars和1500万次数据集下载量，让它成为VLA模型分发的最大渠道。对开源机器人构建者来说，这条信息的实际含义是：**只要你的硬件能被 LeRobot 识别，模型侧就几乎不用操心**——GR00T 1.7、SmolVLA、社区微调版可以直接换着试。

反过来说，接入 LeRobot 生态对硬件是有要求的：相机需要标准 UVC 或已有驱动，关节需要能暴露成统一的位置/力矩接口，遥操作设备需要在支持列表内。LeRobot-Humanoid、Trossen OpenArm 天然满足；Unitree Go2/G1 需要走 SDK 桥接；自制整机则往往要自己写适配层。RoboParts 数据集中的 `robot_ai_models` 实体保持与 LeRobot 模型格式兼容，并在[开源组件兼容性数据层](https://roboparts.cc/oss.html)标注了各开源平台与 LeRobot 的对接状态，可以先查再动手。

---

## 七、选型建议：按场景倒推模型

脱离场景谈"哪个模型最好"没有意义。以下是按部署场景倒推的选型路径。

### 场景1：开源构建者/个人开发者/教育/原型验证

预算敏感，消费级硬件，优先开源。典型机型：LeRobot-Humanoid、roboto_origin、Trossen OpenArm。

- **首选**：SmolVLA（0.45B）或MiniCPM-RobotManip（1.5B）。前者单张消费级GPU即可跑，后者在H100上120ms决策。
- **硬件**：Jetson Orin Nano 8GB（40 TOPS，约¥1490）或RK3588方案。
- **生态**：走LeRobot v0.6.0，用GR00T 1.7做基线，社区微调版丰富。
- **落地顺序建议**：先在 OpenArm 这类单臂平台上跑通"采数据→微调→回放"整条链路，再迁移到双足/全身平台。上肢平台的失败成本远低于双足，调试效率高一个量级。

### 场景2：工业产线/商业部署

可靠性优先，需要力控精度和长时稳定运行。

- **首选**：FabriVLA（0.89B，边缘端部署）或Hy-Embodied全栈（云端RxBrain+端侧VLA-0.5）。
- **硬件**：Jetson Thor T3000（865 FP4 TFLOPS）或高通Dragonwing IQ10（700 TOPS + SIL3功能安全）。
- **参考案例**：银河通用Galbot S1（宁德时代产线）、越疆+腾讯（化妆品产线）、擎仓EVO-1（欧莱雅产线）。

### 场景3：人形机器人/全身体控

需要全身协调、长时序任务、跨本体泛化。典型机型：天工 TienKung 复刻机、Unitree G1 二次开发。

- **首选**：LingBot-VLA 2.0（6B，支持20+构型）或AstraBrain旗舰版（大脑-小脑-动作控制三层架构）。
- **硬件**：Jetson Thor T5000（2070 FP4 TFLOPS，128GB统一内存）。
- **补充**：若需类脑反射能力，参考NeuroVLA的脊髓层方案（0.4W神经形态芯片）。
- **跨本体提示**：LingBot-VLA 2.0 声称适配 20 多种构型，但"适配"指的是接口协议层面，不代表零样本可用。换到你自己的开源整机上，关节顺序、URDF 坐标系定义、力矩单位这些细节仍需逐项对齐——这部分工作量通常比部署模型本身更大。

### 场景4：世界模型/预演再执行

需要在动作前预演结果，规避错误。

- **首选**：Kairos 3.1（8B，Jetson Thor平台125ms延迟）或Sereact Cortex 2.0（"预演再执行"，宝马产线验证）。
- **硬件**：Jetson Thor T5000，BF16精度。
- **数据**：大晓ACE-Data-0或智谱ProcCorpus-60M可作为预训练补充。

---

## 八、数据集与交叉引用

本文涉及的所有VLA模型、芯片、执行器参数，均可在RoboParts数据集中结构化查询：

```python
# 查询所有开源VLA模型及其推荐硬件
import requests
db = requests.get("https://roboparts.cc/api/data.json").json()

open_source_vla = [
    m for m in db["robot_ai_models"]
    if m.get("license", "").startswith("open")
    and "VLA" in m.get("type", "")
]

# 交叉引用：某款模型推荐哪些芯片
for model in open_source_vla:
    recommended_chips = [
        c for c in db["chips"]
        if c.get("specs", {}).get("ai_tops", 0)
        >= model.get("min_tops", 0)
    ]
    print(f"{model['name']}: {[c['name'] for c in recommended_chips]}")
```

数据集覆盖 {{RP:CATEGORIES}} 大分类、{{RP:TOTAL}} 个实体条目，含 {{RP:CAT:actuators}} 款执行器、{{RP:CAT:chips}} 款芯片、{{RP:CAT:protocols}} 款通信协议、{{RP:CAT:robot_ai_models}} 个机器人AI模型。

**开源构建者的完整工作流**：

1. 在[开源组件兼容性数据层](https://roboparts.cc/oss.html)找到你的平台（天工 TienKung / Unitree Go2/G1 / OpenArm / LeRobot-Humanoid / roboto_origin），查它当前的算力配置与已验证模型
2. 想升级到更大的 VLA？把目标算力板卡 + 现有 BOM 提交到 [BOM 兼容性检查](https://roboparts.cc/bom-checker.html)，查供电、接口、结构冲突
3. 需要换传感器或执行器，用[选型引擎](https://roboparts.cc/selection.html)找等效型号
4. 用[供应商寻源](https://roboparts.cc/suppliers.html)确认 Thor / Orin 板卡与配套件的实际交期
5. 要在自研工具链或 CI 中自动做这套校验，走[兼容性数据 API](https://roboparts.cc/data-hub.html)

GitHub：[github.com/roboparts/roboparts-dataset](https://github.com/roboparts/roboparts-dataset)

---

## 九、趋势判断

把WAIC 2026的十款模型放在一起，三个判断浮现出来。

**第一，参数竞赛正在让位于架构竞赛。** FabriVLA用0.89B登顶、MiniCPM用1.5B做到端侧部署、Kairos用8B实现125ms延迟——这些突破都来自架构创新（门控自注意力、视觉Token压缩、KairosRT计算引擎），而非单纯堆参数。2026年下半年，"同等参数下更强"会比"参数更大"更有竞争力。

**第二，世界模型与VLA的融合不可逆。** GR00T 1.7接入Cosmos 3、Kairos 3.1一体化架构、RxBrain的视觉想象+推理协同、LeRobot v0.6.0引入世界模型策略——所有头部玩家都在向"先想象再行动"靠拢。纯VLA模型不会消失，但会越来越多地作为世界模型的动作执行层存在。

**第三，端侧部署门槛的下降速度超预期——这对开源构建者是最大的利好。** 一年前7B模型还需要云端推理，现在1.5B模型在H100上120ms决策、0.89B模型在Orin级别硬件上可跑。这意味着一台几千元的开源机械臂或半尺寸人形，第一次真正具备了跑现代 VLA 的资格。

但门槛下移带来的直接后果是：**瓶颈从"模型"转移到了"硬件配得对不对"**。当更多开发者能在端侧跑VLA，对执行器精度、传感器类型、通信协议的选型需求就会指数级增长；而开源项目的 BOM 往往滞后于模型迭代速度，你照着一年前的物料表买回来的相机，可能根本喂不出模型要的观测格式。RoboParts数据集的 `robot_ai_models` 与 `chips`、`actuators`、`sensors` 实体之间的关联映射，正是为这个趋势准备的。

WAIC 2026不是VLA模型的终点，而是从"实验室Demo"转向"人人可复现"的起点。当银河通用S1在宁德时代稳定运行3个月、智元G2 Max在京东物流7×24小时作业，同时 GR00T 1.7 已经进了 LeRobot 默认配置——VLA模型的硬件选型就已经从研究问题变成了工程问题。而工程问题，正是结构化兼容性数据最能发挥作用的地方。

---

*本文数据截至2026年7月27日，基于WAIC 2026公开技术报告、HuggingFace模型卡、GitHub仓库及厂商官方博客交叉核实。部分厂商未公开的数据已标注。*

*RoboParts数据集持续更新VLA模型与硬件关联映射，访问 [roboparts.cc](https://roboparts.cc) 获取最新结构化数据。*

---

**RoboParts · 开源机器人构建者资源**

- 🔧 免费 BOM 兼容性检查：https://roboparts.cc/bom-checker.html
- 📦 开源组件兼容性数据层：https://roboparts.cc/oss.html
- 🔌 兼容性数据 API（Pro）：https://roboparts.cc/data-hub.html
- 🛒 供应商寻源：https://roboparts.cc/suppliers.html

正在构建或维修开源机器人？用 RoboParts 把零件兼容性一次性查清。

---
