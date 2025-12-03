# Performance Guide

Understand uniqseq's performance characteristics and optimize for your use case.

## Quick Performance Facts

| Characteristic | Description |
|---------------|-------------|
| **Throughput** | Approximately constant (lines per second) |
| **Total time** | Linear scaling with input size - O(n) |
| **Memory** | Bounded by history size and unique pattern count |
| **Disk I/O** | Single-pass streaming (reads once, writes once) |
| **Space complexity** | O(h + u×w) - h=history, u=unique seqs, w=window |

## Performance Characteristics

### Throughput

**Throughput is approximately constant** - the algorithm processes a relatively steady number of lines per second. Total processing time scales linearly with input size (O(n)).

**Factors affecting speed** (relative impact):

1. **Window size**: Larger windows require more comparisons per line
2. **Pattern diversity**: More unique patterns increase memory operations
3. **Hash transforms**: External process overhead for each line (significant)
4. **I/O**: Disk speed, network latency, pipe buffer size

**Measure your throughput**:
```bash
# Generate test data
seq 1 1000000 | awk '{print "Line " $1}' > test.log

# Benchmark
time uniqseq test.log --window-size 3 > /dev/null
```

Use the `time` command to measure actual performance on your hardware and data.

### Memory Usage

uniqseq uses bounded memory regardless of input size:

```
Total memory = History + Sequences + Window Buffer

History:         Fixed size based on max_history
Sequences:       Grows with number of unique patterns found
Window Buffer:   Fixed size based on window_size
```

**Memory control**:

```bash
# Default: Bounded by max_history (file mode: unlimited)
uniqseq large.log

# Smaller history bound: Less memory
uniqseq --max-history 50000 large.log

# Unlimited: Memory grows with unique patterns
uniqseq --unlimited-history large.log
```

**Monitor actual memory usage**:
```bash
# Check peak memory consumption
/usr/bin/time -v uniqseq large.log 2>&1 | grep "Maximum resident"
```

### CPU Usage

**Algorithm complexity**: O(n × w × c)
- n = number of lines
- w = window size
- c = candidates per position (controlled by max_candidates)

**Amortized**: O(n) for most real-world inputs

**CPU-intensive operations** (ordered by typical impact):
1. **Hashing**: BLAKE2b hashing of window contents (primary cost)
2. **Candidate tracking**: Position checks for active candidates (scales with max_candidates)
3. **String comparison**: Exact line matching for candidates
4. **Hash transform**: External subprocess if enabled (can dominate if used)

**Candidate limiting** (default: 100): Limits concurrent candidate tracking for better performance. Lower values improve speed but may miss some patterns.

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
| Large files | `--max-history 100000` | Balance accuracy/memory |
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

Larger window sizes are slower. Benchmark on your data to find the optimal size.

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

### 4. Tune Candidate Tracking

**Problem**: High CPU usage from tracking too many concurrent candidates

**Solution**: Adjust `--max-candidates` based on your accuracy vs speed requirements

```bash
# Faster: Limit candidates (may miss ~10% of patterns)
uniqseq --max-candidates 30 large-file.log

# Balanced (default): Good for most use cases
uniqseq --max-candidates 100 large-file.log

# More accurate: Track more candidates (slower)
uniqseq --max-candidates 200 large-file.log

# Maximum accuracy: Unlimited (slowest, finds all patterns)
uniqseq --unlimited-candidates large-file.log
```

**Performance trade-offs**:

| Setting | Speed | Accuracy | Use Case |
|---------|-------|----------|----------|
| `--max-candidates 30` | Fastest | ~90% | Large files, speed critical |
| `--max-candidates 100` | Fast | ~95% | General use (default) |
| `--max-candidates 200` | Moderate | ~98% | Important logs |
| `--unlimited-candidates` | Slow | 100% | Comprehensive analysis |

**Benchmark different settings**:
```bash
# Test candidate limits on your data
for c in 30 50 100 200; do
    echo -n "Candidates $c: "
    time uniqseq --max-candidates $c large.log > /dev/null 2>&1
done

# Test unlimited
echo -n "Unlimited: "
time uniqseq --unlimited-candidates large.log > /dev/null 2>&1
```

**When to tune**:
- **Lower limit** (30-50): Processing very large files where speed is critical
- **Default** (100): Most use cases - good balance
- **Higher limit** (200+): Critical logs where accuracy matters more than speed
- **Unlimited**: Comprehensive analysis, pattern discovery, baseline comparison

