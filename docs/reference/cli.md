# CLI Reference

Complete reference for the `uniqseq` command-line interface.

## Command Syntax

```bash
uniqseq [OPTIONS] [INPUT_FILE]
```

## Basic Usage

```bash
# Deduplicate a file
uniqseq session.log > output.log

# Process from stdin
cat session.log | uniqseq > output.log

# Custom window size
uniqseq --window-size 5 session.log
```

## Options Reference

### Core Options

#### `--window-size, -w`
**Type**: Integer
**Default**: 10
**Min**: 1

Minimum sequence length to detect (lines buffered and compared before output).

```bash
uniqseq --window-size 15 input.log
```

#### `--max-history, -m`
**Type**: Integer
**Default**: 100000
**Min**: 100

Maximum depth of history (lines matched against). Controls memory usage.

```bash
uniqseq --max-history 50000 input.log
# Or use shortcut
uniqseq -m 50000 input.log
```

#### `--unlimited-history, -M`
**Type**: Boolean
**Default**: False

Unlimited history depth. Suitable for file processing (use caution with streaming). Auto-enabled for file inputs.

```bash
uniqseq --unlimited-history input.log
# Or use shortcut
uniqseq -M input.log
```

#### `--max-unique-sequences, -u`
**Type**: Integer
**Default**: 10000
**Min**: 1

Maximum number of unique sequences to track for newly identified sequences. Uses LRU eviction when limit is reached. Preloaded sequences (from `--read-sequences` or `--library-dir`) are not subject to this limit and are never evicted.

```bash
uniqseq --max-unique-sequences 5000 input.log
# Or use shortcut
uniqseq -u 5000 input.log
```

#### `--unlimited-unique-sequences, -U`
**Type**: Boolean
**Default**: False

Unlimited unique sequence tracking for newly identified sequences. Suitable for file processing (use caution with streaming). Mutually exclusive with `--max-unique-sequences`. Preloaded sequences are always retained regardless of this setting.

```bash
uniqseq --unlimited-unique-sequences input.log
# Or use shortcut
uniqseq -U input.log
```

#### `--max-candidates, -c`
**Type**: Integer
**Default**: 1000
**Min**: 1

Maximum concurrent candidates to track during sequence matching. Lower values improve performance but may miss some patterns. Higher values are more accurate but slower.

**Performance trade-offs**:
- `30-50`: Fast, may miss ~10% of patterns
- `100` (default): Balanced, may miss ~5% of patterns
- `200+`: Slower, catches most patterns
- Unlimited: Slowest, 100% accurate (see `--unlimited-candidates`)

```bash
# Faster processing
uniqseq --max-candidates 30 large-file.log

# More accurate
uniqseq --max-candidates 200 input.log

# Or use shortcut
uniqseq -c 50 input.log
```

#### `--unlimited-candidates, -C`
**Type**: Boolean
**Default**: False

Unlimited candidate tracking for maximum accuracy. Finds all patterns but slower than limited tracking. Suitable for comprehensive analysis where accuracy is critical. Mutually exclusive with `--max-candidates`.

```bash
uniqseq --unlimited-candidates important-data.log

# Or use shortcut
uniqseq -C input.log
```

### Line Processing Options

#### `--skip-chars, -s`
**Type**: Integer
**Default**: 0
**Min**: 0

Skip N characters from start of each line when hashing (e.g., to ignore timestamps).

```bash
# Skip timestamp prefix "[2024-01-15 10:30:01] "
uniqseq --skip-chars 21 app.log
```

#### `--hash-transform`
**Type**: String

Pipe each line through a shell command for hashing (preserves original output).

```bash
# Only hash the log level and message
uniqseq --hash-transform "awk '{print \$4, \$5, \$6}'" app.log
```

### Delimiter Options

#### `--delimiter, -d`
**Type**: String
**Default**: `\n`

Record delimiter. Supports escape sequences: `\n`, `\t`, `\0`.

```bash
# Use null delimiter
uniqseq --delimiter '\0' input.txt
```

#### `--delimiter-hex`
**Type**: String

Hex delimiter (e.g., '00' or '0x0a0d'). Requires `--byte-mode`.

```bash
# Use null byte as delimiter
uniqseq --byte-mode --delimiter-hex 00 input.bin
```

#### `--byte-mode`
**Type**: Boolean
**Default**: False

Process files in binary mode (for binary data, mixed encodings).

```bash
uniqseq --byte-mode input.bin
```

### Filter Options

#### `--track`
**Type**: String (can specify multiple times)

Include lines matching regex pattern for deduplication. First matching pattern wins.

```bash
# Only deduplicate ERROR lines
uniqseq --track '^ERROR' app.log
```

#### `--bypass`
**Type**: String (can specify multiple times)

Bypass deduplication for lines matching regex pattern (pass through unchanged).

```bash
# Never deduplicate WARN lines
uniqseq --bypass '^WARN' app.log
```

#### `--track-file`
**Type**: Path (can specify multiple times)

