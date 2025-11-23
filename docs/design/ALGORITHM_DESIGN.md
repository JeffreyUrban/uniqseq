# Algorithm Design Document

**Status**: Implemented in
**Date**: 2025-11-21
**Last Updated**: 2025-11-21

## Implementation Status

**Core Algorithm**: ✅ Fully Implemented
**Optional Features**: ❌ Deferred to future releases

This document describes both the implemented core algorithm and planned future enhancement features. Sections marked with status indicators show what's available in the current release versus planned functionality.

---

## Overview

The uniqseq deduplication algorithm provides context-aware sequence matching that tracks WHERE sequences occur (not just THAT they occurred), enabling proper duplicate detection for complex, overlapping sequences.

**Core capabilities** :
1. **Context-Aware Matching**: Position-based tracking for accurate duplicate detection
2. **Multiple Candidate Tracking**: Simultaneous evaluation of multiple potential matches for longest-match behavior
3. **Streaming Architecture**: Bounded memory with configurable limits
4. **Oracle-Compatible**: 100% compatibility with reference implementation

**Planned features**:
- **Optional Annotations** : Inline markers showing where sequences were deduplicated
- **Content Archiving**: Optional persistence of skipped sequences to disk
- **Portable Sequence Libraries**: Save/load discovered sequences for reuse across runs

All functionality is supported both as an imported module and as a CLI tool.

---

## Core Algorithm Architecture

### Key Design Principles

1. **Position-Based Tracking**: Every window hash has a position number, enabling overlap detection and multi-candidate tracking

2. **Complete Window Hash Storage**: Store ALL window hashes in unique sequences (one per line) for precise matching
   - Rationale: Simpler logic, immediate mismatch detection, easier to reason about
   - Trade-off: More comparisons per line vs simpler code and precise matching
   - Memory cost: ~70 bytes per line (~70 MB for 10k sequences × 100 lines)

3. **Two-Phase Matching**: Separate handling for new sequences vs known sequences
   - New sequences: Track against window hash history positions
   - Known sequences: Direct comparison against stored `UniqSeq` sequences

4. **Minimal Delay with Position-Based Overlap Prevention**: Use 1-cycle delay buffer with position checking
   - Rationale: Position comparison prevents overlapping matches directly
   - Benefit: Lower latency, simpler memory profile (8 bytes vs window_size × 16 bytes)
   - Mechanism: Check `first_matchable_position = hist_pos + window_size` before matching

5. **Memory Efficiency Where Practical**: Use `__slots__` for fixed-structure classes, avoid for classes with dynamic lists
   - Rationale: Python dataclasses with `__slots__` and dynamic fields have compatibility issues
   - Approach: Slots used for PositionalFIFO, PotentialUniqSeqMatch; not for UniqSeq, NewSequenceCandidate

---

## Data Structures

### 1. PositionalFIFO (Window Hash History)

Position-based FIFO for window hash history with efficient reverse lookup.

**Design principles**:
- Position-based indexing (not LRU reordering)
- Efficient reverse lookup: `find_all_positions(key)` returns all matching positions in O(1)
- Sequential position advancement via `get_next_position(pos)`

**Implementation**:
```python
class PositionalFIFO:
    __slots__ = ['maxsize', 'position_to_key', 'key_to_positions',
                 'next_position', 'oldest_position']

    position_to_key: dict[int, str]  # position -> window hash
    key_to_positions: dict[str, list[int]]  # window hash -> [positions]
    next_position: int  # Next position to assign
    oldest_position: int  # Oldest position (for eviction)
```

**Operations**:
- `append(key)`: Add window hash, return position, evict oldest if at capacity
- `find_all_positions(key)`: Get all positions matching this window hash
- `get_key(position)`: Get window hash at position
- `get_next_position(position)`: Get next position (position + 1)

**Memory**: ~32 bytes per entry (two dict entries + position integers)

---

### 2. UniqSeq (Unique Sequence Pattern)

Represents a discovered unique sequence with complete window hash list.

**Design principle**: Store ALL window hashes for precise matching

