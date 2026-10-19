# RoboParts — SCI 论文达标核验（2026-10-19 复核）

> 复核依据：对照 2026-10-18 评估报告的"七维审稿评分"与"三个致命缺口"，重新核验 `papers/arxiv_submission/main.tex`（1086 行）、`references.bib`（58 条）、`api/*.json`（产物现算）、`api/eval/compatibility-golden.json`、`git log --since=2026-10-18`（共 27 个相关提交）。
> 结论先行：**项目已跨过"够格投稿 SCI 期刊"的门槛，从 arXiv/JOSS 级升入"可信的 Mechatronics / RA-L 投稿级"。但还不是"稳过"——唯一硬 blocker 是外部效度。**

---

## 1. 一句话判定

| 维度 | 2026-10-18 | 2026-10-19 | 变化 |
|---|---|---|---|
| 是否到 SCI 级 | 否（arXiv/JOSS 级） | **临界·已够格投稿但非稳过** | ↑ 跨档 |
| 形式化（定理） | D（定理数 = 0） | **B+（3 定理 + 1 定义，均带证明、可机验）** | ↑↑ |
| 数字对齐 | D（全面漂移，最大差 65×） | **A（摘要 868/430336/262 全部等于现算）** | ↑↑↑ |
| 相关文献 | C（20 条，12 misc，顶会/刊 0） | **B（58 条，14 inproceedings，19 处顶会/刊命中）** | ↑↑ |
| 实验设计 | C（对比=思想实验） | **B−（新增真实 ablation + 设计选择对比）** | ↑ |
| 外部效度 | D（Golden=freeze_anchor） | **D（仍无人工 ground truth）** | — 未动 |
| 诚实性/可复现 | A / B | **A / B**（保持，新增 §5.10 工程可验证性 + C4 贡献） | 保持 |

**净判定：三个致命缺口全部闭合；剩余唯一硬伤是外部效度（无人工标注 ground truth）。**

---

## 2. 三条致命缺口的闭合证据（逐条核验）

### ② d1 结论："电气独霸" → "双轴瓶颈" ✅ 已闭合
- 摘要原文：`61 pairs at d=1 split between electrical (32, 52.46%) and signal (29, 47.54%) axes — a two-axis bottleneck, not a single one.`
- 现算对账：`d1_bottleneck = {mechanical:0, electrical:32, signal:29}` → **完全吻合**。
- 意义：不仅修了错，还把"瓶颈会随语料迁移"的观察**转成了贡献**（data-flywheel 优先级队列的可度量性，由 Bottleneck Necessity 定理支撑）。

### ② 形式化：定理从 0 → 3 + 1 定义，且均有证明 ✅ 已闭合（含更正）
- `Internal Consistency`（Definition，476 行）— 证明：`Immediate from agg rule... ◼`
- `Evidence Monotonicity`（Theorem，496 行）— 证明：基于 `agg` 的 min-结构，证据并集不删 identity 对... ◼
- `Bottleneck Necessity`（Theorem，520 行）— 证明：min-结构 + 轴独立... ◼
- `Undecidability Boundary`（Theorem，549 行）— 证明：`effective_ports()` 只收 declared/partial... ◼
- **更正既往误判**：10-18 我用 `\begin{proof}` 环境计数得到 0，误以为"无证明"。实际证明以内联 `\emph{Proof.} + ◼` 写出，四条均有**实质证明**，且正文明确指向 `tests/property/test_compose_lattice.py`（性质测试 + 变异测试 kill rate 1.00 机验）。
- 同时**采纳了 10-18 的核心建议**：原"Soundness"已正确降级为 `Internal Consistency`，并在 488 行起显式说明"不声称物理 soundness，只声称规格一致性"——精准规避了审稿人抓"重言式 soundness"的风险。

### ③ 数字漂移 ✅ 已闭合
- 摘要 868 / 430,336 / 262 与 `api/entities.json`、`api/compose_semantics.json` 现算**逐项相等**。
- 参考文献从 20 → 58，新增 14 条 `@inproceedings`（ICRA/IROS/CoRL/RSS 等）、ISO 22166 标准条目、Coq/CompCert/F* 形式化先例。

---

## 3. 当前七维复盘（更新版）

