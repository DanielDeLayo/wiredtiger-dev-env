import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np, os, sys

import _common
from _common import miss_at

SP    = sys.argv[1] if len(sys.argv) > 1 else "."
PAGE  = 32768          # 32 KiB leaf page; IAF sees 128 blocks of 256 B per page
OUT   = sys.argv[2] if len(sys.argv) > 2 else "plots"

def load(d, s, p):
    return _common.load("%s/%s/s%d_p%d.csv" % (SP, d, s, p))

def analyse(d, label, cache_gb, data_gb, fname):
    rates = [0, 1, 2, 3, 4, 7]          # log2 rates drawn as partition-0 lines
    swept = [0, 1, 2, 3, 4]             # rates run at every partition
    curves = {(s, p): load(d, s, p) for s in swept for p in range(1 << s)}
    curves.update({(s, 0): load(d, s, 0) for s in rates if s not in swept})
    top   = min(c[0][-1] for c in curves.values())
    grid  = np.unique(np.round(np.logspace(0, np.log10(top), 4000)).astype(np.int64))
    miss  = {k: miss_at(*v, grid) for k, v in curves.items()}
    gb    = grid * PAGE / (1024**3)
    exact = miss[(0, 0)]

    fig, axes = plt.subplots(1, 3, figsize=(19, 5.4))
    colors = {0:"#111111", 1:"#1f77b4", 2:"#d62728", 3:"#2ca02c", 4:"#9467bd", 7:"#8c564b"}

    ax = axes[0]
    for s in rates:
        ax.plot(gb, miss[(s,0)], color=colors[s], lw=2.4 if s==0 else 1.5,
                ls="-" if s==0 else "--", alpha=1.0 if s in (0,2) else 0.65,
                label=("exact (no sampling)" if s==0
                       else "1-in-%d%s" % (1<<s, "  <- shipped" if s==2 else "")))
    ax.axvline(cache_gb, color="#888", ls=":", lw=1.6)
    ax.text(cache_gb, 0.55, " 16 GB cache", color="#666", fontsize=9, rotation=90, va="bottom")
    ax.set_xscale("log"); ax.set_xlabel("cache size (GB, log)"); ax.set_ylabel("miss ratio")
    ax.set_title("MRC vs sampling rate, partition 0\n%s" % label)
    ax.grid(alpha=.3); ax.legend(fontsize=9)

    ax = axes[1]
    for s in rates[1:]:
        ax.plot(gb, (miss[(s,0)]-exact)*100, color=colors[s], lw=2.0 if s==2 else 1.2,
                alpha=1.0 if s==2 else 0.6, label="1-in-%d (p0)" % (1<<s))
    ax.axhline(0, color="#111", lw=1)
    ax.axvline(cache_gb, color="#888", ls=":", lw=1.6)
    ax.set_xscale("log"); ax.set_xlabel("cache size (GB, log)")
    ax.set_ylabel("miss-ratio error (percentage points)")
    ax.set_title("Error vs exact (positive = overstates misses)")
    ax.grid(alpha=.3); ax.legend(fontsize=9)

    ax = axes[2]
    for s in rates[1:4]:
        band = np.array([miss[(s,p)] for p in range(1 << s)])
        ax.fill_between(gb, (band.min(0)-exact)*100, (band.max(0)-exact)*100,
                        color=colors[s], alpha=0.20)
        ax.plot(gb, (band.mean(0)-exact)*100, color=colors[s], lw=1.8,
                label="1-in-%d: mean of %d partitions" % (1<<s, 1<<s))
    ax.axhline(0, color="#111", lw=1)
    ax.axvline(cache_gb, color="#888", ls=":", lw=1.6)
    ax.set_xscale("log"); ax.set_xlabel("cache size (GB, log)")
    ax.set_ylabel("miss-ratio error (pp)")
    ax.set_title("Partition spread (band) vs mean of partitions")
    ax.grid(alpha=.3); ax.legend(fontsize=9)

    plt.tight_layout(); plt.savefig("%s/%s" % (OUT, fname), dpi=130)

    print("\n=== %s ===" % label)
    print("  dataset %.1f GB over %d pages, cache %.0f GB" % (data_gb, int(top), cache_gb))
    near = (gb >= cache_gb*0.5) & (gb <= cache_gb*2)
    print("  %-12s %9s %9s %9s %9s" % ("rate", "max err", "mean err", "@16GB", "near 16GB"))
    for s in rates[1:]:
        e = np.abs(miss[(s,0)]-exact)*100
        at = np.interp(cache_gb, gb, (miss[(s,0)]-exact)*100)
        print("  1-in-%-7d %8.3fpp %8.3fpp %8.3fpp %8.3fpp"
              % ((1<<s), e.max(), e.mean(), at, e[near].max() if near.any() else float('nan')))
    print("  --- partition spread at the 16 GB operating point ---")
    for s in rates[1:4]:
        vals = [np.interp(cache_gb, gb, (miss[(s,p)]-exact)*100) for p in range(1 << s)]
        print("  1-in-%-7d spread %6.3fpp  [%+.3f .. %+.3f]  mean %+.3fpp"
              % ((1<<s), max(vals)-min(vals), min(vals), max(vals), np.mean(vals)))
    print("  exact miss ratio at 16 GB: %.4f" % np.interp(cache_gb, gb, exact))
    print("  wrote %s/%s" % (OUT, fname))

analyse("curves_pareto",    "out_of_cache: pareto=20, scramble, 30M recs (~32 GB), 200M accesses",
        16.0, 32.0, "sampling_pareto20_out_of_cache.png")
analyse("curves_pareto_in", "in_cache: pareto=20, scramble, 6M recs (~6.4 GB), 200M accesses",
        16.0,  6.4, "sampling_pareto20_in_cache.png")

analyse("curves_pareto_nohot",
        "control: same trace, out-of-range draws redrawn instead of clamped to record 0",
        16.0, 32.0, "sampling_pareto20_nohotpage.png")
