# Topic Justification and Outline — EN

**Working title:** How Compatible Is "Compatible"? A Four-Level Decidability Ladder and a Taxonomy of Zeros for Robot End-Arm Interfaces
**Target journal:** Robotics and Computer-Integrated Manufacturing (Elsevier, ISSN 0736-5845), subscription route, no APC.
**Author:** Xing Li
**Companion files:** `00_Spec/spec.md` (writing standard), `00_Spec/FROZEN_NUMBERS.json` (single numeric source).

---

## Part A — Topic justification

### A.1 Why this problem, and why now

Reconfigurable manufacturing assumes that end-of-arm tooling can move between hosts. In practice the question "will these two parts work together" is answered by whoever sold the parts, not by the parts themselves. Every re-tooling decision therefore starts with a manual search through PDFs, and the search ends with a person concluding "probably" or "ask the vendor". The literature has named this gap for at least a decade (Tola et al. 2022 call out six challenge classes and state plainly that no mature public robot system configurators exist), but the gap has been treated as an engineering-information problem: build a better model, populate it, and matching becomes decidable.

This paper tests that assumption directly, on a catalogue large enough to measure (656 composable nodes, 214,840 unordered pairs, 329 manufacturers), and finds the opposite: decidability is not a property of the model but of the evidential threshold applied to it. Holding the corpus fixed and varying only the threshold moves the electrical answer across five orders of magnitude (64.764% → 0.00512% → 0.00372% → 0.00047%). The gap is therefore not solved by better modelling; it is reproduced by it, because the model has no requirement that a declared port mean anything.

### A.2 The gap, stated so it can be attacked

Three separate literatures stop short of this question:

1. **Hardware information models** (HRIM being the most cited) model *messages*, not *mating surfaces*. HRIM's full tree contains 21 class models, 3 instance-level datasheets, 0 mechanical mating fields and 0 connector-level electrical fields; its `gripper.xml` is literally a message module. A model that describes topics cannot decide whether two flanges bolt together.
2. **Commercial ecosystems** (UR+ being the largest for this class of hardware) list products, not interfaces: 528 products with four filters (Category / Applications / Product Type / Compatibility / Region) and 0 interface fields.
3. **Constraint-based configuration** supplies the right formalism (three-valued and partial constraint satisfaction, placeholder variables) but assumes the constraints are *known*; it has nothing to say about a corpus in which 95.48% of the electrical ports carry the placeholder type `ELEC:UNKNOWN`.

Nobody has measured the size of the gap, and nobody has separated the part of it that evidence can close from the part that it cannot. That is the contribution.

### A.3 Positioning sentence (to be reproduced near-verbatim in Abstract and §1)

Prior work treats interface compatibility as a **decision problem** — give the description and the answer follows. We show it is a **measurement problem** — the decision rate is a function of the evidential threshold, and spans five orders of magnitude — and we give the zero a **structural upper bound** that no amount of additional evidence can move.

### A.4 Five contributions (order fixed)

| # | Contribution | Strongest number |
|---|---|---|
| 1 | Four-level decidability ladder; the drop is 5 orders of magnitude, and the mechanism is placeholder self-matching | 139,139 → 11 → 8 → 1; 528/553 ports are `ELEC:UNKNOWN`; 99.992% of D0 is UNKNOWN×UNKNOWN |
| 2 | The electrical axis is the weakest axis under every definition (stated per stratum, never as one sentence) | 0.0796% [0.0069%, 0.268%] vs mechanical 0.1373%–1.5081%; 17–230× at point estimate |
| 3 | Taxonomy of zeros Z1–Z5 with a removability verdict per class | Z1+Z5 = 297/360 = 82.5% irreducible |
| 4 | Proposition P1 (port budget) with C1–C3 | p(UR3e) = p(UR5e) = 1 ⟹ any k ≥ 2 unsatisfiable |
| 5 | The flange is a suite attribute, not a device attribute | one Robotiq gripper reaches three flange designations |

### A.5 Why RCIM

The paper is about integration decisions in reconfigurable manufacturing: which tool goes on which robot, at what evidential price, and which part of the answer is design-fixed. That is RCIM's scope. It is also squarely a manufacturing-systems measurement paper rather than a standards paper, which is why the framing is "what a plant can decide today", not "what a standard should say".

