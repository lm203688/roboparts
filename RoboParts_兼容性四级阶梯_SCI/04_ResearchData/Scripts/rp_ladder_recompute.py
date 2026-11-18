# -*- coding: utf-8 -*-
"""
rp_ladder_recompute.py
Independent recomputation of the D0/D1 decidability ladder and electrical-port
audit counts, straight from the shipped RoboParts corpus.

Universe  : api/morphology_graph.json  (nodes[].ports[].type / .status, .composable)
           api/entities.json           (entity total)
Frozen ref: 00_Spec/FROZEN_NUMBERS.json

Definition used here (documented, recoverable):
  * composable node = node with composable == True
  * unordered pairs = C(n, 2) over composable nodes
  * electrical port = any node port whose type startswith "ELEC:"
  * D0 = number of unordered node pairs that share at least one identical
         electrical port type label, placeholders (ELEC:UNKNOWN) included
  * D0_unknown = the D0 subset shared on ELEC:UNKNOWN only
  * D1 = D0 subset whose shared label is NOT ELEC:UNKNOWN
  * vendors = distinct non-empty manufacturer strings among composable nodes

Output: prints a table and writes results/ladder_recompute.json next to this
script's ../results directory. Run from anywhere; paths are resolved relative
to the repo root (two levels up from this file).
"""
import json
import math
import os
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))  # RoboParts_兼容性四级阶梯_SCI
CORPUS = os.path.join(ROOT, "..", "2.robopart", "api")
FROZEN = os.path.join(ROOT, "00_Spec", "FROZEN_NUMBERS.json")
OUTDIR = os.path.join(ROOT, "04_ResearchData", "results")


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    mg = load(os.path.join(CORPUS, "morphology_graph.json"))
    ent = load(os.path.join(CORPUS, "entities.json"))
    frozen = load(FROZEN)

    nodes = [n for n in mg["nodes"] if n.get("composable")]
    n_nodes = len(nodes)
    n_pairs = n_nodes * (n_nodes - 1) // 2

    # vendor audit
    vendors = {n.get("manufacturer") for n in nodes if n.get("manufacturer")}
    n_vendors = len(vendors)

    # electrical port audit
    elec_rows = []  # (node_id, type, status)
    node_decl = {}  # node_id -> [declared elec types]
    node_unk = {}   # node_id -> bool
    for n in nodes:
        decl = []
        has_unk = False
        for p in n["ports"]:
            t = p["type"]
            if not t.startswith("ELEC:"):
                continue
            s = p.get("status")
            elec_rows.append((n["id"], t, s))
            if s == "declared":
                decl.append(t)
            if "UNKNOWN" in t:
                has_unk = True
        if decl:
            node_decl[n["id"]] = decl
        node_unk[n["id"]] = has_unk

    total_ports = len(elec_rows)
    distinct_types = len({t for _, t, _ in elec_rows})
    unknown_ports = sum(1 for _, t, _ in elec_rows if "UNKNOWN" in t)
    n_declared = sum(1 for _, _, s in elec_rows if s == "declared")
    n_not_declared = sum(1 for _, _, s in elec_rows if s == "not_declared")
    n_decl_nodes = len(node_decl)
    n_multi_decl = sum(1 for v in node_decl.values() if len(v) > 1)

    # D0 / D1 aggregation over shared labels
    label_owners = Counter()
    for n in nodes:
        types = {p["type"] for p in n["ports"] if p["type"].startswith("ELEC:")}
        for t in types:
            label_owners[t] += 1
    d0 = d0_unk = d1 = 0
    for t, c in label_owners.items():
        pairs = c * (c - 1) // 2
        d0 += pairs
        if "UNKNOWN" in t:
            d0_unk += pairs
        else:
            d1 += pairs

    recomputed = {
        "entities_total": len(ent["entities"]),
        "composable_nodes": n_nodes,
        "unordered_pairs": n_pairs,
        "vendors_distinct_nonempty": n_vendors,
        "electrical_ports_total": total_ports,
        "electrical_distinct_type_ids": distinct_types,
        "electrical_unknown_ports": unknown_ports,
        "electrical_status_declared": n_declared,
        "electrical_status_not_declared": n_not_declared,
        "nodes_with_declared_electrical_port": n_decl_nodes,
        "nodes_with_gt1_declared_electrical_port": n_multi_decl,
        "D0_pairs": d0,
        "D0_unknown_pairs": d0_unk,
        "D1_pairs": d1,
    }

    # comparison against frozen
    f = frozen
    checks = [
        ("corpus.entities", f["corpus"]["entities"], recomputed["entities_total"]),
        ("corpus.composable_nodes", f["corpus"]["composable_nodes"], recomputed["composable_nodes"]),
        ("corpus.unordered_pairs", f["corpus"]["unordered_pairs"], recomputed["unordered_pairs"]),
        ("corpus.vendors_with_manufacturer", f["corpus"]["vendors_with_manufacturer"], recomputed["vendors_distinct_nonempty"]),
        ("electrical_ports.total_ports", f["electrical_ports"]["total_ports"], recomputed["electrical_ports_total"]),
        ("electrical_ports.distinct_type_ids", f["electrical_ports"]["distinct_type_ids"], recomputed["electrical_distinct_type_ids"]),
        ("electrical_ports.unknown_type_ports", f["electrical_ports"]["unknown_type_ports"], recomputed["electrical_unknown_ports"]),
        ("electrical_ports.status_declared", f["electrical_ports"]["status_declared"], recomputed["electrical_status_declared"]),
        ("electrical_ports.status_not_declared", f["electrical_ports"]["status_not_declared"], recomputed["electrical_status_not_declared"]),
        ("electrical_ports.nodes_with_more_than_one_declared_electrical_port",
         f["electrical_ports"]["nodes_with_more_than_one_declared_electrical_port"], recomputed["nodes_with_gt1_declared_electrical_port"]),
        ("ladder.D0.pairs", f["ladder"]["levels"][0]["pairs"], recomputed["D0_pairs"]),
        ("ladder.D0_unknown_pairs", f["ladder"]["D0_unknown_pairs"], recomputed["D0_unknown_pairs"]),
        ("ladder.D1.pairs", f["ladder"]["levels"][1]["pairs"], recomputed["D1_pairs"]),
    ]

    report = []
    print(f"{'field':52s} {'frozen':>10s} {'recomputed':>12s}  status")
    for name, exp, got in checks:
        status = "match" if exp == got else "MISMATCH"
        print(f"{name:52s} {exp:>10d} {got:>12d}  {status}")
        report.append({"field": name, "expected": exp, "recomputed": got,
                       "status": status})

    os.makedirs(OUTDIR, exist_ok=True)
    out = {"script": "rp_ladder_recompute.py",
           "corpus": "api/morphology_graph.json + api/entities.json",
           "recomputed": recomputed, "checks": report}
    with open(os.path.join(OUTDIR, "ladder_recompute.json"), "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)
    print("wrote", os.path.join(OUTDIR, "ladder_recompute.json"))


if __name__ == "__main__":
    main()
