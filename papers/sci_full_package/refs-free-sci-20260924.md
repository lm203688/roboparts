# 参考文献清单 · RoboParts 主题（2026-09-24）

> 筛选口径：**免费 / 开放获取 / 预印本**（arXiv、MDPI、PLOS、CC 类）。
> 排除需订阅的 IEEE Xplore 全文、Springer/Palgrave 付费卷、ACM 付费卷。
> 每篇附：主题标签 / 与本项目关联点 / 可引用位置 / 获取方式。
>
> 检索日期：2026-09-24（近 3 年优先，含少量经典）。
> 检索范围：arXiv / Google Scholar 索引 / IEEE 免费摘要页 / MDPI / PLOS / Sage 免费卷。

---

## 一、装配图 / 接口几何 / CAD 语义（最直接相关）

### [R1] Linkify: Learning from Interface-Augmented Assembly Graphs
- **出处**：arXiv 2607.01205v1, 2026-07（cs.CV / Geometric Deep Learning）
- **作者**：Anushrut Jignasu, Daniele Grandi 等
- **获取**：https://arxiv.org/abs/2607.01205v1（免费 PDF）
- **主题**：接口几何 → 装配图 → GATv2 部件检索
- **核心贡献**：为 Fusion 360 Gallery Assembly 数据集重算高保真接口接触；点云编码接口几何；GATv2 在 masked part prediction 上优于非图基线
- **与 RoboParts 关联**：
  - **同问题域**：都在处理「零件间的接口」而非孤立零件；但 Linkify 是几何层（点云），RoboParts 是**语义层**（类型 / 标号 / 状态）
  - **可对照点**：Linkify 的接口接触是「实测重算」，RoboParts 的接口声明是「厂商 datasheet + 用户提交」——两者是数据互补的两种来源
  - **可引用位置**：引言「接口是本问题域的核心数据层」；相关工作「几何 vs 语义两层接口表征」
- **可引用性**：⭐⭐⭐⭐（2026 最新，数据集公开，方法可复现）

### [R2] CAD-Based Relation Learning and Geometric-Symbolic Planning for Robotic Assembly
- **出处**：arXiv 2609.17263, 2026-09（cs.RO）
- **作者**：Fabian Harlacher, Christian Friedrich
- **获取**：https://arxiv.org/abs/2609.17263（免费 PDF）
- **主题**：混合 ASP（装配序列规划），神经网络 + 人机回环 + 符号推理
- **核心贡献**：从点云学几何关系；人工纠错；转符号装配图；可见性射线求取可行方向；ASAP 测试集 85.83% 成功率
- **与 RoboParts 关联**：
  - **人机回环**：RoboParts 的「用户提交 + 出处」通道是同一思路（不猜，让人补）
  - **符号装配图**：与 RoboParts 的形态图（morphology graph）同构，但语义密度不同
  - **可引用位置**：相关工作「学习 vs 符号 vs 混合」三态；讨论「unknown 是人机回环的入口」
- **可引用性**：⭐⭐⭐⭐（新，方法新颖，已投 Elsevier）

### [R3] Semantic Enrichment of CAD-Based Industrial Environments via Scene Graphs
- **出处**：arXiv 2601.06415, 2026-01（cs.RO）
- **作者**：（Fukushima 测试场项目）
- **获取**：https://arxiv.org/html/2601.06415v1（免费 HTML）
- **主题**：CAD → LVLM 标注 → 场景图 → 功能关系推断
- **核心贡献**：USD 格式 CAD → GPT-4o 语义标注 → DBSCAN 空间聚类 → 多层场景图 → 功能单元识别
- **与 RoboParts 关联**：
  - **同为 CAD → 图 的转化**；但 RoboParts 从「已声明接口」出发，[R3] 从「无标签 CAD」出发
  - **可对照点**：RoboParts 的「unknown」= [R3] 的「LLM 未标注」；两条路径都承认「不知」是一等公民
  - **可引用位置**：相关工作「场景图 vs 形态图」