- **A 研究问题与动机**：二值→假绿/假红的论证扎实，reflexivity boundary（两个同型号 OUTPUT_SPIKE 公头插不到一起）仍是反直觉强卖点。保持。
- **A 诚实性**：Threats to validity（1288 行）四点齐全且诚实——明确承认 868 语料小、顶 10 厂商占 37.33%、人工分类需 inter-annotator 复核、snapshot 有时效性。这是投稿级诚实。
- **B 可复现性**：82 产物现算 + 64 闸门 + 变异评分 1.00 + 时间戳；新增 §5.10 把 CI 栅栏本身写成 C4 贡献。仍缺 DOI/Zenodo 归档（P2 项）。
- **B 相关文献**：58 条、含顶会/顶刊与形式化先例。已脱离"文献薄弱"。
- **B− 实验设计**：新增 §5.10 工程可验证性 + C4 贡献（即 10-18 建议的"可信性工程"显式化，已落地）；ablation 真实（翻转 reflexive flag，同数据实跑）；对比为"设计选择对比"（诚实说明"无同规模竞品语料故不 benchmark"）。
- **C→B+ 形式化**：3 定理 + 1 定义，均证明 + 可机验。
- **D 外部效度**：**唯一未动项**。见第 4 节。

---

## 4. 唯一硬 blocker：外部效度（External Validity）

**现状**：`api/eval/compatibility-golden.json` 共 28 cases，类型仍为 `{freeze_anchor, badcase}`——即"冻结引擎自身输出"+"已知坏案例"。它能防回归，**不能证明判定正确**。

**论文自认**（1302–1305 行）：
> "The gap-causation taxonomy ... depends on human judgement over datasheets. A systematic re-annotation study with inter-annotator agreement would strengthen the finding."

即作者已知道、但**尚未补**。这是目前唯一把论文挡在"稳过"之外的缺口。

**补法（ROI 最高，10-18 已列 P1）**：
1. 抽 **50 对**人工标注（覆盖 composed / type_error / unknown 三态，含若干 reflexivity boundary 对），标注者 ≥ 2 人；
2. 报 **Cohen's κ**（≥ 0.8 即强证据）；
3. 把"双标注者 κ"写进 Experiments 与 Threats 的回应。
- 这一步直接回应论文自己点名的缺陷，且把"诚实"从姿态变成可量化证据。预计 3–6 周。

---

## 5. 投稿路径建议（更新）

| 路径 | 当前状态 | 动作 |
|---|---|---|
| **JOSS** | 已达 | 可立即投（软件+数据论文，对形式化/外部效度要求低） |
| **Mechatronics** | 已达（投前做 §4 的 50 对标注更佳） | 现在就可投；cover letter 现成 |
| **RA-L (IEEE)** | 临界 | 补 §4 外部效度后即达；RA-L 看重"可复现 + 实验严谨"，ablation+性质测试已够，缺的是 ground truth |
| **ICRA/IROS** | 仍偏薄 | 等 §4 补完 + 把"可信性工程"做成独立实证章节后再冲 |

**重心结论**：最独特贡献已明确为 **(a) reflexivity boundary（反直觉、有 ablation）** 与 **(b) 可信性工程（变异评分 + 负结果 + 反模式，机器人领域几乎无人做）**，而非"三值框架"本身（别处早有）。叙事已对齐此重心。

---

## 6. 自检边界（诚实登记）

1. 定理证明为**非形式化内联证明 + 性质测试机验**，非 Coq/Isabelle 机器证明；顶 math 刊不够，机器人/系统刊可接受。
2. 数字对齐基于 2026-10-19 现算；`entities.json` 仍含 47 条 quarantine，摘要"868"含隔离件——口径需与正文一致声明（论文已在 Threats 标注 snapshot）。
3. ablation 为**合成翻转**（非独立重实现系统），对比为设计选择对比，非同数据集跑竞品；作者已诚实声明。
4. 外部效度缺口**未经实测**（无联网回探标注集），判定依据为文件内容与论文自述。
5. 参考文献 58 条含部分 `@misc`（arXiv 预印本），正式投稿前需补正式出版信息。
6. 本复核未重跑编译；LaTeX 结构修复提交（0d5a081）存在，但 PDF 渲染成功率未验证。
