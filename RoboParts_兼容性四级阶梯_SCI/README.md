# How Compatible Is "Compatible"? A Four-Level Decidability Ladder and a Taxonomy of Zeros for Robot End-Arm Interfaces

**中文题目：** "兼容"到底有多兼容？机器人末端接口的四级可判定性阶梯与零的分类学

Submission package, generated 2026-11-09 for a single-journal submission under the zero-fee (subscription) route.

---

## 0. Package map

| Folder | Contents | Role |
|---|---|---|
| `00_Spec/` | `FROZEN_NUMBERS.json`, `spec.md` | The single source of every number in the paper, and the writing specification the manuscript was held to |
| `01_Outline/` | `TopicJustification_Outline_EN.md/.docx`, `TopicJustification_Outline_CN.md/.docx` | Topic justification and section-level outline, English and Chinese |
| `02_Manuscript/` | `Manuscript_EN.md/.docx/.pdf`, `Manuscript_CN.md/.docx/.pdf` | The manuscript in both languages, same section order, same table numbers, same numbers |
| `03_Submission/` | `CoverLetter.md`, `TitlePage.md`, `Highlights.md`, `ResponseToReviewer_Prep.md`, `SubmissionGuide_FeeVerification.md`, `PRISMA_SearchLog_and_DataProvenance.md`, `BlindedManuscript.md` | Everything the submission system asks for, plus the fee verification trail and the search log |
| `04_ResearchData/` | `DataDossier.md`, `Tables/T1..T7*.csv`, `Scripts/rp_*.py`, `results/*.json`, `PRISMA_search_log.md`, `references_verified.md`, `literature_notes.md`, `refs.bib` | Supporting data, the verifiable reference ledger, and the scripts that recompute the headline numbers |
| `05_Figures/` | `Fig1_decidability_ladder.png`, `Fig2_axis_forest.png`, `Fig3_zero_taxonomy.png`, `make_figures.py` | Three 300 dpi English figures plus the script that regenerates them |

---

## 1. The claim in one paragraph

Robot cells are retooled by procuring end-of-arm parts whose mutual compatibility has to be established before purchase. The literature has treated that as a decision problem: give the description, and the answer follows. This paper treats it as a measurement problem and measures how much of the answer is decidable at all, at what evidential price, and which part no additional evidence can move. On an audited catalogue of 656 composable end-arm nodes (214,840 unordered pairs, 329 manufacturers), four nested evidence thresholds move the electrical decision rate from **64.764%** (D0) to **0.00512%** (D1) to **0.00372%** (D2) to **0.00047%** (D3) — a spread of five orders of magnitude. The top of the ladder is self-matching: **528 of 553** electrical ports carry the placeholder label `ELEC:UNKNOWN`, and **139,128 of 139,139** D0 pairs (**99.992%**) are unknown matched against unknown. Of 360 co-mount pair evaluations, **297 (82.5%)** return a zero that completing missing datasheets cannot remove, and Proposition P1 proves that on hosts exposing a single tool-side slot, any two-device co-mount question is unsatisfiable regardless of declaration completeness.

The paper does not claim a compatibility rate. It claims that any such rate is a function of an unstated evidential threshold, and it gives the irreducible part a structural bound.

---

## 2. Numbers and where they come from

Every number in the manuscript traces to `00_Spec/FROZEN_NUMBERS.json`. Numbers are tagged at three tiers:

- **[V] verified first-hand** — we opened the vendor document and the quoted text is reproduced word for word (four of the eight cases in Section 8).
- **[O] official or second-hand** — the vendor states it or the audit catalogue records it, but the sentence is a synthesis, not a quotation (four of the eight cases; the whole flange-suite argument in Section 8.2 depends on these and is labelled as such).
- **[E] computed in this study** — the number is produced by the scripts in `04_ResearchData/Scripts/` from the corpus files, and is recomputable.

Two numbers are reported against their documented recomputations rather than silently reconciled, both disclosed in the manuscript: the manufacturer count (**329** frozen vs **328** under strict string de-duplication, Section 3.1) and the mechanical same-flange row (**295 / 0.1373%** frozen vs **996 / 0.4636%** under an unfiltered token match, Section 9.3). The frozen values are the manuscript values; the gap is stated, not smoothed over.

---

## 3. How to recompute the headline numbers

```
cd 04_ResearchData/Scripts
python rp_ladder_recompute.py     # D0 139,139 / D1 11 / D2 8 / D3 1, UNKNOWN×UNKNOWN 139,128
python rp_upper_bound.py          # C(35,2)=595, 35×19=665, 1,260, +8, 1,268, 0.590% / 0.632%
python rp_bootstrap.py            # B=1000, seed=20261109, 329 whole manufacturer clusters (~0.6 s)
```

