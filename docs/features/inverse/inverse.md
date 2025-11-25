# Inverse Mode

The `--inverse` flag reverses deduplication behavior: instead of removing duplicates, it outputs **only** the duplicates and removes everything else. This is useful for analyzing what patterns are repeating in your data.

## What It Does

Inverse mode flips the output:

- **Normal mode**: Output unique sequences, skip duplicates
- **Inverse mode**: Output only duplicates, skip unique sequences
- **Use case**: Identify repeating patterns to find issues or noise

**Key insight**: Inverse mode answers "what's being repeated?" instead of "what's unique?".

## Example: Finding Repeated Errors

This example shows logs where an error sequence repeats. Normal mode removes the duplicate. Inverse mode shows only the duplicate.

???+ note "Input: Logs with repeating pattern"
    ```text hl_lines="1-3 4-6"
    --8<-- "features/inverse/fixtures/input.txt"
    ```

    **First occurrence** (lines 1-3): ERROR, WARNING, INFO sequence
    **Duplicate** (lines 4-6): Same 3-line sequence repeats
    **Unique** (lines 7-8): Different messages

### Normal Mode: Remove Duplicates

Normal mode outputs unique sequences and removes duplicates.

=== "CLI"

    <!-- verify-file: output-normal.txt expected: expected-output.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 > output-normal.txt
    ```

=== "Python"

    <!-- verify-file: output-normal.txt expected: expected-output.txt -->
    ```python
    from uniqseq import StreamingDeduplicator

    dedup = StreamingDeduplicator(
        window_size=3,
        inverse=False  # (1)!
    )

    with open("input.txt") as f:
        with open("output-normal.txt", "w") as out:
            for line in f:
                dedup.process_line(line.rstrip("\n"), out)
            dedup.flush(out)
    ```

    1. Default: normal mode (remove duplicates)

???+ success "Output: Duplicates removed"
    ```text hl_lines="1-3 4-5"
    --8<-- "features/inverse/fixtures/expected-output.txt"
    ```

    **Result**: 5 lines remain. The duplicate 3-line sequence (lines 4-6) was removed.

### Inverse Mode: Show Only Duplicates

Inverse mode outputs only the duplicate sequences and removes unique content.

=== "CLI"

    <!-- verify-file: output-inverse.txt expected: expected-inverse.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 --inverse \
        > output-inverse.txt
    ```

=== "Python"

    <!-- verify-file: output-inverse.txt expected: expected-inverse.txt -->
    ```python
    from uniqseq import StreamingDeduplicator

    dedup = StreamingDeduplicator(
        window_size=3,
        inverse=True  # (1)!
    )

    with open("input.txt") as f:
        with open("output-inverse.txt", "w") as out:
            for line in f:
                dedup.process_line(line.rstrip("\n"), out)
            dedup.flush(out)
    ```

    1. Inverse mode: output only duplicates

???+ warning "Output: Only duplicates shown"
    ```text hl_lines="1-3"
    --8<-- "features/inverse/fixtures/expected-inverse.txt"
    ```

    **Result**: 3 lines remain. Only the duplicate sequence (lines 4-6 from input) is shown. Unique sequences removed.

## How It Works

### Output Inversion

Inverse mode reverses which sequences are output:

```
Input (8 lines):
  Lines 1-3: ERROR, WARNING, INFO    ← First occurrence
  Lines 4-6: ERROR, WARNING, INFO    ← Duplicate
  Lines 7-8: DEBUG, SUCCESS          ← Unique

Normal mode:
  ✓ Output lines 1-3 (first occurrence)
  ✗ Skip lines 4-6 (duplicate)
  ✓ Output lines 7-8 (unique)
  → Result: 5 lines

Inverse mode:
  ✗ Skip lines 1-3 (first occurrence)
  ✓ Output lines 4-6 (duplicate)
  ✗ Skip lines 7-8 (unique)
  → Result: 3 lines
```

Only the duplicate occurrences are output. The first occurrence and unique sequences are skipped.

## Common Use Cases

### Finding Repetitive Errors

```bash
# Analyze build logs for repeated failures
make 2>&1 | uniqseq --inverse --window-size 5 > repeated-errors.txt

# Find which tests are failing repeatedly
pytest --verbose | uniqseq --inverse --window-size 3 > failing-tests.txt
```

### Identifying Noise in Logs

```bash
# Find what messages are repeating (potential noise)
uniqseq app.log --inverse --window-size 3 > noisy-patterns.txt

# Track only errors, find repeated error patterns
uniqseq app.log --track "ERROR" --inverse --window-size 3
```

### Pattern Analysis

```bash
# Extract only duplicate sequences for analysis
uniqseq data.txt --inverse --window-size 10 | sort | uniq -c | sort -rn

# Find repeated API call patterns
tail -f access.log | uniqseq --inverse --window-size 5
```

### Debugging Loops

```bash
# Find infinite loops in program output
./program | uniqseq --inverse --window-size 3

# Detect repeated retry attempts
uniqseq service.log --inverse --track "Retry" --window-size 2
```

## Combining with Other Features

### With Pattern Filtering

```bash
# Find only repeated ERROR sequences
uniqseq log.txt --inverse --track "ERROR" --window-size 3

# Find repeated patterns, excluding DEBUG
uniqseq log.txt --inverse --bypass "DEBUG" --window-size 3
```

### With Skip-Chars

```bash
# Find repeated messages (ignore timestamps)
uniqseq log.txt --inverse --skip-chars 20 --window-size 3
```

### With Hash Transform

```bash
# Find repeated patterns (case-insensitive)
uniqseq log.txt --inverse \
    --hash-transform "tr '[:upper:]' '[:lower:]'" \
    --window-size 3
```

## Understanding Empty Output

If inverse mode produces no output, it means **no duplicates were found**:

```bash
$ uniqseq unique-data.txt --inverse --window-size 3
# (no output)
```

This is actually good news - your data has no repeating sequences!

## Workflow Pattern

A common workflow combines normal and inverse mode:

```bash
# 1. Clean your data (remove duplicates)
uniqseq input.log --window-size 3 > clean.log

# 2. Analyze what was removed (find patterns)
uniqseq input.log --inverse --window-size 3 > duplicates.log

# 3. Review duplicates to understand repetitive issues
cat duplicates.log
```

## Rule of Thumb

**Use inverse mode to analyze what's repeating** rather than clean it up.

- **Normal mode**: "Give me the unique content"
- **Inverse mode**: "Show me what's repeating"
- Great for debugging and pattern analysis
- Combine with other filters for targeted analysis
- Empty output = no duplicates (good!)

## See Also

- [CLI Reference](../../reference/cli.md) - Complete `--inverse` documentation
- [Pattern Filtering](../pattern-filtering/pattern-filtering.md) - Combine with --track/--bypass
- [Common Patterns](../../guides/common-patterns.md) - More inverse mode examples
