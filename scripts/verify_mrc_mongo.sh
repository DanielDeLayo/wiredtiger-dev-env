#!/bin/bash
set -e
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"

DEV_ENV_DIR="/Users/danieldelayo/Gits/wiredtiger-dev-env"
MONGO_DIR="/Users/danieldelayo/Gits/mongo"

# Resolve binaries from bazel install-devcore or bazel-bin
if [ -f "$MONGO_DIR/bazel-bin/install-devcore/bin/mongod" ]; then
    MONGOD_CMD="$MONGO_DIR/bazel-bin/install-devcore/bin/mongod"
else
    MONGOD_CMD="$MONGO_DIR/bazel-bin/src/mongo/db/mongod"
fi

DISTRIBUTION=${1:-multitier}
WRITE_RATIO=${2:-0.0}

if [ "$WRITE_RATIO" != "0.0" ] && [ "$WRITE_RATIO" != "0" ]; then
    RESULTS_DIR="$DEV_ENV_DIR/data/verify_results_mongo_${DISTRIBUTION}_write${WRITE_RATIO}"
else
    RESULTS_DIR="$DEV_ENV_DIR/data/verify_results_mongo_$DISTRIBUTION"
fi
SEED_DIR="$DEV_ENV_DIR/data/mongo_data_seed"

CACHE_SIZES=("1M" "2M" "3M" "5M" "7M" "10M" "15M" "20M")
RECORD_COUNT=300000
OPERATION_COUNT=300000

mkdir -p "$RESULTS_DIR"
cd "$RESULTS_DIR"

# Kill any existing mongod
killall mongod 2>/dev/null || true

# ---------------------------------------------------------
# Phase 1: Populate Seed Data (Loaded Once)
# ---------------------------------------------------------
if [ ! -d "$SEED_DIR" ] || [ "${RELOAD:-0}" = "1" ]; then
    echo "======================================"
    echo "Populating Seed Database ($RECORD_COUNT documents)..."
    echo "======================================"
    rm -rf "$SEED_DIR"
    mkdir -p "$SEED_DIR"

    # Start mongod with generous cache so data loads quickly without eviction
    $MONGOD_CMD --dbpath "$SEED_DIR" --wiredTigerEngineConfigString="cache_size=1G" --logpath "$SEED_DIR/mongod_load.log" &
    LOAD_PID=$!

    echo "Waiting for seed mongod to start..."
    sleep 3

    $DEV_ENV_DIR/venv/bin/python3 $DEV_ENV_DIR/scripts/mongo_workload.py --action load --records $RECORD_COUNT --threads 8

    echo "Shutting down seed mongod..."
    kill -2 $LOAD_PID || true
    wait $LOAD_PID || true
    sleep 2

    # Clean any traces or stats from seed directory
    rm -f "$SEED_DIR/iaf_trace.hist" "$SEED_DIR/WiredTigerStat.*"
    echo "Seed database ready at $SEED_DIR"
else
    echo "======================================"
    echo "Using existing seed database at $SEED_DIR"
    echo "======================================"
fi

# ---------------------------------------------------------
# Phase 2: Benchmark Iterations Across Cache Sizes
# ---------------------------------------------------------
echo "CacheSize,MissRatio" > "$RESULTS_DIR/real_miss_ratios.csv"

for size in "${CACHE_SIZES[@]}"; do
    echo "======================================"
    echo "Running mongod with cache size: $size"
    echo "======================================"

    rm -rf MONGO_DATA
    # Copy clean seed database (APFS on macOS uses fast copy-on-write clone)
    cp -R "$SEED_DIR" MONGO_DATA
    rm -f MONGO_DATA/iaf_trace.hist MONGO_DATA/WiredTigerStat.*

    # Start mongod. Trace records cleanly starting from t=0 on pure read workload.
    $MONGOD_CMD --dbpath MONGO_DATA --wiredTigerEngineConfigString="cache_size=$size,statistics=(all),statistics_log=(wait=1)" --logpath mongod.log &
    MONGOD_PID=$!

    echo "Waiting for mongod to start..."
    sleep 3

    echo "Running fixed-count workload ($DISTRIBUTION, $OPERATION_COUNT ops, write_ratio: $WRITE_RATIO)..."
    $DEV_ENV_DIR/venv/bin/python3 $DEV_ENV_DIR/scripts/mongo_workload.py --action run --operations $OPERATION_COUNT --distribution $DISTRIBUTION --write-ratio $WRITE_RATIO --records $RECORD_COUNT --threads 8 > run.log 2>&1

    echo "Shutting down mongod to flush IAF trace..."
    kill -2 $MONGOD_PID || true
    wait $MONGOD_PID || true
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
