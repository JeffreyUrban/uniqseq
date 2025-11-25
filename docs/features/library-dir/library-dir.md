# Library Mode

The `--library-dir` flag enables persistent pattern libraries that remember
sequences across runs. This allows you to build a knowledge base of known
patterns and apply it consistently across multiple files or processing
sessions.

## What It Does

Library mode creates a reusable collection of patterns:

- **Read**: Load previously discovered sequences from library
- **Write**: Save newly discovered sequences to library
- **Persist**: Maintain pattern library across multiple runs
- **Use case**: Consistent deduplication across related files

**Key insight**: Library mode turns deduplication from a one-time operation
into a persistent knowledge base that grows and improves over time.

## Example: Building a Pattern Library

This example shows processing logs with library mode. The first run discovers
patterns and saves them. Subsequent runs reuse those patterns for consistent
deduplication.

???+ note "Input: Application logs with repeated errors"
    ```text
    --8<-- "features/library-dir/fixtures/input.txt"
    ```

    **Pattern**: 3-line error sequence repeats three times

### First Run: Create Library

Process the first file and build a pattern library:

<!-- verify-file: output.txt expected: expected-deduplicated.txt -->
```console
$ uniqseq input.txt --window-size 3 --library-dir library \
    --quiet > output.txt
```

???+ success "Output: Deduplicated logs"
    ```text
    --8<-- "features/library-dir/fixtures/expected-deduplicated.txt"
    ```

    **Result**: 6 duplicate lines removed (11 lines → 5 lines)

### Library Structure Created

The library directory stores discovered patterns:

```text
$ tree library
library/
├── metadata-20251125-144204-290932/
│   └── config.json
└── sequences/
    └── d1677e5d439343cbfc8c3d3f7d012823.uniqseq
```

**What was created**:
- `sequences/` - Directory containing pattern files (`.uniqseq`)
- `metadata-*/` - Processing metadata with timestamp
- `config.json` - Configuration and statistics for this run

### Examining Library Contents

View the stored pattern:

```text
$ cat library/sequences/*.uniqseq
ERROR: Connection failed
  at network.connect()
  retrying in 5s
```

View processing metadata:

```json
{
  "timestamp": "2025-11-25T14:42:04.292981+00:00",
  "window_size": 3,
  "mode": "text",
  "delimiter": "\\n",
  "max_history": "unlimited",
  "sequences_discovered": 1,
  "sequences_preloaded": 0,
  "sequences_saved": 1,
  "total_records_processed": 11,
  "records_skipped": 6
}
```

**Metadata includes**:
- When the library was used
- What configuration was applied
- How many patterns were loaded vs discovered
- Processing statistics

### Second Run: Reuse Library

Process a new file using the existing library:

```text
$ uniqseq new-logs.txt --window-size 3 --library-dir library \
    --quiet > clean-logs.txt
```

**What happens**:
- Loads existing patterns from library (1 pattern preloaded)
- Applies those patterns to new file immediately
- Saves any newly discovered patterns back to library
- Creates new metadata directory for this run

## How It Works

### Read-Write Cycle

```
┌─────────────┐
│   Library   │
│             │
│ sequences/  │◄────┐
│  pattern1   │     │
│  pattern2   │     │ Save new
│  pattern3   │     │ patterns
└─────────────┘     │
       │            │
       │ Load       │
       │ patterns   │
       ▼            │
┌─────────────┐     │
│  uniqseq    │─────┘
│             │
│ Processing  │
└─────────────┘
```

### Library Benefits

1. **Consistency**: Same patterns recognized across all files
2. **Efficiency**: No need to rediscover known patterns
3. **Accumulation**: Library grows smarter over time
4. **Auditability**: Metadata tracks when patterns were added

## Common Use Cases

### Multi-File Processing

```bash
# Process multiple log files with shared library
for log in app-*.log; do
    uniqseq "$log" --library-dir patterns --window-size 5 \
        --quiet > "clean-$log"
done

# All files deduplicated consistently using same patterns
# Library grows as new patterns are discovered
```

### Daily Log Processing

```bash
# Day 1: Start library
uniqseq app-2025-01-01.log --library-dir app-patterns \
    --window-size 4 > clean-01.log

# Day 2: Library has yesterday's patterns
uniqseq app-2025-01-02.log --library-dir app-patterns \
    --window-size 4 > clean-02.log

# Day 3: Library has patterns from day 1 and 2
uniqseq app-2025-01-03.log --library-dir app-patterns \
    --window-size 4 > clean-03.log
```

