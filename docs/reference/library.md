# Library Usage

Guide to using uniqseq as a Python library in your applications.

## Installation

```bash
pip install uniqseq
```

## Quick Start

### Basic Usage

```python
from uniqseq import UniqSeq

# Create uniqseq
uniqseq = UniqSeq(window_size=10)

# Process lines
lines = ["Line 1", "Line 2", "Line 3", "Line 1", "Line 2", "Line 3", "Line 4"]

for line in lines:
    uniqseq.process_line(line)

# Flush remaining buffer
uniqseq.flush()

# Get statistics
stats = uniqseq.get_stats()
print(f"Processed {stats['total']} lines")
print(f"Removed {stats['skipped']} duplicates")
print(f"Found {stats['unique_sequences']} unique patterns")
```

### Processing Files

```python
from uniqseq import UniqSeq
import sys

def deduplicate_file(input_path, output_path, window_size=10):
    """Deduplicate a file."""
    uniqseq = UniqSeq(window_size=window_size)

    with open(input_path) as input_file, open(output_path, 'w') as output_file:
        for line in input_file:
            line = line.rstrip('\n')
            uniqseq.process_line(line, output_file)

        uniqseq.flush(output_file)

    return uniqseq.get_stats()

# Use it
stats = deduplicate_file('input.log', 'output.log', window_size=5)
print(f"Redundancy: {stats['redundancy_pct']:.1f}%")
```

### Processing Streams

```python
from uniqseq import UniqSeq
import sys

def deduplicate_stream(input_stream, output_stream, window_size=10):
    """Deduplicate stdin to stdout."""
    uniqseq = UniqSeq(
        window_size=window_size,
        max_history=100000  # Limit memory for streaming
    )

    for line in input_stream:
        line = line.rstrip('\n')
        uniqseq.process_line(line, output_stream)

    uniqseq.flush(output_stream)
    return uniqseq.get_stats()

# Use with stdin/stdout
stats = deduplicate_stream(sys.stdin, sys.stdout)
print(f"Processed {stats['total']:,} lines", file=sys.stderr)
```

## Core API

### UniqSeq

The main deduplication class. See [UniqSeq API](uniqseq.md) for complete reference.

```python
from uniqseq import UniqSeq

uniqseq = UniqSeq(
    window_size=10,               # Minimum sequence length
    max_history=100000,           # History depth (None=unlimited)
    max_unique_sequences=10000,   # Max unique sequences (None=unlimited)
    max_candidates=100,           # Max candidates (None=unlimited)
    skip_chars=0,                 # Characters to skip from line start
    hash_transform=None,          # Optional transform function
    delimiter="\n",               # Output delimiter
    inverse=False,                # Inverse mode (keep duplicates)
    annotate=False,               # Add annotation markers
)
```

## Pattern Management

### Pattern Filtering

```python
import re
from uniqseq.uniqseq import UniqSeq, FilterPattern

def create_filtered_uniqseq(track_patterns=None, bypass_patterns=None):
    """Create uniqseq with pattern filters."""
    filter_patterns = []

    # Add track patterns (allowlist)
    if track_patterns:
        for pattern_str in track_patterns:
            filter_patterns.append(FilterPattern(
                pattern=pattern_str,
                action='track',
                regex=re.compile(pattern_str)
            ))

    # Add bypass patterns (denylist)
    if bypass_patterns:
        for pattern_str in bypass_patterns:
            filter_patterns.append(FilterPattern(
                pattern=pattern_str,
                action='bypass',
                regex=re.compile(pattern_str)
            ))

    return UniqSeq(
        window_size=10,
        filter_patterns=filter_patterns
    )

# Only deduplicate ERROR lines
uniqseq = create_filtered_uniqseq(track_patterns=[r'^ERROR'])

# Deduplicate all except WARN lines
uniqseq = create_filtered_uniqseq(bypass_patterns=[r'^WARN'])
```

### Hash Transformation

```python
from uniqseq import UniqSeq

def extract_message(line: str) -> str:
    """Extract log message without timestamp."""
    # Example: "[2024-01-15 10:30:01] ERROR: Connection failed"
    # Returns: "ERROR: Connection failed"
    parts = line.split('] ', 1)
    return parts[1] if len(parts) > 1 else line

# Deduplicate based on message content only
uniqseq = UniqSeq(
    window_size=5,
    hash_transform=extract_message
)
```

## Sequence Libraries

### Saving Sequences

