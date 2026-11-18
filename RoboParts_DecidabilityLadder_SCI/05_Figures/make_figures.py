#!/usr/bin/env python3
"""Generate the three paper figures at 300 dpi, English labels."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

OUT = Path(__file__).resolve().parent
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# ---------- Fig 1: four-level decidability ladder (log waterfall) ----------
levels = ["D0\nlabel equal\n(placeholders\nincluded)",
          "D1\nreal label\nequal",
          "D2\ntype+pin\n+gender",
          "D3\nlocus-corrected\ntrue mating"]
pairs = [139139, 11, 8, 1]
share = [64.764, 0.00512, 0.00372, 0.00047]

fig, ax = plt.subplots(figsize=(7.2, 4.6))
bars = ax.bar(levels, share, color=["#4C72B0", "#55A868", "#C44E52", "#8172B2"], width=0.62)
ax.set_yscale("log")
ax.set_ylabel("Decidable pairs as share of 214,840 (%)")
ax.set_title("Four-level decidability ladder: ~5 orders of magnitude as evidence tightens")
for b, s, p in zip(bars, share, pairs):
    ax.text(b.get_x()+b.get_width()/2, s*1.25, f"{s:.4f}%\n({p:,} pairs)",
            ha="center", va="bottom", fontsize=8.5)
# drop multipliers
drops = [("D0/D1\n12,650x", 0.5), ("D1/D2\n1.4x", 1.5), ("D0/D3\n~139,000x", 2.5)]
for txt, x in drops:
    ax.text(x, 0.02, txt, ha="center", fontsize=8, color="#333333",
            bbox=dict(boxstyle="round,pad=0.25", fc="#F0F0F0", ec="#BBBBBB", lw=0.6))
ax.set_ylim(0.0002, 200)
ax.axhline(0.00047, color="none")
fig.tight_layout()
fig.savefig(OUT/"Fig1_ladder_waterfall.png", dpi=300)
plt.close(fig)

# ---------- Fig 2: three-axis forest plot with CIs ----------
labels = ["Mech · same flange label",
          "Mech · both ends declared",
          "Mech · both ends loose",
          "Elec · both ends declared",
          "Signal · both ends declared"]
point = [0.1373, 1.0291, 1.5081, 0.0796, 36.220]
low   = [0.0132, 0.160, 0.368, 0.0069, 26.18]
high  = [0.573, 2.959, 4.205, 0.268, 45.57]
colors = ["#4C72B0"]*3 + ["#C44E52"] + ["#55A868"]

fig, ax = plt.subplots(figsize=(7.2, 4.4))
y = np.arange(len(labels))[::-1]
for yi, p, lo, hi, c in zip(y, point, low, high, colors):
    ax.plot([lo, hi], [yi, yi], color=c, lw=2.2, solid_capstyle="round")
    ax.plot(p, yi, "o", color=c, markersize=8)
    ax.text(hi*1.15, yi, f"{p:.3f}%  [{lo:.3f}, {hi:.3f}]", va="center", fontsize=8.5)
ax.set_yticks(y)
ax.set_yticklabels(labels)
ax.set_xscale("log")
ax.set_xlabel("Density of decidable pairs (%, log scale) with 95% vendor-cluster CI")
ax.set_title("Three-axis densities: electrical is weakest under every definition")
ax.axvspan(0.0132, 0.268, color="#C44E52", alpha=0.07)
ax.text(0.04, 0.2, "overlap band:\nmech lower CI vs\nelec upper CI", fontsize=7.5, color="#C44E52")
fig.tight_layout()
fig.savefig(OUT/"Fig2_three_axis_forest.png", dpi=300)
plt.close(fig)

# ---------- Fig 3: taxonomy of zeros (measured class sizes, overlap noted) ----------
# Frozen measured values on the 360-pair co-mount layer. Classes overlap by design
# (a pair can be both type_error and not_complementary), so we show measured class
# sizes as a bar chart, not a decomposition summing to 360.
classes = ["Z1\nport exhausted\n(126 pairs)",
           "Z2\ntype mismatch\n(within 171 type_error pairs)",
           "Z3\ndevice-side undeclared\n(63 unknown pairs; 528 ports)",
           "Z4\nhost-side undeclared\n(FR3 branch only, p=null)",
           "Z5\nnon-complementary roles\n(171 not_complementary pairs)"]
values = [126, 171, 63, 1, 171]
c_colors = ["#8172B2", "#CCB974", "#64B5CD", "#C7C7C7", "#C44E52"]
structural = [True, False, False, False, True]

fig, ax = plt.subplots(figsize=(7.4, 4.6))
y = np.arange(len(classes))[::-1]
bars = ax.barh(y, values, color=c_colors, height=0.58)
for yi, v, st in zip(y, values, structural):
    label = "structural" if st else "evidence-removable"
    txt = f"{v} pairs" if v > 1 else "1 host branch (qualitative)"
    ax.text(v+3, yi, txt, va="center", fontsize=8.5)
ax.set_yticks(y)
ax.set_yticklabels(classes, fontsize=8.5)
ax.set_xlim(0, 230)
ax.set_xlabel("Measured size on the 360-pair co-mount layer (pairs; classes overlap)")
ax.set_title("Taxonomy of zeros: Z1+Z5 = 297/360 = 82.5% cannot be removed by more evidence")
fig.tight_layout()
fig.savefig(OUT/"Fig3_taxonomy_of_zeros.png", dpi=300)
plt.close(fig)

print("Figures written:")
for p in ["Fig1_ladder_waterfall.png", "Fig2_three_axis_forest.png", "Fig3_taxonomy_of_zeros.png"]:
    f = OUT/p
    print(f"  {p}  {f.stat().st_size} bytes")
