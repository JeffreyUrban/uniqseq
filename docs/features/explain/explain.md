# Explain Mode

The `--explain` flag outputs explanations to stderr showing why each line
was kept or skipped during deduplication. This helps you understand the
deduplication decisions being made in real-time.

## What It Does

Explain mode adds diagnostic messages to stderr:

- **Normal mode**: Deduplication happens silently
- **With explain**: Messages show why lines were kept/skipped
- **Use case**: Debugging deduplication, understanding filter patterns, troubleshooting unexpected behavior

**Key insight**: Explanations go to stderr, so stdout remains clean for
piping deduplicated data.

## Example: Understanding Deduplication

This example shows a log where a 3-line sequence repeats. Explain mode
reveals when and why the duplicate was skipped.

???+ note "Input: Repeating sequence"
    ```text hl_lines="1-3 5-7"
    --8<-- "features/explain/fixtures/input.txt"
    ```

    **First occurrence** (lines 1-3): Startup sequence
    **Unique** (line 4): Done with setup
    **Duplicate** (lines 5-7): Same startup sequence repeats
    **Unique** (line 8): All systems go

### Without Explain: Silent Deduplication

Without `--explain`, deduplication happens without feedback.

=== "CLI"

    <!-- verify-file: output.txt expected: expected-output.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 --quiet > output.txt
    ```

=== "Python"

    <!-- verify-file: output.txt expected: expected-output.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,
        explain=False  # (1)!
    )

    with open("input.txt") as f:
        with open("output.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Default: no explanations

???+ success "Output: Duplicate removed silently"
    ```text
    --8<-- "features/explain/fixtures/expected-output.txt"
    ```

    **Result**: 5 lines remain. The duplicate (lines 5-7) was removed
    without any indication.

### With Explain: Documented Decisions

With `--explain`, stderr shows why the duplicate was skipped.

=== "CLI"

    <!-- verify-file: output.txt expected: expected-output.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 --explain --quiet \
        > output.txt 2> explain.txt
    ```

=== "Python"

    <!-- verify-file: output.txt expected: expected-output.txt -->
    ```python
    from uniqseq import UniqSeq
    import sys

    uniqseq = UniqSeq(
        window_size=3,
        explain=True  # (1)!
    )

    with open("input.txt") as f:
        with open("output.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Enable explain mode

???+ warning "Stdout: Deduplicated output"
    ```text
    --8<-- "features/explain/fixtures/expected-output.txt"
    ```

???+ info "Stderr: Explanation messages"
    ```text
    --8<-- "features/explain/fixtures/expected-explain.txt"
    ```

    **Result**: Stdout has 5 lines (deduplicated data), stderr shows
    that lines 5-7 were skipped as a duplicate seen 1 time.

## How It Works

### Explanation Format

Explain messages provide actionable information:

**Duplicate sequences skipped**:
```
EXPLAIN: Lines 5-7 skipped (duplicate of lines 1-3, seen 2x)
                └──┬───┘              └───┬───┘      └─┬──┘
                   │                      │            │
         Input line range        Output line range  Count
         (what was removed)      (where it matched)
```

**Filter pattern bypasses**:
```
EXPLAIN: Line 3 bypassed (matched bypass pattern '^INFO')
              └─┬──┘                           └───┬────┘
                │                                  │
         Input line number                  Pattern that matched
```

**Allowlist mode (track patterns)**:
```
EXPLAIN: Line 5 bypassed (no track pattern matched (allowlist mode))
```

### Message Types

| Type | When It Appears | Example |
|------|----------------|---------|
| **Skipped duplicate** | Sequence matches earlier occurrence | `Lines 10-15 skipped (duplicate of lines 1-6, seen 3x)` |
| **Bypassed (pattern)** | Line matches bypass filter | `Line 42 bypassed (matched bypass pattern '^DEBUG')` |
| **Bypassed (allowlist)** | No track pattern matched | `Line 23 bypassed (no track pattern matched (allowlist mode))` |

## Common Use Cases

### Debugging Why Lines Weren't Deduplicated

```bash
# See all deduplication decisions
uniqseq log.txt --explain --window-size 10 2>&1 | grep EXPLAIN

