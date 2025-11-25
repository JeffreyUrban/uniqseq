# Pattern Filtering

The `--track` and `--bypass` options control which lines participate in deduplication using regex patterns. This enables selective deduplication where only specific types of lines (like errors) are checked for repeating sequences, while other lines pass through unchanged.

## What It Does

Pattern filtering affects deduplication behavior:

- **No filter**: All lines participate in deduplication
- **--track PATTERN**: Only lines matching pattern are deduplicated (allowlist mode)
- **--bypass PATTERN**: Lines matching pattern skip deduplication (denylist mode)
- **Use case**: Deduplicate errors while preserving all info/debug messages

**Key insight**: When tracking specific patterns, sequences are formed only from tracked lines. Untracked lines pass through without breaking the sequence tracking.

## Example: Tracking Only Errors

This example shows interleaved error and info messages. Without filtering, the sequences don't repeat because INFO lines interrupt the pattern. With `--track "^ERROR"`, only ERROR lines form sequences.

???+ note "Input: Mixed error and info messages"
    ```text hl_lines="1 3 5 7"
    --8<-- "features/pattern-filtering/fixtures/input.txt"
    ```

    **ERROR lines** (tracked): Lines 1, 3, 5, 7
    **INFO lines** (pass through): Lines 2, 4, 6, 8

### Without Filter: No Duplicates Found

Without pattern filtering, all lines participate in deduplication. The 2-line windows include both ERROR and INFO lines, so no exact duplicates exist.

=== "CLI"

    <!-- verify-file: output-no-filter.txt expected: expected-no-filter.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 2 > output-no-filter.txt
    ```

=== "Python"

    <!-- verify-file: output-no-filter.txt expected: expected-no-filter.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=2,
        filter_patterns=None  # (1)!
    )

    with open("input.txt") as f:
        with open("output-no-filter.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Default: all lines participate in deduplication

???+ warning "Output: All lines kept"
    ```text hl_lines="1 3 5 7"
    --8<-- "features/pattern-filtering/fixtures/expected-no-filter.txt"
    ```

    **Result**: All 8 lines kept. Windows like [ERROR+INFO] don't exactly repeat, so no duplicates detected.

### With Track Pattern: Duplicates Removed

With `--track "^ERROR"`, only ERROR lines form sequences. The sequence [Connection failed, Timeout occurred] at ERROR lines 1+3 repeats at ERROR lines 5+7, so the duplicate is removed.

=== "CLI"

    <!-- verify-file: output-track-error.txt expected: expected-track-error.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 2 --track "^ERROR" \
        > output-track-error.txt
    ```

=== "Python"

    <!-- verify-file: output-track-error.txt expected: expected-track-error.txt -->
    ```python
    import re
    from uniqseq.uniqseq import UniqSeq, FilterPattern

    patterns = [
        FilterPattern(
            pattern="^ERROR",
            action="track",
            regex=re.compile(r"^ERROR")
        )
    ]

    uniqseq = UniqSeq(
        window_size=2,
        filter_patterns=patterns  # (1)!
    )

    with open("input.txt") as f:
        with open("output-track-error.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Python API: use FilterPattern list with compiled regex

???+ success "Output: ERROR sequence duplicates removed"
    ```text hl_lines="1 3"
    --8<-- "features/pattern-filtering/fixtures/expected-track-error.txt"
    ```

    **Result**: Only 6 lines remain. ERROR lines 5 and 7 were removed because they form a duplicate 2-line ERROR sequence matching lines 1+3.

## How It Works

### Selective Sequence Tracking

When using `--track`, sequences are formed only from tracked lines:

```
Input stream:
  1. ERROR: Connection failed    ← Tracked (position 1 in ERROR sequence)
  2. INFO: Retrying...            ← Passes through (not tracked)
  3. ERROR: Timeout occurred      ← Tracked (position 2 in ERROR sequence)
  4. INFO: Attempting reconnect   ← Passes through (not tracked)
  5. ERROR: Connection failed     ← Tracked (position 1 in ERROR sequence)
  6. INFO: Still retrying...      ← Passes through (not tracked)
  7. ERROR: Timeout occurred      ← Tracked (position 2 in ERROR sequence)
  8. INFO: Connection restored    ← Passes through (not tracked)

Tracked ERROR sequence:
  Window 1: [Connection failed, Timeout occurred]  (lines 1+3)
  Window 2: [Connection failed, Timeout occurred]  (lines 5+7)
                    ↓
            Duplicate detected!