**Structure**:
```python
@dataclass
class UniqSeq:
    start_window_hash: str      # Hash of first window (for quick lookup)
    full_sequence_hash: str     # Hash identifying complete sequence
    start_line: int             # Output line number where first seen
    sequence_length: int        # Number of lines in sequence
    repeat_count: int           # How many times seen (excluding first)
    window_hashes: list[str]    # ALL window hashes (one per line)
```

**Note**: No `__slots__` because dynamic `window_hashes` list grows during sequence discovery

**Memory**: ~70 bytes per line in sequence (Python list overhead included)

**Storage**: Two-level dict structure
- Outer key: `start_window_hash` (know when to start matching)
- Inner key: `full_sequence_hash` (distinguish sequences with same start)
- Structure: `OrderedDict[str, dict[str, UniqSeq]]` (OrderedDict for LRU eviction support)

---

### 3. NewSequenceCandidate (New Sequence Being Discovered)

Tracks a new sequence currently being matched against window hash history.

**Design principle**: Track multiple history positions simultaneously using simple set

**Structure**:
```python
@dataclass
class NewSequenceCandidate:
    current_start_line: int     # Output line number where sequence started
    input_start_line: int       # Input line number (0-indexed)
    lines_matched: int          # How many lines matched so far
    window_hashes: list[str]    # ALL window hashes collected
    start_window_hash: str      # First window hash
    buffer_depth: int           # How deep in buffer this extends
    matching_history_positions: set[int]  # History positions still matching
```

**Note**: No `__slots__` because dynamic `window_hashes` list grows during matching

**History position tracking**:
- Simple `set[int]` of position numbers
- Positions removed as mismatches occur
- Finalized when set becomes empty (all candidates eliminated)
- No separate tracking objects needed - position number is sufficient

**Rationale for set-based tracking**:
- Only need position numbers (can look up hash in PositionalFIFO if needed)
- Lower memory: Set of ints vs list of objects
- Simpler: No need to create/destroy tracking objects

---

### 4. PotentialUniqSeqMatch (Match to Known Sequence)

Tracks potential duplicate of a previously identified `UniqSeq` sequence.

**Design principle**: Window-by-window comparison against stored sequence

**Structure**:
```python
@dataclass
class PotentialUniqSeqMatch:
    __slots__ = ['candidate_seq', 'current_start_line', 'next_window_index', 'window_size']

    candidate_seq: UniqSeq      # Existing sequence being compared to
    current_start_line: int     # Output line where match started
    next_window_index: int      # Index in candidate_seq.window_hashes for next expected window
    window_size: int            # Window size (for calculating lines_matched)
```

**Note**: Uses `__slots__` because structure is fixed (no dynamic lists)

**Operations**:
- `get_lines_matched()`: Calculate matched lines = window_size + (next_window_index - 1)
- `get_buffer_depth(line_num_output)`: Calculate buffer depth for this match

---

## Multi-Phase Processing

Each line is processed through 5 phases to ensure correct duplicate detection:

### Phase 1: Update Existing Potential Matches
**Purpose**: Advance window-by-window comparison against known `UniqSeq` sequences

**Logic**:
```python
for match in potential_uniq_matches:
    expected_hash = match.candidate_seq.window_hashes[match.next_window_index]
    if current_window_hash == expected_hash:
        match.next_window_index += 1  # Continue matching
        if match.next_window_index >= len(match.candidate_seq.window_hashes):
            # Complete match - confirmed duplicate!
            skip_buffer_lines(match)
    else:
        remove_match(match)  # Mismatch - not a duplicate
```

### Phase 1b: Update New Sequence Candidates
**Purpose**: Extend candidates and remove failed history position matches

**Logic**:
```python
for candidate in new_sequence_candidates:
    candidate.lines_matched += 1
    candidate.buffer_depth += 1
    candidate.window_hashes.append(current_window_hash)

    # Check all history positions still matching
    for hist_pos in list(candidate.matching_history_positions):
        next_hist_pos = hist_pos + candidate.lines_matched
        expected_hash = window_hash_history.get_key(next_hist_pos)
        if current_window_hash != expected_hash:
            candidate.matching_history_positions.remove(hist_pos)  # Mismatch
```

