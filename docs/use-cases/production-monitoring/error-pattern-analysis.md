# Production Monitoring: Error Pattern Analysis

Extract and analyze unique error patterns from production logs to identify and prioritize issues requiring immediate attention.

## The Problem

Production environments generate massive log volumes with repeated errors:

- **Signal lost in noise** - Same errors repeated thousands of times
- **Hard to prioritize** - Can't quickly see distinct error types
- **Slow incident response** - Wading through duplicates wastes critical time
- **Poor pattern visibility** - Repeated errors obscure other issues

## Input Data

???+ note "production.log"
    ```text hl_lines="2 4 6 7 8 10 11 12 13 14 16 18 19 20"
    --8<-- "use-cases/production-monitoring/fixtures/production.log"
    ```

    Production log with **20 entries**, including **13 ERROR lines**:

    - Database connection timeout (lines 2, 4, 6, 8, 12, 16, 20) - appears **7×**
    - API authentication failed (lines 7, 10, 13, 19) - appears **4×**
    - Cache miss (lines 11, 14) - appears **2×**
    - File not found (line 18) - appears **1×**

## Output Data

???+ success "expected-output.log"
    ```text
    --8<-- "use-cases/production-monitoring/fixtures/expected-output.log"
    ```

    **Result**: **5 unique error patterns** (13 → 5 lines, 62% reduction)

    - Each distinct error type shown once
    - Timestamps preserved for first occurrence
    - Easy to see all active error patterns at a glance

## Solution

=== "CLI (Pipeline)"

    <!-- verify-file: output.log expected: expected-output.log -->
    <!-- termynal -->
    ```console
    $ grep ERROR production.log | \
        uniqseq --skip-chars 24 --window-size 1 --quiet > unique-errors.log
    ```

    **Pipeline stages:**

    1. `grep ERROR` - Extract only error lines
    2. `uniqseq --skip-chars 24` - Skip timestamp, deduplicate error messages
    3. Redirect to file for analysis

=== "CLI (Direct)"

    <!-- verify-file: output.log expected: expected-output.log -->
    ```console
    $ uniqseq production.log \
        --track 'ERROR' \
        --skip-chars 24 \
        --window-size 1 \
        --quiet > unique-errors.log
    ```

    **Options:**

    - `--track 'ERROR'`: Only process lines containing "ERROR"
    - `--skip-chars 24`: Skip timestamp prefix when comparing
    - `--window-size 1`: Deduplicate individual error lines

