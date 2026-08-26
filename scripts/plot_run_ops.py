import sys
import re
import matplotlib.pyplot as plt

def get_curve(log_file):
    sizes = []
    hits = []
    total = 0
    in_csv = False
    try:
        with open(log_file, "r") as f:
            for line in f:
                line = line.strip()
                if "[ERROR]:" in line and len(line.split("[ERROR]: ")) > 1:
                    potential_start = line.split("[ERROR]: ")[1].strip()
                    if re.match(r"^\d+,\d+,\d+$", potential_start):
                        total = int(potential_start.split(",")[0])
                        sizes = []
                        hits = []
                elif line == "Cache Size,Hits":
                    in_csv = True
                elif in_csv:
                    if line == "" or "[" in line:
                        in_csv = False
                    elif re.match(r"^\d+,\d+$", line):
                        parts = line.split(",")
                        sizes.append(int(parts[0]) * 256 / 1024 / 1024) # MB
                        hits.append(1 - (float(parts[1]) / total))
    except Exception as e:
        print(f"Error parsing {log_file}: {e}")
    return sizes, hits

s10, h10 = get_curve("build/verify_results/run_10M.log")
s500, h500 = get_curve("build/verify_results/run_500M.log")

plt.figure(figsize=(10, 6))
plt.plot(s10, h10, label="10M Cache", color="red")
plt.plot(s500, h500, label="500M Cache", color="blue", linestyle="--")
plt.xlim(0, max(max(s10, default=0), max(s500, default=0)))
plt.ylim(0, 1.0)
plt.xlabel("Simulated Cache Size (MB)")
plt.ylabel("Miss Ratio")
plt.title("IAF Curves with run_ops=5000000")
plt.legend()
plt.grid(True)
plt.savefig("/Users/danieldelayo/.gemini/antigravity-ide/brain/49addd11-cce3-447a-9ea5-b59eabe37dca/run_ops_mrc.png")