### A.6 Anticipated rejection risk and mitigation (built into the manuscript, not hidden)

| Risk | Mitigation in text |
|---|---|
| "One catalogue, not a survey" | §3 states the corpus is an audited catalogue; §9 limits every extrapolation; CI reported, not hidden |
| "Wide CIs make the numbers useless" | §5 argues the width is the honest uncertainty at 329 manufacturer clusters, and shows the *ordering* of axes survives it |
| "D3 = 1 pair is anecdotal" | §4 and §9 state D3 is a lower bound on true mating, not an upper bound |
| "P1 is trivial" | §7 gives the proof, then shows why the triviality is the point: the industry built a one-slot tool interface and then wrote compatibility documents as if slots were unlimited |
| "Why not recompute on external parts?" | §2.3 reports the attempt and its result: external corpora supply 3 instance datasheets and 0 interface fields — itself the third independent evidence |

---

## Part B — Section outline (EN manuscript, ~9,000–10,500 words)

### Abstract (250–300 words)
Background one sentence (re-tooling decisions are made without machine-readable interfaces). Method one sentence (656 nodes, 214,840 pairs, four thresholds). Four numbers of the ladder. The mechanism (528/553 placeholder ports). The zero result (Z1+Z5 = 82.5% irreducible) and P1 (p = 1). One closing limitation clause.

### 1. Introduction (1,100–1,400)
- 1.1 The decision a plant actually makes: one paragraph, concrete (mounting a gripper and a force sensor on the same UR5e).
- 1.2 What the field has built: information models, marketplaces, configuration formalisms — one paragraph each, ending with the sentence that none of them answers "how much of this is decidable".
- 1.3 The measurement turn: the ladder in one sentence, with the four numbers; the promise that the drop is mechanical, not rhetorical.
- 1.4 Contributions (five, as table A.4), scope of claims, and the positioning sentence.
- 1.5 Paper organisation (one short paragraph).

### 2. Related Work and Positioning (1,200–1,500)
- 2.1 System configuration and interface modelling — Tola et al. 2022 first (six challenge classes A–G; "no mature public robot system configurators exist"), then Tola 2401.02227, Siltala IPAS 2019, Zheng RCIM 2019, Chaumet et al.
- 2.2 Hardware information models — HRIM (Zamalloa et al., arXiv 1802.01459): 21 class models / 3 instance datasheets / 0 mechanical mating fields / 0 connector-level electrical fields; the `gripper.xml` verbatim line. Then ISO 9409-1 as a mechanical-only standard.
- 2.3 Marketplaces as de-facto interface catalogues — UR+ 528 products, 0/528 interface fields; why this is evidence rather than anecdote.
- 2.4 Incomplete and partial constraint reasoning — Sabin & Freuder 1996, Ciucci & Dubois, Mittal & Falkenhainer AAAI-90, ConfWS 2024. What these give us (the vocabulary of unknown/placeholder) and what they assume (known constraints).
- 2.5 What is missing: no measurement of decidability, no taxonomy of zeros, no structural bound. Positioning sentence closes the section.

### 3. Corpus, Isolation and Provenance (1,000–1,300)
- 3.1 The catalogue: 868 entities, 656 composable nodes, 214,840 unordered pairs, 329 manufacturers.
- 3.2 Isolation: 22 generic placeholders removed → 634 nodes, 200,661 pairs (denominator shrinks 6.6% while 35 parts are the actual completion target).
- 3.3 Port inventory: 553 electrical ports, 17 distinct type ids, 528 `ELEC:UNKNOWN` (95.48%), declared 25 / not_declared 528, 6 nodes with more than one declared port.
- 3.4 Provenance and the three-tier tagging (V/O/E), with the honest statement that the numbers come from scripts run on this corpus (rp_b24.py / rp_b2v2.py / rp_ladder.py), not from a re-run inside this paper.
- 3.5 PRISMA-ScR pointer: search strings, dates, screening counts and exclusion reasons are in the accompanying search log.
- Table 1 (corpus and port counters, ≥10 rows).

