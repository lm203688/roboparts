# RoboParts 科学性与 SCI 达标评估

> 日期：2026-10-18
> 评估对象：项目整体科学性 + `papers/arxiv_submission`（1086 行）+ `papers/mechatronics_submission`
> 评估视角：**SCI 期刊审稿人**（按 Nature/Science Robotics、IEEE RA-L、Mechatronics、RAS 的通用审稿尺）
> 取证方式：论文正文逐节读 + 仓库产物现算比对 + 源码级形式化审查（不手工改任何数据）

---

## 0. 核心判断

> **当前水平：arXiv preprint / JOSS 级（优秀的软件与数据论文）。**
> **尚未达到 SCI 正刊水平**，主要差距不在"工作量"，而在**三类可验证性缺失**：
> ① 没有数学证明（却声称 formalise）；② 没有外部效度（ground truth）；③ 论文核心数字与结论已被仓库新数据推翻。

**一句话**：这台机器的**工程严谨度已经超过很多被接收的论文**，但它的**科学叙事还停留在"我们做了个系统"**，而不是"我们证明了什么"。

三个最刺眼的事实：

| # | 事实 | 性质 |
|---|---|---|
| 1 | 摘要写「all **112** pairs at d=1 are bottlenecked on the **electrical axis alone**」，实际是 **61 对：electrical 32 + signal 29** | **核心结论已被自己的新数据推翻** |
| 2 | 全文 `theorem/lemma/proof` 环境数量 = **0**，但摘要第一句就说 "**formalises** compatibility as a three-valued function" | 声称形式化但无形式化 |
| 3 | 摘要数字 `802 entities / 351,649 pairs / type_error=4`，实际 `868 / 430,336 / **262**` | **type_error 差 65 倍** |

---

## 1. 评估方法：七把审稿尺

按 SCI 通用审稿标准，分解为七个可打分的维度。每把尺子给 **A（达标）/ B（接近）/ C（明显不足）/ D（致命）**。

| 尺 | 维度 | 评分 | 一句话理由 |
|---|---|---|---|
| R1 | 研究问题与动机 | **A** | 三值 vs 二值的"假绿/假红"动机清晰，且是真实工程痛点 |
| R2 | 形式化与理论保证 | **D** | 无 theorem/lemma/proof；唯一的 "Soundness" 有重言式风险 |
| R3 | 实验设计 | **C** | 有 ablation/sensitivity/robustness，但**对比是思想实验，非实跑 baseline** |
| R4 | 外部效度（ground truth） | **D** | Golden 集是 `freeze_anchor`（冻结自身输出），防回归不证正确 |
| R5 | 相关工作与引用 | **C** | 仅 20 条文献，**12 条 @misc**，机器人顶会/顶刊 **0 篇** |
| R6 | 可复现性 | **B** | 82 个产物全部脚本现算、有 CI、有 commit hash；**但无 DOI/Zenodo** |
| R7 | 诚实性与局限讨论 | **A** | Limitations 主动承认无 ground truth、需 inter-annotator 研究——**这是全篇最强项** |

**综合：R1/R7 优秀，R2/R4 致命，R3/R5 明显不足。**

---

## 2. 逐项详评

### R1 · 研究问题与动机 —— A（这是全篇最扎实的部分）

摘要的动机论证是完整且有说服力的：

> 现有三条路径（自由文档 / BOM 试错 / 厂商私有矩阵）都是**二值**的，但真实工程充满必须标 `unknown` 的组合。强制二值导致两个对称错误：**假阳性**（机械损坏、人身伤害）与**假阴性**（浪费集成时间）。

这个动机满足 SCI 的三要素：**真实问题 + 明确缺陷 + 可验证的主张**。

`unknown` 优先于 `composed` 的设计选择（"ignorance is a first-class citizen, not a null value"）是一个**清晰、可争辩、可证伪**的立场——这正是好论文需要的。

---

### R2 · 形式化与理论保证 —— D（致命）

**现象**：对 `main.tex` 全文 grep：

