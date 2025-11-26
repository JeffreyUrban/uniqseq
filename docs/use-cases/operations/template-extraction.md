# Operations: Log Template Extraction

Extract log message templates by normalizing variable parameters, enabling pattern discovery and integration with log analysis tools like Drain3, Spell, or LogPAI.

## The Problem

Application logs contain repeated message templates with varying parameters:

- **High cardinality** - Thousands of unique messages with same structure
- **Hard to analyze** - Variable data obscures common patterns
- **Poor aggregation** - Can't group by message type
- **Template extraction is slow** - ML-based tools require significant computation

**Preprocessing with normalization** dramatically reduces log cardinality and speeds up template extraction.

## Input Data

???+ note "varied-logs.txt"
    ```text hl_lines="1 2 4 7 11 3 5 9 15 6 8 10 13 12 14"
    --8<-- "use-cases/operations/fixtures/varied-logs.txt"
    ```

    Application log with **15 entries** across **4 template patterns**:

    - "User X logged in from Y" (5 instances, different users/IPs)
    - "Failed to connect to database server X" (3 instances, different servers)
    - "Processing request X for user Y took Zms" (4 instances, different IDs/users/times)
    - "Cache miss for key X" (2 instances, different keys)

## Output Data

???+ success "expected-templates.txt"
    ```text
    --8<-- "use-cases/operations/fixtures/expected-templates.txt"
    ```

    **Result**: **4 unique templates** (15 → 4 lines, 73% reduction)

    Variable parameters replaced with placeholders:
    - `<USER>` - Username
    - `<IP>` - IP address
    - `<ID>` - Request ID
    - `<TIME>` - Timing value
    - `<N>` - Server number

## Solution

=== "CLI (External Normalization)"

    <!-- verify-file: output.txt expected: expected-templates.txt -->
    <!-- termynal -->
    ```console
    $ cat varied-logs.txt | \
        sed -E 's/(user |User )[a-z]+/\1<USER>/g; \
                s/from [0-9.]+/from <IP>/g; \
                s/req-[a-z0-9]+/req-<ID>/g; \
                s/took [0-9]+ms/took <TIME>ms/g; \
                s/db-prod-[0-9]+/db-prod-<N>/g; \
                s/user:[a-z]+/user:<USER>/g' | \
        uniqseq --skip-chars 20 --window-size 1 --quiet > templates.txt
    ```

    **Pipeline stages:**

    1. `sed` - Normalize variable parameters to placeholders
    2. `uniqseq` - Deduplicate to extract unique templates
    3. Output contains one instance of each template

=== "CLI (Hash Transform)"

    <!-- verify-file: output.txt expected: expected-templates.txt -->
    ```console
    $ uniqseq varied-logs.txt \
        --skip-chars 20 \
        --hash-transform 'sed -E "s/(user |User )[a-z]+/\1<USER>/g; \
                                   s/from [0-9.]+/from <IP>/g; \
                                   s/req-[a-z0-9]+/req-<ID>/g; \
                                   s/took [0-9]+ms/took <TIME>ms/g; \
                                   s/db-prod-[0-9]+/db-prod-<N>/g; \
                                   s/user:[a-z]+/user:<USER>/g"' \
        --window-size 1 \
        --quiet > grouped-by-template.log
    ```

    **Options:**

    - `--hash-transform`: Normalize before comparing (groups similar logs)
    - Original log lines are preserved in output
    - Deduplication happens on normalized version

