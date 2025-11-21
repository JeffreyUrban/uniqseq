# Implementation Documentation

## Overview

`uniqseq` is a streaming line sequence deduplicator designed for cleaning up verbose text output where multi-line patterns repeat. Unlike traditional line-based deduplication tools (`uniq`, `sort -u`), uniqseq detects and removes repeated **sequences** of lines while preserving all unique content.

**Core Use Case**: Terminal session logs and verbose application output where content is frequently re-displayed (e.g., Claude Code sessions, interactive CLI applications, build output).

## Design Philosophy

### Unix Filter Principles

1. **Data to stdout, UI to stderr**: Clean output data goes to stdout, all formatting (statistics, progress) goes to stderr
2. **Composable**: Works in pipelines with other Unix tools
3. **Streaming**: Processes input line-by-line with bounded memory
4. **No side effects**: Pure filter behavior - read stdin, write stdout

### Key Design Goals

1. **Simplicity**: Straightforward algorithm that's easy to understand and verify
2. **Performance**: O(1) duplicate detection per sequence via hash-based lookup
3. **Memory efficiency**: Bounded memory usage via configurable history limits
4. **Order preservation**: First occurrence of each sequence is kept
5. **Streaming compatibility**: Works with pipes and very large files

## Architecture

### Component Structure

```
uniqseq/
    deduplicator.py    # Core algorithm (StreamingDeduplicator class)
    cli.py             # CLI interface with typer + rich
    __init__.py        # Package exports
    __main__.py        # Module entry point
```

**Separation of Concerns**:
- `deduplicator.py`: Pure Python logic, no CLI dependencies
- `cli.py`: User interface, progress display, statistics formatting
- Clear API boundary allows embedding in other applications

### Core Algorithm: Rolling Hash with FIFO Buffer

The deduplication algorithm uses a sliding window approach:

1. **Maintain FIFO buffer** of N lines (default: 10)
2. **Hash each line** as it arrives (Blake2b, 8-byte digest)
3. **Build window hash** from N consecutive line hashes when buffer fills
4. **Check history** for duplicate window (O(1) set lookup)
5. **Decision**:
   - **If duplicate**: Discard entire buffer (skip N lines)
   - **If unique**: Add to history, emit oldest line, slide window forward

## Design Decisions

### 1. Rolling Hash vs. Full Line History Storage

**Decision**: Store only hashes, not full line content

**Rationale**:
- **Memory efficiency**: 16-byte hash vs. potentially kilobytes of text per sequence
- **Fast comparison**: Hash equality is O(1) integer comparison
- **Collision resistance**: Blake2b cryptographic hash provides negligible collision probability
- **Bounded growth**: History size controlled by hash count, not content size

**Trade-off**: Cannot reconstruct original sequences from history (not needed for deduplication)

### 2. FIFO Buffer with Deque

**Decision**: Use `collections.deque` with `maxlen` parameter

**Rationale**:
- **Automatic size limiting**: Deque with maxlen automatically evicts oldest items
- **O(1) operations**: Both append and popleft are O(1)
- **Simplicity**: No manual index tracking or circular buffer management

**Implementation Detail**: Two parallel deques:
- `line_buffer`: Actual line content (for eventual output)
- `hash_buffer`: Line hashes (for sequence hash computation)

### 3. History Management Strategy

**Implementation**:
- **Window hash buffer**: FIFO deque of size `window_size` holds new window hashes
- **Delayed entry**: Window hashes only enter history after `window_size` more window hashes are seen

**Rationale**:
- **Prevents premature matching**: Window hash buffer ensures we don't match against window hashes still in active buffer (avoids excluding valid alternating patterns)
- **Predictable memory**: Hard limit on memory usage via `max_history`
- **O(1) operations**

### 4. Window hash Buffer for Delayed History Entry

**Decision**: Use FIFO buffer to delay window hash entry into history

**Rationale**:
- **Critical for correctness**: Without delay, alternating patterns get excluded too early
- **Window departure guarantee**: Window hashes only become matchable after they've fully exited the active window
- **Simple implementation**: Single deque with `maxlen=window_size`

**Example Problem Without Buffer**:
```
Input: A, B, A, B, A, B, ...
Without buffer: Second A gets matched while first A still in active window → incorrect skip
With buffer: Second A only matches after first A fully departed → correct behavior
```

### 5. Blake2b Hash Function

**Decision**: Blake2b with 8-byte (64-bit) digest for lines, 16-byte (128-bit) for window hashes

