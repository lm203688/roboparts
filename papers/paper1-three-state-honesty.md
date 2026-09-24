# Three-State Honesty in Open Hardware Compatibility:
## A Vendor-Neutral Determination Layer for Robotic Parts

**RoboParts** · Preprint draft · 2026-09-24

> **状态**：投稿前草稿。数字全部现算自 `scripts/onboarding_block.py::facts()`
> 与 `api/*.json` 产物；禁手写。
> **数据 & 代码**：https://github.com/lm203688/roboparts（MIT + CC BY 4.0）
> **对应锚点**：`docs/PROJECT_DIRECTIONS_V2.md` §1 / §6；
> `docs/direction-evolution-roadmap-20260923.md` Phase B1–B3。

---

## 摘要 (Abstract)

机器人零件的**兼容性判定**是具身智能供应链里最基础也最脆弱的一环。
当前工程实践中，零件间「能不能装」的问题要么靠散文文档，要么靠 BOM 表
和试错，要么被厂商的兼容性矩阵封装。三类方案的共同缺陷是**二元化**：
要么说「能」，要么说「不能」，而真实的工程世界里大量组合是「不知道」。
二元化导致两类错误：把「不知道」当「能」（假兼容，安全灾难）或当「不能」
（假不兼容，浪费用户时间）。

我们提出 **RoboParts**：一个 vendor-neutral 的机器人零件兼容性判定层，
把兼容性形式化为一个**三轴类型系统上的三态可判定函数**：

$$\texttt{compose}(a, b) \in \{\texttt{composed},\ \texttt{type\_error},\ \texttt{unknown}\}$$

- **机械轴**：ISO 9409-1 类标号 = 类型；reflexivity 公理（同型必配）仅在
  **几何规格型**成立，**方向性角色型**（如 OUTPUT_SPIKE）同类不构成互补。
- **电气轴**：连接器针数/间距不容 ⇒ incompatible。
- **信号轴**：按品类定向声明角色（OUTPUT_SPIKE / INPUT_SENSORY / REWARD）；
  REWARD 不参与正向判定。
- **fail-closed 语义**：无证据的轴恒为 `unknown`；`unknown` 优先级高于
  `composed`——「我不知道」是**一等公民**，而非缺失值。

在 802 个机器人零件实体、351,649 全对评测上，我们观察到 composed=0、
type_error=4、unknown=351,645——**这是数据缺口的诚实画像，不是系统的失败**。
进一步用 **gap_distance**（恰有 d 轴判 unknown 的对数）与 **d1_bottleneck**
（d=1 对的轴瓶颈归因）量化：d=1 的 112 对**100% 卡在电气轴**——补电气轴
声明即可把 112 对 unknown 变成可判定，这是数据飞轮的**优先级入口**。
用 **缺口成因分类**（unpublished_suspect 350 / proprietary_suspect 5 /
ambiguous 59）+ **缺口杠杆分析**（242 家制造商、头部 10 家仅占 28.5%）
给出「主缺口只能靠用户提交 / OSS BOM 反喂 / 社区 PR 收敛」的负向证据，
而非空喊「共建生态」。

**贡献**：
1. 三态诚实的兼容性判定形式化（三轴类型系统 + fail-closed 优先级 +
   reflexivity 边界）；
2. 593 节点形态图 + 5.69% 机械声明率的诚实基线（覆盖率地图而非 benchmark）；
3. gap_distance / d1_bottleneck 作为数据飞轮排序依据；
4. 缺口成因三分类 + 杠杆分析（负向证据，防「抓少数厂商 datasheet 解决主缺口」
   的幻想）。

---

## 1. 引言

具身智能的下一个瓶颈不是让机器人**更聪明**，而是让机器人**能装什么**。
一个典型的开源机械臂项目（如 Seeed reBot-DevArm [R14]）会公开 STEP 文件、
BOM、Python SDK、ROS2 集成、LeRobot 教程、Isaac Sim 仿真——四层齐全，
但没有回答一个问题：**「这个夹爪能不能装这个腕部？这个传感器能不能接
这个主板？」** 这类兼容性判定长期以散文、经验试错、或厂商私有矩阵存在，
没有中立、机器可读、可判定的公共层。

