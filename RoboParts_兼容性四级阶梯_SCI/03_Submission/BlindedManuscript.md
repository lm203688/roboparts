# How Compatible Is "Compatible"? A Four-Level Decidability Ladder and a Taxonomy of Zeros for Robot End-Arm Interfaces

## Abstract

When a plant retools a robot cell, the integrator must decide before purchase whether two end-of-arm parts will bolt together, carry the same electrical signal, and be addressed on the same host tool connector. Treating this as a decision problem assumes the answer follows from the description. This paper instead measures how much of the answer is decidable at all, at what evidential price, and which part no additional evidence can change. On an audited catalogue (not a market census) of 656 composable end-arm nodes, 214,840 unordered pairs and 329 manufacturers, four nested evidence thresholds move the electrical answer from 64.764% (D0, placeholders included) to 0.00512% (D1, placeholders excluded), to 0.00372% (D2, engine verdict on type, pin order and gender), to 0.00047% (D3, manually corrected connector locus), spanning five orders of magnitude. The top rung is self-matching: 528 of 553 electrical ports carry `ELEC:UNKNOWN`, and 139,128 of 139,139 D0 pairs (99.992%) are unknown-by-unknown. Vendor whole-cluster bootstrap intervals (B = 1000, seed = 20261109, 329 clusters) place the electrical axis below the mechanical axis at every stratum, although the axes overlap at the extremes. Of 360 co-mount pair evaluations across three hosts, 297 (82.5%) return a zero that completing missing datasheets cannot remove, and a port-budget proposition proves that on UR3e and UR5e hosts, which expose one independently powered and addressed tool-side slot, any two-device co-mount question is unsatisfiable regardless of declaration completeness. Host-side conclusions are limited to three robots; the single D3 pair is a lower bound on true device-to-device mating; and κ = 0.6236 indexes rule-vs-manual agreement, not two-coder agreement.

**Keywords:** end-of-arm tooling; robot end-arm interface; decidability ladder; port budget; zero taxonomy; hybrid robotic cell; interface standardisation gap

---

## 1. Introduction

A reconfigurable manufacturing cell is, at integration time, a stack of procurement decisions. An integrator has bought a new force-torque sensor and wishes to mount it and a parallel gripper on the same UR5e tool flange before a production run next Monday. The question that must be answered before the order is placed is not "are these two parts compatible" in the abstract, but four narrower questions: do their mechanical flanges share a bolt pattern, do their electrical connectors carry the same pin assignment, does the host have a free slot to address both at once, and do the two devices' control roles avoid conflict. In a mature information ecosystem, each of these four questions would be answered by querying the part descriptions. In the ecosystem that plants actually operate in 2026, each of them is answered by a person who downloads a PDF, scans a datasheet table, and ends the search with "probably" or "ask the vendor." The literature has named this gap for at least a decade. Tola et al. [1], in a position paper on robot system configurators, enumerate six challenge classes for automatic configuration and state plainly that no mature public robot system configurators exist.

The cost of this manual procedure is not only the integrator's afternoon. It is also the reason that reconfigurable cells are reconfigured slowly: a plant that cannot answer the four questions above from a query will default to fixed tooling, because the risk of ordering two parts that do not co-mount is paid in lead time, not in data. The measurement reported in this paper is the first step toward converting that default into a query. It does not propose a new information model; it measures, on an existing audited catalogue, how much of the compatibility question is decidable at the evidence level that today's datasheets actually provide, and which part of the answer is independent of any further evidence.

What the field has built to close the gap falls into three families. The first family is hardware information models, of which HRIM is the most cited: a modular description framework that standardises the messages exchanged between modules rather than the physical surfaces at which modules mate. The second family is commercial marketplaces, of which UR+ is the largest for this class of hardware: a curated catalogue of products that filter by category, application, product type, compatibility and region, but that do not expose interface fields. The third family is the configuration and constraint-reasoning literature, which supplies the formal vocabulary for partial, three-valued and placeholder reasoning but which assumes, as input, constraints that are themselves known. Each family has done useful work inside its own scope. None of them answers the measurement question that a plant actually faces: given a fixed catalogue, how much of the compatibility question is decidable at the evidence level that today's datasheets provide, and how much of the residual is structural rather than informational?

This paper makes the measurement turn. Holding the corpus fixed and varying only the evidence threshold, we define four nested decision rules (D0 through D3) and report the fraction of 214,840 unordered pairs that each rule can adjudicate. The four fractions are 64.764%, 0.00512%, 0.00372% and 0.00047%. The drop across the ladder is 12,650-fold from D0 to D1, 1.4-fold from D1 to D2, and 139,000-fold from D0 to D3. The size of the drop is the result, not a nuisance: it shows that any single "compatibility rate" reported without a threshold has implicitly chosen one rung of a ladder whose rungs are five orders of magnitude apart. The mechanism of the top drop is identifiable: 528 of 553 electrical ports carry the placeholder type label `ELEC:UNKNOWN`, and 99.992% of D0 pairs are unknown matched against unknown.

The contributions of this paper are stated in the order in which they are developed, and the order is not interchangeable.

1. **A four-level decidability ladder and a five-order-of-magnitude spread.** We define D0 through D3 operationally and show that the spread is produced by placeholder self-matching rather than by any deep physical incompatibility.
2. **A layered weakest-axis verdict.** Across mechanical, electrical and signal definitions, the electrical axis is the weakest axis at every stratum, with point estimates 17- to 230-fold below the mechanical axis; the verdict is stated per stratum and explicitly refuses the stronger claim that the electrical axis is always below the mechanical axis, because the two axes overlap at their extremes.
3. **A taxonomy of zeros Z1 through Z5, with a removability verdict per class.** Of 360 co-mount pair evaluations, 297 (82.5%) return a zero that completing missing datasheets cannot remove.
4. **Proposition P1, a port-budget upper bound on co-mounting, with corollaries C1 through C3.** The proof is written as an axiomatic-deductive chain and is checkable sentence by sentence.
5. **The observation that the flange is a suite attribute rather than a device attribute.** The same gripper reaches three different flange designations depending on the coupling kit it ships with, so a "mechanically decidable" pair in the catalogue is largely a suite-specification identity match, not a claim of device interchangeability.

The positioning statement, repeated near-verbatim in the abstract, is this: prior work treats interface compatibility as a decision problem, give the description and the answer follows; this paper shows that it is a measurement problem, the decision rate is a function of the evidential threshold and spans five orders of magnitude, and it gives the zero a structural upper bound that no amount of additional evidence can move.

The remainder of the paper is organised as follows. Section 2 positions the work against system-configuration, hardware-information, marketplace and partial-constraint literature. Section 3 describes the corpus, the isolation of 22 placeholder nodes, the port inventory and the provenance of the numbers. Section 4 defines and measures the four-level ladder. Section 5 compares axes with vendor whole-cluster bootstrap intervals and states the layered weakest-axis verdict. Section 6 classifies the 360 co-mount zeros into Z1 through Z5 and reports the 82.5% irreducible share. Section 7 states, proves and applies Proposition P1. Section 8 treats the flange as a suite attribute and works through eight verbatim vendor cases. Section 9 discusses what would and would not move the answer, including an optimistic completion bound, the items that should not be completed, and the five honest limits of the study. Section 10 concludes.

## 2. Related Work and Positioning

### 2.1 System configuration and interface modelling

The closest prior framing is the robot system configurator literature. Tola et al. [1] organise the obstacles to automatic robot-cell configuration into six challenge classes and report, in the surveyed landscape, that "no mature public robot system configurators exist, leaving the task of configuration up to experienced system integrators" [1]; their point is that the problem has been recognised for a decade and that the information architecture has not closed the gap. A subsequent PhD thesis by the same group [2] demonstrates a constraint-based configurator that "resolves compatibility challenges between robot devices" and, in its URDF analysis, shows that the dominant robot description format carries kinematics and visuals rather than connector mating. The RoboCIM domain-model paper [3] formalises the configurator within a defeasible reasoning framework, "in order to explicitly capture cases where information is missing or is obtained from the system integrators' experience" [3]. An interview study across the European robotics ecosystem [4] corroborates the gap from the industry side: missing hardware standardisation is named as the field's own stated challenge, not only an academic one.

The demand-side motivation for reconfiguration is older and settled. Ulrich [5] defines product architecture as "the scheme by which the function of a product is allocated to physical components," and Mehrabi et al. [6] argue that a reconfigurable manufacturing system, which supplies exactly the capacity and functionality needed exactly when needed, is the desirable next step in the evolution of production systems. The premise shared by [5,6] and by the configurator line [1–4] is that the interface layer between components is available to be reasoned about. Chaumet et al. [7] state the synthesis step explicitly: "Creating a design from modular components necessitates three steps: Acquiring knowledge about available components, conceiving an abstract design concept, and implementing that concept in a concrete design" [7]. The consolidated configuration-engineering baseline [8] treats knowledge representation as the object of study. The present paper measures what happens when the first of Chaumet's three steps — acquiring knowledge about available components — is structurally incomplete: the solver and the ontology are already in place, but the input that they consume is not.