=== "Python"

    <!-- verify-file: output.log expected: expected-templates.txt -->
    ```python
    import re
    from uniqseq import UniqSeq

    def normalize_log(line):
        """Normalize variable parameters to placeholders"""
        line = re.sub(r'(user |User )[a-z]+', r'\1<USER>', line)
        line = re.sub(r'from [0-9.]+', 'from <IP>', line)
        line = re.sub(r'req-[a-z0-9]+', 'req-<ID>', line)
        line = re.sub(r'took [0-9]+ms', 'took <TIME>ms', line)
        line = re.sub(r'db-prod-[0-9]+', 'db-prod-<N>', line)
        line = re.sub(r'user:[a-z]+', 'user:<USER>', line)
        return line

    uniqseq = UniqSeq(
        skip_chars=20,    # (1)!
        window_size=1,    # (2)!
    )

    with open("varied-logs.txt") as f:
        with open("output.log", "w") as out:
            for line in f:
                line_clean = line.rstrip("\n")
                normalized = normalize_log(line_clean)  # (3)!
                # Process normalized line, deduplication happens automatically
                uniqseq.process_line(normalized, out)
            uniqseq.flush(out)
    ```

    1. Skip 20-character timestamp prefix
    2. Deduplicate individual log lines
    3. Normalize before checking for duplicates

## How It Works

Normalization converts variable data to placeholders, revealing underlying templates:

```text
Before normalization (15 unique lines):
User alice logged in from 192.168.1.100
User bob logged in from 192.168.1.101
User charlie logged in from 192.168.1.102
User dave logged in from 192.168.1.103
User eve logged in from 192.168.1.104
...

After normalization (1 template):
User <USER> logged in from <IP>
```

## Real-World Workflows

### Discover Log Templates

Extract all unique log message patterns:

```bash
#!/bin/bash
# Extract templates from application logs

cat /var/log/app.log | \
# Normalize common variable patterns
    sed -E 's/[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/<IP>/g; \
            s/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z/<TIMESTAMP>/g; \
            s/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}/\
[a-f0-9]{4}-[a-f0-9]{12}/<UUID>/g; \
            s/(user|User|USER)[:=][a-zA-Z0-9]+/\1:<USER>/g; \
            s/[0-9]+ ms/<TIME>ms/g' | \
# Deduplicate to get unique templates
    uniqseq --skip-chars 20 --window-size 1 --quiet > templates.txt

# Count how many templates exist
echo "Discovered $(wc -l < templates.txt) unique log templates"
```

### Frequency Analysis

Rank templates by occurrence:

```bash
# Normalize, count occurrences, sort by frequency
cat /var/log/app.log | \
    sed -E 's/<normalization-pattern>/<PLACEHOLDER>/g' | \
    uniqseq --skip-chars 20 --window-size 1 --inverse | \
    sort | \
    uniq -c | \
    sort -rn | \
    head -10
```

Output:
```text
1250 [INFO] User <USER> logged in from <IP>
  890 [ERROR] Failed to connect to database server db-prod-<N> on port 5432
  567 [INFO] Processing request req-<ID> for user <USER> took <TIME>ms
  123 [WARN] Cache miss for key user:<USER>:profile
  ...
```

### Integration with Drain3

Drain3 is an ML-based log template extraction tool. Preprocessing with uniqseq speeds it up:

<!-- skip: next -->
```python
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
import re

# Step 1: Pre-normalize obvious patterns
def pre_normalize(line):
    line = re.sub(r'\b\d{1,3}(\.\d{1,3}){3}\b', '<IP>', line)
    line = re.sub(r'\b[a-f0-9]{32}\b', '<HASH>', line)
    line = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', '<TIMESTAMP>', line)
    return line

# Step 2: Feed to Drain3 (now processes faster with less cardinality)
config = TemplateMinerConfig()
template_miner = TemplateMiner(config=config)

with open("/var/log/app.log") as f:
    for line in f:
        normalized = pre_normalize(line)
        result = template_miner.add_log_message(normalized)

# Print discovered templates
for template in template_miner.drain.clusters:
    print(f"{template.size:6d} occurrences: {template.get_template()}")
```

### Generate Template Catalog

Build a catalog of all application log templates:

```bash
#!/bin/bash
# Create comprehensive template catalog

echo "# Application Log Templates" > catalog.md
echo "" >> catalog.md
echo "Generated: $(date)" >> catalog.md
echo "" >> catalog.md

# Process each log level separately
for level in INFO WARN ERROR CRITICAL; do
    echo "## $level Messages" >> catalog.md
    echo "" >> catalog.md

    grep "\\[$level\\]" /var/log/app.log | \
        sed -E 's/<normalization>/<PLACEHOLDER>/g' | \
        uniqseq --skip-chars 20 --window-size 1 --quiet | \
        sed 's/^/- /' >> catalog.md

    echo "" >> catalog.md
done
```

