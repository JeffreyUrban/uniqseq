# Implementation Overview

**Version**: v0.1.0
**Status**: Production Ready
**Algorithm Documentation**: See [ALGORITHM_DESIGN.md](./ALGORITHM_DESIGN.md) for detailed algorithm design

## Overview

`uniqseq` is a streaming line sequence deduplicator designed for cleaning up verbose text output where multi-line patterns repeat. Unlike traditional line-based deduplication tools (`uniq`, `sort -u`), uniqseq detects and removes repeated **sequences** of lines while preserving all unique content.

**Core Use Case**: Terminal session logs and verbose application output where content is frequently re-displayed (e.g., Claude Code sessions, interactive CLI applications, build output).

**Key Features**:
- Context-aware matching: Tracks WHERE sequences occur for accurate duplicate detection
- Streaming architecture: Bounded memory with configurable limits
- Order preservation: First occurrence of each sequence is kept
- Oracle-compatible: 100% test compatibility with reference implementation

---

## Unix Filter Principles

1. **Data to stdout, UI to stderr**: Clean output data goes to stdout, all formatting (statistics, progress) goes to stderr
2. **Composable**: Works in pipelines with other Unix tools
3. **Streaming**: Processes input line-by-line with bounded memory
4. **No side effects**: Pure filter behavior - read stdin, write stdout

---

## Architecture

### Component Structure

```
src/uniqseq/
    deduplicator.py    # Core algorithm (StreamingDeduplicator class)
    cli.py             # CLI interface with typer + rich
    __init__.py        # Package exports
    __main__.py        # Module entry point
```

**Separation of Concerns**:
- `deduplicator.py`: Pure Python logic, no CLI dependencies
- `cli.py`: User interface, progress display, statistics formatting
- Clear API boundary allows embedding in other applications

---

## Core Algorithm

The deduplication algorithm uses **context-aware position-based matching** with multi-candidate tracking.

**High-level approach**:
1. Hash each line as it arrives (Blake2b, 8-byte digest)
2. Build window hashes from consecutive line hashes
3. Track window hash positions in history (PositionalFIFO)
4. Store discovered unique sequences (UniqSeq) with complete window hash lists
5. Match against both history positions and known sequences
6. Emit lines not consumed by active matches

**For detailed algorithm design**, see [ALGORITHM_DESIGN.md](./ALGORITHM_DESIGN.md), which covers:
- Data structures (PositionalFIFO, UniqSeq, NewSequenceCandidate, PotentialUniqSeqMatch)
- Multi-phase processing (5 phases per line)
- Position-based overlap prevention
- EOF flush logic for oracle compatibility
- Memory management and performance characteristics

---

## Key Design Decisions

### 1. Blake2b Hash Function

**Decision**: Blake2b with 8-byte (64-bit) digest for lines, 16-byte (128-bit) for window hashes

**Rationale**:
- Optimal speed/collision tradeoff: 3M lines/sec throughput with cryptographic collision resistance
- Standard library availability (Python hashlib)
- Collision probability ~10^-10 for 1M unique lines (essentially perfect)

**Performance Comparison** (100k unique lines):

| Hash Function  | Speed (lines/sec) | Collision Risk    | Verdict             |
|----------------|-------------------|-------------------|---------------------|
| **blake2b-64** | **3.0M**          | **~10^-10**       | **Optimal** ✓       |
| CRC32          | 4.4M              | 1.2% at 10k lines | Too risky ⚠️        |
| xxHash         | ~4.5M             | Low (64-bit)      | Requires dependency |
| SHA256         | 2.9M              | ~10^-29           | Slower, overkill    |

**Trade-off Decision**: For deduplication, false positives (incorrect dedup) corrupt data. The 1.5x speedup of CRC32 is imperceptible to users, while blake2b provides essentially perfect collision resistance.

### 2. Newline Handling

**Decision**: Strip newlines on input, add back on output

