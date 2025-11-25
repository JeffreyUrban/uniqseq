# Statistics Output

After processing, uniqseq automatically displays statistics showing what was
deduplicated. This helps you understand the effectiveness of deduplication
and tune parameters like window size.

## What It Does

Statistics provide insight into deduplication results:

- **Default**: Table format displayed after processing
- **JSON format**: Machine-readable with `--stats-format json`
- **Quiet mode**: Suppress with `--quiet`
- **Use case**: Understand deduplication effectiveness, tune parameters

**Key insight**: Statistics help you verify deduplication worked and measure
data redundancy.

## Example: Understanding Deduplication Results

This example shows basic log data with repeated sequences. Statistics reveal
how much redundancy was removed.

???+ note "Input: Log with repeated sequences"
    ```text hl_lines="1-3 4-6 8-10"
    --8<-- "features/stats/fixtures/input.txt"
    ```

    **Patterns**:
    - Lines 1-3 repeat as lines 4-6 (ABC sequence x2)
    - Lines 8-10 repeat line 7 and 8-9 (DE sequence x2)

### Default: Statistics Table

By default, statistics are displayed to stderr after processing:

<!-- verify-file: stats-table.txt expected: expected-stats-table.txt -->
```console
$ uniqseq input.txt --window-size 3 > output.txt 2> stats-table.txt
```

Statistics are written to stderr (`stats-table.txt`):

```text
Auto-detected file input: using unlimited history (override with --max-history)
Processing: input.txt

        Deduplication Statistics
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Metric                   ┃     Value ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ Total lines processed    │        10 │
│ Lines emitted            │         7 │
│ Lines skipped            │         3 │
│ Redundancy               │     30.0% │
│ Unique sequences tracked │         1 │
│ Window size              │         3 │
│ Max history              │ unlimited │
└──────────────────────────┴───────────┘
```

**Note**: Statistics are written to stderr, so stdout can be redirected
without capturing statistics.

**Statistics explained**:

- **Total lines processed**: Input line count (10)
- **Lines emitted**: Output line count (7)
- **Lines skipped**: Duplicate lines removed (3)
- **Redundancy**: Percentage of duplicate data (30%)
- **Unique sequences tracked**: Distinct patterns found (1)
- **Window size**: Configured window size (3)
- **Max history**: History limit setting (unlimited)

### JSON Format: Machine-Readable

Use `--stats-format json` for programmatic processing:

<!-- verify-file: stats-json.txt expected: expected-stats-json.txt -->
```console
$ uniqseq input.txt --window-size 3 --stats-format json \
    > output.txt 2> stats-json.txt
```

Statistics in JSON format (`stats-json.txt`):

```json
{
  "statistics": {
    "lines": {
      "total": 10,
      "emitted": 7,
      "skipped": 3
    },
    "redundancy_pct": 30.0,
    "sequences": {
      "unique_tracked": 1
    }
  },
  "configuration": {
    "window_size": 3,
    "max_history": "unlimited",
    "skip_chars": 0
  }
}
```

**Benefits**:
- Parse with `jq`, Python, or other tools
- Integrate into monitoring systems
- Track deduplication metrics over time
- Compare configurations programmatically

### Quiet Mode: Suppress Statistics

Use `--quiet` to suppress all statistics and progress output:

=== "CLI"

    <!-- verify-file: output.txt expected: expected-deduplicated.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 --quiet > output.txt
    ```

=== "Python"

    <!-- verify-file: output.txt expected: expected-deduplicated.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(window_size=3)

    with open("input.txt") as f:
        with open("output.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)

    # Get statistics programmatically
    stats = uniqseq.get_stats()  # (1)!
    print(f"Redundancy: {stats['redundancy_pct']:.1f}%")
    print(f"Skipped: {stats['skipped']} lines")
    ```

    1. Access statistics from uniqseq object

???+ success "Output: Deduplicated log"
    ```text
    --8<-- "features/stats/fixtures/expected-deduplicated.txt"
    ```

    **Result**: 3 duplicate lines removed. No statistics printed to stderr.

## Statistics Fields

### Line Metrics

| Field | Description | Example |
|-------|-------------|---------|
| `total` | Total input lines processed | `10` |
| `emitted` | Lines written to output | `7` |
| `skipped` | Duplicate lines removed | `3` |

### Deduplication Metrics

| Field | Description | Calculation |
|-------|-------------|-------------|
| `redundancy_pct` | Percentage of duplicate data | `(skipped / total) * 100` |
| `unique_sequences` | Distinct patterns tracked | Count of unique window hashes |

### Configuration Echo