### Phase 2: Check for Finalization
**Purpose**: Finalize candidates when all history matches eliminated

**Logic**:
```python
for candidate in new_sequence_candidates:
    if len(candidate.matching_history_positions) == 0:
        # All history candidates eliminated - finalize
        finalize_new_sequence(candidate)
```

**Finalization outcome**: Always results in duplicate handling
- Check if sequence exists in `unique_sequences`
- If exists: Increment repeat_count, skip buffer (duplicate)
- If new: Create UniqSeq, add to unique_sequences, skip buffer (first occurrence becomes the reference)

### Phase 3: Start New Potential Matches
**Purpose**: Detect new matches against both history and known sequences

**Logic**:
```python
# Check for history matches (new sequences)
hist_positions = window_hash_history.find_all_positions(current_window_hash)
for hist_pos in hist_positions:
    # Only match if position has fully departed active window
    first_matchable_position = hist_pos + window_size
    if first_matchable_position <= line_num_input:
        create_new_sequence_candidate(hist_pos)

# Check for UniqSeq matches (known sequences)
if current_window_hash in unique_sequences:
    for uniq_seq in unique_sequences[current_window_hash].values():
        create_potential_uniq_match(uniq_seq)
```

**Position-based overlap prevention**:
- Check `first_matchable_position = hist_pos + window_size`
- Only create match if position has fully departed (first_matchable_position ≤ current input line)
- Ensures no matching against window hashes still in active buffer

### Phase 4: Add to History (with 1-Cycle Delay)
**Purpose**: Add window hashes to history with minimal delay

**Logic**:
```python
if len(window_hash_delay_buffer) == 1:
    # Delay buffer has 1 item - add it before it gets evicted
    evicted_hash = window_hash_delay_buffer[0]
    window_hash_history.append(evicted_hash)

window_hash_delay_buffer.append(current_window_hash)
```

**Design rationale**:
- 1-cycle delay buffer (not window_size cycles)
- Position-based overlap checking in Phase 3 prevents premature matching
- Lower latency: Hashes enter history after 1 cycle vs window_size cycles
- Simpler memory profile: 8 bytes vs window_size × 16 bytes

### Phase 5: Emit Available Lines
**Purpose**: Output lines not consumed by active matches

**Logic**:
```python
# Calculate minimum buffer depth needed for active matches
min_buffer_depth = min(match.buffer_depth for match in all_active_matches)

# Emit lines beyond minimum required depth
while len(line_buffer) > min_buffer_depth:
    emit_line(line_buffer.popleft())
```

---

## EOF Flush Logic

At end of file, perform oracle-compatible finalization of remaining candidates.

**Design principle**: Only skip candidates that represent detectable duplicates

**Logic**:
```python
def flush(output):
    for candidate in new_sequence_candidates:
        lines_from_start_to_eof = line_num_input - candidate.input_start_line

        # Only consider if enough lines from start
        if lines_from_start_to_eof >= window_size:
            should_skip = False

            # Check each history position match
            for hist_pos in candidate.matching_history_positions:
                # First non-overlapping position after history position P
                first_check_pos = hist_pos + window_size

                # Lines remaining from first check position to EOF
                lines_from_first_check = line_num_input - first_check_pos

                # If >= window_size lines remain, duplicate is detectable
                if lines_from_first_check >= window_size:
                    should_skip = True
                    break

            if should_skip:
                skip_candidate_lines_from_buffer()
                record_sequence_pattern(candidate)

    # Flush remaining buffer
    emit_all_remaining_lines()
```

**Rationale**:
- Ensures oracle compatibility (100% test pass rate)
- A duplicate is detectable if there were ≥ window_size lines remaining when it first became non-overlapping
- Matches position-based detection logic of reference implementation

---

## NewSequenceCandidate State Machine

A `NewSequenceCandidate` progresses through distinct states from creation to finalization:

