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

---

## Testing

**Test Framework**: pytest exclusively

**Test Categories**:
- Unit tests: Core algorithm components
- Integration tests: End-to-end workflows
- Oracle tests: Correctness validation against reference implementation
- Property tests: Edge cases and invariants
- Fixture tests: Reproducible test cases

**Test Coverage**: See [TEST_COVERAGE.md](./TEST_COVERAGE.md) for comprehensive test documentation

**Current Status**: 100% test pass rate (418/418 tests passing)

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

See [FUTURE_FEATURES.md](./FUTURE_FEATURES.md) for planned features including:
- Inline annotations showing where duplicates were skipped (v0.2.0)
- Content archiving to disk (v0.3.0)
- Portable sequence libraries (v1.0.0)

---

## Version History

**v0.1.0** (Current) - 2025-11-21
- Initial release
- Core context-aware deduplication algorithm
- Position-based matching with multi-candidate tracking
- Oracle-compatible EOF handling
- CLI with progress and statistics
- 100% test pass rate