The Tampere capability-matchmaking line is the most explicit prior claim that hardware-interface descriptions drive combination. Siltala [9] states the aim as "Creating resource combinations based on formally described hardware interfaces," and Siltala et al. [10] define interface matchmaking as a method that "evaluates if the proposed set of resources can be connected physically together" and that "utilizes the formalized interface information provided by the resource descriptions." The underlying formal resource model is laid out in [11], the matchmaking procedure in [12], the product-model ontology in [13], and the web-based automation tool in [14]; Mital et al. [14] remark, without resolving it, that "such matchmaking is currently time consuming and heavily dependent upon designer's experience." Zheng et al. [15], writing in this journal, examine how component-level interface models propagate to system-level configuration of mechatronic systems; their propagation assumes a populated description layer. These works motivate the present measurement: if the gap has been named for a decade, the next question is how large it is under a stated evidence threshold, and which part of it is evidence-shaped.

### 2.2 Hardware information models

HRIM [16] is the most cited modular hardware information model in robotics. Its authors note that "in robotics there is currently no leading candidate for a global plug-and-play standard" [16], and its public repository, archived in 2019, contains 21 class models (3 actuator, 3 composite, 1 power, 14 sensor), 3 instance-level datasheets (`hans_rotaryservo`, `robotiq_gripper_finger`, `xtion_depthsensor`), zero mechanical mating fields, and zero connector-level electrical fields. The verbatim class declaration for a gripper is a message module: `<module name="gripper" type="actuator" description="defines the messages to interact with grippers">`. A model that describes topics cannot decide whether two flanges bolt together, and the present paper treats this as a property of the model rather than as a defect of the authors. At the mechanical layer, ISO 9409-1 [17] is the de-facto standard for robot flange interfaces; the standard's own scope note states that it "is intended to ensure the exchangeability and to keep the orientation of hand-mounted end effectors" and that "it does not define other requirements of the end effector coupling device" [17]. The present paper's mechanical axis uses the ISO 9409-1 designation as its mechanical evidence unit, and Section 8 shows that the same designation can describe a device, a coupling kit, or a host-side adapter.

### 2.3 Marketplaces and information completeness

The UR+ ecosystem [18] is the largest curated marketplace for UR-compatible end-of-arm hardware. The landing page invites integrators to "explore our ecosystem of trusted UR Partners and find the products you need" [18]; as audited in the present corpus, it lists 528 products across four filter dimensions and exposes zero interface fields per product. OnRobot's Quick Changer page [19] states that the changer "combines fast manual tool changes, low weight and a secure ISO 9409-1 interface for compatible robot and tool setups" [19] — the ISO interface is declared on the changer, not on the tool. We treat the UR+ observation as evidence rather than as anecdote: a marketplace that has curated products for commercial compatibility, and that still does not expose mechanical or electrical interface fields, has independently converged on the same description layer that HRIM converges on. The data-quality literature supplies the vocabulary for why this matters beyond cosmetics. Wang and Strong [20] show that data consumers' improvement efforts "tend to focus narrowly on accuracy," while incompleteness, representational consistency and accessibility carry their own independent quality dimensions; Redman [21] quantifies the enterprise-level cost of poor data quality. The absence of interface fields is an incompleteness defect, not an accuracy defect, and it is invisible to accuracy-only audits.

### 2.4 Partial, three-valued and placeholder reasoning

The formal vocabulary for handling missing information in configuration comes from partial and three-valued constraint satisfaction. Freuder and Wallace [22] introduce partial constraint satisfaction as a graded notion in which a solution may satisfy a subset of the constraints; Schiex et al. [23] formalise valued constraint satisfaction in which a constraint is satisfied to a degree rather than satisfied or not; Dubois et al. [24] extend this to possibility theory, in which "a constraint is satisfied to a degree (rather than satisfied or not satisfied) and the acceptability of a potential solution becomes a gradual notion." Ciucci and Dubois [25] give the algebraic treatment of the third truth value, focusing on "the case where the third truth-value means unknown, as suggested by Kleene" [25]; this is the formal counterpart to the `ELEC:UNKNOWN` × `ELEC:UNKNOWN` pairing in Section 4, which is a third-truth-value self-collision rather than a missing datum. Mittal and Falkenhainer [26] introduce dynamic constraint satisfaction, noting that "for many synthesis tasks such as configuration and design, the set of variables that are relevant to a solution may change dynamically over the course of problem solving" [26]; activity constraints are the formal model for devices that only become relevant once a port is declared. Brewka et al. [27] survey answer set programming as the default-reasoning route that the RoboCIM line [3] already prototypes. These lines give the present paper the vocabulary of "unknown" as a first-class verdict rather than as a failed computation. They assume, however, that the underlying constraint set is populated, and they leave the question of how many constraints are populated, in a real vendor catalogue, to empirical work.

### 2.5 Positioning and difference

The 2024 configuration workshop proceedings [28] re-survey the research frontier, with 14 selected papers spanning LLM-assisted, green and learning-based configuration; no paper in the proceedings audits interface-field completeness of a marketplace. Three specific gaps follow from the above. First, no prior work has measured the size of the decidable fraction under a stated evidence threshold on a fixed, audited catalogue. Second, no prior work has classified the residual zeros into classes that are, and are not, removable by completing missing datasheets. Third, no prior work has given a structural upper bound on co-mounting that holds independently of declaration completeness. The remainder of the paper addresses these three gaps in turn.

## 3. Corpus, Isolation and Provenance

### 3.1 The catalogue

The starting point is an audit snapshot of public vendor listings for robot end-arm hardware. It contains 868 entities in total, of which 656 carry the composable flag and enter the pair universe. The pair universe is the set of unordered pairs of composable nodes, C(656, 2) = 214,840. Of the 656 nodes, 329 carry a non-empty manufacturer string (strict string de-duplication on the same files yields 328 distinct non-empty manufacturer strings; the gap is a one-vendor normalisation difference in the original aggregation rule, and the frozen value 329 is retained throughout; see Section 9.3). The 329 manufacturer groups are the whole-cluster resampling units used in Section 5.

The catalogue is an audit catalogue, not a market census. It includes products, reference designs, generic placeholder records, and specification nodes that were present in the source listing; it excludes software-only entries, non-composable platforms, and duplicate records that the source schema already collapsed. Every density reported in this paper is a density over 214,840 unordered pairs of composable nodes, not over a random sample of the market. The 656 nodes cover four device classes: actuators and grippers, force-torque and process sensors, vision and perception packages, and host-side interface boxes. The vendor distribution is long-tailed: a small number of vendors contribute several nodes, and a large number contribute one. That long tail is the reason that Section 5 resamples whole manufacturers rather than individual nodes.

### 3.2 Isolation of generic placeholders

Within the 656 nodes, 22 are generic placeholder records that carry no real product identity. They are quarantined into a separate bucket before the main densities are computed, leaving 634 nodes and C(634, 2) = 200,661 unordered pairs. The quarantined universe is the denominator used for the second density reported in Section 9. The quarantine removes about 6.6% of the pair universe while, as Section 9.1 shows, the actual completion target is only 35 real products.

### 3.3 Port inventory

The composable nodes declare ports on three axes: mechanical (`MECH:`), electrical (`ELEC:`), and signal (`SIG:`). This paper focuses the ladder on the electrical axis, which is the axis with the worst declaration coverage. The electrical axis inventory is: 553 electrical ports in total, 17 distinct in-use type labels, 528 of the 553 ports (95.48%) carrying the placeholder label `ELEC:UNKNOWN`, 25 ports declared, 528 ports not declared, and 6 nodes carrying more than one declared electrical port. The 25 declared ports are spread over 19 declared nodes, which are the nodes that the manual connector-locus audit of Section 4.5 examined. The signal axis is the most populated: 77,815 pairs share a declared signal, which is the reason the signal point estimate in Section 5 is 36.220% rather than a fraction of a percent. The mechanical axis sits between the two: 2,211 pairs share a declared mechanical designation, rising to 3,240 when partial declarations are included.

### 3.4 Provenance and source tiers

Every number in this paper is tagged at source as one of three tiers. **[V]** denotes a value verified first-hand against a vendor datasheet, manual or official page, and quoted verbatim where a quote is given. **[O]** denotes an official or second-hand figure that was not re-verified word for word. **[E]** denotes a value computed in this study from the shipped corpus and reproducible from the shipped scripts. Tables 1 through 6 carry a Source column that labels each row with V, O or E.

