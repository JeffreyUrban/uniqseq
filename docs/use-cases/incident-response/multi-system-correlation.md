# Incident Response: Multi-System Log Correlation

Correlate logs across multiple systems during incident response to identify which errors are widespread vs. environment-specific, helping prioritize remediation efforts.

## The Problem

During incidents, errors appear across multiple environments:

- **Hard to distinguish** - Which errors are prod-specific vs. widespread?
- **Redundant investigation** - Teams investigate same error in multiple environments
- **Poor prioritization** - Don't know which issues to fix first
- **Context missing** - Can't tell if dev errors are related to prod incident

## Input Data

???+ note "production.log"
    ```text hl_lines="3 5 6 7 8 9 10"
    --8<-- "use-cases/incident-response/fixtures/production.log"
    ```

    Production server log with **10 entries**, including errors:
    - Authentication service unreachable (4×)
    - User login failures (2×)
    - API gateway 503 error (1×)

???+ note "dev.log"
    ```text hl_lines="5 7 9 10 11 12 14"
    --8<-- "use-cases/incident-response/fixtures/dev.log"
    ```

    Development server log with **14 entries**, including:
    - Shared errors (also in production)
    - Dev-specific errors (configuration, environment)
    - Debug logging (not in production)

## Output Data

???+ success "expected-dev-only.log (Dev-Specific Errors)"
    ```text
    --8<-- "use-cases/incident-response/fixtures/expected-dev-only.log"
    ```

    **7 patterns unique to dev** (not seen in production):
    - Debug logging
    - Missing environment variables
    - Configuration validation errors
    - Hot reload warnings

???+ success "expected-common.log (Cross-Environment Errors)"
    ```text
    --8<-- "use-cases/incident-response/fixtures/expected-common.log"
    ```

    **5 patterns common to both** (production incident also affecting dev):
    - Authentication service unreachable
    - User login failures
    - Fallback to local cache

## Solution

=== "Extract Production Patterns"

    ```console
    $ uniqseq production.log \
        --skip-chars 20 \
        --window-size 1 \
        --library-dir ./prod-patterns \
        --quiet > /dev/null
    ```

    **Result**: Unique error patterns from production saved to `./prod-patterns`

=== "Find Dev-Only Issues"

    ```console
    $ uniqseq dev.log \
        --skip-chars 20 \
        --window-size 1 \
        --read-sequences ./prod-patterns \
        --annotate | \
        grep -v "DUPLICATE" | \
        grep "^2024" > dev-only.log
    ```

    **Result**: Errors in dev that were NOT seen in production

=== "Find Common Issues"

    <!-- skip: next -->
    ```console
    $ uniqseq dev.log \
        --skip-chars 20 \
        --window-size 1 \
        --read-sequences ./prod-patterns \
        --annotate | \
        grep "DUPLICATE" | \
        grep -v "^\[" > annotations.txt

    $ # Extract the line numbers and pull those lines from dev.log
    ```

    **Result**: Errors appearing in both environments

=== "Python Workflow"

    <!-- verify-file: output.log expected: expected-dev-only.log -->
    ```python
    from uniqseq import UniqSeq

    # Step 1: Extract unique production patterns into a set
    prod_patterns = set()
    prod_uniqseq = UniqSeq(
        skip_chars=20,
        window_size=1,
    )

    with open("production.log") as f:
        for line in f:
            # Capture each emitted line's hash (after skip_chars)
            line_stripped = line.rstrip("\n")
            # Compute hash of the relevant part (after skip_chars)
            import hashlib
            if len(line_stripped) > 20:
                relevant_part = line_stripped[20:]
            else:
                relevant_part = line_stripped
            line_hash = hashlib.md5(relevant_part.encode()).hexdigest()
            prod_patterns.add(line_hash)

    # Step 2: Process dev log, outputting only lines NOT in production
    with open("dev.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                line_stripped = line.rstrip("\n")
                # Compute hash of relevant part
                if len(line_stripped) > 20:
                    relevant_part = line_stripped[20:]
                else:
                    relevant_part = line_stripped
                line_hash = hashlib.md5(relevant_part.encode()).hexdigest()

                # Only output if this pattern was NOT in production
                if line_hash not in prod_patterns:
                    out.write(line_stripped + '\n')
    ```

## How It Works

Pattern libraries enable cross-system correlation:

```text
Step 1: Extract production patterns
production.log → uniqseq → ./prod-patterns/
  - Authentication service unreachable
  - User login failed
  - API gateway 503
  - Falling back to local cache
  - (6 total unique patterns)

Step 2: Compare dev against production patterns
dev.log + ./prod-patterns → identify dev-only issues

Patterns in both:
  ✓ Authentication service unreachable
  ✓ User login failed
  ✓ Falling back to local cache

Dev-only patterns:
  ! Loading development configuration
  ! Mock authentication service enabled
  ! Missing environment variable: STRIPE_API_KEY
  ! Configuration validation failed
  (7 total dev-specific issues)
```

