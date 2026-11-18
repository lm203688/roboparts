# -*- coding: utf-8 -*-
"""
rp_bootstrap.py
Vendor whole-cluster bootstrap of the five cross-axis decidability densities.

Settings (frozen):  B = 1000, seed = 20261109, cluster unit = manufacturer
(329 clusters, whole-cluster resampling). Empty manufacturer strings are
collapsed into a single "" cluster, which reproduces the frozen cluster count
of 329 from the shipped corpus (328 distinct non-empty manufacturers + 1
empty cluster).

Method documented here because the original rp_b24.py is not recoverable:
  * clusters are drawn with replacement, 329 draws per iteration, numpy
    default_rng(20261109);
  * a drawn cluster contributes every node it contains, duplicated by the
    number of times the cluster was drawn (conventional cluster-bootstrap
    treatment of duplicated clusters);
  * statistic = success pairs / C(total node instances, 2);
  * CI = 2.5 / 97.5 percentiles over B iterations.

Axes:
  mechanical_same_flange              : pairs sharing an identical declared
                                        MECH:ISO flange token (my independent
                                        reconstruction; NOTE: the frozen 295
                                        could not be reproduced with this
                                        rule -- see frozen_checks.json)
  mechanical_both_declared            : C(k,2), k = nodes with a declared
                                        mechanical port
  mechanical_both_declared_or_partial : k = nodes with declared OR partial
                                        mechanical port
  electrical_both_declared             : k = nodes with a declared electrical
                                        port
  signal_both_declared                 : k = nodes with a declared signal port

Writes results/bootstrap_recomputed.json. If numpy is missing the script
prints NOT_RUN and exits 2.
"""
import json
import math
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CORPUS = os.path.join(ROOT, "..", "2.robopart", "api")
FROZEN = os.path.join(ROOT, "00_Spec", "FROZEN_NUMBERS.json")
OUTDIR = os.path.join(ROOT, "04_ResearchData", "results")

B = 1000
SEED = 20261109