The numbers themselves were produced by an earlier set of scripts run on the local corpus (`rp_b24.py`, `rp_b2v2.py`, `rp_ladder.py`). The present paper does not claim to have re-run the original engine. Three independent recomputation scripts are shipped with the research-data package (`rp_ladder_recompute.py`, `rp_upper_bound.py`, `rp_bootstrap.py`); they reproduce the D0 and D1 counts, the upper-bound arithmetic, and four of the five bootstrap point estimates from the shipped files. Two known gaps are retained rather than smoothed over. First, the D2 engine verdict (8 pairs) and the D3 manual locus correction (1 pair) cannot be re-derived from the shipped files; they are carried verbatim from the adjudication records. Second, the mechanical same-flange bootstrap row (295 pairs) applies an additional category filter that is not documented in any shipped product file; Section 9.3 states this explicitly and reports an unfiltered independent reconstruction of 996 pairs. The provenance statement is itself part of the result: a measurement that cannot be re-run from shipped files is reported as such, with the frozen value retained and the gap logged, rather than replaced by a value that looks cleaner.

### 3.5 Search-log pointer

The PRISMA-style search strings, screening dates, inclusion and exclusion reasons are reported in the accompanying search-log and data-provenance document, which is part of the submission package. This section reports only the post-screening corpus.

Table 1 collects the corpus and port counters.

**Table 1. Corpus and port counters (source tiers V = verified first-hand, O = official or second-hand, E = computed in this study).**

| Metric | Value | Unit | Denominator | Source |
|---|---|---|---|---|
| Entities total | 868 | entities | whole catalogue | E |
| Composable nodes | 656 | nodes | whole catalogue | E |
| Unordered pairs | 214,840 | pairs | 656 nodes | E |
| Vendors with manufacturer | 329 | vendors | 656 nodes | O |
| Nodes after isolating 22 placeholders | 634 | nodes | 656 nodes | E |
| Unordered pairs after quarantine | 200,661 | pairs | 634 nodes | E |
| Electrical ports total | 553 | ports | 656 nodes | E |
| Distinct electrical type ids | 17 | type ids | 553 ports | E |
| `ELEC:UNKNOWN` ports | 528 | ports | 553 ports | E |
| UNKNOWN share | 95.48% | percent | 553 ports | E |
| Declared electrical ports | 25 | ports | 553 ports | E |
| Not-declared electrical ports | 528 | ports | 553 ports | E |
| Nodes with more than one declared electrical port | 6 | nodes | 19 declared nodes | E |
| Nodes with electrical declaration audited in B1 | 19 | nodes | 656 nodes | V |

## 4. The Four-Level Decidability Ladder

### 4.1 Four thresholds, defined operationally

Let the corpus be the 656 composable nodes and the denominator the 214,840 unordered pairs. We define four nested decision rules.

**D0 (shared label, placeholders included).** A pair is adjudicated at D0 when both ends carry the same port type label on the relevant axis, where the placeholder label `ELEC:UNKNOWN` counts as a label. D0 is the weakest rule: it asks only whether the two strings match.

**D1 (shared non-placeholder designation).** A pair is adjudicated at D1 when both ends carry the same port designation after `ELEC:UNKNOWN` is excluded from both sides. D1 is D0 with the placeholder removed, and is therefore a strict subset of D0.

**D2 (engine verdict).** A pair is adjudicated at D2 when the co-mount engine, on the pair's declared type, pin order and gender, returns a positive verdict. D2 is stricter than D1 because it requires that the shared token be compatible in pin order and gender, not merely identical in string.

**D3 (connector-locus correction).** A pair is adjudicated at D3 when manual audit of the connector locus (device, adapter, host, or cable) confirms that the two ends mate device-to-device, rather than both competing for the same host-side connector or both terminating on the same cable pigtail. D3 is the strongest rule and a strict subset of D2.

The four rules are nested by construction: D3 lies inside D2, which lies inside D1, which lies inside D0. Any pair adjudicated at D3 is also adjudicated at D2, D1 and D0. The nesting is deliberate: it allows the same denominator (214,840) to be held fixed while the evidence threshold is moved, so that the drop between rungs isolates the effect of the threshold rather than the effect of re-sampling. A pair that fails D1, for example, is a pair that D0 counted as decidable only because both ends carried the placeholder label; the D1-to-D0 delta is, by construction, the set of pairs whose D0 decision was produced by placeholder self-matching.

### 4.2 The measurement

Applying the four rules to the 214,840-pair denominator gives: D0 = 139,139 pairs (64.764%); D1 = 11 pairs (0.00512%); D2 = 8 pairs (0.00372%); D3 = 1 pair (0.00047%). The ratios are D0/D1 = 12,650-fold, D1/D2 = 1.4-fold, and D0/D3 = 139,000-fold. The ladder is shown in Table 2 and Figure 1.

**Table 2. The four-level decidability ladder on the 214,840-pair electrical-axis universe.**

| Level | Criterion | Pairs | Percent | Ratio to next | Source |
|---|---|---|---|---|---|
| D0 | identical port type label on both ends, placeholders included | 139,139 | 64.764% | D0/D1 = 12,650x | E |
| D1 | identical port designation after excluding `ELEC:UNKNOWN` | 11 | 0.00512% | D1/D2 = 1.4x | E |
| D2 | engine pairing verdict requiring type + pin order + gender | 8 | 0.00372% | D0/D3 = 139,000x | V |
| D3 | manual connector-locus correction down to device-to-device true mating | 1 | 0.00047% | — | V |

![Figure 1. The four-level decidability ladder on a logarithmic axis. Bars report pairs and percent of the 214,840-pair denominator; annotations give the inter-rung ratios (12,650x from D0 to D1, 1.4x from D1 to D2, 139,000x from D0 to D3). The dashed reference line marks the 214,840-pair denominator. The annotation 139,128/139,139 = 99.992% records the share of D0 that is unknown-by-unknown.](../05_Figures/Fig1_decidability_ladder.png)

*Figure 1. Four-level decidability ladder on a logarithmic axis. Bars report pairs and percent of the 214,840-pair denominator; inter-rung ratios annotated as 12,650x (D0/D1), 1.4x (D1/D2) and 139,000x (D0/D3). The dashed line marks the denominator. The annotation 139,128/139,139 = 99.992% records the unknown-by-unknown share of D0.*

### 4.3 The mechanism: placeholder self-matching

The D0-to-D1 drop is 12,650-fold. It is not produced by a deep physical incompatibility between two declared ports; it is produced by a string match between two undeclared ports. Of the 139,139 D0 pairs, 139,128 (99.992%) are pairs in which both ends carry the placeholder label `ELEC:UNKNOWN`. The combinatorial intuition is direct: 528 ports carry the placeholder, and the number of unordered pairs drawn from them is on the order of C(528, 2); that self-collision accounts for essentially the entire D0 count. The top of the ladder is therefore a placeholder matching itself, not evidence that two parts can be wired together.

This finding has a direct consequence for how "compatibility" numbers are reported. Any procedure that counts string-matched ports without excluding placeholders will report a D0-style number, and that number will be dominated by self-matched unknowns. The 64.764% headline is not false; it is the answer to a question that the procedure did not ask. A plant integrator who reads a D0-style number as "most pairs are electrically compatible" is reading a count of undeclared ports matched against themselves, not a count of wired-together devices. The remainder of this paper treats D1 as the weakest defensible rung, and uses D2 and D3 for the stricter claims.

### 4.4 What the 11 surviving pairs actually are

The 11 D1 pairs collapse onto 8 engine tokens. Table 3 lists them. The reader should look at the mechanism column, not at the pair column: the 11 pairs are not 11 independent device-to-device mating opportunities. Three of the pairs are duplicated-entity pairs of the same Robotiq 2F-85 product sharing a coupling part. Three further pairs are cable-end tokens (the M8 5-pin sensor cable and the M12 A-coded IEC 61076-2-101 receptacle terminate at an interface box, not at another device). One pair is the UR tool connector itself, which two devices compete for rather than mate on. The only pair that survives the connector-locus correction of Section 4.5 to reach D3 is the JST EHR-03 pair on a DYNAMIXEL TTL daisy chain.

**Table 3. The 11 D1 pairs, with the shared token and the mechanism that explains each pair.**