## Real-World Workflows

### Incident Triage Workflow

```bash
#!/bin/bash
# Rapid incident correlation across environments

PROD_LOG="/var/log/production/app.log"
STAGE_LOG="/var/log/staging/app.log"
DEV_LOG="/var/log/dev/app.log"

# Extract production error patterns
echo "Extracting production error patterns..."
grep ERROR "$PROD_LOG" | \
    uniqseq --skip-chars 20 --window-size 1 \
        --library-dir ./prod-errors --quiet > /dev/null

# Check staging
echo "Checking staging environment..."
grep ERROR "$STAGE_LOG" | \
    uniqseq --skip-chars 20 --window-size 1 \
        --read-sequences ./prod-errors \
        --annotate | \
    grep -c "DUPLICATE" | \
    xargs -I {} echo "  Staging has {} errors also in production"

# Check dev
echo "Checking dev environment..."
grep ERROR "$DEV_LOG" | \
    uniqseq --skip-chars 20 --window-size 1 \
        --read-sequences ./prod-errors \
        --annotate | \
    grep -v "DUPLICATE" | \
    grep "^2024" | \
    wc -l | \
    xargs -I {} echo "  Dev has {} unique errors (not in production)"
```

Output:
```text
Extracting production error patterns...
Checking staging environment...
  Staging has 8 errors also in production
Checking dev environment...
  Dev has 7 unique errors (not in production)
```

**Conclusion**: Incident is affecting production and staging, but dev has separate issues.

### Multi-Region Correlation

```bash
#!/bin/bash
# Compare errors across geographic regions

# Extract US-East patterns
grep ERROR /var/log/us-east/app.log | \
    uniqseq --skip-chars 20 --window-size 1 \
        --library-dir ./us-east-patterns --quiet > /dev/null

# Compare other regions
for region in us-west eu-west ap-southeast; do
    echo "=== $region ==="
    grep ERROR /var/log/$region/app.log | \
        uniqseq --skip-chars 20 --window-size 1 \
            --read-sequences ./us-east-patterns \
            --annotate | \
        grep -v "DUPLICATE" | \
        grep "^2024" > ${region}-unique-errors.log

    echo "  Unique errors: $(wc -l < ${region}-unique-errors.log)"
done
```

Identifies region-specific issues vs. global outages.

### Service Dependency Analysis

```bash
#!/bin/bash
# Determine which service is the root cause

# Extract patterns from suspected root cause (auth service)
grep ERROR /var/log/auth-service.log | \
    uniqseq --skip-chars 20 --window-size 1 \
        --library-dir ./auth-errors --quiet > /dev/null

# Check which downstream services show the same errors
for service in api gateway worker; do
    echo "=== $service ==="
    grep ERROR /var/log/${service}.log | \
        uniqseq --skip-chars 20 --window-size 1 \
            --read-sequences ./auth-errors \
            --annotate | \
        grep "DUPLICATE" | \
        wc -l | \
        xargs -I {} echo "  {} errors correlate with auth service"
done
```

Output:
```text
=== api ===
  45 errors correlate with auth service
=== gateway ===
  67 errors correlate with auth service
=== worker ===
  0 errors correlate with auth service
```

**Conclusion**: Auth service is root cause, impacting API and Gateway but not Worker.

### Time-Window Correlation

```bash
#!/bin/bash
# Compare errors during specific incident window

INCIDENT_START="2024-01-15 14:30:00"
INCIDENT_END="2024-01-15 14:35:00"

# Extract production errors during incident
sed -n "/$INCIDENT_START/,/$INCIDENT_END/p" production.log | \
    grep ERROR | \
    uniqseq --skip-chars 20 --window-size 1 \
        --library-dir ./incident-patterns --quiet > /dev/null

# Check if dev showed same issues
echo "Dev environment during incident:"
sed -n "/$INCIDENT_START/,/$INCIDENT_END/p" dev.log | \
    grep ERROR | \
    uniqseq --skip-chars 20 --window-size 1 \
        --read-sequences ./incident-patterns \
        --annotate | \
    grep "DUPLICATE" | \
    wc -l | \
    xargs -I {} echo "  {} errors match production incident"
```

Helps determine if incident was environment-specific or systemic.

## Advanced Patterns

### Multi-Stage Filtering

