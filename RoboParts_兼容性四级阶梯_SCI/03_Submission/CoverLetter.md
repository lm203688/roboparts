# Cover Letter

**To:** The Editor-in-Chief
Robotics and Computer-Integrated Manufacturing (Elsevier, ISSN 0736-5845)

**Date:** 9 November 2026

**Manuscript:** "How Compatible Is 'Compatible'? A Four-Level Decidability Ladder and a Taxonomy of Zeros for Robot End-Arm Interfaces"

**Author:** Xing Li, Senior Engineer, Zhejiang Academy of Building Research & Design Co., Ltd. (Hangzhou, China)

Dear Editor,

I submit the enclosed manuscript for consideration as a research paper in *Robotics and Computer-Integrated Manufacturing*. The paper is a corpus measurement with one formal proposition. It does not report new hardware experiments; it measures how much of the "is this end-effector compatible with that robot" question is decidable at all, and it proves a structural upper bound on co-mounting that no amount of catalogue completion can remove.

**Why RCIM.** The journal's scope covers computer-integrated manufacturing, robotic assembly, and the integration of end-effectors into workcells — exactly the setting in which a purchaser or integrator has to decide, before buying, whether two listed parts will actually mate. The manuscript addresses that decision process directly: it measures it on a 656-node, 329-vendor audit catalogue with 214,840 unordered pairs, and it states the conditions under which the decision is structurally unavailable.

**What the paper contributes, in three sentences.**

- It shows that interface compatibility is a *measurement problem*, not a decision problem: decidability collapses by five orders of magnitude across four evidence thresholds (64.764% → 0.00512% → 0.00372% → 0.00047%), and the 12,650-fold drop from D0 to D1 is driven by a placeholder mechanism in which 528 of 553 electrical ports carry the type label `ELEC:UNKNOWN` and 99.992% of D0 pairs are `UNKNOWN × UNKNOWN`.
- It classifies the 360 co-mounting zero verdicts into five categories Z1–Z5 and shows that 297 of 360 (82.5%) belong to the two categories that further evidence cannot eliminate (port budget exhausted and role non-complementary).
- It proves proposition P1 — that k ≤ p(h) where p(h) is the host's independently powered, independently addressed tool-side slot count — and derives corollary C1: on the UR3e and UR5e, p = 1, so every k ≥ 2 co-mounting question is unsatisfiable regardless of how complete either side's declarations are. The most optimistic completion bound leaves electrical decidability at 0.590% of the pair denominator.

**Submission declarations.**

- This manuscript is original, has not been published previously in any form, and is not under consideration by any other journal. One manuscript, one journal.
- Three distinct manuscripts of mine are currently tracked in parallel pipelines and are explicitly *not* overlapping with the present one: (i) a materials-durability framework paper tracked for *Cement and Concrete Composites* / *Construction and Building Materials*; (ii) a sodium-ion-battery wall-energy manuscript tracked for *Journal of Building Engineering*; and (iii) an acoustic-energy-harvesting building-wall manuscript tracked elsewhere. None of those shares data, figures, the corpus, the ladder numbers, or the proposition with the present paper. I disclose them here so that the editorial record is complete.
- Funding: none. Competing interests: none.
- I select the **subscription (non-open-access) route**. I do not request Gold Open Access and expect no article processing charge.
- All quantitative inputs are archived in the package's `04_ResearchData/` folder (tables, bootstrap JSON, recomputation scripts, frozen-check manifest) and can be reproduced from the stated inputs and random seed (B = 1000, seed = 20261109).
- AI-assisted language-editing tools were used solely to improve English readability after the scientific content was fixed; the author takes full responsibility for the manuscript.

**Suggested reviewer profile.** Reviewers with expertise in (a) robotic end-of-arm tooling and workcell integration, (b) manufacturing systems integration and standards (ISO 9409-1, UR+, OnRobot, Robotiq coupling ecosystems), and (c) measurement / audit methods on engineering corpora. The axiomatic proposition P1 is short and self-contained; a reviewer comfortable with counting arguments can check it line-by-line.

Thank you for considering the manuscript. I am glad to supply the archived scripts, the full provenance register, or any worked example a reviewer requests.

Yours sincerely,

**Xing Li**
Senior Engineer
Zhejiang Academy of Building Research & Design Co., Ltd.
ORCID 0009-0004-2152-7669
463102527@qq.com