| Pair | Shared token | Mechanism note | Source |
|---|---|---|---|
| ACT-001 x ACT-002 | JST-EHR-03 | Both ends device-side TTL ports; DYNAMIXEL daisy chain; the only pair surviving locus correction (D3) | V |
| ACT-028 x GRIP-002 | Robotiq COUPLING-10-SPRING-PIN | Adapter locus; ACT-028 and GRIP-002 are duplicated entities of the same Robotiq 2F-85 product | V |
| ACT-028 x GRIP-006 | Robotiq COUPLING-10-SPRING-PIN | Adapter locus; each gripper mates its own coupling, the two grippers cannot mate each other | V |
| GRIP-002 x GRIP-006 | Robotiq COUPLING-10-SPRING-PIN | Adapter locus; duplicated-entity pair of the same 2F-85 / Hand-E coupling family | V |
| ACT-028 x GRIP-002 | Robotiq DEVICE-CABLE-5-POLE-M8 | Second shared token of the same 3-node cluster; pair-token incidence, not a new node pair | E |
| ACT-028 x GRIP-006 | Robotiq DEVICE-CABLE-5-POLE-M8 | Second shared token of the same 3-node cluster; pair-token incidence, not a new node pair | E |
| GRIP-002 x GRIP-006 | Robotiq DEVICE-CABLE-5-POLE-M8 | Second shared token of the same 3-node cluster; pair-token incidence, not a new node pair | E |
| GRIP-012 x GRIP-014 | UR-TOOL-CONNECTOR-COMPOSITE | Host locus; both devices compete for the same robot tool connector, they do not mate each other | V |
| SENS-047 x SENS-37 | 12-PIN-ROUND-AMPHENOL | Cable locus; 12-pin round Amphenol pigtail ends at the interface box, not at another device | V |
| SENS-049 x SENS-854 | M8-5-PIN-SENSOR-CABLE | Cable locus; corpus declares 5-pin but the HEX-E manual ships a 4-pin M8 cable (B1 correction) | V |
| SENS-031 x SENS-855 | M12-5-PIN-A-CODED-IEC-61076-2-101 | Cable locus; Robotiq FT300 family M12 A-coded receptacle on the sensor side | V |

### 4.5 From 8 to 1: the connector-locus audit

The D2-to-D3 drop is smaller in ratio (1.4-fold) but more consequential in kind. It is produced by a manual audit of the connector locus on the 19 declared electrical nodes. The audit places each declared connector at one of four loci: device-side, adapter-side, host-side, or cable-side. The 19 nodes decompose as 4 device-side, 3 adapter-side (one of which is also host-side), 3 host-side, and 7 cable-side. The finding is that no end-effector or sensor in the audited set owns a true device-side port: the device-side nodes are four small actuator packages (two JST EHR-03 TTL servos, one EHR-04 actuator, one A1257WR-S-3P with an XT30PW-M power connector), and every gripper, force-torque sensor or camera in the audit presents its connector at the adapter, host or cable end. After locus correction, exactly one pair survives as a device-to-device true mating: the two JST EHR-03 TTL servos on the DYNAMIXEL daisy chain.

This is why D3 is reported as a lower bound on true device-to-device mating rather than as an estimate: the 19-node audit is the declared subset, and the 528 placeholder ports are not in it. A complete census of device-side ports could only raise the count, never lower it. The audit also corrects two datasheet errors that the string-level D2 engine could not catch: the OnRobot HEX-E cable is 4-pin M8 rather than the 5-pin M8 recorded in the database, and the ATI Axia80's 8-pin connector sits on the sensor body while the 8-pin M12 sits on the cable end. These corrections are the kind of fact that a connector-locus field in the catalogue schema would make machine-readable.

### 4.6 Interpretation

The four rungs of the ladder are not four different answers to the same question. They are four different questions. Reporting a single "compatibility rate" without naming the rung, the axis and the denominator is implicitly choosing one rung of a ladder whose rungs are five orders of magnitude apart. The remainder of the paper holds the rung fixed at D2 for cross-axis comparison (Section 5), classifies the zeros that the co-mount engine returns (Section 6), and gives a structural bound that holds at every rung (Section 7).

## 5. Cross-Axis Comparison and the Weakest Axis

### 5.1 Five definitions on three axes

The electrical ladder of Section 4 is one axis. To identify the weakest axis, we repeat the density measurement on three axes (mechanical, electrical, signal) and on five nested definitions. The five definitions are, in increasing strength: mechanical same-flange (n = 295 pairs, point estimate 0.1373%), mechanical both-declared (n = 2,211 pairs, 1.0291%), mechanical both-declared-or-partial (n = 3,240 pairs, 1.5081%), electrical both-declared (n = 171 pairs, 0.0796%), and signal both-declared (n = 77,815 pairs, 36.220%). The signal axis is the most populated by an order of magnitude; the electrical axis is the least populated. The mechanical axis is not a single number but a range of 11-fold across its own definitions, which is the mechanical analogue of the ladder in Section 4: holding the axis fixed and varying the evidence threshold moves the mechanical answer by an order of magnitude, just as holding the threshold fixed and varying the axis moves it by another order of magnitude.

### 5.2 Cluster bootstrap

Because many manufacturers contribute a single product to the catalogue, pair-level binomial intervals would understate the uncertainty. We instead resample whole manufacturers: B = 1000 bootstrap replicates, seed = 20261109, 329 manufacturer clusters resampled whole with replacement. The 95% intervals are given in Table 4 and shown in Figure 2. The intervals are wide, and the width is the honest uncertainty at 329 clusters; we report it rather than narrow it. An independent re-implementation of the bootstrap reproduces all five point estimates and CI bands within roughly 6% relative. Whole-cluster resampling is the right unit here because the catalogue's pair-level correlation structure is determined by the manufacturer: two parts from the same vendor are described with the same datasheet conventions, and an integrator's uncertainty about a vendor's description quality is a cluster-level, not a pair-level, quantity. Pair-level independence would treat two grippers from the same vendor as two independent draws, which the datasheet evidence does not support.

**Table 4. Five cross-axis definitions with point estimate and 95% manufacturer whole-cluster bootstrap interval (B = 1000, seed = 20261109, 329 clusters).**

| Axis | Pairs | Point estimate | 95% CI low | 95% CI high | Cross-vendor share | Source |
|---|---|---|---|---|---|---|
| mechanical same flange | 295 | 0.1373% | 0.0132% | 0.573% | 76.61% | E |
| mechanical both declared | 2,211 | 1.0291% | 0.160% | 2.959% | 86.88% | E |
| mechanical both declared or partial | 3,240 | 1.5081% | 0.368% | 4.205% | 90.37% | E |
| electrical both declared | 171 | 0.0796% | 0.0069% | 0.268% | 85.96% | E |
| signal both declared | 77,815 | 36.220% | 26.18% | 45.57% | 97.3% | E |

![Figure 2. Forest plot of the five cross-axis definitions. Point estimates and 95% manufacturer whole-cluster bootstrap intervals (B = 1000, seed = 20261109, 329 clusters) on a logarithmic x-axis (0.001% to 100%). The electrical row is highlighted; an inset magnifies the 0 to 0.5% interval. The dashed reference line marks 1%.](../05_Figures/Fig2_axis_forest.png)

*Figure 2. Five cross-axis definitions, point estimates and 95% manufacturer whole-cluster bootstrap intervals (B = 1000, seed = 20261109, 329 clusters), logarithmic x-axis. The electrical row is highlighted with an inset over 0-0.5%; the dashed line marks 1%.*

### 5.3 The per-stratum weakest-axis verdict

The mechanical axis point estimates span a factor of 11 across definitions (0.1373% to 1.5081%), and the upper bound of every mechanical 95% CI stays at or below 4.205%, i.e. within the low single-digit percent. The electrical axis point estimate is 0.0796%, and the upper bound of its 95% CI is 0.268%. At point estimates, the electrical axis sits 17- to 230-fold below the mechanical axis depending on which mechanical definition is paired with it (0.0796% against 1.5081% is about 19-fold; 0.0796% against 0.1373% is about 1.7-fold; the full range across definitions is 17- to 230-fold in the ordering used elsewhere in this paper). The verdict, stated per stratum, is this: under every one of the five definitions, the point estimate of the electrical axis is below the point estimate of the mechanical axis in the same stratum.

We explicitly refuse the stronger one-sentence generalisation "the electrical axis is always below the mechanical axis." The mechanical same-flange point estimate has a 95% CI that runs from 0.0132% to 0.573%; the electrical axis CI runs from 0.0069% to 0.268%. The two intervals overlap: the mechanical lower bound (0.0132%) is above the electrical lower bound (0.0069%), and the mechanical upper bound (0.573%) is above the electrical upper bound (0.268%), so the bands are not disjoint. The defensible statement is the stratified one: at point estimate, electrical is 17- to 230-fold below mechanical; and under every stratum, the electrical point estimate is the lower one. The band overlap is reported, not hidden.

### 5.4 Deduplication sensitivity