**Rationale**:
- Normalization: Handles files with mixed line endings (LF, CRLF)
- Consistent hashing: Line content hashed without trailing whitespace
- Unix convention: Internal processing works with stripped lines

### 3. Window Size as Minimum Sequence Length

**Decision**: Default window size of 10 lines, configurable via CLI

**Rationale**:
- Noise reduction: Sequences < 10 lines unlikely to be meaningful duplicates
- Flexibility: Users can tune for their specific use case

**Typical Use Cases**:
- 5 lines: Repeated error messages or warnings
- 10 lines: Default for general terminal output
- 15+ lines: Large repeated blocks (stack traces, file listings)

### 4. Statistics Tracking

**Decision**: Track total, emitted, skipped, unique sequences

**Rationale**:
- Verification: Users can validate effectiveness
- Debugging: Statistics reveal algorithm behavior
- Performance insight: Shows memory usage

**Redundancy Calculation**: `100 * lines_skipped / total_lines`

### 5. CLI with Typer + Rich

**Decision**: Use Typer for CLI framework, Rich for formatting

**Rationale**:
- Modern tooling: Type-safe CLI with automatic help generation
- Rich formatting: Beautiful tables and progress bars
- Unix compatibility: Respects stdout/stderr separation

**Key Feature**: Progress auto-disabled for pipes
```python
show_progress = progress and sys.stdout.isatty()
```

### 6. Custom Delimiters

**Decision**: Support both text delimiters (`--delimiter`) and binary hex delimiters (`--delimiter-hex`)

**Rationale**:
- **Text mode** (`--delimiter`): Simple escape sequences sufficient for most text files
- **Binary mode** (`--delimiter-hex`): Precise byte-level control for binary data
- **Mutually exclusive**: Clear semantics, prevents confusion

**Text Delimiters** (`--delimiter`):
- Supports escape sequences: `\n`, `\t`, `\0`
- Works in default text mode
- Use cases: CSV (`,`), TSV (`\t`), null-delimited (`\0`), custom separators

**Binary Hex Delimiters** (`--delimiter-hex`):
- Accepts hex strings: `00`, `0x0a`, `0d0a` (case insensitive)
- Requires `--byte-mode` flag
- Multi-byte support: `0d0a` for CRLF (2 bytes)
- Use cases: Binary protocols, Windows files (CRLF), custom byte markers

**Implementation Details**:
- `parse_hex_delimiter()`: Converts hex string to bytes with validation
  - Validates even-length hex strings
  - Supports optional `0x` prefix
  - Clear error messages for invalid input
- `convert_delimiter_to_bytes()`: Handles escape sequences for text mode
- `read_records()`: Text-mode record splitting
- `read_records_binary()`: Binary-mode record splitting

**Validation**:
- `--delimiter` and `--delimiter-hex` are mutually exclusive
- `--delimiter-hex` requires `--byte-mode`
- Hex strings must have even length (2 hex chars per byte)
- Invalid hex characters produce clear error messages

### 7. Argument Validation Framework

**Decision**: Fail-fast validation with clear error messages

**Implementation** (v0.1.0):
- `validate_arguments()` helper function validates all argument constraints
- Typer built-in `min` parameter for range validation
- Custom semantic validation (e.g., window_size ≤ max_history)
- Clear error messages via `typer.BadParameter`

**Current Validations** (v0.2.0):
- ✓ `window_size ≥ 2` (Typer built-in)
- ✓ `max_history ≥ 100` (Typer built-in)
- ✓ `window_size ≤ max_history` (semantic constraint)
- ✓ `input_file` exists and is not a directory (Typer built-in)
- ✓ `--delimiter` and `--delimiter-hex` are mutually exclusive
- ✓ `--delimiter-hex` requires `--byte-mode`
- ✓ `--unlimited-history` and `--max-history` are mutually exclusive
- ✓ `--hash-transform` incompatible with `--byte-mode`
- ✓ Hex delimiter validation (even length, valid hex characters)

