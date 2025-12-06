# Performance Optimization Analysis

## Profiling Results Summary

**Total runtime**: 13.997 seconds for 100,000 lines
**Throughput**: ~7,143 lines/second

### Top Hotspots (by total time)

1. **`_update_new_sequence_records`** - 6.528s (46.6% of runtime)
   - Called: 96,799 times
   - Cumulative: 11.630s
   - **PRIMARY BOTTLENECK**

2. **`get_key` (PositionalFIFO)**- 1.871s (13.4%)
   - Called: 13,357,136 times
   - Simple dict lookup, but extremely high call frequency

3. **Set/Dict operations** - ~1.9s (13.6%)
   - `set.add`: 0.959s (13.2M calls)
   - `dict.get`: 0.949s (13.5M calls)

4. **`get_next_position`** - 0.712s (5.1%)
   - Called: 13,357,136 times
   - Just returns `position + 1`, but called millions of times

5. **`_emit_merged_lines`** - 0.700s (5.0%)
   - Called: 96,799 times
   - Buffer management overhead

## Root Cause Analysis

### The `_update_new_sequence_records` Problem

This function accounts for nearly **half** the runtime. Analysis shows:

```python
def _update_new_sequence_records(self, current_window_hash: str) -> None:
    for _candidate_id, candidate in self.new_sequence_records.items():
        still_matching = set()

        for hist_pos in candidate.matching_history_positions:
            # HOTSPOT: Called millions of times
            next_hist_pos = self.window_hash_history.get_next_position(hist_pos)
            next_window_hash = self.window_hash_history.get_key(next_hist_pos)

            if next_window_hash is None:
                continue
            if next_window_hash == current_window_hash:
                still_matching.add(next_hist_pos)

        # Update candidate state
        if still_matching:
            candidate.matching_history_positions = still_matching
            candidate.length += 1
            candidate.buffer_depth += 1
            candidate.window_hashes.append(current_window_hash)
```

**The nested loop structure**:
- Outer loop: iterate over all candidates (~137 candidates per call on average)
- Inner loop: iterate over matching history positions (~97 positions per candidate)
- Each inner iteration: 2 function calls (`get_next_position`, `get_key`)

**Call count calculation**:
- 96,799 calls to `_update_new_sequence_records`
- ~137 candidates per call × ~97 positions per candidate
- = ~13.3M inner loop iterations
- = ~26.6M function calls (get_next_position + get_key)

## Optimization Opportunities

### 1. Inline Simple Functions (Quick Win)

**Target**: `get_next_position`
- Current: Function call overhead for `return position + 1`
- Optimization: Inline directly as `hist_pos + 1`
- **Expected speedup**: ~0.7s saved (5%)

### 2. Optimize PositionalFIFO Data Access

**Target**: `get_key` method
- Current: 13.3M dict lookups via method call
- Optimization Options:
  a. Direct dict access: `self.window_hash_history.position_to_entry[pos].window_hash`
  b. Batch lookup: Pre-fetch keys for all positions in a candidate
  c. Cache recent lookups (LRU cache for last N positions)
- **Expected speedup**: ~1.5s saved (10-11%)

### 3. Restructure Candidate Update Logic

**Target**: Nested loop in `_update_new_sequence_records`
- Current: O(candidates × positions) with high constant factor
- Optimization Options:
  a. Early termination: Skip candidates with no matching positions
  b. Limit candidate tracking: Cap maximum candidates per iteration
  c. Use list comprehension instead of set building
  d. Process candidates in batches

**Example optimization**:
```python
def _update_new_sequence_records(self, current_window_hash: str) -> None:
    position_to_entry = self.window_hash_history.position_to_entry  # Direct access

    for candidate in self.new_sequence_records.values():
        if not candidate.matching_history_positions:
            continue  # Early skip

        # List comprehension instead of loop + set.add
        still_matching = {
            hist_pos + 1  # Inlined get_next_position
            for hist_pos in candidate.matching_history_positions
            if (entry := position_to_entry.get(hist_pos + 1)) is not None
            and entry.window_hash == current_window_hash
        }

        if still_matching:
            candidate.matching_history_positions = still_matching
            candidate.length += 1
            candidate.buffer_depth += 1
            candidate.window_hashes.append(current_window_hash)
```

- **Expected speedup**: ~3-4s saved (21-29%)

### 4. Use __slots__ for NewSequenceCandidate

**Target**: Memory layout of NewSequenceCandidate
- Current: No __slots__, dynamic dict overhead
- Challenge: Has list fields (window_hashes)
- Solution: Restructure to use __slots__ with list field
- **Expected speedup**: ~5-10% (memory locality improvements)

### 5. Optimize Buffer Operations

**Target**: `_emit_merged_lines`
- Current: Multiple deque operations, repeated `len()` calls
- Optimization: Cache buffer lengths, reduce repeated calculations
- **Expected speedup**: ~0.2-0.3s saved (1.5-2%)

## Implementation Priority

### Phase 1: Low-Hanging Fruit (Easy wins, minimal risk)
1. ✅ Inline `get_next_position`
2. ✅ Use direct dict access in hot loops
3. ✅ List comprehension optimization in `_update_new_sequence_records`

**Estimated combined speedup**: 30-40% (4-6 seconds saved)

### Phase 2: Algorithmic Improvements (Medium complexity)
1. Limit maximum candidates tracked simultaneously
2. Early termination optimizations
3. Batch processing

**Estimated additional speedup**: 10-15% (1-2 seconds)

### Phase 3: Advanced Optimizations (Consider if needed)
1. Cython/C extension for PositionalFIFO
2. Custom hash implementation
3. Memory-mapped data structures

**Estimated additional speedup**: 20-30% with Cython

## Benchmarking Plan

1. **Baseline**: Current implementation (13.997s for 100k lines)
2. **After Phase 1**: Target ~8-10s (30-40% improvement)
3. **After Phase 2**: Target ~7-8s (40-50% improvement)
4. **Stretch goal**: ~5-6s (57-65% improvement with Cython)

## Next Steps

1. Implement Phase 1 optimizations
2. Run profiling again to verify improvements
3. Run full test suite to ensure correctness
4. Benchmark with various workloads (different pattern densities)
5. Document optimizations in IMPLEMENTATION.md
