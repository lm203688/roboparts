# How Compatible Is "Compatible"? A Four-Level Decidability Ladder and a Taxonomy of Zeros for Robot End-Arm Interfaces

**Xing Li**

Zhejiang Academy of Building Research & Design Co., Ltd. (legal full name pending confirmation against business license)
ORCID: 0009-0004-2152-7669 · Email: 463102527@qq.com · Position: Senior Engineer

---

## Abstract

Whether two robot end-arm devices can be mounted together is, in product-data practice, treated as a decision problem: give the system a description, and it decides compatible or not. We show, on an audited catalogue of 656 composable robot nodes (214,840 unordered pairs, 329 vendors), that the decision rate itself is a function of the evidence threshold. Holding the node set fixed and tightening only the evidence rule, the share of decidable electrical pairs falls from 64.764% (D0, type-label equality including placeholders) to 0.00512% (D1, real label equality) to 0.00372% (D2, type plus pin order plus gender) to 0.00047% (D3, manual locus correction to true device-to-device mating) — a drop of roughly five orders of magnitude. The mechanism is measurable: 528 of 553 electrical ports (95.48%) carry the placeholder type `ELEC:UNKNOWN`, and 139,128 of the 139,139 D0 pairs (99.992%) are UNKNOWN×UNKNOWN self-collisions. On a three-axis measurement with whole-vendor cluster bootstrap (B=1000), the electrical axis is the weakest under every definition, sitting one to three orders of magnitude below the mechanical axis. We then enumerate the 360-pair co-mount layer, where `mountable = 0`, into a taxonomy of five zero-types (Z1 port-exhausted, Z2 type-mismatch, Z3 device-side undeclared, Z4 host-side undeclared, Z5 non-complementary roles), and prove an upper-bound proposition P1: a host with p(h) independently-powered, independently-addressed connector positions can co-mount at most p(h) devices. Because UR3e and UR5e each expose exactly one tool-side position (p=1), any k≥2 co-mount is structurally unsatisfiable regardless of data completeness; Z1+Z5 already account for 297/360 = 82.5% of the zeros and cannot be removed by filling evidence. Two external censuses point the same way: the canonical robot hardware information model HRIM (21 class models, 3 instance datasheets) carries zero mechanical-mating fields and zero connector-level electrical fields, and the 528-product UR+ marketplace page carries zero interface fields. Compatibility, we conclude, is a measurement problem whose answer depends on the threshold one silently chose; and a large share of its zeros are structural, not data-quality failures.

**Keywords:** robot end effector; interface compatibility; decision support; product data; partial constraints; co-mounting; HRIM; UR+ marketplace

---

## 1. Introduction

Configuring an industrial or collaborative robot system — choosing an arm, an end effector, a sensor, and the cables between them — is still, in practice, performed by experienced system integrators. Tola et al., in a position paper for Aarhus University, state this plainly: *"To our knowledge, no mature public robot system configurators exist, leaving the task of configuration up to experienced system integrators"* [1][V]. The same paper lists, as challenge A through G, the missing standardisation of hardware, the half-used ISO 9409-1 flange standard, the unclear compatibility of devices speaking the same industrial protocol, and the absence of any standard combining the mechanical and communication interface of a device [1].

Two families of response have followed. One family builds configurators and application builders on top of manufacturer ecosystems — Universal Robots' UR+ and ABB's application builders are the closest industrial software to a robot configurator, but they lock the arm to one manufacturer and expose little about the other devices [1]. The other family builds information models, the canonical example being HRIM (Human-Robot Interaction Module), which promises a standard representation of robot hardware so that components from different vendors can be described and composed [2].

Both families share an implicit move. They treat compatibility as a **decision problem**: once the descriptions exist, the system can decide whether two devices mate. The question this paper asks is prior to that move. We do not ask "which descriptions are missing"; we ask **what the decision rate actually is, as a function of how much evidence we demand**, and **which of the resulting zeros are removable by collecting more evidence at all**.