Load track patterns from file (one regex per line, # for comments).

```bash
uniqseq --track-file error-patterns.txt app.log
```

#### `--bypass-file`
**Type**: Path (can specify multiple times)

Load bypass patterns from file (one regex per line, # for comments).

```bash
uniqseq --bypass-file bypass-patterns.txt app.log
```

### Library Options

#### `--read-sequences`
**Type**: Path (can specify multiple times)

Load sequences from directory. Treats loaded sequences as "already seen".

```bash
uniqseq --read-sequences ~/patterns/common app.log
```

#### `--library-dir`
**Type**: Path

Library directory: load existing sequences and save observed sequences.

```bash
uniqseq --library-dir ~/uniqseq-library app.log
```

### Output Options

#### `--inverse`
**Type**: Boolean
**Default**: False

Inverse mode: keep duplicates, remove unique sequences. Outputs only lines that appear in duplicate sequences (2+ times).

```bash
# Show only repeated patterns
uniqseq --inverse app.log
```

#### `--annotate`
**Type**: Boolean
**Default**: False

Add inline markers showing where duplicates were skipped.

```bash
uniqseq --annotate app.log
```

Example output:
```
Line 1
Line 2
Line 3
[DUPLICATE: Lines 105-107 matched lines 1-3 (sequence seen 2 times)]
```

#### `--annotation-format`
**Type**: String

Custom annotation template. Variables: `{start}`, `{end}`, `{match_start}`, `{match_end}`, `{count}`, `{window_size}`.

```bash
uniqseq --annotate --annotation-format "SKIP|{start}|{end}|{count}" app.log
```

Example output:
```
Line 1
Line 2
Line 3
SKIP|105|107|2
```

### Display Options

#### `--quiet, -q`
**Type**: Boolean
**Default**: False

Suppress statistics output to stderr.

```bash
uniqseq --quiet input.log
```

#### `--progress, -p`
**Type**: Boolean
**Default**: False

Show progress indicator (auto-disabled for pipes).

```bash
uniqseq --progress large-file.log
```

#### `--stats-format`
**Type**: String (table | json)
**Default**: table

Statistics output format: 'table' (Rich table) or 'json' (machine-readable).

```bash
uniqseq --stats-format json input.log
```

#### `--explain`
**Type**: Boolean
**Default**: False

Show explanations to stderr for why lines were kept or skipped.

Outputs diagnostic messages showing deduplication decisions:
- When duplicate sequences are skipped
- Which historical sequences were matched
- When lines are bypassed by filter patterns

```bash
# See all deduplication decisions
uniqseq --explain input.log 2> explain.log

# Debug with quiet mode (only explanations, no stats)
uniqseq --explain --quiet input.log

# Validate filter patterns
uniqseq --explain --bypass "^INFO" input.log 2>&1 | grep EXPLAIN
```

Example output:
```
EXPLAIN: Lines 5-7 skipped (duplicate of lines 1-3, seen 2x)
EXPLAIN: Line 10 bypassed (matched bypass pattern '^DEBUG')
```

See [Explain Mode](../features/explain/explain.md) for detailed usage.

### Version Information

#### `--version`
**Type**: Boolean
**Default**: False

Show version and exit.

```bash
uniqseq --version
```

Example output:
```
uniqseq version 0.1.0
```

## Option Combinations

### Mutually Exclusive Options

- `--unlimited-history` and `--max-history`: Use one or the other
- `--delimiter` and `--delimiter-hex`: Use one or the other
- `--annotation-format` requires `--annotate`

### Mode Dependencies

- `--delimiter-hex` requires `--byte-mode`
- Filter patterns (`--track`, `--bypass`) require text mode (incompatible with `--byte-mode`)

## Examples

### Basic Deduplication

```bash
# Remove duplicate sequences (default: 10+ lines)
uniqseq session.log > output.log
```

### Custom Window Size

```bash
# Detect smaller sequences (3+ lines)
uniqseq --window-size 3 app.log

# Detect larger sequences (20+ lines)
uniqseq --window-size 20 verbose.log
```

### Ignoring Timestamps

```bash
# Skip timestamp prefix when comparing
uniqseq --skip-chars 21 app.log
```

### Pattern Filtering

```bash
# Only deduplicate ERROR lines
uniqseq --track '^ERROR' app.log

# Deduplicate all except WARN lines
uniqseq --bypass '^WARN' app.log

# Deduplicate only ERROR and FATAL lines
uniqseq --track '^ERROR' --track '^FATAL' app.log
```

### Library Mode

```bash
# Load known patterns and save new ones
uniqseq --library-dir ~/patterns session.log
```

### Analysis Mode

```bash
# Show only duplicate sequences (for analysis)
uniqseq --inverse --annotate app.log
```

### Binary Data

```bash
# Process binary files with null delimiter
uniqseq --byte-mode --delimiter-hex 00 binary.dat
```

## Statistics Output

### Table Format (Default)

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┓
┃ Metric                   ┃  Value ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━┩
│ Total lines processed    │ 10,000 │
│ Lines emitted            │  8,500 │
│ Lines skipped            │  1,500 │
│ Redundancy               │  15.0% │
│ Unique sequences tracked │     12 │
│ Window size              │     10 │
│ Max history              │ 10,000 │
└──────────────────────────┴────────┘
```

### JSON Format

```json
{
  "statistics": {
    "lines": {
      "total": 10000,
      "emitted": 8500,
      "skipped": 1500
    },
    "redundancy_pct": 15.0,
    "sequences": {
      "unique_tracked": 12
    }
  },
  "configuration": {
    "window_size": 10,
    "max_history": 10000,
    "skip_chars": 0
  }
}
```

## Exit Codes

- **0**: Success
- **1**: Error (invalid arguments, file not found, processing error)

## See Also

- [UniqSeq API](uniqseq.md) - Core deduplication class
- [Library Usage](library.md) - Python library usage
- [Basic Concepts](../getting-started/basic-concepts.md) - Understanding how uniqseq works
