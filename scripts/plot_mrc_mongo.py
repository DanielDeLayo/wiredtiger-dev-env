import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os
import sys

if len(sys.argv) < 3:
    print("Usage: plot_mrc_mongo.py <results_dir> <output_image_path>")
    sys.exit(1)

RESULTS_DIR = sys.argv[1]
OUTPUT_IMAGE = sys.argv[2]
os.makedirs(os.path.dirname(os.path.abspath(OUTPUT_IMAGE)), exist_ok=True)
PAGE_SIZE_BYTES = 256 # Assuming IAF is still quantized to 256 bytes

def parse_size_str(size_str):
    if size_str.endswith('M'):
        return int(size_str[:-1]) * 1024 * 1024
    if size_str.endswith('G'):
        return int(size_str[:-1]) * 1024 * 1024 * 1024
    return int(size_str)

plt.figure(figsize=(10, 6))

colors = ['blue', 'green', 'red', 'purple', 'orange', 'brown', 'cyan', 'magenta']
if os.path.exists(RESULTS_DIR):
    hist_files = [f for f in os.listdir(RESULTS_DIR) if f.startswith('iaf_') and f.endswith('.hist')]
    hist_files.sort(key=lambda f: parse_size_str(f.replace('iaf_', '').replace('.hist', '')))

    for i, hist_file in enumerate(hist_files):
        path = os.path.join(RESULTS_DIR, hist_file)
        if os.path.getsize(path) == 0:
            continue
        
        df = pd.read_csv(path, skiprows=1)
        if df.empty or len(df.columns) < 2:
            continue
            
        cache_sizes_pages = df.iloc[:, 0].astype(float).values
        hits = df.iloc[:, 1].astype(float).values
        
        with open(path, 'r') as f:
            meta_line = f.readline().strip()
        try:
            total_accesses = float(meta_line.split(',')[0])
        except:
            total_accesses = np.max(hits)
            
        if total_accesses == 0:
            continue
            
        miss_ratios = 1.0 - (hits / total_accesses)
        
        cache_sizes_mb = (cache_sizes_pages * PAGE_SIZE_BYTES) / (1024 * 1024)
        
        label = f"IAF Curve ({hist_file})"
        plt.plot(cache_sizes_mb, miss_ratios, label=label, color=colors[i % len(colors)])

    real_mrc_path = os.path.join(RESULTS_DIR, 'real_miss_ratios.csv')
    if os.path.exists(real_mrc_path):
        real_df = pd.read_csv(real_mrc_path)
        
        real_sizes_mb = []
        real_mr = []
        
        for idx, row in real_df.iterrows():
            size_bytes = parse_size_str(row['CacheSize'])
            real_sizes_mb.append(size_bytes / (1024 * 1024))
            real_mr.append(row['MissRatio'])
            
        plt.scatter(real_sizes_mb, real_mr, color='black', marker='X', s=100, label="Real WT Cache Miss Ratio", zorder=5)

plt.xlabel(f'Cache Size (MB) [Assuming {PAGE_SIZE_BYTES}B quantization]')
plt.ylabel('Miss Ratio')
plt.title(f'MongoDB Workload C: IAF vs Real WT Cache Stats ({os.path.basename(RESULTS_DIR)})')
plt.legend()
plt.grid(True)
plt.savefig(OUTPUT_IMAGE)
print(f"Plot saved to {OUTPUT_IMAGE}")
