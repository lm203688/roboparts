# 00 · Frozen Writing Specification (RoboParts Decidability Ladder)

> Frozen 2026-11-09. This file is the single source of truth for numbers, claims, and wording discipline.
> Every downstream artifact (EN/CN manuscript, tables, figures, submission pack) must match this file verbatim.
> Provenance tags: **[V]** = verified against primary source / file record; **[O]** = official or secondary account not word-verified; **[E]** = computed in this study, reproducible.

## 1. Title (selected)

**How Compatible Is "Compatible"? A Four-Level Decidability Ladder and a Taxonomy of Zeros for Robot End-Arm Interfaces**

Alternates held in reserve (not used in this submission):
- B: *Port Budget, Not Data Quality: Why Co-Mounting Robotic End Effectors Is Structurally Unavailable*
- C: *What Nobody Declares: Interface Description Gaps Across a 656-Node Catalogue, a 21-Model Standard, and a 528-Product Marketplace*

## 2. Author block (frozen)

- Xing Li (李星)
- Affiliation: Zhejiang Academy of Building Research & Design Co., Ltd. (浙江省建筑科学设计研究院有限公司) — **legal full name pending user confirmation against business license; listed as open item in PRISMA §7.**
- ORCID: 0009-0004-2152-7669
- Email: 463102527@qq.com
- Title Page position: Senior Engineer
- **RED LINE: no "Academician / Ukrainian / 外籍院士 / 乌克兰" anywhere in any artifact.** Identity appears only as Senior Engineer.

## 3. Frozen numbers (do not round, do not add)

Corpus: entities 868; composable nodes 656; unordered pairs 214,840; vendors (deduped among composable nodes with a manufacturer field) 329. After isolating 22 placeholder nodes: 634 nodes / 200,661 pairs. [E]

Electrical ports: 553 total, 17 distinct type ids, of which **ELEC:UNKNOWN = 528 (95.48%)**; status declared 25 / not_declared 528; nodes carrying more than one declared electrical port = 6. [E]

Four-level ladder (same 656 nodes, 214,840 pairs; only the evidence threshold changes):

| Level | Criterion | Pairs | Share of 214,840 |
|---|---|---|---|
| D0 | port type label equal (placeholders included) | 139,139 | 64.764% |
| D1 | label equal after excluding ELEC:UNKNOWN | 11 | 0.00512% |
| D2 | engine pairing verdict (type + pin order + gender present) | 8 | 0.00372% |
| D3 | manual locus correction to true device-to-device mating | 1 | 0.00047% |

Within D0, **139,128 pairs (99.992%) are UNKNOWN × UNKNOWN** (≈ C(528,2) placeholder self-collisions). [E]

The 11 D1 pairs, enumerated: ACT-001×ACT-002 (JST-EHR-03); ACT-028×GRIP-002, ACT-028×GRIP-006, GRIP-002×GRIP-006 (Robotiq 10-SPRING-PIN and DEVICE-CABLE-5-POLE-M8 each collide twice, same 2F-85 duplicate entity + shared coupler); GRIP-012×GRIP-014 (UR-TOOL-CONNECTOR-COMPOSITE, contending for the same host port); SENS-047×SENS-37 (12-PIN-ROUND-AMPHENOL, cable end); SENS-049×SENS-854 (M8-5-PIN-SENSOR-CABLE, cable end); SENS-031×SENS-855 (M12-5-PIN-A-CODED-IEC-61076-2-101, cable end). [E]

Three-axis + whole-vendor bootstrap (B=1000, seed=20261109, 329 vendors resampled as clusters; point estimate and 95% CI):

| Axis / definition | Pairs | Point | 95% CI | Cross-vendor share |
|---|---|---|---|---|
| Mech · same flange label | 295 | 0.1373% | [0.0132%, 0.573%] | 76.61% |
| Mech · both ends declared | 2,211 | 1.0291% | [0.160%, 2.959%] | 86.88% |
| Mech · both ends loose | 3,240 | 1.5081% | [0.368%, 4.205%] | 90.37% |
| Elec · both ends declared | 171 | 0.0796% | [0.0069%, 0.268%] | 85.96% |
| Signal · both ends declared | 77,815 | 36.220% | [26.18%, 45.57%] | 97.3% |

Dedup sensitivity (name-normalized, 645 nodes / 207,690 pairs): mech same-flange 295→294; D2 8 pairs unchanged; qualitative conclusion unchanged, magnitude change <4%. [E]