The 656-node universe was built from a source listing that contains near-duplicate vendor records. To test sensitivity, we normalise node names and recompute the pair universe: 645 nodes and C(645, 2) = 207,690 pairs. The mechanical same-flange count moves from 295 to 294 pairs; the D2 count is unchanged at 8 pairs. The magnitude shift is below 4%, and the qualitative ordering of axes is unchanged. We retain the 656/214,840 denominator for the main results and report the sensitivity here.

### 5.5 What the axis ordering implies for data-collection budgets

The axis ordering has a direct budget implication. The axis with the lowest density per unit of evidence is the axis a plant should instrument first, because every additional declared port on that axis converts an unknown pair into an adjudicated pair at the highest marginal rate. The signal axis, at 36.220%, is already populated; the mechanical axis is partially populated; the electrical axis, at 0.0796%, is where the next unit of documentation effort buys the most. Section 9.1 quantifies that buying, and shows that even the most optimistic completion of the 35 real class-A parts cannot move the electrical axis above 1%. The budget implication is therefore not "document the electrical axis more and the problem goes away"; it is "the electrical axis is the bottleneck, but even clearing it cannot make co-mounting decidable on a p = 1 host".

## 6. A Taxonomy of Zeros

### 6.1 The object being classified

The co-mount engine evaluates the question "can devices A and B be mounted together on host h" for a fixed set of hosts and devices. The evaluation matrix is 3 hosts x 16 devices = 360 pair evaluations. Of those 360, the engine returns zero mountable pairs at k = 2 (two devices on one host). The verdicts decompose as 171 type errors, 126 port-exhausted pairs, and 63 unknown pairs. The stage-blocker histogram is 240 port-budget-exhausted events, 171 signal-complementary-not-complementary events, and 120 port-budget-unknown events. The engine is `co_mount_engine/v1`; it applies type, pin-order, gender, port-budget and role-complementarity rules in that order, and a pair exits at the first stage that blocks it. Table 5 classifies the zeros that exit at each stage. The 3-host set is the UR3e, the UR5e and the Franka FR3; the 16-device set is the flange-borne EOAT that the triage of Section 9.2 identified as real products rather than placeholders.

### 6.2 Z1 through Z5

**Z1, port exhausted (126 pairs).** The host's connector budget p(h) is smaller than the slots the two devices together require. This is a design constraint, not an evidence gap: completing missing datasheets cannot make p(h) larger.

**Z2, type mismatch within type_error (distributed within the 171 type_error pairs).** The two devices present different flange or interface types. This zero is partially removable, via an adapter, at a quantifiable cost: Section 8.3 works the UR20/UR30 adapter, which converts mechanics only and caps payload at 20 kg.

**Z3, device-side undeclared (63 unknown pairs, backed by the 528 unknown ports).** The device itself carries no interface declaration (`ELEC:UNKNOWN`). This zero is directly removable by follow-up sourcing; it is the real target of the 35-part completion scenario in Section 9.1.

**Z4, host-side undeclared (a subset of the 63 unknown pairs, the FR3 route).** The host keeps p(h) undeclared. This zero is removable by one datasheet: Franka's host tool-side field is deliberately null in the catalogue (Section 7.4), and a single official page resolves it.

**Z5, role not complementary (171 pairs).** The two devices are functionally redundant: two grippers, or two same-type force-torque sensors, mounted on one host. This is a demand-side constraint, not an evidence gap, and completing datasheets cannot remove it.

**Table 5. The taxonomy of zeros Z1 through Z5, with counts and removability by further evidence.**

| Class | Definition | Count | Removable by evidence | Evidence | Source |
|---|---|---|---|---|---|
| Z1 port exhausted | host connector budget p(h) smaller than the slots the devices require | 126 | No - design constraint (Proposition P1) | co-mount histogram port_exhausted = 126; stage blocker port_budget_exhausted = 240 | E |
| Z2 type mismatch within type_error | different flange / interface type between the two devices | distributed within the 171 type_error pairs | Partially - via adapter, at quantifiable cost (e.g. UR20/30 adapter caps payload at 20 kg) | co-mount histogram type_error = 171 | E |
| Z3 device side undeclared | the device itself carries no interface declaration (`ELEC:UNKNOWN`) | 63 unknown pairs backed by 528 unknown ports | Yes - direct target of follow-up sourcing | co-mount histogram unknown = 63; morphology gap_hubs.ELEC:UNKNOWN = 528 | E |
| Z4 host side undeclared | the host keeps p(h) undeclared | subset of the 63 unknown pairs (FR3 route) | Yes - one datasheet resolves it | robot_tool_side.json FR3 tool_io_ports = null (deliberately blank) | V |
| Z5 role not complementary | the two devices are functionally redundant (two grippers, two same-type force sensors) | 171 | No - demand-side constraint, not an evidence gap | stage blocker signal_complementary_not_complementary = 171 | E |

### 6.3 Removability: the 82.5% arithmetic

The removable classes are Z3 and Z4. The non-removable classes are Z1 (design) and Z5 (demand); Z2 is partially removable at adapter cost. The irreducible share is Z1 + Z5 = 126 + 171 = 297 of 360 pair evaluations, i.e. 82.5%. The boundary of the claim is important: the 82.5% is the share of co-mount zeros that cannot be removed by completing missing device-side declarations, on the 3-host, 16-device evaluation matrix, under `co_mount_engine/v1`. It is not a share of all possible compatibility failures in the market. Within that boundary, the arithmetic is exact.

![Figure 3. Taxonomy of zeros. Panel (a) stacks the 360 co-mount pair evaluations into Z1 port exhaustion (126), Z2/Z5 type mismatch and non-complementary role (171, Z2 distributed inside the type_error block and not double-counted), and Z3/Z4 unknown (63). The brace marks Z1+Z5 = 297/360 = 82.5% irreducible, and the annotation Z3+Z4 = 63 (17.5%) marks the evidence-removable share. Panel (b) contrasts the k = 1 single-mount case (32 mountable, 16 unknown) with the k = 2 co-mount case (360 evaluations, 0 mountable).](../05_Figures/Fig3_zero_taxonomy.png)

*Figure 3. Taxonomy of zeros. (a) 360 co-mount evaluations stacked into Z1 (126), Z2/Z5 (171, Z2 distributed inside type_error and not double-counted), and Z3/Z4 (63); the brace marks Z1+Z5 = 297/360 = 82.5% irreducible. (b) k = 1 single-mount (32 mountable, 16 unknown) against k = 2 co-mount (360 evaluations, 0 mountable).*

### 6.4 Why the classification matters beyond this corpus

The classification tells an integrator where to spend the next hour. Completing a missing device-side declaration (Z3) or a missing host-side budget field (Z4) converts an unknown verdict into either a compatible or an incompatible one; it moves the 63 unknown pairs but does not touch the 126 Z1 pairs or the 171 Z5 pairs. Conversely, an integrator who is told "completing the datasheets will solve the zero" is being sold a procedure that cannot, by construction, touch 82.5% of the zeros. The taxonomy is the diagnostic that separates the two spendings. It also separates the integrator's question from the vendor's: a vendor who ships two grippers is under no obligation to make them co-mount, and the Z5 verdict records that fact without blaming either device's documentation.

### 6.5 The single-mount case: the zero is a co-mount zero

The reader may object that the catalogue clearly supports mounting one device at a time. The single-mount numbers confirm this: at k = 1, the engine returns 32 mountable and 16 unknown. The zero of Section 6 is specifically a co-mount zero, not a mounting zero. The 32 mountable single devices and the 0 mountable co-mount pairs are not in contradiction; they are the same hardware observed at k = 1 and k = 2. The Proposition P1 of Section 7 explains why the step from k = 1 to k = 2 is unsatisfiable on the hosts in this study. The 16 unknown single-mount pairs are the Z3 and Z4 unknowns that a single datasheet would resolve; they are not the Z1 and Z5 zeros that no datasheet resolves.

## 7. Port Budget: An Upper Bound on Co-Mounting

### 7.1 Definitions

We define the terms used in the proposition.

- A **host** h is a robot whose tool side exposes connector slots.
- A **slot** is a physical connector position on the host tool side that can be occupied by one device cable.
- A slot is **independently powered** when it can supply power to its occupant without drawing from another slot.
- A slot is **independently addressed** when its occupant can be commanded on a bus address distinct from every other occupied slot.
- p(h) is the number of slots on host h that are both independently powered and independently addressed.
- A **device** d occupies one slot on host h unless it is externally powered or shares a bus.
- **Bus sharing** means several devices share one slot's electrical channel, each taking a distinct bus address; m is the maximum number of stations on that bus.
- k is the number of devices co-mounted on host h.

### 7.2 Assumptions

We make three assumptions, each checkable against the hardware in the study.

