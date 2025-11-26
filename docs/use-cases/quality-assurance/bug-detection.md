# Quality Assurance: Finding Frequently Repeated Errors

Identify potential bugs by finding which errors repeat most often in test runs or production logs. Frequent repetition often indicates underlying issues.

## The Problem

When analyzing test failures or production errors:

- **Hard to spot patterns** - Same errors buried in output
- **Can't prioritize fixes** - Don't know which errors are most common
- **Miss systemic issues** - Repeated errors indicate root cause problems
- **Waste QA time** - Investigating same error multiple times

## Input Data

???+ note "test-failures.log"
    ```text hl_lines="1 3 5 8 10 2 6 9 4 7"
    --8<-- "use-cases/quality-assurance/fixtures/test-failures.log"
    ```

    Test failure log with **10 failures** across 3 different tests:

    - `test_database_connection` (lines 1, 3, 5, 8, 10) - fails **5 times**
    - `test_api_timeout` (lines 2, 6, 9) - fails **3 times**
    - `test_user_authentication` (lines 4, 7) - fails **2 times**

## Output Data

???+ success "expected-annotated.log"
    ```text hl_lines="3-5 7-8 10"
    --8<-- "use-cases/quality-assurance/fixtures/expected-annotated.log"
    ```

    **Annotations show repeat counts:**
    - Line 5: "seen 2 times" → `test_database_connection` failed 3× total
    - Line 8: "seen 3 times" → `test_database_connection` failed 4× total
    - Line 10: Last occurrence (5× total)

## Solution

=== "CLI"

    <!-- verify-file: output.log expected: expected-annotated.log -->
    <!-- termynal -->
    ```console
    $ uniqseq test-failures.log \
        --window-size 1 \
        --skip-chars 13 \
        --annotate \
        --quiet > annotated.log
    ```

    **Options:**

    - `--window-size 1`: Deduplicate individual test failures
    - `--skip-chars 13`: Skip "Test run X: " prefix
    - `--annotate`: Add markers showing duplicate counts

=== "Python"

    <!-- verify-file: output.log expected: expected-annotated.log -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=1,    # (1)!
        skip_chars=13,    # (2)!
        annotate=True,    # (3)!
    )

    with open("test-failures.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Deduplicate individual lines
    2. Skip "Test run X: " prefix when comparing
    3. Add annotation markers for duplicates

## How It Works

Annotations show where duplicates were skipped and how many times each pattern has been seen:

```text
Test run 1: ERROR: test_database_connection failed...
Test run 3: ERROR: test_database_connection failed...  ← removed
  [DUPLICATE: Lines 3-3 matched lines 1-1 (sequence seen 1 times)]

Test run 5: ERROR: test_database_connection failed...  ← removed
  [DUPLICATE: Lines 5-5 matched lines 1-1 (sequence seen 2 times)]
```

The "seen N times" count increments each time the pattern repeats, helping identify the most frequent failures.

## Analyzing Repeat Frequency

### Extract Annotation Counts

Find the highest repeat counts:

```bash
uniqseq test-failures.log --skip-chars 13 --annotate --quiet | \
    grep "DUPLICATE" | \
    grep -oE "seen [0-9]+ times" | \
    awk '{print $2}' | \
    sort -rn | \
    head -1
```

Output: `3` (meaning one error appeared 4 times total: original + seen 3 times)

### Rank Errors by Frequency

Combine with custom annotation format to extract failure names and counts:

```bash
# Extract duplicates and their counts
uniqseq test-failures.log --skip-chars 13 --annotate \
    --annotation-format 'SKIP|{count}' --quiet | \
    grep 'SKIP|' | \
    awk -F'|' '{print $2}' | \
    sort | \
    uniq -c | \
    sort -rn
```

Output:
```text
3 3    # test_database_connection appeared 4 times (3 duplicates)
2 2    # test_api_timeout appeared 3 times (2 duplicates)
1 1    # test_user_authentication appeared 2 times (1 duplicate)
```

### Find Most Critical Bugs

Show errors ordered by frequency:

```bash
#!/bin/bash
# Extract unique errors with their total occurrence count

uniqseq test-failures.log --skip-chars 13 --annotate --quiet | \
    grep -E "ERROR:|DUPLICATE" | \
    while read line; do
        if [[ $line == *"ERROR:"* ]]; then
            ERROR=$line
        elif [[ $line == *"seen"* ]]; then
            COUNT=$(echo $line | grep -oE "seen [0-9]+" | awk '{print $2+1}')
            echo "$COUNT|$ERROR"
        fi
    done | \
    sort -rn -t'|' -k1 | \
    head -5
```

Shows top 5 most frequent errors with their counts.

## Real-World Workflows

### CI/CD Integration

Identify flaky tests in CI:

```bash
#!/bin/bash
# Run in CI pipeline after tests

uniqseq test-output.log --skip-chars 20 --annotate --quiet > annotated.log

# Count failures that appeared more than 3 times
FLAKY=$(grep "DUPLICATE" annotated.log | \
    grep -E "seen [3-9]|seen [0-9]{2}" | wc -l)

if [ $FLAKY -gt 0 ]; then
    echo "WARNING: $FLAKY flaky tests detected"
    grep "DUPLICATE" annotated.log | grep -E "seen [3-9]"
    exit 1
fi
```

### Production Error Triage

Prioritize error investigation:

```bash
# Analyze production errors from last hour
uniqseq /var/log/app-errors.log \
    --skip-chars 20 \
    --annotate \
    --annotation-format 'REPEAT:{count}' | \
    grep 'REPEAT:' | \
    awk -F':' '{print $NF}' | \
    sort -rn | \
    head -1
```

Focus on the error with highest repeat count first.

### Weekly QA Report

Generate report of most common failures:

```bash
#!/bin/bash
# Weekly test failure summary

echo "Most Common Test Failures (Last 7 Days)"
echo "========================================"

cat test-runs/*.log | \
    uniqseq --skip-chars 13 --annotate --quiet | \
    grep "DUPLICATE" | \
    grep -oE "seen [0-9]+ times" | \
    awk '{sum += ($2 + 1)} END {print "Total failures:", sum}'

# Top 10 most repeated
cat test-runs/*.log | \
    uniqseq --skip-chars 13 --annotate --quiet | \
    grep -B1 "DUPLICATE" | \
    grep "ERROR:" | \
    sort | \
    uniq -c | \
    sort -rn | \
    head -10
```

### Correlation Analysis

Find errors that always occur together:

```bash
# Extract sequence patterns (window-size > 1)
uniqseq test-failures.log \
    --window-size 2 \
    --skip-chars 13 \
    --annotate | \
    grep -B2 "DUPLICATE" | \
    grep "ERROR:"
```

Shows which errors consistently appear together.

## Advanced: Custom Metrics

Export repeat counts to monitoring:

```bash
#!/bin/bash
# Push error frequency metrics to Prometheus

uniqseq /var/log/errors.log --skip-chars 20 --annotate --quiet | \
    grep "DUPLICATE" | \
    grep -oE "seen [0-9]+" | \
    awk '{
        counts[$2]++
    } END {
        for (count in counts) {
            print "error_repeat_count{frequency=\"" count "\"} " counts[count]
        }
    }' | \
    curl --data-binary @- http://pushgateway:9091/metrics/job/error_analysis
```

## See Also

- [Annotations](../../features/annotations/annotations.md) - Annotation formats and options
- [Skip Chars](../../features/skip-chars/skip-chars.md) - Ignoring variable prefixes
- [Inverse Mode](../../features/inverse/inverse.md) - Showing only duplicates