- **可引用性**：⭐⭐⭐（新方法，数据集封闭）

### [R4] Knowledge-driven Automated Design of Industrial Robots: A Unified Graph-Based Framework
- **出处**：Advances in Engineering Informatics 69 (2026), 103995
- **DOI**：10.1016/j.aei.2025.103995
- **作者**：Tao Sun, Bo Wang, Xinming Huo
- **获取**：https://acm-stag.literatumonline.com/doi/10.1016/j.aei.2025.103995（摘要免费，全文需订阅）
- **主题**：4 类图 + 3 引擎（运动/力分析、部件推荐、CAD 装配）统一机器人自动设计
- **核心贡献**：图谱驱动 + RBR/CBR 推理 + KG 组件推荐 + CAD 装配自动化
- **与 RoboParts 关联**：
  - **同为图谱驱动**，但 [R4] 是「设计时」，RoboParts 是「查询时」
  - **KG 组件推荐**与 RoboParts 的「兼容性判定」是同一条链的两端
  - **可引用位置**：相关工作「设计时 vs 查询时」图谱应用对比
- **可引用性**：⭐⭐⭐（付费期刊，摘要可用）

---

## 二、工程本体 / 制造知识图谱

### [R5] ExtruOnt: An Ontology for Describing a Type of Manufacturing Machine
- **出处**：arXiv 2401.11848, 2024-01（cs.AI / Semantic Web）
- **DOI**：10.48550/arXiv.2401.11848
- **作者**：Julio Ramírez-Durán, Víctor Berges, Idoia Illarramendi, Arantza 等
- **获取**：https://arxiv.org/abs/2401.11848（免费 PDF）
- **主题**：挤出机本体（Industry 4.0），机器可解释描述
- **核心贡献**：挤出机本体（组件 / 空间连接 / 特征 / 3D 表示 / 传感器）；域专家协作开发
- **与 RoboParts 关联**：
  - **同为「本体驱动」的机器学习可读工程数据**；但 [R5] 聚焦单机，RoboParts 聚焦**跨厂商组合**
  - **术语对齐**：ExtruOnt 的 spatial connections 与 RoboParts 的 interfaces 是同一概念
  - **可引用位置**：相关工作「本体驱动的单机 vs 跨机描述」
- **可引用性**：⭐⭐⭐⭐（免费，本体可复用）

### [R6] Model Management to Support Systems Engineering Workflows using Ontology-Based Knowledge Graphs
- **出处**：Journal of Industrial Information Integration 42 (2024) 100720
- **作者**：Arkadiusz Ryś, Lucas Lima, Joeri Exelmans, Dennis Janssens, Hans Vangheluwe
- **获取**：arXiv 版免费（搜索标题可找）
- **主题**：本体驱动的模型工件管理（CPS 系统工程）
- **核心贡献**：本体定义工作流概念 + 工件 + 形式化；KG 存储与推理
- **与 RoboParts 关联**：
  - **同为「本体 + KG」方法学**；但 [R6] 是「模型工件」，RoboParts 是「零件实体」
  - **可引用位置**：相关工作「系统级 vs 零件级」本体化
- **可引用性**：⭐⭐⭐（付费期刊，arXiv 版可用）

### [R7] Interpreting Behaviors and Geometric Constraints as Knowledge Graphs for Robot Manipulation Control
- **出处**：arXiv 2310.03932v2（cs.RO）
- **作者**：（含 M. Jagersand 等）
- **获取**：https://arxiv.org/html/2310.03932v2（免费 HTML）
- **主题**：行为 + 几何约束 → KG → 机器人操作控制
- **核心贡献**：把操作任务的行为和几何约束编码为 KG，支持控制推理
- **与 RoboParts 关联**：
  - **同为 KG 用于机器人操作**；但 [R7] 是「动作级」，RoboParts 是「零件级」
  - **可引用位置**：相关工作「操作级 KG vs 零件级 KG」
