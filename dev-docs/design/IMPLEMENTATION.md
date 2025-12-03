# Implementation Overview

**Status**: In Development
**Algorithm Documentation**: See [ALGORITHM_DESIGN.md](./ALGORITHM_DESIGN.md) for detailed algorithm design

## Overview

`uniqseq` is a streaming line sequence deduplicator designed for cleaning up verbose text output where multi-line sequences repeat. Unlike traditional line-based deduplication tools (`uniq`, `sort -u`), uniqseq detects and removes repeated **sequences** of lines while preserving all unique content.

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
    uniqseq.py    # Core algorithm (UniqSeq class)
    library.py         # Pattern library I/O and metadata management
    cli.py             # CLI interface with typer + rich
    __init__.py        # Package exports
    __main__.py        # Module entry point
```

**Separation of Concerns**:
- `uniqseq.py`: Pure Python logic, no CLI dependencies
- `library.py`: Sequence storage and hash computation
- `cli.py`: User interface, progress display, statistics formatting
- Clear API boundary allows embedding in other applications

---

## Core Algorithm

The deduplication algorithm uses **context-aware position-based matching** with multi-candidate tracking.

**High-level approach**:
1. Hash each line as it arrives (Blake2b, 8-byte digest)
2. Build window hashes from consecutive line hashes
3. Track window hash positions in history (PositionalFIFO)
4. Store discovered unique sequences (SequenceRecord) with complete window hash lists
5. Match against both history positions and known sequences
6. Emit lines not consumed by active matches

**For detailed algorithm design**, see [ALGORITHM_DESIGN.md](./ALGORITHM_DESIGN.md), which covers:
- Data structures (PositionalFIFO, SequenceRecord, NewSequenceCandidate, PotentialSeqRecMatch)
- Multi-phase processing (5 phases per line)
- Position-based overlap prevention
- EOF flush logic for oracle compatibility
- Memory management and performance characteristics

---

## Pattern Libraries

Pattern libraries allow saving and reusing discovered sequences across multiple runs, enabling workflows where patterns are learned from one source and applied to others.

### Library Structure

```
library_dir/
  sequences/
    <hash1>.uniqseq    # Sequence file (native format)
    <hash2>.uniqseq
    ...
  metadata-YYYYMMDD-HHMMSS/
    config.json        # Run metadata
```

**Sequence Files**: Stored in native format (file content IS the sequence), named by Blake2b hash.

**Metadata**: Timestamped directories with JSON config containing:
- Window size, delimiter, mode (text/binary)
- Sequences discovered/preloaded/saved
- Total records processed/skipped

### Library Operations

**Save Discovered Patterns** (`--library-dir`):
- Creates library directory if needed
- Saves each newly discovered sequence to `sequences/<hash>.uniqseq`
- Writes metadata for the run

**Load Patterns** (`--read-sequences`):
- Loads all `.uniqseq` files from directory
- Treats sequences as "already seen" (skip on first observation)
- Validates hash matches content, renames if mismatched

**Combined Mode** (`--library-dir` + `--read-sequences`):
- Loads patterns from `--read-sequences` (read-only)
- Saves new patterns to `--library-dir`
- Enables pause/resume workflows

### Hash Computation

Sequence hashes are computed using the same algorithm:

1. Split sequence into lines (WITHOUT delimiters)
2. Compute line hashes using `hash_line()`
3. Compute window hashes for all sliding windows
4. Compute full sequence hash: `hash_window(num_lines, window_hashes)`

This ensures library hashes exactly match for consistent pattern matching.

### Preloaded Sequence Integration

Preloaded sequences are loaded into the `unique_sequences` data structure with special handling:

- Stored as `SequenceRecord` objects with `start_line = float('-inf')`
- All window hashes precomputed for matching
- Detected through normal Phase 3 matching (no special case)
- Immediate confirmation for sequences where `length == window_size`
- Saved to library when observed for first time (if not already saved)

**Example Workflow**:
```bash
# Learn patterns from verbose output
cat verbose.log | uniqseq --library-dir ~/patterns

