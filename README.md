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
- **Fast**: O(1) hash-based lookups, processes ~20k lines/sec
- **Progress display**: Optional live progress with statistics

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

Options:
  -w, --window-size INTEGER    Minimum sequence length to detect [default: 10]
  -m, --max-history INTEGER    Maximum depth of history [default: 10000]
  -q, --quiet                  Suppress statistics output to stderr
  -p, --progress               Show progress indicator (auto-disabled for pipes)
  -h, --help                   Show this message and exit
```

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
# Clean up repeated command outputs (50% reduction typical)
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

## Performance

`uniqseq` is designed for efficiency:

- **Hash-based lookups**: O(1) duplicate detection
- **Configurable buffer**: Control memory usage with `--max-history`
- **Streaming processing**: Works with arbitrarily large inputs
- **Typical throughput**: ~20,000 lines/second

Benchmark on real terminal session (77,966 lines):
- Output: 40,811 lines (47.7% reduction)
- Processing time: ~4 seconds
- Memory: ~320KB for sequence history (10k history depth)

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
