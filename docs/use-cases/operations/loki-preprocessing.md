# Operations: Log Ingestion Preprocessing

Reduce log storage costs and improve query performance by deduplicating logs before sending to Loki, Elasticsearch, or other centralized logging systems.

## The Problem

Centralized logging systems charge based on ingestion volume:

- **Storage costs** - Duplicate logs waste expensive storage
- **Query performance** - Larger indices slow down searches
- **Retention limits** - Duplicates fill retention windows faster
- **Network bandwidth** - Shipping duplicate logs wastes bandwidth

**Typical savings**: 50-90% reduction in log volume for verbose applications.

## Input Data

???+ note "app-verbose.log"
    ```text hl_lines="2 5 9 3 6 10 4 7"
    --8<-- "use-cases/operations/fixtures/app-verbose.log"
    ```

    A verbose application log with **10 entries**:

    - "Database connection failed" (lines 2, 5, 9) - appears 3×
    - "Retrying database connection" (lines 3, 6, 10) - appears 3×
    - "Request queued for retry" (lines 4, 7) - appears 2×

## Output Data

???+ success "expected-loki-input.log"
    ```text
    --8<-- "use-cases/operations/fixtures/expected-loki-input.log"
    ```

    **Result**: 5 duplicate entries removed → **50% reduction** in ingestion volume

## Solution

=== "CLI (Streaming)"

    <!-- verify-file: output.log expected: expected-loki-input.log -->
    ```console
    $ cat app-verbose.log | \
        uniqseq --skip-chars 20 --window-size 1 --quiet > output.log
    ```

    **How it works:**

    1. `cat` - Stream log file (in production, use `tail -f` for live logs)
    2. `uniqseq` - Deduplicate in real-time
    3. Output can be piped to promtail, filebeat, or other log shippers

=== "CLI (Batch)"

    <!-- verify-file: output.log expected: expected-loki-input.log -->
    ```console
    $ uniqseq app-verbose.log \
        --skip-chars 20 \
        --window-size 1 \
        --quiet > output.log
    ```

    Process log files in batches before ingestion with filebeat or other shippers.

=== "Python"

    <!-- verify-file: output.log expected: expected-loki-input.log -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        skip_chars=20,  # (1)!
        window_size=1,  # (2)!
    )

    # Stream processing for log shipper
    with open("app-verbose.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Skip 20-character timestamp prefix
    2. Deduplicate individual log lines

## How It Works

Before sending logs to your centralized logging system, uniqseq removes duplicate entries while preserving timestamps:

```text
Before (10 lines → Loki):
2024-01-15 10:30:02 ERROR Database connection failed...
2024-01-15 10:30:05 ERROR Database connection failed...  ← duplicate
2024-01-15 10:30:09 ERROR Database connection failed...  ← duplicate

After (5 lines → Loki):
2024-01-15 10:30:02 ERROR Database connection failed...
(2 duplicates removed, saving storage and bandwidth)
```

## Real-World Integration

### Loki with Promtail

Stream logs through uniqseq before Promtail ingests them:

```bash
# In systemd service or Docker container
tail -f /var/log/app.log | \
    uniqseq --skip-chars 20 --window-size 1 | \
    promtail --config /etc/promtail/config.yml
```

**Promtail config** (`promtail.yml`):
```yaml
clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: deduplicated-logs
    stdin:
      use_incoming_timestamp: true
```

### Elasticsearch with Filebeat

Deduplicate log files before Filebeat processes them:

```bash
#!/bin/bash
# Preprocessing script run by cron
for logfile in /var/log/app/*.log; do
    uniqseq "$logfile" --skip-chars 20 --window-size 1 > "${logfile}.deduped"
done

# Filebeat picks up *.deduped files
filebeat -c /etc/filebeat/filebeat.yml
```

**Filebeat config** (`filebeat.yml`):
```yaml
filebeat.inputs:
  - type: log
    paths:
      - /var/log/app/*.deduped
    fields:
      preprocessed: true
```

### Fluentd Pipeline

Integrate uniqseq as a preprocessing filter:

```bash
# Fluentd exec input
<source>
  @type exec
  command tail -f /var/log/app.log | uniqseq --skip-chars 20 --window-size 1
  format json
  tag app.deduped
</source>

<match app.deduped>
  @type elasticsearch
  host elasticsearch.internal
  index_name app-logs-deduped
</match>
```

## Cost Analysis

### Storage Savings

**Before deduplication:**
```bash
$ wc -c < app-verbose.log
500000000  # 500 MB/day
```

**After deduplication:**
```bash
$ uniqseq app-verbose.log --skip-chars 20 --window-size 1 | wc -c
150000000  # 150 MB/day → 70% reduction
```

**Annual savings** (at $0.10/GB/month):
- Before: 182.5 GB/year × $0.10 = $18.25/month
- After: 54.75 GB/year × $0.10 = $5.48/month
- **Savings: $12.77/month per application**

### Query Performance

Smaller indices mean faster queries:

```bash
# Loki query with duplicates: 10M entries
# Query time: 5-10 seconds

# Loki query without duplicates: 3M entries
# Query time: 1-2 seconds
```

## Advanced Workflows

### Multi-Stage Deduplication

Combine with other preprocessing:

```bash
# Stage 1: Remove debug logs
grep -v DEBUG app.log | \
# Stage 2: Deduplicate
    uniqseq --skip-chars 20 --window-size 1 | \
# Stage 3: Send to Loki
    promtail --config promtail.yml
```

### Application-Specific Normalization

Normalize application-specific fields before deduplication:

```bash
# Remove request IDs before deduplicating
uniqseq app.log \
    --hash-transform 'sed -E "s/req-[a-z0-9]+/REQ/g"' \
    --skip-chars 20 \
    --window-size 1 | \
    promtail --config promtail.yml
```

### Per-Service Deduplication

Deduplicate each microservice separately:

```bash
#!/bin/bash
for service in auth api gateway; do
    tail -f /var/log/${service}.log | \
        uniqseq --skip-chars 20 --window-size 1 | \
        promtail --config ${service}-promtail.yml &
done
```

## Monitoring Deduplication

Track reduction metrics:

```bash
#!/bin/bash
# Log preprocessing metrics
ORIGINAL=$(wc -l < app.log)
uniqseq app.log --skip-chars 20 --window-size 1 > deduped.log
DEDUPED=$(wc -l < deduped.log)
REDUCTION=$(( 100 - (DEDUPED * 100 / ORIGINAL) ))

echo "Log reduction: ${REDUCTION}% (${ORIGINAL} → ${DEDUPED} lines)"

# Send to Prometheus/Grafana
echo "log_reduction_percent{app=\"myapp\"} ${REDUCTION}" | \
    curl --data-binary @- http://pushgateway:9091/metrics/job/log_preprocessing
```

## When to Use This

**Good candidates for preprocessing:**
- ✅ Verbose applications with retry logic
- ✅ High-frequency logging (>1000 lines/second)
- ✅ Expensive log retention (Splunk, Datadog, etc.)
- ✅ Bandwidth-constrained environments

**Not recommended:**
- ❌ Low-volume logs (<100 MB/day)
- ❌ Logs where every entry is unique
- ❌ Compliance/audit logs requiring complete history
- ❌ Real-time alerting on duplicate detection

## See Also

- [Skip Chars](../../features/skip-chars/skip-chars.md) - Ignoring timestamp prefixes
- [Hash Transform](../../features/hash-transform/hash-transform.md) - Normalizing before deduplication
- [Statistics](../../features/stats/stats.md) - Measuring deduplication effectiveness