### 4. The Four-Level Decidability Ladder (1,500–1,800)
- 4.1 Four thresholds defined exactly (D0 type label identical including placeholder; D1 identical designation excluding UNKNOWN; D2 engine verdict requiring type + pin order + gender; D3 manual locus correction to device-to-device mating). One paragraph each, with the exact operational test.
- 4.2 The measurement: 139,139 (64.764%), 11 (0.00512%), 8 (0.00372%), 1 (0.00047%); ratios 12,650×, 1.4×, 139,000×.
- 4.3 The mechanism: 139,128 of 139,139 are UNKNOWN×UNKNOWN (99.992%), i.e. the top of the ladder is a placeholder matching itself. Give the combinatorial intuition (C(528,2)-scale self-collision).
- 4.4 What the 11 surviving pairs are: the table of 11 with shared tokens; explain the Robotiq duplicate entity and the three cable-end tokens. This is where the reader learns that even D1 is mostly not what it looks like.
- 4.5 From 8 to 1: the connector-locus audit (19 nodes: device 4, adapter 3, host 3, cable 7, one node both host and adapter), and the finding that no end effector or sensor in the audited set owns a true device-side port.
- 4.6 Interpretation: any single reported "compatibility rate" has implicitly chosen a rung; the choice is worth five orders of magnitude.
- Table 2 (ladder), Table 3 (11 pairs), Fig 1.

### 5. Cross-Axis Comparison and the Weakest Axis (1,100–1,400)
- 5.1 Five definitions on three axes, with n and point estimates (295/0.1373%, 2,211/1.0291%, 3,240/1.5081%, 171/0.0796%, 77,815/36.220%).
- 5.2 Cluster bootstrap: B = 1000, seed 20261109, 329 manufacturer clusters; CIs as frozen. Why whole-cluster resampling and why the CIs are this wide (many single-part manufacturers contribute ~0 pairs).
- 5.3 The per-stratum statement of the weakest axis: mechanical point estimates span 11× across definitions and never exceed 5% at the CI upper bound; electrical stays below 0.268% at the CI upper bound; hence electrical is the weakest axis in every stratum — and the sentence that must not be written ("electrical is always lower than mechanical") is explicitly refused, because the mechanical lower bound 0.0132% overlaps the electrical upper bound 0.268%.
- 5.4 Deduplication sensitivity: 645 nodes / 207,690 pairs; 295 → 294; D2 unchanged at 8; magnitude shifts below 4%, qualitative conclusions unchanged.
- 5.5 What the axis ordering implies for data collection budgets: the axis a plant should instrument first is the one whose density is lowest per unit of evidence.
- Table 4, Fig 2.

### 6. A Taxonomy of Zeros (1,300–1,600)
- 6.1 The object being classified: 360 pair evaluations, 3 hosts, 16 devices, `mountable = 0`.
- 6.2 Z1 port exhaustion (126 pairs; 240 stage-blocked events). Z2 type mismatch (distributed inside the 171 type_error pairs). Z3 device-side undeclared (528 ports; 63 unknown pairs). Z4 host-side undeclared (FR3 route only, p = null; a subset of the 63). Z5 role not complementary (171 pairs).
- 6.3 Removability: Z1 and Z5 are design and requirement constraints, not evidence gaps; Z3 and Z4 are evidence gaps. Z1+Z5 = 297/360 = 82.5%. State the arithmetic and the boundary of the claim.
- 6.4 Why the classification matters beyond this corpus: it tells an integrator where to spend the next hour (complete Z3/Z4) and what spending it cannot buy (Z1).
- 6.5 The single-mount case: mountable 32, unknown 16 at k = 1 — the zero is specifically a co-mount zero, not a mounting zero. This resolves the apparent contradiction between 32 and 0.
- Table 5, Fig 3.

### 7. Port Budget: An Upper Bound on Co-Mounting (900–1,200)
- 7.1 Definitions: p(h), independent power, independent addressing, slot, bus sharing with m stations.
- 7.2 Proposition P1 and proof: each device needs independent power and an independent address; one physical connector slot carries one physical channel; two devices cannot share one slot. With bus sharing, k ≤ p(h)·m.
- 7.3 Corollary C1: UR3e and UR5e both expose p = 1 (M8 8-pin, 8 pins, 1 slot), so any k ≥ 2 question is unsatisfiable regardless of both sides' declaration completeness. C2: completing Z3/Z4 moves unknown to compatible or incompatible and cannot change Z1. C3: FR3 leaves p undeclared, so its unknown pairs belong to Z4 and must not be merged into Z1.
- 7.4 The pin-versus-bit discipline: 8 is a pin count; the channel count is 1. Treating pins as bits lets an engine report eight simultaneously mountable tools on a host that can serve one.
- 7.5 Consequence for the field: compatibility documentation for co-mounting is not merely incomplete, it is answering a question the hardware cannot host.