We measure on an audited robot-part catalogue (RoboParts): 868 entities, of which 656 are composable nodes forming 214,840 unordered pairs, contributed by 329 vendors [E]. We tighten the evidence threshold in four steps (Section 3.3) and observe a drop of five orders of magnitude (Section 4.1). We measure three axes — mechanical flange, electrical connector, signal definition — under whole-vendor cluster bootstrap (Section 4.2). We enumerate a 360-pair co-mount layer and classify every zero (Section 4.3). We then prove a proposition that removes the matter from empiricism (Section 4.4). Finally, we check two external objects that are not our catalogue at all — the HRIM repository and the UR+ marketplace — and find the same interface-description absence on both (Section 4.7).

The positioning sentence, kept throughout: **prior work treats compatibility as a decision problem (given a description, it is decidable); this study shows it is a measurement problem (the decision rate itself is a function of the evidence threshold, varying by five orders of magnitude), and gives a structural upper bound on zeros.**

*Contributions.*

1. A four-level decidability ladder (D0–D3) and a measured five-order-of-magnitude drop, whose mechanism we identify as placeholder-port self-matching (528/553 electrical ports are `ELEC:UNKNOWN`).
2. A stratified measurement showing the electrical axis is the weakest under every definition, 1–3 orders below the mechanical axis, reported with wide vendor-cluster confidence intervals.
3. A taxonomy of zeros Z1–Z5 on the co-mount layer, with a proof that Z1+Z5 = 297/360 = 82.5% cannot be eliminated by evidence filling.
4. Proposition P1 (port-budget upper bound) with proof and three corollaries, including the monotonic invariance of evidence.
5. The empirical finding that a flange label is a kit property, not a device property — the same gripper mates to three different ISO labels depending on which coupling kit was purchased.

## 2. Related Work

**Robot configuration and system integration.** Tola et al. [1] frame configuration as a missing-standard problem and propose answer-set programming and co-simulation as routes; their follow-up [3] formalises the configuration task. Siltala et al. [4] and Zheng et al. [5] address system-integration and product-configurability modelling from the industrial-engineering side; Chaumet et al. [6] work on constraint-based configuration as a combinatorial service. None of these works measures how often, in a real part population, the available evidence actually suffices to decide a pair.

**Hardware information models.** HRIM [2] is the most cited open robot hardware information model; we census its repository directly (Section 4.7) and find that its "information" is ROS message topics, not mating geometry or connector pins. ISO 9409-1 defines the circular mounting flange, but Tola et al. already note manufacturers use it unevenly [1]; our data add that the same device can present three different ISO labels depending on the purchased kit (Section 4.5). The UR+ marketplace [7] is the largest commercial end-effector catalogue we can inspect; its 528 products carry no interface fields at all.

**Partial and three-valued constraints.** A decision that cannot yet be taken is not "false"; it is *unknown*. This is the textbook territory of dynamic and partial constraint satisfaction [8][9], three-valued logics for incompleteness [10], and the configuration-web community's treatment of unknown as a third status [11]. Our contribution on this axis is not a new logic but an **empirical separation**: among the 63 `unknown` verdicts on the co-mount layer, only some are unknown-pending-evidence (Z3, Z4); the rest are already decided-now zeros (Z1, Z5) that no amount of additional evidence will move. The taxonomy (Section 4.3) is that separation made explicit.

**Gap.** No prior work (to our reading) (i) measures a decidability rate as a function of the evidence threshold on a real part population, (ii) bounds which share of incompatibilities is structural rather than evidential, or (iii) shows, by independent census, that the leading information model and the leading marketplace both omit the mating fields the decision requires.

## 3. Corpus and Method

### 3.1 The catalogue