**Design Principles**:
- Validate before processing any data
- Separation of concerns (validation logic separate from business logic)
- Clear, actionable error messages
- Extensible for future feature combinations

**Example**:
```python
def validate_arguments(window_size: int, max_history: int) -> None:
    """Validate argument combinations and constraints."""
    if window_size > max_history:
        raise typer.BadParameter(
            f"--window-size ({window_size}) cannot exceed --max-history ({max_history}). "
            f"The window must fit within the history buffer."
        )
```

### 8. Hash Transform for Flexible Matching

**Decision**: Support piping each line through a Unix filter for hashing while preserving original output

**Rationale**:
- **Flexible deduplication**: Match lines based on transformed content (timestamps removed, case-insensitive, field extraction)
- **Output preservation**: Original lines appear in output unchanged
- **Unix philosophy**: Leverage existing shell commands (cut, awk, sed, tr)
- **Composability**: Works with --skip-chars for multi-stage transformations

**Implementation Details**:
- `create_hash_transform()`: Creates callable from shell command string
  - Validates single-line output (rejects filters that split/join lines)
  - 5-second timeout per line
  - Clear error messages for command failures
  - Uses `subprocess.run()` with `shell=True`
- `StreamingDeduplicator`: Accepts optional `hash_transform` callable
  - Applied before hashing (line_for_hashing = transform(line))
  - Original line stored for output
  - Transform order: skip-chars → hash-transform → hash

**Validation**:
- `--hash-transform` incompatible with `--byte-mode` (operates on text only)
- Transform must produce exactly one line per input
- Empty output allowed (treated as empty string for hashing)

**Common Use Cases**:
```bash
# Case-insensitive matching
--hash-transform "tr '[:upper:]' '[:lower:]'"

# Skip timestamps (alternative to --skip-chars for variable-width timestamps)
--hash-transform "cut -d'|' -f2-"

# Extract specific fields
--hash-transform "awk '{print \$3, \$4}'"

# Remove whitespace variations
--hash-transform "sed 's/[[:space:]]+/ /g'"
```

**Design Trade-offs**:
- **Performance**: Spawns subprocess per line (~100-500 lines/sec vs 3M lines/sec without transform)
  - Acceptable for interactive use cases (terminal logs, build output)
  - Not suitable for massive batch processing
- **Security**: Uses `shell=True` for Unix filter composability
  - Users control command execution (local tool, not network service)
  - Commands timeout after 5 seconds
- **Correctness**: Strict single-line validation prevents silent data corruption

---

## Performance Characteristics

### Time Complexity
- **Per-line processing**: O(1) average case
- **Total processing**: O(N) where N = total lines

### Space Complexity
- **Total**: O(W + H + S × L)
  - W = dynamic line buffer size
  - H = max_history (default: 100,000)
  - S = unique sequences stored
  - L = average sequence length

**Typical memory usage**: ~10-60 MB for realistic workloads
- Window hash history: ~3.2 MB (100k × 32 bytes)
- Unique sequences: ~10-50 MB (varies by content)
- Line buffer: ~1-10 KB (dynamic)

