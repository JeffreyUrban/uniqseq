# Choosing the Right Window Size

Window size is the most important parameter for tuning uniqseq to your data. This guide helps you choose the right value for different scenarios.

## Quick Reference

| Scenario | Recommended Window Size | Rationale |
|----------|------------------------|-----------|
| Single-line log entries | `1` | Each line is independent |
| Short error messages (2-3 lines) | `3` | Detects 2+ line patterns |
| Stack traces (5-10 lines) | `5` | Typical stack trace length |
| Multi-line JSON/XML | `10` (default) | Structured data blocks |
| Large code blocks | `20-50` | Function-length patterns |
| Unknown data | `1` then increase | Start conservative |

## Understanding Window Size

**Window size = minimum sequence length to detect**

- Window size `3` → detects sequences of 3+ lines
- Window size `10` → detects sequences of 10+ lines
- Sequences shorter than window size are **never** detected

**Key trade-off**:

- **Smaller** = more sensitive, finds shorter patterns
- **Larger** = less sensitive, only finds longer patterns

## Decision Process

### Step 1: Identify Your Pattern Length

Look at your data and estimate how long repeated patterns typically are:

```bash
# Example: Check a sample of your data
head -50 your-file.log
```

**Count the lines in a typical repeated pattern**:

- Error message with timestamp? → 1 line
- Exception with stack trace? → 5-10 lines
- Build output block? → 10-20 lines
- Multi-line JSON object? → Variable

### Step 2: Start Conservative

**Rule of thumb**: Start with a window size slightly smaller than your estimated pattern length.

- Estimated 5-line pattern? Try `--window-size 3`
- Estimated 10-line pattern? Try `--window-size 5`
- Estimated 20-line pattern? Try `--window-size 10`

**Why smaller?** Catches both your target patterns AND any shorter ones that also repeat.

### Step 3: Test and Adjust

Run uniqseq with your initial window size and check the results:

```bash
# Test with initial window size
uniqseq your-file.log --window-size 5 > output.log

# Compare sizes
wc -l your-file.log output.log
```

**If too many lines removed**: Increase window size (being too aggressive)
**If too few lines removed**: Decrease window size (missing patterns)

### Step 4: Use Statistics

Check the statistics to understand what's happening:

```bash
uniqseq your-file.log --window-size 5 --stats-format json 2>&1 | \
    jq '.statistics'
```

Key metrics:

- `redundancy_pct`: Percentage of duplicate lines (target: 20-80%)
- `unique_sequences_tracked`: Number of distinct patterns found
- `lines.skipped`: Total lines removed

## Common Scenarios

### Single-Line Deduplication

**Use case**: Log files where each line is independent

```bash
# Apache access logs - same request repeated
uniqseq access.log --window-size 1
```

**Window size 1**:

- Treats each line as its own sequence
- Perfect for flat log files
- Equivalent to `sort | uniq` but preserves order

### Application Error Logs

**Use case**: Errors with timestamps + message

```text
2024-01-15 10:30:15 ERROR: Database connection failed
2024-01-15 10:30:16 ERROR: Database connection failed
2024-01-15 10:30:17 ERROR: Database connection failed
```

**Solution**: Use `--skip-chars` with `--window-size 1`

```bash
# Ignore timestamps (first 20 chars), deduplicate messages
uniqseq error.log --skip-chars 20 --window-size 1
```

### Stack Traces

**Use case**: Multi-line exceptions that repeat

```text
Traceback (most recent call last):
  File "app.py", line 42, in handler
    process_request()
  File "app.py", line 87, in process_request
    db.connect()
ConnectionError: Connection refused
```

**Typical length**: 5-10 lines
**Recommended**: `--window-size 5`

```bash
# Detect 5+ line stack traces
uniqseq app.log --window-size 5
```

### Build Output

**Use case**: Compiler warnings or test failures

```text
warning: unused variable: `result`
  --> src/main.rs:42:9
   |
42 |     let result = calculate();
   |         ^^^^^^ help: if this is intentional,
   |                prefix it with an underscore: `_result`
```

**Typical length**: 3-5 lines
**Recommended**: `--window-size 3`

```bash
# Catch repeated warnings
uniqseq build.log --window-size 3
```

### JSON/Structured Data

**Use case**: Multi-line JSON objects

```json
{
  "timestamp": "2024-01-15T10:30:15Z",
  "level": "ERROR",
  "message": "Connection failed",
  "stack": "..."
}
```