```

Lines 5 and 7 are removed because they form the same 2-line ERROR sequence as lines 1+3.

### Allowlist vs Denylist Mode

**Allowlist mode** (`--track`):
- Only matching lines are tracked for deduplication
- Non-matching lines pass through unchanged
- Use when you want to deduplicate specific types only

**Denylist mode** (`--bypass`):
- Matching lines pass through unchanged
- Non-matching lines are tracked for deduplication
- Use when you want to preserve specific types

```bash
# Allowlist: only deduplicate ERROR lines
uniqseq log.txt --track "^ERROR"

# Denylist: deduplicate everything except INFO
uniqseq log.txt --bypass "^INFO"
```

### Pattern Evaluation Order

When both `--track` and `--bypass` are specified, they're evaluated sequentially:

1. Check `--track` first
2. Then check `--bypass`
3. First match wins

```bash
# Track ERROR or WARN, but bypass WARN: Deprecated
uniqseq log.txt \
    --track "ERROR|WARN" \
    --bypass "Deprecated"

# Result: ERROR and WARN lines are tracked,
#         except "WARN: Deprecated" bypasses
```

## Common Use Cases

### Deduplicate Only Errors

```bash
# Track only ERROR lines
uniqseq app.log --track "^ERROR" --window-size 3

# Track multiple severity levels
uniqseq app.log --track "ERROR|FATAL|CRITICAL" --window-size 3
```

### Preserve Debug Messages

```bash
# Deduplicate everything except DEBUG
uniqseq app.log --bypass "^DEBUG" --window-size 3

# Preserve multiple log levels
uniqseq app.log --bypass "DEBUG|TRACE|INFO" --window-size 3
```

### Test Output Filtering

```bash
# Only deduplicate test failures
pytest --verbose | uniqseq --track "FAILED" --window-size 5

# Preserve passing tests, deduplicate failures
pytest --verbose | uniqseq --bypass "PASSED" --window-size 5
```

### Build Log Filtering

```bash
# Track only warnings and errors
make 2>&1 | uniqseq --track "warning|error" --window-size 3

# Bypass progress indicators
npm install | uniqseq --bypass "^npm WARN" --window-size 3
```

### Combining with Other Features

```bash
# Track errors, skip timestamps, case-insensitive
uniqseq log.txt \
    --track "error" \
    --skip-chars 22 \
    --hash-transform "tr '[:upper:]' '[:lower:]'" \
    --window-size 3
```

## Pattern Syntax

Patterns use Python regular expressions (re module):

**Anchors**:
```bash
^ERROR   # Matches line starting with ERROR
ERROR$   # Matches line ending with ERROR
^ERROR$  # Matches line that is exactly ERROR
```

**Alternation**:
```bash
ERROR|WARN|FATAL  # Matches any of these
```

**Character classes**:
```bash
^\[ERROR\]   # Matches lines starting with [ERROR]
^[EW]        # Matches lines starting with E or W
```

**Case insensitive** (use with `--track-ignore-case` or `--bypass-ignore-case`):
```bash
uniqseq log.txt --track "error" --track-ignore-case
# Matches ERROR, Error, error, etc.
```

## Choosing Track vs Bypass

### Use --track when:
- You want to deduplicate only specific types (errors, failures)
- Most lines should pass through unchanged
- You have a clear subset to target

```bash
# Deduplicate only test failures
pytest | uniqseq --track "FAILED"
```

### Use --bypass when:
- You want to deduplicate everything except specific types
- Only a small subset should be preserved
- You want to exclude noise from deduplication

```bash
# Deduplicate all except progress indicators
npm install | uniqseq --bypass "^fetching|^extracted"
```

### Use both when:
- Complex filtering logic required
- Need exceptions to rules
- First match wins (order matters!)

```bash
# Track errors, but bypass deprecation warnings
uniqseq log.txt \
    --track "ERROR|WARN" \
    --bypass "DeprecationWarning"
```

## Pattern Files

For complex patterns, use pattern files:

```bash
# track_patterns.txt
^ERROR
^FATAL
^CRITICAL
# Comments are supported

# Use with --track-file
uniqseq app.log --track-file track_patterns.txt --window-size 3
```

Pattern files support:
- One pattern per line
- Comments (lines starting with #)
- Blank lines (ignored)
- Same regex syntax as command line

## Rule of Thumb

**Use pattern filtering when you want selective deduplication** of specific message types while preserving others.

- **--track**: "Only deduplicate these patterns"
- **--bypass**: "Deduplicate everything except these patterns"
- Test patterns on sample data first
- Use anchors (^, $) for precise matching
- Combine with other features for powerful filtering

## See Also

- [CLI Reference](../../reference/cli.md) - Complete pattern filtering documentation
- [Common Patterns](../../guides/common-patterns.md) - More filtering examples
- [CI Build Logs](../../use-cases/ci-logs/multi-line-sequences.md) - Real-world use case