| Field | Description | Purpose |
|-------|-------------|---------|
| `window_size` | Configured window size | Verify settings |
| `max_history` | History limit setting | Check if limited |
| `skip_chars` | Prefix skip setting | Confirm skip value |

## Common Use Cases

### Tuning Window Size

```bash
# Try different window sizes, compare redundancy
for size in 3 5 10; do
    echo "Window size: $size"
    uniqseq log.txt --window-size $size --quiet 2>&1 | \
        grep "Redundancy"
done
```

### Monitoring Deduplication

```bash
# Track deduplication metrics over time
uniqseq app.log --stats-format json 2> stats.json
jq '.statistics.redundancy_pct' stats.json

# Alert if redundancy is high
REDUNDANCY=$(jq '.statistics.redundancy_pct' stats.json)
if (( $(echo "$REDUNDANCY > 50" | bc -l) )); then
    echo "Warning: High redundancy detected!"
fi
```

### Batch Processing Reports

```bash
# Process multiple files, collect stats
for log in *.log; do
    uniqseq "$log" --quiet --stats-format json \
        > "clean/$log" 2> "stats/${log}.json"
done

# Generate summary report
jq -s 'map(.statistics.lines) | add' stats/*.json
```

### Validating Configuration

```bash
# Verify settings are applied
uniqseq input.txt --window-size 5 --skip-chars 20 \
    | grep -A 2 "Configuration"

# Check if history limit is in effect
uniqseq large.log --max-history 10000 \
    | grep "Max history"
```

## Programmatic Access (Python API)

```py
from uniqseq import UniqSeq
import json

uniqseq = UniqSeq(window_size=5)

# Process data
with open("input.log") as f:
    with open("output.log", "w") as out:
        for line in f:
            uniqseq.process_line(line.rstrip("\n"), out)
        uniqseq.flush(out)

# Access statistics
stats = uniqseq.get_stats()

# Print formatted stats
print(f"Processed {stats['total']:,} lines")
print(f"Removed {stats['skipped']:,} duplicates "
      f"({stats['redundancy_pct']:.1f}% redundancy)")
print(f"Output: {stats['emitted']:,} lines")

# Save as JSON
with open("stats.json", "w") as f:
    json.dump(stats, f, indent=2)
```

## Understanding Redundancy Percentage

The redundancy metric helps assess data patterns:

| Redundancy % | Interpretation | Action |
|--------------|----------------|--------|
| 0-10% | Low duplication | Data is mostly unique |
| 10-30% | Moderate duplication | Deduplication helpful |
| 30-50% | High duplication | Significant space savings |
| 50%+ | Very high duplication | Consider increasing window size |

**Example interpretations**:

```bash
# Low redundancy (5%)
# Input: 10000 lines → Output: 9500 lines
# Most data is unique, minimal duplication

# High redundancy (45%)
# Input: 10000 lines → Output: 5500 lines
# Nearly half the data was duplicates

# Very high redundancy (80%)
# Input: 10000 lines → Output: 2000 lines
# Extremely repetitive data
```

## Statistics with Other Features

### With Annotations

```bash
# Statistics show skipped lines, annotations show what was skipped
uniqseq log.txt --annotate | grep DUPLICATE | wc -l
# Should match "Lines skipped" in statistics
```

### With Inverse Mode

```bash
# Statistics show different metrics in inverse mode
uniqseq log.txt --inverse
# "Lines emitted" = duplicates found
# "Lines skipped" = unique lines filtered out
```

### With Pattern Filtering

```bash
# Statistics only count tracked patterns
uniqseq log.txt --track "ERROR" --window-size 3
# Total lines = all lines processed
# Skipped = duplicate ERROR sequences found
# Other lines passed through without counting as "skipped"
```

## Performance Note

Statistics collection has minimal overhead:
- Counters updated during processing (no post-processing)
- No memory overhead (just integer counters)
- JSON formatting slightly slower than table (still negligible)

## Rule of Thumb

**Use statistics to:**
- Verify deduplication is working
- Measure data redundancy
- Tune window size (maximize redundancy while avoiding false positives)
- Monitor deduplication effectiveness over time

**Use JSON format when:**
- Integrating with monitoring systems
- Batch processing multiple files
- Building automation around deduplication
- Generating reports programmatically

**Use quiet mode when:**
- You only need the deduplicated output
- Piping to another command
- Running in cron jobs where stderr is logged
- Performance testing (avoid terminal I/O)

## See Also

- [Window Size](../window-size/window-size.md) - Tuning for better results
- [CLI Reference](../../reference/cli.md) - Complete statistics documentation
- [Guides: Performance](../../guides/performance.md) - Optimization tips