```python
from pathlib import Path
from uniqseq import UniqSeq
from uniqseq.library import compute_sequence_hash
import sys

# Track saved sequences to prevent duplicates
saved_hashes = set()

def save_callback(file_content: str) -> None:
    """Save discovered sequences."""
    # Compute hash from file content
    seq_hash = compute_sequence_hash(file_content)

    # Skip if already saved
    if seq_hash in saved_hashes:
        return

    lib_dir = Path('~/uniqseq-patterns').expanduser()
    lib_dir.mkdir(exist_ok=True)

    # Save as text file
    filepath = lib_dir / f'{seq_hash}.txt'
    filepath.write_text(file_content)

    saved_hashes.add(seq_hash)
    print(f"Saved pattern: {seq_hash}", file=sys.stderr)

uniqseq = UniqSeq(
    window_size=10,
    save_sequence_callback=save_callback
)
```

### Loading Sequences

```python
from pathlib import Path
from uniqseq.library import load_sequences_from_directory

# Load known patterns
library_dir = Path('~/uniqseq-patterns').expanduser()
sequences = load_sequences_from_directory(
    directory=library_dir,
    delimiter='\n',
    window_size=10,
    byte_mode=False
)

print(f"Loaded {len(sequences)} known patterns")

# Create uniqseq with preloaded patterns
uniqseq = UniqSeq(
    window_size=10,
    preloaded_sequences=sequences
)

# These patterns will be skipped on first occurrence
```

### Complete Library Workflow

```python
from pathlib import Path
from uniqseq import UniqSeq
from uniqseq.library import (
    load_sequences_from_directory,
    save_sequence_file,
    save_metadata
)

def process_with_library(input_file, library_dir, window_size=10):
    """Process file using a sequence library."""
    from uniqseq.library import compute_sequence_hash

    library_dir = Path(library_dir)
    sequences_dir = library_dir / 'sequences'

    # Load existing patterns
    preloaded = set()
    if sequences_dir.exists():
        preloaded = load_sequences_from_directory(
            sequences_dir, '\n', window_size, False
        )
        print(f"Loaded {len(preloaded)} existing patterns")

    # Track saved sequences
    saved_hashes = set()

    def save_callback(file_content: str) -> None:
        """Save new sequences."""
        seq_hash = compute_sequence_hash(file_content)
        if seq_hash not in saved_hashes:
            save_sequence_file(
                file_content, sequences_dir, False
            )
            saved_hashes.add(seq_hash)

    # Process file
    uniqseq = UniqSeq(
        window_size=window_size,
        preloaded_sequences=preloaded if preloaded else None,
        save_sequence_callback=save_callback,
        max_history=None  # Unlimited for files
    )

    with open(input_file) as f:
        for line in f:
            uniqseq.process_line(line.rstrip('\n'))

    uniqseq.flush()

    # Save metadata
    stats = uniqseq.get_stats()
    save_metadata(
        library_dir=library_dir,
        window_size=window_size,
        max_history=None,
        delimiter='\n',
        byte_mode=False,
        sequences_discovered=stats['unique_sequences'],
        sequences_preloaded=len(preloaded),
        sequences_saved=len(saved_hashes),
        total_records_processed=stats['total'],
        records_skipped=stats['skipped']
    )

    print(f"Discovered {len(saved_hashes)} new patterns")
    return stats

# Use it
stats = process_with_library('app.log', '~/uniqseq-library', window_size=10)
```

## Advanced Features

### Binary Data Processing

```python
from uniqseq import UniqSeq

def process_binary_file(input_path, output_path):
    """Process binary file with null delimiters."""
    uniqseq = UniqSeq(
        window_size=10,
        delimiter=b'\x00'  # Null byte delimiter
    )

    with open(input_path, 'rb') as infile, \
         open(output_path, 'wb') as outfile:

        for record in infile.read().split(b'\x00'):
            if record:  # Skip empty
                uniqseq.process_line(record, outfile)

        uniqseq.flush(outfile)

    return uniqseq.get_stats()
```

### Inverse Mode (Pattern Extraction)

```python
from uniqseq import UniqSeq

def extract_repeated_patterns(input_file, output_file, min_repeats=2):
    """Extract only patterns that repeat."""
    # Inverse mode: keep duplicates, remove unique
    uniqseq = UniqSeq(
        window_size=10,
        inverse=True,
        max_history=None
    )

    with open(input_file) as infile, open(output_file, 'w') as outfile:
        for line in infile:
            uniqseq.process_line(line.rstrip('\n'), outfile)

        uniqseq.flush(outfile)

    stats = uniqseq.get_stats()
    print(f"Found {stats['unique_sequences']} repeated patterns")
    print(f"Extracted {stats['emitted']} lines from duplicates")
    return stats
```

