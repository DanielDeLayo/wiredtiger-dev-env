#!/bin/bash
set -e

WORKSPACE_DIR="/Users/danieldelayo/Gits/wiredtiger-dev-env"
WT_DIR="/Users/danieldelayo/Gits/wiredtiger"
WTPERF_CMD="$WT_DIR/build/bench/wtperf/wtperf"
WTPERF_CONFIG="$WT_DIR/bench/wtperf/runners/ycsb-100read.wtperf"
RESULTS_DIR="$WT_DIR/build/verify_results"

CACHE_SIZES=("2M" "5M" "10M" "20M" "50M" "100M" "200M")
RUN_TIME=20
ICOUNT=100000

mkdir -p "$RESULTS_DIR"
cd "$RESULTS_DIR"

echo "CacheSize,MissRatio" > "$RESULTS_DIR/real_miss_ratios.csv"
rm -f "$RESULTS_DIR/"*.hist

# Run for different cache sizes
for size in "${CACHE_SIZES[@]}"; do
    echo "======================================"
    echo "Running wtperf with cache size: $size"
    echo "======================================"

    # We clear WT_TEST to ensure fresh stats
    rm -rf WT_TEST
    mkdir WT_TEST
    
    # Run wtperf and capture output to extract the printed IAF CSV
    $WTPERF_CMD -O "$WTPERF_CONFIG" -o conn_config="\"cache_size=$size,log=(enabled=false)\"" -o run_ops=10000000 -o icount=$ICOUNT -o warmup=2 > wtperf_out.log 2>&1 || true

    # Extract the CSV from wtperf_out.log
    # The CSV starts with a line containing 3 comma-separated numbers (e.g. 14887219,930,14887219)
    # But it is prefixed with WT error logs.
    # We will use python to reliably extract the last complete CSV from the log.
    python3 -c '
import sys
import re

log_file = "wtperf_out.log"
out_file = "'"$RESULTS_DIR"'/iaf_'"$size"'.hist"

last_csv = []
current_csv = []
in_csv = False

try:
    with open(log_file, "r") as f:
        for line in f:
            line = line.strip()
            # The start of the CSV might be embedded in the ERROR prefix:
            # e.g. "[WT_VERB_EVICTION][ERROR]: 14887219,930,14887219"
            if "[ERROR]:" in line and len(line.split("[ERROR]: ")) > 1:
                potential_start = line.split("[ERROR]: ")[1].strip()
                if re.match(r"^\d+,\d+,\d+$", potential_start):
                    # Save the previous one if it was complete
                    if len(current_csv) > 2:
                        last_csv = current_csv
                    current_csv = [potential_start]
                    in_csv = True
                    continue
                    
            if in_csv:
                if line == "Cache Size,Hits" or re.match(r"^\d+,\d+$", line):
                    current_csv.append(line)
                elif line == "" or "[" in line:
                    in_csv = False
                    if len(current_csv) > 2:
                        last_csv = current_csv
                    
    # Also check if it finished on a csv
    if len(current_csv) > 2:
        last_csv = current_csv

    if last_csv:
        with open(out_file, "w") as out:
            out.write("\n".join(last_csv) + "\n")
        print("Successfully extracted IAF hist file.")
    else:
        print("Warning: No IAF hist file could be extracted!")
except Exception as e:
    print(f"Error parsing log: {e}")
'

    # Extract cache misses from WiredTiger statistics
    STAT_FILE=$(ls -t WT_TEST/WiredTigerStat.* 2>/dev/null | head -n 1)
    if [ -n "$STAT_FILE" ]; then
        LAST_STAT=$(tail -n 1 "$STAT_FILE")
        
        PAGES_READ_INTERNAL=$(echo "$LAST_STAT" | jq '.wiredTiger.cache["internal pages read into cache"] // 0')
        PAGES_READ_LEAF=$(echo "$LAST_STAT" | jq '.wiredTiger.cache["leaf pages read into cache"] // 0')
        PAGES_REQ_INTERNAL=$(echo "$LAST_STAT" | jq '.wiredTiger.cache["pages requested from the cache internal"] // 0')
        PAGES_REQ_LEAF=$(echo "$LAST_STAT" | jq '.wiredTiger.cache["pages requested from the cache leaf"] // 0')

        PAGES_READ=$((PAGES_READ_INTERNAL + PAGES_READ_LEAF))
        PAGES_REQUESTED=$((PAGES_REQ_INTERNAL + PAGES_REQ_LEAF))
        
        if [ "$PAGES_REQUESTED" -ne 0 ]; then
            MISS_RATIO=$(echo "scale=6; $PAGES_READ / $PAGES_REQUESTED" | bc)
        else
            MISS_RATIO="0"
        fi
        
        echo "Size: $size | Pages Read: $PAGES_READ | Pages Requested: $PAGES_REQUESTED | Miss Ratio: $MISS_RATIO"
        echo "$size,$MISS_RATIO" >> "$RESULTS_DIR/real_miss_ratios.csv"
    else
        echo "Warning: No stats file found for size $size"
    fi
done

echo "Verification data collection complete."