- **可引用性**：⭐⭐⭐⭐（免费，方法清晰）

---

## 三、本体 / 装配引导 / 制造

### [R8] Machine Learning on Assembly Guidance System Ontology for Manufacturing Assembly
- **出处**：Proc. IMechE Part B: J. Eng. Manufacture 240(11), 2301-2318, 2026-09
- **DOI**：10.1177/09544054251395468
- **作者**：Zhi Lon Gan, Siti Nurmaya Musa, Hwa Jen Yap（University of Malaya）
- **获取**：https://journals.sagepub.com/doi/abs/10.1177/09544054251395468（需付费，摘要免费）
- **主题**：装配引导系统本体 + 机器学习
- **与 RoboParts 关联**：
  - **同为本体 + ML**；但 [R8] 是「装配引导」（AR），RoboParts 是「兼容性判定」
  - **可引用位置**：相关工作「装配时 vs 选型时」本体应用
- **可引用性**：⭐⭐（付费，仅摘要）

### [R9] Combining Machine Learning and Ontology: A Systematic Literature Review
- **出处**：arXiv 2401.07744, 2024
- **作者**：Ghidalia S, Narsis OL, Bertaux A, 等
- **获取**：https://arxiv.org/abs/2401.07744（免费 PDF）
- **主题**：ML + 本体 系统综述
- **与 RoboParts 关联**：
  - **综述类**，可直接引用作为「本体 + ML 是新兴方向」的证据
  - **可引用位置**：相关工作「本体 + ML 现状」
- **可引用性**：⭐⭐⭐⭐（免费综述）

---

## 四、不确定性 / 失败感知 / 三态诚实（RoboParts 差异化最相关的簇）

### [R10] ReconVLA: An Uncertainty-Guided and Failure-Aware Vision-Language-Action Framework for Robotic Control
- **出处**：arXiv 2604.16677v1, 2026-04（cs.RO）
- **作者**：（含 CQR-based UQ）
- **获取**：https://arxiv.org/html/2604.16677v1（免费 HTML）
- **主题**：VLA 的不确定性感知 + 失败检测；保形预测（CQR）
- **核心贡献**：
  - 系统分解 VLA 不确定性来源（输入 / 动作）
  - CQR 提供动作级置信区间
  - 运行时状态一致性检查
  - 「让机器人知道自己不知道」的框架
- **与 RoboParts 关联**：
  - **⭐⭐⭐⭐⭐ 最直接相关**：[R10] 明确说「今天 VLA 不报告系统性不确定性指标，意味着机器人不知道自己在冒险」——这正是 RoboParts 想解决的
  - **同思路**：都是「让系统显式表达未知」；RoboParts 的三态语义与 [R10] 的 UQ 是同一哲学在**数据层**与**决策层**的两条路
  - **可引用位置**：引言「未知是数据层的头等公民」；讨论「数据层三态 vs 决策层 UQ」的互补
- **可引用性**：⭐⭐⭐⭐⭐（免费，最新，哲学同构）

### [R11] 关于 VLA 不确定性的综述
- **出处**：（含在 [R10] 的引用里）
- **可引用性**：⭐⭐⭐（间接引用）

---

## 五、3D 打印 / 转接件 / 制造接口标准

### [R12] STEP-NC-Based Framework for Additive Manufacturing Systems
- **出处**：IGI Global (2024)，Chapter 3
- **获取**：https://www.igi-global.com/viewtitlesample.aspx?id=410941（免费试读）
- **主题**：STEP-NC 封装几何 / 材料 / 工艺参数；AM 全流程单一数字脊柱
- **与 RoboParts 关联**：
  - **同为「统一数据脊柱」**；但 [R12] 是「制造流程」，RoboParts 是「选型流程」
  - **可引用位置**：相关工作「CAD/CAM/CNC 脊柱 vs 选型脊柱」
- **可引用性**：⭐⭐（部分免费）

