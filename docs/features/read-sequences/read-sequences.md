# Read-Only Sequence Loading

The `--read-sequences` flag loads pre-defined patterns from directories without
modifying them. This allows you to apply reference patterns, vendor-provided
error lists, or baseline sequences for consistent filtering.

## What It Does

Read-sequences mode applies external patterns without persistence:

- **Read**: Load sequences from directory
- **Apply**: Treat loaded patterns as already seen
- **No Write**: Never modify the source directory
- **Use case**: Apply external reference patterns, baseline filtering

**Key insight**: Use read-sequences when you want to filter against known
patterns but don't want to build or modify a pattern library.

## Example: Filtering Known Errors

This example shows processing logs with vendor-provided error patterns. The
error patterns are loaded from a reference directory and applied without
modification.

???+ note "Reference patterns: Known database errors"
    ```text
    $ cat known-patterns/*.uniqseq
    ERROR: Database connection timeout
      at db.connect()
      retry in 5s
    ```

    **Pattern**: 3-line database error from vendor documentation

???+ note "Input: Application logs with known errors"
    ```text
    --8<-- "features/read-sequences/fixtures/input.txt"
    ```

    **Contains**: Database error appears twice (both will be filtered)

### Process with Reference Patterns

Apply the known error patterns without modifying them:

<!-- verify-file: output.txt expected: expected-filtered.txt -->
```console
$ uniqseq input.txt --window-size 3 \
    --read-sequences known-patterns --quiet > output.txt
```

???+ success "Output: Known errors filtered out"
    ```text
    --8<-- "features/read-sequences/fixtures/expected-filtered.txt"
    ```

    **Result**: Both database error occurrences removed (12 lines → 7 lines).
    The known pattern was recognized immediately.

## How It Works

### Read-Only Loading

```
┌──────────────────┐
│ Reference        │
│ Patterns         │
│                  │
│ known-patterns/  │
│   error1.uniqseq │◄─── Read-only
│   error2.uniqseq │     (never modified)
│   error3.uniqseq │
└──────────────────┘
         │
         │ Load once
         │ at startup
         ▼
  ┌──────────────┐
  │   uniqseq    │
  │              │
  │  Processing  │
  └──────────────┘
```

### Multiple Directories

You can load from multiple reference directories:

```bash
# Load patterns from multiple sources
uniqseq app.log --window-size 3 \
    --read-sequences vendor-errors/ \
    --read-sequences team-patterns/ \
    --read-sequences baseline/
```

**All patterns combined**: Patterns from all directories are loaded and
applied together.

## Common Use Cases

### Vendor Error Filtering

```bash
# Vendor provides known error patterns
# Your app: filter those out to see novel issues
uniqseq app.log --window-size 4 \
    --read-sequences vendor-known-issues/ \
    > novel-issues.log
```

### Baseline Comparison

```bash
# Establish baseline from production
uniqseq prod-baseline.log --window-size 5 \
    --library-dir baseline/ --quiet

# Filter test logs against baseline
# Only patterns NOT in baseline appear in output
uniqseq test-run.log --window-size 5 \
    --read-sequences baseline/sequences/ \
    > test-novel-patterns.log
```

### Team Reference Patterns

```bash
# Team maintains reference patterns in git repo
# Everyone filters against same references
git clone team-references.git refs/

# Process logs with team references (read-only)
uniqseq local.log --window-size 3 \
    --read-sequences refs/common-errors/
```

### Configuration Management

```bash
# Load multiple pattern sets based on environment
case "$ENV" in
  prod)
    REF="--read-sequences prod-patterns/"
    ;;
  staging)
    REF="--read-sequences staging-patterns/ \
         --read-sequences prod-patterns/"
    ;;
  dev)
    REF="--read-sequences dev-patterns/"
    ;;
esac

uniqseq app.log --window-size 4 $REF
```

## Combining with Library Mode

Use both read-only patterns and read-write library together:

```bash
# Load vendor patterns (read-only)
# AND maintain your own library (read-write)
uniqseq app.log --window-size 3 \
    --read-sequences vendor-errors/ \
    --library-dir local-patterns/
```

