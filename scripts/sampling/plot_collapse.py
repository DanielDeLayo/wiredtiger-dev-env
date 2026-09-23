"""Does the sampling error collapse if you rescale the cache-size axis by the rate?

The intuition being tested: sampling 1-in-S means the curve only "sees" cache/S
blocks of residency, so a coarse rate is only a problem when the cache of interest
is small relative to S. If that were the whole story, plotting error against
*sampled* residency (cache_blocks / S) would collapse every rate onto one line.

It does not, and need not: the error peaks at a few sampled blocks, and above
~1 MiB of real cache it is the same at every rate.

    plot_collapse.py <curves_dir> <out.png>
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import BLOCK, common_grid, load_dir, miss_at

CURVES = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "sampling_collapse.png"
RATES = [1, 2, 3]

curves = {s: load_dir(CURVES, s, 0) for s in [0] + RATES}
grid = common_grid(list(curves.values()))
miss = {s: miss_at(*v, grid) for s, v in curves.items()}
mb = grid * BLOCK / (1024 * 1024)
exact = miss[0]
err = {s: np.abs(miss[s] - exact) * 100 for s in RATES}

colors = {1: "#1f77b4", 2: "#d62728", 3: "#2ca02c"}


def smooth(y, k=41):
    """Running RMS -- the raw error is spiky and the trend is what matters."""
    return np.sqrt(np.convolve(y ** 2, np.ones(k) / k, mode="same"))


fig, axes = plt.subplots(1, 3, figsize=(19, 5.4))

# Panel 1: error against the real cache size. Each rate peaks somewhere different.
ax = axes[0]
for s in RATES:
    ax.plot(mb, smooth(err[s]), color=colors[s], lw=1.8, label="1-in-%d" % (1 << s))
    i = np.argmax(smooth(err[s]))
    ax.plot(mb[i], smooth(err[s])[i], "o", color=colors[s], ms=7)
ax.set_xscale("log")
ax.set_xlabel("cache size (MiB, log)")
ax.set_ylabel("RMS miss-ratio error (pp)")
ax.set_title("Error vs real cache size\n(dots mark each rate's peak)")
ax.grid(alpha=.3)
ax.legend(fontsize=9)

# Panel 2: the same error against SAMPLED residency, cache_blocks / S. If the
# rescaling were the whole story these three would lie on top of each other.
ax = axes[1]
for s in RATES:
    ax.plot(grid / (1 << s), smooth(err[s]), color=colors[s], lw=1.8,
            label="1-in-%d" % (1 << s))
ref = grid / 2.0
ax.plot(ref, 40 * ref ** -0.5, color="#888888", ls="--", lw=1.4,
        label=r"$1/\sqrt{n}$ reference")
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("sampled blocks resident (cache_blocks / S, log)")
ax.set_ylabel("RMS error (pp, log)")
ax.set_title("Rescaled by the sampling rate\n(peaks at a few sampled blocks)")
ax.grid(alpha=.3, which="both")
ax.legend(fontsize=9)

# Panel 3: absolute error in the region that matters for a real deployment.
ax = axes[2]
for s in RATES:
    ax.plot(mb, smooth(err[s]), color=colors[s], lw=1.8, label="1-in-%d" % (1 << s))
ax.axhline(1.0, color="#111111", ls=":", lw=1.4)
ax.annotate("1pp", xy=(0.02, 1.0), xycoords=("axes fraction", "data"),
            xytext=(0, 4), textcoords="offset points", fontsize=9)
ax.set_xscale("log")
ax.set_xlabel("cache size (MiB, log)")
ax.set_ylabel("RMS error (pp)")
ax.set_ylim(0, 4)
ax.set_title("Large-cache regime")
ax.grid(alpha=.3)
ax.legend(fontsize=9)

plt.tight_layout()
plt.savefig(OUT, dpi=130)

print("%-8s %12s %14s %12s %12s" % ("rate", "peak err", "at sampled blk", ">256MiB", ">1GiB"))
big1 = mb >= 256
big2 = mb >= 1024
for s in RATES:
    sm = smooth(err[s])
    i = np.argmax(sm)
    print("1-in-%-3d %11.2fpp %14d %11.2fpp %11.2fpp"
          % ((1 << s), sm[i], grid[i] / (1 << s),
             sm[big1].mean() if big1.any() else float("nan"),
             sm[big2].mean() if big2.any() else float("nan")))

print("\ndecay exponent (err ~ cache^k; -0.5 would be 1/sqrt(n)):")
for s in RATES:
    m = (mb >= 1) & (smooth(err[s]) > 0)
    k = np.polyfit(np.log(mb[m]), np.log(smooth(err[s])[m]), 1)[0]
    print("  1-in-%-3d k = %+.3f" % ((1 << s), k))
print("\nwrote %s" % OUT)