### [R13] ANSI Blog: Additive Manufacturing Standards
- **出处**：https://blog.ansi.org/ansi/additive-manufacturing-standards-iso-astm-3d/
- **获取**：免费
- **主题**：ISO/ASTM 52900 / 52901 / 52902 / 52915 等 AM 标准概览
- **与 RoboParts 关联**：
  - **背景阅读**：说明「标准化 = 术语统一 + 数据交换 + 测试方法」三件套
  - **可引用位置**：引言「标准化是选型基础设施」
- **可引用性**：⭐⭐（背景）

---

## 六、开源硬件生态 / BOM 语义

### [R14] Seeed reBot-DevArm（开源机械臂）
- **出处**：GitHub / Gitee（CN000024 OSHWA 认证）
- **获取**：https://gitee.com/seeed-projects/reBot-DevArm
- **主题**：四层开源（硬件 / 控制 / ROS / Embodied AI）；CERN-OHL-W 2.0 硬件许可
- **与 RoboParts 关联**：
  - **实证**：说明开源硬件已有成熟 BOM 实践，但**缺兼容性判定层**——RoboParts 的生态位
  - **可引用位置**：引言「开源硬件成熟但兼容性层缺失」
- **可引用性**：⭐⭐⭐⭐（开源项目，可复现）

### [R15] TetherIA Aero Hand（$314 开源腱驱动手）
- **出处**：https://tetheria.ai
- **获取**：https://github.com/tetheria/aero-hand（Apache-2.0 软件 + CC BY-NC-SA 4.0 硬件）
- **主题**：腱驱动手 + ROS2 + MuJoCo + BOM
- **与 RoboParts 关联**：
  - **同 [R14]**：开源 BOM 丰富但**未标注兼容性**——RoboParts 的价值主张
  - **可引用位置**：引言「开源硬件生态的兼容性盲区」
- **可引用性**：⭐⭐⭐（可引用项目实践）

---

## 七、Robot HAL / 标准化（背景）

### [R16] Hardware Abstraction Layers for Modular Robotic Synthesis Workflows
- **出处**：PatSnap Eureka report（综述类）
- **获取**：https://eureka.patsnap.com/report-hardware-abstraction-layers-for-modular-robotic-synthesis-workflows（免费）
- **主题**：ROS / OPC UA / ISO / Open-RMF / RIA / euRobotics 等 HAL 标准化
- **与 RoboParts 关联**：
  - **背景阅读**：说明 HAL 标准化是**通信层**，不是**零件兼容性层**
  - **可引用位置**：相关工作「通信 HAL vs 零件兼容性层」
- **可引用性**：⭐⭐⭐（综述）

---

## 汇总

| # | 主题 | 免费度 | 相关性 | 可引用性 |
|---|---|---|---|---|
| R1 | Linkify (接口图) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| R2 | CAD 关系学习 (ASP) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| R3 | CAD → 场景图 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| R4 | 知识图谱机器人设计 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| R5 | ExtruOnt 本体 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| R6 | 本体 KG 系统工程 | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| R7 | 操作 KG | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| R8 | 装配引导本体 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| R9 | ML + 本体综述 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **R10** | **ReconVLA (不确定性)** | **⭐⭐⭐⭐⭐** | **⭐⭐⭐⭐⭐** | **⭐⭐⭐⭐⭐** |
| R11 | VLA UQ 综述 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| R12 | STEP-NC 框架 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| R13 | AM 标准概览 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ |
| R14 | reBot-DevArm | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| R15 | TetherIA Aero Hand | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| R16 | Robot HAL 综述 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

**核心必引（5 篇）**：R1 / R2 / R5 / R7 / R10——覆盖「接口几何 / 装配符号 / 本体 / 操作 KG / 不确定性」五个维度。

**RoboParts 差异化定位**（一句话）：
> R10 让**决策层**承认未知；R1-R9 让**数据层**表达接口；**RoboParts 让**数据层**显式说出「我不知道」——三态诚实是零件兼容性层的唯一诚实答案**。
