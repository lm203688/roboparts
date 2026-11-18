# Cover Letter

**To:** The Editors-in-Chief
**Re:** Submission of the manuscript "How Compatible Is 'Compatible'? A Four-Level Decidability Ladder and a Taxonomy of Zeros for Robot End-Arm Interfaces"

Dear Editors,

We submit our manuscript for consideration as a research article. The study asks a prior question before the usual robot-configurator work: given a fixed population of 656 composable robot-end-arm nodes (214,840 unordered pairs, 329 vendors), how often is a compatibility *decidable* — and how does that rate move when we tighten the evidence rule?

Three findings define the paper.

First, the decidable electrical share falls from 64.764% to 0.00047% across four nested evidence thresholds — five orders of magnitude — and the mechanism is measurable: 528 of 553 electrical ports (95.48%) are the placeholder type `ELEC:UNKNOWN`, and 99.992% of the loosest-level pairs are placeholder-self-collisions. A single "compatibility rate" reported without its threshold is silently choosing among five orders of magnitude.

Second, on a 360-pair co-mount layer where zero configurations are mountable, we classify every zero into five types (Z1–Z5) and prove an upper-bound proposition: a host with p(h) independently-powered, independently-addressed tool-side positions can co-mount at most p(h) devices. Because the UR3e and UR5e each expose exactly one position, any two-device co-mount is structurally unsatisfiable regardless of data completeness; 82.5% of the evaluated zeros are of this structural kind and cannot be removed by filling evidence.

Third, two independent external objects tell the same story: the canonical HRIM information model (21 class models, 3 instance datasheets) carries zero mechanical-mating fields and zero connector-level electrical fields, and the 528-product UR+ marketplace page carries zero interface fields. Interface-description absence appears ecosystem-level rather than catalogue-specific.

We believe the contribution suits a readership working on robotics product data, configuration systems, and manufacturing integration, because it changes the expected return of "fill the missing interface data": it shows that a large share of incompatibilities are decided by design (port budget, role non-complementarity), not by evidence.

The manuscript has not been published and is not under consideration elsewhere; it is not part of any other submission currently in review. All computed values are reproducible from a shipped data bundle and scripts. We report our inter-rater reliability (κ = 0.6236, rule-versus-human) and our wide vendor-cluster confidence intervals honestly in the text, together with the other stated threats to validity.

We request to publish under the subscription (non-open-access) model, at no article-processing charge, consistent with the journal's hybrid policy.

Thank you for your consideration.

Sincerely,
Xing Li (Senior Engineer)
Zhejiang Academy of Building Research & Design Co., Ltd.
ORCID 0009-0004-2152-7669 · 463102527@qq.com
