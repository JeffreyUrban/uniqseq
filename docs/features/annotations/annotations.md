# Annotations

The `--annotate` flag adds markers to the output showing where duplicate
sequences were removed. This helps you understand what was deduplicated
and where the original sequence appeared.

## What It Does

Annotations add informational markers:

- **Normal mode**: Duplicates removed silently
- **With annotations**: Markers show what was removed and where
- **Use case**: Understand deduplication decisions, audit what was filtered

**Key insight**: Annotations document the deduplication process without
changing which lines are output.

## Example: Tracking Removed Duplicates

This example shows a simple log where a 3-line sequence repeats.
Annotations reveal where the duplicate was removed.

???+ note "Input: Repeating sequence"
    ```text hl_lines="1-3 4-6"
    --8<-- "features/annotations/fixtures/input.txt"
    ```

    **First occurrence** (lines 1-3): Line A, B, C
    **Duplicate** (lines 4-6): Same sequence repeats
    **Unique** (line 7): Line D

### Without Annotations: Silent Removal

Without `--annotate`, duplicates are removed without any indication
in the output.

=== "CLI"

    <!-- verify-file: output-no-annotate.txt expected: expected-no-annotate.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 > output-no-annotate.txt
    ```

=== "Python"

    <!-- verify-file: output-no-annotate.txt expected: expected-no-annotate.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,
        annotate=False  # (1)!
    )

    with open("input.txt") as f:
        with open("output-no-annotate.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Default: no annotations

???+ success "Output: Duplicate removed"
    ```text
    --8<-- "features/annotations/fixtures/expected-no-annotate.txt"
    ```

    **Result**: 4 lines remain. The duplicate (lines 4-6) was removed silently.

### With Annotations: Documented Removal

With `--annotate`, a marker is inserted showing where the duplicate
was removed and what it matched.

=== "CLI"

    <!-- verify-file: output-annotate.txt expected: expected-annotate.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 --annotate \
        > output-annotate.txt
    ```

=== "Python"

    <!-- verify-file: output-annotate.txt expected: expected-annotate.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,
        annotate=True  # (1)!
    )

    with open("input.txt") as f:
        with open("output-annotate.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Enable annotations

???+ warning "Output: Duplicate documented"
    ```text hl_lines="4"
    --8<-- "features/annotations/fixtures/expected-annotate.txt"
    ```

    **Result**: 5 lines (4 content + 1 annotation). The marker shows:
    - Input lines 4-6 were duplicates
    - They matched output lines 1-3
    - This sequence was seen 1 time (as a duplicate)

## How It Works

### Annotation Format

The default annotation format provides key information:

```
[DUPLICATE: Lines 4-6 matched lines 1-3 (sequence seen 1 times)]
           └──┬───┘         └───┬───┘           └────┬────┘
              │                 │                     │
     Input line range     Output line range    Duplicate count
      (what was removed)  (where it matched)   (how many times)
```

**Fields explained**:
- **Lines 4-6**: The duplicate lines from the input (removed)
- **matched lines 1-3**: Where in the output the original sequence appears
- **sequence seen 1 times**: How many times this pattern has repeated

### Annotation Placement

Annotations are inserted where the duplicate would have appeared:

```
Input (7 lines):          Output with annotations (5 lines):
1. Line A          →      1. Line A
2. Line B          →      2. Line B
3. Line C          →      3. Line C
4. Line A          ✗      4. [DUPLICATE: Lines 4-6 matched lines 1-3...]
5. Line B          ✗         (annotation inserted here)
6. Line C          ✗
7. Line D          →      5. Line D
```

The annotation appears at the position where the duplicate sequence began.

## Custom Annotation Format

Use `--annotation-format` to customize the marker:

```bash
# Custom format with specific fields
uniqseq log.txt --annotate \
    --annotation-format "SKIP|Lines {start}-{end}|Count:{count}"

# Minimal format
uniqseq log.txt --annotate \
    --annotation-format "[Removed {count} duplicate lines]"

# JSON-like format
uniqseq log.txt --annotate \
    --annotation-format \
      '{"removed":"{start}-{end}","matched":"{match_start}-{match_end}"}'
```

### Available Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `{start}` | First input line of duplicate | `4` |
| `{end}` | Last input line of duplicate | `6` |
| `{match_start}` | First output line of match | `1` |
| `{match_end}` | Last output line of match | `3` |
| `{count}` | Number of times seen | `1` |

## Common Use Cases

### Auditing Deduplication

```bash
# Review what was filtered
uniqseq build.log --annotate > clean.log
grep DUPLICATE clean.log

# Count how many duplicates were found
uniqseq app.log --annotate | grep -c DUPLICATE
```

### Understanding Patterns

```bash
# Find frequently repeating patterns (high count)
uniqseq log.txt --annotate | grep "sequence seen [5-9]"

# See what's being filtered in real-time
tail -f app.log | uniqseq --annotate --window-size 3
```

### Custom Processing

```bash
# Extract just the annotations for analysis
uniqseq log.txt --annotate | grep "^\[DUPLICATE"

# Parse annotations with custom format
uniqseq log.txt --annotate \
    --annotation-format "REMOVED|{start}|{end}|{count}" \
    | grep "^REMOVED"
```

### Debugging Deduplication

```bash
# Verify window size is correct
uniqseq data.txt --annotate --window-size 5

# Check if skip-chars is working
uniqseq log.txt --annotate --skip-chars 20 --window-size 3
```

## Combining with Other Features

### With Pattern Filtering

```bash
# Annotate only ERROR deduplication
uniqseq log.txt --annotate --track "ERROR" --window-size 3
```

### With Inverse Mode

Annotations are **not** added in inverse mode (duplicates are output, not skipped):

```bash
# No annotations - inverse outputs duplicates directly
uniqseq log.txt --inverse --annotate  # annotate has no effect
```

### With Hash Transform

```bash
# Show what was removed after case normalization
uniqseq log.txt --annotate \
    --hash-transform "tr '[:upper:]' '[:lower:]'" \
    --window-size 3
```

## Performance Note

Annotations add minimal overhead:
- One marker line per duplicate sequence
- No impact on deduplication logic
- Useful for debugging without performance cost

## Rule of Thumb

**Use annotations when you need to understand** what was deduplicated.

- **Production filtering**: Usually skip annotations (cleaner output)
- **Debugging/analysis**: Enable annotations to see decisions
- **Auditing**: Use custom format for machine parsing
- **Not with inverse mode**: Annotations only apply to removed duplicates

## See Also

- [CLI Reference](../../reference/cli.md) - Complete annotation documentation
- [Inverse Mode](../inverse/inverse.md) - Output duplicates instead
- [Common Patterns](../../guides/common-patterns.md) - Annotation examples
