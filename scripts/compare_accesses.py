import os
import re
import pandas as pd

RESULTS_DIR = "/Users/danieldelayo/Gits/wiredtiger/build/verify_results"

df = pd.read_csv(os.path.join(RESULTS_DIR, "stability.csv"))
# Re-extract the PAGES_REQUESTED from the log files since stability.csv doesn't have it
wt_reqs = []
for i in range(1, 6):
    log_file = os.path.join(RESULTS_DIR, f"stability_run_{i}.log")
    req = 0
    with open(log_file, "r") as f:
        for line in f:
            if "pages requested from the cache internal" in line or "pages requested from the cache leaf" in line:
                # We need to parse json or just grep the output of the shell script.
                pass
# Wait, stability_test.sh printed to stdout! Let's just grep the stability_test.sh stdout? No I didn't save it to a file.
# I will just parse WiredTigerStat.XX for each run? No, they were deleted!