Output (`catalog.md`):
```markdown
# Application Log Templates

Generated: 2024-01-15 10:00:00

## INFO Messages

- User <USER> logged in from <IP>
- Processing request req-<ID> for user <USER> took <TIME>ms
...

## ERROR Messages

- Failed to connect to database server db-prod-<N> on port 5432
...
```

### Compare Template Changes

Detect new log templates introduced by code changes:

```bash
#!/bin/bash
# Compare templates before and after deployment

# Extract baseline templates
cat logs-before-deploy.log | \
    sed -E 's/<normalization>/<PLACEHOLDER>/g' | \
    uniqseq --skip-chars 20 --window-size 1 \
        --library-dir ./baseline-templates --quiet > /dev/null

# Find new templates after deployment
cat logs-after-deploy.log | \
    sed -E 's/<normalization>/<PLACEHOLDER>/g' | \
    uniqseq --skip-chars 20 --window-size 1 \
        --read-sequences ./baseline-templates \
        --annotate | \
    grep -v "DUPLICATE" | \
    grep "^2024" > new-templates.txt

echo "New log templates introduced:"
cat new-templates.txt
```

### Anomaly Detection

Use template frequency changes to detect anomalies:

```bash
#!/bin/bash
# Compare template frequencies week-over-week

# Week 1 template counts
cat week1.log | \
    sed -E 's/<normalization>/<PLACEHOLDER>/g' | \
    sort | uniq -c > week1-counts.txt

# Week 2 template counts
cat week2.log | \
    sed -E 's/<normalization>/<PLACEHOLDER>/g' | \
    sort | uniq -c > week2-counts.txt

# Find templates with significant frequency increase
join week1-counts.txt week2-counts.txt | \
    awk '{
        increase = ($2 - $1) / $1 * 100
        if (increase > 50) print increase "% increase:", $3
    }' | \
    sort -rn
```

## Advanced Patterns

### Multi-Stage Normalization

Different normalization strategies for different log sections:

```bash
# Stage 1: Normalize timestamps and IDs
cat app.log | \
    sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z/<TS>/g; \
            s/[a-f0-9]{8}-[a-f0-9]{4}/<ID>/g' | \
# Stage 2: Normalize numeric values
    sed -E 's/[0-9]+ (ms|MB|requests)/<NUM> \1/g' | \
# Stage 3: Deduplicate
    uniqseq --skip-chars 20 --window-size 1 --quiet
```

### Hierarchical Templates

Extract templates at different specificity levels:

```bash
# High specificity (preserve more detail)
cat app.log | \
    sed -E 's/[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/<IP>/g' | \
    uniqseq --skip-chars 20 --window-size 1 --quiet > templates-specific.txt

# Low specificity (more aggressive normalization)
cat app.log | \
    sed -E 's/[0-9]+/<NUM>/g; s/[a-z]+/<WORD>/g' | \
    uniqseq --skip-chars 20 --window-size 1 --quiet > templates-general.txt
```

### Template-Based Filtering

Use extracted templates to filter logs:

```bash
# Extract error templates
grep ERROR app.log | \
    sed -E 's/<normalization>/<PLACEHOLDER>/g' | \
    uniqseq --skip-chars 20 --window-size 1 \
        --library-dir ./error-templates --quiet > /dev/null

# Filter production logs for known error templates
uniqseq production.log --skip-chars 20 --window-size 1 \
    --read-sequences ./error-templates \
    --track 'ERROR' | \
    grep -v "NEW PATTERN"
```

Shows only errors matching known templates (filters out new errors).

### Generate Regex Patterns

Convert templates to regex for monitoring:

