# RoboParts 论文 · Mechatronics 投稿版

## 目标期刊

- **Mechatronics: The Science of Intelligent Machines** (ISSN 0957-4158)
- Publisher: Elsevier Ltd.
- IF (2024): 3.2 / 5y 3.6
- CAS 分区: 大类计算机科学 3 区 / 小类工程:机械 2 区、机器人学 3 区、工程:电子电气 3 区
- Publishing model: **Hybrid** — Subscription track **APC = $0**（明确承诺 "No publication fee charged to authors"）
- Word limit: 10,000 词 / 15 页
- 投稿: https://www.editorialmanager.com/MECH

## 文件清单

| 文件 | 用途 |
|---|---|
| `main.tex` | 主稿件（LaTeX，`elsarticle-num` 模板，编号引用） |
| `references.bib` | BibTeX 参考文献（19 条，Elsevier 编号格式） |
| `cover_letter.tex` | 编辑信（已移除审稿人建议，转 PDF 附加） |
| `highlights.txt` | 5 条 highlights（每条 ≤ 85 字符） |
| `figures/*.pdf` | 4 张真实数据图（矢量 PDF，Elsevier 要求） |
| `scripts/make_figures.py` | 图生成脚本（读 `api/*.json` 现算，禁手写） |
| `README.md` | 本文件：编译与投稿流程 |

## 编译

```bash
# 1) 从 CTAN 或 Elsevier 官方下载 elsarticle 包
# https://www.ctan.org/pkg/elsarticle
# 下载后把 elsarticle.cls / elsarticle-num.bst 放到当前目录

# 2) 三次编译（bibtex + latex + latex）
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex

# 3) 输出 main.pdf，提交 Editorial Manager 时选 "Regular Article"
```

## 图（4 张真实数据图，全部矢量 PDF）

全部由 `scripts/make_figures.py` 从 `api/*.json` **现算生成**，跑一次即可重建：

```bash
python papers/mechatronics_submission/scripts/make_figures.py
```

脚本内建断言保证与 SoT 一致（top10_share_pct / distinct_manufacturers / d1 总数 / gap_distance 求和）。

| 文件 | 引用 label | 内容 |
|---|---|---|
| `figures/concentration_curve.pdf` | `\ref{fig:concentration}` | 242 家制造商累计份额 vs. rank，标注 Top 10 = 28.5%、90% 需要多少家 |
| `figures/d1_bottleneck_bar.pdf` | `\ref{fig:d1}` | 112 对 d=1 的轴分布：电气 100% / 信号 0% / 机械 0% |
| `figures/gap_distance_hist.pdf` | `\ref{fig:gap}` | 对数轴柱状图：d=0/1/2/3 各多少对，凸显 d=3 长尾 |
| `figures/reflexivity_boundary.pdf` | `\ref{fig:reflexivity}` | 左右对比：几何规格型（虚线 → composed） vs 方向性角色型（点线 → type_error） |

## 用户必须手动补的东西（占位符 `TODO`）

`main.tex` / `cover_letter.tex` 内以 `TODO_` 前缀标记，投稿前用编辑器全局搜索：

1. **作者姓名**（现写 `Lexing Li`，按实际英文名改）
2. **单位全称** `TODO_affiliation`（如无依托机构可写 "Independent Researcher, China"）
3. **通讯邮箱** `TODO_email`（必须真实可收发邮件，Elsevier 用它发所有通知）

其余项已处理：
- ✅ ORCID：`https://orcid.org/0009-0004-2152-7669`（已写入作者块）
- ✅ 基金号：无 → Acknowledgements 节已删除
- ✅ 审稿人建议：用户不提供 → Cover letter 已改为 "We have no reviewer suggestions"
- ✅ 全部图：4 张矢量 PDF 真实数据图，脚本可重建
- ✅ Data Availability：GitHub 仓库 + commit 快照
- ✅ Competing Interests 声明（"no competing interests"）
- ✅ Generative AI Use 声明（"confined to language editing"）

## 数字溯源（现算，禁手写）

所有数据都来自 `scripts/onboarding_block.py::facts()` 与 `api/*.json` 产物，与 `papers/paper1-three-state-honesty.md` 一致：

| 数字 | 值 | 来源 |
|---|---|---|
| 总实体 | 802 | `facts()['total_entities']` |
| 机械可判定 | 439 | `facts()['mech_applicable']` |
| 机械已声明 | 25 | `facts()['mech_declared']` |
| 机械声明率 | 5.69% | `facts()['mech_pct']` |
| 全对评测对数 | 351,649 | `api/compose_semantics.json['aggregates']['pairs_evaluated']` |
| composed | 0 | `aggregates.overall_counts['composed']` |
| type_error | 4 | `aggregates.overall_counts['type_error']` |
| unknown | 351,645 | `aggregates.overall_counts['unknown']` |
| d=1 对数 | 112 | `aggregates.gap_distance['1']` |
| d=1 电气瓶颈 | 100% | `aggregates.d1_bottleneck` |
| 未发表嫌疑 | 350 | `gap_classification.buckets.unpublished_suspect` |
| 私有嫌疑 | 5 | `buckets.proprietary_suspect` |
| 模糊 | 59 | `buckets.ambiguous` |
| 制造商数 | 242 | `gap_leverage.distinct_manufacturers` |
| 头部 10 家占比 | 28.5% | `gap_leverage.top10_share_pct` |

## 关键改动 vs 原稿 `paper1-three-state-honesty.md`

| 维度 | 原稿 | Mechatronics 版 |
|---|---|---|
| 摘要长度 | 中文长摘要 | ≤ 250 词英文 |
| Highlights | 无 | 5 条 bullet（每条 ≤ 85 字符） |
| 章节顺序 | 引言→相关工作→形式化→实现→评估→讨论→结论 | IMRaD：Intro→Related→Method→Dataset→Experiments→Discussion→Conclusion |
| 参考文献 | 中文叙述式 | Elsevier 编号制 `[1]` `[2]` ... |
| 声明 | 无 | + Data Availability + Generative AI Use + Competing Interests |
| 图表 | 无 | 4 张真实数据矢量 PDF + 4 张表格（全部数据来自 pipeline） |
| 语言 | 中文 | 英文（投稿要求） |
| 语气 | 反思型 + 哲学立场 | 数据驱动的实证论说 |

## 投稿路径（三阶段）

1. **投稿前**：填完 `TODO_email` + `TODO_affiliation` → 下载 elsarticle → 三次编译 → 检查 PDF
2. **投稿**：https://www.editorialmanager.com/MECH → New Submission → Regular Article → 上传 PDF + 源文件 + highlights.txt + cover_letter.pdf
3. **备选转投**（如 6 个月内未决定）：
   - Robotics and Autonomous Systems（IF 5.2，2 区，同类 Elsevier，模板复用率高）
   - Knowledge and Information Systems（IF 3.1，Ontology 更对味）
   - Journal of Intelligent Manufacturing（IF 7.4，2 区，制造+知识表示交叉）
