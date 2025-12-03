# Performance Optimization

This directory contains performance analysis, optimization scripts, and benchmark results for uniqseq.

## Files

### Documentation

- **`OPTIMIZATION_ANALYSIS.md`** - Initial profiling analysis and Phase 1 strategy
  - Identifies CPU hotspots
  - Explains root causes of performance bottlenecks
  - Provides optimization roadmap (Phase 1, 2, 3)

- **`PERFORMANCE_RESULTS.md`** - Phase 1 comprehensive benchmark results
  - Before/after comparison
  - Multiple workload patterns tested
  - Reproduction instructions
  - Real-world vs profiled performance

- **`PHASE2_RESULTS.md`** - Phase 2 detailed analysis and results
  - Candidate limiting strategy
  - Performance improvements (2.76x speedup)
  - Trade-off analysis
  - Combined Phase 1+2 results

### Scripts

- **`profile_uniqseq.py`** - Profiling script using cProfile
  - Identifies function-level hotspots
  - Measures function call counts
  - Adds ~55% overhead (useful for optimization targeting, not real-world perf)
  - Usage: `python optimization/profile_uniqseq.py`

- **`benchmark_uniqseq.py`** - Comprehensive benchmark suite
  - Tests multiple workload patterns (heavy dup, short patterns, mixed, unique)
  - Tests different scales (10k, 50k, 100k lines)
  - Tests different window sizes (5, 10, 15, 20)
  - No profiling overhead (measures real-world performance)
  - Usage: `python optimization/benchmark_uniqseq.py`

- **`analyze_candidates.py`** - Candidate tracking analysis
  - Tracks candidate counts and behavior
  - Identifies optimization opportunities
  - Provides recommendations
  - Usage: `python optimization/analyze_candidates.py`

## Quick Start

### Run Performance Benchmark

```bash
# Comprehensive benchmark (recommended)
python optimization/benchmark_uniqseq.py

# Profile to identify hotspots (for further optimization)
python optimization/profile_uniqseq.py
```

### Current Performance (Phase 2)

**Real-world throughput** (100k lines):
- Heavy duplication (80% redundancy): **89,195 lines/sec** (2.76x over Phase 1)
- Typical workload (64% redundancy): **122,099 lines/sec** (1.31x over Phase 1)
- No duplicates (best case): **278,651 lines/sec** (similar to Phase 1)

**Optimization achievements**:
- **Phase 1**: 2.02x speedup under profiling
- **Phase 2**: 5.34x speedup under profiling (2.55x additional)
- **Combined**: 12.7x faster in real-world usage (vs original)
- 60% reduction in function calls (Phase 2)
- 84% reduction in candidate tracking overhead
- Zero additional memory usage
- 100% test compatibility maintained

## Optimization History

### Phase 1 (Completed)

**Target**: 30-40% improvement
**Achieved**: 102% improvement (2.02x speedup)

**Changes**:
1. Inlined simple functions (`get_next_position`)
2. Direct data structure access (bypass method calls)
3. Set comprehensions (replace nested loops)
4. Cached frequently accessed values

**Impact**:
- Eliminated ~26.6M function calls per 100k lines
- Primary hotspot (`_update_new_sequence_candidates`) reduced from 6.5s to 3.9s

### Phase 2 (Completed)

**Target**: 10-15% additional improvement
**Achieved**: 176% improvement (2.76x speedup)
**Exceeded target by**: 1600%!

**Implemented optimizations**:
- ✅ Limit concurrent candidates to 30 (MAX_CANDIDATES)
- ✅ Prioritize candidates by earliest start (longest match)
- ✅ Evict worst candidates when at limit

**Impact**:
- Candidate tracking: 75.77 → 21.88 avg (71% reduction)
- Position checks: 13.4M → 2.1M (84% reduction)
- Primary hotspot: 3.765s → 0.869s (4.3x faster)
- Real-world throughput: 32,357 → 89,195 lines/sec (2.76x)

**See [PHASE2_RESULTS.md](./PHASE2_RESULTS.md) for detailed analysis.**

### Phase 3 (Future)

**Estimated gain**: 2-3x additional improvement

**Planned optimizations**:
- Cython/C extensions for PositionalFIFO
- Native hash implementations
- Core loop compilation

**Total potential**: 6-8x over current optimized version

## Related Documentation

- Main algorithm: [`dev-docs/design/ALGORITHM_DESIGN.md`](../dev-docs/design/ALGORITHM_DESIGN.md)
- Implementation: [`dev-docs/design/IMPLEMENTATION.md`](../dev-docs/design/IMPLEMENTATION.md)
- Testing: [`dev-docs/testing/TESTING_STRATEGY.md`](../dev-docs/testing/TESTING_STRATEGY.md)