```
theorem / lemma / proposition / definition / proof / corollary 环境数量 = 0
```

摘要却写着：

> "We present RoboParts, a vendor-neutral determination layer that **formalises** compatibility as a three-valued function..."

**审稿人会怎么写**：*"The paper claims to formalise X, but contains no definitions, theorems, or proofs. At most it presents an implementation. This is an engineering report, not a research contribution."*

**更深一层的问题：唯一的 "Soundness" 是重言式**

`scripts/compose_core.py` 里定义了三条代数律，第一条是：

```python
{
    "name": "Soundness（可靠性）",
    "statement": "compose(a,b) = composed ⇒ 每一轴都至少存在一个 pair verdict = identity。",
    ...
}
```

**问题**：`composed` 的**定义**就是"每轴都有 identity"。所以"composed ⇒ 每轴有 identity"是一个**重言式（tautology）**，它的逆否命题同样平凡成立。用性质测试去"验证"它，验证的是实现有没有写错，**不是理论保证**。

真正的 Soundness 应该是：**「compose 说能装 ⇒ 物理上真的能装」**——这需要 ground truth，不是测试能给的。

**学术诚信点**：把内部一致性命名为 "Soundness" 是**术语误用**。它应该叫 **Internal Consistency（内部一致性）**。审稿人抓到这一点会很不利。

**可救之处**：另两条律是有实质内容的——

- **Monotonicity under evidence（证据单调性）**：禁止 `compatible → incompatible/unknown` 的翻转。这**可以真正证明**（依赖聚合函数"取最差轴"的单调性），不只是测试。
- **Undecidability boundary（不可判定边界）**：专有接口无论加多少条目恒为 unknown。这也**可以证明**。

---

### R3 · 实验设计 —— C

**做得好的部分**（真实存在，不是虚的）：

| 实验 | 位置 |
|---|---|
| d1-bottleneck 分析 | §5.2 |
| Reflexivity boundary 案例研究 | §5.3 |
| Robustness：4 条 arithmetic crosscheck invariants 作为 CI 闸门 | §5.4 |
| Ablation：关掉 reflexivity boundary 会怎样 | §5.7 |
| Sensitivity：语料增长的敏感性 | §5.8 |
| Reproducibility：commit hash + 确定性 | §5.9 |

这六项是**完整的实验组合**，很多被接收的论文都没有这么全。ablation 和 sensitivity 尤其到位。

**致命短板：§5.6 "Comparison to alternatives" 是思想实验**

```
\item \textbf{Binary-only matrix} (typical vendor practice):
would report composed = 0 and type_error = 351,649 ...
```

论文自己交代了原因：*"Because no prior work publishes a vendor-neutral compatibility corpus of comparable size, we do not benchmark against prior systems."*

这个理由**合理但不充分**。审稿人会要求：

> 不需要跟别人比，但至少要**自己实现一个 baseline 并真的跑一遍**。
> "binary-only" 和 "optimistic-default" 都只是把聚合函数改一行的事——**跑出来，列成表**。

**从"分析性对比"升级到"实验性对比"，成本极低（改一个 flag + 重跑），收益极大。**

---

### R4 · 外部效度 —— D（致命，且论文已自认）

**Golden 评估集的真相**：

`api/eval/compatibility-golden.json`，28 条，每条带 `"type": "freeze_anchor"`。

```json
{
 "id": "GOLD-01",
 "type": "freeze_anchor",     ← 冻结锚点
 ...
 "expect": { "overall_in": ["compatible", "needs_review"], ... }
}
```

**`freeze_anchor` 意味着：这 28 条是"引擎曾经的输出被冻结下来"。**
它能防**回归**（引擎漂移了会报警），但**不能证明正确性**（如果引擎一开始就错了，它会一直错下去，且一直绿）。

这是与 R2 的 Soundness 问题**同源**的：整个验证体系是**自证的（self-certifying）**，缺少独立于系统的参照。

**论文在 §8.3 已经诚实承认**：

