#!/bin/bash
set -e
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"

DEV_ENV_DIR="/Users/danieldelayo/Gits/wiredtiger-dev-env"
MONGO_DIR="/Users/danieldelayo/Gits/mongo"
MONGOD_CMD="$MONGO_DIR/bazel-bin/src/mongo/db/mongod"
YCSB_DIR="$DEV_ENV_DIR/tools/ycsb-0.17.0"
YCSB_CMD="$YCSB_DIR/bin/ycsb"

DISTRIBUTION=${1:-zipfian}
RESULTS_DIR="$DEV_ENV_DIR/data/verify_results_mongo_$DISTRIBUTION"

CACHE_SIZES=("1M" "2M" "3M" "4M" "5M" "6M" "7M" "8M" "9M" "10M")
RECORD_COUNT=300000
OPERATION_COUNT=300000

mkdir -p "$RESULTS_DIR"
cd "$RESULTS_DIR"

echo "CacheSize,MissRatio" > "$RESULTS_DIR/real_miss_ratios.csv"

# Kill any existing mongod
killall mongod 2>/dev/null || true

for size in "${CACHE_SIZES[@]}"; do
    echo "======================================"
    echo "Running mongod with cache size: $size"
    echo "======================================"

    rm -rf MONGO_DATA
    mkdir -p MONGO_DATA

    # Start mongod. We pass statistics_log to periodically flush WT stats to a file.
    $MONGOD_CMD --dbpath MONGO_DATA --wiredTigerEngineConfigString="cache_size=$size,statistics=(all),statistics_log=(wait=1)" --logpath mongod.log &
    MONGOD_PID=$!

    echo "Waiting for mongod to start..."
    sleep 3

    echo "Loading data with YCSB..."
    $YCSB_CMD load mongodb -s -P $YCSB_DIR/workloads/workloadc -p mongodb.url="mongodb://localhost:27017/ycsb?w=0" -p recordcount=$RECORD_COUNT > ycsb_load.log 2>&1

    echo "Running workload with YCSB ($DISTRIBUTION)..."
    $YCSB_CMD run mongodb -s -P $YCSB_DIR/workloads/workloadc -p mongodb.url="mongodb://localhost:27017/ycsb?w=0" -p requestdistribution=$DISTRIBUTION -p operationcount=$OPERATION_COUNT > ycsb_run.log 2>&1

    echo "Shutting down mongod to flush IAF trace..."
    kill -2 $MONGOD_PID || true
    wait $MONGOD_PID || true
    
    # Wait for mongod to fully exit and finish writing the log
    sleep 2

    out_file="iaf_${size}.hist"
    if [ -f "MONGO_DATA/iaf_trace.hist" ]; then
        mv MONGO_DATA/iaf_trace.hist "$out_file"
        echo "Successfully extracted IAF hist file to $out_file"
    else
        echo "Warning: No IAF hist file could be extracted!"
    fi

    # Extract cache misses from WiredTiger statistics
    STAT_FILE=$(ls -t MONGO_DATA/WiredTigerStat.* 2>/dev/null | head -n 1)
    if [ -n "$STAT_FILE" ]; then
        PAGES_READ_INTERNAL=$(grep "internal pages read into cache" "$STAT_FILE" | tail -n 1 | awk '{print $4}')
        PAGES_READ_LEAF=$(grep "leaf pages read into cache" "$STAT_FILE" | tail -n 1 | awk '{print $4}')
        PAGES_REQ_INTERNAL=$(grep "pages requested from the cache internal" "$STAT_FILE" | tail -n 1 | awk '{print $4}')
        PAGES_REQ_LEAF=$(grep "pages requested from the cache leaf" "$STAT_FILE" | tail -n 1 | awk '{print $4}')

        PAGES_READ_INTERNAL=${PAGES_READ_INTERNAL:-0}
        PAGES_READ_LEAF=${PAGES_READ_LEAF:-0}
        PAGES_REQ_INTERNAL=${PAGES_REQ_INTERNAL:-0}
        PAGES_REQ_LEAF=${PAGES_REQ_LEAF:-0}

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

echo "MongoDB verification data collection complete."