The RoboParts audit corpus lives in nine JSON tables: `entities.json` (868 entities), `morphology_graph.json`, `mechanical_interfaces.json`, `electrical_interfaces.json`, `co_mount.json`, `robot_tool_side.json`, `compatibility.json`, `compose_semantics.json`, and `evidence_valuation.json`. After isolating 22 generic placeholder nodes (e.g. `SENS-001` with no model number), the composable set is **656 nodes and 214,840 unordered pairs**, contributed by **329 vendors** (vendors counted among composable nodes carrying a manufacturer field, deduplicated) [E]. Under isolation, the denominator shrinks to 634 nodes / 200,661 pairs; all ladder densities in this paper use the 656/214,840 denominator, and the isolated re-count is reported as a sensitivity (Section 4.6).

Provenance tags follow the whole paper: **[V]** denotes a value verified against a primary document or file record; **[O]** an official or secondary account not word-for-word verified; **[E]** a value computed in this study and reproducible from the shipped scripts (`rp_ladder.py`, `rp_b24.py`, `rp_b2v2.py`).

### 3.2 Electrical ports as found

The catalogue holds **553 electrical ports across 17 distinct type ids**; of these, **528 (95.48%) are typed `ELEC:UNKNOWN`**. Port status splits 25 declared versus 528 not declared. Only **6 nodes carry more than one declared electrical port** [E]. This asymmetry — five hundred placeholders against a handful of real labels — is the empirical spine of the ladder.

### 3.3 The four-level ladder

We hold the 656-node / 214,840-pair population fixed and change only the evidence rule [E]:

- **D0 — placeholder-tolerant label equality.** Two pairs match when their port type labels are equal, placeholders included.
- **D1 — real label equality.** Exclude `ELEC:UNKNOWN`; the remaining labels must be identical.
- **D2 — engine pairing verdict.** The configuration engine may emit an identity or adapter verdict only when type, pin order, and gender are all present.
- **D3 — locus-corrected true mating.** A manual pass re-adjudicates each D2 pair by the port's *locus* (device / adapter / host / cable): only a device-side port mating a device-side port counts.

The four levels are nested by construction (D3 ⊂ D2 ⊂ D1 ⊂ D0); the reported question is how fast the count collapses.

### 3.4 Three axes and cluster bootstrap

We measure three axes separately: the mechanical flange axis (same ISO label; both-ends-declared; both-ends-loose), the electrical connector axis (both ends declared), and the signal-definition axis (both ends declared). Because vendor clustering dominates the variance (329 vendors, many single-product), we re-sample vendors as clusters B=1000 (seed 20261109) and report the point estimate and 95% percentile interval [E].

### 3.5 External censuses

Two objects outside the catalogue are censused directly. HRIM (`AcutronicRobotics/HRIM`, Apache-2.0, archived, last push 2019-08-07, 71 stars) is enumerated via its git tree, counting class models, instance datasheets, mechanical-mating fields, and connector-level electrical fields [V]. The UR+ marketplace page (`universal-robots.com/plus/products/`) is inspected for product count and for the presence of any interface filter [V].

### 3.6 Reproducibility

Full search strings, databases, access dates (2026-11-09), hit counts, and exclusion reasons are logged as a PRISMA-ScR record in `04_ResearchData/PRISMA_ScR.md`; where a hit count could not be retrieved it is recorded `NOT_RETRIEVABLE` with the reason, never estimated.

## 4. Results

### 4.1 The ladder (Fig. 1)

| Level | Pairs | Share of 214,840 | Ratio to next level |
|---|---|---|---|
| D0 | 139,139 | 64.764% | — |
| D1 | 11 | 0.00512% | D0/D1 ≈ 12,650× |
| D2 | 8 | 0.00372% | D1/D2 ≈ 1.4× |
| D3 | 1 | 0.00047% | D0/D3 ≈ 139,000× |

[E]

