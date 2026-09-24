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
| `references.bib` | BibTeX 参考文献（20 条，Elsevier 编号格式） |
| `cover_letter.tex` | 编辑信（可选，转成 PDF 附加） |
| `README.md` | 本文件：编译与投稿流程 |

## 编译

```bash
# 1) 从 CTAN 或 Elsevier 官方下载 elsarticle 包
# https://www.ctan.org/pkg/elsarticle
# 下载后把 elsarticle.cls / elsarticle-harv.bst / elsarticle-num.bst 放到当前目录

# 2) 三次编译（bibtex + latex + latex）
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex

# 3) 输出 main.pdf，提交 Editorial Manager 时选 "Regular Article"
```

## 用户必须手动补的东西（占位符 `TODO`）

在 `main.tex` 内以 `% TODO:` 前缀标记，投稿前用编辑器全局搜索：

1. **作者信息**（`\author{...}` / `\affil{...}` / `\ead{...}` / ORCID）
2. **基金号**（`\fntext`，无则写 "This work was supported by ..."）
3. **图**：所有 `\includegraphics{figures/xxx.pdf}` 需替换为真实图表（矢量 PDF/SVG）
4. **AI 使用声明**：`\usepackage[ai]` 部分按 Elsevier 要求写明使用了什么 AI 工具（本论文写作过程如使用 LLM 需在此声明）
5. **Data Availability** 具体 DOI / URL（现写 GitHub 仓库 + `api/*.json` 快照）
6. **通讯地址与邮编**

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
| d=1 对数 | 112 | `aggregates.d1_bottleneck['count']` |
| d=1 电气瓶颈比例 | 100% | `d1_bottleneck.by_axis.electrical / d1_bottleneck.count` |
| 未发表嫌疑 | 350 | `api/gap_classification.json['buckets'].unpublished_suspect.count` |
| 私有嫌疑 | 5 | `buckets.proprietary_suspect.count` |
| 模糊 | 59 | `buckets.ambiguous.count` |
| 制造商数 | 242 | `totals.manufacturers` |
| 头部 10 家占比 | 28.5% | `gap_leverage.top10_share` |

## 关键改动 vs 原稿 `paper1-three-state-honesty.md`

| 维度 | 原稿 | Mechatronics 版 |
|---|---|---|
| 摘要长度 | 中文长摘要 | ≤ 250 词英文 |
| Highlights | 无 | 5 条 bullet（每条 ≤ 85 字符） |
| 章节顺序 | 引言→相关工作→形式化→实现→评估→讨论→结论 | IMRaD：Intro→Related→Method→Dataset→Experiments→Discussion→Conclusion |
| 参考文献 | 中文叙述式 | Elsevier 编号制 `[1]` `[2]` ... |
| 声明 | 无 | + Data Availability + Generative AI Use + Competing Interests |
| 图表 | 无 | 5 个 figure slot + 4 个 table slot（占位） |
| 语言 | 中文 | 英文（投稿要求） |
| 语气 | 反思型 + 哲学立场 | 数据驱动的实证论说 |

## 投稿路径（三阶段）

1. **投稿前**：填完所有 TODO → 编译 → PDF 检查
2. **投稿**：https://www.editorialmanager.com/MECH → New Submission → Regular Article → 上传 PDF + 源文件
3. **备选转投**（如 6 个月内未决定）：
   - Robotics and Autonomous Systems（IF 5.2，2 区，同类 Elsevier，模板复用率高）
   - Knowledge and Information Systems（IF 3.1，Ontology 更对味）
   - Journal of Intelligent Manufacturing（IF 7.4，2 区，制造+知识表示交叉）