> "Our taxonomy explicitly does not attempt to distinguish these, because it cannot without external ground truth."

诚实承认是**加分项**，但**不解决问题**。SCI 期刊会要求补上。

---

### R5 · 相关工作与引用 —— C

```
参考文献总数：20
  @article   : 4
  @misc      : 12        ← arXiv / 网页 / 博客
  @standard  : 3
  @techreport: 1

顶会/顶刊命中：ICRA 0 · IROS 0 · CoRL 0 · RSS 0 · NeurIPS 0 · RA-L 0 · Science Robotics 0
```

**这是审稿人 30 秒内就能看到并写进意见的硬伤。**

一篇投 SCI 期刊的机器人论文，相关工作里**一篇机器人顶会都没有**，会被判定为"作者不熟悉领域"或"刻意回避相近工作"。

Related Work 的**结构其实不错**（5 个子节：standards / assembly graphs / uncertainty-aware robot learning / open-source hardware / hardware abstraction layers）——骨架对了，**血肉不够**。

---

### R6 · 可复现性 —— B（强，但差最后一公里）

**已有的（很扎实）**：

- 82 个 `api/*.json` 全部由脚本现算，README 明确"禁止手改"
- 64 道 CI 闸门，`npm run ci` 可跑
- 论文 §5.9 给出 commit hash（`50a2e012`）与确定性声明
- 三条代数律有 417 行性质测试 `tests/property/test_compose_lattice.py` + 变异测试 `test_mutation_kills_soundness`
- 变异评分 6/6 = 1.00

**这一项放在很多实验室里都算优秀。**

**差的最后一公里**：

- **无 DOI / Zenodo**——`CITATION.cff` 写了版本号 `2026.09`，但没有归档快照。论文引用的数据集三年后可能打不开。
- 数据集未冻结快照：论文数字随仓库漂移（这正是 §2 数字过期的原因）

---

### R7 · 诚实性 —— A（最强项，且是差异化的）

论文 §8.3 Threats to validity 主动列出：

- Corpus size 802 小，不声称泛化
- Vendor representation 有系统偏差
- **Manual classification 需要 inter-annotator agreement 研究**（主动指出自己的方法论缺陷）
- Time-sensitivity：5.69% 是快照

加上项目层面的资产：

- `docs/negative-results.md`：NR-01~NR-10，**NR-001 明确记录"T2 定理被证伪"**
- `docs/verification-antipatterns-2026.md`：AP-01~AP-12，从 170+ 次运行提炼

**"发表负结果 + 承认自己的定理被证伪"——这在学术界是稀缺品质，也是本项目最独特的科学资产。**

> 建议：把这一点**升级为论文的一个显式贡献**（见 §4 方案 C4），而不是只在 limitations 里提一句。

---

## 3. 贡献度评估

### 3.1 真实贡献清单（按强度排序）

| # | 贡献 | 类型 | 新颖性 | 可证性 |
|---|---|---|---|---|
| C1 | **三值兼容性函数 + unknown 优先** | 概念/框架 | 中 | 中（设计选择，非定理） |
| C2 | **Reflexivity boundary**（自反性只对 geometric-spec 成立，对 directional-role 撤回） | 设计洞察 | **高**（小但真新颖） | 高（有 ablation） |
| C3 | **gap-distance / d1-bottleneck 度量** | 度量方法 | 中高 | 高（可复算） |
| C4 | **工程可信信号体系**：变异评分 + 负结果档案 + 反模式档案 | 方法论 | **很高（罕见）** | 高（自动化） |
| C5 | **gap causation taxonomy**（三类归因） | 分类学 | 中 | 中（需 inter-annotator） |
| C6 | 868 实体开源数据集 + 82 个现算产物 | 数据/资源 | 中 | — |

### 3.2 最独特的贡献是什么

不是 C1（三值逻辑在别的领域早有），而是 **C2 + C4 的组合**：