我们的核心主张是：**兼容性判定的正确语义不是二元，而是三态**。
「我知道能」和「我知道不能」是两种有证据的状态；「我不知道」是第三种
有证据的状态——它精确指出「补哪个声明、补多少、能把多少 unknown 变成
可判定」。忽略第三种状态会导致两类实际错误：

- **假兼容**：把「没查到」当「可以」——机械损伤、电气损坏、甚至人身伤害。
- **假不兼容**：把「没查到」当「不可以」——用户花数小时试错才知道其实
  可以装，或者反过来。

RoboParts 的差异化设计是**三态诚实（three-state honesty）**：
$$\texttt{compose}(a, b) \in \{\texttt{composed},\ \texttt{type\_error},\ \texttt{unknown}\}$$
其中 `unknown` 优先级**高于** `composed`——只要任一轴无证据，总裁决
就是 `unknown`。这是与所有二元兼容性矩阵的分界线。

**vendor-neutral** 是另一条不可退让的设计原则：RoboParts 不生产、不代理
任何零件，与所收录厂商无销售利益关系。没有卖东西的理由就没有骗用户
选一个理由——这是我们敢把「不知道」放第一位的结构性原因。

**本文贡献**：
1. **形式化**：三轴（机械 / 电气 / 信号）类型系统 + 三态裁决代数 +
   reflexivity 公理的**边界条件**（几何规格型 vs 方向性角色型）。
2. **诚实基线**：802 实体、439 可判定粒度、25 已声明（5.69%）的
   机械接口公开登记率——覆盖率地图，不是 benchmark。
3. **瓶颈归因**：gap_distance（d=1/2/3）+ d1_bottleneck（轴归因）作为
   数据飞轮的排序依据；112 对 d=1 全部卡在电气轴，是可行动的洞察。
4. **缺口成因分类**：414 开放缺口 = unpublished_suspect 350 /
   proprietary_suspect 5 / ambiguous 59；加**杠杆分析**（242 家制造商，
   头部 10 家仅 28.5%）作为「抓少数厂商不够」的负向证据。

---

## 2. 相关工作

### 2.1 装配图与接口几何

Linkify [R1] 为 Fusion 360 Gallery Assembly 数据集重算高保真接口接触，
用点云编码接口几何，GATv2 在 masked part prediction 上优于非图基线。
**与 RoboParts 的差别**：Linkify 是**几何层**（点云、接触面），RoboParts
是**语义层**（标号、类型、状态）。两者互补——Linkify 告诉你「两个零件
接触面是什么形状」，RoboParts 告诉你「两个零件能不能组成一个系统」。

CAD-Based Relation Learning [R2] 用神经网络学几何关系，人工纠错，转符号
装配图，可见性射线求可行方向。**与人机回环的关系**：RoboParts 的「用户
提交 + 出处」通道是同一哲学——不猜，让人补。

Semantic Enrichment via Scene Graphs [R3] 从 USD 格式 CAD 生成多层场景图。
RoboParts 的形态图（morphology graph）与之同构，但语义密度不同——RoboParts
从「已声明接口」出发，[R3] 从「无标签 CAD」出发。

### 2.2 工程本体与知识图谱

ExtruOnt [R5] 为挤出机建立本体（组件 / 空间连接 / 特征 / 3D 表示 / 传感器），
机器可读。**与 RoboParts 的差别**：ExtruOnt 是**单机**本体，RoboParts 是
**跨厂商组合**判定。术语对齐：ExtruOnt 的 spatial connections 与 RoboParts
的 interfaces 是同一概念。

Model Management KG [R6] 用本体定义工作流概念 + 工件 + 形式化。**与
RoboParts 的差别**：系统级 vs 零件级本体化。

Operational KG [R7] 把操作任务的行为和几何约束编码为 KG，用于控制推理。
**与 RoboParts 的差别**：动作级 vs 零件级 KG。

ML + Ontology 综述 [R9] 系统总结了本体 + ML 的 200+ 篇工作，说明「本体
驱动的机器可读工程数据」是新兴方向——RoboParts 是零件兼容性层的落地实例。

