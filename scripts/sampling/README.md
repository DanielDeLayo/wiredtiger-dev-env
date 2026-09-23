# Sampling-accuracy experiments

How much does address-hash sampling distort the miss-ratio curve? These are the trace
generators and plotters behind `../../plots/sampling_*.png`.

Production ships **1-in-4, partition 0** (`WT_IAF_SAMPLING_LOG2` in
`wiredtiger/src/include/analyze_cache_inline.h`). The partition is hardcoded. That mattered
when the miss-ratio curve was divided by `total_requests`; divided by `raw_accesses`, it
barely does -- see "What these found" below.

## Computing the miss-ratio curve

Each curve is a CSV whose first line is `total_requests,curve_blocks,raw_accesses`. With
sampling, `total_requests` and the `Hits` column are sampled counts multiplied by the rate;
`raw_accesses` is the exact access count.

    miss_curve = total_requests - hits
    mrc        = miss_curve / raw_accesses

The miss curve is invariant to which addresses were sampled. `total_requests` is not: a heavy
hitter is entirely in or out of the sample, and shifts it by its scaled access count. The
miss-ratio curve therefore divides by `raw_accesses`, never by `total_requests`.
`_common.miss_at` does this; every plotter uses it.

Rows are sparse (emitted only where the curve moves), so the curve is a step function:
`_common` samples it with `searchsorted` and never interpolates.

## The generators

| file | trace | arguments |
|---|---|---|
| `samp_pareto.cc` | The harness's real workload: `pareto=20`, `scramble=true`, key 100 B + value 1024 B, 32 KiB leaf pages. Reproduces `wtperf_rand()` and `testutil_pareto()` exactly, then maps record -> leaf page. One unit on the cache-size axis is one page. | `<log2 rate> <partition> <records> <records per page> <accesses> <cap in pages>` |
| `samp_pareto_nohot.cc` | Identical, except out-of-range Pareto draws are redrawn instead of clamped to record 0. Isolates the artificial hot record. | as `samp_pareto` |
| `samp_part.cc` | Zipf theta=0.99 over 1M keys, 4 KiB pages (16 blocks each). | `<log2 rate> <cap in blocks> <accesses> <partition>` |
| `pop.cc` | Prints the page-level popularity histogram of the pareto trace. No curve, no IaF. | `<records> <records per page> <accesses>` |

Each `.cc` except `pop.cc` links straight against the IaF sources:

    IAF=~/Gits/Increment-and-Freeze
    for f in samp_pareto samp_pareto_nohot samp_part; do
        g++ -O3 -std=c++17 -I$IAF/includes -o /tmp/$f $f.cc \
            $IAF/src/bounded_iaf.cc $IAF/src/increment_and_freeze.cc $IAF/src/projection.cc
    done
    g++ -O3 -std=c++17 -o /tmp/pop pop.cc

## Reproducing the plots

Every run of a given trace sees the same access stream, so the difference between rates or
partitions is sampling error alone. Rate 0 (1-in-1) is the exact curve.

    SP=/tmp/curves
    mkdir -p $SP/curves_pareto $SP/curves_pareto_in $SP/curves_pareto_nohot $SP/curves_part

    # pareto, rates 1-in-1 through 1-in-16, every partition
    #   out_of_cache: 30M records (~32 GB);  in_cache: 6M records (~6.4 GB)
    for s in 0 1 2 3 4; do
        for p in $(seq 0 $(( (1<<s) - 1 ))); do
            /tmp/samp_pareto       $s $p 30000000 29 200000000 1200000 > $SP/curves_pareto/s${s}_p${p}.csv &
            /tmp/samp_pareto       $s $p  6000000 29 200000000  250000 > $SP/curves_pareto_in/s${s}_p${p}.csv &
            /tmp/samp_pareto_nohot $s $p 30000000 29 200000000 1200000 > $SP/curves_pareto_nohot/s${s}_p${p}.csv &
        done; wait
    done

    # Zipf, rates 1-in-1 through 1-in-8, every partition
    for s in 0 1 2 3; do
        for p in $(seq 0 $(( (1<<s) - 1 ))); do
            /tmp/samp_part $s 16000000 3000000 $p > $SP/curves_part/s${s}_p${p}.csv &
        done; wait
    done

    python3 plot_pareto.py     $SP               ../../plots   # the three sampling_pareto20_* figures
    python3 plot_partitions.py $SP/curves_part   ../../plots/sampling_partitions.png
    python3 plot_collapse.py   $SP/curves_part   ../../plots/sampling_collapse.png

