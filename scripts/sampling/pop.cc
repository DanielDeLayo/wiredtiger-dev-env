#include <cstdio>
#include <cstdint>
#include <cmath>
#include <random>
#include <vector>
#include <algorithm>
#define PARETO_SHAPE 1.5
static inline uint64_t pareto(uint64_t rand, uint64_t range, unsigned skew){
  double S1=(-1/PARETO_SHAPE), S2=(double)range*(skew/100.0)*(PARETO_SHAPE-1);
  double U=1-(double)rand/(double)UINT32_MAX;
  uint64_t r=(uint64_t)((pow(U,S1)-1)*S2); if(r>range) r=0; return r;
}
static inline uint64_t fnv(uint64_t v){uint64_t h=0xcbf29ce484222325ull;const uint8_t*d=(const uint8_t*)&v;
  for(size_t i=0;i<8;i++){h^=d[i];h*=0x100000001b3ull;} return h;}
int main(int argc,char**argv){
  uint64_t recs=atoll(argv[1]), rpp=atoll(argv[2]), n=atoll(argv[3]);
  uint64_t npages=(recs+rpp-1)/rpp;
  std::vector<uint32_t> rec_cnt, pg_cnt(npages,0);
  std::mt19937_64 rng(777); std::uniform_int_distribution<uint32_t> U32(0,UINT32_MAX);
  rec_cnt.assign(0,0);
  for(uint64_t i=0;i<n;i++){
    uint64_t r=fnv(pareto(U32(rng),recs,20))%recs;
    pg_cnt[r/rpp]++;
  }
  std::vector<uint32_t> s=pg_cnt; std::sort(s.rbegin(),s.rend());
  uint64_t tot=0; for(auto c:s) tot+=c;
  auto frac=[&](double p){ uint64_t k=(uint64_t)(npages*p); uint64_t a=0; for(uint64_t i=0;i<k;i++)a+=s[i]; return 100.0*a/tot; };
  printf("pages=%llu  accesses=%llu  touched=%llu\n",(unsigned long long)npages,(unsigned long long)n,
         (unsigned long long)std::count_if(pg_cnt.begin(),pg_cnt.end(),[](uint32_t c){return c>0;}));
  printf("  top  0.1%% of pages -> %6.2f%% of accesses\n",frac(0.001));
  printf("  top    1%% of pages -> %6.2f%% of accesses\n",frac(0.01));
  printf("  top    5%% of pages -> %6.2f%% of accesses\n",frac(0.05));
  printf("  top   10%% of pages -> %6.2f%% of accesses\n",frac(0.10));
  printf("  top   20%% of pages -> %6.2f%% of accesses\n",frac(0.20));
  printf("  top   50%% of pages -> %6.2f%% of accesses\n",frac(0.50));
  printf("  hottest page = %.4f%% of accesses\n", 100.0*s[0]/tot);
}