Co-mount layer (co_mount_engine/v1): hosts 3 (UR3e HUB-030, UR5e HUB-031, Franka Research 3 SUPERDEX-fr3), devices 16, pair_evaluations 360, **mountable = 0**; verdicts type_error 171 / port_exhausted 126 / unknown 63; stage blockers port_budget=exhausted 240, signal_complementary=not_complementary 171, port_budget=unknown 120; single_mount mountable 32 (one device can hang) / unknown 16. [E]

Host tool side (robot_tool_side.json): UR3e and UR5e both `tool_flange=MECH:ISO9409-1-A50-4-M6`, **tool_io_ports=1**, connector "M8 8-pin", pins 8, signals ["24V","GND","2x DO","2x DI","2x AI/RS485"], source_tier A, confidence 0.85; FR3 `tool_io_ports=null` (deliberately blank; datasheet says only "end effector connector"), signals ["2x DI","2x DO (24V, isolated, EN 61131-2 type 3)"], tier B, confidence 0.95. **Discipline: 8 is pin count, not bit count; bits = 1. Treating pins as bits makes the engine believe 8 tools can hang at once.** [V]

B1 locus (19 declared-electrical nodes, audited one by one): device 4 (ACT-001/002 JST EHR-03, ACT-003 EHR-04, ACT-016 A1257WR-S-3P+XT30PW-M, all actuator buses); adapter 3 (Robotiq 2F-85/Hand-E 10-spring-pin on their coupler); host 3 (Robotiq EPick, OnRobot VGC10 write "plug into robot tool connector"; OnRobot RG2 mixed); cable 7 (ATI 12-pin Amphenol, OnRobot HEX M8, Robotiq FT 300 M12, all cable ends); GRIP-007 simultaneously host+adapter. **No end effector and no sensor carries a true device-side port.** Of the 8 engine-"decidable" pairs, after locus re-adjudication only ACT-001×ACT-002 remains a true device-to-device mating (DYNAMIXEL TTL bus, daisy-chainable). [V]

B2 triage (101 EOAT mechanical not_declared, adjudicated one by one; 121 composable EOAT = grippers 26 + sensors 95): A flange-bearing 35 (grippers 15 incl. 4 dexterous hands + six-axis F/T 20); B body/clip-mounted 44 (RealSense cameras 5, tactile/electronic skin such as GelSight/DIGIT/TacTip/uSkin/TSF-85, LiDAR/IMU/event cameras, whole-unit perception kits); C generic placeholders 22 (SENS-001~005, 008, 009, 13~27 etc., no model or fake vendor string). Real products 79, placeholders 22, empty vendor field 32. **Coding agreement: keyword rule vs. manual adjudication, κ=0.6236, agreement 74.26%, 26 flips** (below the 0.75 threshold); therefore "fill in all 101" is a pseudo-requirement — the real backlog is 35. [E]

B3 external catalogs: HRIM repo `AcutronicRobotics/HRIM` (Apache-2.0, archived, last push 2019-08-07, 71 stars), full-tree census → class models 21 (actuator 3 / composite 3 / power 1 / sensor 14), **instance-level datasheets only 3** (hans_rotaryservo, robotiq_gripper_finger, xtion_depthsensor), **mechanical mating fields 0**, **connector-level electrical fields 0**; `models/actuator/gripper/gripper.xml` reads verbatim `<module name="gripper" type="actuator" description="defines the messages to interact with grippers">` and everything includes `topics/*.xml` ⇒ it is a **communication information model, not an assembly information model**. UR+ marketplace `universal-robots.com/plus/products/` shows **528 products**, filters only Category/Applications/Product Type/Compatibility/Region, **interface fields 0/528**. Conclusion: "take 50 external parts and recompute" is not executable; this is itself a third independent evidence (interface-description absence is ecosystem-level). [V]

B1 four closed loops (verbatim quotes available in the audit report):
1. OnRobot 2FG7 goes host-side via Quick Changer; 2FGP20 manual states "supported in the operation mode via tool connector: 2FG7, 2FGP20"; the "ETHERNET" in the declared name is a communication protocol, not a connector type.
2. HEX-E manual Scope of Delivery: "sensor cable (4 pin M8 - 4 pin M8, 5 m)" ⇒ the database's 5-pin is wrong, it is 4-pin M8; HEX-E QC manual: "For RG2-FT the Quick Changer tool data connector cannot be used. Instead use the marked M8-4pin connector".
3. ATI 9610-05: "This model has an 8-pin M8 connector on the sensor. All other Axia80 models have a 6-pin M8 connector." ⇒ body is 6-pin M8 (some models 8-pin), 8-pin M12 is at the other end of the cable (part 9105-C-ZC22-ZC28-4).
4. UR official: "UR20/30 Tool Flange Adapter — Official tool flange adapter to convert the UR20/UR30 layout to EN ISO 9409-1-50-4-M6 (e-Series layout). Maximum rated payload 20 kg." UR8 Long/15/18 = ISO 9409-1-50-4-M6; UR20/30 = ISO 9409-1-80-6-M8 ⇒ the "UR tool connector de facto standard" holds only within a generation; cross-generation needs an adapter that converts mechanics only, not electricals, and clamps payload to 20 kg.

