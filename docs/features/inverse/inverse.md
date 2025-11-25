# Inverse Mode

The `--inverse` flag reverses deduplication behavior: instead of removing duplicates, it outputs **only** the duplicates and removes everything else. This is useful for analyzing what patterns are repeating in your data.

## What It Does

Inverse mode flips the output:

- **Normal mode**: Output unique sequences, skip duplicates
- **Inverse mode**: Output only duplicates, skip unique sequences
- **Use case**: Identify repeating patterns, especially with normalization

**Key insight**: Inverse mode combined with `--skip-chars` or `--hash-transform` reveals which lines matched after normalization, preserving their original form.

## Example: Finding Repeated Errors in Timestamped Logs

This example shows server logs where the same error appears at different times. Using `--skip-chars 20` ignores timestamps when finding duplicates, then inverse mode shows which timestamped lines matched.

???+ note "Input: Timestamped server logs with repeated error"
    ```text hl_lines="1-3 5-7 9-11"
    --8<-- "features/inverse/fixtures/input.txt"
    ```

    **Lines 1-3** (08:15:23): Database error - first occurrence
    **Line 4**: Unique INFO message
    **Lines 5-7** (08:18:12): Database error - second occurrence (duplicate)
    **Line 8**: Unique INFO message
    **Lines 9-11** (08:20:45): Database error - third occurrence (duplicate)
    **Line 12**: Unique INFO message

### Normal Mode with Skip-Chars: Remove Duplicates

Normal mode with `--skip-chars 20` ignores timestamp prefixes when detecting duplicates.

=== "CLI"

    <!-- verify-file: output-normal.txt expected: expected-normal.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 --skip-chars 20 \
        > output-normal.txt
    ```

=== "Python"

    <!-- verify-file: output-normal.txt expected: expected-normal.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,
        skip_chars=20,  # (1)!
        inverse=False
    )

    with open("input.txt") as f:
        with open("output-normal.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Skip first 20 characters (timestamp prefix) when hashing

???+ success "Output: Duplicates removed, timestamps preserved"
    ```text hl_lines="1-3"
    --8<-- "features/inverse/fixtures/expected-normal.txt"
    ```

    **Result**: 6 lines. Two 3-line duplicate errors removed (highlighted: first occurrence kept).
    Original timestamps preserved in output.

### Inverse Mode with Skip-Chars: Show Only Duplicates

Inverse mode with `--skip-chars 20` shows duplicate occurrences with their timestamps.

=== "CLI"

    <!-- verify-file: output-inverse.txt expected: expected-inverse.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 --skip-chars 20 \
        --inverse > output-inverse.txt
    ```

=== "Python"

    <!-- verify-file: output-inverse.txt expected: expected-inverse.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,
        skip_chars=20,  # (1)!
        inverse=True    # (2)!
    )

    with open("input.txt") as f:
        with open("output-inverse.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Skip timestamp prefix when detecting duplicates
    2. Output only duplicate occurrences

???+ warning "Output: Both duplicates shown with timestamps"
    ```text hl_lines="1-3 4-6"
    --8<-- "features/inverse/fixtures/expected-inverse.txt"
    ```

    **Result**: 6 lines. Both duplicate errors shown:
    - Lines 1-3: Duplicate at 08:18:12 (lines 5-7 from input)
    - Lines 4-6: Duplicate at 08:20:45 (lines 9-11 from input)

    **Key insight**: Timestamps preserved! You can see WHEN each duplicate occurred.

## How It Works

### Output Inversion with Skip-Chars

Inverse mode combined with `--skip-chars` ignores prefixes when detecting duplicates, but preserves them in output:

```
Input (12 lines with timestamps):
  Lines 1-3:   08:15:23 ERROR...      ← First occurrence
  Line 4:      08:17:45 INFO...       ← Unique
  Lines 5-7:   08:18:12 ERROR...      ← Second occurrence (duplicate)
  Line 8:      08:19:30 INFO...       ← Unique
  Lines 9-11:  08:20:45 ERROR...      ← Third occurrence (duplicate)
  Line 12:     08:22:00 INFO...       ← Unique

With --skip-chars 20 (ignore timestamp prefix):
  Lines 1-3, 5-7, and 9-11 all match (same ERROR message)

Normal mode + skip-chars:
  ✓ Output lines 1-3 (first ERROR at 08:15:23)
  ✓ Output line 4 (unique)
  ✗ Skip lines 5-7 (duplicate ERROR at 08:18:12)
  ✓ Output line 8 (unique)
  ✗ Skip lines 9-11 (duplicate ERROR at 08:20:45)
  ✓ Output line 12 (unique)
  → Result: 6 lines

Inverse mode + skip-chars:
  ✗ Skip lines 1-3 (first ERROR - original)
  ✗ Skip line 4 (unique)
  ✓ Output lines 5-7 (duplicate ERROR at 08:18:12 - timestamp preserved!)
  ✗ Skip line 8 (unique)
  ✓ Output lines 9-11 (duplicate ERROR at 08:20:45 - timestamp preserved!)
  ✗ Skip line 12 (unique)
  → Result: 6 lines showing both duplicates with timestamps
```

**Key insight**: Skip-chars affects matching, not output. Timestamps are preserved, letting you see WHEN each duplicate occurred.

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
