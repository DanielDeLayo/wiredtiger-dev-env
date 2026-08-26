#!/bin/bash
set -e

WORKSPACE_DIR="/Users/danieldelayo/Gits/wiredtiger-dev-env"
WT_DIR="/Users/danieldelayo/Gits/wiredtiger"
WTPERF_CMD="$WT_DIR/build/bench/wtperf/wtperf"
WTPERF_CONFIG="$WT_DIR/bench/wtperf/runners/ycsb-100read.wtperf"
RESULTS_DIR="$WT_DIR/build/verify_results_skew_sweep"

# Pareto exponents to sweep. 0 = uniform, higher = more skewed.
PARETO_VALUES=(0 20 50 80)
CACHE_SIZES=("10M" "25M" "50M" "75M" "100M" "150M")
ICOUNT=100000

mkdir -p "$RESULTS_DIR"
cd "$RESULTS_DIR"

for pareto in "${PARETO_VALUES[@]}"; do
    PARETO_DIR="$RESULTS_DIR/pareto_$pareto"
    mkdir -p "$PARETO_DIR"
    echo "CacheSize,MissRatio" > "$PARETO_DIR/real_miss_ratios.csv"

    for size in "${CACHE_SIZES[@]}"; do
        echo "======================================"
        echo "Running wtperf: pareto=$pareto cache=$size"
        echo "======================================"

        rm -rf WT_TEST_SWEEP
        mkdir WT_TEST_SWEEP

        $WTPERF_CMD -h WT_TEST_SWEEP -O "$WTPERF_CONFIG" \
            -o conn_config="\"cache_size=$size,log=(enabled=false)\"" \
            -o pareto=$pareto \
            -o threads="((count=4,reads=1))" \
            -o populate_threads=1 \
            -o run_ops=2000000 \
            -o run_time=60 \
            -o icount=$ICOUNT \
            -o warmup=0 > wtperf_sweep.log 2>&1 || true

        python3 -c '
import sys, re

log_file = "wtperf_sweep.log"
out_file = "'"$PARETO_DIR"'/iaf_'"$size"'.hist"

last_csv = []
current_csv = []
in_csv = False

try:
    with open(log_file, "r") as f:
        for line in f:
            line = line.strip()
            if "[ERROR]:" in line and len(line.split("[ERROR]: ")) > 1:
                potential_start = line.split("[ERROR]: ")[1].strip()
                if re.match(r"^\d+,\d+,\d+$", potential_start):
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

        STAT_FILE=$(ls -t WT_TEST_SWEEP/WiredTigerStat.* 2>/dev/null | head -n 1)
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

            echo "pareto=$pareto | Size: $size | Pages Read: $PAGES_READ | Pages Requested: $PAGES_REQUESTED | Miss Ratio: $MISS_RATIO"
            echo "$size,$MISS_RATIO" >> "$PARETO_DIR/real_miss_ratios.csv"
        else
            echo "Warning: No stats file found for pareto=$pareto size=$size"
        fi
    done
done

echo "Skew sweep complete."