<!-- skip: next -->
```python
import re

# Read templates
with open("templates.txt") as f:
    templates = f.readlines()

# Convert placeholders to regex
for template in templates:
    regex = template
    regex = re.sub(r'<USER>', r'[a-zA-Z0-9]+', regex)
    regex = re.sub(r'<IP>', r'\\d{1,3}(\\.\\d{1,3}){3}', regex)
    regex = re.sub(r'<ID>', r'[a-f0-9-]+', regex)
    regex = re.sub(r'<TIME>', r'\\d+', regex)

    print(f"Template: {template.strip()}")
    print(f"Regex:    {regex}")
    print()
```

Use these regex patterns in monitoring tools like Grafana, Datadog, or Splunk.

## Integration Examples

### Elasticsearch Mapping

```bash
# Extract templates for Elasticsearch field mapping
cat app.log | \
    sed -E 's/<normalization>/<PLACEHOLDER>/g' | \
    uniqseq --skip-chars 20 --window-size 1 --quiet | \
    jq -R '{template: .}' | \
    jq -s '{templates: .}'
```

### Prometheus Alert Rules

```yaml
# Generate alert rules from templates
groups:
  - name: log_patterns
    rules:
      - alert: NewLogTemplate
        expr: |
          log_template_count{template="User <USER> failed login"} > 100
        annotations:
          summary: High occurrence of login failures
```

### LogPAI Integration

<!-- skip: next -->
```python
from logpai.logparser import Drain

# Pre-normalize logs
with open("app.log") as f, open("normalized.log", "w") as out:
    for line in f:
        normalized = pre_normalize(line)
        out.write(normalized + "\n")

# Run Drain parser on pre-normalized logs (faster convergence)
parser = Drain.LogParser(log_format='<Time> <Level> <Content>')
parser.parse("normalized.log")
```

## Performance Benefits

### Reduced Cardinality

```bash
# Before normalization
$ cat app.log | wc -l
1,000,000 lines

$ cat app.log | sort | uniq | wc -l
850,000 unique lines (85% cardinality)

# After normalization
$ cat app.log | sed -E 's/<normalization>/<PLACEHOLDER>/g' | \
    uniqseq --skip-chars 20 --quiet | wc -l
1,200 unique templates (0.12% cardinality)
```

**99.88% reduction in cardinality** for ML-based template extraction.

### Faster Template Mining

```bash
# Without preprocessing
$ time drain3-mine app.log
real    15m23s

# With uniqseq preprocessing
$ cat app.log | sed -E 's/<normalization>/<PLACEHOLDER>/g' > normalized.log
$ time drain3-mine normalized.log
real    2m15s  # 6.8× faster
```

## Common Normalization Patterns

| Pattern | Regex | Example |
|---------|-------|---------|
| IP Address | `\d{1,3}(\.\d{1,3}){3}` | `192.168.1.1` → `<IP>` |
| UUID | `[a-f0-9]{8}-[a-f0-9]{4}...` | `550e8400-e29b-...` → `<UUID>` |
| Timestamp (ISO) | `\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}` | `2024-01-15T10:00:00` → `<TS>` |
| Numbers | `\d+` | `12345` → `<NUM>` |
| Hex Hash | `[a-f0-9]{32,64}` | `a3b5c7d9...` → `<HASH>` |
| Email | `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+` | `user@example.com` → `<EMAIL>` |
| URL | `https?://[^\s]+` | `https://api.example.com/...` → `<URL>` |

## When to Use This

**Good for:**
- ✅ High-cardinality log analysis
- ✅ Template discovery and cataloging
- ✅ Pre-processing for ML-based log mining
- ✅ Anomaly detection (new template patterns)
- ✅ Log message standardization

**Not ideal for:**
- ❌ Logs already using structured logging (JSON)
- ❌ Low-volume logs (<1000 lines/day)
- ❌ Logs with no repeated patterns
- ❌ Real-time streaming (batch processing more effective)

## See Also

- [Hash Transform](../../features/hash-transform/hash-transform.md) - Normalization before deduplication
- [Library Mode](../../features/library-dir/library-dir.md) - Saving template patterns
- [Pattern Filtering](../../features/pattern-filtering/pattern-filtering.md) - Filtering by template
- [Log Normalization](../data-processing/log-normalization.md) - Multi-step normalization workflows
