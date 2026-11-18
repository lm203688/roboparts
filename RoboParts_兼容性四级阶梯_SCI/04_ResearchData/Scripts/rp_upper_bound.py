# -*- coding: utf-8 -*-
"""
rp_upper_bound.py
Recompute the optimistic completion upper bound (paper section 7 / Table 6).

Scenario: all 35 class-A flange-borne EOAT parts are fully completed.
  new pairs among the 35 completed parts      = C(35, 2)
  new pairs of those 35 against already-declared nodes (n=19) = 35 x 19
  plus the 8 observed D2 pairs already in the corpus.

Inputs are hard-coded counts taken from FROZEN_NUMBERS.json
(upper_bound_calculation block); this script only re-evaluates the arithmetic,
it does not re-derive the 35 / 19 / 8 from the corpus.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
FROZEN = os.path.join(ROOT, "00_Spec", "FROZEN_NUMBERS.json")
OUTDIR = os.path.join(ROOT, "04_ResearchData", "results")


def main():
    with open(FROZEN, encoding="utf-8") as f:
        frozen = json.load(f)
    ub = frozen["upper_bound_calculation"]

    n_A = 35
    n_existing_declared = ub["existing_declared_nodes"]  # 19
    observed_D2 = 8
    pairs_total = frozen["corpus"]["unordered_pairs"]            # 214840
    pairs_after_quarantine = frozen["corpus"]["after_isolating_22_placeholders"]["pairs"]  # 200661

    among_35 = math.comb(n_A, 2)
    to_existing = n_A * n_existing_declared
    max_new = among_35 + to_existing
    max_D2 = max_new + observed_D2
    density_denom_full = max_D2 / pairs_total * 100.0
    density_denom_quarantined = max_D2 / pairs_after_quarantine * 100.0

    recomputed = {
        "C(35,2)": among_35,
        "35x19": to_existing,
        "max_new_pairs": max_new,
        "max_D2_pairs": max_D2,
        "density_of_214840_pct": round(density_denom_full, 3),
        "density_of_200661_pct": round(density_denom_quarantined, 3),
    }
    expected = {
        "C(35,2)": ub["new_pairs_among_the_35"],
        "35x19": ub["new_pairs_to_existing"],
        "max_new_pairs": ub["max_new_pairs"],
        "max_D2_pairs": ub["max_D2_pairs"],
    }
    print(json.dumps(recomputed, indent=1))
    checks = []
    for k, exp in expected.items():
        got = recomputed[k]
        status = "match" if exp == got else "MISMATCH"
        checks.append({"field": "upper_bound." + k, "expected": exp,
                       "recomputed": got, "status": status})
        print(f"{k:16s} frozen={exp:>6d} recomputed={got:>6d} {status}")
    # densities: frozen strings "0.590%" / "0.632%"
    for k, exp_s in [("density_of_214840_pct", ub["density_of_214840"]),
                     ("density_of_200661_pct", ub["density_of_200661"])]:
        got_s = f"{recomputed[k]:.3f}%"
        status = "match" if got_s == exp_s else "MISMATCH"
        checks.append({"field": "upper_bound." + k, "expected": exp_s,
                       "recomputed": got_s, "status": status})
        print(f"{k:26s} frozen={exp_s:>8s} recomputed={got_s:>8s} {status}")

    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "upper_bound_recompute.json"), "w", encoding="utf-8") as fp:
        json.dump({"script": "rp_upper_bound.py", "recomputed": recomputed,
                   "checks": checks}, fp, ensure_ascii=False, indent=1)
    print("wrote", os.path.join(OUTDIR, "upper_bound_recompute.json"))


if __name__ == "__main__":
    main()