Flange-as-kit property (empirical support for contribution 5): the same Robotiq gripper, via universal connection kit, mates to both 31.5-4-M5 and 40-4-M6; via the UR-specific coupler it is 50-4-M6; 3-Finger is 40-4-M6 only. OnRobot devices themselves write no flange — they write "mount to Quick Changer"; the Quick Changer robot side is ISO 9409-1-50-4-M6. ATI Axia mounting side is 71.12 mm bolt circle, 6×M5, no ISO label ⇒ the "mechanical axis decidable 2,016 pairs" is materially **kit-spec equality**, not device interchangeability. [V]

## 4. Five contributions (order fixed)

1. A four-level decidability ladder with a 5-order-of-magnitude drop; mechanism = placeholder-port self-matching (528/553).
2. The weakest axis: under every definition the electrical axis sits 1–3 orders of magnitude below the mechanical axis (must be stated stratified, because mechanical lower CI 0.0132% and electrical upper CI 0.268% overlap; one-sentence generalization is forbidden).
3. A taxonomy of zeros Z1–Z5 and the bound Z1+Z5 = 297/360 = 82.5% not eliminable by evidence filling.
4. Proposition P1 (port-budget upper bound) with proof and corollaries C1–C3.
5. Flange is a kit property, not a device property.

## 5. Proposition P1 (frozen statement and proof)

**P1 (port-budget upper bound).** Let host h carry p(h) connector positions on its tool side that are independently powered and independently addressable. A device d that does not borrow external independent power or a bus occupies 1 position. Then the number k of independent devices co-mounted on h satisfies **k ≤ p(h)**.

*Proof.* Every device requires independent power-up and independent addressing. One physical connector position provides exactly one physical channel; two devices cannot share the same physical connector. If bus sharing is allowed (e.g., a DYNAMIXEL daisy chain), then k ≤ p(h)·m where m is the maximum node count on that bus.

- **C1.** UR3e/UR5e have p=1 ⇒ any k≥2 co-mount problem is unsatisfiable, independently of how complete the declarations on either side are.
- **C2 (monotonic invariance of evidence).** Filling Z3/Z4 can only turn unknown into compatible or incompatible; it does not change the satisfiability of Z1. Hence "fill the data and the system unlocks" is logically false.
- **C3.** FR3's p is undeclared ⇒ its unknowns belong to Z4; they are undecidable before evidence is supplied and must not be merged into Z1 (this corrects the v2 misjudgment).

## 6. Wording discipline (red lines)

- Forbidden hype words in any language: unlock, breakthrough, first proof, game-changing, "首次证明可测", "解锁", "突破". Allowed: "we measured", "we prove an upper bound", "holds under condition X".
- Positioning sentence (frozen): *Prior work treats compatibility as a **decision problem** (given a description, it is decidable); this study shows it is a **measurement problem** (the decision rate itself is a function of the evidence threshold, varying by five orders of magnitude), and gives a **structural upper bound on zeros**.*
- Tola et al. 2022 must be the first cited position paper; the verbatim quote "no mature public robot system configurators exist" must appear with the PDF link.
- No fabricated DOI. Every reference must carry a working URL or DOI; arXiv preprints are labeled preprint, not "formally published".

## 7. Fee policy (zero APC)

Only subscription route or no-APC path is permitted. Elsevier official position (verified 2026-11-09, https://www.elsevier.com/about/policies-and-standards/pricing): journals operate two models; subscription articles are funded by reading subscriptions and carry no APC. Authors may choose the subscription model at no cost in hybrid journals. Per-journal fee-page verification status is recorded in 03_Submission/Submission_Guide_Fee_Verification.md; any page blocked by robots.txt/WAF is recorded NOT_VERIFIED with a 30-second manual re-check path, never with an unverified number.

## 8. Honest boundaries (must appear in the manuscript)

1. The sample is an audited catalogue, not a market census (656 nodes, 329 vendors).
2. Bootstrap clusters by vendor; CIs are wide and external inference must be bounded.
3. B2's κ=0.6236 is "rule vs. human", not "two humans"; report and discuss honestly.
4. Numbers come from three hosts in a single catalogue; host-side conclusions hold only for UR3e/UR5e/FR3.
5. Of the 19 electrical-declared nodes, device-side ports are extremely scarce; D3's single pair is a lower bound on "true mating", not an upper bound.
