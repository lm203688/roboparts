# RoboParts Decidability Ladder — SCI Submission Package

**Paper:** *How Compatible Is "Compatible"? A Four-Level Decidability Ladder and a Taxonomy of Zeros for Robot End-Arm Interfaces*

**Author:** Xing Li · Senior Engineer · Zhejiang Academy of Building Research & Design Co., Ltd. (legal full name pending confirmation) · ORCID 0009-0004-2152-7669 · 463102527@qq.com

**Date frozen:** 2026-11-09. **Route:** subscription / no-APC. **Not submitted by the assistant** (writing + package only).

## What is inside

```
00_Spec/frozen_spec.md           Frozen numbers, claims, wording discipline, fee policy
01_Outline/Outline_EN.md          English outline
01_Outline/Outline_CN.md          Chinese outline (parallel structure, same numbers)
02_Manuscript/Manuscript_EN.md    English master (submission base)
02_Manuscript/Manuscript_EN.docx  English Word
02_Manuscript/Manuscript_EN.pdf   English PDF (pandoc/xelatex, Cambria)
02_Manuscript/Manuscript_CN.md     Chinese parallel draft
02_Manuscript/Manuscript_CN.docx  Chinese Word
03_Submission/Cover_Letter_EN.md
03_Submission/Highlights_EN.md    6 highlights, each ≤85 chars
03_Submission/Title_Page_EN.md
03_Submission/Submission_Guide_Fee_Verification.md   fee verification + journal order
03_Submission/Response_to_Reviewer_prep.md           anticipated reviewer lines
04_ResearchData/ladder_D0_D3.csv                 the four-level ladder
04_ResearchData/bootstrap_three_axis.csv         point estimates + 95% CIs
04_ResearchData/upper_bound_calc.md              reproducible <1% bound on filling 35 parts
04_ResearchData/PRISMA_ScR.md                    reproducible search record
04_ResearchData/data_provenance.md               number → source-file map
04_ResearchData/rp_reproduce.py                  recomputes the headline densities
05_Figures/Fig1_ladder_waterfall.png             300 dpi, English labels
05_Figures/Fig2_three_axis_forest.png            300 dpi
05_Figures/Fig3_taxonomy_of_zeros.png            300 dpi
05_Figures/make_figures.py                       plotting script
build_docx.py                                   md → docx builder (kept for regeneration)
```

## The five contributions (order fixed)

1. Four-level decidability ladder D0→D3: 64.764% → 0.00512% → 0.00372% → 0.00047% (~5 orders), mechanism = 528/553 `ELEC:UNKNOWN` placeholders self-matching.
2. Electrical axis is the weakest under every definition (1–3 orders below mechanical; CIs reported stratified).
3. Taxonomy of zeros Z1–Z5; Z1+Z5 = 297/360 = 82.5% cannot be removed by more evidence.
4. Proposition P1 (port-budget upper bound) with proof and corollaries C1–C3; UR3e/UR5e p=1 ⇒ any two-device co-mount is structurally unsatisfiable.
5. Flange is a kit property, not a device property (one gripper, three ISO labels).

## Provenance tags

Every number carries **[V]** (verified primary), **[O]** (official/secondary, not word-verified), or **[E]** (computed in this study, reproducible). The frozen numbers derive from the main agent's on-the-fly computation over the local RoboParts corpus (`rp_b24.py` / `rp_b2v2.py` / `rp_ladder.py`); see `04_ResearchData/data_provenance.md`.

## Open items for the author (not resolvable by the assistant)

- Legal affiliation full name (business-license exact string).
- CN byline confirmation.
- Per-journal fee-page screenshots (see `03_Submission/Submission_Guide_Fee_Verification.md` §2 re-check path).
- Final choice among AEIN / JIM / RCIM / Mechatronics, and suggested reviewer names.
- Confirm no overlap with other papers in review (CBM / JBE / acoustic-power).
