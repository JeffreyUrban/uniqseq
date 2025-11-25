# Hash Transformations

The `--hash-transform` option applies a shell command to each line before hashing, enabling flexible comparison logic while preserving original output. This is powerful for case-insensitive matching, field extraction, and custom normalization.

## What It Does

Hash transformation affects how lines are compared for deduplication:

- **Without hash-transform**: Lines are hashed as-is
- **With hash-transform**: Lines are piped through a shell command, then the transformed output is hashed
- **Use case**: Match lines that differ only in case, timestamps, or specific fields

**Key insight**: The original line is always output, but the transformed version is used for comparison.

## Example: Case-Insensitive Deduplication

This example shows error logs with inconsistent capitalization. The same sequence appears twice but with different case. Without hash-transform, these are treated as different sequences.

???+ note "Input: Logs with inconsistent case"
    ```text hl_lines="1-3 4-6"
    --8<-- "features/hash-transform/fixtures/input.txt"
    ```

    **Pattern 1** (lines 1-3): First occurrence with uppercase
    **Pattern 2** (lines 4-6): Same content with lowercase

### Without Hash Transform: Case-Sensitive

Without `--hash-transform`, the different case makes each sequence unique. No deduplication occurs.

=== "CLI"

    <!-- verify-file: output-no-transform.txt expected: expected-no-transform.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 > output-no-transform.txt
    ```

=== "Python"

    <!-- verify-file: output-no-transform.txt expected: expected-no-transform.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,
        hash_transform=None  # (1)!
    )

    with open("input.txt") as f:
        with open("output-no-transform.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Default: no transformation

???+ warning "Output: No deduplication"
    ```text hl_lines="1-3 4-6"
    --8<-- "features/hash-transform/fixtures/expected-no-transform.txt"
    ```

    **Result**: All 6 lines kept. Different case prevents duplicate detection.

### With Hash Transform: Case-Insensitive

With `--hash-transform "tr '[:upper:]' '[:lower:]'"`, all text is converted to lowercase before hashing. Now the duplicate sequence is detected.

=== "CLI"

    <!-- verify-file: output-lowercase.txt expected: expected-lowercase.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 \
        --hash-transform "tr '[:upper:]' '[:lower:]'" \
        > output-lowercase.txt
    ```

