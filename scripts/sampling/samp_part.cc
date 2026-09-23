// Zipfian trace -- closer to the pareto/YCSB distribution the perf harness uses.
#include "bounded_iaf.h"
#include <iostream>
#include <random>
#include <cmath>
#include <vector>
#include <cstdlib>
int main(int argc, char** argv){
  size_t slog = atoi(argv[1]), cap = atoll(argv[2]), n = atoll(argv[3]);
  const size_t N = 1000000; const double theta = 0.99;
  // Precompute a zipf CDF over N keys once; identical for every sampling rate.
  std::vector<double> cdf(N); double sum = 0;
  for (size_t i=0;i<N;i++){ sum += 1.0/std::pow(i+1, theta); cdf[i]=sum; }
  for (auto &c : cdf) c /= sum;
  BoundedIAF a(slog, 20240601, (size_t)atoll(argv[4]), 65536, cap);
  std::mt19937_64 rng(777);
  std::uniform_real_distribution<double> U(0,1);
  for (size_t i=0;i<n;i++){
    size_t k = std::lower_bound(cdf.begin(), cdf.end(), U(rng)) - cdf.begin();
    uint64_t addr = k + 4;
    size_t page_bytes = 4096;                       // uniform page size, like a WT leaf
    a.memory_access((req_count_t)addr, (req_count_t)((page_bytes+255)/256));
  }
  a.flush();
  a.print_small_csv_streaming(std::cout);
}