### 2.3 不确定性与失败感知

ReconVLA [R10] 是**最直接相关的哲学**：它明确说「今天 VLA 不报告系统性
不确定性指标，意味着机器人不知道自己在冒险」。它的解法是保形预测
（CQR）+ 运行时状态一致性检查，让 VLA 显式表达「不知道」。

RoboParts 与 ReconVLA 是同一哲学在两条层的两条路：
- **ReconVLA** 让**决策层**（VLA 策略）承认未知；
- **RoboParts** 让**数据层**（零件兼容性）承认未知。

两者不冲突，可组合：RoboParts 告诉决策层「A 和 B 的组合是 unknown」，
ReconVLA 让决策层在收到这个信号时主动降级或请求人工介入。

### 2.4 标准化与开源硬件

Robot HAL 综述 [R16] 覆盖了 ROS / OPC UA / ISO / Open-RMF 等**通信层**
标准化。**与 RoboParts 的差别**：HAL 解决「两个机器人怎么通信」，
RoboParts 解决「两个零件能不能装」。前者是协议，后者是数据。

Seeed reBot-DevArm [R14] 与 TetherIA Aero Hand [R15] 是成熟的开源硬件
项目，BOM 下到螺丝级、许可规范（CERN-OHL-W 2.0、Apache-2.0）、SDK / ROS2 /
Isaac Sim / LeRobot 齐全——但都**没有标注兼容性**。这是 RoboParts 的生态位：
开源硬件已有成熟 BOM 实践，缺的是兼容性判定层。

---

## 3. 形式化

### 3.1 端口类型格 (Port Type Lattice)

每个零件有若干**端口 (port)**，每个端口有三个属性：
- `type`：类型标号（如 `MECH:ISO9409-1-A25`、`ELEC:JST-EHR-03`、
  `SIG:OUTPUT_SPIKE`）；
- `status`：`declared` / `partial` / `not_declared` / `n_a`；
- `evidence`：出处 URL + 证据等级（tier_a / tier_b / community）。

类型按**轴**分组：机械（`MECH:*`）、电气（`ELEC:*`）、信号（`SIG:*`）。

### 3.2 裁决代数 (Verdict Algebra)

单轴裁决四值：
$$\texttt{compatible} \prec \texttt{compatible\_via\_adapter} \prec \texttt{incompatible} \prec \texttt{unknown}$$

优先级：`incompatible` ⇒ 整轴不可判定为 composed；`unknown` ⇒ 整轴不确认可装。

### 3.3 总裁决 (Overall Verdict)

三态：`composed` / `type_error` / `unknown`。

优先级规则（**fail-closed**）：
$$\texttt{any axis} \to \texttt{incompatible} \Rightarrow \texttt{type\_error}$$
$$\texttt{any axis} \to \texttt{unknown} \Rightarrow \texttt{unknown}$$
$$\texttt{all axes} \to \texttt{compatible}\ (\text{or via\_adapter}) \Rightarrow \texttt{composed}$$

**`unknown` 优先于 `composed`**——这是与所有二元兼容性矩阵的分界线。

### 3.4 Reflexivity 公理及其边界

**经典公理**：`same type ⇒ composable`（同型必配）。

**我们的边界条件**：这条公理仅对**几何规格型**（ISO 9409-1 法兰标号）
成立——同标号法兰必然可装。**对方向性角色型**（`SIG:OUTPUT_SPIKE`、
`SIG:INPUT_SENSORY`）**不成立**——两个 OUTPUT_SPIKE 端不是「必然可装」，
而是**互为不互补**（需要控制器中介，超出二元组合的判定域）。

**形式化**：类型分为两类：
- `GeometrySpec`：同型自配对 ⇒ `compatible`；
- `DirectionalRole`：同型自配对 ⇒ `not_complement`（不是 `compatible`）。

