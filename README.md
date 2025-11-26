# uniqseq

**Stream-based deduplication for repeating sequences in text and binary data**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What It Does

`uniqseq` identifies and removes repeated multi-line patterns from streaming data using a sliding window and hash-based detection. Unlike traditional line-by-line deduplication tools, it detects when **sequences** of lines (or bytes) repeat—perfect for cleaning verbose logs, repeated error traces, build output, or any data with multi-line patterns.

It works on both text (line-delimited) and binary (byte-delimited) streams, processes data in a single pass with bounded memory usage, and stores only cryptographic hashes—never the actual content—making it efficient for large-scale data processing.

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

- **Sequence detection** - Identifies repeating multi-line (or multi-byte) patterns
- **Text & binary modes** - Process line-delimited text or byte-delimited binary data
- **Streaming architecture** - Single-pass processing with real-time output
- **Memory efficient** - Stores only window hashes in history (32 bytes each), not full content
- **Pattern filtering** - Selectively deduplicate with regex patterns
- **Flexible normalization** - Skip prefixes, transform content, or extract fields
- **Python API & CLI** - Use as a command-line tool or import as a library
- **Sequence libraries** - Save and reuse pattern libraries across sessions

**[📚 Full Feature Documentation →](docs/)**

## Installation

```bash
# From source (PyPI coming soon)
pip install git+https://github.com/JeffreyUrban/uniqseq.git

# Development installation
git clone https://github.com/JeffreyUrban/uniqseq
cd uniqseq
pip install -e ".[dev]"
```

**Requirements:** Python 3.9+

## Quick Start

### Command Line

```bash
# Basic usage - deduplicate 10-line sequences (default)
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
    window_size=3,        # Detect 3-line patterns
    skip_chars=0,         # No prefix to skip
    max_history=100000    # Bounded memory
)

# Process stream
with open("app.log") as infile, open("clean.log", "w") as outfile:
    for line in infile:
        deduplicator.process_line(line.rstrip("\n"), outfile)
    deduplicator.flush(outfile)  # Emit buffered content
```

**[📖 See detailed usage examples →](docs/getting-started/quick-start.md)**

## Use Cases

- **Log processing** - Clean repeated error traces, stack traces, debug output
- **Build systems** - Deduplicate compiler warnings, test failures
- **Terminal sessions** - Clean up verbose CLI output (from `script` command)
- **Monitoring & alerting** - Reduce noise from repeated alert patterns
- **Data pipelines** - Filter redundant multi-line records in ETL workflows
- **Binary analysis** - Deduplicate repeated byte sequences in memory dumps, network captures

**[📘 See real-world examples →](docs/use-cases/)**

## How It Works

`uniqseq` uses a sliding window approach with cryptographic hashing:

1. **Buffering** - Maintains a FIFO buffer of N records (window size)
2. **Hashing** - When buffer is full, computes BLAKE2b hash of current window
3. **Comparison** - Checks if hash exists in history (O(1) lookup)
4. **Output** - If unique, emits oldest record; if duplicate, discards entire window
5. **Memory** - History stores only 32-byte window hashes, not full content

```
Memory usage = (max_history × 32 bytes) + (unique_sequences × metadata) + (window_size × avg_record_size)
```

The streaming architecture ensures output appears with minimal delay—the buffer is flushed immediately upon confirming no match for a window, maintaining real-time responsiveness.

**[🔬 Algorithm details →](docs/about/algorithm.md)**

## Documentation

- **[Quick Start](docs/getting-started/quick-start.md)** - Get started in 5 minutes
- **[Choosing Window Size](docs/guides/choosing-window-size.md)** - How to select the right window size
- **[Common Patterns](docs/guides/common-patterns.md)** - Copy-paste ready examples
- **[Performance Guide](docs/guides/performance.md)** - Optimization tips
- **[Troubleshooting](docs/guides/troubleshooting.md)** - Solutions to common problems
- **[CLI Reference](docs/reference/cli.md)** - Complete command-line options
- **[Python API](docs/reference/library.md)** - Library reference

**[📚 Full Documentation →](docs/)**

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

**[🤝 Contributing Guide →](docs/about/contributing.md)**

## Performance

- **Time complexity:** O(n) - linear with input size
- **Space complexity:** O(h + u×w) where h=history depth, u=unique sequences, w=window size
- **Throughput:** Approximately constant lines/second (hardware-dependent)
- **Memory:** Bounded by history depth - configurable for streaming or batch workloads

**[⚡ Performance optimization →](docs/guides/performance.md)**

## License

MIT License - See [LICENSE](LICENSE) file for details

## Author

[Jeffrey Urban](https://jeffreyurban.com)

---

**[⭐ Star on GitHub](https://github.com/JeffreyUrban/uniqseq)** | **[📝 Report Issues](https://github.com/JeffreyUrban/uniqseq/issues)** | **[📖 Read the Docs](docs/)**
