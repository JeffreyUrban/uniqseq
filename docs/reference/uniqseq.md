# UniqSeq API

API reference for the `UniqSeq` class - the core deduplication engine.

## Overview

The `UniqSeq` class provides the core deduplication algorithm. It processes lines one at a time in streaming fashion, maintaining bounded memory usage regardless of input size.

## Key Features

- **Streaming Processing**: Process unlimited input with fixed memory
- **Position-Aware Matching**: Tracks where sequences occur for accurate duplicate detection
- **Configurable Window Size**: Detect sequences of any length
- **Pattern Filtering**: Include or exclude lines based on regex patterns
- **Library Support**: Load and save known sequence patterns
- **Inverse Mode**: Isolate repeated patterns for analysis
- **Annotation Support**: Mark where duplicates were removed

## Class Reference

::: uniqseq.uniqseq.UniqSeq
    options:
      show_source: false
      show_root_heading: true
      heading_level: 3

## Basic Usage

### Simple Deduplication

```python
from uniqseq import UniqSeq
import sys

# Create uniqseq with default settings
uniqseq = UniqSeq(window_size=10)

# Process lines from stdin
for line in sys.stdin:
    line = line.rstrip('\n')  # Remove newline
    uniqseq.process_line(line, sys.stdout)

# Flush remaining buffer
uniqseq.flush(sys.stdout)

# Get statistics
stats = uniqseq.get_stats()
print(
    f"Processed {stats['total']} lines, skipped {stats['skipped']}",
    file=sys.stderr
)
```

### Custom Configuration

```python
from uniqseq import UniqSeq

uniqseq = UniqSeq(
    window_size=5,              # Detect 5-line sequences
    max_history=50000,          # Track up to 50k unique windows
    max_candidates=50,          # Limit concurrent candidates (faster)
    skip_chars=21,              # Skip timestamp prefix
)

# Process file
with open('input.log') as f:
    for line in f:
        line = line.rstrip('\n')
        uniqseq.process_line(line)

uniqseq.flush()
```

### Performance Tuning

```python
from uniqseq import UniqSeq

# Fast mode: good for large files where speed is critical
fast_uniqseq = UniqSeq(
    window_size=10,
    max_candidates=30,          # Fewer candidates = faster
    max_history=50000,          # Smaller history = less memory
)

# Accurate mode: comprehensive analysis
accurate_uniqseq = UniqSeq(
    window_size=10,
    max_candidates=None,        # Unlimited = catches all patterns
    max_history=None,           # Unlimited = complete history
)

# Balanced mode (default): good for most use cases
balanced_uniqseq = UniqSeq(
    window_size=10,
    max_candidates=100,         # Default: balanced performance
    max_history=100000,         # Default: reasonable memory
)
```

## Advanced Features

### Pattern Filtering

```python
import re
from uniqseq.uniqseq import UniqSeq, FilterPattern

# Create filter patterns
patterns = [
    FilterPattern(
        pattern=r'^ERROR',
        action='track',
        regex=re.compile(r'^ERROR')
    ),
    FilterPattern(
        pattern=r'^WARN',
        action='bypass',
        regex=re.compile(r'^WARN')
    ),
]

uniqseq = UniqSeq(
    window_size=10,
    filter_patterns=patterns
)
```

### Hash Transformation

```python
def extract_log_message(line: str) -> str:
    """Extract just the message part of a log line."""
    # Skip timestamp and log level, keep only message
    parts = line.split(maxsplit=3)
    return parts[3] if len(parts) > 3 else line

uniqseq = UniqSeq(
    window_size=10,
    hash_transform=extract_log_message
)
```

### Library Mode

```python
from pathlib import Path

def save_callback(seq_hash: str, seq_lines: list[str]) -> None:
    """Save discovered sequences to disk."""
    output_dir = Path('~/sequences').expanduser()
    output_dir.mkdir(exist_ok=True)

    filepath = output_dir / f'{seq_hash}.txt'
    filepath.write_text('\n'.join(seq_lines))

uniqseq = UniqSeq(
    window_size=10,
    save_sequence_callback=save_callback
)
```

### Preloaded Sequences

```python
# Load known patterns to skip on first occurrence
preloaded = {
    'abc123def456': 'Line 1\nLine 2\nLine 3',
    '789ghi012jkl': 'Error A\nError B\nError C',
}

uniqseq = UniqSeq(
    window_size=3,
    preloaded_sequences=preloaded
)
```

### Inverse Mode