> **C2**：发现"自反性"这个看似天然的公理，在 `OUTPUT_SPIKE` 这类**方向性角色**类型上不成立——两个同型号的公头插不到一起。这是一个**具体、反直觉、可验证**的发现，且论文为它做了 ablation。
>
> **C4**：把"如何证明一个判定系统可信"本身做成工程产物——变异测试杀死率 1.00、10 条负结果、12 条反模式。**机器人领域几乎没有项目这么做。**

**建议：把论文的重心从 C1（三值框架）移到 C2+C4（可信性工程）**。前者是"我们做了个系统"，后者是"我们解决了领域里一个没人解决的问题"。

### 3.3 一个必须修的对外口径冲突

README 写：

> "真正不可复制的是判定引擎（三态 fail-closed compose）+ **三条定理（T1/T2/T3）** + 49 项 CI 闸门"

但内部文档说：

- `docs/HEALTHCHECK_20261004.md:153`：**"T3 目前是强假说而非定理"（样本 13 对）**
- `docs/negative-results.md:14`：**"NR-001: T2 定理证伪「单条声明有边际收益」"**

**即：T2 已被证伪、T3 只是假说，但 README 对外宣称"三条定理"。**

审稿人或合作者交叉验证时会立刻发现这个冲突。必须先自洽（见方案 P0-3）。

---

## 4. 致命缺陷清单（按"会被拒稿"的可能性排序）

| 优先级 | 缺陷 | 审稿人原话（模拟） |
|---|---|---|
| **P0-1** | 摘要核心结论被自己数据推翻（d1: 112×100%electrical → 61×(32 elec + 29 sig)） | *"The abstract's main empirical claim contradicts the authors' own released artifact."* |
| **P0-2** | 数字全面过期（802/351,649/type_error=4/5.69%/242/28.5%） | *"Numbers do not match the released dataset."* |
| **P0-3** | 声称 formalise 但无 theorem/proof；Soundness 是重言式 | *"No formal contribution; at best an implementation."* |
| **P0-4** | 无外部 ground truth（Golden 是 freeze_anchor） | *"No external validation; results are self-certifying."* |
| **P1-1** | 参考文献 20 条、12 条 misc、顶会 0 | *"Related work is insufficient."* |
| **P1-2** | 对比实验是思想实验 | *"No baseline is actually run."* |
| **P1-3** | 对外宣称"三条定理"但 T2 证伪、T3 假说 | *"Claims are not consistent with the artifacts."* |
| **P2-1** | 无 DOI/Zenodo，数据集快照未冻结 | *"Artifacts may not be available in the future."* |

---

## 5. 提升方案：从 preprint 到 SCI

### 阶段 P0 · 止血（1–2 周，必须做）

**目标**：让论文与仓库自洽，消除会被立刻拒稿的硬伤。

#### P0-1 · 全量数字重算 + 结论重写

```
论文 → 实际（现算值）
  802 entities          → 868
  351,649 pairs         → 430,336
  type_error = 4        → 262            ← 差 65 倍
  5.69% declaration     → 16.2%（README 口径）/ 6.6%（standard+flange 严格口径）
  242 vendors           → 348
  top-10 = 28.5%        → 18.7%
  112 pairs @ d=1       → 61 pairs @ d=1
  100% electrical       → electrical 32 / signal 29 / mechanical 0   ← 结论改变
```

**d1 结论必须重写**。原文"all 112 pairs are bottlenecked on the electrical axis alone"现已不成立——signal 轴占 29/61 = **47.5%**。

新结论建议措辞：

> "At d=1, 61 pairs remain: 32 (52.5%) bottlenecked on the electrical axis and 29 (47.5%) on the signal axis. Unlike the earlier snapshot in which the electrical axis accounted for 100% of d=1 pairs, the signal axis has emerged as a **co-equal bottleneck** — a shift caused by [说明原因：signal 端口补声明 / 电气取证补齐]. This itself demonstrates that the bottleneck is **not a fixed property of the domain but a function of corpus state**, which is precisely why we publish it as a recomputed measure rather than a constant."

