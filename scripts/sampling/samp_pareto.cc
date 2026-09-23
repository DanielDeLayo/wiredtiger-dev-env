// Page-address trace for the harness's actual YCSB-HVW configs:
//   pareto=20, scramble=true, key_sz=100, value_sz=1024, type=file (32KiB leaf pages).
// Reproduces wtperf_rand() exactly: uniform u32 -> testutil_pareto(.,range,20) -> fnvhash64 % range,
// then maps the record number to the leaf page that holds it.
#include "bounded_iaf.h"
#include <iostream>
#include <random>
#include <cmath>
#include <cstdlib>
#include <cstdint>

#define PARETO_SHAPE 1.5

static inline uint64_t pareto(uint64_t rand, uint64_t range, unsigned skew) {
  double S1 = (-1 / PARETO_SHAPE);
  double S2 = (double)range * (skew / 100.0) * (PARETO_SHAPE - 1);
  double U = 1 - (double)rand / (double)UINT32_MAX;
  uint64_t r = (uint64_t)((pow(U, S1) - 1) * S2);
  if (r > range) r = 0;   // ~2.7% of draws; makes record 0 hot, exactly as in wtperf
  return r;
}

static inline uint64_t fnvhash64(uint64_t val) {
  uint64_t h = UINT64_C(0xcbf29ce484222325);
  const uint8_t *d = (const uint8_t *)&val;
  for (size_t i = 0; i < sizeof(val); i++) { h ^= d[i]; h *= UINT64_C(0x00000100000001b3); }
  return h;
}

int main(int argc, char** argv) {
  size_t slog  = atoi(argv[1]);         // sample 1 in 2^slog
  size_t part  = atoll(argv[2]);        // sample partition
  uint64_t recs = atoll(argv[3]);       // icount
  uint64_t rpp  = atoll(argv[4]);       // records per leaf page
  uint64_t n    = atoll(argv[5]);       // accesses
  size_t cap    = atoll(argv[6]);       // max cache size, in pages

  BoundedIAF a(slog, 20240601, part, 65536, cap);
  std::mt19937_64 rng(777);
  std::uniform_int_distribution<uint32_t> U32(0, UINT32_MAX);

  for (uint64_t i = 0; i < n; i++) {
    uint64_t rval = pareto(U32(rng), recs, 20);
    rval = fnvhash64(rval) % recs;      // scramble=true
    a.memory_access((req_count_t)(rval / rpp + 1), 1);
  }
  a.flush();
  a.print_small_csv_streaming(std::cout);
}
