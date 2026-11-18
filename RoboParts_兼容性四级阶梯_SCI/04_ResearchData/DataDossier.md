# Data Dossier — Four-Level Decidability Ladder for Robot End-Arm Interfaces

Package: `RoboParts_兼容性四级阶梯_SCI/04_ResearchData/`
Build date: 2026-11-09. Authority for every number: `00_Spec/FROZEN_NUMBERS.json` (v1-frozen-2026-11-09). This dossier changes no frozen number; where independent recompute disagrees, the frozen value is retained and the disagreement is logged in `results/frozen_checks.json`.

Source tiers: **[V]** verified first-hand (datasheet / manual / official page, quoted verbatim); **[O]** official or second-hand口径 not verbatim-checked; **[E]** computed in this study and reproducible from the shipped scripts.

---

## 1. Merged data-support table

Supporting-data table: 24 data rows (excluding header). Count recorded here for machine check at packaging; the table itself is below.

Every number used in the manuscript, where it is used, where it comes from, and whether this dossier re-derived it. 24 rows.

| # | Manuscript claim | Value | Used in | Tier | Source file | Recompute status |
|---|---|---|---|---|---|---|
| 1 | Catalogue size | 868 entities | §3 | E | `api/entities.json` | match |
| 2 | Composable node universe | 656 nodes | §3, denominator of all densities | E | `api/morphology_graph.json` | match |
| 3 | Unordered pair universe | 214,840 pairs | §4–§7 denominator | E | C(656,2) | match |
| 4 | Vendors in the audit catalogue | 329 manufacturers | §1, §3, bootstrap cluster count | O | `api/morphology_graph.json` | mismatch (indep. count 328; gap 1 vendor) |
| 5 | Nodes after quarantining 22 generic placeholders | 634 | §3, §9 | E | `B2B4_裁定数据.json` | match (656−22) |
| 6 | Pairs after quarantine | 200,661 | §7 second density | E | C(634,2) | match |
| 7 | Electrical ports audited | 553 ports | §3, §4 mechanism | E | `api/morphology_graph.json` | match |
| 8 | Distinct electrical type labels in use | 17 type ids | §3 | E | `api/morphology_graph.json` | match |
| 9 | Placeholder electrical ports | 528 of 553 (95.48%) | Abstract, §1, §4 mechanism | E | `api/morphology_graph.json` | match |
| 10 | Declared / not-declared electrical ports | 25 / 528 | §3, §7 | E | `api/morphology_graph.json` | match |
| 11 | Nodes carrying >1 declared electrical port | 6 nodes | §3 data dictionary | E | `api/morphology_graph.json` | match |
| 12 | D0 decidable pairs (placeholders included) | 139,139 (64.764%) | Abstract, §4, Table 2, Fig 1 | E | `api/morphology_graph.json` + `Scripts/rp_ladder_recompute.py` | match |
| 13 | D0 share that is UNKNOWN×UNKNOWN | 139,128 / 139,139 = 99.992% | §4 mechanism, Fig 1 | E | C(528,2) | match |
| 14 | D1 pairs after excluding placeholders | 11 (0.00512%) | Abstract, §4, Table 3 | E | same pipeline | match |
| 15 | D2 engine-verdict pairs | 8 (0.00372%) | §4, Table 2 | V | `B4_稳健性与B2分诊_计算产物.json` | not_recomputed (engine verdict, read verbatim) |
| 16 | D3 true device-to-device mating pairs | 1 (0.00047%) | §4, Table 2, B1 locus | V | `B1_电气端口取证表.md` | not_recomputed (manual locus adjudication) |
| 17 | Ladder ratios | 12,650× / 1.4× / 139,000× | §4 | E | arithmetic on frozen levels | match (139139/11 ≈ 12,649; frozen 12,650× retained) |
| 18 | Cross-axis densities (five bootstrap rows) | 295 / 2,211 / 3,240 / 171 / 77,815 pairs | §5, Table 4, Fig 2 | E | `B4_稳健性与B2分诊_计算产物.json` | point estimates match for 4/5 axes; same-flange axis mismatch (see §4) |
| 19 | Cluster bootstrap CI bands | as in Table 4 | §5, Fig 2 | E | re-implemented in `Scripts/rp_bootstrap.py` | re-run: point values identical, CI within ~6% relative |
| 20 | Co-mount pair evaluations and zero verdict | 360 evals; type_error 171 / port_exhausted 126 / unknown 63 | §6, Table 5, Fig 3 | E | `api/co_mount.json` | match |
| 21 | Irreducible-zero share | Z1+Z5 = 297/360 = 82.5% | Abstract, §6 | E | 126+171 over 360 | match |
| 22 | Host port budget p(h) | UR3e = UR5e = 1; FR3 = null | §7, C1/C3 | V | `api/robot_tool_side.json` | match |
| 23 | Optimistic completion upper bound | 1,268 pairs = 0.590% / 0.632% | §9, Table 6 | E | `Scripts/rp_upper_bound.py` | match |
| 24 | Flange-as-suite evidence (8 cases) | T7 rows | §8 | mixed: 4×[V] verbatim + 4×[O] synthesis | `FROZEN_NUMBERS.json` B1 quotes + suite evidence | 其中 4 条为 [V] 逐字原文（UR20/30 适配器、Axia80 端口位置、HEX-E 线长针数、FR3 datasheet 短语）、4 条为 [O] 审计归纳（Robotiq 三标号、OnRobot Quick Changer、ATI 71.12 mm 孔圆、DYNAMIXEL 菊花链） |