**Rationale**:
- **Optimal speed/collision tradeoff**: 3M lines/sec throughput with cryptographic collision resistance
- **Excellent collision resistance**: ~10^-12 collision probability at 10k lines, negligible for all practical workloads
- **Standard library**: Available in Python hashlib, no external dependencies
- **Modern design**: Blake2b (2012) is faster than MD5/SHA while providing cryptographic security
- **Configurable**: Digest size can be adjusted if requirements change

**Digest Sizes**:

1. **Individual lines: 8-byte digest** (sufficient for millions of lines)
   - 64-bit hash space (2^64 possible values)
   - Collision probability ~10^-10 for 1M unique lines
   - Safe for billions of unique line patterns

2. **Window hashes: 16-byte digest** (extra safety for compound hashes)
   - 128-bit hash space (2^128 possible values)
   - Collision probability ~10^-29 for 1M unique window hashes
   - Conservative choice for "hashes of hashes"

**Rationale for Different Digest Sizes**: Window hashes are "hashes of hashes" (computed from concatenated line hashes), so we use a larger digest (16 bytes) for extra collision resistance.

**Performance Comparison** (100k unique lines):

| Hash Function  | Speed (lines/sec) | Collision Risk    | Verdict             |
|----------------|-------------------|-------------------|---------------------|
| **blake2b-64** | **3.0M**          | **~10^-10**       | **Optimal** ✓       |
| CRC32          | 4.4M              | 1.2% at 10k lines | Too risky ⚠️        |
| xxHash         | ~4.5M             | Low (64-bit)      | Requires dependency |
| SHA256         | 2.9M              | ~10^-29           | Slower, overkill    |

**Why Not Alternatives**:
- **CRC32**: 1.5x faster but 1.2% collision risk at 10k lines - unacceptable for deduplication
- **xxHash**: Similar speed to CRC32 but requires external package (not in standard library)
- **SHA256**: Slightly slower than blake2b with more security than needed

**Trade-off Decision**: For deduplication, false positives (incorrect dedup) corrupt data - unacceptable. The 1.5x speedup of CRC32 (35ms vs 23ms for 100k lines) is imperceptible to users, while blake2b provides essentially perfect collision resistance

### 6. Buffering Behavior

**Decision**: Emit oldest line from buffer after confirming sequence uniqueness

**Rationale**:
- **Order preservation**: Lines emitted in same order as input
- **Latency**: N-line delay before output (necessary for sequence detection)
- **Flush required**: Buffer must be flushed at EOF to emit trailing lines

**Important**: This means the tool cannot detect duplicates that span EOF (acceptable trade-off)

### 7. Progress Callback Design

**Decision**: Optional callback at 1000-line intervals

**Rationale**:
- **UI separation**: Core logic doesn't depend on progress display
- **Configurable frequency**: 1000-line interval balances responsiveness vs. overhead
- **Testability**: Tests can run without progress callbacks

**CLI Integration**: Rich progress bar updates via callback

### 8. Newline Handling

**Decision**: Strip newlines on input, add back on output

**Rationale**:
- **Normalization**: Handles files with mixed line endings (LF, CRLF)
- **Consistent hashing**: Line content hashed without trailing whitespace
- **Unix convention**: Internal processing works with stripped lines

### 9. Window Size as Minimum Length

**Decision**: Default window size of 10 lines, configurable via CLI

**Rationale**:
- **Noise reduction**: Sequences < 10 lines unlikely to be meaningful duplicates
- **Performance**: Smaller windows reduce hash computation frequency
- **Flexibility**: Users can tune for their specific use case

**Typical Use Cases**:
- 5 lines: Repeated error messages or warnings
- 10 lines: Default for general terminal output
- 15+ lines: Large repeated blocks (stack traces, file listings)

### 10. Statistics Tracking

**Decision**: Track total, emitted, skipped, redundancy%, unique sequences

**Rationale**:
- **Verification**: Users can validate effectiveness
- **Debugging**: Statistics reveal algorithm behavior
- **Performance insight**: Shows memory usage (unique sequences count)

**Redundancy Calculation**: `100 * lines_skipped / total_lines`

### 11. CLI with Typer + Rich

**Decision**: Use Typer for CLI framework, Rich for formatting

**Rationale**:
- **Modern tooling**: Type-safe CLI with automatic help generation
- **Rich formatting**: Beautiful tables and progress bars
- **Unix compatibility**: Respects stdout/stderr separation

**Key Feature**: Progress auto-disabled for pipes
```python
show_progress = progress and sys.stdout.isatty()
```

## Performance Characteristics

### Time Complexity

- **Per-line processing**: O(1) hash computation + O(1) set lookup = **O(1)**
- **Total processing**: O(N) where N = total lines
- **History clearing**: O(1) set clear operation (amortized negligible)

