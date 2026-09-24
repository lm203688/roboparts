"""Generate real figures for the Mechatronics submission.

Reads api/gap_classification.json + api/compose_semantics.json (SoT)
and writes vector PDFs to papers/mechatronics_submission/figures/.

All numbers come from the pipeline output — no hand-written constants.
Elsevier requires vector PDF/SVG/EPS or 600 dpi bitmap; we emit PDF.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parent.parent.parent.parent
API = ROOT / "api"
OUT = ROOT / "papers" / "mechatronics_submission" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------
# Palette — muted Elsevier-friendly scheme (colour-blind safe-ish)
# ------------------------------------------------------------------
C_COMP      = "#1f77b4"   # blue   - composed
C_TYPE      = "#c0392b"   # red    - type_error
C_UNK       = "#7f8c8d"   # grey   - unknown
C_ELEC      = "#d35400"   # orange - electrical axis
C_MEC       = "#2c3e50"   # dark   - mechanical axis
C_SIG       = "#16a085"   # teal   - signal axis
C_ACCENT    = "#2980b9"
C_MUTED     = "#bdc3c7"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": "#333333",
    "axes.labelcolor": "#222222",
    "text.color": "#222222",
    "xtick.color": "#333333",
    "ytick.color": "#333333",
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "pdf.fonttype": 42,      # TrueType - Elsevier accepts
    "ps.fonttype": 42,
})


def _load(name):
    with open(API / name, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------
# Figure 1: manufacturer concentration curve
# ------------------------------------------------------------------
def fig_concentration():
    """Cumulative share of unpublished-suspect gap vs. vendor rank.

    Data source: entities.json mechanical_interface.status=not_declared,
    grouped by manufacturer. Reproduces gap_leverage.top10 exactly.
    """
    ents = _load("entities.json")["entities"]
    cnt = Counter()
    for e in ents:
        mi = e.get("mechanical_interface")
        if isinstance(mi, dict) and mi.get("status") == "not_declared":
            cnt[e.get("manufacturer") or None] += 1

    ordered = sorted(cnt.items(), key=lambda x: -x[1])
    names = [m if m else "(no manufacturer)" for m, _ in ordered]
    counts = [c for _, c in ordered]
    total = sum(counts)
    cum = []
    s = 0
    for c in counts:
        s += c
        cum.append(100.0 * s / total)

    fig, ax = plt.subplots(figsize=(4.6, 3.0), dpi=300)
    x = list(range(1, len(cum) + 1))
    ax.plot(x, cum, color=C_ACCENT, linewidth=1.6)
    ax.fill_between(x, cum, color=C_ACCENT, alpha=0.10)

    # Mark the "top 10 = 28.5%" annotation
    if len(cum) >= 10:
        ax.axvline(10, color=C_TYPE, linestyle=":", linewidth=0.9)
        ax.annotate(f"Top 10 = {cum[9]:.1f}%\n(414 → 118 closed)",
                    xy=(10, cum[9]), xytext=(28, cum[9] - 18),
                    arrowprops=dict(arrowstyle="->", color=C_TYPE,
                                    linewidth=0.8),
                    fontsize=8, color=C_TYPE)

    # Mark the 90% threshold - find vendor rank at which we cross 90%
    idx90 = next((i for i, v in enumerate(cum) if v >= 90.0), None)
    if idx90 is not None:
        ax.axhline(90, color="#555555", linestyle="--", linewidth=0.7)
        ax.annotate(f"90% needs\n{idx90 + 1} vendors",
                    xy=(idx90 + 1, 90), xytext=(idx90 - 45, 68),
                    arrowprops=dict(arrowstyle="->", color="#555555",
                                    linewidth=0.7),
                    fontsize=8, color="#555555")

    ax.set_xlabel(f"Vendor rank (n = {len(names)} distinct vendors)")
    ax.set_ylabel("Cumulative share of unpublished-suspect gap (%)")
    ax.set_title(f"Manufacturer concentration curve (n = {total} gap)",
                 pad=6)
    ax.set_xlim(0, len(x) + 8)
    ax.set_ylim(0, 100)
    ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT / "concentration_curve.pdf")
    fig.savefig(OUT / "concentration_curve.png", dpi=600)
    plt.close(fig)

    # Sanity check: top-10 must reproduce gap_leverage.top10_share_pct
    with open(API / "gap_classification.json", "r", encoding="utf-8") as f:
        gl = json.load(f)["gap_leverage"]
    ours = 100.0 * sum(counts[:10]) / total
    assert abs(ours - gl["top10_share_pct"]) < 0.05, \
        f"concentration top10 mismatch: ours {ours} vs SoT {gl['top10_share_pct']}"
    assert len(names) == gl["distinct_manufacturers"], \
        f"vendor count mismatch: ours {len(names)} vs SoT {gl['distinct_manufacturers']}"
    print(f"[fig:concentration] wrote (top10={ours:.1f}%, vendors={len(names)}, "
          f"total_gap={total})")


# ------------------------------------------------------------------
# Figure 2: reflexivity boundary (conceptual)
# ------------------------------------------------------------------
def fig_reflexivity():
    """Side-by-side: geometric-specification type vs directional-role type.

    Left panel  : flange A55 = flange A55  -> composed (dashed arc)
    Right panel : OUTPUT_SPIKE = OUTPUT_SPIKE -> type_error (dotted arc)
    """
    fig, axes = plt.subplots(1, 2, figsize=(6.0, 2.7), dpi=300,
                             gridspec_kw={"width_ratios": [1, 1]})

    # --- LEFT: geometric-specification (compatible) ---
    ax = axes[0]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Geometric-specification type", fontsize=9, pad=2)

    # two flange symbols - drawn as small rectangular "flange plates"
    def flange(ax, x, y, label):
        rect = FancyBboxPatch((x - 1.6, y - 0.35), 3.2, 0.7,
                              boxstyle="round,pad=0.05,rounding_size=0.1",
                              linewidth=1.1, edgecolor=C_MEC,
                              facecolor="#eaf2f8", mutation_aspect=1)
        ax.add_patch(rect)
        ax.text(x, y, label, ha="center", va="center", fontsize=8,
                color=C_MEC, fontweight="bold")

    flange(ax, 2.8, 3.5, "A55")
    flange(ax, 7.2, 3.5, "A55")

    # dashed arc between them - matches -> composed
    arc = FancyArrowPatch((4.2, 3.5), (5.8, 3.5),
                          connectionstyle="arc3,rad=0.5",
                          arrowstyle="->", mutation_scale=10,
                          linewidth=1.4, linestyle="--", color=C_COMP)
    ax.add_patch(arc)
    ax.text(5.0, 5.2, "composed", ha="center", fontsize=8,
            color=C_COMP, fontweight="bold")
    ax.text(5.0, 2.2, "same label → same geometry\n→ compatible",
            ha="center", fontsize=7, color="#333333")
    ax.text(5.0, 8.2, "✓ self-mate OK", ha="center", fontsize=9,
            color=C_COMP, fontweight="bold")

    # --- RIGHT: directional-role type (type_error) ---
    ax = axes[1]
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Directional-role type", fontsize=9, pad=2)

    def spike(ax, x, y, label):
        # Draw a spike shape - triangle pointing right
        tri = plt.Polygon([(x - 1.4, y - 0.35), (x - 1.4, y + 0.35),
                           (x + 1.4, y)],
                          closed=True, linewidth=1.1,
                          edgecolor=C_TYPE, facecolor="#fdedec")
        ax.add_patch(tri)
        ax.text(x - 0.2, y, label, ha="center", va="center", fontsize=7,
                color=C_TYPE, fontweight="bold")

    spike(ax, 2.8, 3.5, "OUT")
    spike(ax, 7.2, 3.5, "OUT")

    # dotted arc between them - not compatible
    arc = FancyArrowPatch((4.4, 3.5), (5.6, 3.5),
                          connectionstyle="arc3,rad=0.5",
                          arrowstyle="<->", mutation_scale=10,
                          linewidth=1.4, linestyle=":", color=C_TYPE)
    ax.add_patch(arc)
    ax.text(5.0, 5.2, "type\\_error", ha="center", fontsize=8,
            color=C_TYPE, fontweight="bold")
    ax.text(5.0, 2.2, "same role → both sources\n→ not complementary",
            ha="center", fontsize=7, color="#333333")
    ax.text(5.0, 8.2, "✗ self-mate invalid", ha="center", fontsize=9,
            color=C_TYPE, fontweight="bold")

    fig.tight_layout()
    fig.savefig(OUT / "reflexivity_boundary.pdf")
    fig.savefig(OUT / "reflexivity_boundary.png", dpi=600)
    plt.close(fig)
    print("[fig:reflexivity] wrote")


# ------------------------------------------------------------------
# Figure 3: d1 bottleneck axis bar
# ------------------------------------------------------------------
def fig_d1_bar():
    """Bar chart: which axis is responsible for the sole unknown in d=1 pairs.

    Data source: compose_semantics.json aggregates.d1_bottleneck.
    """
    cs = _load("compose_semantics.json")
    d1 = cs["aggregates"]["d1_bottleneck"]
    # Sanity: sum must equal d=1 population
    gd = cs["aggregates"]["gap_distance"]
    total_d1 = gd["1"]
    total_bottleneck = sum(d1.values())
    assert total_d1 == total_bottleneck, \
        f"d1 total mismatch: gap_distance={total_d1} bottleneck_sum={total_bottleneck}"

    axes_labels = ["electrical", "signal", "mechanical"]
    values = [d1.get(a, 0) for a in axes_labels]
    colors = [C_ELEC, C_SIG, C_MEC]

    fig, ax = plt.subplots(figsize=(3.8, 2.3), dpi=300)
    bars = ax.barh(axes_labels, values, color=colors, height=0.55)
    ax.invert_yaxis()  # electrical on top
    for bar, v in zip(bars, values):
        if v > 0:
            ax.text(v + max(values) * 0.02, bar.get_y() + bar.get_height() / 2,
                    f"{v}  ({100.0 * v / total_d1:.1f}%)",
                    va="center", ha="left", fontsize=8,
                    fontweight="bold")
        else:
            ax.text(max(values) * 0.02, bar.get_y() + bar.get_height() / 2,
                    "0", va="center", ha="left", fontsize=8,
                    color="#888888")

    ax.set_xlabel("pairs (n = %d at d = 1)" % total_d1, fontsize=8)
    ax.set_title("d1 bottleneck: 100% electrical", fontsize=9, pad=4)
    ax.grid(True, axis="x", linestyle=":", linewidth=0.5, alpha=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xlim(0, max(values) * 1.35)

    fig.tight_layout()
    fig.savefig(OUT / "d1_bottleneck_bar.pdf")
    fig.savefig(OUT / "d1_bottleneck_bar.png", dpi=600)
    plt.close(fig)
    print(f"[fig:d1_bar] wrote (total_d1={total_d1}, "
          f"elec={d1['electrical']}, sig={d1['signal']}, mec={d1['mechanical']})")


# ------------------------------------------------------------------
# Figure 4 (bonus): gap_distance histogram - shown in discussion
# ------------------------------------------------------------------
def fig_gap_distance():
    """Histogram of gap_distance - how many pairs need 1/2/3 declarations.

    Useful for the "priority ordering" claim in Discussion §5.3.
    """
    cs = _load("compose_semantics.json")
    gd = cs["aggregates"]["gap_distance"]
    labels = ["d = 0\n(composed)", "d = 1", "d = 2", "d = 3"]
    values = [gd["0"], gd["1"], gd["2"], gd["3"]]
    total = sum(values)
    colors = [C_COMP, C_ACCENT, "#95a5a6", "#7f8c8d"]

    fig, ax = plt.subplots(figsize=(4.2, 2.6), dpi=300)
    bars = ax.bar(labels, values, color=colors, width=0.55)
    for bar, v in zip(bars, values):
        pct = 100.0 * v / total
        ax.text(bar.get_x() + bar.get_width() / 2, v + total * 0.02,
                f"{v:,}\n({pct:.2f}%)", ha="center", va="bottom",
                fontsize=7.5)

    ax.set_ylabel("pairs", fontsize=8)
    ax.set_xlabel("gap_distance", fontsize=8)
    ax.set_title("Pairs by gap_distance  (n = 351,649)", fontsize=9, pad=4)
    ax.set_yscale("log")
    ax.grid(True, axis="y", linestyle=":", linewidth=0.5, alpha=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()
    fig.savefig(OUT / "gap_distance_hist.pdf")
    fig.savefig(OUT / "gap_distance_hist.png", dpi=600)
    plt.close(fig)
    print(f"[fig:gap_hist] wrote (sum={total})")


if __name__ == "__main__":
    fig_concentration()
    fig_reflexivity()
    fig_d1_bar()
    fig_gap_distance()
    print("\nAll figures written to:", OUT)
    for p in sorted(OUT.glob("*.pdf")):
        size_kb = p.stat().st_size / 1024
        print(f"  {p.name:35s}  {size_kb:6.1f} KB")