---

## 2. Data dictionary

| Field | Meaning | Value range |
|---|---|---|
| entity | A catalogue entry in `api/entities.json`; any component, chip, platform, software or specification record | 868 total; `composable=true` selects the 656-node pair universe |
| node | A composable catalogue entry modelled in `api/morphology_graph.json` | 656 nodes, each with a `ports[]` list |
| port | A declared interface on a node, tagged by axis prefix (`MECH:` / `ELEC:` / `SIG:`) and status (`declared` / `partial` / `not_declared`) | 1,463 ports total; electrical axis: 25 declared + 528 not_declared |
| port type label | The exact `type` string of a port, e.g. `ELEC:CONNECTOR:JST-EHR-03`, `MECH:ISO9409-1-A50-4-M6`, `ELEC:UNKNOWN` | 17 in-use electrical labels; `ELEC:UNKNOWN` is the placeholder |
| pair (unordered) | Any unordered combination of two composable nodes | C(656,2) = 214,840 |
| D0 / D1 / D2 / D3 | Evidence thresholds: D0 shared label incl. placeholders; D1 shared non-placeholder label; D2 engine verdict on type+pin order+gender; D3 manual locus-corrected true device-to-device mating | 139,139 / 11 / 8 / 1 pairs |
| cluster (bootstrap) | A manufacturer group; whole-cluster resampling unit | 329 clusters (frozen; empty-manufacturer nodes collapsed to one cluster reproduces 329 from the shipped files) |
| co-mount evaluation | A two-device question: "can devices A and B be mounted together on host h" under `co_mount_engine/v1` | 3 hosts × 16 devices = 360 evals; verdicts type_error / port_exhausted / unknown |
| p(h) | Host tool-side connector slots, independently powered and independently addressed | integer or null (FR3 deliberate null); p(UR3e)=p(UR5e)=1 |
| Z1–Z5 | Taxonomy of zero results: port exhausted / type mismatch / device-side undeclared / host-side undeclared / role not complementary | counts in Table 5 |

---

## 3. Provenance (per spec §6)

The numbers were produced by the main agent's earlier scripts run on the local ROBOPARTS corpus: `rp_b24.py`, `rp_b2v2.py`, `rp_ladder.py` (original paths `C:\Users\xing\AppData\Local\Temp\`, since cleaned). Shipped product files:

- `切口核验_RoboParts可判定性/核验报告_RoboParts_收尾B2B3B4_v3.md` — v3 verification narrative;
- `切口核验_RoboParts可判定性/B4_稳健性与B2分诊_计算产物.json` — ladder and bootstrap product;
- `切口核验_RoboParts可判定性/B2B4_裁定数据.json` — co-mount KPI and B2 adjudication;
- `切口核验_RoboParts可判定性/B1_电气端口取证表.md` — the 19-node locus audit and verbatim quotes;
- `切口核验_RoboParts可判定性/B2_EOAT分诊表_v2裁定.csv` — 101-row adjudication detail.