### Team Shared Libraries

```bash
# Share pattern library across team
git clone team-patterns.git library/

# Process files using team's known patterns
uniqseq local-logs.txt --library-dir library --window-size 3

# Commit newly discovered patterns back
cd library/
git add sequences/
git commit -m "Add patterns from local-logs processing"
git push
```

### Baseline Establishment

```bash
# Establish baseline from known-good logs
uniqseq baseline.log --library-dir known-patterns \
    --window-size 5 --quiet

# Process production logs against baseline
uniqseq prod.log --library-dir known-patterns \
    --window-size 5 > novel-events.log

# novel-events.log contains only patterns NOT in baseline
```

## Combining with Read-Only Sequences

Library mode (`--library-dir`) can be combined with read-only sequences
(`--read-sequences`):

```bash
# Load read-only reference patterns AND use read-write library
uniqseq app.log \
    --read-sequences vendor-errors.txt \
    --library-dir local-patterns \
    --window-size 4
```

**Behavior**:
- `--read-sequences`: Loads patterns but doesn't save them
- `--library-dir`: Loads patterns AND saves new ones
- Both sets of patterns are used for deduplication

**Use case**: Use vendor-provided patterns as reference, maintain your own
library for application-specific patterns.

## Library File Format

### Sequence Files (`.uniqseq`)

Each sequence file contains one multi-line pattern:

```
Line 1 of pattern
Line 2 of pattern
Line 3 of pattern
```

**Filename**: Hash of the pattern (e.g., `d1677e5d.uniqseq`)

**Encoding**:
- Text mode: UTF-8 text with newlines
- Byte mode: Raw bytes

### Metadata Files (`config.json`)

Each run creates a metadata directory with configuration:

```json
{
  "timestamp": "2025-11-25T14:42:04.292981+00:00",
  "window_size": 3,
  "mode": "text",
  "delimiter": "\\n",
  "max_history": "unlimited",
  "sequences_discovered": 1,
  "sequences_preloaded": 0,
  "sequences_saved": 1,
  "total_records_processed": 11,
  "records_skipped": 6
}
```

**Purpose**: Track when library was used, with what configuration, and what
patterns were added.

## Limitations

### Window Size Consistency

Patterns in library must match the window size used:

```bash
# Create library with window-size 3
uniqseq app.log --library-dir lib --window-size 3

# ERROR: Can't use library with different window size
uniqseq app.log --library-dir lib --window-size 5
# Error: Window size mismatch
```

**Solution**: Use separate libraries for different window sizes, or only load
patterns that match your window size.

### No Pattern Management Tools

The library is just files on disk. To manage patterns:

```bash
# List patterns
ls library/sequences/

# Remove specific pattern
rm library/sequences/d1677e5d439343cbfc8c3d3f7d012823.uniqseq

# Clear all patterns
rm -rf library/sequences/*.uniqseq

# Archive old metadata
mv library/metadata-2025* archive/
```

### Binary vs Text Mode

Libraries created in text mode can't be used in byte mode and vice versa:

```bash
# Create library in text mode
uniqseq app.log --library-dir lib --window-size 3

# ERROR: Can't use text library in byte mode
uniqseq binary.log --library-dir lib --byte-mode --window-size 3
```

**Solution**: Use separate libraries for text and binary processing.

## When to Use Library Mode

**Use library mode when:**
- Processing multiple related files
- Building a knowledge base of patterns over time
- Need consistent deduplication across runs
- Working with recurring patterns across files
- Sharing patterns across team or systems

**Use read-sequences when:**
- One-time processing with known patterns
- Patterns shouldn't be modified
- Don't need to save newly discovered patterns
- Just want to apply external reference patterns

**Use neither when:**
- Processing single file once
- Each file has unique patterns
- Don't need pattern persistence

## Performance Note

Library mode has minimal overhead:
- Load time: Proportional to number of patterns in library
- Save time: Only saves newly discovered patterns
- Memory: Same as normal operation (patterns loaded into uniqseq)
- Disk: One small file per unique pattern discovered

Libraries with thousands of patterns load in milliseconds.

## See Also

- [CLI Reference](../../reference/cli.md) - Complete library-dir documentation
- [Pattern Filtering](../pattern-filtering/pattern-filtering.md) - Selective deduplication
- [Window Size](../window-size/window-size.md) - Choosing the right window size