### Progress Monitoring

```python
from uniqseq import UniqSeq
import sys

def process_with_progress(input_file, callback_interval=1000):
    """Process file with progress callbacks."""
    uniqseq = UniqSeq(window_size=10)

    def progress_callback(line_num, lines_skipped, seq_count):
        """Called every callback_interval lines."""
        redundancy = 100 * lines_skipped / line_num if line_num > 0 else 0
        print(f"Progress: {line_num:,} lines, "
              f"{redundancy:.1f}% redundancy, "
              f"{seq_count} patterns",
              file=sys.stderr)

    with open(input_file) as f:
        for line in f:
            uniqseq.process_line(
                line.rstrip('\n'),
                progress_callback=progress_callback
            )

    uniqseq.flush()
    return uniqseq.get_stats()
```

### Custom Annotations

```python
from uniqseq import UniqSeq

def process_with_annotations(input_file, output_file):
    """Process with custom annotation format."""
    uniqseq = UniqSeq(
        window_size=10,
        annotate=True,
        annotation_format=(
            '[REMOVED: {start}-{end}, '
            'pattern #{match_start}, count={count}]'
        )
    )

    with open(input_file) as infile, open(output_file, 'w') as outfile:
        for line in infile:
            uniqseq.process_line(line.rstrip('\n'), outfile)

        uniqseq.flush(outfile)

    return uniqseq.get_stats()
```

## Integration Examples

### Flask Application

```python
from flask import Flask, request, Response
from uniqseq import UniqSeq
import io

app = Flask(__name__)

@app.route('/deduplicate', methods=['POST'])
def deduplicate():
    """API endpoint to deduplicate text."""
    window_size = int(request.args.get('window_size', 10))

    # Get input text
    input_text = request.get_data(as_text=True)
    lines = input_text.split('\n')

    # Deduplicate
    uniqseq = UniqSeq(window_size=window_size)
    output = io.StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Return deduplicated text
    return Response(output.getvalue(), mimetype='text/plain')
```

### Pandas Integration

```python
import pandas as pd
from uniqseq import UniqSeq
import io

def deduplicate_dataframe_column(df, column, window_size=10):
    """Deduplicate text in a DataFrame column."""
    uniqseq = UniqSeq(window_size=window_size)
    output = io.StringIO()

    # Process column values
    for value in df[column]:
        if pd.notna(value):
            uniqseq.process_line(str(value), output)

    uniqseq.flush(output)

    # Get deduplicated lines
    deduplicated = output.getvalue().split('\n')

    return deduplicated, uniqseq.get_stats()
```

## Library Functions Reference

### load_sequences_from_directory()

Load sequence patterns from a directory:

```python
from uniqseq.library import load_sequences_from_directory
from pathlib import Path

sequences = load_sequences_from_directory(
    directory=Path('~/patterns'),
    delimiter='\n',
    window_size=10,
    byte_mode=False
)
# Returns: set[Union[str, bytes]]
```

### save_sequence_file()

Save a sequence to a file:

```python
from uniqseq.library import save_sequence_file
from pathlib import Path

filepath = save_sequence_file(
    sequence='Line 1\nLine 2\nLine 3',
    sequences_dir=Path('~/patterns'),
    byte_mode=False
)
# Returns: Path to saved file
```

### compute_sequence_hash()

Compute hash for a sequence:

```python
from uniqseq.library import compute_sequence_hash

# Text mode (str)
seq_hash = compute_sequence_hash('Line 1\nLine 2\nLine 3')

# Binary mode (bytes)
seq_hash = compute_sequence_hash(b'Line 1\x00Line 2\x00Line 3')

# Returns: 32-character hex string
```

### save_metadata()

Save metadata for a library run:

```python
from uniqseq.library import save_metadata
from pathlib import Path

config_path = save_metadata(
    library_dir=Path('~/library'),
    window_size=10,
    max_history=None,
    delimiter='\n',
    byte_mode=False,
    sequences_discovered=15,
    sequences_preloaded=10,
    sequences_saved=5,
    total_records_processed=10000,
    records_skipped=1500
)
```

## See Also

- [UniqSeq API](uniqseq.md) - Complete API reference
- [CLI Reference](cli.md) - Command-line usage
- [Algorithm Details](../about/algorithm.md) - How it works