**Variable length**: 5-20+ lines
**Recommended**: Start with `--window-size 5`, adjust up if needed

```bash
# Deduplicate JSON log entries
uniqseq app.json --window-size 5
```

## Advanced Tuning

### Finding the Optimal Window Size

Try multiple window sizes and compare results:

```bash
#!/bin/bash
# Test different window sizes

for size in 1 3 5 10 20; do
    lines=$(uniqseq your-file.log --window-size $size --quiet | wc -l)
    echo "Window $size: $lines lines remaining"
done
```

Example output:

```text
Window 1: 8500 lines remaining
Window 3: 7200 lines remaining  ← Good balance
Window 5: 6800 lines remaining
Window 10: 9500 lines remaining  ← Too large, missing patterns
Window 20: 9900 lines remaining
```

**Choose the "elbow"**: Where increasing window size starts having less effect.

### Window Size Too Large?

**Symptoms**:

- Very few lines removed
- Statistics show low redundancy (< 10%)
- Known duplicate patterns not detected

**Solution**: Decrease window size

```bash
# Before: Missing 4-line patterns
uniqseq app.log --window-size 10  # Only finds 10+ line patterns

# After: Catching 4-line patterns
uniqseq app.log --window-size 3   # Finds 3+ line patterns
```

### Window Size Too Small?

**Symptoms**:

- Too many lines removed
- Important variations being deduplicated
- Statistics show very high redundancy (> 90%)

**Solution**: Increase window size or use pattern filtering

```bash
# Option 1: Increase window size
uniqseq app.log --window-size 10

# Option 2: Track only specific patterns
uniqseq app.log --window-size 3 --track "^ERROR"
```

### Mixed Pattern Lengths

**Problem**: Your data has both short (3-line) and long (20-line) patterns

**Solution 1**: Choose smaller window (catches both)

```bash
# Window size 3 catches 3-line AND 20-line patterns
uniqseq app.log --window-size 3
```

**Solution 2**: Multiple passes

```bash
# Pass 1: Remove long patterns
uniqseq app.log --window-size 20 | \
# Pass 2: Remove short patterns
    uniqseq --window-size 3 > output.log
```

## Real-World Examples

### CI Build Logs

**Pattern**: Repeated test failures with setup + error + teardown

```bash
# Typical test failure is 10-15 lines
# Use window size 5 to catch partial matches too
uniqseq build.log --window-size 5 > clean-build.log
```

### Production Error Monitoring

**Pattern**: Same error repeating with different timestamps

```bash
# Single-line errors, skip timestamp prefix
uniqseq production.log --skip-chars 20 --window-size 1
```

### Memory Dump Analysis

**Pattern**: Repeated 16-byte or 32-byte blocks

```bash
# Hexdump output is 4 lines per 64 bytes
# Use window size 4 for 64-byte block detection
uniqseq memory.hex --window-size 4
```

## Troubleshooting

### "Nothing is being deduplicated"

1. **Check if patterns actually repeat**:
   ```bash
   sort your-file.log | uniq -c | sort -rn | head
   ```

2. **Try window size 1**:
   ```bash
   uniqseq your-file.log --window-size 1
   ```

3. **Check for variable data** (timestamps, IDs):
   ```bash
   # Use skip-chars or hash-transform
   uniqseq your-file.log --skip-chars 20 --window-size 1
   ```

### "Too much is being removed"

1. **Increase window size**:
   ```bash
   # From 3 to 5
   uniqseq your-file.log --window-size 5
   ```

2. **Use pattern filtering**:
   ```bash
   # Only deduplicate ERROR lines
   uniqseq your-file.log --track "^ERROR"
   ```

3. **Check with annotations**:
   ```bash
   # See what's being marked as duplicate
   uniqseq your-file.log --window-size 3 --annotate | less
   ```

## Best Practices

1. **Start small, increase if needed**: Window size 1-3 is a safe starting point
2. **Use statistics**: Let the data guide your decision
3. **Test on a sample**: Try on 1000 lines before processing gigabytes
4. **Document your choice**: Record why you chose a particular window size
5. **Re-evaluate periodically**: Data patterns may change over time

## See Also

- [Window Size Feature](../features/window-size/window-size.md) - Technical details and examples
- [Performance Guide](./performance.md) - Optimization tips
- [Pattern Filtering](../features/pattern-filtering/pattern-filtering.md) - Selective deduplication
- [Skip Chars](../features/skip-chars/skip-chars.md) - Ignoring variable prefixes