**See [ALGORITHM_DESIGN.md](./ALGORITHM_DESIGN.md#performance-characteristics) for detailed analysis.**

---

## Memory Management

### History Depth Behavior

**File mode**: Unlimited history depth by default
- Rationale: File size is known, can deduplicate entire file efficiently
- Override: User can specify `--max-history` explicitly if needed

**Streaming mode** (stdin): Default max_history = 100,000
- Rationale: Handles virtually all realistic use cases while maintaining bounded memory
- Memory cost: ~3.2 MB at default limit
- Override: User can adjust via `--max-history` flag

---

## Code Organization

### Core Module: src/uniqseq/deduplicator.py

**Purpose**: Core deduplication algorithm, minimal dependencies (hashlib only)

**Key classes**:
- `PositionalFIFO`: Position-based FIFO for window hash history
- `UniqSeq`: Discovered unique sequence pattern
- `NewSequenceCandidate`: New sequence being matched against history
- `PotentialUniqSeqMatch`: Match to known sequence
- `StreamingDeduplicator`: Main deduplicator class

**Key functions**:
- `hash_line()`: Blake2b line hashing (8-byte digest)
- `hash_window()`: Blake2b window hashing (16-byte digest)

**Design**: Pure Python, embeddable in other applications

### CLI Module: src/uniqseq/cli.py

**Purpose**: Command-line interface with rich formatting

**Key functions**:
- `main()`: Typer command with argument parsing
- `print_stats()`: Rich table formatting for statistics

**Design**: Separates UI concerns from core logic

**Important**: All console output goes to stderr to preserve stdout for data:
```python
console = Console(stderr=True)  # Preserve stdout for data
```

---

## Edge Cases and Handling

### 1. Empty Input
**Behavior**: Outputs nothing, reports 0 lines processed

### 2. Single Line
**Behavior**: Output immediately at flush, no deduplication (buffer never fills)

### 3. Sequences Shorter Than Window
**Behavior**: Passed through unchanged, no deduplication possible

### 4. Partial Matches
**Behavior**: Not treated as duplicates - all lines must match for sequence to be duplicate

### 5. Keyboard Interrupt
**Behavior**: Flush buffer, print partial statistics, exit gracefully

---

## Usage Examples

### Basic Deduplication
```bash
# Deduplicate a file
uniqseq session.log > deduplicated.log

# Use in a pipeline
cat session.log | uniqseq > deduplicated.log
```

### Custom Window Size
```bash
# Detect 15+ line sequences
uniqseq --window-size 15 session.log > output.log

# Detect shorter sequences (5+ lines)
uniqseq --window-size 5 session.log > output.log
```

### Memory Management
```bash
# Larger history for very long sessions
uniqseq --max-history 500000 session.log > output.log

# Bounded memory for streaming
cat continuous_stream | uniqseq --max-history 50000 > output.log
```

### Progress and Statistics
```bash
# Show live progress (auto-disabled for pipes)
uniqseq --progress session.log > output.log

# Quiet mode (no statistics)
uniqseq --quiet session.log > output.log
```

### Custom Delimiters

**Text Mode** (`--delimiter`):
```bash
# Null-delimited records (common from find -print0)
find . -type f -print0 | uniqseq --delimiter '\0' > unique_files.txt

# Comma-separated data
uniqseq --delimiter ',' data.csv > clean.csv

# Tab-delimited data
uniqseq --delimiter '\t' data.tsv > clean.tsv
```

**Binary Mode** (`--delimiter-hex`):
```bash
# Null byte delimiter (requires --byte-mode)
uniqseq --byte-mode --delimiter-hex 00 file.bin > clean.bin

# CRLF line endings (Windows)
uniqseq --byte-mode --delimiter-hex 0d0a windows_file.txt > clean.txt

# Custom binary protocol delimiter
uniqseq --byte-mode --delimiter-hex 1e protocol.dat > clean.dat
```

### Skip Prefix Characters
```bash
# Skip fixed-width timestamp prefix when hashing
uniqseq --skip-chars 23 app.log > clean.log

# Input:  "2024-11-22 10:30:15 | ERROR: failed"
# Hashed: "ERROR: failed"
# Output: "2024-11-22 10:30:15 | ERROR: failed" (timestamp preserved in output)
```

### Hash Transform
```bash
# Case-insensitive matching (original case preserved in output)
uniqseq --hash-transform "tr '[:upper:]' '[:lower:]'" app.log > clean.log

# Skip variable-width timestamps (alternative to --skip-chars)
uniqseq --hash-transform "cut -d'|' -f2-" app.log > clean.log

# Extract specific fields for matching
uniqseq --hash-transform "awk '{print \$3, \$4}'" app.log > clean.log

# Combine with --skip-chars for multi-stage transformation
uniqseq --skip-chars 10 --hash-transform "sed 's/[[:space:]]+/ /g'" app.log > clean.log
```

---

## Testing

**Test Framework**: pytest exclusively

**Test Categories**:
- Unit tests: Core algorithm components
- Integration tests: End-to-end workflows
- Oracle tests: Correctness validation against reference implementation
- Property tests: Edge cases and invariants
- Fixture tests: Reproducible test cases

**Test Coverage**: See [TEST_COVERAGE.md](../testing/TEST_COVERAGE.md) for comprehensive test documentation

**Current Status**: 100% test pass rate (462/462 tests passing, 94.55% code coverage)

---

## Related Tools Comparison

| Tool | Scope | Order Preservation | Memory |
|------|-------|-------------------|---------|
| `uniq` | Adjacent duplicate **lines** | ✅ Yes | O(1) |
| `sort -u` | All duplicate **lines** | ❌ No (sorts) | O(N) |
| `awk '!seen[$0]++'` | All duplicate **lines** | ✅ Yes | O(N) |
| **`uniqseq`** | **Duplicate line sequences** | **✅ Yes** | **O(H)** bounded |

**Why uniqseq is different**: Operates on sequences of lines (10+ lines by default), not individual lines. Preserves order without sorting. Bounded memory via configurable history limits.

---

## API for Embedding

The `StreamingDeduplicator` class can be used in other Python applications:

```python
from uniqseq.deduplicator import StreamingDeduplicator
import sys

# Create deduplicator
dedup = StreamingDeduplicator(window_size=10, max_history=100000)

# Process lines
for line in input_stream:
    dedup.process_line(line.rstrip('\n'), sys.stdout)

# Flush at end
dedup.flush(sys.stdout)

# Get statistics
stats = dedup.get_stats()
print(f"Skipped {stats['skipped_lines']} duplicate lines", file=sys.stderr)
```

**See [ALGORITHM_DESIGN.md](./ALGORITHM_DESIGN.md) for detailed API documentation.**

---

## References

**Algorithm Inspiration**:
- Rolling hash techniques (Rabin-Karp string matching)
- Position-based duplicate detection (rsync, deduplication systems)
- Streaming algorithms with bounded memory

**Hash Function**: Blake2b
- [BLAKE2 official site](https://www.blake2.net/) - Performance benchmarks
- Python hashlib documentation - Standard library availability
- Cryptographic security properties - Collision resistance

**Testing Approach**:
- Oracle-based testing for correctness validation
- Property-based testing for edge cases
- Fixture-based testing for reproducibility

---

## Future Enhancements

See [PLANNING.md](../planning/PLANNING.md) for planned features including:
- Inline annotations showing where duplicates were skipped (v0.2.0)
- Content archiving to disk (v0.3.0)
- Portable sequence libraries (v1.0.0)

---

## Version History

**v0.2.0** (In Progress) - 2025-11-22
- Custom delimiters: `--delimiter` for text mode with escape sequences
- Binary mode: `--byte-mode` for binary file processing
- Hex delimiters: `--delimiter-hex` for precise byte-level delimiters
- Skip prefix: `--skip-chars N` for timestamp handling
- Hash transform: `--hash-transform` for flexible matching via Unix filters
- Auto-detection: Unlimited history for files, bounded for streams
- Unlimited history mode: `--unlimited-history` flag
- JSON statistics: `--stats-format json` for automation
- Enhanced validation: Delimiter mutual exclusivity, hex validation, hash-transform incompatibility
- 509 tests passing, 93% code coverage
- Polymorphic type handling: Union[str, bytes] throughout stack

**v0.1.0** - 2025-11-22
- Initial production release
- Core context-aware deduplication algorithm
- Position-based matching with multi-candidate tracking
- Oracle-compatible EOF handling
- CLI with progress and statistics (Typer + Rich)
- Comprehensive argument validation framework
- 462 tests passing, 94.55% code coverage
- Quality tooling: ruff, mypy, pre-commit hooks
- CI/CD: GitHub Actions with Python 3.9-3.13 matrix testing