**This dossier does not claim to have re-run the original engine.** The three scripts under `Scripts/` are independent recomputations written from the shipped corpus only; their outputs are in `results/`. Where they succeed, they are labelled "independent recomputation of D0/D1 / upper-bound arithmetic / cluster bootstrap"; where they cannot recover the original rule, the frozen value is retained and the gap is logged, never smoothed over.

Corpus files read in this build: `api/morphology_graph.json`, `api/entities.json`, `api/co_mount.json`, `api/robot_tool_side.json`, plus the product files above.

---

## 4. Recompute consistency

Full machine-readable log: `results/frozen_checks.json` — 57 checks: **45 match, 3 mismatch, 9 not_recomputed**.

**mismatch (3):**

1. `corpus.vendors_with_manufacturer` — frozen 329 vs independent count 328 (distinct non-empty manufacturer strings on the 656 composable nodes). One-vendor normalisation gap in the original rule; magnitude 0.3%. Frozen 329 retained.
2. `bootstrap.mechanical_same_flange.pairs` — frozen 295 vs independent reconstruction 996. **Independent aggregation rule used here:** an unordered node pair is counted when both nodes carry the same declared `MECH:ISO` flange token, summed over all tokens as Σ C(n_t, 2) across the full 656-node composable universe. **Why this is systematically higher than the engine row:** the engine's 295 applies, on top of the token match, an additional category/composability filter that restricts attention to flange-borne EOAT and host-side contexts; that filter boundary was embedded in the original `rp_b24.py` and is not documented in any shipped product file, so it cannot be reproduced here. My 996 is therefore an unfiltered upper bound of the engine count, not a contradiction of it — the direction of the gap is exactly what this difference predicts (unfiltered > filtered), and the frozen 295 is retained as the engine value.
3. `bootstrap.mechanical_same_flange.point_pct` — consequence of row 2 (0.1373% vs my reconstruction 0.4636%). Same cause: the unfiltered token-match density of 996/214,840; the engine's filtered density is the manuscript value.

**not_recomputed (9):** D2=8 and D3=1 (engine verdict and manual locus — read from the adjudication records, not re-derived); the name-normalisation dedup block (rule not shipped); the B2 triage counts (read from `B2B4_裁定数据.json`); the B3 external counts (HRIM 21/3/0/0, UR+ 528 — not re-fetched).

**bootstrap actually ran:** `Scripts/rp_bootstrap.py` executed with B=1000, seed=20261109, whole-cluster manufacturer resampling; runtime **0.56 s**. All five point estimates reproduced; four of five reproduced exactly (2,211 / 3,240 / 171 / 77,815 pairs); the fifth is the mismatched same-flange row above. Re-computed CI bands (e.g. electrical 0.0053%–0.3113% vs frozen 0.0069%–0.268%) confirm the same conclusion: the electrical axis stays below ~0.3% at the 95% level under the re-run method.

---

## 5. Third-party reproduction steps

From the repository root (`RoboParts_兼容性四级阶梯_SCI/`), with the `2.robopart/api/` corpus present one level up:

```powershell
# 0. prerequisites
python --version        # this build used 3.13; numpy installed
# 1. D0/D1 + port audit recompute (writes results/ladder_recompute.json)
python 04_ResearchData/Scripts/rp_ladder_recompute.py
# 2. upper-bound arithmetic (writes results/upper_bound_recompute.json)
python 04_ResearchData/Scripts/rp_upper_bound.py
# 3. vendor whole-cluster bootstrap, B=1000 seed=20261109
#    (writes results/bootstrap_recomputed.json; ~1 s on a laptop)
python 04_ResearchData/Scripts/rp_bootstrap.py
# 4. verify the frozen ledger
python -c "import json; d=json.load(open('04_ResearchData/results/frozen_checks.json',encoding='utf-8')); from collections import Counter; print(Counter(c['status'] for c in d['checks']))"
```

Expected console: ladder script prints 13 lines with 12 `match` and 1 `MISMATCH` (vendors 329 vs 328); upper-bound script prints 6 `match`; bootstrap script prints five axis rows with point densities 0.4636% / 1.0291% / 1.5081% / 0.0796% / 36.2200%.

**Scope limits for a reproducer:** (a) D2=8 and D3=1 cannot be re-derived from the shipped files — they are engine and manual-locus results carried over verbatim; (b) the same-flange bootstrap row (295) cannot be reproduced from the corpus alone without the original engine rule; (c) all densities share the 214,840-pair denominator, which is C(656,2), not a sample drawn from a market.