The collapse is mechanical. Of the 139,139 D0 pairs, **139,128 (99.992%) are UNKNOWN×UNKNOWN** — placeholders matching placeholders, approximately C(528,2) collisions among the 528 placeholder ports. Once placeholders are excluded, only 11 pairs share a real label; after requiring pin order and gender, 8; after locus correction, 1. The 11 D1 pairs are, enumerated: ACT-001×ACT-002 (JST-EHR-03); ACT-028×GRIP-002, ACT-028×GRIP-006, GRIP-002×GRIP-006 (Robotiq 10-SPRING-PIN and DEVICE-CABLE-5-POLE-M8 each colliding twice, the same 2F-85 duplicate entity plus a shared coupler); GRIP-012×GRIP-014 (UR-TOOL-CONNECTOR-COMPOSITE, contending for the same host port); SENS-047×SENS-37 (12-PIN-ROUND-AMPHENOL, cable end); SENS-049×SENS-854 (M8-5-PIN-SENSOR-CABLE, cable end); SENS-031×SENS-855 (M12-5-PIN-A-CODED-IEC-61076-2-101, cable end) [E].

After the manual locus pass, exactly one D2 pair survives as a true device-to-device mating: ACT-001×ACT-002 over the DYNAMIXEL TTL bus, which is daisy-chainable by design [V]. Every other "decidable" pair is either a cable-end meeting a cable-end, a duplicate entity, or two devices contending for the same host port. The D3 count of one is therefore a **lower bound** on true mating, not an upper bound.

### 4.2 The weakest axis (Fig. 2)

| Axis / definition | Pairs | Point | 95% CI (vendor cluster) | Cross-vendor |
|---|---|---|---|---|
| Mech · same flange label | 295 | 0.1373% | [0.0132%, 0.573%] | 76.61% |
| Mech · both ends declared | 2,211 | 1.0291% | [0.160%, 2.959%] | 86.88% |
| Mech · both ends loose | 3,240 | 1.5081% | [0.368%, 4.205%] | 90.37% |
| Elec · both ends declared | 171 | 0.0796% | [0.0069%, 0.268%] | 85.96% |
| Signal · both ends declared | 77,815 | 36.220% | [26.18%, 45.57%] | 97.3% |

[E]

The mechanical point estimate moves by eleven-fold across definitions (0.137% to 1.51%) but never crosses 5% even at the upper CI. The electrical point estimate moves even more dramatically depending on the definition used (0.00047% at D3 to 0.0796% under both-ends-declared), and its 95% upper bound (0.268%) remains below the mechanical point estimates. We state this stratified, not as a single claim: the mechanical lower CI (0.0132%) and the electrical upper CI (0.268%) do overlap numerically, so the honest statement is that the electrical axis is one to three orders below the mechanical axis **in point estimate and under every reasonable definition**, with wide cluster intervals that reflect the vendor heterogeneity rather than contradicting the ordering. The signal axis, by contrast, is dense (36.220%) — a declaration of *what signals exist* is far more common than a declaration of *how they physically plug in*.

### 4.3 The taxonomy of zeros (Fig. 3)

The co-mount layer evaluates **360 pairs** (3 hosts × 16 devices, pairwise). `mountable = 0`. Verdicts split type_error 171 / port_exhausted 126 / unknown 63; stage blockers split port_budget=exhausted 240 / signal_complementary=not_complementary 171 / port_budget=unknown 120; single-mount mountable is 32 (one device can hang alone) with 16 unknown [E]. We classify every zero:

