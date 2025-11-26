# Production Monitoring: Long-Running Job Analysis

Monitor batch job progress and clean up verbose logs from long-running ETL processes, data migrations, or scheduled tasks using statistics tracking.

## The Problem

Long-running batch jobs produce verbose logs with repeated progress messages:

- **Repetitive progress updates** - "Processing batch N" appears hundreds of times
- **Hard to spot errors** - Important warnings buried in progress noise
- **Log file bloat** - Gigabytes of logs for multi-hour jobs
- **No summary metrics** - Manual counting to understand job completion

## Input Data

???+ note "batch-job.log"
    ```text hl_lines="4-5 6-7 8-9 10-11 12-13 15-16 17-18 19-20 21-22 23-24 26-27 28-29"
    --8<-- "use-cases/production-monitoring/fixtures/batch-job.log"
    ```

    Batch job log with **30 lines** covering 12 batches:

    - "Processing batch N/100" appears **12×**
    - "Processed N records" appears **12×**
    - "Slow query detected" appears **2×** (lines 14, 19)
    - Other: startup, connection, checkpoint messages

## Output Data

???+ success "expected-clean.log"
    ```text hl_lines="14 19"
    --8<-- "use-cases/production-monitoring/fixtures/expected-clean.log"
    ```

    **Result**: **29 lines** (1 duplicate "Slow query" warning removed)

    The repeated progress messages have different content (batch numbers, record counts, percentages), so they're not exact duplicates when ignoring timestamps.

## Solution

=== "CLI (Clean Log)"

    <!-- verify-file: output.log expected: expected-clean.log -->
    <!-- termynal -->
    ```console
    $ uniqseq batch-job.log \
        --skip-chars 20 \
        --window-size 1 \
        --quiet > clean-job.log
    ```

    **Options:**

    - `--skip-chars 20`: Skip timestamp prefix
    - `--window-size 1`: Deduplicate individual lines
    - `--quiet`: Suppress statistics (only output clean log)

=== "CLI (Track Progress)"

    ```console
    $ uniqseq batch-job.log \
        --skip-chars 20 \
        --window-size 1 \
        --stats-format json \
        > clean-job.log \
        2> job-stats.json
    ```

    **Result**: Clean log to stdout, metrics to stderr

    Extract specific metrics with `jq`:

    ```bash
    $ jq '.statistics.redundancy_pct' job-stats.json
    3.3

    $ jq '.statistics.lines' job-stats.json
    {
      "total": 30,
      "emitted": 29,
      "skipped": 1
    }
    ```

=== "Python (With Stats)"

    <!-- verify-file: output.log expected: expected-clean.log -->
    ```python
    from uniqseq import UniqSeq
    import json

    uniqseq = UniqSeq(
        skip_chars=20,    # (1)!
        window_size=1,    # (2)!
    )

    # Process log file
    with open("batch-job.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)

    # Get statistics programmatically
    stats = uniqseq.get_stats()  # (3)!

    # Save metrics
    with open("job-stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    ```

    1. Skip 20-character timestamp prefix
    2. Deduplicate individual log lines
    3. Access statistics from uniqseq object

## How It Works

Deduplication removes exact duplicate messages while preserving unique progress updates:

```text
Before (30 lines):
2024-01-15 10:00:10 [INFO] Processing batch 1/100 (1000 records)
2024-01-15 10:00:15 [INFO] Processed 1000 records (1% complete)
2024-01-15 10:00:20 [INFO] Processing batch 2/100 (1000 records)
2024-01-15 10:00:25 [INFO] Processed 2000 records (2% complete)
2024-01-15 10:01:00 [WARN] Slow query detected: transaction_summary took 2.5s
...
2024-01-15 10:01:25 [WARN] Slow query detected: transaction_summary \
    took 2.5s  ← duplicate

After (29 lines):
Same content, but duplicate warning removed
```

## Real-World Workflows

### Monitor Job Progress in Real-Time

Watch a running job and see only new, unique log entries:

