# uniqseq

**Stream-based deduplication for repeating sequences**

[![PyPI version](https://img.shields.io/pypi/v/uniqseq.svg)](https://pypi.org/project/uniqseq/)
[![Tests](https://github.com/JeffreyUrban/uniqseq/actions/workflows/test.yml/badge.svg)](https://github.com/JeffreyUrban/uniqseq/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/JeffreyUrban/uniqseq/branch/main/graph/badge.svg)](https://codecov.io/gh/JeffreyUrban/uniqseq)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Documentation](https://img.shields.io/readthedocs/uniqseq)](https://uniqseq.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What It Does

`uniqseq` identifies and removes repeated multi-record patterns from streaming data. Unlike traditional line-by-line deduplication tools, it detects when sequences of records repeat, where a record can be a line, a byte sequence, or any delimiter-separated unit.

Works with text streams (line-delimited, null-delimited, etc.) and binary streams (byte-delimited with any delimiter), processes data in a single pass, and maintains bounded memory usage.

## Quick Example

```bash
# Input with repeated 3-line sequence
$ cat app.log
Starting process...
Loading config
Connecting to DB
Starting process...
Loading config
Connecting to DB
Done

# Remove duplicates (specify window size to match pattern length)
$ uniqseq --window-size 3 app.log
Starting process...
Loading config
Connecting to DB
Done
```

## Key Features

- **Sequence detection** - Identifies repeating multi-record patterns
- **Flexible delimiters** - Text with any delimiter or byte streams
- **Streaming architecture** - Single-pass processing with real-time output
- **Memory efficient** - Bounded memory usage for unlimited input
- **Pattern filtering** - Selectively deduplicate with regex patterns
- **Content transformation** - Match on normalized content while preserving original output
- **Python API & CLI** - Use as a command-line tool or import as a library
- **Sequence libraries** - Save and reuse pattern libraries across sessions

**[Full Feature Documentation](https://uniqseq.readthedocs.io/)**

## Installation

### Via Homebrew (macOS/Linux)

```bash
brew tap jeffreyurban/uniqseq && brew install uniqseq
```

Homebrew manages the Python dependency and provides easy updates via `brew upgrade`.

### Via pipx (Cross-platform)

```bash
pipx install uniqseq
```

[pipx](https://pipx.pypa.io/) installs in an isolated environment with global CLI access. Works on macOS, Linux, and Windows. Update with `pipx upgrade uniqseq`.

### Via pip

```bash
pip install uniqseq
```

Use `pip` if you want to use uniqseq as a library in your Python projects.

### From Source

```bash
# Development installation
git clone https://github.com/JeffreyUrban/uniqseq
cd uniqseq
pip install -e ".[dev]"
```

**Requirements:** Python 3.9+

## Quick Start

### Command Line

```bash
# Basic usage (deduplicate 10-line sequences by default)
uniqseq app.log > clean.log

# Adjust window size for your data
uniqseq --window-size 3 build.log    # 3-line patterns
uniqseq --window-size 5 errors.log   # 5-line patterns

# Stream processing
tail -f app.log | uniqseq --window-size 5

# Ignore timestamps when comparing
uniqseq --skip-chars 24 timestamped.log

# Only deduplicate ERROR lines
uniqseq --track "^ERROR" app.log

# See what was removed
uniqseq --annotate app.log
```

### Python API

```python
from uniqseq import UniqSeq

# Initialize with configuration
deduplicator = UniqSeq(
    window_size=3,
    skip_chars=0,
    max_history=100000
)

# Process stream
with open("app.log") as infile, open("clean.log", "w") as outfile:
    for line in infile:
        deduplicator.process_line(line.rstrip("\n"), outfile)
    deduplicator.flush(outfile)
```

## Use Cases

- **Log processing** - Clean repeated error traces, stack traces, debug output
- **Build systems** - Deduplicate compiler warnings, test failures
- **Terminal sessions** - Clean up verbose CLI output (from `script` command)
- **Monitoring & alerting** - Reduce noise from repeated alert patterns
- **Data pipelines** - Filter redundant multi-line records in ETL workflows
- **Binary analysis** - Deduplicate repeated byte sequences in memory dumps, network captures

## How It Works

`uniqseq` uses a sliding window with hash-based pattern detection:

1. **Buffering** - Maintains a sliding window of N records
2. **Hashing** - Computes a hash for each window position
3. **History tracking** - Records which window patterns have been seen
4. **Sequence tracking** - Tracks known multi-window sequences
5. **Matching** - Compares current windows against history and known sequences
6. **Transformation** - Optionally normalizes content for matching while preserving original data in output

Output is produced with minimal delay. When a window doesn't match any known pattern, the oldest buffered record is immediately emitted.

## Documentation

**[Read the full documentation at uniqseq.readthedocs.io](https://uniqseq.readthedocs.io/)**

Key sections:
- **Getting Started** - Installation and quick start guide
- **Use Cases** - Real-world examples across different domains
- **Guides** - Window size selection, performance tips, common patterns
- **Reference** - Complete CLI and Python API documentation

## Development

```bash
# Clone repository
git clone https://github.com/JeffreyUrban/uniqseq.git
cd uniqseq

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=uniqseq --cov-report=html
```

## Performance

- **Time complexity:** O(n) - linear with input size
- **Space complexity:** O(h + u×w) where h=history depth, u=known sequences, w=window size
- **Throughput:** Approximately constant records per second
- **Memory:** Bounded by configurable history depth

## License

MIT License - See [LICENSE](LICENSE) file for details

## Author

[Jeffrey Urban](https://jeffreyurban.com)

---

**[Star on GitHub](https://github.com/JeffreyUrban/uniqseq)** | **[Report Issues](https://github.com/JeffreyUrban/uniqseq/issues)**
