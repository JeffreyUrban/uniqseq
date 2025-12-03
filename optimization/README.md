# Performance Optimization

This directory contains performance analysis, optimization scripts, and benchmark results for uniqseq.

## Files

### Documentation

- **`OPTIMIZATION_ANALYSIS.md`** - Detailed analysis of profiling results and optimization strategy
  - Identifies CPU hotspots
  - Explains root causes of performance bottlenecks
  - Provides optimization roadmap (Phase 1, 2, 3)

- **`PERFORMANCE_RESULTS.md`** - Comprehensive benchmark results and performance metrics
  - Before/after comparison
  - Multiple workload patterns tested
  - Reproduction instructions
  - Real-world vs profiled performance

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

## Quick Start

### Run Performance Benchmark

```bash
# Comprehensive benchmark (recommended)
python optimization/benchmark_uniqseq.py

# Profile to identify hotspots (for further optimization)
python optimization/profile_uniqseq.py
```

### Current Performance

**Real-world throughput** (100k lines):
- Heavy duplication (80% redundancy): **32,357 lines/sec**
- Typical workload (64% redundancy): **93,470 lines/sec**
- No duplicates (best case): **287,494 lines/sec**

**Optimization achievements**:
- 2.02x speedup under profiling
- 4-13x speedup in real-world usage
- 66% reduction in function calls
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

### Phase 2 (Future)

**Estimated gain**: 10-15% additional improvement

**Planned optimizations**:
- Limit concurrent candidates
- Early termination optimizations
- Batch processing

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