### 8. The Flange as a Suite Attribute (800–1,000)
- 8.1 Three vendor cases: Robotiq (31.5-4-M5 / 40-4-M6 / 50-4-M6 via coupling kits; 3-Finger only 40-4-M6), OnRobot (device carries no flange; Quick Changer robot side is ISO 9409-1-50-4-M6), ATI Axia (71.12 mm bolt circle, 6 × M5, no ISO designation).
- 8.2 Consequence: "mechanically decidable" pairs in the catalogue are largely *suite-specification identity*, not device interchangeability. This explains why the mechanical axis can be decidable and still produce no mountable pair.
- 8.3 Cross-generation: UR8 Long / 15 / 18 = ISO 9409-1-50-4-M6; UR20 / 30 = ISO 9409-1-80-6-M8; the official adapter converts mechanics only and caps payload at 20 kg. Compatibility here is not binary: mechanically convertible, electrically not, at a quantified payload cost.
- 8.4 What a device-level identity judgement would require (hole geometry, dowel positions, load path) — and why the catalogue does not have it.

### 9. Discussion: What Would Change the Answer (1,000–1,300)
- 9.1 The optimistic completion bound: complete all 35 class-A parts; at most C(35,2) = 595 pairs among them plus 35 × 19 = 665 pairs against every already-declared node, giving at most 1,268 pairs, 0.590% of 214,840 (0.632% of 200,661). Below 1% even in the most favourable case. Recomputation in `04_ResearchData/Scripts/rp_upper_bound.py`.
- 9.2 What should *not* be completed: the 44 body-mounted or surface-mounted parts (RealSense cameras, visuotactile and electronic skins, LiDAR/IMU/event cameras) must not receive flange declarations; the keyword rule and manual adjudication disagree at κ = 0.6236 (agreement 74.26%, 26 flips), which is why the real target is 35 parts, not 101.
- 9.3 Honest limits (all five, in order): catalogue not census; cluster CIs; rule-versus-human κ; three hosts; D3 as a lower bound.
- 9.4 What would move the answer: a device-side port census (the only channel that can raise D3), a host-side port-budget field (which would convert Z1 from blocked to tagged), and a mandatory connector-locus field in catalogue schemas.
- 9.5 Transferability: the ladder is a measurement protocol, not a claim about one database; any catalogue with declared and placeholder ports can be run through the same four thresholds.

### 10. Conclusion (300–450)
Three sentences of substance: the ladder (measurement, not decision), the taxonomy (82.5% irreducible), the bound (k ≤ p(h)). One sentence on what practitioners should stop doing (reporting a single compatibility rate). No repetition of the abstract wording.

### References
28–40 entries, numbered, every entry with DOI or URL, per `04_ResearchData/references_verified.md`.

### Declarations
Funding: none. Competing interests: none. Data availability: the corpus is an audited catalogue available from the corresponding author on reasonable request; all derived tables, bootstrap outputs and recomputation scripts are supplied in the accompanying research-data package.

---

## Part C — Table and figure schedule

| Item | Content | Rows |
|---|---|---|
| Table 1 | Corpus and port counters | ≥10 |
| Table 2 | Four-level ladder (D0–D3) | 4 |
| Table 3 | The 11 D1 pairs with shared tokens | 11 |
| Table 4 | Five definitions with point estimate and 95% CI | 5 |
| Table 5 | Zero taxonomy Z1–Z5 with removability | 5 |
| Table 6 | Upper-bound recomputation, step by step | ≥6 |
| Fig 1 | Ladder waterfall on log axis, with ratios | — |
| Fig 2 | Forest plot of five definitions, electrical row highlighted | — |
| Fig 3 | Zero taxonomy stack + k=1 vs k = 2 panel | — |