Inputs are the corpus JSON files; every number the scripts print is compared against `00_Spec/FROZEN_NUMBERS.json` in `04_ResearchData/results/frozen_checks.json` (57 checks: 45 match, 3 mismatch, 9 not recomputed — each mismatch and each non-recomputed item is itemised in `04_ResearchData/DataDossier.md` §4).

`python 02_Manuscript/check_numbers.py 02_Manuscript/Manuscript_EN.md 00_Spec/FROZEN_NUMBERS.json` re-runs the numeric gate used before submission: banned-string scan, required-number presence, percentage whitelist against the frozen file, and per-table row counts.

---

## 4. Journal route and the zero-fee constraint

| Order | Journal | Publisher | Route | Cost |
|---|---|---|---|---|
| 1 | Robotics and Computer-Integrated Manufacturing (ISSN 0736-5845) | Elsevier, hybrid | subscription | no charge to the author |
| 2 | Journal of Intelligent Manufacturing (ISSN 0956-5515) | Springer, hybrid | subscription (Open Choice is the paid option) | no charge to the author |
| 3 | Mechatronics (ISSN 0957-4158) | Elsevier, hybrid | subscription | no charge to the author |
| 4 | Advanced Engineering Informatics (ISSN 1474-0346) | Elsevier, hybrid | subscription | no charge to the author |

One manuscript, one journal at a time; no simultaneous submissions. The three Elsevier titles are covered by the publisher's own statement that authors publishing in hybrid journals can publish under the subscription model at no cost. **Journal-level APC figures are marked `NOT_VERIFIED`** in `03_Submission/SubmissionGuide_FeeVerification.md`: the figure matters only for the paid route, and the paid route is not taken. Do not fabricate the figures to fill the table.

The manuscript is declared as not under consideration elsewhere and as having no overlap with the author's three manuscripts currently under review (construction and building materials; building engineering; sound-powered building envelope). This declaration is in `03_Submission/CoverLetter.md`.

---

## 5. Authorship

Corresponding author: **Xing Li**, Senior Engineer, Zhejiang Academy of Building Research & Design Co., Ltd., ORCID 0009-0004-2152-7669, 463102527@qq.com. Full legal affiliation name pending confirmation against the business licence (see `03_Submission/PRISMA_SearchLog_and_DataProvenance.md` §7).

---

## 6. The reference library

`04_ResearchData/references_verified.md` holds **38 verified records**: 29 entered through the structured search (the flow recorded in `PRISMA_search_log.md`: 35 identified, 31 after de-duplication, 29 included) and 9 added by citation chasing and targeted verification. The manuscript cites **28** of the 38; the ten held but uncited records are listed with their reasons. Every manuscript entry carries a DOI or an openable URL, and the numbering runs continuously from [1] to [28].

Two entries were corrected while the library was built, and the corrections are recorded rather than silently applied. The 1996 Sabin &amp; Freuder item had first been logged under a wrong title (an IEEE Expert paper that could not be opened); it is now the verified workshop paper *Configuration as Composite Constraint Satisfaction*, and it is held in the library without being cited. The Siltala 2016 item had been logged under a single author and now carries its three authors and its DOI.

---

## 7. What is not done here

- No submission has been made to any journal, and no account action was taken on the author's behalf. The submission itself is left to the author.
- Reviewer suggestions are not drafted.
- Section 8 rests on four verbatim quotes and four audit syntheses; the distinction is stated case by case and must not be collapsed in copy-editing.
- The mechanical axis is reported at flange-string level. A device-level mechanical identity judgement would need hole geometry, dowel positions and the load path, which no vendor in the audit publishes in machine-readable form.

---

## 8. Known pending items

1. Legal affiliation full name to be confirmed against the business licence.
2. Journal-level APC figures remain `NOT_VERIFIED` (the paid route is not taken, so this does not block submission).
3. `Sabin &amp; Freuder 1996` is verified and held but not cited, so that the manuscript's 28 entries can all be traced to an opened record; nothing is cited that could not be opened.
4. Reviewer suggestions to be written by the author if the journal requests them.

---

## 9. Language versions

The English manuscript is the submission text (9,663 words of body text, 28 references). The Chinese manuscript is a full parallel translation, not an abridged one: same section order, same six tables with the same row counts, same figures, same [1]–[28] numbering, and every number reproduced verbatim (10,774 Chinese characters of body text). Where a figure caption or a table header had to be translated, the numbers inside were left untouched.

---

*Package generated 2026-11-09. Everything in it is reproducible from the files in this folder; nothing in it depends on a service that must be paid for.*
