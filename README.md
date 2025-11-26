# uniqseq

Deduplicate repeated sequences of lines in text streams and files.

A Unix-style filter that detects and removes repeated multi-line patterns from text input. Like `uniq` but for sequences of lines instead of single lines.

## What Makes It Different

Most deduplication tools work line-by-line. `uniqseq` detects when **sequences** of lines repeat:

```text
# Input
Starting process...
Loading config
Connecting to DB
Starting process...
Loading config
Connecting to DB
Done

# Output
Starting process...
Loading config
Connecting to DB
Done
```

Perfect for cleaning up verbose output, repeated error traces, or any text with multi-line patterns.

## Features

- **Sequence detection**: Identifies repeated multi-line patterns using rolling hash
- **Streaming mode**: Process stdin or files directly
- **Memory efficient**: Configurable history depth for bounded memory usage
- **Order preserving**: Keeps first occurrence of each sequence
- **Fast**: O(1) hash-based lookups with linear time complexity
- **Progress display**: Optional live progress with statistics
- **Pattern filtering**: Include/exclude lines from deduplication with regex patterns
- **Annotations**: Mark where duplicates were skipped with customizable markers
- **Inverse mode**: Show only duplicates instead of unique content
- **Sequence libraries**: Save and reuse pattern libraries across sessions

## Installation

### From Source

```bash
git clone https://github.com/JeffreyUrban/uniqseq
cd uniqseq
pip install .
```

### Development Installation

```bash
git clone https://github.com/JeffreyUrban/uniqseq
cd uniqseq
pip install -e ".[dev]"
```

### Future: PyPI and Homebrew (Coming Soon)

Package distribution via PyPI and Homebrew will be available in a future release.

## Platform Support

- **Linux**: From source (pip), PyPI/Homebrew coming soon
- **macOS**: From source (pip), Homebrew coming soon
- **Windows**: From source (pip), PyPI coming soon

## Usage

```bash
# Streaming mode (pipe input)
cat verbose.log | uniqseq > clean.log
command-with-verbose-output | uniqseq

# File mode
uniqseq input.txt > output.txt

# Configure sequence length
uniqseq --window-size 5 < input.txt    # Look for 5-line patterns
uniqseq --window-size 15 < input.txt   # Look for 15-line patterns

# Show progress and statistics
uniqseq --progress input.txt > output.txt

# Quiet mode (no statistics)
uniqseq --quiet input.txt > output.txt
```

## Common Use Cases

- **Terminal output**: Clean up verbose CLI tool output (e.g., from `script` command)
- **Log processing**: Remove repeated error stacks or debug traces
- **Test output**: Deduplicate repeated test failures or warnings
- **ETL pipelines**: Filter redundant multi-line records
- **Monitoring**: Reduce noise from repeated alert patterns
- **Documentation**: Clean up example output with repetition

## How It Works

`uniqseq` uses a sliding window with rolling hash to detect duplicate sequences:

1. Maintains a FIFO buffer of N lines (window size, default: 10)
2. For each new line:
   - Adds line to buffer
   - When buffer is full, hashes the current window
   - Checks if window hash exists in history
   - If duplicate: discards buffer and skips sequence
   - If unique: adds to history, emits oldest line from buffer
3. At EOF, emits remaining buffered lines

The deque-based buffer ensures memory usage stays bounded even with large files.

## Options

```
uniqseq [OPTIONS] [FILE]

Arguments:
  [FILE]    Input file to deduplicate (reads from stdin if not specified)

Core Options:
  -w, --window-size INTEGER       Minimum sequence length to detect [default: 10]
  -m, --max-history INTEGER       Maximum depth of history [default: 10000]
      --unlimited-history         Use unlimited history (auto-enabled for files)

Pattern Filtering:
  --track TEXT                    Apply dedup only to lines matching regex
  --bypass TEXT                   Bypass dedup for lines matching regex
  --track-file PATH               Load track patterns from file
  --bypass-file PATH              Load bypass patterns from file

Annotations & Inspection:
  --annotate                      Add markers showing where duplicates were skipped
  --annotation-format TEXT        Custom annotation template (requires --annotate)
  --inverse                       Show only duplicates (opposite of normal mode)

Sequence Libraries:
  --library-dir PATH              Save/load sequence patterns
  --read-sequences PATH           Load patterns (read-only)

Output Control:
  -q, --quiet                     Suppress statistics output to stderr
  -p, --progress                  Show progress indicator (auto-disabled for pipes)

Other:
  -h, --help                      Show this message and exit
  --version                       Show version and exit
```

See `uniqseq --help` for complete options list.

## Examples

### Cleaning Build Output

```bash
# Remove repeated compiler warnings
make 2>&1 | uniqseq --window-size 3
```

### Processing Application Logs

```bash
# Remove repeated stack traces (assuming 10-line traces)
uniqseq --window-size 10 < app.log > clean.log
```

### Terminal Session Cleanup

```bash
# Clean up repeated command outputs
script -q session.txt
uniqseq session.txt > cleaned.txt
```

### Pipeline Integration

```bash
# Use in complex pipelines
tail -f /var/log/app.log | \
  grep ERROR | \
  uniqseq --window-size 5 | \
  your-alert-system
```

### Annotations (Show Where Duplicates Were Skipped)

```bash
# Add markers showing what was deduplicated
uniqseq --annotate app.log > annotated.log

# Custom annotation format
uniqseq --annotate --annotation-format '... {count}x duplicate ...' app.log

# Machine-readable format
uniqseq --annotate --annotation-format 'SKIP|{start}|{end}|{count}' app.log
```

### Inverse Mode (Show Only Duplicates)

```bash
# Find only duplicated sequences
uniqseq --inverse app.log > duplicates.log

# Analyze which errors repeat most
uniqseq --track 'ERROR' --inverse app.log | less
```

### Pattern Filtering

```bash
# Only deduplicate error messages
uniqseq --track 'ERROR' app.log > clean.log

# Deduplicate everything except debug messages
uniqseq --bypass 'DEBUG' app.log > clean.log

# Use pattern files
uniqseq --track-file error-patterns.txt --bypass-file noise-patterns.txt app.log
```

## Performance

`uniqseq` is designed for efficiency:

- **Hash-based lookups**: O(1) duplicate detection per line
- **Linear time complexity**: O(n) total time for n lines
- **Bounded memory**: Configurable history depth with `--max-history`
- **Streaming processing**: Works with arbitrarily large inputs
- **Single-pass**: Reads input once, writes output once

## Requirements

- Python 3.9+
- Dependencies: `typer>=0.9.0`, `rich>=13.0.0`

## Algorithm Details

The rolling hash algorithm provides:

- **Line hashing**: Blake2b with 8-byte digest (16-char hex)
- **Sequence hashing**: Blake2b with 16-byte digest of concatenated line hashes
- **History management**: Automatic clearing when max_history exceeded
- **Collision resistance**: Cryptographic hash prevents false matches

## Development

```bash
# Clone and install in development mode
git clone https://github.com/JeffreyUrban/uniqseq.git
cd uniqseq
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=uniqseq --cov-report=html
```

## License

MIT License - see LICENSE file for details

## Contributing

Contributions welcome! Please open an issue or pull request on GitHub.

## Author

[Jeffrey Urban](https://jeffreyurban.com)

[uniqseq on GitHub](https://github.com/JeffreyUrban/uniqseq)