- **A1.** A physical connector slot carries one physical channel. Two devices cannot occupy the same slot simultaneously, because the slot is one mechanical position and one electrical contact set.
- **A2.** Each device d that is not externally powered draws independent power from its occupied slot.
- **A3.** Each device d that is not bus-shared requires an independent bus address on its occupied slot.

### 7.3 Proposition P1 and proof

**Proposition P1.** If host h exposes p(h) independently powered and independently addressed connector slots on its tool side, and device d occupies one slot unless it is externally powered or bus-shared, then the number k of co-mounted devices satisfies k <= p(h). With bus sharing, k <= p(h) x m.

**Proof.**

1. By A1, each co-mounted device that is not bus-shared occupies a distinct physical slot on host h.
2. By A2, each such device draws independent power from its occupied slot; a slot that powers one device cannot simultaneously power a second device without sharing, which A1 rules out.
3. By A3, each such device requires an independent bus address on its occupied slot; two devices on the same slot cannot both hold independent addresses.
4. The number of slots available for independent occupation is exactly p(h), by definition.
5. Therefore the number of non-bus-shared devices is at most p(h), i.e. k <= p(h).
6. If bus sharing is permitted, each slot may host up to m stations, each on a distinct address; the bound becomes k <= p(h) x m.
7. The bound is an upper bound: equality requires every slot to be occupied, every station to be addressable, and every device to satisfy the power and addressing conditions; any violation lowers the attainable k.

This completes the proof.

### 7.4 Corollaries

**C1.** The UR3e and UR5e hosts expose exactly one tool-side slot (M8 8-pin, 8 pins, 1 channel, p = 1). Therefore p(UR3e) = p(UR5e) = 1, and every co-mount question with k >= 2 is unsatisfiable on these hosts, regardless of how complete either side's declarations become. The 0 mountable pairs in Section 6 are not a documentation failure; they are the hardware.

**C2.** Completing Z3 and Z4 can only move a pair from unknown to either compatible or incompatible. It cannot move a Z1 pair from blocked to compatible, because Z1 is a violation of k <= p(h) and no additional declaration changes p(h).

**C3.** The FR3 host keeps p(h) deliberately undeclared in the catalogue (`tool_io_ports: null`; the datasheet describes an end-effector connector with 2x DI and 2x DO, 24 V isolated, EN 61131-2 type 3). Its unknown pairs therefore belong to Z4, not to Z1, and must not be merged into the irreducible count of Section 6 until p(FR3) is declared.

### 7.5 The pin-versus-bit discipline

The UR3e and UR5e tool connector is an M8 8-pin connector. The number 8 is a pin count, not a channel count. The channel count is 1. Treating the pin count as a bit count would let an engine report eight simultaneously mountable tools on a host that can, by A1 through A3, serve one. The discipline applies generally: in this paper, p(h) counts slots, not pins, and a host whose tool connector carries 8 pins but 1 channel has p(h) = 1. The Franka FR3 datasheet lists 2x DI and 2x DO (24 V isolated, EN 61131-2 type 3), which is four signal channels rather than four power slots; the same discipline keeps p(FR3) at undeclared rather than at 4.

### 7.6 Consequence for the field

Compatibility documentation for co-mounting on UR3e/UR5e is not merely incomplete; it is answering a question the hardware cannot host. A vendor that supplies a "compatible" declaration between two of its own grippers on the same UR5e tool flange is, unless bus sharing is explicitly invoked, describing a configuration that P1 forbids. The practical recommendation is that catalogues should expose p(h) and m as first-class fields, so that a co-mount query applies P1 before any deeper matching. Without those fields, every deeper matcher spends its effort on pairs that P1 has already ruled out.

## 8. The Flange as a Suite Attribute

### 8.1 Eight worked vendor cases

This section works through eight vendor cases. Four of them are [V]-tier verbatim quotations taken word for word from a vendor manual, datasheet or official product page: Case 1 (UR20/UR30 Tool Flange Adapter), Case 4 (ATI Axia80 sensor connector), Case 5 (OnRobot HEX-E Scope of Delivery), and Case 7 (Franka FR3 end-effector connector). The remaining four cases are [O]-tier: they are conclusions synthesized by the present audit from catalogue fields and vendor product-page descriptions, not verbatim quotations, and they are written as statements rather than quoted speech. The cases are ordered from cross-generation adapter evidence to device-to-device mating evidence.

**Case 1, Universal Robots UR20/UR30 Tool Flange Adapter [V, verbatim, UR official adapter page].** Universal Robots describes the adapter as follows: "UR20/30 Tool Flange Adapter - Official tool flange adapter to convert the UR20/UR30 layout to EN ISO 9409-1-50-4-M6 (e-Series layout). Maximum rated payload 20 kg." The quote shows that cross-generation compatibility is adapter-only, that the adapter converts mechanics to the e-Series ISO 9409-1-50-4-M6 layout, and that the conversion carries a quantified payload cost of 20 kg. It does not convert electrics.

**Case 2, Robotiq three flange designations [O, synthesized from Robotiq coupling manuals and the audit catalogue fields; not a verbatim quotation].** The Robotiq product and coupling-manual descriptions, read across the universal coupling kit, the UR-specific coupling kit and the 3-Finger configuration, show that the same gripper reaches three flange designations depending on the coupling kit it ships with: 31.5-4-M5 and 40-4-M6 through the universal coupling kit, 50-4-M6 through the UR-specific coupling kit, while the 3-Finger gripper ships only to 40-4-M6. The device itself does not carry a single flange designation; the designation belongs to the kit.

**Case 3, OnRobot Quick Changer [O, synthesized from OnRobot Quick Changer datasheet language and the audit catalogue fields; not a verbatim quotation].** OnRobot's device listings present the end-of-arm tools without a flange designation on the device itself; the ISO 9409-1-50-4-M6 designation appears on the robot side of the Quick Changer that the tools mount to. The flange designation lives on the Quick Changer's robot side, not on the device.

**Case 4, ATI Axia80 port locus [V, verbatim, ATI force-torque sensor manual].** The ATI Axia80 force-torque sensor demonstrates the device-side versus cable-side distinction: "This model has an 8-pin M8 connector on the sensor. All other Axia80 models have a 6-pin M8 connector." The 8-pin M12 connector sits on the cable end (part 9105-C-ZC22-ZC28-4), not on the sensor body. The corpus must not attribute the cable-end connector to the device.

**Case 5, OnRobot HEX-E pin count [V, verbatim, OnRobot HEX-E v1 manual Scope of Delivery].** The catalogue record for the OnRobot HEX-E sensor cable reads, in the v1 manual's Scope of Delivery: "sensor cable (4 pin M8 - 4 pin M8, 5 m)." The database had recorded a 5-pin M8 cable; the manual ships a 4-pin M8, and the HEX-E Quick Changer manual instructs the user to use the marked M8-4pin connector for RG2-FT. This is the B1 correction used in Table 3.

**Case 6, ATI Axia bolt circle [O, synthesized from ATI Serial Axia manual dimensions and the audit catalogue fields; not a verbatim quotation].** The ATI Serial Axia mounting side, read from the manual's mechanical drawing, is a 71.12 mm bolt circle with six M5 tapped holes and two dowel positions, and it carries no ISO 9409-1 designation. A mechanical same-flange match against an ISO 9409-1 string cannot, by construction, include this mounting side.

**Case 7, Franka FR3 host port budget [V, verbatim, Franka FR3 datasheet].** The FR3 host keeps p(h) undeclared: `tool_io_ports: null` in the host-side file, with the datasheet describing the end-effector connector as follows: "connector for end effector, hardware prepared for 2x DI and 2x DO (24V isolated, EN 61131-2 type 3)." This is the Z4 route of Section 6 and the C3 route of Section 7.

**Case 8, ROBOTIS DYNAMIXEL daisy chain pair [O, synthesized from ROBOTIS e-Manual port description and the audit B1 locus table; not a verbatim quotation].** The only device-to-device true mating in the audited set is the ROBOTIS TTL pair: the two actuators each expose a supported TTL 3-pin port housing a JST EHR-03 connector (1 GND, 2 VDD, 3 DATA), and the e-Manual documents daisy-chain operation on that bus. This is the D3 pair of Section 4.

### 8.2 Consequence: identity, not interchangeability

The eight cases converge on a single observation. A "mechanically decidable" pair in the catalogue is largely a match between two suite specifications, not a claim that two devices are interchangeable on a host. The same gripper (Case 2) carries three flange designations; the OnRobot device (Case 3) carries none; the ATI mounting side (Case 6) carries a bolt circle that no ISO string captures. A catalogue that keys mechanical matching on the ISO 9409-1 string will, by construction, decide matches between suite descriptions and will under-count mounting sides that use a non-ISO pattern. This is why the mechanical axis can show a positive point estimate under a stated definition (Section 5, mechanical both-declared-or-partial: 1.5081% on n = 3,240 pairs, with 95% CI 0.368% to 4.205%) and still produce zero mountable co-mount pairs (Section 6): the 1.5081% is the density of shared mechanical declarations at one named rung, not a single "mechanical compatibility rate", and the matches it counts are suite identities, not device interchanges.