**Behavior**:
- **vendor-errors/**: Loaded but never modified
- **local-patterns/**: Loaded AND updated with new patterns
- Both sets of patterns used for deduplication

**Use case**: Use external reference patterns while building your own library
of application-specific patterns.

## Difference from Library Mode

| Feature | `--read-sequences` | `--library-dir` |
|---------|-------------------|-----------------|
| **Read patterns** | ✅ Yes | ✅ Yes |
| **Write patterns** | ❌ No | ✅ Yes |
| **Modifies source** | ❌ Never | ✅ Adds sequences |
| **Creates metadata** | ❌ No | ✅ Yes |
| **Use case** | External references | Pattern accumulation |
| **Multiple dirs** | ✅ Yes | ❌ No (single dir) |

**When to use each**:
- **read-sequences**: Applying external, unchanging reference patterns
- **library-dir**: Building and maintaining your own growing pattern library

## Pattern Directory Structure

Read-sequences expects the same directory structure as library sequences:

```
known-patterns/
└── files containing text or byte data
```

**Compatible with**:
- Library directories: `--read-sequences library/sequences/`
- Standalone pattern directories: `--read-sequences patterns/`
- Any directory containing files with text or byte data to match

## Creating Reference Patterns

### From Existing Logs

```bash
# Build reference library from known-good logs
uniqseq baseline.log --window-size 3 \
    --library-dir temp-lib/ --quiet

# Use sequences as read-only reference
cp -r temp-lib/sequences/ reference-patterns/
rm -rf temp-lib/

# Apply reference patterns to new logs
uniqseq new-logs.log --window-size 3 \
    --read-sequences reference-patterns/
```

### Manual Pattern Creation

Create `.uniqseq` files manually with pattern content:

```bash
mkdir -p custom-patterns/

# Create pattern file (filename doesn't matter, use hash or description)
cat > custom-patterns/db-timeout.uniqseq << 'EOF'
ERROR: Database connection timeout
  at db.connect()
  retry in 5s
EOF

# Use custom patterns
uniqseq app.log --window-size 3 \
    --read-sequences custom-patterns/
```

**File naming**: The filename doesn't affect pattern matching. Use descriptive
names or hashes for organization.

## Pattern File Format

Sequence files contain the multi-line pattern:

```
Line 1 of pattern
Line 2 of pattern
Line 3 of pattern
```

**Encoding**:
- Text mode: UTF-8 text with configured delimiter (default: newline)
- Byte mode: Raw bytes with configured delimiter (default: newline)

**Window size**: Window size must be equal to or smaller than the pattern
(`--window-size 3` requires patterns with 3 or more lines).

## Limitations

### Window Size Requirements

Window size must be equal to or smaller than the pattern:

```bash
# Create 3-line patterns
uniqseq baseline.log --window-size 3 --library-dir lib/

# Works: 3-line patterns work with window-size 3
uniqseq new.log --window-size 3 --read-sequences lib/sequences/

# Won't match: window-size 5 too large for 3-line patterns
# (Window size 5 requires patterns with 5+ lines)
uniqseq new.log --window-size 5 --read-sequences lib/sequences/
```

**Best practice**: Keep pattern window size and processing window size
consistent for reliable matching.

### Pattern Count Performance

Loading many patterns has minimal overhead:

- **Load time**: O(number of patterns × pattern size)
- **Memory**: All patterns loaded into memory at startup
- **Matching**: Same as normal operation

Libraries with thousands of patterns load in milliseconds.

### Mode Consistency

For best results, create patterns in the same mode you'll use them:

```bash
# Create text patterns
uniqseq app.log --library-dir patterns/

# Use text patterns in text mode
uniqseq new.log --read-sequences patterns/sequences/

# Create byte-mode patterns
uniqseq binary.log --byte-mode --library-dir binary-patterns/

# Use byte patterns in byte mode
uniqseq new-binary.log --byte-mode --read-sequences binary-patterns/sequences/
```

**Note**: While any file can be read in byte mode, patterns created in text
mode may not match effectively when processing in byte mode due to encoding
differences.

## Validation and Errors

uniqseq validates pattern directories on load:

```bash
# Invalid window size
$ uniqseq app.log --window-size 5 --read-sequences 3-line-patterns/
Error: Pattern window size mismatch

# Missing directory
$ uniqseq app.log --read-sequences missing-dir/
Error: Directory not found: missing-dir/

# Invalid pattern file
$ uniqseq app.log --read-sequences patterns/
Error loading sequences: Invalid format in pattern.uniqseq
```

## Performance Note

Read-sequences has minimal overhead:
- **Startup**: Load patterns once at beginning (milliseconds)
- **Runtime**: Same as normal operation
- **Memory**: All patterns loaded into memory (minimal for typical use)
- **No disk I/O**: After initial load, no file access

## When to Use Read-Sequences

**Use read-sequences when:**
- Applying external reference patterns
- Filtering against vendor-provided error lists
- Using baseline patterns from production
- Pattern set should not be modified
- Loading from multiple reference directories
- Sharing read-only patterns across team

**Use library-dir when:**
- Building pattern library over time
- Want to save newly discovered patterns
- Maintaining growing knowledge base
- Need processing metadata and history

**Use both when:**
- Have external references AND building own library
- Need read-only patterns plus pattern accumulation

## See Also

- [Library Mode](../library-dir/library-dir.md) - Read-write pattern libraries
- [CLI Reference](../../reference/cli.md) - Complete read-sequences documentation
- [Pattern Filtering](../pattern-filtering/pattern-filtering.md) - Selective deduplication
