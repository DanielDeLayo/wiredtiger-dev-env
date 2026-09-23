# IAF cache-analysis update

Two patches, one per upstream repo. Both verified to apply cleanly with `git apply --check`
against the revisions below. Also here:

- `MRC-GUIDE.md` -- how to read and plot the curve, including the 256-byte quantization.
  Written for an agent working on your side.
- `plot_mrc.py` -- self-contained plotter: point it at a WiredTiger log and it pulls out
  every `IAF-SUMMARY` dump. Stdlib + matplotlib only.

## 1. Increment-and-Freeze

Vendored via `src/third_party/increment_and_freeze/scripts/import.sh`, which pins:

    REVISION="f535b31e1bf39328b4388d41f4a2cbb578ebd8b6"   # old

Bump it and re-run the script:

    REVISION="3e23d8682ae98efe646dfb8b7764aeaa037104ea"   # new

No `SRCS`/`HDRS` changes are needed -- every modified file is already in those lists and no
files were added, so a straight re-import picks everything up. `iaf-update.patch` is included
if you would rather apply the delta directly (base: `f535b31`).

Your hand-written `BUILD.bazel` for the vendored copy is unaffected. Upstream's own
`BUILD.bazel` also changed in this range (correct `@rules_cc//cc:cc_library.bzl` load, and
`//conditions:default` added to selects that previously only resolved on macOS), but you do
not consume it.

## 2. WiredTiger

**This is now rebased onto current upstream WiredTiger.** The integration branch was 575
commits behind; it has been merged with `wiredtiger/wiredtiger` develop at
`9ddb133839` ("WT-18649 Reland the Palite victim cache"), giving merge commit
`8284b35af8`.

Apply `wiredtiger-iaf.patch`. Unlike the previous handoff this is not a delta against an
older port -- it is **the entire integration as one patch against upstream develop
`9ddb133839`**, verified with `git apply --check` on a pristine worktree of that revision.
35 files, +417/-12. If your tree is at a different upstream revision, `git apply --3way`
should still land it; only two files have ever conflicted (see below).

**One file is new: `src/include/analyze_cache_inline.h`.** It is included from
`wt_internal.h`, so a `glob(["**/*.h"])` will pick it up once present, but `dist/s_all` may
want it registered. This is the file most likely to be dropped in a port -- please check it
landed.

### What the upstream merge changed

Three things conflicted or went stale against current develop, and four real defects in the
original port turned up while doing it:

- `ext/storage_sources/dir_store/` **was deleted upstream.** Its `IAF::IAF` link line went
  with it. Nothing under the new `ext/page_log/` needs the link -- a full
  `HAVE_ANALYZE_CACHE=1` build links clean without it.
- `bench/workgen/CMakeLists.txt` and `src/block_cache/block_map.c` conflicted textually with
  upstream edits. Both resolved keeping both sides.
- `src/reconcile/rec_write.c` guarded its `iaf_api.h` include on **`HAVE_ANANLYZE_CACHE`** --
  misspelled, so the include never fired and the header only reached that file indirectly
  through `wt_internal.h`. Fixed.
- **The object-ID overrides were not guarded.** The port repurposes the address cookie's
  object-ID slot to carry the persistent page ID, and forces `objectid = 0` after unpacking
  a cookie. Those assignments, the disabled `block->objectid == objectid` assertions, and the
  hardcoded root object ID in `block_ckpt.c` were all unconditional, so a **stock build with
  `HAVE_ANALYZE_CACHE` off silently lost its tiered-storage object IDs** and the assertions
  that check them. All of it is now behind `#ifdef HAVE_ANALYZE_CACHE` in `block_addr.c`,
  `block_ckpt.c`, `block_ext.c`, `block_read.c`, `block_slvg.c`, `block_vrfy.c` and
  `block_map.c`. Non-analysis builds are now behaviourally identical to upstream. This is
  worth reviewing -- if you had been running the port with the flag off anywhere, it was not
  a no-op.
- `block_io.c` asserted `block_meta != NULL` unconditionally with a plain `assert()`. Stock
  callers may legitimately pass NULL (see the WT-14717 FIXME). Guarded, and switched to
  `WT_ASSERT`.
- `CMakeLists.txt` hardcoded an absolute path to the Increment-and-Freeze checkout. It is now
  an `IAF_SOURCE_DIR` cache variable defaulting to a sibling of the WiredTiger source tree,
  with a clear `FATAL_ERROR` when the path does not exist.

Verified: `HAVE_ANALYZE_CACHE=1` and stock builds both compile clean on `9ddb133839`; wtperf
at `pareto=20` emits `IAF-SUMMARY` dumps whose curve covers the configured cache.

## What changed, and why you should care

- **The curve is no longer truncated.** It used to be capped at a fixed 1,000,000 blocks =
  256 MiB, regardless of cache size. Against a 16 GB cache that meant the curve stopped at
  1/64 of the operating point, so the earlier YCSB curves did not reach the size you were
  actually running at. The bound is now derived from `cache_size` with 4x headroom, applied
  from `__wt_cache_create()` and again on reconfigure.

- **Overhead is much lower.** On wtperf, cache-resident, 8 threads, the instrumentation cost
  went from ~75% of throughput to ~7.5%. The cost was never the IAF algorithm -- it was the
  rate of acquisition on a single global mutex on every page-in. Two changes fixed it:
  1-in-4 sampling, and testing `should_sample()` before taking the lock so the ~3 in 4
  rejected accesses never touch it. Please re-measure on your harness; your workload
  amortises the per-page-in cost over much more work than wtperf does, so your numbers
  (30% in_cache / 10-15% out_of_cache) should improve by less in relative terms.

- **Sampling is on: 1 in 4** (`WT_IAF_SAMPLING_LOG2` in `analyze_cache_inline.h`). The
  cache-size axis is scaled back up when the curve is emitted, so reported sizes are still
  real blocks. Memory for the curve drops 4x. Sampling selects whole addresses, so a
  heavy-hitter page (the root, a hot record) is entirely in or out of the sample, and
  `total_requests` shifts by its scaled access count. The miss curve, `total_requests - Hits`,
  is invariant to this. The miss-ratio curve divides it by `raw_accesses`, the exact access
  count, never by `total_requests`. Details in `MRC-GUIDE.md`; `plot_mrc.py` does this.

- **Each dump is now prefixed with a summary line** so the prediction and the observation can
  be checked against each other without correlating separate log lines:

      IAF-SUMMARY cache_bytes=...,cache_blocks=...,curve_max_blocks=...,curve_covers_cache=...,
      bytes_inuse=...,pages_requested=...,pages_read=...,hit_rate_pct=...,stats_enabled=...
      <the existing CSV, unchanged>

  `curve_covers_cache=false` means the curve does not reach the configured cache size and the
  two numbers cannot be compared. `hit_rate_pct` is WiredTiger's own, and reads zero unless
  the connection was opened with `statistics=(fast)`.

  Printing still happens once per processed chunk, as before -- nothing about the cadence
  changed, so your harness should still parse it.

## Caveats

- Measurements above are wtperf on macOS/arm64, single machine. Not YCSB on mongod.
- The concurrency change was validated by stress testing and curve-equivalence A/B only.
  ThreadSanitizer is broken on the machine this was developed on (a TSAN hello-world
  segfaults), so it has **not** been sanitizer-verified. Worth a TSAN run on Linux.
