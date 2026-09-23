"""Shared loading for the IAF sampling-accuracy experiments.

Every experiment writes curves as `<dir>/s<rate>_p<partition>.csv` (or `s<rate>.csv`
where only partition 0 was run), in the format print_small_csv_streaming emits:

    <total_requests>,<curve_blocks>,<raw_accesses>
    Cache Size,Hits
    1,3829
    ...

Rows are sparse -- emitted only where the curve moves -- so the curve is a step
function and must be sampled with searchsorted, never interpolated.

With sampling, <total_requests> and Hits are sampled counts multiplied by the rate, and
<raw_accesses> is the exact access count. The miss curve, total_requests - Hits, is invariant
to which addresses were sampled; total_requests alone is not, because a heavy hitter is
entirely in or out of the sample. The miss-ratio curve is therefore
(total_requests - Hits) / raw_accesses.
"""
import os

import numpy as np

BLOCK = 256  # IAF quantizes the cache-size axis to 256-byte blocks.


def load(path):
    """Returns (sizes, hits, total_requests, raw_accesses)."""
    with open(path) as f:
        header = f.readline().split(",")
        total = float(header[0])
        raw = float(header[2]) if len(header) > 2 else total
        f.readline()  # "Cache Size,Hits"
        rows = [l.split(",") for l in f if l.strip()]
    sz = np.array([float(r[0]) for r in rows])
    hits = np.array([float(r[1]) for r in rows])
    return sz, hits, total, raw


def load_dir(d, rate, part=None):
    names = ["s%d_p%d.csv" % (rate, part or 0), "s%d.csv" % rate]
    if rate == 0:
        names.append("exact.csv")   # some runs name the unsampled reference this way
    for name in names:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return load(p)
    raise FileNotFoundError("no curve for rate %d part %s in %s" % (rate, part, d))


def miss_at(sz, hits, total, raw, grid):
    """Miss-ratio curve at each grid point, from the last row at or below it."""
    idx = np.searchsorted(sz, grid, side="right") - 1
    out = np.where(idx >= 0, hits[np.clip(idx, 0, len(hits) - 1)], 0.0)
    return (total - out) / raw


def common_grid(curves, n=3000):
    top = min(c[0][-1] for c in curves)
    return np.unique(np.round(np.logspace(0, np.log10(top), n)).astype(np.int64))