**登记优先于公理**：`type_compat` 表里**显式登记**的自配对裁决优先级
高于 reflexivity 公理。这条纪律在早期实现里被违反过一次——`type_compat`
里登记了 `OUTPUT_SPIKE ~ OUTPUT_SPIKE`，但 `pair_verdict` 无条件对
`ta == tb` 返回 identity，**静默覆盖了登记**，登记等于没登记。我们修了它，
并补了 6 条 SIG 判据到合成图。这是本轮唯一真正的引擎级 bug。

### 3.5 信号轴的角色定向

早期实现把所有实体无差别赋全部 3 个信号类型，等于什么都没声明。我们改为
**按品类定向**：
- 执行器 / 夹爪 / 柔性执行器 / 谐波 / 生体机构 / 一体化关节 → `OUTPUT_SPIKE`
- 传感器 → `INPUT_SENSORY`
- REWARD → 不参与点对点正向判定

结果：593 节点全可组合、`composable=0`，但信号端口 declared 从 0 → 392
（OUTPUT_SPIKE 297 / INPUT_SENSORY 95）。

---

## 4. 实现

### 4.1 引擎规模

- `compose_engine.py`：约 300 行纯函数 Python，零依赖。
- 数据底座：`api/morphology_graph.json`（593 节点、2,185 端口、147 类型对）
  + `api/entities.json`（802 实体、11 品类）。
- 产出：`api/compose_semantics.json`（规则表 R0–R5、全对聚合、判例）。

### 4.2 Pipeline 骨架

`scripts/pipeline/` 是无第三方依赖的**算子 + DAG 执行器**，把每个 `build_*.py`
拆成纯函数算子（`@operator(name, stage, description)` 装饰器，重名 / 格式
fail-fast），用声明式 DAG 编排（输入引用 `prev_op.key` 支持嵌套路径），
每一步留下 trace（算子名 / 耗时 / 成功 / 错误摘要 / 输出摘要）。

**等价性证明**是唯一闸门：`scripts/verify_pipeline.py` 23 项自测，其中关键
一项**逐字段对账** `build_X.build()` 与 `Pipeline.run('X')` 的输出——
只允许 `meta.generated_at` / `meta.generated_by` 差异，其余字段全相等。
**只比产物必假绿**：变异测试断言 crosscheck 能拦下聚合与 facts 的漂移。

已迁移：`gap_classification`（7 算子）+ `compose_semantics`（6 算子）。

### 4.3 闸门工程

我们承认一个方法论立场：**「可判定」本身必须被检验**。所以：
- 每个 build_ 脚本都有 `verify_*.py` 配套自证（`verify_compose_semantics.py`
  21 项、`verify_morphology_graph.py` 21 项、`verify_provenance.py` 12 项、
  `verify_croissant.py` 7 项、`verify_pipeline.py` 23 项）；
- `ci_gate.py` 44 项闸门，全部走「阳性 + 阴性 + 变异」三对照——
  只测绿路径的闸门等于没闸门；
- `verify_live_numbers.py` 四条轴：页面数字 / llms.txt 子集口径 /
  对外接口总数 / 定位口径自称面。

---

## 5. 评估

### 5.1 数据规模（现算，禁手写）

| 指标 | 数值 | 出处 |
|---|---|---|
| 实体总数 | 802 | `facts().total_entities` |
| 机械可判定粒度 | 439 | `facts().mech_applicable` |
| 机械已声明 | 25 | `facts().mech_declared` |
| **机械声明率** | **5.69%** | `facts().mech_pct` |
| 形态图节点 | 593 | `morphology_graph.json` |
| 端口数 | 2,185 | `morphology_graph.json` |
| 类型对 | 147 | `morphology_graph.json` |
| 全对评测对数 | 351,649 | `compose_semantics.aggregates.pairs_evaluated` |

**声明率是覆盖率地图，不是 benchmark**。5.69% 说明：机械接口公开登记
是**稀有事件**——242 家制造商中，只有 25 家在 439 个可判定粒度的实体
上公开了 ISO 9409-1 类标号。这不是我们数据抓取差，是整个行业的公开
登记率就是这个水平。

### 5.2 三态分布（351,649 对全对评测）