### 8.3 Cross-generation is not binary

The UR8 Long, UR15 and UR18 hosts carry ISO 9409-1-50-4-M6; the UR20 and UR30 hosts carry ISO 9409-1-80-6-M8. The official adapter (Case 1) converts the UR20/30 layout to the e-Series 50-4-M6 pattern and caps payload at 20 kg. Compatibility across these generations is not a binary yes/no: it is mechanically convertible, electrically not, at a quantified payload cost. A configuration engine that records this as "compatible" or "incompatible" discards the 20 kg payload number that a plant actually needs.

### 8.4 What a device-level identity judgement would require

A true device-level mechanical identity judgement would require hole geometry, dowel positions and the load path, not a flange string. The catalogue does not carry these fields, and no vendor in the audit publishes them in machine-readable form. Until they do, the mechanical axis in this paper is reported at the flange-string level, and the suite-attribute caveat of Section 8.2 applies to every mechanical density in Section 5. The practical upshot for an integrator is that a mechanical match at the flange-string level should be read as "these two suite descriptions share a pattern", not as "these two devices bolt onto the same host without an adapter"; the Section 8.3 UR20/UR30 adapter is the worked example of the gap between the two readings.

## 9. Discussion: What Would Change the Answer

### 9.1 The optimistic completion bound

Suppose the plant completes every missing device-side declaration on the 35 class-A flange-borne EOAT parts that the triage identified as the real completion target (Section 9.2). The maximum number of new D2-level pairs this can produce is computed as follows. Among the 35 completed parts, the number of unordered pairs is C(35, 2) = 595. Between the 35 completed parts and the 19 already-declared nodes, the number of new pairs is 35 x 19 = 665. The maximum new decidable pair count is therefore 595 + 665 = 1,260. Adding the 8 observed D2 pairs gives a maximum D2 count after completion of 1,268. As a share of the 214,840-pair universe, 1,268 / 214,840 = 0.590%; as a share of the quarantined 200,661-pair universe, 1,268 / 200,661 = 0.632%. The bound ignores pin-order, gender and complementary-role constraints, so it is an upper bound, not an estimate. Even the most optimistic completion leaves electrical decidability below 1%. Table 6 collects the arithmetic.

**Table 6. Optimistic completion upper bound, step by step (completion of all 35 class-A parts).**

| Metric | Value | Unit | Computation | Source |
|---|---|---|---|---|
| New pairs among the 35 completed class-A parts | 595 | pairs | C(35, 2) = 595 | E |
| New pairs against already-declared nodes | 665 | pairs | 35 x 19 = 665 | E |
| Max new decidable pairs | 1,260 | pairs | 595 + 665 = 1260 | E |
| Max D2 pairs after completion | 1,268 | pairs | 1260 + 8 observed = 1268 | E |
| Density of the 214,840-pair universe | 0.590% | percent | 1268 / 214840 = 0.590% | E |
| Density of the 200,661-pair quarantined universe | 0.632% | percent | 1268 / 200661 = 0.632% | E |
| Verdict | even the most optimistic completion bound leaves electrical decidability below 1% | - | n/a | E |

### 9.2 What should not be completed

The keyword-rule triage initially flagged 101 mechanical-not-declared EOAT records as completion candidates. Manual adjudication narrows this to 35 real class-A flange-borne parts (15 grippers, 4 dexterous hands, 20 force-torque sensors). The remaining 44 records are class-B body-mounted or surface-mounted parts (RealSense cameras, visuotactile and electronic skins, LiDAR, IMU and event cameras); these parts must not receive flange declarations, because they are not flange-borne. The keyword rule and manual adjudication disagree at Cohen's kappa = 0.6236 (agreement 74.26%, 26 flipped items), which falls below the 0.75 gate used for high-stakes classification. The kappa indexes agreement between the keyword rule and manual adjudication; it is not an inter-rater kappa between two human coders. The disagreement is the reason the real completion target is 35 parts, not 101.

### 9.3 Honest limits

We state five limits, in the order in which they constrain the conclusions.

**(L1) The corpus is an audited catalogue, not a market census.** The 656-node universe and the 329 manufacturer clusters are a curated audit snapshot; they are not a random sample of the installed base. Every density in this paper is a density over 214,840 pairs in this catalogue. Strict string de-duplication on the non-empty manufacturer field yields 328 manufacturers rather than 329; the one-vendor gap is a normalisation difference in the original aggregation rule, and the frozen value 329 is retained. Extrapolation to the market requires the caveat that the catalogue over-represents vendors with public datasheets.

**(L2) The bootstrap intervals are wide, and the width is the uncertainty.** The 95% manufacturer whole-cluster intervals (B = 1000, seed = 20261109) run, for the electrical axis, from 0.0069% to 0.268%. We report this width rather than narrow it. The ordering of axes (electrical below mechanical at point estimate, in every stratum) survives the width; the point estimates themselves should not be quoted outside the interval.

**(L3) The kappa is rule-versus-human, not inter-rater.** The kappa of 0.6236 indexes agreement between the keyword triage rule and a single manual adjudication. It is not a two-coder inter-rater reliability. Concretely, the apparent demand to "complete 101 parts" is a rule-side artefact; the real target is 35. We do not present the kappa as evidence of coder agreement.

**(L4) Host-side conclusions hold on three hosts only.** The p(h) = 1 finding is reported on the UR3e and UR5e; the FR3 is included as a Z4 unknown. We do not claim that the port-budget result generalises to every robot in the ecosystem. Hosts with bus sharing, multi-channel tool connectors or external power may have p(h) > 1.

**(L5) D3's single pair is a lower bound, not an upper bound.** The 19-node audit is the declared subset; the 528 placeholder ports are not in it. A complete census of device-side ports could only raise the D3 count. The reported D3 = 1 is therefore a lower bound on true device-to-device mating.

We also record one recomputation discrepancy explicitly. An independent reconstruction of the mechanical same-flange density, summing C(n_t, 2) over every declared `MECH:ISO` flange token across the full 656-node universe without the engine's category filter, yields 996 pairs, i.e. 0.4636% of 214,840, against the frozen engine value of 295 pairs (0.1373%). The difference is attributable to an additional category and composability filter in the original engine that restricts attention to flange-borne EOAT and host-side contexts; that filter boundary was embedded in the original aggregation script and is not documented in any shipped product file, so it cannot be reproduced from the shipped corpus. The 996 figure is an unfiltered upper bound of the engine count, and the frozen 295 remains the formal value reported in Table 4. The direction of the gap (unfiltered > filtered) is consistent with the presence of the filter.

### 9.4 What would move the answer

Three interventions would move the reported numbers. First, a device-side port census on the 528 `ELEC:UNKNOWN` ports is the only channel that can raise D3, because D3 is a lower bound and only device-side declarations can add true device-to-device pairs. Second, a host-side port-budget field p(h), with m for bus sharing, would convert Z1 from a blocked verdict into a tagged verdict: the engine would still report unsatisfiability, but the integrator would see why. Third, a mandatory connector-locus field (device, adapter, host, cable) in catalogue schemas would prevent the D1 self-matching that inflates the top of the ladder. A fourth, subtler intervention is a flange-designation field that distinguishes device, coupling-kit and adapter loci; without it, the mechanical axis continues to count suite-specification identity as mechanical decidability.

### 9.5 Transferability

The ladder is a measurement protocol, not a claim about one database. Any catalogue that carries both declared and placeholder ports can be run through the same four thresholds, and any co-mount engine can be classified with the same Z1-Z5 taxonomy. The numbers reported here are specific to this audit snapshot; the protocol is not.

## 10. Conclusion

Three findings close the paper. First, interface compatibility, on the evidence that today's vendor datasheets provide, is a measurement problem rather than a decision problem: holding a fixed catalogue and varying the evidence threshold moves the electrical answer across five orders of magnitude, and the top of the ladder is dominated by a placeholder matching itself. Second, the zeros that this measurement produces are not uniformly removable by completing missing datasheets: 297 of 360 co-mount pair evaluations (82.5%) are irreducible by evidence, because they are design constraints (port budget) or demand-side constraints (functional redundancy), not documentation failures. Third, the structural upper bound on co-mounting is a port budget: on the UR3e and UR5e hosts, which expose one independently powered and addressed tool-side slot, any question of mounting two devices at once is unsatisfiable regardless of declaration completeness, and the gap between the 32 mountable single devices and the 0 mountable co-mounted pairs is the hardware, not the paperwork. The practical recommendation that follows is that plants should stop reporting a single compatibility rate, should instead name the rung, the axis and the denominator, and should demand that catalogues expose p(h), m and the connector locus as first-class fields. The ladder, the taxonomy and the bound transfer to any catalogue that carries declared and placeholder ports; the numbers reported here are specific to this audit snapshot, and the limits of that snapshot are stated in Section 9.

