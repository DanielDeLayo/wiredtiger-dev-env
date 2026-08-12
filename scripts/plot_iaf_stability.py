import matplotlib.pyplot as plt
import os
import re
import json

WORKSPACE = "/Users/danieldelayo/Gits/wiredtiger-dev-env"
RESULTS_DIR = "/Users/danieldelayo/Gits/wiredtiger/build/verify_results"

CACHE_LIMIT_MB = 10
BLOCK_SIZE = 256
TARGET_BLOCKS = (CACHE_LIMIT_MB * 1024 * 1024) // BLOCK_SIZE

runs = []
wt_miss_ratios = []
iaf_miss_ratios = []

for i in range(1, 6):
    log_file = os.path.join(RESULTS_DIR, f"stability_run_{i}.log")
    if not os.path.exists(log_file):
        continue
        
    # We will use the WT stats from stability.csv that we already generated
    pass

import pandas as pd
df = pd.read_csv(os.path.join(RESULTS_DIR, "stability.csv"))
wt_miss_ratios = df['MissRatio'].tolist()
runs = df['Run'].tolist()

for i in range(1, 6):
    log_file = os.path.join(RESULTS_DIR, f"stability_run_{i}.log")
    
    total_accesses = 0
    hits_at_target = 0
    
    in_csv = False
    with open(log_file, "r") as f:
        for line in f:
            line = line.strip()
            if "[ERROR]:" in line and len(line.split("[ERROR]: ")) > 1:
                potential_start = line.split("[ERROR]: ")[1].strip()
                if re.match(r"^\d+,\d+,\d+$", potential_start):
                    in_csv = True
                    total_accesses = float(potential_start.split(",")[0])
                    continue
                    
            if in_csv:
                if line == "" or "[" in line:
                    if line != "" and not re.match(r"^\d+,\d+$", line) and line != "Cache Size,Hits":
                        in_csv = False
                elif re.match(r"^\d+,\d+$", line):
                    parts = line.split(",")
                    size = int(parts[0])
                    hits = float(parts[1])
                    if size <= TARGET_BLOCKS:
                        hits_at_target = hits
                    else:
                        in_csv = False # We passed our target, no need to parse further
    
    if total_accesses > 0:
        iaf_mr = 1.0 - (hits_at_target / total_accesses)
    else:
        iaf_mr = 0.0
    iaf_miss_ratios.append(iaf_mr)
    print(f"Run {i}: IAF Miss Ratio = {iaf_mr:.6f}")

plt.figure(figsize=(10, 6))
plt.plot(runs, wt_miss_ratios, marker='o', linestyle='-', color='red', markersize=8, label="WiredTiger Miss Ratio")
plt.plot(runs, iaf_miss_ratios, marker='s', linestyle='-', color='blue', markersize=8, label="IAF (Exact LRU) Miss Ratio")

# Calculate mean and std dev
wt_mean = sum(wt_miss_ratios) / len(wt_miss_ratios)
iaf_mean = sum(iaf_miss_ratios) / len(iaf_miss_ratios)

plt.axhline(y=wt_mean, color='red', linestyle='--', alpha=0.5, label=f'WT Mean ({wt_mean:.4f})')
plt.axhline(y=iaf_mean, color='blue', linestyle='--', alpha=0.5, label=f'IAF Mean ({iaf_mean:.4f})')

plt.ylim(0, max(0.5, max(wt_miss_ratios) * 1.5))
plt.xticks(runs)
plt.xlabel("wtperf Run Iteration")
plt.ylabel("Cache Miss Ratio")
plt.title(f"Stability: WiredTiger vs IAF across 5 runs ({CACHE_LIMIT_MB}MB Cache, 100% Read, 20s)")
plt.legend()
plt.grid(True)

OUTPUT_PLOT = os.path.join(WORKSPACE, "plots", "iaf_stability_mrc.png")
plt.savefig(OUTPUT_PLOT)
print(f"Plot saved to {OUTPUT_PLOT}")
