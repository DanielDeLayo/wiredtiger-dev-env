#!/bin/bash
set -e

WT_DIR="/Users/danieldelayo/Gits/wiredtiger"
WTPERF_CMD="$WT_DIR/build/bench/wtperf/wtperf"
WTPERF_CONFIG="$WT_DIR/bench/wtperf/runners/ycsb-100read.wtperf"

mkdir -p "$WT_DIR/build/verify_results"
echo "Run,MissRatio" > "$WT_DIR/build/verify_results/stability.csv"

for i in {1..5}; do
    echo "Running iteration $i..."
    cd "$WT_DIR"
    rm -rf WT_TEST
    mkdir WT_TEST
    
    $WTPERF_CMD -O "$WTPERF_CONFIG" -o conn_config="\"cache_size=10M,log=(enabled=false)\"" -o run_ops=10000000 -o icount=100000 -o warmup=2 > "build/verify_results/stability_run_${i}.log" 2>&1 || true

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
        
        echo "$i,$MISS_RATIO" >> "build/verify_results/stability.csv"
        echo "Iteration $i | Pages Read: $PAGES_READ | Pages Requested: $PAGES_REQUESTED | Miss Ratio: $MISS_RATIO"
    fi
done