The caps only need to cover the trace's footprint: a larger cap gives the same curve.

## What these found

**Dividing by `raw_accesses` removes the hot-record error.** Divided by `total_requests`, the
out_of_cache miss-ratio curve had ~2.3pp mean error at every rate, almost all from one page:
`testutil_pareto()` clamps its ~2.7% out-of-range draws to record 0 (per the comment in
`test/utility/misc.c`), that record's page hashes into **partition 2** at 1-in-4, and
production ships partition 0. The page's absence shifts `total_requests` but not the miss
curve, so with `raw_accesses` as the denominator the error falls to that of the trace with the
hot record removed:

    out_of_cache, partition 0     max err    mean err    at 16 GB
      1-in-2                       2.610pp     0.097pp    +0.061pp
      1-in-4  (shipped)            2.627pp     0.093pp    -0.061pp
      1-in-8                       2.577pp     0.128pp    +0.090pp
      1-in-16                      2.549pp     0.147pp    +0.082pp

    same trace, hot record removed (samp_pareto_nohot)
      1-in-2                       0.931pp     0.025pp    +0.030pp
      1-in-4                       0.642pp     0.078pp    -0.050pp
      1-in-8                       0.867pp     0.094pp    -0.023pp

    divided by total_requests instead (out_of_cache, partition 0)
      1-in-4                       2.739pp     2.342pp    +0.985pp

The ~2.6pp max is at caches below ~5 MB, which cannot hold the hot page between its
accesses; there its accesses are misses and do not cancel. Above ~5 MB the error is within
0.1pp, except for up to 0.8pp of step noise near 16 GB.

**Page-level skew is far flatter than the record-level distribution suggests.** `scramble=true`
plus ~29 records per 32 KiB leaf page averages the Pareto weights away: the top 20% of pages
draw only ~41% of accesses, not 80%. The single hottest page is 2.74% -- the record-0 bucket.

**Internal pages are in the trace.** `IAF_ID_IGNORE` is only applied on the salvage, overflow,
verify and block-cache paths, not on descent, and a probe run measured internal:leaf page
requests at exactly **2:1**. The root page alone is therefore ~1/3 of everything IAF sees --
a far larger single-address concentration than the synthetic hot record. It is entirely in or
out of the sample in the same way, and cancels from the miss curve at any cache that holds it
between accesses. Not yet measured end to end.

**On Zipf, the rate matters only below ~1 MiB.** Peak error grows with the rate (2.3pp at
1-in-2, 7.5pp at 1-in-4, 16.4pp at 1-in-8) and sits at a few sampled blocks of residency.
Above ~1 MiB every rate is within 0.2-0.9pp, and above 1 GiB the RMS error is 0.29pp,
0.29pp and 0.22pp. Divided by `total_requests`, the rates stayed separated out to the
largest caches.

## Caveats

- Synthetic page-address traces, not a WiredTiger run. They model the descent as one leaf
  access per operation and ignore internal pages entirely -- which, given the 2:1 finding
  above, is the biggest thing they are missing.
- Uniform 32 KiB leaf pages, ~29 records each. Real fill varies.
- `plot_collapse.py` and `plot_partitions.py` are reconstructions of scripts that were
  originally run as inline heredocs and lost. The conclusions reproduce; exact peak
  positions shift a little with the smoothing window.