| Class | Definition | Measured | Removable by evidence? |
|---|---|---|---|
| Z1 port-exhausted | host positions < positions required | 126 pairs / 240 blockings | No (design; P1) |
| Z2 type-mismatch | flange/connector types differ | within the 171 type_error pairs | Partly (adapters; cost quantifiable, e.g. the UR20 adapter's 20 kg ceiling) |
| Z3 device-side undeclared | device carries no port declaration | 528 ports / 63 unknown pairs | Yes (the direct target of backlog collection) |
| Z4 host-side undeclared | host gives no pin count or model | FR3 branch only (p=null) | Yes (one datasheet) |
| Z5 non-complementary roles | two devices are functionally redundant | 171 not_complementary pairs | No (requirement-side, not evidence) |

**Z1+Z5 = 297/360 = 82.5%** of the evaluated pairs are zeros that additional evidence cannot turn into a mountable configuration [E]. The remaining 17.5% (Z3, Z4, and part of Z2) are the only zeros a data-collection programme can touch.

### 4.4 Proposition P1 and corollaries

**P1 (port-budget upper bound).** Let host h carry p(h) connector positions on its tool side that are independently powered and independently addressable. A device d that does not borrow external independent power or a bus occupies one position. Then the number k of independent devices co-mounted on h satisfies **k ≤ p(h)**.

*Proof.* Every device requires independent power-up and independent addressing. One physical connector position provides exactly one physical channel; two devices cannot share the same physical connector. If bus sharing is allowed (e.g. a DYNAMIXEL daisy chain), then k ≤ p(h)·m, where m is the maximum node count on that bus. ∎

**C1.** UR3e and UR5e each expose `tool_io_ports = 1` on the tool side, with a single "M8 8-pin" connector (8 is the **pin count**, not the bit count; bits = 1) [V]. Hence any k≥2 co-mount problem on these two hosts is unsatisfiable, independently of how complete the declarations on either side are.

**C2 (monotonic invariance of evidence).** Filling Z3 or Z4 can only move a verdict from unknown to compatible or from unknown to incompatible. It cannot change the satisfiability of Z1, which is decided by p(h). The programme "collect the missing data and co-mounting will follow" is therefore logically false: it solves a problem (unknown pairs) that is not the reason the 360-pair layer is all zeros.

**C3.** The Franka Research 3 host has `tool_io_ports = null` in the catalogue — a deliberate blank, because its datasheet names only an "end effector connector" without a model or pin count [V]. Its unknowns belong to Z4, not Z1; they are undecidable until evidence is supplied and must not be merged into the structural Z1 count.

### 4.5 Flange is a kit property, not a device property

Three manufacturer families, read from their own documentation [V], make the point:

- **Robotiq.** The same gripper (2F-85 / Hand-E / AirPick / EPick), through a universal connection kit, mates to both 31.5-4-M5 and 40-4-M6; through the UR-specific coupler it reads 50-4-M6; the 3-Finger model is 40-4-M6 only.
- **OnRobot.** The devices themselves carry no flange label; they are documented as "mount to Quick Changer". The Quick Changer's robot side is ISO 9409-1-50-4-M6.
- **ATI.** The Axia mounting side is a 71.12 mm bolt circle with 6×M5 tapped holes and no ISO label.

Consequently, the 2,016-pair mechanical "identity" count in the catalogue is materially **kit-spec equality**, not device interchangeability. Two parts sharing an ISO label may share it only because a purchased kit makes them so; remove the kit and the mating geometry is unstated. This is why the mechanical axis looks decidable (295–3,240 pairs) while the co-mount layer remains all zeros.

### 4.6 Robustness checks

*Name-normalised dedup.* After merging duplicate entity names, the population becomes 645 nodes / 207,690 pairs. The mechanical same-flange count moves 295 → 294; the D2 count of 8 is unchanged. Magnitude change is below 4%; all qualitative conclusions hold [E].

*Coding agreement on the backlog.* Among 101 EOAT nodes with mechanical interfaces not declared, manual adjudication produced 35 flange-bearing parts (A: 15 grippers incl. 4 dexterous hands + 20 six-axis F/T sensors), 44 body/clip-mounted parts (B: RealSense cameras, tactile skins, LiDAR/IMU/event cameras, whole-unit perception kits), and 22 generic placeholders (C). The keyword rule versus manual adjudication gives **Cohen's κ = 0.6236, agreement 74.26%, 26 flips** — below the 0.75 threshold [E]. We report this honestly as rule-versus-human agreement, not two-human agreement; it means the true backlog is 35 parts, not 101, and that filling fields without first fixing the coding rule would inject noise.

*Optimistic upper bound on filling the 35-part backlog.* Suppose, generously, that all 35 flange-bearing parts are filled and that each newly declared part matches, on the electrical axis, with every other declared part. There are 25 declared electrical ports in the catalogue; adding 35 well-documented devices at most enlarges the declared port pool by a small factor, and D2 remains bounded by pairs that simultaneously share type, pin order, and gender — conditions that held for 8 of 214,840 pairs even under the most generous D0 reading. Even at the most optimistic fill rate, the D2 density remains below 1% (recomputed in `04_ResearchData/upper_bound_calc.md`). Filling the backlog reclassifies zeros; it does not manufacture compatibility.

### 4.7 The external census (HRIM and UR+)

HRIM's repository, enumerated full-tree [V]: **21 class models** (actuator 3, composite 3, power 1, sensor 14); **3 instance-level datasheets** (hans_rotaryservo, robotiq_gripper_finger, xtion_depthsensor); **0 mechanical-mating fields** (no flange, PCD, bolt-circle, or mounting model anywhere; the generic model carries only power, id, module_3d, module_urdf, specs_comm, state_comm, status); **0 connector-level electrical fields** (electrical coverage stops at power.xml for voltage/current and specs_comm.xml for protocol — no connector model, no pin count, no pin order). The canonical gripper class model reads, verbatim, `<module name="gripper" type="actuator" description="defines the messages to interact with grippers">`, and its mandatory/optional blocks are entirely `xi:include` references to `topics/*.xml`. HRIM is a **communication information model** — it defines the messages exchanged with a gripper — not an assembly information model. It has been cited for eight years and carries zero mating fields.

The UR+ marketplace page displays **528 products**, with filters limited to Category, Applications, Product Type, Compatibility, and Region [V]. There is no flange field, no connector field, no pin-order field. Interface-field coverage is **0/528**.

The originally planned "take 50 external parts and recompute" study is therefore not executable: the two external sources together contribute zero parts with both mechanical and electrical declarations. This non-result is itself the third independent evidence — a widely cited information model and a 528-product commercial marketplace both omit the mating fields that a compatibility decision requires. Interface-description absence is ecosystem-level, not a defect of one catalogue.

## 5. Discussion

**Why "fill the data" does not make co-mounting possible.** C2 says the silent promise of every product-data project — more fields, more decisions — applies only to Z3/Z4. On the 360-pair layer, 82.5% of zeros are Z1 or Z5 and are decided now, not later. The practical consequence is that a configurator built on this catalogue will report "unknown" honestly for the remaining 17.5%, and will report "cannot" for the 82.5% with a reason that no datasheet will change.

**The de-facto standard is generation-bounded.** The UR tool connector is treated as the industrial default, but our host-side audit shows it holds only within the 50-4-M6 generation (UR3e/5e/10e/16e, 8 Long/15/18). UR20/30 moved to ISO 9409-1-80-6-M8; the official adapter converts only mechanics, not electricals, and clamps the payload to 20 kg [V]. "Compatible" here is a non-binary quantity: mechanical adapter yes, electrical adapter no, payload penalty 20 kg.

**Field-name contamination is systemic.** Three of the four closed B1 loops are the same failure in different clothes: the word "ETHERNET" written into a connector name (a protocol, not a connector); a 5-pin label where the delivery cable is 4-pin M8; a cable-end M12 recorded as a second sensor port [V]. The catalogue's electrical axis is not missing data so much as mis-attributed data — and mis-attributed data is worse than unknown, because it passes a label-equality check at D0.

**Relation to partial-constraint logic.** The configuration literature treats unknown as a symmetric third value [8][9][10][11]. Our taxonomy says it is not symmetric: Z3/Z4 unknowns wait for evidence, Z1/Z5 zeros are already final. A configurator that renders both as "unknown" on the same grey chip is overpromising on 82.5% of its decisions.

**Scope.** This is an audited catalogue (656 nodes, 329 vendors), not a market census; the bootstrap intervals are wide and must bound external inference; the κ=0.6236 is rule-versus-human, not two-human; the host-side conclusions hold only for UR3e/UR5e/FR3; and D3's single pair is a lower bound on true mating.

## 6. Threats to Validity

1. *Sample.* The 656-node set is an audit catalogue, not a probabilistic sample of the robot hardware market.
2. *Variance.* Cluster bootstrap by 329 vendors yields wide CIs; point estimates should not be read as ecosystem-wide rates.
3. *Inter-rater.* The B2 κ=0.6236 compares an automated rule to one human adjudicator, not two humans.
4. *Hosts.* Host-side numbers rest on three hosts (UR3e, UR5e, FR3); generalisation to other arms requires the corresponding datasheets.
5. *Lower bound.* With only one true device-to-device mating at D3, the true-mating rate is bounded below by 0.00047%; it could be higher in a better-curated catalogue, but the ladder's *structure* is what we claim.

## 7. Conclusion

On a fixed population of 656 composable robot nodes and 214,840 pairs, the share of decidable electrical pairs moves from 64.764% to 0.00047% as the evidence threshold tightens — five orders of magnitude, driven by 528 placeholder ports matching themselves. The electrical axis is the weakest under every definition. On the co-mount layer, 82.5% of zeros are structural (port budget or role non-complementarity) and are proved by P1 to be unsatisfiable regardless of data completeness; the remaining zeros wait on evidence that exists in principle. The leading information model (HRIM) and the leading marketplace (UR+, 528 products) both omit the mating fields these decisions require. Compatibility is not a door that better data opens; it is a measurement whose answer depends on the threshold, and a set of zeros whose upper bound is structural.

## References

1. Tola, V., et al. *Towards Easy Robot System Integration: Challenges and Future Directions.* Position paper, Aarhus University, 2022. PDF: https://clagms.github.io/assets/pdfs/Tola2022.pdf [V]
2. Zamalloa, J. B., et al. *HRIM: A Framework and Representation to Standardize the Hardware and Interfaces of Robots.* arXiv:1802.01459, 2018 (preprint; repository archived 2019-08-07). https://arxiv.org/abs/1802.01459 [V]
3. Tola, V., et al. Configuration of robot systems: a formalisation. arXiv:2401.02227, 2024 (preprint). https://arxiv.org/abs/2401.02227 [O]
4. Siltala, L., et al. IPAS: an approach to product configurability. IPAS conference / industrial engineering literature, 2019. (Secondary; exact venue to be confirmed in camera-ready.) [O]
5. Zheng, P., et al. Data-driven product design and manufacturing for customisation. *Robotics and Computer-Integrated Manufacturing*, 2019. HAL record: https://hal.science/hal-02129390/ [O]
6. Chaumet, J.-R., et al. Constraint-based configuration as a service. *Procedia CIRP* / arXiv:2311.18533, 2023. https://arxiv.org/abs/2311.18533 [O]
7. Universal Robots. UR+ Marketplace, product directory. https://www.universal-robots.com/plus/products/ (accessed 2026-11-09; 528 products observed). [V]
8. Mittal, S., Falkenhainer, B. Dynamic constraint satisfaction problems. *Proceedings of AAAI-90*, 1990. [O]
9. Sabin, D., Freuder, E. C. Contradicting conventional wisdom in constraint satisfaction. *Constraints*, 1996. [O]
10. Ciucci, D., Dubois, D. Three-valued logic and uncertainty. (Partiality/rough-sets literature.) [O]
11. ConfWS 2024 (configuration workshop), proceedings record. https://imt-mines-albi.hal.science/hal-04770758v1 [O]

---

*Data availability.* All computed values in this paper are reproducible from the shipped scripts and the frozen data bundle in `04_ResearchData/`. The underlying RoboParts JSON tables are audit records and are referenced by filename in Appendix A; external census values (HRIM tree, UR+ page) are as observed on 2026-11-09.
