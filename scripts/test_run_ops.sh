#!/bin/bash
export WTPERF_CMD="./build/bench/wtperf/wtperf"
export WTPERF_CONFIG="bench/wtperf/runners/ycsb-100read.wtperf"

mkdir -p build/verify_results

for size in "10M" "500M"; do
    echo "Running with cache_size=$size..."
    rm -rf WT_TEST
    mkdir WT_TEST
    # Use run_ops instead of run_time
    $WTPERF_CMD -O "$WTPERF_CONFIG" -o conn_config="\"cache_size=$size,log=(enabled=false)\"" -o run_ops=5000000 -o icount=100000 -o warmup=0 > "build/verify_results/run_${size}.log" 2>&1 || true
    
    # Extract total accesses
    grep -B 1 "Cache Size,Hits" "build/verify_results/run_${size}.log" | tail -n 2
done
