"""Sampled vs exact miss-ratio curves from real WiredTiger runs.

    plot_wt_convergence.py <out.png> <exact.log> <exact_repeat.log> <rate>=<sampled.log> ...

Each log is a WiredTiger verbose log with IAF-SUMMARY dumps; the last dump (the run
connection's) is used. The first exact log is the reference. The repeat is a second
unsampled run of the same workload: its distance from the reference is run-to-run noise,
the floor any sampled run can be judged against. Separate runs cannot share an access
stream, so every difference here includes that noise.

    e.g. plot_wt_convergence.py wt.png s0a.log s0b.log 4=s2.log 16=s4.log 128=s7.log
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "handoff"))
from plot_mrc import BLOCK, parse   # the handoff parser, so both read the log the same way

OUT, EXACT, REPEAT = sys.argv[1], sys.argv[2], sys.argv[3]
SAMPLED = [(int(a.split("=", 1)[0]), a.split("=", 1)[1]) for a in sys.argv[4:]]
LO_GB = 5e-3

SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, BAND = "#e1e0d9", "#c3c2b7", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]      # reference palette slots 1-3, light mode

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "xtick.color": MUTED,
    "ytick.color": MUTED, "text.color": INK, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 1, "grid.linestyle": "-", "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10, "axes.titlesize": 11,
    "axes.titleweight": "bold", "legend.frameon": False,
})


def last_dump(path):
    d = parse(path)[-1]
    return np.array(d["sz"], float), np.array(d["hits"], float), d["total"], d["raw"], d["summary"]


def mrc_at(dump, grid):
    sz, hits, total, raw, _ = dump
    idx = np.searchsorted(sz, grid, side="right") - 1
    h = np.where(idx >= 0, hits[np.clip(idx, 0, len(hits) - 1)], 0.0)
    return (total - h) / raw


exact, repeat = last_dump(EXACT), last_dump(REPEAT)
samp = [(r, last_dump(p)) for r, p in SAMPLED]
top = min(d[0][-1] for d in [exact, repeat] + [s for _, s in samp]) * 0.95
grid = np.unique(np.round(np.logspace(0, np.log10(top), 3000)).astype(np.int64))
gb = grid * BLOCK / 1024 ** 3
ex = mrc_at(exact, grid)
summ = exact[4]
cache_gb = int(summ["cache_bytes"]) / 1024 ** 3
observed = 1 - float(summ["hit_rate_pct"]) / 100

fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
ax = axes[0]
ax.plot(gb, ex, color=BAND, lw=7, solid_capstyle="round", label="exact (no sampling)")
for (r, d), c in zip(samp, SERIES):
    ax.plot(gb, mrc_at(d, grid), color=c, lw=1.6, label="1-in-%d" % r)
ax.axvline(cache_gb, color=INK2, lw=1, ls=(0, (1, 2)))
ax.set_xscale("log")
ax.set_xlabel("cache size (GB, log)")
ax.set_ylabel("miss ratio")
ax.set_title("WiredTiger: sampled vs exact miss-ratio curve", loc="left", pad=18)
ax.text(0, 1.01, "wtperf, pareto=20, 3M records (~3.4 GB), %.1f GB cache, %dM page accesses"
        % (cache_gb, round(exact[3] / 1e6)), transform=ax.transAxes, color=INK2,
        fontsize=9, va="bottom")
ax.legend(loc="lower left", fontsize=9)

ax = axes[1]
ax.axhspan(-1, 1, color=GRID, alpha=0.55, lw=0, label="within 1 point")
ax.axhline(0, color=AXIS, lw=1)
ax.axvspan(gb[0], LO_GB, color=GRID, alpha=0.35, lw=0)
ax.plot(gb, (mrc_at(repeat, grid) - ex) * 100, color=MUTED, lw=1.2,
        label="second exact run (run-to-run noise)")
for (r, d), c in zip(samp, SERIES):
    ax.plot(gb, (mrc_at(d, grid) - ex) * 100, color=c, lw=1.2, label="1-in-%d" % r)
ax.axvline(cache_gb, color=INK2, lw=1, ls=(0, (1, 2)))
ax.text(cache_gb, 2.85, "%.1f GB cache " % cache_gb, color=INK2, fontsize=8.5, rotation=90,
        va="top", ha="right")
ax.set_xscale("log")
ax.set_ylim(-3, 3)
ax.set_xlabel("cache size (GB, log)")
ax.set_ylabel("minus the exact run (percentage points)")
ax.set_title("Error vs the exact run", loc="left", pad=18)
ax.legend(loc="upper left", fontsize=9)
plt.tight_layout()
plt.savefig(OUT, dpi=140)

keep = gb >= LO_GB
print("reference: %s  raw_accesses=%d  WiredTiger measured miss ratio %.4f" % (EXACT, exact[3], observed))
print("%-26s %14s %13s %13s %10s" % ("run", "raw_accesses", "mean |err|", "@ cache", "T/R - 1"))
for label, d in [("second exact run", repeat)] + [("1-in-%d" % r, d) for r, d in samp]:
    e = (mrc_at(d, grid) - ex) * 100
    at = np.interp(cache_gb, gb, e)
    print("%-26s %14d %11.3fpp %+11.3fpp %+9.2f%%" % (label, d[3], np.abs(e[keep]).mean(), at,
                                                       (d[2] / d[3] - 1) * 100))
print("wrote %s" % OUT)
