# Response to Reviewers — Prepared Replies

Internal working document. These are anticipated reviewer comments drafted against the actual weaknesses of the manuscript, not against generic advice. Each reply cites the frozen numbers in `00_Spec/FROZEN_NUMBERS.json` verbatim. No reply is to be sent as written; the final response letter will follow the reviewer's actual wording.

---

## R1. The corpus is an audit catalogue, not a market census. 656 composable nodes across 329 vendors cannot support an ecological claim.

We agree, and we have bounded the claim accordingly. The manuscript states in §3 that the corpus is an audit snapshot of public vendor listings — 868 entities, 656 composable nodes, 214,840 unordered pairs across 329 vendors — and we do not extrapolate a population-level prevalence. What we do claim is internal to the snapshot: that decidability collapses by 5 orders of magnitude between D0 (64.764%) and D3 (0.00047%), and that 528 of 553 electrical ports carry `ELEC:UNKNOWN`. Both numbers are reproducible from the archived scripts and inputs. The honest-boundary clause in §9.1 states explicitly that external validity requires a second, independently built catalogue.

---

## R2. The confidence interval on the electrical axis is absurdly wide (0.0069%–0.268%). The point estimate 0.0796% is not useful.

We agree that the CI is wide, and we report it rather than hiding it. The cluster bootstrap is by manufacturer (329 clusters, B = 1000, seed = 20261109), and the electrical axis has only 171 declared pairs, so a single large vendor can move the point estimate substantially. The point estimate is not the headline; the headline is the *ordering*: at every definition level the electrical point estimate lies below the mechanical point estimate, by 17–230-fold. The CI overlap the reviewer is concerned about (mechanical lower bound 0.0132% vs. electrical upper bound 0.268%) is discussed explicitly in §5, and we deliberately do not claim "electrical is always below mechanical" — we claim the point estimates are ordered.

---

## R3. κ = 0.6236 is keyword-rule versus manual adjudication, not two independent human coders. You cannot call this inter-rater reliability.

We cannot, and we do not. The manuscript states verbatim that "the 0.6236 is keyword-rule versus manual adjudication, not inter-rater; it falls below the 0.75 gate." The consequence is deliberately drawn: because the automated keyword rule agrees with manual adjudication at only 74.26% and flips 26 items, the 101 mechanically-undeclared EOAT are not all recoverable by a script. The true backlog is 35 class-A flange-borne parts, not 101. Reporting κ as rule-vs-human is a lower bound on how much a second human rater would add, and we treat it as such in §9.

---

## R4. The host-side result is built on three robots (UR3e, UR5e, FR3). You generalise the port-budget proposition to the whole EOAT ecosystem.

We do not generalise. The proposition P1 is a counting argument: if host h exposes p(h) independently powered and independently addressed slots, and a device occupies one slot unless externally powered or bus-shared, then k ≤ p(h). The corollary C1 applies only to UR3e and UR5e, both with p = 1, and C3 explicitly leaves FR3 as p undeclared (Z4, not Z1). The manuscript states in §9.4 that the host-side result holds only on these three platforms. Extending to ABB, Fanuc, KUKA or Yaskawa requires measuring their tool-side I/O, which is future work and is labelled as such.

---

## R5. D3 has exactly one pair. A ladder whose top rung has n = 1 is not a ladder; it is a worked example.

This is the honest-boundary clause §9.5, stated verbatim in the manuscript. The D3 figure of 1 pair (0.00047%) is a *lower bound* on true device-to-device mating, because the audited 19 nodes contain only 4 device-side ports (ACT-001, ACT-002, ACT-003, ACT-016) and no end-effector or sensor in the audited set owns a true device-side port. The D3 number is reported as the yield after connector-locus correction (ACT-001 × ACT-002, DYNAMIXEL TTL daisy chain), not as an estimate. We make no asymptotic claim from it.

---

## R6. Why not recompute the ladder on external parts — HRIM, UR+ — to see if the gap is specific to your catalogue?

We did, and the external corpora make the gap worse, not better. HRIM (AcutronicRobotics, archived 2019-08-07, 71 stars) ships 21 class models but only 3 instance datasheets and zero mechanical-mating fields and zero connector-level electrical fields. UR+ lists 528 products and supplies 0/528 interface-mating fields. The §3.5 conclusion is that the interface-field absence is ecosystem-level, not a quirk of our catalogue. We did not include HRIM or UR+ in the pair denominator because they do not contain the mating fields the ladder requires; doing so would have produced structurally undefined pairs.

---

## R7. Proposition P1 (k ≤ p(h)) is trivial. It is just a slot-counting argument dressed up as a theorem.

The counting arithmetic is simple, but its consequence is not. p(UR3e) = p(UR5e) = 1 implies C1: every k ≥ 2 co-mount question on these hosts is unsatisfiable regardless of how complete either side's declarations are. This converts a "we found zero mountable pairs" empirical result into a structural upper bound — the maximum optimistic completion bound is 1,268 new pairs, i.e. 0.590% of the 214,840 denominator. The point of P1 is not that counting is hard; it is that no amount of catalogue completion can raise k above p(h) on these hosts. The proof is written out line-by-line in §7 so that a reviewer can check the assumptions (independently powered, independently addressed, non-bus-shared) and see exactly where they fail.