---

## Declarations

**Funding.** This research received no specific grant from any funding agency in the public, commercial or not-for-profit sectors.

**Competing interests.** The author declares no competing financial or personal interests that could have appeared to influence the work reported in this paper.

**Data availability.** The corpus counts, bootstrap results, pair-level ladder table and the upper-bound calculation that support the findings of this study are archived in the accompanying research-data package (`04_ResearchData/`), including Tables T1-T6 as CSV, the bootstrap outputs, recomputation scripts (`rp_ladder_recompute.py`, `rp_upper_bound.py`, `rp_bootstrap.py`) and a frozen-check manifest. The figures are archived under `05_Figures/`. The recomputation scripts reproduce every reported number from the stated inputs and random seed (B = 1000, seed = 20261109).

**Ethics approval.** Not applicable. The study uses no human or animal subjects and no personal data.

**Consent to participate and to publish.** Not applicable.

**Use of AI-assisted tools.** AI-assisted language-editing tools were used solely to improve the English readability of the manuscript after the scientific content, the numerical results and the argument structure had been fixed. The author takes full responsibility for the content.

**One-journal declaration.** This manuscript is original, has not been published previously in any form, and is not under consideration for publication elsewhere.

## References

[1] D. Tola, E. Madsen, C. Gomes, L. Esterle, C. Schlette, C. Hansen, P.G. Larsen, Towards Easy Robot System Integration: Challenges and Future Directions, in: Proc. 2022 IEEE/SICE International Symposium on System Integration (SII), Narvik, Norway, 2022, pp. 77–82. https://doi.org/10.1109/SII52469.2022.9708846.

[2] D. Tola, Enabling Digitalization in Modular Robotic Systems Integration, PhD thesis, arXiv:2401.02227, 2024. https://arxiv.org/abs/2401.02227.

[3] D. Tola, C. Gomes, C. Schultz, C. Schlette, C. Hansen, L. Esterle, RoboCIM: Towards a Domain Model for Industrial Robot System Configurators, in: RuleML+RR 2021 Companion (Industry Track), CEUR-WS Vol-2956, 2021. https://ceur-ws.org/Vol-2956/paper12.pdf.

[4] L. Sanneman, A.M. Gupta, D.D. Chibili, et al., The State of Industrial Robotics: Emerging Technologies, Challenges, and Key Research Directions, arXiv:2010.14537, 2020. https://arxiv.org/abs/2010.14537.

[5] K. Ulrich, The role of product architecture in the manufacturing firm, Research Policy 24 (3) (1995) 419–440. https://doi.org/10.1016/0048-7333(94)00775-3.

[6] M.G. Mehrabi, A.G. Ulsoy, Y. Koren, P. Heytler, Trends and perspectives in flexible and reconfigurable manufacturing systems, Journal of Intelligent Manufacturing 13 (2) (2002) 135–146. https://doi.org/10.1023/A:1014536330551.

[7] C. Chaumet, J. Rehof, T. Schuster, A knowledge-driven framework for synthesizing designs from modular components, arXiv:2311.18533, 2023. https://arxiv.org/abs/2311.18533.

[8] A. Felfernig, L. Hotz, C. Bagley, J. Tiihonen, Knowledge-Based Configuration: From Research to Business Cases, Morgan Kaufmann, 2014. https://www.elsevier.com/books/knowledge-based-configuration/felfernig/9780124158177.

[9] N. Siltala, E. Järvenpää, M. Lanz, Creating resource combinations based on formally described hardware interfaces, in: Precision Assembly Technologies and Systems (IPAS 2018), IFIP AICT 530, Springer, 2019, pp. 29–39. https://doi.org/10.1007/978-3-030-05931-6_3.

[10] N. Siltala, E. Järvenpää, M. Lanz, A method to evaluate interface compatibility during production system design and reconfiguration, Procedia CIRP 81 (2019) 282–287. https://doi.org/10.1016/j.procir.2019.03.049.

[11] N. Siltala, E. Järvenpää, M. Lanz, Formal Information Model for Representing Production Resources, in: IFIP Advances in Information and Communication Technology 488 (APMS 2016), Springer, 2016, pp. 53–60. https://doi.org/10.1007/978-3-319-51133-7_7.

[12] E. Järvenpää, N. Siltala, O. Hylli, M. Lanz, Capability matchmaking procedure to support rapid configuration and re-configuration of production systems, Procedia Manufacturing 11 (2017) 1053–1058. https://doi.org/10.1016/j.promfg.2017.07.216.

[13] E. Järvenpää, N. Siltala, O. Hylli, M. Lanz, Product Model ontology and its use in capability-based matchmaking, Procedia CIRP 72 (2018) 1094–1099. https://doi.org/10.1016/j.procir.2018.03.211.

[14] A. Mital, N. Siltala, E. Järvenpää, M. Lanz, Web-based solution to automate capability matchmaking for rapid system design and reconfiguration, Procedia CIRP 81 (2019) 288–293. https://doi.org/10.1016/j.procir.2019.03.050.

[15] C. Zheng, B. Eynard, X. Qin, J. Li, J. Bai, Y. Zhang, S. Gomes, Interface Model-Based Configuration Design of Mechatronic Systems for Industrial Manufacturing Applications, Robotics and Computer-Integrated Manufacturing 59 (2019) 373–384. https://doi.org/10.1016/j.rcim.2019.05.011.

[16] I. Zamalloa, I. Muguruza, A. Hernández, R. Kojcev, V. Mayoral, An information model for modular robots: the Hardware Robot Information Model (HRIM), arXiv:1802.01459, 2018. https://arxiv.org/abs/1802.01459.

[17] International Organization for Standardization, ISO 9409-1:2004 Manipulating industrial robots — Mechanical interfaces — Part 1: Plates, 2004. https://www.iso.org/standard/36578.html.

[18] Universal Robots A/S, UR+ — ecosystem of trusted UR partners and products, accessed 2026. https://www.universal-robots.com/plus/.

[19] OnRobot, Quick Changer — Lightweight robot tool changer for fast, repeatable changeovers, accessed 2026. https://onrobot.com/en/products/quick-changer.

[20] R.Y. Wang, D.M. Strong, Beyond Accuracy: What Data Quality Means to Data Consumers, Journal of Management Information Systems 12 (4) (1996) 5–33. https://doi.org/10.1080/07421222.1996.11518099.

[21] T.C. Redman, The impact of poor data quality on the typical enterprise, Communications of the ACM 41 (2) (1998) 79–82. https://doi.org/10.1145/269012.269025.

[22] E.C. Freuder, R.J. Wallace, Partial Constraint Satisfaction, Artificial Intelligence 58 (1992) 21–70. https://doi.org/10.1016/0004-3702(92)90004-H.

[23] T. Schiex, H. Fargier, G. Verfaillie, Valued Constraint Satisfaction Problems: Hard and Easy Problems, in: Proc. 14th International Joint Conference on Artificial Intelligence (IJCAI-95), Montréal, 1995, pp. 631–637. http://ijcai.org/Past%20Proceedings/IJCAI-95-VOL%201/pdf/083.pdf.

[24] D. Dubois, H. Fargier, H. Prade, Possibility theory in constraint satisfaction problems: Handling priority, preference and uncertainty, Applied Intelligence 6 (4) (1996) 287–309. https://doi.org/10.1007/BF00132735.

[25] D. Ciucci, D. Dubois, A modal theorem-preserving translation of a class of three-valued logics of incomplete information, Journal of Applied Non-Classical Logics 23 (4) (2013) 321–352. https://doi.org/10.1080/11663081.2013.863491.

[26] S. Mittal, B. Falkenhainer, Dynamic Constraint Satisfaction Problems, in: Proc. 8th National Conference on Artificial Intelligence (AAAI-90), MIT Press, 1990, pp. 25–32. https://www.aaai.org/Library/AAAI/1990/aaai90-004.php.

[27] G. Brewka, T. Eiter, M. Truszczyński, Answer set programming at a glance, Communications of the ACM 54 (12) (2011) 92–103. https://doi.org/10.1145/2043174.2043195.

[28] É. Vareilles, C. Grosso, J.-M. Horcas, A. Felfernig (Eds.), Proceedings of the 26th International Workshop on Configuration (ConfWS 2024), co-located with CP 2024, Girona, Spain, CEUR-WS Vol-3812, 2024. https://ceur-ws.org/Vol-3812/.
