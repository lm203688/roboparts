# -*- coding: utf-8 -*-
"""
make_figures.py -- Regenerates Fig.1, Fig.2, Fig.3 for the RoboParts
four-level decidability ladder manuscript.

All numbers below are FROZEN constants taken verbatim from
    00_Spec/FROZEN_NUMBERS.json (v1-frozen-2026-11-09)
and are NOT re-derived or rounded. Do not read any data file at run time;
edit the constants here if the frozen numbers change.

Output (same directory as this script):
    Fig1_decidability_ladder.png
    Fig2_axis_forest.png
    Fig3_zero_taxonomy.png
All PNGs: 300 dpi, 7.0 in wide, English-only labels, no in-figure titles.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

# ----------------------------------------------------------------------------
# Global style (spec §3): Arial with DejaVu Sans fallback; axis labels 8-9 pt,
# tick labels 7-8 pt; palette fixed (no indigo / purple).
# ----------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 8.5,
    "axes.labelsize": 8.5,
    "axes.titlesize": 8.5,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7.5,
    "axes.linewidth": 0.8,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
})

C_SLATE   = "#2F4858"   # frozen palette
C_STEEL   = "#33658A"
C_LIGHT   = "#86BBD8"
C_AMBER   = "#F6AE2D"
C_ORANGE  = "#F26419"
C_GREY    = "#8C8C8C"

# ----------------------------------------------------------------------------
# FROZEN constants (FROZEN_NUMBERS.json) -- ladder
# ----------------------------------------------------------------------------
D_LEVELS   = ["D0", "D1", "D2", "D3"]
D_PAIRS    = [139139, 11, 8, 1]          # ladder.levels[].pairs
D_PCT      = ["64.764%", "0.00512%", "0.00372%", "0.00047%"]
D_RATIO_01 = "12,650x"                   # ladder.ratios.D0_over_D1
D_RATIO_12 = "1.4x"                      # ladder.ratios.D1_over_D2
D_RATIO_03 = "139,000x"                  # ladder.ratios.D0_over_D3
D_UNKNOWN_PAIRS = 139128                 # ladder.D0_unknown_pairs
D_UNKNOWN_SHARE = "99.992%"              # ladder.D0_unknown_share
D_DENOM    = 214840                      # ladder.denominator_pairs / corpus.unordered_pairs

# FROZEN -- bootstrap rows (bootstrap.rows[])
B_ROWS = [
    # label, point %, ci_low %, ci_high %, n, colour
    ("mechanical, same flange",                0.1373, 0.0132, 0.573,  "n = 295",   C_STEEL),
    ("mechanical, both declared",               1.0291, 0.160,  2.959,  "n = 2,211", C_STEEL),
    ("mechanical, both declared or partial",  1.5081, 0.368,  4.205,  "n = 3,240", C_STEEL),
    ("electrical, both declared",              0.0796, 0.0069, 0.268,  "n = 171",   C_ORANGE),
    ("signal, both declared",                  36.220, 26.18,  45.57,  "n = 77,815",C_SLATE),
]
B_B, B_SEED = 1000, 20261109            # bootstrap.B / bootstrap.seed

# FROZEN -- zero taxonomy (zero_taxonomy / co_mount)
Z_TOTAL   = 360                          # zero_taxonomy.evaluation_denominator
Z1, Z5Z2, Z3Z4 = 126, 171, 63           # Z1_port_exhausted; Z2 distributed in 171
                                        # type_error pairs; Z3+Z4 subset of 63 unknown
Z_IRR     = 297                          # irreducible_Z1_plus_Z5
Z_IRR_PCT = "82.5%"                      # irreducible_share_pct
S_MOUNT, S_UNK = 32, 16                 # co_mount.single_mount.{mountable,unknown}
K2_EVAL, K2_MOUNT = 360, 0              # co_mount.{pair_evaluations,mountable_pairs}


# ============================================================================
# Fig 1 -- four-level decidability ladder, log axis
# ============================================================================
def fig1():
    fig, ax = plt.subplots(figsize=(7.0, 4.3))
    x = range(len(D_LEVELS))
    bar_colors = [C_SLATE, C_STEEL, C_LIGHT, C_AMBER]

    ax.bar(x, D_PAIRS, width=0.62, bottom=0.5, color=bar_colors,
           edgecolor="white", linewidth=0.8, zorder=3)

    # y axis: log, floor 0.5 (so the D3 = 1 bar is visible); top raised to
    # 4.5e5 so the D0 top label sits fully ABOVE the 214,840 dashed line.
    ax.set_yscale("log")
    ax.set_ylim(0.5, 4.5e5)
    ax.set_yticks([1, 10, 100, 1000, 10000, 100000])
    ax.set_yticklabels(["1", "10", "100", "1,000", "10,000", "100,000"])
    ax.set_ylabel("decidable pairs (unordered, log scale)")
    ax.set_xticks(list(x))
    ax.set_xticklabels(D_LEVELS)
    ax.set_xlim(-0.6, 3.8)
    ax.grid(axis="y", which="major", color="#DDDDDD", linewidth=0.6, zorder=0)

    # denominator reference line (214,840 all unordered pairs); label sits
    # BELOW the line at the left, clear of the D0 top label which now sits
    # ABOVE the line.
    ax.axhline(D_DENOM, linestyle="--", color=C_GREY, linewidth=1.1, zorder=2)
    ax.text(-0.55, D_DENOM * 0.92, f"P = {D_DENOM:,} all unordered pairs",
            ha="left", va="top", fontsize=7.5, color=C_GREY)

    # bar-top labels: pairs + percentage (singular for the D3 = 1 pair).
    # D0's whole two-line label sits ABOVE the 214,840 dashed line.
    for xi, (p, pct) in enumerate(zip(D_PAIRS, D_PCT)):
        unit = "pair" if p == 1 else "pairs"
        ly = D_DENOM * 1.30 if xi == 0 else p * 1.25
        ax.text(xi, ly, f"{p:,} {unit}\n{pct}",
                ha="center", va="bottom", fontsize=7.5, color="black")

    # drop ratios between consecutive bars (geometric midpoint in log space)
    import math
    y01 = math.sqrt(D_PAIRS[0] * D_PAIRS[1])
    y12 = math.sqrt(D_PAIRS[1] * D_PAIRS[2])
    ax.annotate("", xy=(0.5, D_PAIRS[1] * 1.4), xytext=(0.5, D_PAIRS[0] / 1.4),
                arrowprops=dict(arrowstyle="->", color=C_GREY, lw=0.8))
    ax.text(0.56, y01, D_RATIO_01, ha="left", va="center", fontsize=7.5,
            color=C_GREY)
    ax.annotate("", xy=(1.5, D_PAIRS[2] * 1.4), xytext=(1.5, D_PAIRS[1] / 1.4),
                arrowprops=dict(arrowstyle="->", color=C_GREY, lw=0.8))
    ax.text(1.56, y12, D_RATIO_12, ha="left", va="center", fontsize=7.5,
            color=C_GREY)

    # overall D0 -> D3 ratio
    ax.text(3.72, 4.0e4, f"D0 -> D3 = {D_RATIO_03}\n(~5 orders of magnitude)",
            ha="right", va="center", fontsize=8, color=C_SLATE,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=C_SLATE, lw=0.8))

    # D0 UNKNOWN x UNKNOWN note
    ax.text(0.42, 2.5e4,
            f"{D_UNKNOWN_PAIRS:,} of 139,139 ({D_UNKNOWN_SHARE})\nare UNKNOWN x UNKNOWN",
            ha="left", va="center", fontsize=7.5, color=C_SLATE)

    fig.savefig("Fig1_decidability_ladder.png")
    plt.close(fig)


# ============================================================================
# Fig 2 -- five-definition forest plot, log x axis
# ============================================================================
def fig2():
    fig, ax = plt.subplots(figsize=(7.0, 4.1))
    ys = list(range(len(B_ROWS) - 1, -1, -1))     # top row first

    ax.set_xscale("log")
    ax.set_xlim(0.001, 300)
    ax.set_xticks([0.001, 0.01, 0.1, 1, 10, 100])
    ax.set_xticklabels(["10$^{-3}$", "10$^{-2}$", "10$^{-1}$",
                        "10$^0$", "10$^1$", "10$^2$"])
    ax.set_ylim(-0.55, len(B_ROWS) - 0.45)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in B_ROWS])
    ax.set_xlabel("decidable share of unordered pairs (%)")
    ax.axvline(1.0, linestyle="--", color=C_GREY, linewidth=1.1, zorder=1)
    ax.text(1.03, len(B_ROWS) - 0.45, "1%", ha="left", va="top",
            fontsize=7.5, color=C_GREY)
    ax.grid(axis="x", which="major", color="#DDDDDD", linewidth=0.6, zorder=0)

    for (label, pt, lo, hi, ntxt, col), yi in zip(B_ROWS, ys):
        ax.errorbar(pt, yi, xerr=[[pt - lo], [hi - pt]],
                    fmt="o", color=col, ecolor=col, elinewidth=1.4,
                    capsize=3, markersize=5, zorder=3)
        # n labels sit just past each CI cap so they never collide with the
        # inset or the right axes edge.
        ax.text(hi * 1.22, yi, ntxt, ha="left", va="center", fontsize=7.5,
                color="black")

    # footnote removed: B=1000 / seed / cluster-bootstrap CI are stated in the
    # Table 4 and Fig.2 captions in the manuscript, so no in-figure note.

    # inset: zoom of the electrical row over 0-0.5% (linear axis), parked in
    # the empty upper-right cell (x > ~8%, y > ~2.3) so no CI cap or n-label
    # is ever covered.
    in_ax = ax.inset_axes([0.83, 0.62, 0.16, 0.33])
    e_pt, e_lo, e_hi = 0.0796, 0.0069, 0.268
    in_ax.errorbar([0.0796], [0], xerr=[[0.0796 - 0.0069], [0.268 - 0.0796]],
                   fmt="o", color=C_ORANGE, ecolor=C_ORANGE, elinewidth=1.4,
                   capsize=3, markersize=5)
    in_ax.set_xlim(0, 0.5)
    in_ax.set_ylim(-0.5, 0.5)
    in_ax.set_yticks([])
    in_ax.set_xticks([0, 0.25, 0.5])
    in_ax.set_xticklabels(["0", "0.25", "0.5%"], fontsize=6.5)
    for spine in in_ax.spines.values():
        spine.set_linewidth(0.7)

    fig.savefig("Fig2_axis_forest.png")
    plt.close(fig)


# ============================================================================
# Fig 3 -- zero taxonomy: (a) stacked 360 evaluations, (b) k=1 vs k=2
# ============================================================================
def bracket(ax, x0, x1, y, text, dy=0.09, fs=7.5, text_center=None):
    """Simple horizontal bracket above a bar segment, with a label."""
    ax.plot([x0, x0, x1, x1], [y, y + dy, y + dy, y],
            color="black", linewidth=0.9, clip_on=False)
    tc = (x0 + x1) / 2 if text_center is None else text_center
    ax.text(tc, y + dy + 0.015, text,
            ha="center", va="bottom", fontsize=fs)


def fig3():
    fig, (axa, axb) = plt.subplots(
        2, 1, figsize=(7.0, 4.8),
        gridspec_kw={"height_ratios": [1.0, 1.15], "hspace": 0.55})

    # ---- panel (a): stacked horizontal bar of the 360 pair evaluations ----
    segs = [(126, "Z1\n126 (35.0%)", C_STEEL),
            (171, "Z5 / Z2\n171 (47.5%)", C_LIGHT),
            (63, "Z3 / Z4\n63 (17.5%)", C_GREY)]
    left = 0.0
    for val, lab, col in segs:
        axa.barh(0, val, left=left, height=0.5, color=col,
                 edgecolor="white", linewidth=0.8)
        axa.text(left + val / 2, 0, lab, ha="center", va="center",
                fontsize=7.5, color="black")
        left += val
    axa.set_xlim(0, 400)
    axa.set_ylim(-0.75, 0.85)
    axa.set_yticks([])
    axa.set_xlabel("pair evaluations (n = 360)")
    axa.set_xticks([0, 60, 120, 180, 240, 300, 360])

    # brackets: irreducible vs removable
    bracket(axa, 0, Z_IRR, 0.32,
            f"Z1+Z5 = {Z_IRR}/360 = {Z_IRR_PCT} irreducible (no evidence can change it)")
    bracket(axa, Z_IRR, Z_TOTAL, 0.32,
            "Z3+Z4 = 63\n17.5%, removable", text_center=322)

    axa.text(0, -0.62,
             "Note: Z2 is distributed within the 171 type_error pairs "
             "and is not counted twice.",
             ha="left", va="center", fontsize=7, color=C_GREY)
    axa.text(-0.09, 1.02, "(a)", transform=axa.transAxes,
             ha="left", va="bottom", fontsize=8.5, fontweight="bold")

    # ---- panel (b): k=1 single mount vs k=2 co-mount ----
    groups = ["k=1 single mount", "k=2 co-mount"]
    gx = [0, 1]
    w = 0.32
    # group 1: mountable 32, unknown 16
    axb.bar(0 - w / 2, S_MOUNT, width=w, color=C_STEEL, label="mountable")
    axb.bar(0 + w / 2, S_UNK, width=w, color=C_GREY, label="unknown")
    # group 2: 360 evaluations, 0 mountable -- draw a visible zero stub at the
    # baseline so "0" reads as the headline result, not as a missing bar.
    axb.bar(1 - w / 2, K2_EVAL, width=w, color=C_LIGHT,
            label="evaluations")
    axb.bar(1 + w / 2, 8, width=w, color=C_STEEL)

    for xpos, v in [(0 - w / 2, S_MOUNT), (0 + w / 2, S_UNK),
                    (1 - w / 2, K2_EVAL)]:
        axb.text(xpos, v + 6, str(v), ha="center", va="bottom", fontsize=7.5)
    axb.text(1 + w / 2, 14, "mountable = 0\n(0 of 360)",
             ha="center", va="bottom", fontsize=7.5)

    axb.set_xticks(gx)
    axb.set_xticklabels(groups)
    axb.set_ylim(0, 420)
    axb.set_ylabel("pair outcomes")
    axb.legend(loc="upper left", frameon=False, ncol=3)
    axb.text(-0.09, 1.02, "(b)", transform=axb.transAxes,
             ha="left", va="bottom", fontsize=8.5, fontweight="bold")

    fig.savefig("Fig3_zero_taxonomy.png")
    plt.close(fig)


if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    fig1()
    fig2()
    fig3()
    print("done: Fig1, Fig2, Fig3 written to", os.getcwd())