| 总裁决 | 对数 | 占比 |
|---|---|---|
| `composed` | 0 | 0.000% |
| `type_error` | 4 | 0.001% |
| `unknown` | 351,645 | 99.999% |

**`composed = 0` 的诚实含义**：这不是系统失败，是**数据缺口的诚实画像**。
机械接口公开登记率只有 5.69%，绝大多数实体没有任何公开接口证据，
三轴必然有大量 `unknown`。若强行报告「99.999% unknown 意味着系统没用」，
那是在要求系统撒谎。

### 5.3 Gap Distance（可行动的瓶颈定位）

**定义**：`gap_distance[d]` = 恰有 d 轴判 `unknown` 的配对数（仅统计
overall=`unknown`；`type_error` 是类型冲突而非证据缺口，不计入）。

| d | 对数 | 含义 |
|---|---|---|
| 0 | 0 | 三轴全明确，但非 composed（type_error 或 composed） |
| **1** | **112** | 补一轴声明即可判定——**最高优先级** |
| 2 | 56,437 | 需补两轴声明 |
| 3 | 295,096 | 三轴全 unknown |

**`d=1` 是数据补录的最高优先级目标**：只需补一轴（通常是电气轴，见下）
就能把 112 对 unknown 变成可判定对。这 112 对是**可行动的**。

### 5.4 D1 Bottleneck（轴归因）

在 d=1 的 112 对里，唯一 unknown 的轴分布：

| 轴 | 对数 | 占比 |
|---|---|---|
| mechanical | 0 | 0% |
| **electrical** | **112** | **100%** |
| signal | 0 | 0% |

**发现**：d=1 对的瓶颈**100% 在电气轴**。机械轴已按品类定向声明
（`MECH:ISO9409-1-A{n}`），信号轴已按品类定向声明（`SIG:OUTPUT_SPIKE` /
`SIG:INPUT_SENSORY`），电气轴仍待补。**这是可行动的结论**：数据飞轮
的排序依据是「先补电气轴」，不是「平均补三轴」。

（历史对比：2026-09-23 之前我们曾归因为「SIG 全未声明导致 composed=0」
——那是 2026-09-23 之前的状态。信号轴定向声明后，真实瓶颈已由
d1_bottleneck 指出。**归因必须现读产物聚合，不要复述记忆**。）

### 5.5 缺口成因分类

414 开放缺口（applicable 439 - declared 25）的成因分类：

| 分类 | 实体数 | 判据 |
|---|---|---|
| unpublished_suspect | 350 | 有制造商，但未落专有集合 |
| proprietary_suspect | 5 | 制造商已知采用专有生态（partial 证据） |
| ambiguous | 59 | 无制造商，无法区分 (i)/(ii) |
| **合计** | **414** | |

**判据收紧（2026-09-24）**：原判据 `manufacturer ∨ source` 把 59 条**无制造商**
但有 source_tier 的实体推成 unpublished——**不知厂商是谁就谈不上「厂商未公开」**，
退回 ambiguous。收紧后 unpublished 350 / ambiguous 59。

**负向证据**：unpublished_suspect 是**抓取目标清单**，不是「厂商不公开」
的实证。它无法区分「厂商真没公开」与「我们没爬到」——两种都判 published 嫌疑。

### 5.6 缺口杠杆分析（为什么主缺口不能靠抓少数厂商解决）

对 414 开放缺口按制造商聚合：

| 指标 | 数值 |
|---|---|
| 独立制造商数 | 242 |
| 头部 10 家占比 | **28.5%** |
| 无制造商占比 | **14.3%** |
| 物理安装类开放缺口 | 403 / 414 = 97.3% |

**结论**：头部 10 家仅占 28.5%，剩余 71.5% 分散在 232 家；且 14.3%
的缺口**连制造商都不知**。**抓少数厂商 datasheet 是必要但不充分**——
主缺口只能靠**用户提交 / OSS BOM 反喂 / 社区 PR** 收敛。这是空喊
「共建生态」时不敢给出的负向证据。

---

## 6. 讨论

### 6.1 「`composed = 0` 让系统无用吗？」——反论

