# Response-to-Reviewer Preparation (anticipated)

Drafted against the expected reviewer lines of attack. Each entry: anticipated comment, our position, where in the manuscript it is already addressed.

**R1. "Your 64.764% is inflated by placeholders; everyone knows D0 is meaningless."**
Agreed — that is the point. The ladder exists precisely to show that the loosest common reporting practice (label equality) reports a number five orders above the most stringent evidence rule. We do not claim D0 is meaningful; we measure the gap D0→D3 and identify its mechanism (528/553 placeholders). Addressed in §4.1 and Fig. 1.

**R2. "The electrical CI overlaps the mechanical CI; you cannot call electrical the weakest axis."**
We state this stratified: mechanical lower CI 0.0132% and electrical upper CI 0.268% do numerically overlap; the claim is that the electrical point estimate is one to three orders below the mechanical point estimate under every definition, with wide cluster intervals reflecting vendor heterogeneity. We do not claim the CIs do not overlap. Addressed in §4.2 and Fig. 2.

**R3. "κ = 0.6236 is below 0.75; your backlog classification is unreliable."**
We agree and report it honestly as rule-versus-human agreement, not two-human agreement. The consequence we draw is conservative: the real backlog is 35 parts, not 101, and the coding rule must be fixed (structural three-question decision tree) before any larger fill. Addressed in §4.6.

**R4. "UR3e/UR5e p=1 is trivially obvious; P1 is not a contribution."**
The contribution is not the observation p=1 but the formal statement that co-mount satisfiability is bounded by p(h) *independently* of data completeness, and the corollary (C2) that "fill the data" cannot unlock Z1 zeros. The triviality of p=1 on a single host is exactly what makes the bound easy to verify; the generalisation to bus-shared devices (k ≤ p(h)·m) is the non-trivial extension. Addressed in §4.4.

**R5. "HRIM is old/archived; censusing it is a straw man."**
HRIM remains the canonical open hardware information model and is still cited; the point is that its information layer was always communication (topics), never assembly. We also census the live 528-product UR+ marketplace, which is not archived and shows the same zero-interface-field result. Two independent sources, one old and one live. Addressed in §4.7.

**R6. "You have three hosts; generalising about co-mounting is overreach."**
Explicitly bounded in §6 (Threats to Validity) and in the host-side table: host-side conclusions hold only for UR3e/UR5e/FR3. We do not claim p(h) values for other arms; FR3's p is left null precisely because its datasheet does not state it.

**R7. "D3 = 1 pair is too thin to claim anything about true mating."**
We label D3 a lower bound on true mating, not an upper bound. The claim is about the *structure* of the ladder (how fast the count collapses as evidence tightens), not about the absolute true-mating rate. Addressed in §4.1 and §6.

**R8. "Why not just collect the missing data and re-run?"**
C2 answers this: filling Z3/Z4 moves unknown to compatible/incompatible but cannot move Z1 zeros, which are 82.5% of the layer. We also compute the optimistic upper bound on filling the real 35-part backlog (D2 density stays <1%). Addressed in §4.6 upper-bound calculation and §5.

**R9. Missing DOI / venue confirmation for secondary references (Siltala, Ciucci & Dubois, ConfWS).**
These are carried as [O] secondary references with working URLs (HAL/arXiv/known venue); we will upgrade them to exact citation with DOI in the camera-ready proof, and they are flagged in the reference list. No DOI is fabricated.

**R10. "The 11 D1 pairs look like duplicates of the same Robotiq gripper."**
Correct, and we say so: three of the 11 are the same 2F-85 duplicate entity plus a shared coupler; the dedup sensitivity (645 nodes/207,690 pairs, 295→294, D2 unchanged, <4% magnitude change) shows the density conclusions are unaffected. Addressed in §4.6.
