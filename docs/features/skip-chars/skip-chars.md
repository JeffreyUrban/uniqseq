# Ignoring Prefixes

The `--skip-chars N` option tells uniqseq to ignore the first N characters when comparing lines. This is essential for logs with timestamps or other changing prefixes.

## What It Does

Skip-chars affects how lines are hashed for comparison:

- **Without skip-chars**: Entire line is hashed (timestamps make lines different)
- **With skip-chars N**: First N characters are skipped, only the rest is hashed
- **Use case**: Logs where timestamp changes but message repeats

**Key insight**: Lines with different prefixes but identical content after position N are treated as duplicates.

## Example: Timestamped Error Logs

This example shows error logs with timestamps. The same error repeats multiple times, but timestamps differ. Without skip-chars, these look like different lines.

???+ note "Input: Errors with timestamps"
    ```text hl_lines="1-3 5-7 9-11"
    --8<-- "features/skip-chars/fixtures/input.txt"
    ```

    **Pattern 1** (lines 1-3): First occurrence of connection timeout
    **Pattern 2** (lines 5-7): Same error, different timestamps
    **Pattern 3** (lines 9-11): Same error again, different timestamps

### Without Skip-Chars: All Lines Kept

Without `--skip-chars`, the timestamps make each line unique. No deduplication occurs.

=== "CLI"

    <!-- verify-file: output-no-skip.txt expected: expected-no-skip.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 > output-no-skip.txt
    ```

=== "Python"

    <!-- verify-file: output-no-skip.txt expected: expected-no-skip.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,
        skip_chars=0  # (1)!
    )

    with open("input.txt") as f:
        with open("output-no-skip.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Default: don't skip any characters

???+ warning "Output: No deduplication"
    ```text hl_lines="1-3 5-7 9-11"
    --8<-- "features/skip-chars/fixtures/expected-no-skip.txt"
    ```

    **Result**: All 12 lines kept. Timestamps make each line unique, so no duplicates are detected.

### With Skip-Chars 22: Duplicates Removed

With `--skip-chars 22`, the timestamp prefix `[2024-11-25 10:15:01] ` (22 characters) is ignored. Now the duplicate errors are detected.

=== "CLI"

    <!-- verify-file: output-skip-22.txt expected: expected-skip-22.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 --skip-chars 22 \
        > output-skip-22.txt
    ```

=== "Python"

    <!-- verify-file: output-skip-22.txt expected: expected-skip-22.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,
        skip_chars=22  # (1)!
    )

    with open("input.txt") as f:
        with open("output-skip-22.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Skip first 22 chars (timestamp prefix)

???+ success "Output: Duplicates removed"
    ```text hl_lines="1-3"
    --8<-- "features/skip-chars/fixtures/expected-skip-22.txt"
    ```

    **Result**: Only 6 lines remain. The duplicate error patterns (lines 5-7 and 9-11 from input) were removed.

## How It Works

### Character Offset Comparison

When skip-chars is enabled, uniqseq compares lines starting at the specified position:

```
Line: "[2024-11-25 10:15:01] ERROR: Database connection timeout"
      └────────┬─────────┘ └──────────────┬─────────────────┘
          skip 22 chars            compare this part

Line: "[2024-11-25 10:15:05] ERROR: Database connection timeout"
      └────────┬─────────┘ └──────────────┬─────────────────┘
          skip 22 chars            compare this part
                                           ↓
                                    Match found!
```

Both lines hash to the same value because everything after position 22 is identical.

### Finding the Right Offset

To determine the skip-chars value, count characters in the prefix:

```bash
# Count characters in timestamp prefix
echo "[2024-11-25 10:15:01] " | wc -c
# Output: 22

# Use this value with --skip-chars
uniqseq log.txt --skip-chars 22
```

**Important**: Include the space after the closing bracket in your count.

### Visual Example

```
Position: 0         10        20  22
          |         |         |   |
Line 1:  "[2024-11-25 10:15:01] ERROR: Database..."
Line 2:  "[2024-11-25 10:15:05] ERROR: Database..."
          └─────────┬─────────┘   └──────┬───────
             Different              Same (matched)
            (ignored)
```

## Common Use Cases

### Log Files with Timestamps

```bash
# ISO format: [2024-01-15 10:30:45]
uniqseq app.log --skip-chars 22

# Unix timestamp format: [1705318245.123]
uniqseq app.log --skip-chars 17

# Custom format: "2024-01-15 10:30:45 - "
uniqseq app.log --skip-chars 22
```

### Line Numbers or Markers

```bash
# Line numbers: "00001: Message"
uniqseq output.txt --skip-chars 7

# Thread IDs: "[Thread-12345] Log message"
uniqseq thread.log --skip-chars 15
```

### Process IDs

```bash
# Format: "pid=12345 message"
uniqseq process.log --skip-chars 10

# Format: "[PID:12345] message"
uniqseq process.log --skip-chars 12
```

## Choosing the Right Skip Value

### Measure Your Prefix

Use shell tools to measure:

```bash
# Method 1: Echo and count
echo "[2024-11-25 10:15:01] " | wc -c

# Method 2: Visual inspection
head -1 logfile.txt
# Count characters including spaces
```

### Test Your Value

```bash
# Test with a small sample
head -20 app.log | uniqseq --skip-chars 22 --window-size 3

# Verify deduplication works as expected
```

### Too Small vs Too Large

**Too small**: Doesn't skip entire prefix
```bash
# Only skips "[2024-11-25 10:", includes seconds
uniqseq log.txt --skip-chars 18  # ⚠️ Lines still differ
```

**Too large**: Skips into message content
```bash
# Skips into "ERROR:", might miss differences
uniqseq log.txt --skip-chars 30  # ⚠️ False positives
```

**Just right**: Skips exactly the prefix
```bash
# Skips "[2024-11-25 10:15:01] " completely
uniqseq log.txt --skip-chars 22  # ✅ Correct
```

## Rule of Thumb

**Set skip-chars to the length of your changing prefix**, including trailing spaces.

- Timestamp + space → Count total characters
- Verify with `wc -c` or manual count
- Test on sample data to confirm

## See Also

- [Common Patterns Guide](../../guides/common-patterns.md) - More timestamp handling examples and patterns
- [CLI Reference](../../reference/cli.md) - Complete `--skip-chars` documentation
- [CI Build Logs](../../use-cases/ci-logs/multi-line-sequences.md) - Real-world example
