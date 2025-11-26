# Data Processing: Log Normalization

Normalize log entries by removing timestamps, IDs, and normalizing whitespace before deduplication. Find truly unique messages despite formatting variations.

## The Problem

Application logs often have the same message repeated with variations:

- **Timestamps differ** - Same error at different times
- **Request IDs differ** - Unique IDs make every line look different
- **Whitespace varies** - Inconsistent spacing in log messages
- **UUIDs and session IDs** - Obscure duplicate patterns

These variations prevent traditional line-based deduplication from working.

## Input Data

???+ note "request.log"
    ```text hl_lines="1 3 2 4 6"
    --8<-- "use-cases/data-processing/fixtures/request.log"
    ```

    The log contains **6 entries**, but only **3 unique messages**:

    - "Processing payment" (lines 1, 3) - different timestamps/request IDs
    - "Payment gateway timeout" (lines 2, 4, 6) - different whitespace & IDs
    - "Retry attempt 1" (line 5) - unique

## Output Data

???+ success "expected-normalized.log"
    ```text
    --8<-- "use-cases/data-processing/fixtures/expected-normalized.log"
    ```

    **Result**: 3 duplicate entries removed → 3 unique messages

## Solution

=== "CLI"

    <!-- verify-file: output.log expected: expected-normalized.log -->
    <!-- termynal -->
    ```console
    $ uniqseq request.log \
        --hash-transform "sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z//g' | \
                          sed -E 's/req-[a-z0-9]+//g' | \
                          tr -s ' '" \
        --window-size 1 \
        --quiet > output.log
    ```

    **How it works:**

    1. Remove ISO timestamps: `sed -E 's/[0-9]{4}-.../g'`
    2. Remove request IDs: `sed -E 's/req-[a-z0-9]+//g'`
    3. Normalize whitespace: `tr -s ' '` (squeeze multiple spaces to one)

=== "Python"

    <!-- verify-file: output.log expected: expected-normalized.log -->
    ```python
    import re
    from uniqseq import UniqSeq

    def normalize_log(line):
        # Remove ISO timestamp
        line = re.sub(r'\d{4}-\d{2}-\d{2}T[\d:.]+Z', '', line)
        # Remove request IDs
        line = re.sub(r'req-[a-z0-9]+', '', line)
        # Normalize whitespace
        line = ' '.join(line.split())
        return line

    uniqseq = UniqSeq(
        hash_transform=normalize_log,  # (1)!
        window_size=1,  # (2)!
    )

    with open("request.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Python lambda for multi-step normalization
    2. Deduplicate individual lines

## How It Works

The `--hash-transform` normalizes each line before hashing, but preserves the original line in output:

```text
Original:
2024-01-15T10:30:02.456Z | req-d4e5f6 | ERROR | Payment   gateway   timeout

After normalization (for hashing):
|  | ERROR | Payment gateway timeout
     ↓ (timestamps/IDs removed, whitespace normalized)

Output (original preserved):
2024-01-15T10:30:02.456Z | req-d4e5f6 | ERROR | Payment   gateway   timeout
```

Lines with identical normalized content are considered duplicates.

### Multi-Step Transformation

Complex normalizations combine multiple steps:

1. **Remove timestamps**: Strip ISO 8601 timestamps
2. **Remove IDs**: Strip request/session/trace IDs
3. **Normalize whitespace**: Convert multiple spaces to single space

## Real-World Workflows

### Remove All Variable Data

Normalize timestamps, IDs, IP addresses, and numbers:

```bash
uniqseq app.log \
    --hash-transform \
        "sed -E 's/[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/IP/g' | \
         sed -E 's/[0-9]+/NUM/g' | \
         tr -s ' '" \
    --window-size 1 > normalized.log
```

### Case-Insensitive + Normalization

Combine case conversion with other normalizations:

```bash
uniqseq app.log \
    --hash-transform "tr '[:upper:]' '[:lower:]' | \
                      sed -E 's/user-[0-9]+/USER/g' | \
                      tr -s ' '" \
    --window-size 1 > output.log
```

### Extract Error Patterns

Remove context to find error message patterns:

```bash
# Keep only the error message part (field 4)
uniqseq app.log \
    --hash-transform "awk -F'|' '{print \$4}' | tr -s ' '" \
    --window-size 1 > error-patterns.log
```

### Production Log Analysis

Analyze production logs with high cardinality IDs:

```bash
# Remove UUIDs, session IDs, timestamps
uniqseq production.log \
    --hash-transform \
        "sed -E 's/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-\
[a-f0-9]{4}-[a-f0-9]{12}//g' | \
         sed -E 's/session_[a-zA-Z0-9]+//g' | \
         sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}//g' | \
         tr -s ' '" \
    --window-size 1 \
    --annotate > unique-errors.log
```

The `--annotate` flag shows how many times each pattern appeared.

## Performance Considerations

Hash transforms run a subprocess for each line. For large files:

**Optimize the pipeline**:
```bash
# Slower: Complex regex
--hash-transform "sed -E 's/very-complex-pattern//g'"

# Faster: Simple patterns
--hash-transform "sed 's/simple-string//g'"

# Faster: Multiple simple sed commands
--hash-transform "sed 's/foo//g' | sed 's/bar//g'"
```

**Consider preprocessing**:
```bash
# For very large files, preprocess once outside uniqseq
sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[\d:.]+Z//g' huge.log | \
    uniqseq --window-size 1
```

## Common Normalization Patterns

```bash
# Remove ISO timestamps
sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z//g'

# Remove UUIDs
sed -E 's/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}//g'

# Remove IP addresses
sed -E 's/[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}//g'

# Remove all numbers
sed 's/[0-9]\+//g'

# Normalize whitespace
tr -s ' '

# Case-insensitive
tr '[:upper:]' '[:lower:]'

# Remove email addresses
sed -E 's/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}//g'
```

## See Also

- [Hash Transform](../../features/hash-transform/hash-transform.md) - Detailed hash transform documentation
- [Field Extraction](field-extraction.md) - Extract specific fields
- [Skip Chars](../../features/skip-chars/skip-chars.md) - Skip fixed-width prefixes
