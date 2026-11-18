# Data Provenance

All numbers in this paper come from the main agent's on-the-fly computation over the local RoboParts corpus at `C:\Users\xing\Desktop\所有项目\2.robopart\api\*.json` (entities, morphology_graph, compose_semantics, evidence_valuation, co_mount, robot_tool_side, compatibility, mechanical_interfaces, electrical_interfaces). The producing scripts were `rp_b24.py`, `rp_b2v2.py`, `rp_ladder.py`; the producing JSON artifacts were `B4_稳健性与B2分诊_计算产物.json` and `B2B4_裁定数据.json`, with the triage detail in `B2_EOAT分诊表_v2裁定.csv`.

The present paper did not re-run those scripts in its own environment; the frozen numbers in `00_Spec/frozen_spec.md` are the authoritative record of that computation. This file records the lineage honestly so a reviewer can trace each number to its source file.

| Number in paper | Source file / table | Provenance tag |
|---|---|---|
| 868 entities / 656 composable nodes / 214,840 pairs / 329 vendors | entities.json + morphology_graph.json; rp_ladder.py output | [E] |
| 634 nodes / 200,661 pairs after isolating 22 placeholders | rp_b24.py output | [E] |
| 553 electrical ports / 17 type ids / 528 ELEC:UNKNOWN (95.48%) | electrical_interfaces.json; rp_ladder.py | [E] |
| D0 139,139 (64.764%) / D1 11 (0.00512%) / D2 8 (0.00372%) / D3 1 (0.00047%) | rp_ladder.py | [E]/[V] |
| D0 UNKNOWN×UNKNOWN subset 139,128 (99.992%) | rp_ladder.py | [E] |
| Three-axis bootstrap point estimates and 95% CIs | rp_b24.py, B=1000 seed=20261109, 329 vendor clusters | [E] |
| Dedup 645 nodes / 207,690 pairs; mech 295→294; D2 8 unchanged | rp_b2v2.py | [E] |
| Co-mount 360 pairs / mountable 0 / type_error 171 / port_exhausted 126 / unknown 63 | co_mount.json | [E] |
| UR3e/UR5e tool_io_ports=1, M8 8-pin; FR3 p=null | robot_tool_side.json | [V] |
| B1 locus: device 4 / adapter 3 / host 3 / cable 7 / GRIP-007 host+adapter | B1_电气端口取证表.md | [V] |
| B2 triage A 35 / B 44 / C 22; κ=0.6236, agreement 74.26%, 26 flips | B2_EOAT分诊表_v2裁定.csv; rp_b24.py | [E] |
| HRIM 21 class models / 3 instance datasheets / 0 mechanical / 0 connector fields; archived 2019-08-07; 71 stars | GitHub tree census | [V] |
| UR+ 528 products, 0 interface fields | universal-robots.com/plus/products/ census | [V] |
| B1 four loops (2FG7 host path; HEX-E 4-pin M8; ATI 6-pin M8 body / 8-pin M12 cable; UR20/30 adapter 20 kg) | manufacturer manuals, quoted verbatim in 核验报告_RoboParts_收尾B2B3B4_v3.md | [V] |

## Reproducibility note

To reproduce the ladder densities from the frozen inputs, run `rp_reproduce.py` in this folder; it recomputes the headline densities from the frozen counts (it does not re-open the 1.8 MB entities.json, which is the main agent's audit record). The bootstrap CIs require the per-pair vendor labels, which are not shipped; the point estimates and CIs are carried as frozen values in `bootstrap_three_axis.csv` with the script parameters (B=1000, seed=20261109) documented so a reviewer with the corpus can re-derive them.
