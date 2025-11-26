# Data Processing: Field-Based Deduplication

Deduplicate log lines based on specific fields while preserving the complete original lines in output. Useful when only certain fields matter for uniqueness.

## The Problem

Server logs often have unique timestamps, server IDs, or request IDs, but the underlying messages repeat:

- **Same error from different servers** - Different server names, same error message
- **Same message at different times** - Different timestamps, same log content
- **Unique IDs obscure patterns** - Request IDs make every line look unique

Traditional line-based deduplication can't ignore these varying fields.

## Input Data

???+ note "server.log"
    ```text hl_lines="1 4 6 2 5 8 3 7"
    --8<-- "use-cases/data-processing/fixtures/server.log"
    ```

    The log contains **8 entries**, but only **3 unique messages**:

    - "Request processed successfully" (lines 1, 4, 6) - appears 3×
    - "Connection timeout" (lines 2, 5, 8) - appears 3×
    - "High memory usage detected" (lines 3, 7) - appears 2×

## Output Data

???+ success "expected-field-output.log"
    ```text hl_lines="1-3"
    --8<-- "use-cases/data-processing/fixtures/expected-field-output.log"
    ```

    **Result**: 5 duplicate lines removed → only unique messages remain

## Solution

=== "CLI"

    <!-- verify-file: output.log expected: expected-field-output.log -->
    <!-- termynal -->
    ```console
    $ uniqseq server.log \
        --hash-transform 'awk -F"|" "{print \$4}"' \
        --window-size 1 \
        --quiet > output.log
    ```

    **Options:**

    - `--hash-transform 'awk...'`: Extract field 4 (message) for comparison
    - `--window-size 1`: Deduplicate individual lines (not sequences)
    - `--quiet`: Suppress statistics

=== "Python"

    <!-- verify-file: output.log expected: expected-field-output.log -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        hash_transform=lambda line: line.split("|")[3].strip(),  # (1)!
        window_size=1,  # (2)!
    )

    with open("server.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Extract field 4 (message) using Python lambda
    2. Deduplicate individual lines (window_size=1)

## How It Works

The `--hash-transform` flag transforms each line for hashing purposes while keeping the original line in output:

```text
Original line:
2024-01-15 10:30:01 | INFO  | server-01 | Request processed successfully
                                           ↓
                                Hash only this part
                                (field 4: message)
                                           ↓
Output (original line preserved):
2024-01-15 10:30:01 | INFO  | server-01 | Request processed successfully
```

Lines with the same field 4 value are considered duplicates, but the complete original line is written to output.

### Why Window Size 1?

By default, uniqseq looks for repeated sequences of 10 lines. For field-based deduplication of individual log entries, use `--window-size 1` to treat each line independently.

## Real-World Workflows

### Deduplicate by Error Code

Extract only the error code for comparison:

```bash
# Log format: "timestamp | level | ERROR_CODE_123 | message"
uniqseq app.log \
    --hash-transform 'awk -F"|" "{print \$3}"' \
    --window-size 1 > unique-errors.log
```

### Multi-Field Deduplication

Combine multiple fields for uniqueness:

```bash
# Deduplicate by level + message (ignore timestamp and server)
uniqseq server.log \
    --hash-transform 'awk -F"|" "{print \$2 \$4}"' \
    --window-size 1 > output.log
```

### Case-Insensitive Field Matching

Combine with case normalization:

```bash
uniqseq server.log \
    --hash-transform 'awk -F"|" "{print \$4}" | tr "[:upper:]" "[:lower:]"' \
    --window-size 1 > output.log
```

### Track Unique Messages Across Servers

Use a library to accumulate unique messages:

```bash
# Day 1: server-01 logs
uniqseq server-01.log \
    --hash-transform 'awk -F"|" "{print \$4}"' \
    --window-size 1 \
    --library-dir messages-lib/ > clean-01.log

# Day 2: server-02 logs (reuses library)
uniqseq server-02.log \
    --hash-transform 'awk -F"|" "{print \$4}"' \
    --window-size 1 \
    --library-dir messages-lib/ > clean-02.log
```

The library tracks messages across all servers.

## Performance Considerations

Hash transforms run an external command for each line. For large files:

1. **Use efficient commands**: `cut` is faster than `awk`, `awk` is faster than `sed`
2. **Avoid complex regex**: Simple field extraction is fastest
3. **Consider preprocessing**: If possible, preprocess outside uniqseq

```bash
# Slower (subprocess per line)
uniqseq large.log --hash-transform 'awk...' --window-size 1

# Faster (preprocess once)
awk -F"|" '{$1=""; $3=""; print}' large.log | uniqseq --window-size 1
```

## See Also

- [Hash Transform](../../features/hash-transform/hash-transform.md) - Detailed hash transform documentation
- [Window Size](../../features/window-size/window-size.md) - Understanding window sizes
- [Pattern Libraries](../../features/library-dir/library-dir.md) - Cross-file deduplication
