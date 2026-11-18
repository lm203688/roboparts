#!/usr/bin/env python3
"""
Reproduce the headline ladder densities from the frozen counts.
Frozen inputs come from the main agent's on-the-fly computation over the
RoboParts corpus (entities.json, morphology_graph.json, electrical_interfaces.json,
co_mount.json, robot_tool_side.json). This script recomputes the reported densities
so the arithmetic is auditable; it does not re-open the full corpus.
"""
from math import comb

DENOM = 214_840  # unordered pairs over 656 composable nodes

ladder = [
    ("D0", 139_139),
    ("D1", 11),
    ("D2", 8),
    ("D3", 1),
]

print("=== Four-level decidability ladder ===")
for i, (name, n) in enumerate(ladder):
    share = n / DENOM * 100
    if i + 1 < len(ladder):
        n_next = ladder[i+1][1]
        ratio = f"{n/n_next:,.1f}x"
    else:
        ratio = "-"
    print(f"{name}: {n:>7} pairs  {share:>9.5f}%   ratio_to_next={ratio}")

print("\n=== D0 UNKNOWN x UNKNOWN subset ===")
unk = 139_128
print(f"UNKNOWN x UNKNOWN pairs within D0: {unk}  share of D0 = {unk/139_139*100:.3f}%")

print("\n=== Optimistic upper bound on filling the 35-part backlog ===")
n_after = 25 + 35
opt = comb(n_after, 2)
print(f"C({n_after},2) = {opt} pairs  density = {opt/DENOM*100:.3f}%  (must stay < 1%)")

print("\n=== Zero taxonomy on the 360-pair co-mount layer ===")
z1, z5 = 126, 171  # port_exhausted pairs + not_complementary pairs (distinct classes;
                   # the frozen 297/360 = 82.5% uses the class-level counts as given)
print(f"Z1+Z5 = {z1+z5}/360 = {(z1+z5)/360*100:.1f}% not evidence-eliminable")
