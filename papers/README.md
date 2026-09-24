# RoboParts 论文计划 · 2026-09-24

> 方向转向研发后的论文产出计划。每篇论文对应方向锚点
> `docs/PROJECT_DIRECTIONS_V2.md` 的一条主张。
> **纪律**：数字全部现算自 `scripts/onboarding_block.py::facts()`
> 与 `api/*.json` 产物；禁手写。代码 MIT / 数据 CC BY 4.0。

---

## 索引

| # | 论文 | 状态 | 主要贡献 | 目标出口 |
|---|---|---|---|---|
| **P1** | Three-State Honesty in Open Hardware Compatibility | **草稿完成** | 三态裁决代数 + 5.69% 基线 + d1_bottleneck 100% 电气 + 缺口成因三分类 + 杠杆分析 | arXiv cs.RO 预印本 |
| P2 | A Gap-Cause Taxonomy for Mechanical Interface Data | 大纲（待写） | unpublished/proprietary/ambiguous 三分类 + 杠杆分析的负向证据 | Sensors (MDPI) 短文 |
| P3 | Operator+DAG Modeling for Reproducible Engineering Data Pipelines | 大纲（待写） | 零依赖算子+DAG 骨架 + 等价性证明作为闸门 | arXiv cs.SE / J. Ind. Inf. Integration |

**参考文献清单**：`papers/refs-free-sci-20260924.md`（16 篇免费 / 开放获取论文）

---

## P1：Three-State Honesty in Open Hardware Compatibility

**文件**：`papers/paper1-three-state-honesty.md`

**核心主张**：
$$\texttt{compose}(a, b) \in \{\texttt{composed},\ \texttt{type\_error},\ \texttt{unknown}\}$$
`unknown` 优先级**高于** `composed`——「我不知道」是一等公民。

**贡献**：
1. 三轴（机械 / 电气 / 信号）类型系统 + 三态裁决代数 + reflexivity 公理边界；
2. 802 实体、439 可判定粒度、25 已声明（5.69%）的诚实基线；
3. gap_distance（d=1/2/3）+ d1_bottleneck 作为数据飞轮排序依据
   （112 对 d=1 全部卡在电气轴）；
4. 缺口成因三分类 + 杠杆分析（242 家制造商、头部 10 家仅 28.5%）的负向证据。

**必引参考文献**：[R1] Linkify · [R2] CAD 关系学习 · [R5] ExtruOnt ·
[R7] 操作 KG · **[R10] ReconVLA（最直接哲学同构）**。

**投稿路径**（成本升序）：
1. arXiv cs.RO 预印本（免费，占时间戳）；
2. IROS / ICRA workshop（短文 4–6 页）；
3. Science Robotics「Technical Comment」/ RAM（RA-Letters）；
4. 期刊（Sensors MDPI / J. Ind. Inf. Integration）。

---

## P2：A Gap-Cause Taxonomy for Mechanical Interface Data（大纲，待写）

**核心主张**：414 开放缺口 = unpublished_suspect 350 /
proprietary_suspect 5 / ambiguous 59——**成因分类是可判定的**，
不需要「让厂商开放数据」这种不可验证的主张。

**贡献**：
1. 缺口成因三分类判据（`manufacturer ∨ source` 收紧后的版本，
   59 条无制造商退回 ambiguous）；
2. 杠杆分析（242 家制造商、头部 10 家 28.5%、14.3% 无制造商）；
3. **负向证据**：抓少数厂商 datasheet 是必要但不充分，
   主缺口只能靠用户提交 / OSS BOM 反喂 / 社区 PR 收敛；
4. 与 ExtruOnt [R5] / Model Management KG [R6] 的本体学对比——
   我们做的是「数据缺口本体」，不是「组件本体」。

**目标出口**：Sensors (MDPI) 短文（开放获取，需 APC 或机构订阅）
或 arXiv cs.AI 预印本。

**必引**：[R5] ExtruOnt · [R6] Model Management KG · [R9] ML+Ontology 综述。

---

## P3：Operator+DAG Modeling for Reproducible Engineering Data Pipelines（大纲，待写）

**核心主张**：**「可判定」本身必须被检验**——等价性证明是
pipeline 骨架价值的唯一定义，只比产物必假绿，必须变异对照。

**贡献**：
1. 零依赖纯 stdlib 算子 + DAG 骨架（借鉴 GOAI 2026 冠军 DataFlow-Agent
   的建模思想，不搬依赖——它是 vLLM 重栈，进不了 Workers）；
2. **等价性证明**：`verify_pipeline.py` 23 项自测，逐字段对账
   `build_X.build()` 与 `Pipeline.run('X')`，SKIP 仅 `meta.generated_at`/
   `meta.generated_by`，其余全相等；
3. **两条硬约束**：算子名含 `.` 时 `resolve_input` 必须做长度降序
   前缀匹配（naive `split('.')` 会误判）；`_summarize` 只做形状摘要
   不 dump 全量（trace 里不出现 PII 或大对象）；
4. 已迁移：gap_classification（7 算子）+ compose_semantics（6 算子）；
   未迁移 13 个 build_ 脚本。

**目标出口**：arXiv cs.SE 预印本 或 J. Industrial Information Integration。

**必引**：[R6] Model Management KG · [R9] ML+Ontology 综述 ·
STEP-NC 框架 [R12]（同为「统一数据脊柱」方法学）。

---

## 通用纪律

1. **数字现算**：任何论文里的数字必须能从 `facts()` 或 `api/*.json`
   现读，不手写；手写期望的下场——临时探针报 4 处 FAIL 全是探针自己错。
2. **参考文献免费优先**：优先 arXiv / MDPI / PLOS；付费期刊只引摘要。
3. **不夸大贡献**：`composed = 0` 是数据缺口的诚实画像，不是系统失败；
   5.69% 是覆盖率地图，不是 benchmark。
4. **投稿前复核**：锚点 §2 三问闸门（真数据 / 独特贡献 / 可复现代码）。
5. **投稿时机**：先 arXiv 预印本占时间戳，再视反馈决定是否升级期刊。

---

## 与现有文档的关系

- **`docs/paper-compose-calculus-outline.md`**：Phase B3 提纲占位（旧），
  本文档 P1 是它的正式草稿版。
- **`docs/PROJECT_DIRECTIONS_V2.md`**：方向锚点 v2.2，§1 是 P1 的主张源。
- **`docs/direction-evolution-roadmap-20260923.md`**：Phase B 路线图，
  B1/B2 已落地（P1 的基础设施），B3 是论文发表。
- **`docs/hardcore-roadmap-20260921.md`**：硬骨头清单，P3 是 H1 声明率
  提升的方法学前置。