# Find out why specific lines stayed
uniqseq log.txt --explain 2>&1 | grep "Line 42"
```

### Validating Filter Patterns

```bash
# Check which lines match your bypass pattern
uniqseq log.txt --explain --bypass "^INFO" 2>&1 | grep "bypassed"

# Verify track patterns are working
uniqseq log.txt --explain --track "^ERROR" 2>&1 | grep "allowlist"
```

### Understanding Sequence Matching

```bash
# See which sequences are being matched
uniqseq log.txt --explain --window-size 5 2>&1 | grep "duplicate of"

# Find frequently repeating patterns
uniqseq log.txt --explain 2>&1 | grep "seen [5-9]x"
```

### Troubleshooting Unexpected Behavior

```bash
# Why isn't this being deduplicated?
uniqseq log.txt --explain --skip-chars 20 2>&1 | grep "Lines 100-110"

# What's happening with hash transforms?
uniqseq log.txt --explain \
    --hash-transform "tr '[:upper:]' '[:lower:]'" \
    2>&1 | grep EXPLAIN
```

## Combining with Other Features

### With Quiet Mode

```bash
# Only explanations, no statistics
uniqseq log.txt --explain --quiet 2> explain.log
grep EXPLAIN explain.log
```

### With Annotations

```bash
# Both stdout annotations and stderr explanations
uniqseq log.txt --explain --annotate > output.txt 2> explain.log
```

The difference:
- **Annotations**: Added to stdout, show where duplicates were removed
- **Explain**: Sent to stderr, show why decisions were made

### With JSON Stats

```bash
# Explanations + machine-readable stats
uniqseq log.txt --explain --stats-format json 2> diagnostics.txt
```

### With Progress

```bash
# Real-time explanations with progress indicator
uniqseq large.log --explain --progress 2>&1 | tee diagnostics.txt
```

## Filtering Explain Output

### Extract Specific Information

```bash
# Only show skipped duplicates
uniqseq log.txt --explain 2>&1 | grep "skipped"

# Only show filter bypasses
uniqseq log.txt --explain 2>&1 | grep "bypassed"

# Only high-repetition sequences
uniqseq log.txt --explain 2>&1 | grep "seen [5-9]x"
```

### Separate Stdout and Stderr

```bash
# Deduplicated data to file, explanations to terminal
uniqseq log.txt --explain > clean.log

# Both to separate files
uniqseq log.txt --explain > clean.log 2> explain.log

# Merge for analysis
uniqseq log.txt --explain 2>&1 | grep "Line 42"
```

## Performance Note

Explain mode has minimal overhead:
- Simple conditional check before printing
- Messages only written when explain is enabled
- No impact on deduplication performance
- Stderr output is buffered (efficient)

## Comparison with Annotations

| Feature | Explain (`--explain`) | Annotations (`--annotate`) |
|---------|----------------------|---------------------------|
| **Output** | stderr | stdout |
| **Format** | `EXPLAIN: <message>` | `[DUPLICATE: ...]` |
| **Shows** | Why decisions made | What was removed |
| **Use for** | Debugging, understanding | Auditing, documentation |
| **Data flow** | Diagnostic | Part of output |
| **Performance** | Negligible | Minimal |

**Use both together** for complete visibility:
```bash
uniqseq log.txt --explain --annotate > output.txt 2> explain.log
```

## Rule of Thumb

**Use explain mode when you need to understand** the deduplication process.

- **Initial setup**: Validate window size and filters are working correctly
- **Debugging**: Understand why specific lines weren't deduplicated
- **Pattern development**: Test and refine filter patterns
- **Troubleshooting**: Diagnose unexpected behavior
- **Learning**: Understand how the algorithm works on your data

**Don't use in production** unless actively debugging—the extra output
can clutter logs.

## See Also

- [CLI Reference](../../reference/cli.md) - Complete explain documentation
- [Annotations](../annotations/annotations.md) - Mark removed duplicates in output
- [Pattern Filtering](../pattern-filtering/pattern-filtering.md) - Using track/bypass patterns
- [Troubleshooting](../../guides/troubleshooting.md) - Common issues and solutions