# Apply learned patterns to new output
cat new_output.log | uniqseq --read-sequences ~/patterns/sequences

# Incremental learning (add new patterns to library)
cat more_output.log | uniqseq --library-dir ~/patterns
```

---

## Pattern Filtering

Pattern filtering (Stage 4, Phase 1) controls which lines participate in deduplication. Lines that don't match filter patterns bypass the deduplication pipeline entirely and pass through unchanged.

### Filtering Architecture

**Separate Buffer Design**: Filtered lines use a completely separate buffer from deduplicated lines:

```python
# Deduplication buffers (for lines that participate in deduplication)
self.line_buffer: deque[Union[str, bytes]]  # Actual lines
self.hash_buffer: deque[str]  # Line hashes (parallel)
self.line_num_buffer: deque[int]  # Input line numbers (parallel)

# Filtered lines buffer (bypass deduplication entirely)
# Stores (input_line_num, line) tuples
self.filtered_lines: deque[tuple[int, Union[str, bytes]]]
```

**Key principle**: Filtered lines never enter the hashing or windowing logic. They are completely isolated from the deduplication pipeline.

### Filter Pattern Types

**Track patterns** (`--track`): Allowlist mode
- Lines matching track patterns are deduplicated
- Lines NOT matching any track pattern pass through unchanged
- Use case: Focus deduplication on specific types (errors, warnings)

**Bypass patterns** (`--bypass`): Denylist mode
- Lines matching bypass patterns pass through unchanged
- Lines NOT matching any bypass pattern are deduplicated
- Use case: Exclude noisy content from deduplication

### Pattern Evaluation

**Sequential evaluation** (first-match-wins):

```python
def _evaluate_filter(self, line: Union[str, bytes]) -> Optional[str]:
    """Evaluate filter patterns against a line.

    Returns:
        "bypass" - bypass deduplication (pass through)
        "track" - deduplicate this line
        "no_match_allowlist" - no pattern matches in allowlist mode
        None - no pattern matches, default behavior (deduplicate)
    """
    if not self.filter_patterns:
        return None

    # Convert to string for regex matching
    line_str = line.decode("utf-8") if isinstance(line, bytes) else line

    # Evaluate patterns in order - first match wins
    for filter_pattern in self.filter_patterns:
        if filter_pattern.regex.search(line_str):
            return filter_pattern.action

    # No match - check if we have track patterns (allowlist mode)
    has_track_patterns = any(p.action == "track" for p in self.filter_patterns)
    if has_track_patterns:
        return "no_match_allowlist"  # Pass through

    return None  # Default: deduplicate
```

**Order matters**: Patterns are evaluated in command-line order. This allows fine-grained control:

```bash
# Bypass broad category, then track specific subcategory
uniqseq --bypass 'DEBUG' --track 'DEBUG CRITICAL' app.log
# "DEBUG INFO" → passes through (--bypass matches first)
# "DEBUG CRITICAL" → deduplicated (--track matches second, overrides bypass)
```

### Ordering Preservation

**Challenge**: Filtered lines must maintain correct input order relative to deduplicated lines, even though they're in separate buffers.

**Solution**: Merged emission with line number tracking:

1. **Line numbering**: All lines tagged with input line number when received
2. **Separate buffering**: Deduplication buffer holds lines awaiting processing, filtered buffer holds lines that bypassed deduplication
3. **Merged emission**: During output, compare line numbers from both buffers and emit in order

```python
def _emit_merged_lines(self, output: Union[TextIO, BinaryIO]) -> None:
    """Emit lines from both buffers in input order."""
    while True:
        # Check if uniqseq buffer can emit (respecting buffer depth)
        dedup_can_emit = len(self.line_buffer) > min_required_depth
        dedup_line_num = self.line_num_buffer[0] if dedup_can_emit else float("inf")

        # Check if filtered buffer can emit
        # (only if before earliest buffered uniqseq line)
        filtered_can_emit = len(self.filtered_lines) > 0
        if filtered_can_emit and self.line_buffer:
            filtered_line_num = self.filtered_lines[0][0]
            earliest_dedup_line = self.line_num_buffer[0]
            filtered_can_emit = filtered_line_num < earliest_dedup_line
        else:
            filtered_line_num = self.filtered_lines[0][0] if filtered_can_emit else float("inf")

        # Emit whichever has the lower line number
        if dedup_can_emit and dedup_line_num <= filtered_line_num:
            # Emit from deduplication buffer
            line = self.line_buffer.popleft()
            self.hash_buffer.popleft()
            self.line_num_buffer.popleft()
            self._write_line(output, line)
            self.line_num_output += 1
        elif filtered_can_emit and filtered_line_num < dedup_line_num:
            # Emit from filtered buffer
            _, line = self.filtered_lines.popleft()
            self._write_line(output, line)
            self.line_num_output += 1
        else:
            break  # Nothing to emit