=== "Python"

    <!-- verify-file: output.log expected: expected-output.log -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        skip_chars=24,    # (1)!
        window_size=1,    # (2)!
    )

    with open("production.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                # Filter ERROR lines
                if "ERROR" in line:  # (3)!
                    uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Skip 24-character timestamp prefix
    2. Deduplicate individual error lines
    3. Manual filtering (or use --track in CLI)

## How It Works

By combining grep filtering with timestamp-aware deduplication, you can quickly extract unique error patterns:

```text
Before (13 ERROR lines):
2024-01-15 10:30:15.567 ERROR Database connection timeout...
2024-01-15 10:30:45.123 ERROR Database connection timeout...  ← duplicate
2024-01-15 10:31:15.789 ERROR Database connection timeout...  ← duplicate
...
(7 total database errors)

After (5 unique patterns):
2024-01-15 10:30:15.567 ERROR Database connection timeout...
2024-01-15 10:31:20.234 ERROR API authentication failed...
2024-01-15 10:32:30.456 ERROR Cache miss...
...
```

Each line represents a distinct error pattern requiring investigation.

## Real-World Workflows

### Quick Incident Triage

Extract unique errors for rapid assessment:

```bash
# Last hour of production errors
tail -n 10000 /var/log/app.log | \
    grep ERROR | \
    uniqseq --skip-chars 24 --window-size 1 | \
    wc -l
```

Output: `5` (5 distinct error types to investigate)

### Error Priority Ranking

Combine with frequency counting:

```bash
# Find most common errors
grep ERROR production.log | \
    uniqseq --skip-chars 24 --window-size 1 --inverse | \
    sort | \
    uniq -c | \
    sort -rn | \
    head -5
```

Output shows error frequency:
```text
  7 ERROR Database connection timeout: Connection to postgres://db:5432 \
      failed after 30s
  4 ERROR API authentication failed: Invalid JWT signature for user \
      service-account-prod
  1 ERROR Cache miss: Redis key 'user:12345' not found
  1 ERROR Cache miss: Redis key 'user:67890' not found
  1 ERROR File not found: /var/data/config/override.json
```

### Save Error Patterns for Investigation

Build a library of known error patterns:

```bash
#!/bin/bash
# Daily error pattern extraction

DATE=$(date +%Y-%m-%d)
LOG_DIR="/var/log/production"
PATTERN_DIR="/var/patterns/errors"

grep ERROR ${LOG_DIR}/app-${DATE}.log | \
    uniqseq --skip-chars 24 --window-size 1 \
        --library-dir ${PATTERN_DIR} \
        --quiet > /dev/null

# Now PATTERN_DIR contains all unique error signatures
ls -1 ${PATTERN_DIR}
```

### Multi-Stage Filtering

Filter by severity before deduplication:

```bash
# Extract critical errors only
grep -E "ERROR|CRITICAL|FATAL" production.log | \
    grep -v "HealthCheck" | \
    uniqseq --skip-chars 24 --window-size 1 | \
    tee critical-errors.log
```

### Real-Time Monitoring

Watch live logs for new error patterns:

```bash
# Monitor for new error patterns
tail -f /var/log/app.log | \
    grep --line-buffered ERROR | \
    uniqseq --skip-chars 24 --window-size 1
```

Only new (unique) error patterns will appear, filtering out repeated occurrences.

### Cross-Service Error Analysis

Analyze errors across multiple services:

```bash
#!/bin/bash
# Aggregate errors from all microservices

for service in auth api gateway payment; do
    echo "=== ${service} errors ==="
    grep ERROR /var/log/${service}.log | \
        uniqseq --skip-chars 24 --window-size 1 | \
        sed "s/^/[${service}] /"
done | \
    uniqseq --skip-chars 7 --window-size 1  # Skip "[service] " prefix
```

Shows unique errors across all services.

### Alert Integration

Send unique errors to alerting systems:

```bash
#!/bin/bash
# Send new error patterns to Slack

LIBRARY_DIR="/var/patterns/errors"

tail -n 1000 /var/log/production.log | \
    grep ERROR | \
    uniqseq --skip-chars 24 --window-size 1 \
        --library-dir ${LIBRARY_DIR} \
        --annotate | \
    grep "NEW PATTERN" | \
    while read line; do
        curl -X POST https://hooks.slack.com/... \
            -d "{\"text\": \"🚨 New error pattern: $line\"}"
    done
```

Only alerts on new error patterns, not duplicates.

## Performance Benefits

### Before Deduplication

```bash
$ grep ERROR production.log | wc -l
13
```

Analyst must review 13 error lines to understand issues.

### After Deduplication

```bash
$ grep ERROR production.log | uniqseq --skip-chars 24 --window-size 1 | wc -l
5
```

Analyst reviews 5 unique patterns → **62% reduction in review time**.

## Advanced Patterns

### Normalize Variable Data

Remove transaction IDs before deduplication:

```bash
# Remove variable parts to group similar errors
grep ERROR production.log | \
    uniqseq --skip-chars 24 \
        --hash-transform 'sed -E "s/user:[0-9]+/user:XXX/g"' \
        --window-size 1
```

Groups all "Cache miss: user:*" errors together.

### Time-Windowed Patterns

Analyze error patterns by time window:

```bash
#!/bin/bash
# Show error patterns for each hour

for hour in {00..23}; do
    echo "=== Hour ${hour}:00 ==="
    grep " ${hour}:" production.log | \
        grep ERROR | \
        uniqseq --skip-chars 24 --window-size 1
done
```

### Error Correlation

Find errors that occur together:

```bash
# Find 2-error sequences that repeat
grep ERROR production.log | \
    uniqseq --skip-chars 24 --window-size 2 --annotate | \
    grep "DUPLICATE"
```

Shows which errors consistently appear together (potential cascading failures).

## Integration Examples

### Splunk Query

```bash
# Pre-filter Splunk export before analysis
splunk search 'index=production level=ERROR' -output csv | \
    uniqseq --skip-chars 24 --window-size 1 | \
    less
```

### Datadog Logs

```bash
# Analyze Datadog log export
datadog logs tail --service=api --level=ERROR | \
    uniqseq --skip-chars 24 --window-size 1
```

### ELK Stack

```bash
# Deduplicate Elasticsearch query results
curl -s "http://elk:9200/logs/_search" -d '...' | \
    jq -r '.hits.hits[]._source.message' | \
    grep ERROR | \
    uniqseq --skip-chars 24 --window-size 1
```

## See Also

- [Skip Chars](../../features/skip-chars/skip-chars.md) - Ignoring timestamp prefixes
- [Pattern Filtering](../../features/pattern-filtering/pattern-filtering.md) - Track/bypass patterns
- [Library Mode](../../features/library-dir/library-dir.md) - Saving error pattern signatures
- [Inverse Mode](../../features/inverse/inverse.md) - Showing only duplicates for frequency analysis
