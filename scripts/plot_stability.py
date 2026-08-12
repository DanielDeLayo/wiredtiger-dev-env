import matplotlib.pyplot as plt
import pandas as pd
import os

WORKSPACE = "/Users/danieldelayo/Gits/wiredtiger-dev-env"
RESULTS_DIR = "/Users/danieldelayo/Gits/wiredtiger/build/verify_results"
STABILITY_CSV = os.path.join(RESULTS_DIR, "stability.csv")
OUTPUT_PLOT = os.path.join(WORKSPACE, "plots", "stability_mrc.png")

df = pd.read_csv(STABILITY_CSV)

plt.figure(figsize=(8, 5))
plt.plot(df['Run'], df['MissRatio'], marker='o', linestyle='-', color='red', markersize=8)

# Calculate mean and std dev
mean_val = df['MissRatio'].mean()
std_val = df['MissRatio'].std()

plt.axhline(y=mean_val, color='blue', linestyle='--', label=f'Mean ({mean_val:.4f})')
plt.fill_between(df['Run'], mean_val - std_val, mean_val + std_val, color='blue', alpha=0.1, label=f'±1 Std Dev ({std_val:.4f})')

plt.ylim(0, max(0.5, df['MissRatio'].max() * 1.5))
plt.xticks(df['Run'])
plt.xlabel("wtperf Run Iteration")
plt.ylabel("WiredTiger Cache Miss Ratio")
plt.title("Stability of Miss Ratio across 5 runs (10MB Cache, 100% Read, 20s)")
plt.legend()
plt.grid(True)
plt.savefig(OUTPUT_PLOT)
print(f"Plot saved to {OUTPUT_PLOT}")
