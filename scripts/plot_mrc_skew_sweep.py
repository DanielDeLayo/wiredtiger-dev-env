import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os

WT_DIR = "/Users/danieldelayo/Gits/wiredtiger"
RESULTS_DIR = os.path.join(WT_DIR, "build/verify_results_skew_sweep")
PAGE_SIZE_BYTES = 256

PARETO_VALUES = [0, 20, 50, 80]
IAF_COLORS   = ['#1f77b4', '#2ca02c', '#d62728', '#9467bd']  # blue, green, red, purple
REAL_MARKERS = ['o', 's', '^', 'D']

def parse_size_str(size_str):
    if size_str.endswith('M'):
        return int(size_str[:-1]) * 1024 * 1024
    if size_str.endswith('G'):
        return int(size_str[:-1]) * 1024 * 1024 * 1024
    return int(size_str)

fig, ax = plt.subplots(figsize=(12, 7))

for i, pareto in enumerate(PARETO_VALUES):
    pareto_dir = os.path.join(RESULTS_DIR, f"pareto_{pareto}")
    if not os.path.isdir(pareto_dir):
        print(f"Missing results for pareto={pareto}, skipping.")
        continue

    color = IAF_COLORS[i % len(IAF_COLORS)]
    marker = REAL_MARKERS[i % len(REAL_MARKERS)]
    label_suffix = "uniform" if pareto == 0 else f"pareto={pareto}"

    # Plot IAF curve from each hist file (pick the one that covers most cache sizes)
    hist_files = sorted(f for f in os.listdir(pareto_dir) if f.startswith('iaf_') and f.endswith('.hist'))
    best_df = None
    best_accesses = 0

    for hist_file in hist_files:
        path = os.path.join(pareto_dir, hist_file)
        if os.path.getsize(path) == 0:
            continue
        df = pd.read_csv(path, skiprows=1)
        if df.empty or len(df.columns) < 2:
            continue
        with open(path) as f:
            meta = f.readline().strip()
        try:
            total = float(meta.split(',')[0])
        except:
            continue
        if total > best_accesses:
            best_accesses = total
            best_df = df
            best_total = total

    if best_df is not None:
        cache_sizes_pages = best_df.iloc[:, 0].astype(float).values
        hits = best_df.iloc[:, 1].astype(float).values
        miss_ratios = 1.0 - (hits / best_total)
        cache_sizes_mb = (cache_sizes_pages * PAGE_SIZE_BYTES) / (1024 * 1024)
        ax.plot(cache_sizes_mb, miss_ratios,
                color=color, linewidth=2,
                label=f"IAF ({label_suffix})")

    # Plot real WT miss ratio points
    real_path = os.path.join(pareto_dir, "real_miss_ratios.csv")
    if os.path.exists(real_path):
        real_df = pd.read_csv(real_path)
        real_mb = [parse_size_str(r['CacheSize']) / (1024 * 1024) for _, r in real_df.iterrows()]
        real_mr = [r['MissRatio'] for _, r in real_df.iterrows()]
        ax.scatter(real_mb, real_mr,
                   color=color, marker=marker, s=80, zorder=5,
                   label=f"Real WT ({label_suffix})")

ax.set_xlabel(f'Cache Size (MB) [IAF block = {PAGE_SIZE_BYTES}B]', fontsize=13)
ax.set_ylabel('Miss Ratio', fontsize=13)
ax.set_title('MRC vs. Access Skew (Pareto exponent sweep)', fontsize=14)
ax.legend(fontsize=10)
ax.grid(True, alpha=0.4)
plt.tight_layout()

out_path = '/Users/danieldelayo/.gemini/antigravity-ide/brain/49addd11-cce3-447a-9ea5-b59eabe37dca/verification_mrc_skew_sweep.png'
plt.savefig(out_path, dpi=150)
print(f"Plot saved to verification_mrc_skew_sweep.png")
