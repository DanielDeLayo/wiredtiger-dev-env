import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os

WORKSPACE = "/Users/danieldelayo/Gits/wiredtiger-dev-env"
RESULTS_DIR = "/Users/danieldelayo/Gits/wiredtiger/build/verify_results"
PAGE_SIZE_BYTES = 256 # Assume IAF was quantized to 256-byte blocks
# If pages are 32KB, change this to 32768.

def parse_size_str(size_str):
    if size_str.endswith('M'):
        return int(size_str[:-1]) * 1024 * 1024
    if size_str.endswith('G'):
        return int(size_str[:-1]) * 1024 * 1024 * 1024
    return int(size_str)

plt.figure(figsize=(10, 6))

# 1. Plot IAF Miss Ratio Curves
# We plot the curve from each run to show consistency
colors = ['blue', 'green', 'red', 'purple', 'orange']
hist_files = [f for f in os.listdir(RESULTS_DIR) if f.startswith('iaf_') and f.endswith('.hist')]
hist_files.sort()

for i, hist_file in enumerate(hist_files):
    path = os.path.join(RESULTS_DIR, hist_file)
    if os.path.getsize(path) == 0:
        continue
    
    # Read the hist file
    # Format: First line is metadata. Second line is "Cache Size,Hits"
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
    
    # Convert pages to MB (IAF already uses in-memory footprint, so this is exact)
    cache_sizes_mb = (cache_sizes_pages * PAGE_SIZE_BYTES) / (1024 * 1024)
    
    label = f"IAF Curve ({hist_file})"
    plt.plot(cache_sizes_mb, miss_ratios, label=label, color=colors[i % len(colors)])

# 2. Plot Real Cache Statistics
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

plt.xlabel('Cache Size (MB) [Assuming {}B quantization]'.format(PAGE_SIZE_BYTES))
plt.ylabel('Miss Ratio')
plt.title('Uniform Experiment: Increment-and-Freeze vs Real WiredTiger Stats')
plt.legend()
plt.grid(True)
plt.savefig('/Users/danieldelayo/.gemini/antigravity-ide/brain/49addd11-cce3-447a-9ea5-b59eabe37dca/verification_mrc_uniform.png')
print("Plot saved to verification_mrc_uniform.png")