```
┌─────────────────┐
│   NOT CREATED   │
└────────┬────────┘
         │
         │ Window hash matches history position
         │ (AND position has departed active window)
         ▼
┌────────────────────────────────────────────────────────────────┐
│  CREATED                                                       │
│  - Created with start_window_hash, current_start_line         │
│  - lines_matched = window_size                                 │
│  - window_hashes = [start_window_hash]                        │
│  - matching_history_positions = {pos1, pos2, ...}             │
│                                                                 │
│  Note: UniqSeq matches are tracked separately as              │
│        PotentialUniqSeqMatch (not via NewSequenceCandidate)   │
└────────┬───────────────────────────────────────────────────────┘
         │
         │ Each cycle: Phase 1b updates candidate
         │ - Increment lines_matched += 1
         │ - Increment buffer_depth += 1
         │ - Append current_window_hash to window_hashes
         │ - Remove failed history positions from set
         ▼
┌────────────────────────────────────────────────────────────────┐
│  TRACKING                                                      │
│  - matching_history_positions may contain 0+ positions        │
│                                                                 │
│  Continue until: len(matching_history_positions) == 0         │
│  (all history match candidates eliminated via mismatch)       │
└────────┬───────────────────────────────────────────────────────┘
         │
         │ All candidates eliminated (Phase 2: check_for_finalization)
         ▼
┌────────────────────────────────────────────────────────────────┐
│  FINALIZED                                                     │
│                                                                 │
│  1. Calculate full_sequence_hash from window_hashes            │
│  2. Check if sequence exists in unique_sequences:               │
│     a) If exists → Increment repeat_count, handle duplicate   │
│     b) If new → Create UniqSeq, add to unique_sequences       │
│  3. Handle duplicate (skip buffer, emit annotation if enabled)│
│  4. Remove from new_sequence_candidates                        │
└────────────────────────────────────────────────────────────────┘
```

**Key Points**:
- **Creation trigger**: Window hash matches history position AND position has departed active window
- **UniqSeq matches**: Tracked separately via `PotentialUniqSeqMatch` (not `NewSequenceCandidate`)
- **State advancement**: Each cycle removes failed history positions from set; finalize when set empty
- **Finalization outcome**: Always results in duplicate handling (either against existing UniqSeq or newly created one)
- **Longest match**: Continues tracking until ALL history candidates fail, ensuring complete sequence capture

---

## Detailed Example: Repeating Pattern

This example illustrates how the algorithm handles a perfectly repeating pattern with window_size=10.

### Input
```
40 lines total - sequence "ABCDEFGHIJ" repeated 4 times:

Position: 0  1  2  3  4  5  6  7  8  9 | 10 11 12 13 14 15 16 17 18 19 | 20 21 22 23 24 25 26 27 28 29 | 30 31 32 33 34 35 36 37 38 39
Content:  A  B  C  D  E  F  G  H  I  J |  A  B  C  D  E  F  G  H  I  J |  A  B  C  D  E  F  G  H  I  J |  A  B  C  D  E  F  G  H  I  J
          <----1st occurrence-------> | <----2nd occurrence-------> | <----3rd occurrence-------> | <----4th occurrence------->
```

### Processing Trace

**After position 9 (first complete window):**
```
Output Buffer: (empty)
Input Buffer: positions 0-9 (ABCDEFGHIJ)
Hash history: (empty)
Current hash: h:A-J
→ h:A-J enters history at position 0
```

**After position 19 (end of 2nd occurrence):**
```
Output Buffer: positions 0-9 (ABCDEFGHIJ) - emitted via Phase 5
Input Buffer: positions 10-19 (ABCDEFGHIJ)
Hash history: h:A-J, h:B-A, h:C-B, h:D-C, h:E-D, h:F-E, h:G-F, h:H-G, h:I-H, h:J-I
Current hash: h:A-J
→ MATCH! h:A-J found at history position 0
→ Create candidate: Match 1 at history position 0
```

**After position 20 (start of 3rd occurrence):**
```
Output Buffer: positions 0-9 (held - not emitted due to active match)
Input Buffer: positions 11-20 (BCDEFGHIJA)
Active matches:
  Match 1: input 10-11 matching history 0-1
  Match 2: input 11 matching history 1 (NEW - h:B-A matches position 1)
```

