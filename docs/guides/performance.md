# Performance Guide

Understand uniqseq's performance characteristics and optimize for your use case.

## Quick Performance Facts

| Characteristic | Value | Notes |
|---------------|-------|-------|
| **Throughput** | ~1-2 million lines/sec | On modern hardware |
| **Memory (default)** | ~3-10 MB | With max-history=100,000 |
| **Memory (unlimited)** | ~32 bytes × unique patterns | Grows with data diversity |
| **Disk I/O** | Single-pass streaming | Reads once, writes once |
| **Time complexity** | O(n) | Linear in input size |
| **Space complexity** | O(h + u×w) | h=history, u=unique seqs, w=window |

## Performance Characteristics

### Throughput

**Typical performance**: 1-2 million lines per second on modern hardware

**Factors affecting speed**:

1. **Window size**: Larger windows → more comparisons → slower
2. **Pattern diversity**: More unique patterns → more memory operations
3. **Hash transforms**: External process overhead for each line
4. **I/O**: Disk speed, network latency, pipe buffer size

**Benchmark example**:
```bash
# Generate test data: 1 million lines
seq 1 1000000 | awk '{print "Line " $1}' > test.log

# Measure throughput
time uniqseq test.log --window-size 3 > /dev/null
```

Expected output (modern laptop):
```text
real    0m0.5s  ← ~2 million lines/second
user    0m0.4s
sys     0m0.1s
```

### Memory Usage

uniqseq uses bounded memory regardless of input size:

```
Total memory = History + Sequences + Window Buffer

History:         ~32 bytes × max_history entries
Sequences:       ~(avg_line_length + 32) bytes × unique_sequences
Window Buffer:   ~avg_line_length × window_size
```

**Examples**:

```bash
# Default: ~3-10 MB typical
uniqseq large.log

# Limited history: ~1.6 MB
uniqseq --max-history 50000 large.log

# Unlimited: Grows with unique content
uniqseq --unlimited-history large.log
```

**Memory profiling**:
```bash
# Monitor memory usage
/usr/bin/time -v uniqseq large.log 2>&1 | grep "Maximum resident"
```

### CPU Usage

**Algorithm complexity**: O(n × w × c)
- n = number of lines
- w = window size
- c = candidates per position (typically 1-2)

**Amortized**: O(n) for most real-world inputs

**CPU-intensive operations**:
1. **Hashing**: BLAKE2b hashing of window contents (~80% of CPU time)
2. **String comparison**: Exact line matching for candidates
3. **Hash transform**: External subprocess if enabled

## Optimization Strategies

### 1. Choose the Right History Depth

**Problem**: Unlimited history uses more memory than needed

**Solution**: Use bounded history for streaming use cases

```bash
# Default (100k entries): Balanced performance
uniqseq app.log --max-history 100000

# Smaller history: Lower memory, may miss distant duplicates
uniqseq app.log --max-history 10000

# Unlimited: Best accuracy, higher memory
uniqseq app.log --unlimited-history
```

**When to use each**:

| Use Case | History Setting | Why |
|----------|----------------|-----|
| Real-time logs | `--max-history 10000` | Bounded memory |
| Batch processing | `--unlimited-history` | Catch all duplicates |
| Large files (GB+) | `--max-history 100000` | Balance accuracy/memory |
| Testing/demo | `--max-history 100` | Fast, predictable |

### 2. Optimize Window Size

**Problem**: Large window size → more comparisons → slower

**Solution**: Use the smallest window size that catches your patterns

```bash
# Too large: Wastes CPU comparing unnecessary lines
uniqseq --window-size 50 single-line-errors.log

# Right size: Minimal comparisons
uniqseq --window-size 1 single-line-errors.log
```

**Performance impact**:
```bash
# Benchmark different window sizes
for w in 1 5 10 20 50; do
    echo -n "Window $w: "
    time uniqseq --window-size $w large.log > /dev/null 2>&1
done
```

Example output:
```text
Window 1:  0.3s  ← Fastest for single-line patterns
Window 5:  0.5s
Window 10: 0.8s
Window 20: 1.2s
Window 50: 2.5s  ← Slowest, unnecessary for this data
```

**Rule of thumb**: Use smallest window that catches your patterns

### 3. Avoid Expensive Hash Transforms

**Problem**: `--hash-transform` spawns subprocess for every line

**Solution**: Use simpler alternatives when possible

```bash
# SLOW: Complex pipeline per line
uniqseq --hash-transform "sed 's/[0-9]//g' | awk '{print \$3}'" app.log

# FASTER: Skip-chars for fixed-width prefixes
uniqseq --skip-chars 24 app.log

# FASTER: Simpler transform
uniqseq --hash-transform "cut -c 25-" app.log
```

**Performance comparison**:
```bash
# Test transform overhead
time uniqseq --hash-transform "cat" test.log > /dev/null    # Minimal transform
time uniqseq --hash-transform "sed 's/foo/bar/'" test.log > /dev/null  # Heavy
```