```

**Correctness**: Filtered lines wait for earlier deduplicated lines to be processed before emission, ensuring perfect input order preservation.

### Performance Characteristics

**Filtering cost**: O(P) per line where P = number of filter patterns
- Regex evaluation is sequential (first-match-wins)
- Typically P < 10, so overhead is negligible
- Compiled regexes cached at startup

**Memory impact**: Minimal
- Filtered lines buffer grows at same rate as normal buffer
- Line number tracking adds ~8 bytes per line (int64)
- No additional hash computation for filtered lines

**Throughput**: ~2-5% slower than unfiltered operation (negligible)

### Limitations

**Text mode only**: Filter patterns require UTF-8 string matching
- Validation: `--track` and `--bypass` incompatible with `--byte-mode`
- Reason: Binary data may not decode as valid UTF-8
- Future: Could support binary pattern matching if needed

**No pattern files (Phase 1)**: Patterns must be specified on command line
- Coming in Phase 2: `--track-file` and `--bypass-file` for pattern libraries

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

**Trade-off Decision**: For deduplication, false positives (incorrect uniqseq) corrupt data. The 1.5x speedup of CRC32 is imperceptible to users, while blake2b provides essentially perfect collision resistance.

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

**Implementation**:
- `validate_arguments()` helper function validates all argument constraints
- Typer built-in `min` parameter for range validation
- Custom semantic validation (e.g., window_size ≤ max_history)
- Clear error messages via `typer.BadParameter`

**Current Validations**:
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
- `UniqSeq`: Accepts optional `hash_transform` callable
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

### Real-World Performance

**Throughput benchmarks** (100k lines):
- **Best case** (no duplicates): 287,494 lines/sec
- **Typical case** (mixed patterns, 64% redundancy): 93,470 lines/sec
- **Heavy duplication** (80% redundancy): 32,357 lines/sec

**Performance varies by workload characteristics**:
- Less duplication → faster (less candidate tracking)
- More duplication → slower (more match overhead)
- Window size has minimal impact (±10% variation)

**See [optimization/PERFORMANCE_RESULTS.md](../../optimization/PERFORMANCE_RESULTS.md) for detailed benchmarks and [ALGORITHM_DESIGN.md](./ALGORITHM_DESIGN.md#performance-characteristics) for complexity analysis.**

### Performance Optimizations

The implementation includes several critical optimizations for hot code paths:

1. **Direct data structure access**: Hot loops bypass method calls and access internal dicts directly
   - Eliminates ~26M function calls per 100k lines
   - 2x speedup in candidate update logic

2. **Inlined simple operations**: Trivial functions like `get_next_position()` inlined as arithmetic
   - Reduces function call overhead
   - Improves instruction cache locality

3. **Set comprehensions**: Replaced nested loops with optimized comprehensions
   - More efficient than manual set building
   - Better Python VM optimization

4. **Cached values**: Frequently accessed values cached in local variables
   - Reduces repeated attribute lookups
   - Improves buffer emission performance

**Overall optimization impact**: 2x speedup under profiling, 4-13x faster in real-world usage depending on workload.

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

### Core Module: src/uniqseq/uniqseq.py

**Purpose**: Core deduplication algorithm, minimal dependencies (hashlib only)

**Key classes**:
- `PositionalFIFO`: Position-based FIFO for window hash history
- `SequenceRecord`: Discovered unique sequence
- `NewSequenceCandidate`: New sequence being matched against history
- `PotentialSeqRecMatch`: Match to known sequence
- `UniqSeq`: Main uniqseq class

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

The `UniqSeq` class can be used in other Python applications:

```python
from uniqseq.uniqseq import UniqSeq
import sys