**After position 29 (end of 3rd occurrence):**
```
Output Buffer: positions 0-9 (held)
Input Buffer: positions 20-29 (ABCDEFGHIJ)
Active matches:
  Match 1: input 10-20 matching history 0-10 (20 windows = 21 lines)
  Match 2: input 11-20 matching history 1-10 (20 windows = 20 lines)
  ...
  Match 11: input 20 matching history 10, 0 (1 window = 10 lines, matches TWO positions)
```

**After position 39 (end of 4th occurrence):**
```
Output Buffer: positions 0-9 (held)
Input Buffer: positions 30-39 (ABCDEFGHIJ)
Active matches: 21 candidates total
  Match 1: input 10-30 matching history 0-20 (30 windows = 31 lines)
  Match 2: input 11-30 matching history 1-20 (29 windows = 30 lines)
  ...
  Match 21: input 30 matching history 20, 10, 0 (1 window = 10 lines)
```

**At EOF (position 40 doesn't exist):**
- Cannot compute new window hash (need 10 lines)
- **Condition 1 met**: EOF reached
- All 21 candidates **end** simultaneously

**Subset Elimination:**
- All 21 candidates end at same position (39)
- Keep candidate with earliest start: Match 1 (starts at position 10)
- Match 1 covers input positions 10-39 (30 lines, representing 2nd + 3rd + 4th occurrences)

**Final Result:**
```
Output: positions 0-9 (ABCDEFGHIJ)
Skipped: positions 10-39 (30 lines - one long matched sequence)
```

### Candidate Termination Rules

**Candidates end when either:**

1. **EOF is reached** (no more input to extend matches)

2. **Mismatch occurs** - current window hash doesn't match any potential continuation:
   - Doesn't match next expected position in history for any of the candidate's matching positions, **AND**
   - Doesn't match next window hash in any existing unique sequence

**Example of mismatch:**
If position 35 had 'X' instead of 'F':
- Current hash: h:X-E (not h:F-E)
- All 21 candidates expect h:F-E at their respective next positions
- All candidates mismatch → all end
- Subset elimination: Keep Match 1 (positions 10-34, 25 lines)

**Multiple candidates at same ending position:**
- Keep the one with earliest start (longest match)
- This ensures we capture the maximum extent of the duplicate sequence

---

## Memory Management

### Bounded Memory Architecture

**Fixed memory components**:
- Line buffer: O(W) where W = dynamic size (grows to accommodate active matches)
- Hash buffer: O(W) parallel to line buffer
- Window hash delay buffer: O(1) - size 1, ~8 bytes
- Window hash history: O(H) where H = max_history (default: 100,000)
  - Memory: ~32 bytes × max_history = ~3.2 MB at default

**Variable memory components**:
- Unique sequences: O(S × L) where S = unique sequences, L = avg sequence length
  - Memory: ~70 bytes/line × avg_length × num_sequences
  - Bounded by max_unique_sequences (default: 10,000)
  - LRU eviction via OrderedDict when limit reached
  - Typical: ~10-50 MB for realistic workloads

**Active tracking** (temporary):
- NewSequenceCandidates: O(C) where C = concurrent candidates
- PotentialUniqSeqMatches: O(M) where M = concurrent matches
- Typically small: Most candidates finalize quickly

**Total typical memory**: ~10-60 MB for realistic workloads

### History Depth Behavior

**File mode**: Unlimited history depth by default (max_history = unlimited)
- Rationale: File size is known, can deduplicate entire file efficiently
- Memory: Scales with unique sequence count (not total file size)
- Override: User can specify `--max-history` explicitly if needed

**Streaming mode** (stdin): Default max_history = 100,000
- Rationale: Handles virtually all realistic use cases while maintaining bounded memory
- Memory cost: ~32 bytes per entry = 3.2 MB at default limit
- Performance: O(1) hash lookup, no performance degradation with larger history
- Override: User can adjust via `--max-history` flag

---

## Optional Features (Future Releases)

### 1. Inline Annotation Output [NOT YET IMPLEMENTED - Planned]

**Status**: Deferred to future release
**Priority**: Medium
**Depends on**: Core algorithm (✅ implemented)

When enabled, insert formatted annotation lines in output stream when duplicates are skipped.

**Default annotation format**:
```
[... skipped duplicate lines 1234-1243 ...]
```

**Line numbering behavior**:

**File mode** (input is a file path): Absolute line numbers (1-indexed from file start)
```
[... skipped duplicate lines 1234-1243 ...]
```

**Streaming mode** (input is stdin): Relative line numbers (backward from current output position)
```
[... skipped duplicate lines back 50-41 ...]
```

**Mode detection**: Automatically determined by input source

**Override**: User can explicitly set line number format via CLI flag:
- `--line-numbers absolute` - Always use absolute (1-indexed)
- `--line-numbers relative` - Always use relative (back N lines)

**Design considerations**:
- Annotations go to stdout (part of data stream, not UI)
- User-configurable format string with variables
- Distinguishable from actual content (bracketed, descriptive)

---

### 2. Content Archiving to Disk [NOT YET IMPLEMENTED - Planned]

**Status**: Deferred to future release
**Priority**: Low
**Depends on**: Core algorithm (✅ implemented)

Optionally write each unique skipped sequence to a file in a specified directory.

**Enabling archiving**: Specify `--archive-dir <path>` (no default directory)
- Archiving is opt-in via the `--archive-dir` parameter
- Directory is created if it doesn't exist (including parent directories)

**Key properties**:
- **Hash-based naming**: Use sequence hash in filename to avoid duplicating identical content
- **Idempotent**: If file exists, don't write again (same hash = same content)
- **Self-documenting**: Files contain the actual skipped lines for reference

**Default filename format**:
```
uniqseq-{hash}.txt
```

**User-configurable filename format** (examples):
```
uniqseq-{hash}-lines{start}-{end}.txt
skip-{timestamp}-{hash}.txt
duplicate-seq-{count:04d}-{hash}.txt
```

---

### 3. Format Specifiers [NOT YET IMPLEMENTED - Planned]

**Status**: Deferred to future release
**Priority**: Medium
**Depends on**: Annotations and/or Archiving

Both annotation text and archive filenames support format specifiers:

| Specifier        | Description                           | Example               |
|------------------|---------------------------------------|-----------------------|
| `{start}`        | First line number of skipped sequence | `1234`                |
| `{end}`          | Last line number of skipped sequence  | `1243`                |
| `{count}`        | Number of lines in sequence           | `10`                  |
| `{hash}`         | Sequence hash (8-char hex, filesystem-safe) | `a3f5c8d9`            |
| `{hash_full}`    | Full sequence hash (32-char hex)      | `a3f5c8d9e1b2c4f6...` |
| `{timestamp}`    | ISO timestamp (sanitized for filenames) | `2025-11-20T14_32_15` |
| `{filename}`     | Archive filename (annotation only)    | `uniqseq-a3f5c8d9.txt` |
| `{seq_num}`      | Nth unique sequence skipped (across all hashes) | `42`         |
| `{instance_num}` | Nth duplicate of this specific hash   | `2` (excludes 1st occurrence) |

**Format string examples**:

Annotation text:
```
--default--
[... skipped duplicate lines {start}-{end} ...]

--verbose--
[DUPLICATE REMOVED: {count} lines ({start}-{end}), hash={hash}]

--minimal--
[skip {start}-{end}]

--relative (streaming mode)--
[... skipped duplicate lines back {start}-{end} ...]

--with archive reference--
[... {count} duplicate lines archived to {filename} ...]
```

Archive filename:
```
--default--
uniqseq-{hash}.txt

--descriptive--
skipped-{start:08d}-{end:08d}-{hash}.txt

--timestamped--
{timestamp}-{hash}.txt

--numbered--
skip-{seq_num:04d}-{hash}.txt
```

---

### 4. Portable Sequence Libraries [NOT YET IMPLEMENTED - Planned]

**Status**: Future enhancement
**Priority**: Low
**Depends on**: Core algorithm (✅ implemented), stable UniqSeq format

Save/load discovered patterns for reuse across runs.

**Planned features**:
- Export unique_sequences to JSON/binary format
- Load patterns at startup for immediate matching
- Merge libraries from multiple runs
- Pattern library management (list, filter, combine)

**Use cases**:
- Pre-load common sequences for faster deduplication
- Share discovered sequences across team/deployments
- Build domain-specific sequence libraries (e.g., build output, test logs)

---

## Implementation Roadmap

### (Current) ✅
- Core algorithm with context-aware matching
- PositionalFIFO window hash history
- Multi-candidate tracking with position-based overlap prevention
- UniqSeq storage with complete window hash lists
- Oracle-compatible EOF handling
- CLI with basic options (--window-size, --max-history, --quiet, --progress)
- 100% test pass rate

### (Planned)
- Inline annotations (--annotate flag)
- Format string support for annotations
- File vs streaming mode line numbering
- Configurable annotation format

### (Planned)
- Content archiving (--archive-dir flag)
- Hash-based filename generation
- Format string support for filenames
- Idempotent archive writes

### (Future)
- Sequence library save/load
- Pattern reuse across runs
- Library merging and management
- Stable API and file formats

---

## Performance Characteristics

### Time Complexity

**Per-line processing**: O(1) average case
- Hash computation: O(line_length) - typically small constant
- History lookup: O(1) via dict
- Position checking: O(1) arithmetic
- Candidate updates: O(C) where C = active candidates (typically 0-5)
- Match updates: O(M) where M = active matches (typically 0-3)

**Total processing**: O(N) where N = total lines

**Worst case**: O(N × C × M) for pathological input with many overlapping sequences
- Mitigated by bounded C and M (candidates/matches finalize quickly)

### Space Complexity

**Total**: O(W + H + S × L)
- W = dynamic line buffer size (window_size + active match depth)
- H = max_history (default: 100,000 window hashes)
- S = unique sequences stored (bounded by max_unique_sequences)
- L = average sequence length

**Typical**: ~10-60 MB for realistic workloads
- Window hash history: ~3.2 MB (100k × 32 bytes)
- Unique sequences: ~10-50 MB (10k sequences × 100 lines × 70 bytes/line)
- Line buffer: ~1-10 KB (dynamic, grows for active matches)

---

## Design Rationale Summary

### Why Position-Based Tracking?
- Enables overlap detection without large delay buffers
- Supports multi-candidate tracking (multiple history positions simultaneously)
- Provides foundation for oracle-compatible EOF handling
- Trade-off: 2× memory per history entry vs incorrect duplicate detection

### Why ALL Window Hashes Instead of Anchors?
- Simpler logic: No gaps, immediate mismatch detection
- Easier to reason about and maintain
- Precise matching at every line
- Trade-off: More comparisons vs code simplicity

### Why 1-Cycle Delay Buffer?
- Position-based overlap checking handles correctness
- Lower latency (hashes enter history faster)
- Simpler memory profile (8 bytes vs window_size × 16 bytes)
- Functionally equivalent to larger delay via different mechanism

### Why Simple set[int] for History Positions?
- Only need position numbers (can look up hash if needed)
- Lower memory than tracking objects
- Simpler implementation (no create/destroy overhead)
- Sufficient information for matching logic

### Why Selective __slots__ Usage?
- Python dataclass limitations with __slots__ and dynamic lists
- Use where practical (PositionalFIFO, PotentialUniqSeqMatch)
- Avoid where problematic (UniqSeq, NewSequenceCandidate have growing lists)
- Pragmatic approach: Optimize where it works, simplify where it doesn't

---

## References

**Algorithm Inspiration**:
- Rolling hash techniques (Rabin-Karp string matching)
- Position-based duplicate detection (rsync, deduplication systems)
- Streaming algorithms with bounded memory

**Hash Function**: Blake2b
- 8-byte digest for line hashes (64-bit)
- 16-byte digest for window hashes (128-bit)
- Standard library availability (hashlib)
- Cryptographic collision resistance

**Testing**:
- Oracle-based testing for correctness validation
- Property-based testing for edge cases
- Fixture-based testing for reproducibility
- 100% test pass rate in