**Optimization hierarchy** (fastest to slowest):
1. No transform: `uniqseq app.log`
2. Skip-chars: `uniqseq --skip-chars 20 app.log`
3. Simple command: `uniqseq --hash-transform "cut -c 21-" app.log`
4. Pipeline: `uniqseq --hash-transform "sed ... | awk ..." app.log`

**When to preprocess instead**:
```bash
# If transform is expensive, do it once outside uniqseq
sed 's/complex-regex/replacement/g' huge.log | uniqseq --window-size 5
```

### 4. Pattern Filtering

**Problem**: Processing lines you don't need to deduplicate

**Solution**: Use `--track` to limit processing

```bash
# Process everything: Slow
uniqseq entire-log.log

# Only deduplicate ERROR lines: Faster
uniqseq --track '^ERROR' entire-log.log
```

**Impact**: Reduces hash computations and memory usage

```bash
# Benchmark filtering
time uniqseq large.log > /dev/null
time uniqseq --track '^ERROR' large.log > /dev/null
```

If ERROR lines are 10% of log → ~90% less work

### 5. Streaming vs Batch

**For batch processing**: Read from file (automatic unlimited history)

```bash
# Efficient: Single-pass, optimized I/O
uniqseq large-file.log > output.log
```

**For streaming**: Use stdin with bounded history

```bash
# Efficient: Bounded memory, real-time
tail -f app.log | uniqseq --max-history 10000
```

**For very large files**: Consider chunking if memory is constrained

```bash
# Process in chunks with shared library
uniqseq --library-dir /tmp/patterns part1.log > clean1.log
uniqseq --library-dir /tmp/patterns part2.log > clean2.log
uniqseq --library-dir /tmp/patterns part3.log > clean3.log
```

## Real-World Optimization Examples

### Scenario 1: 100 GB Log File

**Problem**: Need to deduplicate massive log file

**Approach**:
```bash
# Use limited history to bound memory
uniqseq --window-size 3 \
        --max-history 100000 \
        --skip-chars 24 \
        huge-100gb.log > clean.log
```

**Why**:
- `--window-size 3`: Small window → faster processing
- `--max-history 100000`: ~3 MB history, bounded memory
- `--skip-chars 24`: Faster than hash-transform for timestamps

**Expected performance**:
- Memory: ~10 MB total
- Time: ~50-100 minutes (1-2M lines/sec)
- Single-pass streaming

### Scenario 2: Real-Time Log Monitoring

**Problem**: Process live log stream with minimal latency

**Approach**:
```bash
# Optimize for low latency
tail -f /var/log/app.log | \
    uniqseq --window-size 1 \
            --max-history 5000 \
            --track '^ERROR' \
            --quiet
```

**Why**:
- `--window-size 1`: Instant output (no buffering)
- `--max-history 5000`: Minimal memory
- `--track '^ERROR'`: Only process ERROR lines
- `--quiet`: No statistics overhead

**Expected performance**:
- Latency: <1ms per line
- Memory: <1 MB
- CPU: Minimal

### Scenario 3: Build Log Deduplication

**Problem**: 500 MB build log with compiler warnings

**Approach**:
```bash
# Fast batch processing
uniqseq --window-size 3 \
        --unlimited-history \
        build.log > clean-build.log
```

**Why**:
- File input: Automatic unlimited history
- `--window-size 3`: Matches 3-line warning format
- No transforms: Maximum throughput

**Expected performance**:
- Time: 30-60 seconds
- Memory: ~50 MB (depends on unique warnings)

### Scenario 4: Complex Transform with Large File

**Problem**: Need to normalize data but file is 50 GB

**Approach 1** (faster): Preprocess separately
```bash
# Preprocess once, then deduplicate
sed 's/[0-9]{4}-[0-9]{2}-[0-9]{2}//g' huge.log | \
    tr -s ' ' | \
    uniqseq --window-size 5 > clean.log
```

**Approach 2** (slower but simpler): Use hash-transform
```bash
# Transform during deduplication
uniqseq --hash-transform "sed 's/[0-9]{4}-[0-9]{2}-[0-9]{2}//g' | tr -s ' '" \
        --window-size 5 \
        huge.log > clean.log
```

**Performance comparison**:
- Approach 1: ~2M lines/sec
- Approach 2: ~200K lines/sec (10× slower due to subprocess overhead)

## Performance Monitoring

### Track Statistics

Use `--stats-format json` to monitor performance metrics:

```bash
uniqseq large.log \
    --stats-format json 2>&1 | \
    jq '.statistics'
```

Output:
```json
{
  "lines": {
    "total": 1000000,
    "unique": 850000,
    "skipped": 150000
  },
  "redundancy_pct": 15.0,
  "unique_sequences_tracked": 5000,
  "sequences_discovered": 5000,
  "pattern_library": "none"
}
```