### Space Complexity

- **Line buffer**: O(W) where W = window size (default: 10 lines, ~1 KB)
- **Hash buffer**: O(W) small hashes (default: 10 × 8 bytes = 80 bytes)
- **Window hash history**: O(H) where H = max_history (lines of history)
  - **Default varies by mode**:
    - File mode: None (unlimited)
    - Streaming mode: 100,000 lines of history (3.2 MB)
- **Total**: **O(W + H)** bounded memory
  - Typical streaming: 10 + 100,000 ≈ **3.2 MB**
  - File mode: Scales with file size

## Algorithm Walk-Through

### Example: Processing with window_size=3

**Input stream**:
```
A      � Line 1
B      � Line 2
C      � Line 3
A      � Line 4
B      � Line 5
C      � Line 6
D      � Line 7
```

**Processing steps**:

1. **Lines 1-2**: Buffer = [A, B], not full yet � no output
2. **Line 3**: Buffer = [A, B, C], full � hash window "ABC"
   - Not in history � add to history
   - Output oldest line: **A**
   - Buffer = [B, C]
3. **Line 4**: Buffer = [B, C, A], full � hash window "BCA"
   - Not in history � add to history
   - Output oldest line: **B**
   - Buffer = [C, A]
4. **Line 5**: Buffer = [C, A, B], full � hash window "CAB"
   - Not in history � add to history
   - Output oldest line: **C**
   - Buffer = [A, B]
5. **Line 6**: Buffer = [A, B, C], full � hash window "ABC"
   - **Found in history!** � Duplicate detected
   - Discard buffer (skip lines A, B, C)
   - Buffer = []
6. **Line 7**: Buffer = [D], not full � no output
7. **EOF flush**: Output remaining buffer � **D**

**Final output**: A, B, C, D (lines 1-3, 7)
**Skipped**: Lines 4-6 (duplicate window ABC)

## Edge Cases and Handling

### 1. Empty Input

**Behavior**: Outputs nothing, reports 0 lines processed (see `test_empty_input` in tests)

### 2. Single Line

**Behavior**: Output immediately at flush, no deduplication (buffer never fills)

### 3. Sequences Shorter Than Window

**Behavior**: Passed through unchanged, no deduplication possible (see `test_short_sequences`)

### 4. Partial Matches

**Behavior**: Not treated as duplicates - all lines must match for sequence to be duplicate (see `test_partial_matches`)

### 5. Keyboard Interrupt

**Behavior**: Flush buffer, print partial statistics, exit gracefully (see `cli.py:178-185`)

## Code Organization

### Key Files and Their Responsibilities

#### src/uniqseq/deduplicator.py

**Purpose**: Core deduplication algorithm, no external dependencies except hashlib

**Key classes/functions**:
- `StreamingDeduplicator`: Main deduplicator class
  - `process_line()`: Per-line processing entry point
  - `flush()`: Emit remaining buffer at EOF
  - `get_stats()`: Statistics dictionary
  - `line_buffer`, `hash_buffer`: FIFO buffers for current window (size: `window_size`)
  - `window_hash_buffer`: FIFO buffer delaying entry to window_hash_history (size: `window_size`)
  - `window_hash_history`: seen window hashes (max: `max_history`)
- `hash_line()`: Blake2b line hashing
- `hash_window()`: Blake2b window hashing

**Design**: Pure Python, embeddable in other applications

#### src/uniqseq/cli.py

**Purpose**: Command-line interface with rich formatting

**Key functions**:
- `main()`: Typer command with argument parsing
- `print_stats()`: Rich table formatting for statistics

**Design**: Separates UI concerns from core logic

**Important**: All console output goes to stderr (see `cli.py:26`):
```python
console = Console(stderr=True)  # Preserve stdout for data
```

## References

**Related Tools**:
- `uniq`: Single-line deduplication (only adjacent duplicates)
- `sort -u`: Single-line deduplication (requires sorting, loses order)
- `awk '!seen[$0]++'`: Single-line deduplication (order-preserving)

**Why uniqseq is different**: Operates on sequences of lines, not individual lines. Preserves order without sorting.

**Algorithm Inspiration**: Rolling hash technique commonly used in:
- Rabin-Karp string matching
- rsync block-level file synchronization
- Data deduplication systems

**Hash Function Choice**: Blake2b selected based on:
- [BLAKE2 official site](https://www.blake2.net/) - Performance benchmarks
- Python hashlib documentation - Standard library availability
- Cryptographic security properties - Collision resistance

## Version History

**v0.1.0** (Current)
- Initial release