### 5. Pattern Filtering

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

If ERROR lines are a small fraction of the log, filtering provides proportional speedup.

### 6. Streaming vs Batch

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

### Scenario 1: Very Large Log File

**Problem**: Need to deduplicate massive log file

**Approach**:
```bash
# Use limited history and candidates to bound memory and CPU
uniqseq --window-size 3 \
        --max-history 100000 \
        --max-candidates 50 \
        --skip-chars 24 \
        huge-log-file.log > clean.log
```

**Why**:
- `--window-size 3`: Small window → faster processing
- `--max-history 100000`: Bounded memory
- `--max-candidates 50`: Faster candidate tracking, good accuracy
- `--skip-chars 24`: Faster than hash-transform for timestamps

**Characteristics**:
- Memory: Bounded by max-history setting
- Processing: Single-pass streaming
- Throughput: Linear scaling

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

**Characteristics**:
- Latency: Minimal (no buffering with window-size 1)
- Memory: Small (bounded by history setting)
- CPU: Low (only processes ERROR lines)

### Scenario 3: Build Log Deduplication

**Problem**: Large build log with compiler warnings

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

**Characteristics**:
- Processing: Fast batch mode
- Memory: Scales with number of unique warnings

### Scenario 4: Complex Transform with Large File

**Problem**: Need to normalize data in large file

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
- Approach 1: Much faster (single preprocessing pass)
- Approach 2: Slower (subprocess spawned per line)

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
MEM=$(uniqseq "$FILE" > /dev/null 2>&1; \
      /usr/bin/time -v uniqseq "$FILE" 2>&1 | \
      grep "Maximum resident" | awk '{print $6/1024}')
END=$(date +%s)
TIME=$((END-START))
STATS=$(uniqseq "$FILE" --stats-format json 2>&1 | \
        jq -r '.statistics.redundancy_pct')
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

**Understanding memory usage**:

Memory is determined by three factors:
1. **History size**: Controlled by `--max-history`
2. **Unique sequences**: Varies with data (check statistics)
3. **Window buffer**: Controlled by `--window-size`

Use `--stats-format json` to see actual `unique_sequences_tracked` count.

### "High CPU usage"

**Diagnosis**:
1. Large window size → more string comparisons
2. Too many candidates → excessive position checking
3. Hash transform → subprocess overhead
4. Many unique patterns → more candidate evaluation

**Solutions**:
```bash
# Reduce window size
uniqseq --window-size 3 app.log  # Instead of 50

# Limit candidate tracking (biggest CPU impact)
uniqseq --max-candidates 30 app.log  # Instead of 100

# Remove expensive transforms
uniqseq --skip-chars 20 app.log  # Instead of --hash-transform

# Limit pattern tracking
uniqseq --track '^ERROR' app.log  # Only process ERROR lines
```

**Test candidate limit impact**:
```bash
# Measure speedup from limiting candidates
time uniqseq app.log > /dev/null  # Baseline (100 candidates)
time uniqseq --max-candidates 30 app.log > /dev/null  # Faster
```

Typically, reducing from 100 to 30 candidates provides 2-3x speedup with ~10% accuracy trade-off.

## Best Practices

1. **Start simple**: Use defaults first, optimize only if needed
2. **Measure first**: Benchmark before optimizing
3. **Right-size window**: Use smallest window that works
4. **Tune candidates**: Lower `--max-candidates` for speed, higher for accuracy
5. **Avoid transforms**: Use skip-chars when possible
6. **Bounded history**: Use limited history for streaming
7. **Filter early**: Use `--track` to reduce processing
8. **Preprocess once**: Don't repeat expensive transforms per line

## Performance Checklist

Before processing large files:

- [ ] Tested on sample to verify configuration
- [ ] Window size is appropriate (not larger than needed)
- [ ] Candidate limit tuned (lower for speed, higher for accuracy)
- [ ] Using skip-chars instead of hash-transform if possible
- [ ] History depth is appropriate (bounded for streams, unlimited for files)
- [ ] Using pattern filtering if only some lines need deduplication
- [ ] Benchmarked configuration on representative sample

## See Also

- [Choosing Window Size](./choosing-window-size.md) - Window size optimization
- [History Management](../features/history/history.md) - History depth trade-offs
- [Algorithm Details](../about/algorithm.md) - How uniqseq works internally
- [CLI Reference](../reference/cli.md) - All performance-related options