---

## R8. If the same gripper reaches three different flange designations (31.5-4-M5, 40-4-M6, 50-4-M6) depending on the coupling kit, then "identity" of a device is not well-defined. Your D1 pairs are not really pairs of devices.

This is exactly the §8 finding, stated as a result rather than as a defect. The flange is a suite attribute, not a device attribute: Robotiq's same gripper reaches three flange sizes through the universal vs. UR-specific coupling kit; OnRobot devices carry no flange designation at all and mate to a Quick Changer; ATI's mounting side is a 71.12 mm bolt circle with 6 × M5 and no ISO designation at all. The D1 pairs are therefore pairs of *catalogue nodes*, not pairs of interchangeable physical devices, and the manuscript says so explicitly. The consequence is that "device identity" in the EOAT market is a coupling-kit-level fact, not a device-level fact — which is itself one of the measured contributions.

---

## R9. Your catalogue is private and not publicly archived. Other researchers cannot reproduce the 656-node count.

We agree this is a real limitation. What we archive in `04_ResearchData/` is the *derived* layer: pair counts per ladder level, bootstrap rows, the 11 D1 pairs with their engine tokens, the 360 co-mount evaluations, and the recomputation scripts. The underlying vendor listings were pulled from public vendor web pages in 2026 and are copyright-attributable to the vendors; we do not republish their product pages. A reviewer can reproduce the ladder from the archived tables and the scripts; a researcher who wants to rebuild the input corpus from scratch can do so from the cited vendor datasheets, and §3 lists the provenance tier [V]/[O]/[E] for every number. We have flagged this as the single largest reproducibility gap in §9.

---

## R10. You did not supplement the 44 class-B body/surface-mounted parts. Why not?

Because they are not end-arm interfaces. Class B contains 44 parts that mount to the robot body or to a surface (including 5 RealSense cameras), and 22 generic placeholders. Adding them to the flange-borne denominator would mix two physical mounting regimes and inflate the electrical-port count with parts that never reach the tool flange. The 35 class-A flange-borne parts (15 grippers, 4 dexterous hands, 20 force-torque sensors) are the backlog; the upper-bound calculation in §9.2 completes only those 35, yielding C(35,2) = 595 pairs plus 35 × 19 = 665 pairs against the 19 already-declared nodes, i.e. 1,260 new pairs on top of the 8 observed. Including class B would not move the conclusion; it would change the denominator.

---

## R11. A single-author paper with no second coder and no experimental validation will not convince a robotics reviewer.

We have not claimed an experimental result. The paper is a corpus measurement plus a counting proposition, and the abstract says so in the first sentence: it does not ask whether a given pair is compatible, it asks how much of the question is decidable at what evidential price. The numbers that would benefit from a second coder (the 101 undeclared EOAT triage) are already flagged via κ = 0.6236 as rule-vs-human, and the manuscript reports the reduced backlog of 35 rather than the optimistic 101. We do not present a hardware mating test because P1 is satisfied by inspection of the host tool-side I/O (UR3e/UR5e M8 8-pin, p = 1; FR3 p undeclared), and running one would not change k ≤ p(h).

---

## R12. Your upper-bound scenario (1,268 pairs, 0.590%) is called "optimistic". On what assumptions is it optimistic?

It is optimistic in three directions simultaneously. First, it completes all 35 class-A parts to fully declared flanges and ports. Second, it ignores pin-order, gender and complementary-role constraints — i.e. it counts a pair as potentially D2 merely because both ends declare a port, without checking that the pin order or gender matches. Third, it treats every new node as compatible with every already-declared node. Removing any of these assumptions lowers the bound. The manuscript states the arithmetic explicitly in §9.2: C(35,2) = 595, plus 35 × 19 = 665, plus the 8 observed, = 1,268 pairs, i.e. 0.590% of the 214,840 denominator. Even on these generous assumptions, electrical decidability stays below 1%.

---

## R13 (reserve). The 11 D1 pairs collapse onto 8 engine tokens, and three are cable-end tokens. Is D1 really a separate level, or just a re-run of D0 with placeholders stripped?

D1 is the level at which `ELEC:UNKNOWN` is excluded as a match token. D0 counts 139,139 pairs (64.764%), of which 139,128 (99.992%) are `UNKNOWN × UNKNOWN` self-matches driven by the placeholder mechanism. Stripping the placeholder token leaves 11 pairs (0.00512%), which collapse onto 8 engine tokens because Robotiq 2F-85 is duplicated as an entity and three pairs share the same cable-end token. The ratio D0/D1 = 12,650× is the placeholder-mechanism effect, not a measurement noise: it is exactly the number we want to expose. We keep D1 as its own level because it answers a different question ("after we stop counting unknown as compatible, how much remains?") than D0 ("what does a naive string match say?").