**这个"从 100% electrical 变成双瓶颈"的变化，本身可以写成一个有价值的观察**——它证明了瓶颈会迁移，因此必须持续重算。把缺陷转成贡献。

**工程动作**：加一道闸门 **G-S1**——论文 `main.tex` 中的 `\d{3},?\d*` 数字与 `api/*.json` 现算值比对，漂移即判红。**从根上消灭"论文数字过期"**。

#### P0-2 · 形式化补强（把重言式换成真定理）

**做什么**：删除/降级现有的 "Soundness"，补三条**真正可证**的定理。

建议的定理结构（写在 `main.tex` 新 §3.x，并在 `compose_core.py` 里给出机器可查的对应测试）：

**Theorem 1（Evidence Monotonicity，证据单调性）**
设 $E \subseteq E'$ 为两个证据集（type_compat 条目集），$\succeq$ 为判定确定性偏序（$\mathsf{unknown} \prec \mathsf{type\_error} \prec \mathsf{compatible} \prec \mathsf{composed}$）。则：

$$\mathsf{compose}_{E}(a,b) = \mathsf{composed} \implies \mathsf{compose}_{E'}(a,b) = \mathsf{composed}$$

**为什么可证**：聚合函数是"取各轴最小值"，而每轴的判定只依赖 $E$ 中条目的**并**；增加条目不会移除已有 identity。因此整体 verdict 在 $\succeq$ 上单调不降。**这是一个真实的代数性质，不是重言式。**

**Theorem 2（Bottleneck Necessity，瓶颈必要性）**
若恰有一轴 $k$ 返回 $\mathsf{unknown}$（即 $d=1$），则补充**轴 $k$** 的声明是使 $\mathsf{compose}$ 变为 decided 的**必要条件**；且在"轴 $k$ 可声明"假设下亦为充分条件。

**为什么可证**：由聚合函数的 min 结构直接得出。

**Theorem 3（Undecidability Boundary，不可判定边界）**
对专有端口类型 $t \in \mathcal{T}_{\text{prop}}$，任意证据集 $E$ 下 $\mathsf{compose}$ 在含 $t$ 的轴上恒为 $\mathsf{unknown}$。

**为什么可证**：`effective_ports()` 过滤 `status ∉ {declared, partial}`，专有类型永不进入判定。

**同时**：把现有 "Soundness" **重命名为 "Internal Consistency"**，并在论文中明确：

> "We deliberately do **not** claim soundness in the physical sense: verifying that `composed` implies physically assemblable requires ground-truth assembly records, which we do not have (§8.3). What we claim is internal consistency: the implementation matches its specification, verified by property-based testing and mutation testing (kill rate 1.00)."

**这一句会显著改善审稿印象**——主动划清"我们能证明什么"与"我们不能证明什么"的边界，是成熟的学术写作。

#### P0-3 · 对外口径自洽

README 的"三条定理（T1/T2/T3）"改为：

> "三条代数律（可靠性 / 证据单调性 / 不可判定边界，经性质测试与变异测试验证）+ 三条研究假说（其中 T2 已被证伪，见 NR-001；T3 为强假说，样本 56 对）"

把"定理"降级为"律/假说"——**这不会削弱项目，反而会增强可信度**，因为它与负结果档案的诚实形象一致。

---

### 阶段 P1 · 达标（3–6 周）

#### P1-1 · 外部效度：构造真正的 ground truth（**最高优先级**）

这是从 preprint 到 SCI 的**分水岭**。方案：

**Step 1 · 人工标注集（50 对）**

从当前语料中分层抽样 50 对（建议：15 对已知能装 / 15 对已知不能装 / 20 对 unknown），由**人**根据厂商 datasheet 独立判定，产出 `api/eval/compatibility-groundtruth.json`。

与现有 Golden 集的关键区别：

| | Golden（现有） | Ground truth（新建） |
|---|---|---|
| 来源 | 冻结引擎输出 | **人工依据 datasheet 独立判定** |
| 字段 | `type: freeze_anchor` | `type: human_annotated` + `annotator` + `evidence_url` |
| 能证明 | 无回归 | **正确性** |

**Step 2 · 双标注者 + Cohen's κ**

至少 2 名标注者独立标注同一批对，报告 **Cohen's kappa**（或 Krippendorff's α）。这直接回应了论文 §8.3 自己提出的缺陷。

**Step 3 · 报告混淆矩阵**

对这 50 对，报告系统的 precision / recall / **unknown rate**，并特别报告：

- **假阳性数（说能装但实际不能）**——这是安全关键指标，论文整篇在反对它，必须给出实测数字
- 若假阳性 = 0，这就是一个**强结果**，可以写进摘要

**成本估算**：50 对人工标注约 2–3 人日。**这是整个提升方案里 ROI 最高的一项。**

#### P1-2 · Baseline 实跑

把 §5.6 的思想实验变成真实验。实现成本极低（改聚合 flag + 重跑）：

| Baseline | 做法 | 报告指标 |
|---|---|---|
| Binary-pessimistic | `unknown → incompatible` | 假阴性数、误指派数 |
| Binary-optimistic | `unknown → compatible` | **假阳性数**（安全关键） |
| Vendor-matrix 模拟 | 仅同厂商才判 compatible | 覆盖率 |
| RoboParts（三态） | 现状 | unknown 率 + 假阳性数 |

产出一个 4 行表格。**这一张表能把 §5.6 从"我们的设计更好"变成"我们测出来更好"。**

#### P1-3 · 参考文献补强（20 → 50+）

必须补的方向（每条 3–5 篇）：

- **模块化机器人 / 硬件抽象**：ICRA/IROS 上 modular robotics、hardware abstraction layer 的工作
- **机器人数据集与基准**：Open X-Embodiment、Bridge、DROID、RH20T（它们都是"数据集论文"，是本文最好的定位锚）
- **知识图谱与硬件知识表示**： robotics ontology / knowledge graph for hardware
- **不确定性量化**：aleatoric/epistemic uncertainty 在机器人中的应用
- **BOM / 供应链信息学**：PLM、supply chain ontology
- **形式化方法与类型系统**：如果把 Theorem 1–3 补上，需要引类型系统与格论的基础文献

**目标**：顶会顶刊占比 ≥ 50%，`@misc` 降到 ≤ 20%。

---

### 阶段 P2 · 加分（2–3 月，决定投哪个档）

#### P2-1 · 可复现性归档

- 数据集快照上传 **Zenodo**，拿 DOI，写进 `CITATION.cff` 与论文
- 代码打 **release tag**，与论文 commit 对应
- 补 **Artifact Evaluation** 材料（README 里给一条 `make reproduce` 命令）

#### P2-2 · 把"可信性工程"升级为显式贡献（C4）

新增一节 §3.x **"Engineering verifiability"**，系统描述：

- 变异评分（6 mutants, kill rate 1.00）
- 负结果档案 NR-01~NR-10
- 验证反模式 AP-01~AP-12
- 性质测试 + 变异自证

并给出**可迁移的方法论**：

> "Any decision system that must say 'I don't know' faces the same verification problem. We distill the failure modes we hit into 12 antipatterns and 10 negative results, each with a falsifiable test. We argue this is reusable beyond robotics."

**这一步能把论文从"一个机器人零件库"提升到"一类判定系统的可信性方法"**——显著提升可接收期刊的档次。

#### P2-3 · 敏感性分析扩展

现有 §5.8 只做了"语料增长的敏感性"。建议补：

- **厂商去留敏感性**：移除 top-5 厂商后，结论是否仍成立
- **标注阈值敏感性**：`confidence` 阈值从 0.5 到 0.9 扫描，结论稳定性
- **轴权重敏感性**：若三轴不等权，瓶颈识别是否改变

---

## 6. 目标期刊分层与路线

| 档次 | 期刊/会议 | 当前是否可达 | 需要完成的方案 |
|---|---|---|---|
| 入门 | **JOSS / SoftwareX** | ✅ **现在就可达** | 无（JOSS 看重软件质量，本项目超出标准） |
| 中档 | **Mechatronics (Elsevier)** / **Robotics and Autonomous Systems** | ⚠️ 需 P0 + P1-1 + P1-3 | 形式化 + ground truth + 引用 |
| 高档 | **IEEE RA-L / ICRA / IROS** | ❌ 需 P0+P1+P2 | 全部 + 更强的新颖性叙事 |
| 顶刊 | **Science Robotics / Nature Machine Intelligence** | ❌ 暂不可及 | 需要物理实验验证 + 大规模部署证据 |

**建议路径**：

1. **先投 JOSS（1–2 周）**——锁定"软件+数据"贡献，拿一个正式引用，成本低
2. **同步做 P0 + P1**（6 周），然后投 **Mechatronics**（已有 cover letter，路径现成）
3. P2 完成后，视审稿反馈决定冲 RA-L/ICRA

**不建议**：直接投高档会议——目前的新颖性叙事（"我们做了个三值判定系统"）在 ICRA 会被认为贡献偏薄。**必须先把叙事重心移到 C2（reflexivity boundary）+ C4（可信性工程）**。

---

## 7. 诚实边界（本评估自身的局限）

1. **`type_error` 4 → 262 的差值原因未追查**。可能是判定规则变化、语料增长、或口径调整。报告中只陈述"数字不一致"这一事实，未断言是论文错误还是产物语义变更。**这是后续必须查清的第一件事**——若口径变了，论文需要的是"重新定义"而非"改数字"。

2. **d1_bottleneck 从 (112, 100% electrical) 变为 (61, 32 elec + 29 sig) 的成因未定位**。可能来自电气取证补齐（`electrical_evidence.json`）或 signal 端口补声明。建议查 `git log` 与产物变更史确认。

3. **R2 的"重言式"判断是基于 `compose_core.py` 中 `ALGEBRAIC_LAWS[0].statement` 的措辞**。若论文 §3 另有独立的形式化定义（本次 grep 未发现 theorem 环境，但不能完全排除用散文形式给出的定义），结论需相应调整。

4. **参考文献质量判断基于 `booktitle`/`journal` 字段的关键词命中**。若某条目实为顶会论文但字段未写 `booktitle`（常见于 `@misc`），实际顶会占比可能被低估。

5. **"50 对 ground truth"的样本量建议是估算**，未做统计功效分析（power analysis）。正式实验设计时建议先做功效分析确定样本量。

6. **本评估未读 `papers/mechatronics_submission/main.tex` 全文**，仅确认其存在且结构与 arXiv 版平行。两版可能存在差异，投稿前需对齐。

7. **变异评分 1.00 的语义边界**：6 个变异体是针对已知失效模式手工设计的，不代表对任意突变的鲁棒性。论文若引用此数字，需说明变异体的构造方式。

---

## 附录：立即可执行的最小动作清单

```bash
# 1. 建立论文数字与产物的一致性闸门（P0-1 的工程化）
#    新增 G-S1：扫描 main.tex 数字 ↔ api/*.json 现算值

# 2. 定位 type_error 从 4 → 262 的成因
git log --oneline -- api/compose_semantics.json
python -c "import json;d=json.load(open('api/compose_semantics.json'));print(d['aggregates']['overall_counts'])"

# 3. 定位 d1_bottleneck 结论变化的成因
python -c "import json;d=json.load(open('api/compose_semantics.json'));print(d['aggregates']['d1_bottleneck'], d['aggregates']['gap_distance'])"

# 4. Ground truth 标注集（P1-1）
#    新建 api/eval/compatibility-groundtruth.json
#    字段：type=human_annotated, annotator, evidence_url, expected_verdict

# 5. Baseline 实跑（P1-2）
#    在 compose_core 加 --binary-pessimistic / --binary-optimistic flag
```

---

*本评估所有数字均由脚本现算自 `api/*.json`，未手工填写。结论可经 `python scripts/ci_gate.py` 与仓库产物复核。*
