"""Does the sampled miss-ratio curve converge to the exact one? Two figures for the handoff.

    plot_convergence.py <curves_root> <out_dir>

<curves_root> holds curves_pareto/ and curves_pareto_in/ (see README, "Reproducing the
plots"). Writes:

  sampling_convergence.png          exact vs sampled curve, and the error, for both traces
  sampling_convergence_summary.png  mean error against sampling rate, partition 0 and the
                                    range over every partition
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import load, miss_at

ROOT, OUT = sys.argv[1], sys.argv[2]
PAGE_GB = 32768 / 1024 ** 3        # one unit on these curves' axis is one 32 KiB leaf page
LO_GB = 5e-3                       # below ~5 MB the sample holds too few pages to judge

TRACES = [
    ("curves_pareto", "out_of_cache", "pareto=20, 30M records (~32 GB), 16 GB cache", 30_000_000),
    ("curves_pareto_in", "in_cache", "pareto=20, 6M records (~6.4 GB), 16 GB cache", 6_000_000),
]
LINES = [(2, "1-in-4 (shipped)"), (4, "1-in-16"), (7, "1-in-128")]   # log2 rate, label
SWEPT = [1, 2, 3, 4]                                                # rates run at every partition

# Reference palette, light mode (dataviz references/palette.md).
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, BAND = "#e1e0d9", "#c3c2b7", "#c3c2b7"
SERIES = {2: "#2a78d6", 4: "#eb6834", 7: "#1baf7a"}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED,
    "ytick.color": MUTED, "text.color": INK, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 1, "grid.linestyle": "-", "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10, "axes.titlesize": 11,
    "axes.titleweight": "bold", "legend.frameon": False,
})


def curve(d, s, p=0):
    return load(os.path.join(ROOT, d, "s%d_p%d.csv" % (s, p)))


def grid_for(curves):
    top = min(c[0][-1] for c in curves) * 0.95
    return np.unique(np.round(np.logspace(0, np.log10(top), 3000)).astype(np.int64))


def mean_err(exact, samp, grid, gb):
    keep = gb >= LO_GB
    return np.abs(miss_at(*samp, grid) - miss_at(*exact, grid))[keep].mean() * 100


# ---- Figure 1: the curves and their error ------------------------------------------------
fig, axes = plt.subplots(2, 2, figsize=(13, 8.4))
for row, (d, name, desc, _) in enumerate(TRACES):
    exact = curve(d, 0)
    samp = {s: curve(d, s) for s, _ in LINES}
    grid = grid_for([exact] + list(samp.values()))
    gb = grid * PAGE_GB
    ex = miss_at(*exact, grid)

    ax = axes[row, 0]
    ax.plot(gb, ex, color=BAND, lw=7, solid_capstyle="round", label="exact (no sampling)")
    for s, label in LINES:
        ax.plot(gb, miss_at(*samp[s], grid), color=SERIES[s], lw=1.6, label=label)
    ax.set_xscale("log")
    ax.set_ylim(-0.02, 1.05)
    ax.set_xlabel("cache size (GB, log)")
    ax.set_ylabel("miss ratio")
    ax.set_title("%s: sampled curves lie on the exact one" % name, loc="left", pad=18)
    ax.text(0, 1.01, desc, transform=ax.transAxes, color=INK2, fontsize=9, va="bottom")
    ax.legend(loc="lower left", fontsize=9)

    ax = axes[row, 1]
    ax.axhspan(-1, 1, color=GRID, alpha=0.55, lw=0, label="within 1 point")
    ax.axhline(0, color=AXIS, lw=1)
    ax.axvspan(gb[0], LO_GB, color=GRID, alpha=0.35, lw=0)
    ax.text(np.sqrt(gb[0] * LO_GB), 2.75, "too few sampled\npages to judge",
            color=MUTED, fontsize=8.5, ha="center", va="top")
    for s, label in LINES:
        ax.plot(gb, (miss_at(*samp[s], grid) - ex) * 100, color=SERIES[s], lw=1.2,
                label=label)
    if gb[-1] >= 16:
        ax.axvline(16, color=INK2, lw=1, ls=(0, (1, 2)))
        ax.text(16, 2.85, "16 GB cache ", color=INK2, fontsize=8.5, rotation=90,
                va="top", ha="right")
    ax.set_xscale("log")
    ax.set_ylim(-3, 3)
    ax.set_xlabel("cache size (GB, log)")
    ax.set_ylabel("sampled minus exact (percentage points)")
    ax.set_title("%s: error vs the exact curve" % name, loc="left", pad=18)
    ax.legend(loc="lower center", bbox_to_anchor=(0.62, 0.02), fontsize=9, ncol=2)

plt.tight_layout(h_pad=2.2)
plt.savefig(os.path.join(OUT, "sampling_convergence.png"), dpi=140)

# ---- Figure 2: error against rate ---------------------------------------------------------
rates = [1, 2, 3, 4, 7]
fig, ax = plt.subplots(figsize=(8.6, 4.8))
styles = {"out_of_cache": dict(color=INK, marker="o", ls="-"),
          "in_cache": dict(color=MUTED, marker="s", ls="--")}
for d, name, _, recs in TRACES:
    exact = curve(d, 0)
    samp0 = {s: curve(d, s) for s in rates}
    grid = grid_for([exact] + list(samp0.values()))
    gb = grid * PAGE_GB
    p0 = [mean_err(exact, samp0[s], grid, gb) for s in rates]
    st = styles[name]
    ax.plot([1 << s for s in rates], p0, color=st["color"], ls=st["ls"], lw=2,
            marker=st["marker"], ms=8, mec=SURFACE, mew=2,
            label="%s, partition 0 (%s pages total)" % (name, format(recs // 29, ",")))
    for s in SWEPT:
        errs = [mean_err(exact, curve(d, s, p), grid, gb) for p in range(1 << s)]
        ax.vlines(1 << s, min(errs), max(errs), color=st["color"], lw=2, alpha=0.35)
    for s, v in zip(rates, p0):
        if s in (2, 7):
            dy = 9 if name == "in_cache" else -9
            ax.annotate("%.2f" % v, (1 << s, v), xytext=(9, dy), textcoords="offset points",
                        color=INK2, fontsize=9, va="center")
ax.plot([], [], color=MUTED, lw=2, alpha=0.35, label="range over every partition")
ax.set_xscale("log", base=2)
ax.set_xticks([1 << s for s in rates])
ax.set_xticklabels(["1-in-%d%s" % (1 << s, "\n(shipped)" if s == 2 else "") for s in rates])
ax.set_ylim(0, None)
ax.set_xlabel("sampling rate")
ax.set_ylabel("mean |error|, caches >= 5 MB (points)")
ax.set_title("Partition 0 stays under 0.2 points of error through 1-in-16", loc="left")
ax.legend(loc="upper left", fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(OUT, "sampling_convergence_summary.png"), dpi=140)
print("wrote %s/sampling_convergence.png and sampling_convergence_summary.png" % OUT)