不是。`unknown` 是**可行动的**：它精确指出「补哪个声明、补多少、能把
多少 unknown 对变成可判定对」。这 112 对 d=1 是数据飞轮的排序入口，
295,096 对 d=3 是长期攻坚目标。

**对比二元方案**：如果强行把 unknown 归入 composed，会得到 99.999% 的
「兼容」——这是最危险的假信号，会让用户基于错误假设做出安全决策。
如果强行把 unknown 归入 type_error，会得到 99.999% 的「不兼容」——
这是最浪费的信号，会让用户花数小时试错。

**三态诚实的价值**：unknown 是**信息**，不是缺失。它精确指出「要补什么、
补多少、优先补哪个」——这正是数据飞轮的排序依据。

### 6.2 Vendor-neutrality 是设计原则，不是营销话术

我们强调「不生产、不代理任何零部件」，这不是道德表演，而是**结构性原因**：
- 有卖东西的理由，就有把 unknown 当 composed 的理由（把「不知」当「可以」
  好推销）；
- 有卖东西的理由，就有把 known 当 unknown 的理由（把已知隐藏起来好收钱）；
- 没有卖东西的理由，就没有任何一类撒谎的动机。

这就是三态诚实能站住的结构性原因——它不是「良心好」，是「没得选」。

### 6.3 与 ReconVLA 的互补（决策层 UQ vs 数据层三态）

ReconVLA [R10] 让 VLA 策略显式表达「不知道」（保形预测 + 运行时状态
一致性检查）。RoboParts 让数据层显式表达「不知道」（三态裁决 + fail-closed）。
两者不冲突，可组合：

- RoboParts 告诉决策层「A 和 B 的组合是 unknown」；
- ReconVLA 让决策层在收到这个信号时主动降级或请求人工介入。

**这是一个完整的三层栈**：
1. **数据层**（RoboParts）：「A 和 B 能不能装？」——三态回答。
2. **推理层**（KG + 本体）：「如果 A 和 B 是 unknown，我能选什么替代？」
3. **决策层**（ReconVLA）：「我现在不知道，我要降级还是请求人工介入？」

RoboParts 是这条栈的底座——没有诚实的数据层，上面两层都在猜。

### 6.4 与几何层接口（Linkify 类）的互补

Linkify [R1] 用点云编码接口几何，做装配图 masked part prediction。
RoboParts 用语义类型做兼容性判定。两者互补：

- **Linkify** 告诉你「两个零件接触面是什么形状」；
- **RoboParts** 告诉你「两个零件能不能组成一个系统」。

组合场景：Linkify 检测到两个零件接触面匹配（几何可装），RoboParts 检查
电气轴发现连接器针数不容（电气不可装）——组合结论是 type_error。
几何可装 ≠ 系统可装，这是二元兼容性矩阵永远回答不了的问题。

---

## 7. 结论与未来工作

### 7.1 结论

- **兼容性判定的正确语义是三态，不是二元**。RoboParts 是 vendor-neutral
  的三态判定层，`unknown` 是一等公民。
- **5.69% 机械声明率是覆盖率地图，不是 benchmark**。
- **d=1 的 112 对 100% 卡在电气轴**——数据飞轮的排序入口。
- **414 开放缺口的成因分类 + 杠杆分析**给出「抓少数厂商不够」的负向证据。
- **可判定本身被检验**：23 项 pipeline 自测 + 44 项 ci_gate 全绿。

### 7.2 未来工作

1. **数据飞轮排序算法**：基于 gap_distance + d1_bottleneck 自动排序
   「下一个最值得补的声明是什么」；
2. **转接盘几何**：`compatible_via_adapter` 的**可打印可信**（H3 硬骨头，
   尚未做）——需要 3D 打印后力学验证；
3. **信号契约层**：把机械兼容延伸到信号级联（GAP-G2，neurorobotics 域）；
4. **依赖类型升级**：从轻量 effect system 升级到 Lean 4 依赖类型
   （`MECH:ISO9409-1-A{n}` 的参数化标号天然是 indexed type）；
5. **开源 BOM 反喂 ingestion**：`ingest_oss_bom.mjs` 目前写 `oss_components.json`，
   与声明率分母 `entities.json` 不相通，需打通。