```bash
# Stage 1: Extract critical production errors
grep -E "ERROR|CRITICAL" production.log | \
    grep -v "HealthCheck" | \
    uniqseq --skip-chars 20 --window-size 1 \
        --library-dir ./critical-prod --quiet > /dev/null

# Stage 2: Find matching errors in dev
grep -E "ERROR|CRITICAL" dev.log | \
    uniqseq --skip-chars 20 --window-size 1 \
        --read-sequences ./critical-prod \
        --annotate

# Stage 3: Alert if critical prod errors appear in dev
```

### Baseline Comparison

```bash
#!/bin/bash
# Compare current logs against known-good baseline

# Create baseline from last week (before incident)
uniqseq baseline-week.log --skip-chars 20 --window-size 1 \
    --library-dir ./known-good --quiet > /dev/null

# Compare current logs
uniqseq current.log --skip-chars 20 --window-size 1 \
    --read-sequences ./known-good \
    --annotate | \
    grep -v "DUPLICATE" | \
    grep "^2024" > new-error-patterns.log

# These are errors NOT seen in baseline
echo "New error patterns since baseline:"
cat new-error-patterns.log
```

### Normalize Before Comparison

```bash
# Remove variable data before correlation
uniqseq production.log \
    --hash-transform 'sed -E "s/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z//g"' \
    --skip-chars 20 \
    --window-size 1 \
    --library-dir ./prod-normalized --quiet > /dev/null

# Now dev comparison ignores timestamps
uniqseq dev.log \
    --hash-transform 'sed -E "s/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z//g"' \
    --skip-chars 20 \
    --window-size 1 \
    --read-sequences ./prod-normalized \
    --annotate
```

Groups errors with different timestamps but identical messages.

## Integration with Incident Response Tools

### PagerDuty Alert Correlation

```bash
#!/bin/bash
# Correlate PagerDuty alerts with log patterns

# Export PagerDuty incident logs
pd incident logs --id $INCIDENT_ID > pd-errors.log

# Extract patterns from production
uniqseq production.log --skip-chars 20 --window-size 1 \
    --library-dir ./prod-patterns --quiet > /dev/null

# Check which PagerDuty errors match production
uniqseq pd-errors.log --skip-chars 20 --window-size 1 \
    --read-sequences ./prod-patterns \
    --annotate | \
    grep "DUPLICATE" | \
    wc -l | \
    xargs -I {} echo "PagerDuty: {} alerts correlate with production logs"
```

### Slack Incident Channel

```bash
#!/bin/bash
# Post correlation results to Slack incident channel

DEV_UNIQUE=$(uniqseq dev.log --skip-chars 20 --window-size 1 \
    --read-sequences ./prod-patterns --annotate | \
    grep -v "DUPLICATE" | grep "^2024" | wc -l)

curl -X POST https://hooks.slack.com/... -d "{
  \"text\": \"🔍 Log Correlation Results\",
  \"attachments\": [{
    \"text\": \"Found $DEV_UNIQUE dev-specific errors not in production.\",
    \"color\": \"warning\"
  }]
}"
```

### Grafana Dashboard

```bash
# Generate metrics for Grafana
PROD_UNIQUE=$(uniqseq production.log --skip-chars 20 --stats-format json \
    --quiet 2>&1 | jq '.statistics.lines.emitted')

DEV_UNIQUE=$(uniqseq dev.log --skip-chars 20 --read-sequences ./prod-patterns \
    --annotate | grep -v "DUPLICATE" | grep "^2024" | wc -l)

# Push to Prometheus
PUSHGATEWAY="http://pushgateway:9091"
METRICS_JOB="metrics/job/log_correlation"
cat <<EOF | curl --data-binary @- ${PUSHGATEWAY}/${METRICS_JOB}
incident_unique_errors{env="production"} ${PROD_UNIQUE}
incident_unique_errors{env="dev"} ${DEV_UNIQUE}
incident_correlation_overlap{env="dev"} $((PROD_UNIQUE - DEV_UNIQUE))
EOF
```

## When to Use This

**Good for:**
- ✅ Multi-environment incident response
- ✅ Root cause analysis across services
- ✅ Determining blast radius of outages
- ✅ Prioritizing fixes (widespread vs. isolated)
- ✅ Baseline comparison (current vs. known-good)

**Not ideal for:**
- ❌ Single-environment debugging
- ❌ Real-time streaming (use direct filtering instead)
- ❌ Logs with no common patterns
- ❌ Highly variable error messages

## See Also

- [Library Mode](../../features/library-dir/library-dir.md) - Saving and loading pattern libraries
- [Read-Only Patterns](../../features/read-sequences/read-sequences.md) - Using saved patterns
- [Annotations](../../features/annotations/annotations.md) - Marking duplicate matches
- [Pattern Filtering](../../features/pattern-filtering/pattern-filtering.md) - Track/bypass patterns