# Create uniqseq
uniqseq = UniqSeq(window_size=10, max_history=100000)

# Process lines
for line in input_stream:
    uniqseq.process_line(line.rstrip('\n'), sys.stdout)

# Flush at end
uniqseq.flush(sys.stdout)

# Get statistics
stats = uniqseq.get_stats()
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

### Track/Bypass and Inspection

**Objective**: Fine-grained control over deduplication and visibility into results.

**Sequential Track/Bypass Evaluation**:
Track/Bypass evaluated in command-line order, **first match wins**.

**Flags**:
- `--track <regex>` - Include lines matching regex for deduplication
- `--bypass <regex>` - Exclude lines matching regex (pass through unchanged)
- `--track-file <path>` - Load patterns from file
- `--bypass-file <path>` - Load patterns from file

**Track/Bypass File Format**:
- One regex pattern per line
- `#` for comments
- Blank lines ignored
- Preserve file order in evaluation

**Example**:
```bash
uniqseq --bypass 'DEBUG' --track 'DEBUG CRITICAL' app.log
# "DEBUG INFO" → bypass (rule 1 matches first)
# "DEBUG CRITICAL" → track (rule 2 matches first)
# "INFO" → default (no match, proceed to uniqseq)
```

**Common Sequence Libraries** (documented in EXAMPLES.md):
- `error-patterns.txt` - ERROR, CRITICAL, FATAL, Exception, etc.
- `noise-patterns.txt` - DEBUG, TRACE, VERBOSE, etc.
- `security-events.txt` - Authentication, Authorization, sudo, etc.

**Inverse Mode** (`--inverse`):
- Keep duplicates, remove unique sequences
- Useful for finding repeated patterns
- Algorithm-specific, hard to achieve via composition

**Annotations** (`--annotate`):
- Inline markers showing where duplicates were skipped
- Custom format: `--annotation-format <template>`
- Template variables: `{start}`, `{end}`, `{match_start}`, `{match_end}`, `{count}`, `{window_size}`

**Example**:
```bash
uniqseq --annotate --annotation-format '[SKIP: lines {start}-{end}, seen {count}x]' app.log
```
Output:
```
Line A
Line B
Line C
[SKIP: lines 4-6, seen 2x]
Line D
```

**Processing Pipeline**:
1. Input → Read lines
2. Track/Bypass Evaluation → First match determines action (track/bypass/default)
3. Skip/Transform → Apply skip-chars, hash-transform
4. Hash → Compute line hash
5. Deduplication → Match check (normal or inverse mode)
6. Annotation → Add markers if enabled
7. Output → Write to stdout

**See**: [docs/planning/STAGE_4_DETAILED.md](../planning/STAGE_4_DETAILED.md)

---

### Removed Features

**Features removed from planning**:

1. **`--min-repeats N`**
   - Rationale: Adds complexity without clear use case
   - Alternative: Use `--inverse` + sequence libraries

2. **Multi-file diff**
   - Rationale: Achievable via composition with sequence libraries
   - Alternative: Save sequences per file, compare with library tools

3. **Context lines** (`-A/-B/-C`)
   - Rationale: Overlaps with `--annotate` feature, unclear use case
   - Alternative: Use `--annotate` to show where duplicates were skipped