**Key metrics**:
- `redundancy_pct`: Higher → more deduplication → more memory/CPU
- `unique_sequences_tracked`: Memory usage indicator
- `lines.total / time`: Throughput

### Benchmark Your Data

**Create a baseline**:
```bash
#!/bin/bash
# benchmark.sh

FILE="$1"
WINDOW="$2"

echo "Benchmarking $FILE with window size $WINDOW"
echo "=========================================="

# Throughput test
echo "Throughput:"
time uniqseq --window-size "$WINDOW" "$FILE" > /dev/null

# Memory test
echo -e "\nMemory usage:"
/usr/bin/time -v uniqseq --window-size "$WINDOW" "$FILE" > /dev/null 2>&1 | \
    grep -E "(Maximum resident|wall clock)"

# Statistics
echo -e "\nStatistics:"
uniqseq --window-size "$WINDOW" "$FILE" \
    --stats-format json 2>&1 | \
    jq '.statistics | {redundancy_pct, unique_sequences_tracked}'
```

Usage:
```bash
chmod +x benchmark.sh
./benchmark.sh app.log 5
```

### Profile with Different Configurations

**Test multiple configurations**:
```bash
#!/bin/bash
# compare-configs.sh

FILE="$1"

echo "Configuration,Time(s),Memory(MB),Redundancy(%)"

# Config 1: Default
START=$(date +%s)
MEM=$(uniqseq "$FILE" > /dev/null 2>&1; /usr/bin/time -v uniqseq "$FILE" > /dev/null 2>&1 | grep "Maximum resident" | awk '{print $6/1024}')
END=$(date +%s)
TIME=$((END-START))
STATS=$(uniqseq "$FILE" --stats-format json 2>&1 | jq -r '.statistics.redundancy_pct')
echo "Default,$TIME,$MEM,$STATS"

# Config 2: Small window
# ... repeat for other configs
```

## Troubleshooting Performance Issues

### "Too slow for my data"

**Diagnosis**:
1. Check window size: Is it larger than needed?
2. Check for hash transforms: Are you using `--hash-transform`?
3. Check file size: How many lines?

**Solutions**:
- Reduce window size if possible
- Replace hash-transform with skip-chars
- Use pattern filtering (`--track`)
- Consider preprocessing

### "Using too much memory"

**Diagnosis**:
```bash
# Monitor memory during processing
/usr/bin/time -v uniqseq app.log > /dev/null 2>&1 | grep "Maximum resident"
```

**Solutions**:
- Use `--max-history 10000` instead of unlimited
- Reduce window size (less buffer memory)
- Use `--track` to limit what's deduplicated

**Memory usage breakdown**:
```python
# Estimate memory usage
history_entries = 100000      # --max-history value
unique_sequences = 5000       # From statistics
avg_line_length = 100         # Typical line length
window_size = 10              # --window-size value

history_mb = (history_entries * 32) / 1024 / 1024
sequences_mb = (unique_sequences * (avg_line_length + 32)) / 1024 / 1024
buffer_mb = (window_size * avg_line_length) / 1024 / 1024

total_mb = history_mb + sequences_mb + buffer_mb
print(f"Estimated memory: {total_mb:.1f} MB")
```

### "High CPU usage"

**Diagnosis**:
1. Large window size → more string comparisons
2. Hash transform → subprocess overhead
3. Many unique patterns → more candidate evaluation

**Solutions**:
```bash
# Reduce window size
uniqseq --window-size 3 app.log  # Instead of 50

# Remove expensive transforms
uniqseq --skip-chars 20 app.log  # Instead of --hash-transform

# Limit pattern tracking
uniqseq --track '^ERROR' app.log  # Only process ERROR lines
```

## Best Practices

1. **Start simple**: Use defaults first, optimize only if needed
2. **Measure first**: Benchmark before optimizing
3. **Right-size window**: Use smallest window that works
4. **Avoid transforms**: Use skip-chars when possible
5. **Bounded history**: Use limited history for streaming
6. **Filter early**: Use `--track` to reduce processing
7. **Preprocess once**: Don't repeat expensive transforms per line

## Performance Checklist

Before processing large files:

- [ ] Tested on sample (1000 lines) to verify configuration
- [ ] Window size is appropriate (not larger than needed)
- [ ] Using skip-chars instead of hash-transform if possible
- [ ] History depth is appropriate (bounded for streams, unlimited for files)
- [ ] Using pattern filtering if only some lines need deduplication
- [ ] Benchmarked configuration on representative sample

## See Also

- [Choosing Window Size](./choosing-window-size.md) - Window size optimization
- [History Management](../features/history/history.md) - History depth trade-offs
- [Algorithm Details](../about/algorithm.md) - How uniqseq works internally
- [CLI Reference](../reference/cli.md) - All performance-related options