```python
# Keep only duplicates (for pattern analysis)
uniqseq = UniqSeq(
    window_size=10,
    inverse=True
)

# Process lines - will output only repeated sequences
for line in input_lines:
    uniqseq.process_line(line, sys.stdout)

uniqseq.flush(sys.stdout)
```

### Annotations

```python
# Add markers where duplicates were skipped
uniqseq = UniqSeq(
    window_size=10,
    annotate=True,
    annotation_format='[SKIP: Lines {start}-{end}, seen {count}x]'
)
```

## Memory Management

### History Limits

The `max_history` parameter controls memory usage:

```python
# Limited history (bounded memory)
uniqseq = UniqSeq(
    window_size=10,
    max_history=10000  # Track last 10k windows
)

# Unlimited history (for file processing)
uniqseq = UniqSeq(
    window_size=10,
    max_history=None  # No limit
)
```

**Memory usage**:
- Each window hash: ~100 bytes
- 10,000 windows ≈ 1 MB
- 100,000 windows ≈ 10 MB

### Unique Sequence Limits

The `max_unique_sequences` parameter limits unique patterns tracked:

```python
uniqseq = UniqSeq(
    window_size=10,
    max_history=100000,
    max_unique_sequences=5000  # Track up to 5k unique patterns
)
```

When the limit is reached, oldest sequences are evicted (LRU).

## Statistics

### get_stats()

Returns deduplication statistics:

```python
stats = uniqseq.get_stats()

print(f"Total lines: {stats['total']}")
print(f"Emitted: {stats['emitted']}")
print(f"Skipped: {stats['skipped']}")
print(f"Redundancy: {stats['redundancy_pct']:.1f}%")
print(f"Unique sequences: {stats['unique_sequences']}")
```

**Return value**:
```python
{
    'total': int,            # Total lines processed
    'emitted': int,          # Lines written to output
    'skipped': int,          # Lines skipped as duplicates
    'redundancy_pct': float, # Percentage of duplicates
    'unique_sequences': int  # Number of unique patterns found
}
```

## Binary Mode

Process binary data with bytes instead of strings:

```python
uniqseq = UniqSeq(
    window_size=10,
    delimiter=b'\n'  # Use bytes delimiter
)

# Process binary lines
with open('input.bin', 'rb') as f:
    for line in f:
        line = line.rstrip(b'\n')
        uniqseq.process_line(line, sys.stdout.buffer)

uniqseq.flush(sys.stdout.buffer)
```

## Progress Callbacks

Monitor processing progress:

```python
def progress_callback(
    line_num: int, lines_skipped: int, seq_count: int
) -> None:
    """Called every 1000 lines."""
    redundancy = 100 * lines_skipped / line_num if line_num > 0 else 0
    print(f"Processed {line_num:,} lines, {redundancy:.1f}% redundancy",
          file=sys.stderr)

uniqseq = UniqSeq(window_size=10)

for line in input_lines:
    uniqseq.process_line(line, sys.stdout, progress_callback=progress_callback)
```

## Performance Considerations

### Window Size

- **Smaller windows** (5-10 lines): More sensitive, finds shorter patterns
- **Larger windows** (20-50 lines): Less sensitive, only finds longer patterns
- **Rule of thumb**: Set to the minimum pattern length you want to detect

### History Size

- **Limited history** (10k-100k): Fixed memory, may miss old duplicates
- **Unlimited history**: Grows with unique patterns, best for files
- **Auto-detection**: CLI auto-enables unlimited for files, limited for streams

### Skip Characters

Using `skip_chars` is more efficient than `hash_transform`:

```python
# Efficient: skip characters during hashing
uniqseq = UniqSeq(skip_chars=21)

# Less efficient: transform entire line
uniqseq = UniqSeq(
    hash_transform=lambda line: line[21:]
)
```

## Concurrent Processing

Each `UniqSeq` instance maintains internal state for a single stream. For parallel processing, create separate instances per stream:

```python
from concurrent.futures import ThreadPoolExecutor

def process_file(filepath):
    # Each worker gets its own UniqSeq instance
    uniqseq = UniqSeq(window_size=10)
    with open(filepath) as f:
        for line in f:
            uniqseq.process_line(line.rstrip('\n'))
    uniqseq.flush()
    return uniqseq.get_stats()

# Process multiple files in parallel
with ThreadPoolExecutor() as executor:
    results = executor.map(process_file, file_list)
```

**Note**: Do not share a single `UniqSeq` instance across threads. Each stream requires its own instance to maintain correct state.

## See Also

- [CLI Reference](cli.md) - Command-line interface
- [Library Usage](library.md) - Higher-level library functions
- [Algorithm Details](../about/algorithm.md) - How the algorithm works