def main():
    try:
        import numpy as np
    except Exception as e:  # pragma: no cover
        print("NOT_RUN: numpy unavailable (%s)" % e)
        sys.exit(2)

    with open(os.path.join(CORPUS, "morphology_graph.json"), encoding="utf-8") as f:
        mg = json.load(f)
    with open(FROZEN, encoding="utf-8") as f:
        frozen = json.load(f)

    nodes = [n for n in mg["nodes"] if n.get("composable")]

    # cluster key = manufacturer, empty collapsed to ""
    def clust(n):
        m = n.get("manufacturer")
        return m if m else ""

    cluster_ids, clusters = {}, []
    for n in nodes:
        c = clust(n)
        if c not in cluster_ids:
            cluster_ids[c] = len(clusters)
            clusters.append([])
        clusters[cluster_ids[c]].append(n)
    n_clusters = len(clusters)

    # per-node property flags
    def has_decl(n, axis):
        return any(p["type"].startswith(axis) and p.get("status") == "declared"
                   for p in n["ports"])

    def has_decl_or_part(n, axis):
        return any(p["type"].startswith(axis) and p.get("status") in ("declared", "partial")
                   for p in n["ports"])

    # cluster-level totals
    prop = {k: [0] * n_clusters for k in
            ["mech_decl", "mech_decl_or_part", "elec_decl", "sig_decl"]}
    size = [0] * n_clusters
    token_clusters = {}  # token -> per-cluster node count

    for ci, cnodes in enumerate(clusters):
        for n in cnodes:
            size[ci] += 1
            if has_decl(n, "MECH:"):
                prop["mech_decl"][ci] += 1
            if has_decl_or_part(n, "MECH:"):
                prop["mech_decl_or_part"][ci] += 1
            if has_decl(n, "ELEC:"):
                prop["elec_decl"][ci] += 1
            if has_decl(n, "SIG:"):
                prop["sig_decl"][ci] += 1
            for p in n["ports"]:
                t = p["type"]
                if t.startswith("MECH:ISO") and p.get("status") == "declared":
                    token_clusters.setdefault(t, [0] * n_clusters)
                    token_clusters[t][ci] += 1

    size = np.array(size, dtype=float)
    P = {k: np.array(v, dtype=float) for k, v in prop.items()}
    T = {k: np.array(v, dtype=float) for k, v in token_clusters.items()}

    rng = np.random.default_rng(SEED)
    # bootstrap distributions of density (%)
    dens = {k: np.empty(B) for k in
            ["mech_same_flange", "mech_both_declared", "mech_both_declared_or_partial",
             "elec_both_declared", "sig_both_declared"]}
    for b in range(B):
        draw = rng.integers(0, n_clusters, size=n_clusters)  # whole-cluster resample
        mult = np.bincount(draw, minlength=n_clusters).astype(float)
        N = float((size * mult).sum())
        denom = N * (N - 1) / 2.0
        if denom <= 0:
            continue
        # both-declared axes
        for key, src in [("mech_both_declared", "mech_decl"),
                         ("mech_both_declared_or_partial", "mech_decl_or_part"),
                         ("elec_both_declared", "elec_decl"),
                         ("sig_both_declared", "sig_decl")]:
            kk = float((P[src] * mult).sum())
            dens[key][b] = (kk * (kk - 1) / 2.0) / denom * 100.0
        # same-flange token aggregation
        sp = 0.0
        for t, vec in T.items():
            cc = float((vec * mult).sum())
            sp += cc * (cc - 1) / 2.0
        dens["mech_same_flange"][b] = sp / denom * 100.0

    # observed point densities on the full corpus (214840 pairs)
    full_pairs = len(nodes) * (len(nodes) - 1) // 2
    obs = {}
    for axis in ["mech_both_declared", "mech_both_declared_or_partial",
                 "elec_both_declared", "sig_both_declared"]:
        kk = int(P[{"mech_both_declared": "mech_decl",
                    "mech_both_declared_or_partial": "mech_decl_or_part",
                    "elec_both_declared": "elec_decl",
                    "sig_both_declared": "sig_decl"}[axis]].sum())
        obs[axis] = {"pairs": kk * (kk - 1) // 2,
                     "point_pct": f"{kk * (kk - 1) / 2.0 / full_pairs * 100.0:.4f}%"}
    sp_full = 0
    for t, vec in T.items():
        cc = int(vec.sum())
        sp_full += cc * (cc - 1) // 2
    obs["mech_same_flange"] = {"pairs": sp_full,
                               "point_pct": f"{sp_full / full_pairs * 100.0:.4f}%"}

    result = {"script": "rp_bootstrap.py", "B": B, "seed": SEED,
              "cluster_unit": "manufacturer", "n_clusters_observed": n_clusters,
              "note": "frozen says 329 clusters; empty manufacturer collapsed to one cluster",
              "axes": {}}
    frozen_rows = {r["axis"]: r for r in frozen["bootstrap"]["rows"]}
    name_map = {"mech_same_flange": "mechanical_same_flange",
                "mech_both_declared": "mechanical_both_declared",
                "mech_both_declared_or_partial": "mechanical_both_declared_or_partial",
                "elec_both_declared": "electrical_both_declared",
                "sig_both_declared": "signal_both_declared"}
    for key, fname in name_map.items():
        lo, hi = np.percentile(dens[key][dens[key] > 0], [2.5, 97.5]) if (dens[key] > 0).any() else (0.0, 0.0)
        row = {
            "observed_pairs": obs[key]["pairs"],
            "observed_point_pct": obs[key]["point_pct"],
            "ci95_low_pct": f"{lo:.4f}%",
            "ci95_high_pct": f"{hi:.4f}%",
            "frozen_point_pct": frozen_rows[fname]["point_pct"],
            "frozen_ci": [frozen_rows[fname]["ci_low"], frozen_rows[fname]["ci_high"]],
        }
        result["axes"][fname] = row
        print(f"{fname:42s} obs={obs[key]['pairs']:>7d} {obs[key]['point_pct']:>9s} "
              f"CI[{lo:.4f}%, {hi:.4f}%]  frozen {frozen_rows[fname]['point_pct']} "
              f"[{frozen_rows[fname]['ci_low']}, {frozen_rows[fname]['ci_high']}]")

    os.makedirs(OUTDIR, exist_ok=True)
    with open(os.path.join(OUTDIR, "bootstrap_recomputed.json"), "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=1)
    print("wrote", os.path.join(OUTDIR, "bootstrap_recomputed.json"))


if __name__ == "__main__":
    main()