=== "Python"

    <!-- verify-file: output-lowercase.txt expected: expected-lowercase.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,
        hash_transform=lambda line: line.lower()  # (1)!
    )

    with open("input.txt") as f:
        with open("output-lowercase.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Python API: use function to transform for comparison

???+ success "Output: Duplicates removed"
    ```text hl_lines="1-3"
    --8<-- "features/hash-transform/fixtures/expected-lowercase.txt"
    ```

    **Result**: Only 3 lines remain. The second sequence (lines 4-6) was removed because it matches the first when case is normalized.

## How It Works

### Transformation Pipeline

When hash-transform is enabled, each line goes through this process:

```
Original line
     ↓
┌────────────────────┐
│  Shell Command     │  ← Transform for hashing only
│  (tr, cut, sed...) │
└────────────────────┘
     ↓
  Transformed text
     ↓
  Hash function
     ↓
  Hash value  ────────→  Used for comparison

Original line  ────────→  Written to output (unchanged!)
```

**Critical point**: The transformation only affects comparison. Original lines are always output as-is.

### Example Transformation

```
Input:  "ERROR: Connection timeout"
           ↓ tr '[:upper:]' '[:lower:]'
        "error: connection timeout"
           ↓ Hash
        7a3f9b2c...  (hash value)

Input:  "error: connection timeout"
           ↓ tr '[:upper:]' '[:lower:]'
        "error: connection timeout"
           ↓ Hash
        7a3f9b2c...  (same hash!)

→ Duplicate detected, second occurrence removed
```

Both lines produce the same hash after transformation, so they're treated as duplicates.

## Common Use Cases

### Case-Insensitive Matching

```bash
# Ignore case differences
uniqseq log.txt --hash-transform "tr '[:upper:]' '[:lower:]'"

# Alternative using awk
uniqseq log.txt --hash-transform "awk '{print tolower(\$0)}'"
```

### Field Extraction

```bash
# Compare only message field (after pipe)
uniqseq timestamped.log --hash-transform "cut -d'|' -f2-"

# Example input:
#   2024-01-01 10:00:00 | Error: Database timeout
#   2024-01-02 15:30:00 | Error: Database timeout
# → Second line removed (same message after timestamp)

# Extract specific columns
uniqseq csv.txt --hash-transform "cut -d',' -f3,5"
```

### Whitespace Normalization

```bash
# Collapse multiple spaces to single space
uniqseq data.txt --hash-transform "tr -s ' '"

# Remove all whitespace
uniqseq data.txt --hash-transform "tr -d ' \t'"
```

### Pattern Removal

```bash
# Remove timestamps at start of line
uniqseq log.txt --hash-transform "sed 's/^[0-9-]* [0-9:]* //'"

# Remove bracketed prefixes like [INFO], [ERROR]
uniqseq log.txt --hash-transform "sed 's/^\[[^]]*\] //'"
```

### Combining with Skip-Chars

You can use both `--skip-chars` and `--hash-transform` together:

```bash
# Skip first 20 chars, then extract field 2
uniqseq log.txt --skip-chars 20 --hash-transform "cut -d':' -f2-"
```

Order of operations:
1. Skip first N characters
2. Apply hash transform to remaining text
3. Hash the result

## Choosing the Right Transform

### Test Your Transform First

Before using with uniqseq, verify the transform does what you expect:

```bash
# Test your transform on a sample line
echo "ERROR: Connection timeout" | tr '[:upper:]' '[:lower:]'
# Output: error: connection timeout

# Test on multiple lines
head -5 log.txt | cut -d'|' -f2-
# Verify it extracts the right part
```

### Common Shell Commands

**Case conversion**:
- `tr '[:upper:]' '[:lower:]'` - lowercase
- `tr '[:lower:]' '[:upper:]'` - uppercase

**Field extraction**:
- `cut -d'|' -f2-` - extract fields 2+ (pipe delimiter)
- `cut -c 10-` - extract characters 10+
- `awk '{print $2}'` - extract second field (space delimiter)

**Pattern removal**:
- `sed 's/pattern//'` - remove pattern
- `sed 's/^prefix//'` - remove prefix
- `tr -d 'chars'` - delete specific characters

**Whitespace handling**:
- `tr -s ' '` - collapse multiple spaces
- `sed 's/^[[:space:]]*//'` - remove leading whitespace

### Transform Requirements

**Must output exactly one line**:
```bash
# ✅ Good: single line output
uniqseq log.txt --hash-transform "tr '[:upper:]' '[:lower:]'"

# ❌ Bad: multiple lines
uniqseq log.txt --hash-transform "fold -w 40"
# Error: Transform produced multiple lines
```

**Exit code doesn't matter**:
```bash
# Transform can fail (exit non-zero)
# Empty output is treated as empty line
uniqseq log.txt --hash-transform "grep PATTERN"
# Lines without PATTERN → empty output → same hash
```

### Performance Considerations

Hash transforms spawn a shell process for each line:

```bash
# Fast: simple shell built-ins
tr '[:upper:]' '[:lower:]'  # Very fast
cut -d'|' -f2-               # Very fast

# Slower: complex sed/awk
sed 's/complex.*regex//'     # Still reasonable

# Slow: external programs
python -c "import sys; ..."  # Much slower
```

For large files, prefer simple commands like `tr`, `cut`, or basic `sed`.

## Rule of Thumb

**Use hash-transform when you need flexible comparison logic** that can't be expressed with skip-chars alone.

- **Case-insensitive**: `tr '[:upper:]' '[:lower:]'`
- **Field extraction**: `cut` or `awk`
- **Pattern removal**: `sed`
- **Test your transform** on sample data first
- **Keep it simple** for better performance

## See Also

- [CLI Reference](../../reference/cli.md) - Complete `--hash-transform` documentation
- [Ignoring Prefixes](../skip-chars/skip-chars.md) - Simpler alternative for fixed prefixes
- [Common Patterns](../../guides/common-patterns.md) - More transformation examples
