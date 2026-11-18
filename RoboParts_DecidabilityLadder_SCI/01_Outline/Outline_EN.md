# Outline (EN) — How Compatible Is "Compatible"?

Target type: research article, measurement + formal proposition. Length target ~7,500 words EN.

1. Introduction
   1.1 Why robot system integration still depends on human integrators (Tola et al. 2022, verbatim quote; Sanneman et al.; Schou et al.)
   1.2 The implicit move: compatibility as a decision problem (configurators, product-data systems, HRIM as the canonical hardware information model)
   1.3 What we actually measure: a 656-node audited catalogue, a 21-model standard tree, a 528-product marketplace
   1.4 Positioning: compatibility is a measurement problem, not a decision problem; and zeros have a structural upper bound
   1.5 Contributions (five, in order)

2. Related Work
   2.1 Robot configuration and system integration (Tola 2022; Tola arXiv 2401.02227; Siltala IPAS 2019; Zheng et al. RCIM 2019; Chaumet et al. Procedia CIRP/arXiv 2311.18533)
   2.2 Hardware/interface information models (HRIM, Zamalloa et al. arXiv 1802.01459; ISO 9409-1; UR+ marketplace)
   2.3 Partial constraints and three-valued decision logic (Sabin & Freuder 1996; Mittal & Falkenhainer AAAI-90; Ciucci & Dubois; ConfWS 2024)
   2.4 Gap: nobody has measured how the decidability rate moves as the evidence threshold moves, and nobody has bounded which zeros are structurally unavoidable

3. Corpus and Method
   3.1 The RoboParts catalogue (entities.json, morphology_graph.json, mechanical/electrical_interfaces.json, co_mount.json, robot_tool_side.json, compatibility.json, evidence_valuation.json) — 868 entities → 656 composable nodes → 214,840 unordered pairs; 329 vendors
   3.2 Provenance tags [V]/[O]/[E]; reproducibility scripts rp_b24.py / rp_b2v2.py / rp_ladder.py
   3.3 The four-level ladder D0–D3 (definition of each threshold)
   3.4 Three-axis measurement and whole-vendor cluster bootstrap (B=1000, seed=20261109)
   3.5 External censuses: HRIM full-tree and UR+ 528-product page
   3.6 PRISMA-ScR search record (databases, strings, dates, exclusions) — full table in 04_ResearchData

4. Results
   4.1 The ladder: 64.764% → 0.00512% → 0.00372% → 0.00047%; 99.992% of D0 is UNKNOWN×UNKNOWN; enumeration of the 11 D1 pairs (Fig. 1)
   4.2 Three-axis densities and CIs (Fig. 2); the electrical axis is the weakest under every definition, stratified statement
   4.3 The taxonomy of zeros Z1–Z5 on the 360-pair co-mount layer; Z1+Z5 = 297/360 = 82.5% not evidence-eliminable (Fig. 3)
   4.4 Proposition P1, proof, corollaries C1–C3; the p=1 fact for UR3e/UR5e; the p=null fact for FR3
   4.5 Flange as a kit property (Robotiq three flange labels; OnRobot Quick Changer; ATI 71.12 mm circle)
   4.6 Robustness: dedup sensitivity (645 nodes/207,690 pairs; <4% magnitude change); κ=0.6236 coding agreement
   4.7 External evidence: HRIM 21 class models / 3 instance datasheets / 0 mechanical fields / 0 connector fields; UR+ 0/528 interface fields

5. Discussion
   5.1 Why "fill the data" does not unlock co-mounting (C2 monotonic invariance)
   5.2 The de-facto UR standard is generation-bounded and pays a 20 kg payload penalty (B1 loop 4)
   5.3 Field-name contamination as a systemic failure mode (protocol names and cable topology written into connector fields; B1 loops 1–3)
   5.4 The optimistic upper-bound calculation: even filling the real 35-part backlog, D2 density remains <1% (reproducible computation)
   5.5 Relation to partial-constraint literature: unknown is not symmetric; Z3/Z4 are decidable-after-evidence, Z1/Z5 are decidable-now

6. Threats to Validity (the five honest boundaries)

7. Conclusion

8. References

Appendices: A. Data dictionary and file manifest; B. The 11 D1 pairs and 8 D2 pairs; C. Bootstrap procedure; D. PRISMA-ScR record; E. Open items (legal affiliation name; CN byline; NOT_VERIFIED fee pages)