```bash
# Follow log file, show only new unique patterns
tail -f /var/log/batch-job.log | \
    uniqseq --skip-chars 20 --window-size 1
```

Only new unique messages appear (repeated "Processing batch N" with different N will show, exact duplicates won't).

### Extract Job Statistics

Monitor deduplication metrics to understand log verbosity:

```bash
#!/bin/bash
# Analyze job logs after completion

JOB_LOG="/var/log/etl-job-$(date +%Y%m%d).log"

uniqseq "$JOB_LOG" --skip-chars 20 --window-size 1 \
    --stats-format json \
    > "/var/clean-logs/$(basename $JOB_LOG)" \
    2> "/var/metrics/$(basename $JOB_LOG).json"

# Extract metrics
METRICS_FILE="/var/metrics/$(basename $JOB_LOG).json"
REDUNDANCY=$(jq '.statistics.redundancy_pct' "$METRICS_FILE")
echo "Log redundancy: ${REDUNDANCY}%"

# Alert if excessive duplication
if (( $(echo "$REDUNDANCY > 20" | bc -l) )); then
    echo "WARNING: High log duplication - consider reducing log verbosity"
fi
```

### Daily Batch Job Cleanup

Automatically clean and archive batch job logs:

```bash
#!/bin/bash
# Daily log cleanup for batch jobs

LOG_DIR="/var/log/batch-jobs"
ARCHIVE_DIR="/var/archive/clean-logs"
STATS_DIR="/var/metrics/batch-stats"

for log in ${LOG_DIR}/*.log; do
    basename=$(basename "$log")

    # Deduplicate and capture stats
    uniqseq "$log" --skip-chars 20 --window-size 1 \
        --stats-format json \
        > "${ARCHIVE_DIR}/${basename}" \
        2> "${STATS_DIR}/${basename}.json"

    # Extract key metrics
    total=$(jq '.statistics.lines.total' "${STATS_DIR}/${basename}.json")
    emitted=$(jq '.statistics.lines.emitted' "${STATS_DIR}/${basename}.json")

    echo "${basename}: ${total} → ${emitted} lines"
done

# Compress original logs
gzip ${LOG_DIR}/*.log
```

### Compare Job Runs

Track deduplication metrics over time to detect logging changes:

```bash
#!/bin/bash
# Compare batch job patterns week-over-week

# Process week 1 logs
uniqseq week1-job.log --stats-format json --quiet \
    > /dev/null 2> week1-stats.json

# Process week 2 logs
uniqseq week2-job.log --stats-format json --quiet \
    > /dev/null 2> week2-stats.json

# Compare redundancy
W1_RED=$(jq '.statistics.redundancy_pct' week1-stats.json)
W2_RED=$(jq '.statistics.redundancy_pct' week2-stats.json)

echo "Week 1 redundancy: ${W1_RED}%"
echo "Week 2 redundancy: ${W2_RED}%"

# Alert if significant change
DIFF=$(echo "$W2_RED - $W1_RED" | bc)
if (( $(echo "$DIFF > 10" | bc -l) )); then
    echo "⚠️  Redundancy increased by ${DIFF}% - check for logging loops"
fi
```

### Integration with Monitoring

Push deduplication metrics to monitoring systems:

```bash
#!/bin/bash
# Send batch job metrics to Prometheus

JOB_NAME="daily_etl"
LOG_FILE="/var/log/${JOB_NAME}.log"

# Process and get stats
uniqseq "$LOG_FILE" --stats-format json --quiet \
    > /dev/null 2> stats.json

# Extract metrics
TOTAL=$(jq '.statistics.lines.total' stats.json)
EMITTED=$(jq '.statistics.lines.emitted' stats.json)
SKIPPED=$(jq '.statistics.lines.skipped' stats.json)
REDUNDANCY=$(jq '.statistics.redundancy_pct' stats.json)

# Push to Prometheus pushgateway
cat <<EOF | curl --data-binary @- http://pushgateway:9091/metrics/job/batch_logs
# TYPE batch_log_lines gauge
batch_log_lines{job="${JOB_NAME}",type="total"} ${TOTAL}
batch_log_lines{job="${JOB_NAME}",type="emitted"} ${EMITTED}
batch_log_lines{job="${JOB_NAME}",type="skipped"} ${SKIPPED}
batch_log_redundancy_pct{job="${JOB_NAME}"} ${REDUNDANCY}
EOF
```

## Advanced Scenarios

### Multi-Stage Log Processing

Clean logs and filter for errors:

```bash
# Stage 1: Deduplicate
uniqseq batch-job.log --skip-chars 20 --window-size 1 --quiet | \
# Stage 2: Extract errors and warnings
    grep -E "ERROR|WARN" | \
# Stage 3: Save for review
    tee errors.log
```

### Normalize Variable Data

Remove timestamps and counters for more aggressive deduplication:

```bash
# Normalize progress messages before deduplication
uniqseq batch-job.log \
    --hash-transform 'sed -E "s/[0-9]+/N/g"' \
    --window-size 1 \
    --quiet
```

This groups all "Processing batch N" messages together (more aggressive).

### Extract Job Summary

Build a concise job summary from verbose logs:

```bash
#!/bin/bash
# Create executive summary of batch job

echo "=== Batch Job Summary ==="
echo ""

# Start/end times
echo "Started: $(head -1 batch-job.log | cut -d' ' -f1-2)"
echo "Ended: $(tail -1 batch-job.log | cut -d' ' -f1-2)"
echo ""

# Deduplication metrics
uniqseq batch-job.log --stats-format json --quiet \
    > /dev/null 2> stats.json

echo "Log Statistics:"
jq -r '.statistics |
    "  Total lines: \(.lines.total)
     Unique events: \(.lines.emitted)
     Duplicates removed: \(.lines.skipped)
     Redundancy: \(.redundancy_pct)%"' stats.json
echo ""

# Error summary
echo "Issues Found:"
uniqseq batch-job.log --skip-chars 20 --window-size 1 --quiet | \
    grep -c ERROR | \
    xargs -I {} echo "  Errors: {}"

uniqseq batch-job.log --skip-chars 20 --window-size 1 --quiet | \
    grep -c WARN | \
    xargs -I {} echo "  Warnings: {}"
```

### Detect Logging Loops

Find suspiciously repeated messages:

```bash
# Show messages that appear many times (potential loops)
uniqseq batch-job.log --skip-chars 20 --annotate --quiet | \
    grep "DUPLICATE" | \
    grep -oE "seen [0-9]+ times" | \
    awk '{print $2}' | \
    sort -rn | \
    head -1 | \
    xargs -I {} echo "Most repeated message seen {} times"
```

If a message repeats hundreds of times, investigate for logging loops.

## Performance Benefits

### Storage Savings

```bash
# Before cleanup
$ wc -c < batch-job-full.log
5242880  # 5 MB

# After deduplication (typical 10-30% reduction for batch jobs)
$ uniqseq batch-job-full.log --quiet | wc -c
4194304  # 4 MB → 20% reduction
```

### Analysis Speed

```bash
# Time to grep through original log
$ time grep ERROR batch-job-full.log
real    0m2.5s

# Time to grep through deduplicated log
$ time grep ERROR batch-job-clean.log
real    0m2.0s  # 20% faster
```

## When to Use This

**Good candidates:**
- ✅ ETL jobs with repeated progress updates
- ✅ Data migration scripts with batch processing
- ✅ Long-running imports/exports (hours to days)
- ✅ Scheduled tasks with verbose logging

**Not recommended:**
- ❌ Short jobs (<1 minute) with unique messages
- ❌ Jobs where every log line is critical for compliance
- ❌ Real-time streaming applications (use tail -f | uniqseq instead)

## See Also

- [Statistics](../../features/stats/stats.md) - Understanding and using statistics output
- [Skip Chars](../../features/skip-chars/skip-chars.md) - Ignoring timestamp prefixes
- [Hash Transform](../../features/hash-transform/hash-transform.md) - Normalizing variable data
- [Error Pattern Analysis](./error-pattern-analysis.md) - Extracting unique errors
