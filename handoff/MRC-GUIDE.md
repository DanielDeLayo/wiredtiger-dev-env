# Reading and plotting the IAF miss-ratio curve

Notes for an agent working with output from a WiredTiger build with `HAVE_ANALYZE_CACHE`.
Everything here is about *interpreting* the data; see `README.md` for how to merge the code.

## Where the data comes from

The build writes the curve to the WiredTiger verbose log (`WT_VERB_EVICTION`, INFO level) once
per processed chunk, and once more at connection close. Each dump is a summary line followed
by a CSV:

    IAF-SUMMARY cache_bytes=1073741824,cache_blocks=4194304,curve_max_blocks=16777216,
    curve_covers_cache=true,bytes_inuse=745567396,pages_requested=79344883,pages_read=25065,
    hit_rate_pct=99.9684,stats_enabled=true
    77173968,2705176,79344883
    Cache Size,Hits
    1,6371
    2,6371
    ...

Line 1 of the CSV is metadata, **not** column headers:

| field | meaning |
|---|---|
| `total_requests` | sampled access count, multiplied by the sampling rate. Used only to form the miss curve; **never** the denominator |
| `max_cache_size` | largest cache size present in this curve, in blocks |
| `raw_accesses` | exact access count, including unsampled accesses and duplicates. The denominator of the miss-ratio curve |

Then `Cache Size,Hits` and the rows. `pandas.read_csv(path, skiprows=1)` is the right call.

## The 256-byte quantization -- read this before plotting

**The `Cache Size` column is in 256-byte blocks, not bytes and not pages.**

`IAF_BLOCK_SIZE` is 256. Every access is rounded *up* to a whole number of blocks:
`nblocks = ceil(page_memory_footprint / 256)`. So a 4 KiB page occupies 16 units on the axis,
and a cache of N units holds N*256 bytes.

To plot in bytes:

    cache_bytes = cache_size_column * 256

Consequences worth knowing:

- Axis resolution is 256 B. You cannot distinguish cache sizes finer than that.
- Rounding is always up, so total footprint is very slightly overstated -- at most 255 B per
  distinct page. Negligible at realistic page sizes; do not "correct" for it.
- The unit is *memory footprint*, not on-disk page size. An in-memory page with updates
  attached is larger than its disk image, and is counted at the larger size.
- Do not confuse this with a page count. Dividing by 4096 to "get pages" is wrong unless every
  page really is 4 KiB.

## Computing the curve

    miss_curve = total_requests - hits          # misses at each cache size
    mrc        = miss_curve / raw_accesses      # miss-ratio curve

`hits` is the `Hits` column; `total_requests` and `raw_accesses` are from the metadata line.
The miss curve is non-increasing in cache size.

Do **not** compute `1 - hits / total_requests`. It agrees with the above only when sampling is
off (`total_requests == raw_accesses`); see "Sampling".

**Rows are sparse.** A row is emitted only when the cache size has grown 5% or `Hits` has
grown 1% (minimum one) since the last row, so spacing is geometric, not
uniform, and most cache sizes are absent. Treat it as a step function: to read a value at an
arbitrary size, take the last row at or below it (`previous`-style interpolation). Do not
assume row index relates to cache size, and do not linearly interpolate across a wide gap and
present it as measured.

## Sampling

Sampling is on by default at 1 in 4 (`WT_IAF_SAMPLING_LOG2 = 2`). The CSV is already
rescaled: `Cache Size` is in real blocks, and `total_requests` and `Hits` are sampled counts
multiplied by 4. Do not rescale again; multiplying by 4 a second time is the likeliest mistake.

Sampling selects whole addresses. A page that draws a large share of accesses -- a heavy
hitter, such as the root -- is entirely in the sample or entirely out, and with few such pages
this does not average out. `total_requests` shifts by the page's scaled access count, and can
differ from `raw_accesses` by far more than a few percent.

**The miss curve is invariant to this.** Once the cache holds the heavy hitter between its
accesses, it misses only on its first access, so it adds the same amount to `total_requests`
and to `Hits` and cancels from `total_requests - hits`.

**The miss-ratio curve must divide by the expected access count, not the sampled one.**
`raw_accesses` counts every access, sampled or not, so it is exactly the expected value of
`total_requests`:

    mrc = (total_requests - hits) / raw_accesses

Dividing by `total_requests` puts the heavy hitter's sampling error into every point of the
curve.

## Multiple dumps in one run

Each dump is **cumulative over the whole run so far**, not a delta. For a final MRC, use the
last dump. The sequence of dumps is useful for checking whether the curve has converged --
if the last few differ materially, the run was too short.

## Validating against WiredTiger's own numbers

The summary line exists so the prediction and the observation can be compared without
correlating separate log lines:

- `cache_blocks` is the configured cache in the same units as the x-axis. That is the point at
  which to read the curve.
- `hit_rate_pct` is WiredTiger's actually-measured hit rate, from its own counters.
- `curve_covers_cache=false` means the curve does not reach `cache_blocks`. **The two numbers
  are then not comparable at all** -- say so rather than reading off the last row.
- `stats_enabled=false` means the connection was opened without `statistics=(fast)`, so
  `hit_rate_pct`, `pages_requested` and `pages_read` are all zero and must be ignored.

**Expect the curve to predict a lower miss ratio than WiredTiger achieves.** In a local
wtperf run the curve predicted 0.150 where WiredTiger measured 0.276. That gap is expected,
not an error: IAF models optimal LRU over page accesses, while the real cache also holds
internal pages, update structures and per-page overhead, and does not use pure LRU. Treat a
gap of roughly 10-15 points as normal. A gap in the *other* direction (observed miss ratio
below the prediction) is suspicious and worth investigating.

## A script that does all of this

`plot_mrc.py`, next to this file, is self-contained (stdlib + matplotlib, no pandas). Point it
at a WiredTiger log:

    python3 plot_mrc.py wiredtiger.log mrc.png          # last dump only
    python3 plot_mrc.py wiredtiger.log mrc.png --all    # overlay every dump

It converts blocks to bytes, computes the miss-ratio curve as above, draws the sparse rows as
a step function, and adds two reference marks so the prediction and the observation can be
read off one figure:
a vertical line at `cache_bytes` and a horizontal line at the miss ratio implied by
`hit_rate_pct`. It also warns when `curve_covers_cache=false`.

The connection must be opened with `verbose=[eviction:0]` (or higher) or no dumps are emitted
and the script will tell you so.