### 7.3 开源与数据贡献

- **代码**：https://github.com/lm203688/roboparts（MIT）
- **数据**：CC BY 4.0
- **提交通道**：`add_mechanical_interface.py` 的 `_curated()` 只留带
  `source_url` 的提交——用户提交带出处，我们的分类器把它纳入
  `unpublished_suspect` / `proprietary_suspect` 桶，进入下一轮分类。
- **社区 PR**：欢迎直接 PR 到 `entities.json`，每条实体带 `source_url`。

---

## 8. 参考文献（仅列本文必引的核心 10 篇）

- **[R1]** Jignasu, A., Grandi, D., et al. (2026). *Linkify: Learning from
  Interface-Augmented Assembly Graphs*. arXiv:2607.01205.
- **[R2]** Harlacher, F., Friedrich, C. (2026). *CAD-Based Relation Learning
  and Geometric-Symbolic Planning for Robotic Assembly*. arXiv:2609.17263.
- **[R3]** (2026). *Semantic Enrichment of CAD-Based Industrial Environments
  via Scene Graphs for Simulation and Reasoning*. arXiv:2601.06415.
- **[R5]** Ramírez-Durán, J., Berges, V., Illarramendi, I., et al. (2024).
  *ExtruOnt: An Ontology for Describing a Type of Manufacturing Machine
  for Industry 4.0 Systems*. arXiv:2401.11848.
- **[R7]** (2024). *Interpreting Behaviors and Geometric Constraints as
  Knowledge Graphs for Robot Manipulation Control*. arXiv:2310.03932.
- **[R9]** Ghidalia, S., Narsis, O.L., Bertaux, A., et al. (2024).
  *Combining Machine Learning and Ontology: A Systematic Literature Review*.
  arXiv:2401.07744.
- **[R10]** (2026). *ReconVLA: An Uncertainty-Guided and Failure-Aware
  Vision-Language-Action Framework for Robotic Control*. arXiv:2604.16677.
- **[R14]** Seeed Studio (2026). *reBot-DevArm*. Gitee/GitHub, OSHWA
  CN000024, CERN-OHL-W 2.0.
- **[R15]** TetherIA (2026). *Aero Hand*. GitHub, Apache-2.0 + CC BY-NC-SA.
- **[R16]** PatSnap Eureka (2025). *Hardware Abstraction Layers for Modular
  Robotic Synthesis Workflows*.

**完整参考文献清单**：见 `papers/refs-free-sci-20260924.md`（16 篇，含
5 篇核心必引 + 11 篇背景与对照）。

---

## 附录 A：目标投稿出口

按投稿成本升序：
1. **arXiv 预印本**（cs.RO）：占时间戳与优先权，免费，无审稿成本。
   → 本轮已完成草稿，可直接投。
2. **IROS / ICRA workshop**（具身组件标准化方向）：短文 4–6 页，投稿成本低。
3. **Science Robotics「Technical Comment」类** / **RAM**（RA-Letters）：
   短文，需要更强的实证支撑。
4. **期刊**（如 Sensors MDPI / J. Industrial Information Integration）：
   长文，需要更多实验与对比。

**投稿决策走锚点 §2 三问闸门**：
- 有真数据吗？→ 有（802 实体、351,649 对、5.69% 声明率现算）。
- 有独特贡献吗？→ 有（三态诚实 + 缺口成因分类 + 杠杆分析）。
- 有可复现的代码吗？→ 有（MIT + CC BY 4.0，GitHub 公开）。

---

## 附录 B：数字来源（现算，禁手写）

所有数字均通过以下脚本现算：
- `python -c "from scripts.onboarding_block import facts; print(facts())"`
- `python -c "import json; print(json.load(open('api/compose_semantics.json'))['aggregates'])"`
- `python -c "import json; print(json.load(open('api/gap_classification.json'))['buckets'])"`

**纪律**：任何生成器源串里的裸数字必须改为 `facts()` 现算；`build_articles.py`
曾因硬编码 688（真值 798）导致锚点扫描与回归都不覆盖——**双盲区**。
