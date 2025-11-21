# Algorithm Redesign - Planning Document

**Status**: Planning (awaiting user review)
**Date**: 2025-11-20
**Last Updated**: 2025-11-21

## Overview

This document describes a comprehensive redesign of the uniqseq deduplication algorithm to enable:

1. **Context-Aware Matching**: Track WHERE sequences occur (not just THAT they occurred) to enable proper duplicate detection
2. **Multiple Candidate Tracking**: Support simultaneous evaluation of multiple potential matches for longest-match behavior
3. **Optional Annotations**: Inline markers showing where sequences were deduplicated (disabled by default)
4. **Content Archiving**: Optional persistence of skipped sequences to disk for audit/debugging
5. **Portable Sequence Libraries**: Save/load discovered patterns for reuse across runs (future enhancement)

The redesign maintains the streaming, bounded-memory architecture while adding the contextual information needed for accurate deduplication of complex, overlapping patterns.

All functionality is supported both as an imported module and as a CLI tool.

## Key Architectural Improvements (Updated 2025-11-21)

**Summary of changes from original design:**

1. **PositionalFIFO for window hash history** (replaces deque of WindowHashEntry):
   - Position-based indexing with efficient reverse lookup
   - No LRU reordering (order is preserved by position)
   - `find_all_positions(key)` returns all matching positions in O(1)
   - `get_next_position(pos)` advances through history

2. **Window hash storage for precise matching**:
   - `UniqSeq` stores ALL window hashes (not just sampled anchors)
   - Checks EVERY window hash for matches (not just every `window_size` lines)
   - Simpler logic: no gaps, immediate mismatch detection, easier to reason about
   - Trade-off: More comparisons per line, but simpler code and precise matching
   - Memory cost: ~70 bytes per line in practice (~70 MB for 10k sequences × 100 lines due to Python overhead)
   - Future optimization: Could check sparsely and refine only when needed

3. **Two-level dict for unique sequences**:
   - Outer key: `start_window_hash` (essential for knowing when to start matching)
   - Inner key: `full_sequence_hash` (distinguishes sequences with same start)
   - Structure: `dict[str, dict[str, UniqSeq]]`

4. **NewSequenceCandidate with history match tracking** (key design change):
   - NEW sequences tracked as `NewSequenceCandidate` objects (created only for history matches)
   - Each new sequence tracks multiple potential history matches:
     - `matching_history_positions`: set of history positions still matching
   - Finalization happens when ALL history match candidates are eliminated
   - UniqSeq matches tracked separately via `PotentialUniqSeqMatch` (handled as direct duplicates)

5. **Updated data structures**:
   - `NewSequenceCandidate`: tracks a new sequence with its potential match sets
   - `PotentialHistoryMatch`: links new sequence to history position
   - `PotentialUniqSeqMatch`: tracks match to known unique sequence
   - No `__slots__` for classes with dynamic lists (`UniqSeq`, `NewSequenceCandidate`)

## Use Cases

1. **Transparency**: Users can see where deduplication occurred without having to diff files
2. **Debugging**: Quick reference to what was removed (line ranges, optionally file paths)
3. **Archival**: Preserve skipped content for later review without duplicating identical sequences
4. **Auditability**: Track what content was removed and when

## Feature Components

### History Depth Behavior

**File mode**: Unlimited history depth by default (no automatic clearing)
- Rationale: File size is known, can deduplicate entire file efficiently
- Memory: Scales with unique sequence count (not total file size)
- Override: User can specify `--max-history` explicitly if needed

**Streaming mode** (stdin): Default max_history=100,000
- Rationale: Handles virtually all realistic use cases while maintaining bounded memory
- Memory cost: ~32 bytes per unique sequence = 3.2 MB at default limit
- Performance: O(1) hash lookup, no performance degradation with larger history
- Override: User can set `--max-history unlimited` for unbounded history or lower value for memory-constrained systems

### 1. Inline Annotation Output

If the feature is enabled, when a duplicate sequence is detected and skipped, insert a formatted annotation line in the output stream.

**Default annotation format**:
```
[... skipped duplicate lines 1234-1243 ...]
```

**Line numbering behavior**:

**File mode** (input is a file path): Absolute line numbers (1-indexed from file start)
```
[... skipped duplicate lines 1234-1243 ...]
```

**Streaming mode** (input is stdin): Relative line numbers (backward from current output position, counting only emitted lines)
```
[... skipped duplicate lines back 50-41 ...]
```

**Mode detection**: Automatically determined by input source
- File path argument → file mode (absolute numbers)
- Stdin/pipe → streaming mode (relative numbers)

**Override**: User can explicitly set line number format via CLI flag:
- `--line-numbers absolute` - Always use absolute (1-indexed)
- `--line-numbers relative` - Always use relative (back N lines)

The line ranges refer to where the duplicate sequence **first appeared** in the output (before being repeated and skipped).

**With file archiving enabled**:
```
[... skipped duplicate lines 1234-1243 (archived: uniqseq-a3f5c8d9.txt) ...]
```

**Design considerations**:
- Annotations go to stdout (part of data stream, not UI)
- User-configurable format string with variables
- Distinguishable from actual content (bracketed, descriptive)

### 2. Content Archiving to Disk

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

### 3. Format Specifiers

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

## Architecture Changes

### Fundamental Algorithm Redesign

The current algorithm has a fundamental limitation: it only tracks seen sequence hashes without maintaining context for WHERE sequences occurred. The new design separates concerns:

1. **Window Hash History** (100k positions): Positional FIFO of recent window hashes with position tracking for detecting NEW sequences
2. **Unique Sequence Tracking**: OrderedDict of identified unique patterns (LRU-evicted) with anchor lists for efficient matching
3. **Active Match Tracking**: In-progress comparisons against both window hash history and known sequences

**Key Architectural Improvements:**

1. **PositionalFIFO for window hash history**: Custom data structure with position-based lookups (not LRU) and efficient reverse index for finding all positions matching a given hash

2. **Anchor-based sequence matching**: Store anchor hashes (sampled every `window_size` lines) in `SequenceMetadata` for efficient comparison. Potential matches check anchors incrementally, allowing early termination on mismatch and preventing line buffer output until mismatch occurs.

3. **Delay buffer for window hashes**: Window hashes wait in a `window_size` delay buffer before entering history, ensuring they've fully departed the active window before becoming matchable.

4. **Named properties with `__slots__`**: Use dataclasses with slots for memory efficiency and readability (no `[1]` indexing)

5. **Buffer depth tracking**: Track how deep each active match extends into buffer to know which lines can be emitted

6. **Separate output/input line tracking**: `line_num_output` for emitted lines (used for annotations), `line_num_input` for processed lines

7. **Dynamic buffer growth**: Line buffer grows beyond window_size to accommodate active matches being tracked

**Why anchor-based matching?**
- **Early termination**: Mismatch at any anchor immediately stops tracking that potential match
- **Prevents premature output**: Line buffer cannot emit lines until all active matches complete or fail
- **Memory efficient**: Only store anchors (every Nth window hash), not all window hashes in sequence
- **Handles overlapping patterns**: Multiple potential matches can be tracked simultaneously without interference

### NewSequenceCandidate State Machine

A `NewSequenceCandidate` represents a new sequence being discovered, tracked from first match until finalized:

```
┌─────────────────┐
│   NOT CREATED   │
└────────┬────────┘
         │
         │ Window hash matches history position
         ▼
┌────────────────────────────────────────────────────────────────┐
│  CREATED                                                       │
│  - Created with start_window_hash, current_start_line         │
│  - lines_matched = window_size                                 │
│  - window_hashes = [start_window_hash]                        │
│  - matching_history_positions initialized with match(es)      │
│                                                                 │
│  Note: UniqSeq matches are tracked separately as              │
│        PotentialUniqSeqMatch (not via NewSequenceCandidate)   │
└────────┬───────────────────────────────────────────────────────┘
         │
         │ Each cycle: Phase 1 updates matches, Phase 1b updates candidate
         │ - Increment lines_matched += 1
         │ - Increment buffer_depth += 1
         │ - Append window_hashes
         │ - Phase 1 removes failed matches from tracking sets
         ▼
┌────────────────────────────────────────────────────────────────┐
│  TRACKING                                                      │
│  - matching_history_positions may contain 0+ positions        │
│                                                                 │
│  Continue until: len(matching_history_positions) == 0         │
│  (all history match candidates eliminated via mismatch)       │
└────────┬───────────────────────────────────────────────────────┘
         │
         │ All candidates eliminated (Phase 2 check_for_finalization)
         ▼
┌────────────────────────────────────────────────────────────────┐
│  FINALIZED                                                     │
│                                                                 │
│  1. Calculate full_sequence_hash from window_hashes            │
│  2. Check if pattern exists in unique_sequences:               │
│     a) If exists → Increment repeat_count, handle duplicate   │
│     b) If new → Create UniqSeq, add to unique_sequences       │
│  3. Handle duplicate (skip buffer, emit annotation if enabled)│
│  4. Remove from new_sequence_candidates                        │
└────────────────────────────────────────────────────────────────┘
```

**Key Points:**
- **Creation trigger**: Only when window hash matches history position(s)
- **UniqSeq matches**: Tracked separately via `PotentialUniqSeqMatch` (not `NewSequenceCandidate`)
- **State advancement**: Each cycle removes failed history match candidates; finalize when all eliminated
- **Finalization outcome**: Always results in duplicate handling (either against existing UniqSeq or newly created one)
- **Longest match**: Continues tracking until ALL history candidates fail, ensuring we capture the complete sequence

### Example Walkthrough: Multiple Candidates

Concrete example showing multiple potential matches being tracked and eliminated (window_size=3):

**Setup:**
- Window hash history contains: [H1, H2, H3, H4, H1, H2] at positions [0, 1, 2, 3, 4, 5]
- No UniqSeq patterns yet

**Input stream processing:**

```
Cycle 10: Process line 10, buffer = [A, B, C] (lines 8-10)
  - current_window_hash = H1
  - Phase 3: _check_for_new_history_matches(H1)
    - find_all_positions(H1) → [0, 4]
    - Create NewSequenceCandidate("new_10"):
      - current_start_line = 8
      - lines_matched = 3
      - window_hashes = [H1]
      - matching_history_positions = {0, 4}
    - Create PotentialHistoryMatch("new_10", 0)
    - Create PotentialHistoryMatch("new_10", 4)
  - Phase 4: Add H1 to delay buffer

Cycle 11: Process line 11, buffer = [B, C, D] (lines 9-11)
  - current_window_hash = H2
  - Phase 1: _update_potential_history_matches(H2)
    - Match ("new_10", 0): next_pos=1, history[1]=H2, current=H2 → MATCH! Continue
    - Match ("new_10", 4): next_pos=5, history[5]=H2, current=H2 → MATCH! Continue
  - Phase 1b: Update NewSequenceCandidate("new_10"):
    - lines_matched = 4
    - buffer_depth = 4
    - window_hashes = [H1, H2]
  - Phase 2: Check finalization: matching_history_positions = {0, 4} → Not empty, continue

Cycle 12: Process line 12, buffer = [C, D, E] (lines 10-12)
  - current_window_hash = H5
  - Phase 1: _update_potential_history_matches(H5)
    - Match ("new_10", 0): next_pos=2, history[2]=H3, current=H5 → MISMATCH!
      - Remove position 0 from matching_history_positions
      - Delete PotentialHistoryMatch("new_10", 0)
    - Match ("new_10", 4): next_pos=5, history[5]=H2, current=H5 → MISMATCH!
      - Remove position 4 from matching_history_positions
      - Delete PotentialHistoryMatch("new_10", 4)
  - Phase 1b: Update NewSequenceCandidate("new_10"):
    - lines_matched = 5
    - buffer_depth = 5
    - window_hashes = [H1, H2, H5]
  - Phase 2: Check finalization: matching_history_positions = {} → EMPTY!
    - _finalize_new_sequence("new_10"):
      - full_hash = hash("5:[H1:H2:H5]")
      - Check unique_sequences[H1][full_hash] → Not found (new pattern)
      - Create UniqSeq:
        - start_window_hash = H1
        - full_sequence_hash = full_hash
        - start_line = 8
        - sequence_length = 5
        - repeat_count = 1
        - window_hashes = [H1, H2, H5]
      - Add to unique_sequences[H1][full_hash]
      - Handle as duplicate (skip buffer, emit annotation)
    - Delete NewSequenceCandidate("new_10")
```

**Key observations:**
1. **Multiple candidates tracked**: Both positions 0 and 4 matched initially
2. **Simultaneous elimination**: Both candidates failed on the same cycle (H5 ≠ H3 and H5 ≠ H2)
3. **Longest match captured**: Continued until ALL candidates eliminated (5 lines, not 4)
4. **Finalization registered pattern**: New UniqSeq created with complete sequence data

**Alternative scenario** (if position 4 had continued matching):
- Candidate at position 0 would be removed at Cycle 12
- Candidate at position 4 would continue tracking
- Finalization would occur later when position 4 fails
- Result: Even longer sequence captured

This demonstrates the "longest match" behavior - we always capture the complete sequence by waiting until all potential matches are exhausted.

### Memory Analysis

Memory usage scales with multiple factors depending on data patterns:

#### Core Data Structures

| Component | Size per Entry | Default Limit | Typical Memory |
|-----------|---------------|---------------|----------------|
| **Window Hash History** | ~32 bytes/hash | 100k (streaming) | 3.2 MB |
| **Window Hash Delay Buffer** | ~32 bytes/hash | window_size (10) | 320 bytes |
| **Line Buffer** | ~100 bytes/line | Dynamic (grows with matches) | 1-10 KB |

#### Unique Sequence Storage (LRU-evicted)

**Per UniqSeq entry** (varies by sequence length):
- Base object: ~120 bytes (fields, Python overhead)
- Window hashes list: ~70 bytes/line × sequence_length
- **Total**: ~120 + (70 × length) bytes per unique sequence

**Examples**:
- 10-line sequence: 120 + 700 = **820 bytes**
- 50-line sequence: 120 + 3,500 = **3.6 KB**
- 100-line sequence: 120 + 7,000 = **7.1 KB**

**Default limit**: 10,000 unique sequences (max_unique_sequences)

**Memory at capacity** (assuming average 50-line sequences):
- 10,000 × 3.6 KB = **36 MB**

**Scaling behavior**:
- **Best case**: Few unique patterns, many repetitions → minimal memory
- **Worst case**: Every sequence is unique → fills to max_unique_sequences, then LRU evicts

#### Active Match Tracking (Transient)

Memory scales with **concurrent active matches** (data-dependent):

**NewSequenceCandidate** (one per new sequence being tracked):
- Base: ~200 bytes + (70 bytes × lines_matched)
- Example: 50-line sequence = 200 + 3,500 = **3.7 KB**

**PotentialHistoryMatch** (one per history position being compared):
- Size: ~80 bytes per match
- Count: Up to (# of NewSequenceCandidates) × (avg matches per candidate)

**PotentialUniqSeqMatch** (one per UniqSeq being compared):
- Size: ~120 bytes per match
- Count: Varies with how many sequences start with same window hash

**Typical scenarios**:

1. **Low overlap** (most sequences unique):
   - Few active candidates at a time
   - Active tracking: **< 1 MB**

2. **High overlap** (many partial matches):
   - Example: 100 NewSequenceCandidates, each tracking 5 history positions
   - NewSequenceCandidates: 100 × 3.7 KB = 370 KB
   - PotentialHistoryMatch: 500 × 80 bytes = 40 KB
   - Active tracking: **~400 KB**

3. **Worst case** (pathological input with massive overlap):
   - Hundreds of simultaneous candidates
   - Could reach **several MB** transiently
   - Resolves as matches succeed/fail

#### Total Memory Estimate

**Baseline** (minimal matching):
- Window hash history: 3.2 MB
- UniqSeq storage (1000 sequences, avg 50 lines): 3.6 MB
- Active tracking: 0.5 MB
- **Total: ~7-8 MB**

**Typical workload** (moderate matching):
- Window hash history: 3.2 MB
- UniqSeq storage (5000 sequences, avg 50 lines): 18 MB
- Active tracking: 1-2 MB
- **Total: ~22-23 MB**

**At capacity** (max unique sequences):
- Window hash history: 3.2 MB (streaming) or scales with file (file mode)
- UniqSeq storage (10k sequences, avg 50 lines): 36 MB
- Active tracking: 2-5 MB
- **Total: ~41-44 MB**

**Pathological case** (extreme concurrent matching):
- Window hash history: 3.2 MB
- UniqSeq storage: 36 MB (at capacity)
- Active tracking: 10-20 MB (hundreds of active candidates)
- **Total: ~50-60 MB**

#### Memory Configuration

**For memory-constrained environments**:
```python
dedup = StreamingDeduplicator(
    window_size=10,
    max_history=10000,           # 320 KB instead of 3.2 MB
    max_unique_sequences=1000    # 3.6 MB instead of 36 MB
)
# Total baseline: ~4-5 MB instead of ~7-8 MB
```

**For high-volume servers**:
```python
dedup = StreamingDeduplicator(
    window_size=10,
    max_history=500000,          # 16 MB (more history)
    max_unique_sequences=50000   # 180 MB (more patterns)
)
# Total at capacity: ~200 MB
```

#### Key Takeaway

Memory usage is **data-dependent**:
- **Best case**: Highly repetitive data → minimal UniqSeq storage, few active matches
- **Worst case**: Highly variable data → UniqSeq fills to limit, many concurrent partial matches
- **Configurable**: Adjust `max_history` and `max_unique_sequences` based on available memory

The LRU eviction strategy ensures bounded memory even with pathological input patterns.

#### Future Feature: Portable Sequence Libraries

For workloads with extremely high numbers of unique sequences (e.g., 100k+ patterns), or for reusing known patterns across multiple runs, sequences can be persisted to human-readable files:

**Use Cases**:
1. **Pre-populate known patterns**: Load common sequences from previous runs or curated libraries
2. **Portable pattern sharing**: Share sequence libraries across teams or systems
3. **Bounded memory for large workloads**: Keep only active sequences in memory, lazy-load from disk
4. **Incremental processing**: Build up sequence knowledge across multiple processing sessions
5. **Stop and resume**: Save state when interrupted, resume processing later with accumulated knowledge

**Workflow**:

1. **Export sequences** (during or after processing):
   ```bash
   # Save discovered sequences to directory
   uniqseq input.log --save-sequences ./sequences/

   # Or save only sequences seen N+ times
   uniqseq input.log --save-sequences ./sequences/ --min-occurrences 3
   ```

2. **Load sequences** (for subsequent runs):
   ```bash
   # Pre-load known sequences
   uniqseq new.log --load-sequences ./sequences/

   # Combine: load existing + save new discoveries
   uniqseq new.log --load-sequences ./prev/ --save-sequences ./updated/
   ```

3. **Stop and resume** (interrupted processing):
   ```bash
   # Initial run (interrupted at line 500k)
   uniqseq huge.log --save-sequences ./state/ > output.log
   ^C  # Interrupted!

   # Resume from where we left off (skip already processed lines)
   tail -n +500001 huge.log | uniqseq --load-sequences ./state/ \
       --save-sequences ./state/ >> output.log
   ```

   **Note**: This restores discovered sequence patterns but not active match state:
   - ✅ Loaded sequences will be recognized as duplicates
   - ❌ Any `NewSequenceCandidate` or `PotentialMatch` in progress when interrupted are lost
   - **Implication**: May see a "second first occurrence" of sequences that were being tracked but not finalized
   - **Acceptable**: For long-running jobs, restoring 99%+ of knowledge is sufficient

**File Format** (human-readable text):

```
# sequences/abc123def456.seq
# UniqSeq metadata file
start_line: 1234
sequence_length: 15
repeat_count: 5
start_window_hash: abc123def456
full_sequence_hash: fedcba987654321
---
# Actual sequence content (15 lines)
Error: Connection timeout
  at line 42 in module.py
  stacktrace line 1
  stacktrace line 2
  ...
```

**Disk-Backed Storage Strategy**:

1. **On export** (`--save-sequences`):
   - Write each `UniqSeq` to `{full_sequence_hash}.seq` file
   - Include metadata (hashes, line numbers, repeat count)
   - Include actual line content (reconstructed from buffer or archived)
   - Create index file mapping `start_window_hash` → list of full hashes

2. **On import** (`--load-sequences`):
   - Scan directory for `.seq` files
   - Build in-memory index: `start_window_hash` → `{full_hash → disk_path}`
   - Keep only metadata in memory (~32 bytes per sequence)
   - Lazy-load full `UniqSeq` on potential match

3. **On LRU eviction** (when memory limit reached):
   - If sequence was loaded from disk: just evict (already persisted)
   - If sequence is new discovery and `--save-sequences` enabled: write to disk, then evict
   - Keep hash in index for future lazy-loading

**Memory Savings**:
- **Current (all in memory)**: 10k sequences × 3.6 KB = 36 MB
- **Disk-backed index only**: 100k sequences × 32 bytes = **3.2 MB** (11x reduction)
- Active sequences loaded on-demand (typically < 1000 in memory at once)

**Example Implementation**:

```python
class SequenceLibrary:
    """Manages persistent sequence storage with lazy loading."""

    def __init__(self, library_dir: Optional[Path] = None, max_memory: int = 1000):
        self.library_dir = library_dir
        self.memory_sequences = OrderedDict()  # Full UniqSeq objects
        self.disk_index = {}  # start_hash -> {full_hash -> Path}
        self.max_memory = max_memory

        if library_dir and library_dir.exists():
            self._load_index()

    def _load_index(self):
        """Build index from .seq files in library_dir (metadata only)."""
        for seq_file in self.library_dir.glob("*.seq"):
            metadata = self._read_metadata(seq_file)  # Parse header only
            start_hash = metadata['start_window_hash']
            full_hash = metadata['full_sequence_hash']

            if start_hash not in self.disk_index:
                self.disk_index[start_hash] = {}
            self.disk_index[start_hash][full_hash] = seq_file

    def get_sequences(self, start_hash: str) -> dict[str, UniqSeq]:
        """Get all sequences with this start hash, lazy-loading from disk."""
        result = {}

        # Get from memory first
        if start_hash in self.memory_sequences:
            result.update(self.memory_sequences[start_hash])
            self.memory_sequences.move_to_end(start_hash)  # LRU

        # Lazy-load from disk if needed
        if start_hash in self.disk_index:
            for full_hash, path in self.disk_index[start_hash].items():
                if full_hash not in result:
                    uniq_seq = self._load_from_disk(path)
                    self._add_to_memory(start_hash, full_hash, uniq_seq)
                    result[full_hash] = uniq_seq

        return result

    def save_sequence(self, uniq_seq: UniqSeq):
        """Persist sequence to disk."""
        if not self.library_dir:
            return

        filename = f"{uniq_seq.full_sequence_hash}.seq"
        path = self.library_dir / filename

        with open(path, 'w') as f:
            # Write metadata
            f.write(f"# UniqSeq metadata\n")
            f.write(f"start_line: {uniq_seq.start_line}\n")
            f.write(f"sequence_length: {uniq_seq.sequence_length}\n")
            f.write(f"repeat_count: {uniq_seq.repeat_count}\n")
            f.write(f"start_window_hash: {uniq_seq.start_window_hash}\n")
            f.write(f"full_sequence_hash: {uniq_seq.full_sequence_hash}\n")
            f.write(f"---\n")
            # Write content (reconstructed from archived content or buffer)
            for line in uniq_seq.content_lines:  # Would need to track this
                f.write(line)
```

**CLI Integration**:

```python
@app.command()
def main(
    input_file: Path,
    load_sequences: Optional[Path] = None,   # Pre-load from directory
    save_sequences: Optional[Path] = None,   # Save discoveries to directory
    max_memory_sequences: int = 1000,        # LRU limit for in-memory sequences
    min_occurrences: int = 1,                # Only save sequences seen N+ times
):
    """Process input with optional sequence library."""

    library = SequenceLibrary(
        library_dir=load_sequences,
        max_memory=max_memory_sequences
    )

    # Process input, using library for known sequences
    # Save new discoveries if save_sequences specified
```

**Benefits**:

1. **Portability**: Share sequence libraries across systems (text format, human-readable)
2. **Reusability**: Build up knowledge over multiple runs
3. **Memory efficiency**: Support 100k+ sequences with bounded memory
4. **Transparency**: Users can inspect, edit, or manually create sequence files
5. **Incremental learning**: Accumulate patterns over time without memory growth
6. **Resilience**: Stop and resume long-running jobs without losing discovered patterns

**Trade-offs**:

- **Pro**: User-facing feature with clear value (vs. hidden cache)
- **Pro**: Human-readable format enables manual curation
- **Pro**: LRU keeps frequently-used sequences hot in memory
- **Pro**: Stop/resume doesn't require full state serialization (just finalized sequences)
- **Con**: Disk I/O on cold sequences (acceptable for rare patterns)
- **Con**: Need to track content lines (not just hashes) for export
- **Con**: Stop/resume loses in-progress matches (acceptable - most knowledge preserved)

**Future Enhancement**:

Could support multiple formats:
- `.seq` (text, human-readable)
- `.seqdb` (SQLite, for very large libraries with indexing)
- `.json` (for tool integration)

### Core Algorithm Updates (deduplicator.py)

**New constants**:
```python
MIN_SEQUENCE_LENGTH = 10
DEFAULT_MAX_HISTORY = 100000  # 100k lines of history = ~3.2 MB memory
DEFAULT_MAX_UNIQUE_SEQUENCES = 10000  # 10k unique patterns = ~320 KB
```

**New helper class** (PositionalFIFO for window hash history):
```python
class PositionalFIFO:
    """
    Positional FIFO for window hash history.

    Maintains ordering and position tracking for window hashes without LRU reordering.
    Supports efficient lookup of all positions matching a given hash.
    """
    __slots__ = ['maxsize', 'position_to_key', 'key_to_positions',
                 'next_position', 'oldest_position']

    def __init__(self, maxsize: int):
        self.maxsize = maxsize
        self.position_to_key = {}  # position -> key
        self.key_to_positions = {}  # key -> [pos1, pos2, ...]
        self.next_position = 0
        self.oldest_position = 0

    def append(self, key: str) -> int:
        """Add key, return position. Evicts oldest if at capacity."""
        position = self.next_position

        # Evict oldest if at capacity
        if len(self.position_to_key) >= self.maxsize:
            old_key = self.position_to_key[self.oldest_position]
            self.key_to_positions[old_key].remove(self.oldest_position)
            if not self.key_to_positions[old_key]:
                del self.key_to_positions[old_key]
            del self.position_to_key[self.oldest_position]
            self.oldest_position += 1

        # Add new entry
        self.position_to_key[position] = key
        if key not in self.key_to_positions:
            self.key_to_positions[key] = []
        self.key_to_positions[key].append(position)
        self.next_position += 1

        return position

    def find_all_positions(self, key: str) -> list[int]:
        """Get all positions with this key."""
        return self.key_to_positions.get(key, [])

    def get_key(self, position: int) -> Optional[str]:
        """Get key at position."""
        return self.position_to_key.get(position)

    def get_next_position(self, position: int) -> int:
        """Get next position (position + 1).

        Note: History advances in lockstep with processing, so next position always exists
        when we're comparing. If this returns a position not in history, it indicates a bug.
        """
        return position + 1
```

**New data structures and parameters**:
```python
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

@dataclass
class UniqSeq:
    """A unique sequence pattern identified during processing.

    Note: No __slots__ because we have a list field (window_hashes) that grows dynamically.
    """
    start_window_hash: str      # Hash of first window
    full_sequence_hash: str     # Hash identifying the sequence (length + all window hashes)
    start_line: int             # Output line number where first seen
    sequence_length: int        # Number of lines in sequence
    repeat_count: int           # How many times seen (excluding first)
    window_hashes: list[str] = field(default_factory=list)  # ALL window hashes (one per line)

@dataclass
class NewSequenceCandidate:
    """A new sequence being built from current input, tracked until finalized.

    Note: No __slots__ because we have list fields that grow dynamically.
    Created only when window hash matches history (not for UniqSeq matches).
    """
    current_start_line: int     # Output line number where this sequence started
    lines_matched: int          # How many lines in this sequence so far
    window_hashes: list[str] = field(default_factory=list)  # ALL window hashes
    start_window_hash: str      # First window hash
    buffer_depth: int           # How many lines deep in buffer this extends

    # Tracking which history positions still match
    matching_history_positions: set[int] = field(default_factory=set)

@dataclass
class PotentialHistoryMatch:
    """Links a new sequence candidate to a position in history.

    Note: No __slots__ because parent has list field.
    """
    history_position: int       # Current position in history being compared
    new_seq_id: str             # ID of NewSequenceCandidate this matches

@dataclass
class PotentialUniqSeqMatch:
    """Tracking potential duplicate of a previously identified sequence.

    Note: Direct duplicates are handled immediately without creating a NewSequenceCandidate.
    """
    __slots__ = ['candidate_seq', 'current_start_line', 'next_window_index', 'window_size']
    candidate_seq: UniqSeq      # Existing sequence we're comparing to
    current_start_line: int     # Output line number where this match started
    next_window_index: int      # Index in candidate_seq.window_hashes for next expected window
    window_size: int            # Window size (needed to calculate lines_matched)

    def get_lines_matched(self) -> int:
        """Calculate how many lines matched so far."""
        return self.window_size + (self.next_window_index - 1)

    def get_buffer_depth(self, line_num_output: int) -> int:
        """Calculate how deep in buffer this match extends."""
        lines_matched = self.get_lines_matched()
        return (self.current_start_line - line_num_output) + lines_matched

def __init__(
    self,
    window_size: int = MIN_SEQUENCE_LENGTH,
    max_history: int = DEFAULT_MAX_HISTORY,  # 100k lines
    max_unique_sequences: int = DEFAULT_MAX_UNIQUE_SEQUENCES,  # 10k patterns
    # New parameters for annotation/archiving:
    skip_annotation: Optional[str] = None,  # Format string for annotation
    line_number_mode: str = "absolute",     # "absolute" or "relative"
    archive_dir: Optional[Path] = None,     # Directory for archived content
    archive_filename: str = "uniqseq-{hash}.txt",  # Filename format
):
    # Positional FIFO for window hash history (no LRU reordering)
    self.window_hash_history = PositionalFIFO(maxsize=max_history)

    # Delay buffer - window hashes wait here before entering history
    self.window_hash_delay_buffer = deque(maxlen=window_size)

    # Unique sequences (LRU-evicted at max_unique_sequences)
    # Key: start_window_hash (used to trigger potential match tracking)
    # Value dict: full_sequence_hash -> UniqSeq
    # Note: Using OrderedDict for LRU eviction (most recently accessed at end)
    self.unique_sequences = OrderedDict()  # OrderedDict[str, dict[str, UniqSeq]]
    # Note: This is a two-level dict to support multiple sequences with same start hash

    # New sequences being built from current input
    # Key: unique ID for this new sequence (e.g., f"new_{start_line}")
    self.new_sequence_candidates = {}  # dict[str, NewSequenceCandidate]

    # Active matches to window hash history (detecting NEW sequences)
    # Key: (new_seq_id, history_position)
    self.potential_history_matches = {}  # dict[tuple[str, int], PotentialHistoryMatch]

    # Active matches to known unique sequences (detecting duplicates)
    # Key: f"uniq_{line_num}_{seq_hash}"
    self.potential_uniq_matches = {}  # dict[str, PotentialUniqSeqMatch]

    # Line buffer (grows beyond window_size to accommodate active matches)
    self.line_buffer = deque()  # Grows as needed for active matches

    # Output line tracking
    self.line_num_input = 0      # Lines read from input
    self.line_num_output = 0     # Lines emitted to output

    # Statistics
    self.lines_skipped = 0
    self.annotations_emitted = 0
    self.sequences_archived = 0
```

**Completely rewritten processing logic**:

Old algorithm (single-pass, loses context):
```python
# OLD - INCORRECT
if seq_hash in self.sequence_history:
    # Duplicate detected! Discard buffer
    self.line_buffer.clear()
    self.hash_buffer.clear()
    self.lines_skipped += self.window_size
```

New algorithm (multi-phase with context preservation and anchor-based matching):
```python
def process_line(self, line: str, output: TextIO):
    """Process a single line through multi-phase duplicate detection."""
    self.line_num_input += 1

    # Add line to buffer
    self.line_buffer.append(line)

    # Need full window before processing
    if len(self.line_buffer) < self.window_size:
        return

    # Calculate window hash for current position
    current_window_hash = self._hash_window(self.line_buffer, -self.window_size)

    # === PHASE 1: Update existing potential matches ===
    self._update_potential_history_matches(current_window_hash)
    self._update_potential_uniq_matches(current_window_hash)

    # === PHASE 1b: Update new sequence candidates state ===
    for new_seq in self.new_sequence_candidates.values():
        new_seq.lines_matched += 1
        new_seq.buffer_depth += 1
        # Store every window hash (checked once we have window_size lines)
        new_seq.window_hashes.append(current_window_hash)

    # === PHASE 2: Check if any new sequences should be finalized ===
    # A new sequence is finalized when all its potential match candidates are eliminated
    self._check_for_finalization()

    # === PHASE 3: Start new potential matches ===
    self._check_for_new_history_matches(current_window_hash)
    self._check_for_new_uniq_matches(current_window_hash)

    # === PHASE 4: Add to delay buffer (eventually enters history) ===
    evicted_hash = None
    if len(self.window_hash_delay_buffer) == self.window_size:
        # About to evict - add it to history first
        evicted_hash = self.window_hash_delay_buffer[0]
        position = self.window_hash_history.append(evicted_hash)

    self.window_hash_delay_buffer.append(current_window_hash)

    # === PHASE 5: Emit lines not consumed by active matches ===
    self._emit_available_lines(output)

def _update_potential_history_matches(self, current_window_hash: str):
    """Update matches against window hash history by comparing each new window hash."""
    for (new_seq_id, history_pos), hist_match in list(self.potential_history_matches.items()):
        new_seq = self.new_sequence_candidates[new_seq_id]

        # Get next expected position in history
        next_history_pos = self.window_hash_history.get_next_position(hist_match.history_position)

        # Get the window hash at next position
        next_hash = self.window_hash_history.get_key(next_history_pos)

        if next_hash is None:
            # History position doesn't exist - this should NEVER happen since we add in lockstep
            raise RuntimeError(
                f"History position {next_history_pos} does not exist. "
                f"This indicates a bug in the algorithm - history should advance "
                f"in lockstep with current processing."
            )

        if current_window_hash != next_hash:
            # Mismatch! Remove this history position from candidate's match set
            new_seq.matching_history_positions.discard(history_pos)
            del self.potential_history_matches[(new_seq_id, history_pos)]
            continue

        # Match continues - advance position
        hist_match.history_position = next_history_pos

def _check_for_finalization(self):
    """Check if any new sequence candidates should be finalized.

    A new sequence is finalized when all history match candidates are eliminated.
    """
    for new_seq_id, new_seq in list(self.new_sequence_candidates.items()):
        # Check if all history match candidates are gone
        if len(new_seq.matching_history_positions) == 0:
            # No more candidates - finalize this new sequence
            self._finalize_new_sequence(new_seq)
            del self.new_sequence_candidates[new_seq_id]

def _update_potential_uniq_matches(self, current_window_hash: str):
    """Update matches against known unique sequences using window-by-window comparison.

    Note: Checks every line's window hash for simplicity and precision.
    Optimization opportunity: Could check sparsely (every window_size lines) and refine
    only when needed for disambiguation.
    """
    to_remove = []
    confirmed_duplicate = None

    for match_id, match in list(self.potential_uniq_matches.items()):
        # Verify current window hash matches expected hash
        # (We check every window for simplicity and precision)
        expected_hash = match.candidate_seq.window_hashes[match.next_window_index]

        if current_window_hash != expected_hash:
            # Mismatch! This is not a duplicate - remove from tracking
            to_remove.append(match_id)
            continue

        # Window matches! Move to next window
        match.next_window_index += 1

        # Check if we've matched all windows (reached full sequence length)
        if match.next_window_index >= len(match.candidate_seq.window_hashes):
            # CONFIRMED DUPLICATE!
            confirmed_duplicate = match
            to_remove.append(match_id)
            break

    # Clean up non-matching and completed matches
    for match_id in to_remove:
        del self.potential_uniq_matches[match_id]

    # Handle confirmed duplicate
    if confirmed_duplicate:
        self._handle_duplicate(confirmed_duplicate)

def _finalize_new_sequence(self, new_seq: NewSequenceCandidate):
    """
    Finalize a new sequence when all potential matches are eliminated.

    The sequence is complete at this point.
    """
    # Calculate full sequence hash from window hashes
    full_hash = self._calculate_full_sequence_hash(
        new_seq.lines_matched,
        new_seq.window_hashes
    )

    # Check if this exact pattern already exists under this start hash
    if new_seq.start_window_hash in self.unique_sequences:
        seq_dict = self.unique_sequences[new_seq.start_window_hash]
        if full_hash in seq_dict:
            # Already exists - this occurrence is a duplicate!
            existing_seq = seq_dict[full_hash]
            existing_seq.repeat_count += 1

            # LRU update: move to end (most recently matched)
            self.unique_sequences.move_to_end(new_seq.start_window_hash)

            self._handle_duplicate_of_existing(existing_seq, new_seq.current_start_line, new_seq.lines_matched)
            return

    # New unique sequence - register it
    uniq_seq = UniqSeq(
        start_window_hash=new_seq.start_window_hash,
        full_sequence_hash=full_hash,
        start_line=new_seq.current_start_line,  # Line where this sequence started
        sequence_length=new_seq.lines_matched,
        repeat_count=1,  # This current occurrence is first repeat
        window_hashes=new_seq.window_hashes.copy()  # Store all window hashes for future matching
    )

    # Add to two-level dict
    if new_seq.start_window_hash not in self.unique_sequences:
        self.unique_sequences[new_seq.start_window_hash] = {}
    self.unique_sequences[new_seq.start_window_hash][full_hash] = uniq_seq

    # LRU update: move to end (most recently added/used)
    self.unique_sequences.move_to_end(new_seq.start_window_hash)

    # This occurrence (current) is a duplicate - skip it
    self._handle_duplicate_of_new(uniq_seq, new_seq.current_start_line, new_seq.lines_matched)

    # LRU eviction if needed when adding new unique sequences
    total_seqs = sum(len(seq_dict) for seq_dict in self.unique_sequences.values())
    if total_seqs > self.max_unique_sequences:
        # LRU eviction: remove least recently used (first in OrderedDict)
        lru_start_hash = next(iter(self.unique_sequences))
        del self.unique_sequences[lru_start_hash]

def _emit_available_lines(self, output: TextIO):
    """
    Emit lines from buffer that are not part of any active match.

    Lines can be emitted once they're beyond the buffer_depth of all active new sequences and uniq matches.
    """
    # Find minimum buffer depth across all active matches
    min_depth = self.window_size  # Default: can emit beyond window

    for new_seq in self.new_sequence_candidates.values():
        min_depth = max(min_depth, new_seq.buffer_depth)

    for match in self.potential_uniq_matches.values():
        min_depth = max(min_depth, match.get_buffer_depth(self.line_num_output))

    # Emit lines beyond min_depth
    while len(self.line_buffer) > min_depth:
        line = self.line_buffer.popleft()
        output.write(line)
        if not line.endswith("\n"):
            output.write("\n")
        self.line_num_output += 1

        # Decrement buffer_depth for all active new sequences
        # (PotentialUniqSeqMatch buffer_depth is now calculated, not stored)
        for new_seq in self.new_sequence_candidates.values():
            new_seq.buffer_depth -= 1
```

**New helper methods**:

```python
def _hash_window(self, buffer: deque, offset: int) -> str:
    """
    Hash a window of lines from buffer.

    Args:
        buffer: Line buffer (deque)
        offset: Negative offset from end (e.g., -10 for last 10 lines)

    Returns:
        8-byte (16-char hex) Blake2b hash of window
    """
    start_idx = len(buffer) + offset
    window_lines = list(buffer)[start_idx:start_idx + self.window_size]
    assert len(window_lines) == self.window_size

    combined = "\n".join(window_lines)
    return hashlib.blake2b(combined.encode("utf-8"), digest_size=8).hexdigest()

def _calculate_full_sequence_hash(self, length: int, window_hashes: list[str]) -> str:
    """
    Calculate identifying hash for a sequence pattern.

    Combines sequence length with all window hashes to create a unique
    fingerprint independent of specific line content or line numbers.

    Args:
        length: Number of lines in sequence
        window_hashes: ALL window hashes (one per line)

    Returns:
        16-byte (32-char hex) Blake2b hash uniquely identifying this pattern
    """
    data = f"{length}:{':'.join(window_hashes)}"
    return hashlib.blake2b(data.encode("utf-8"), digest_size=16).hexdigest()

def _check_for_new_history_matches(self, current_window_hash: str):
    """Start tracking potential matches against window hash history."""
    # Find all positions in history with this window hash
    matching_positions = self.window_hash_history.find_all_positions(current_window_hash)

    if not matching_positions:
        return  # No matches

    # Create or get new sequence candidate for this position
    current_start_line = self.line_num_output + len(self.line_buffer) - self.window_size + 1
    new_seq_id = f"new_{current_start_line}"

    if new_seq_id not in self.new_sequence_candidates:
        # Create new sequence candidate
        new_seq = NewSequenceCandidate(
            current_start_line=current_start_line,
            lines_matched=self.window_size,
            window_hashes=[current_window_hash],
            start_window_hash=current_window_hash,
            buffer_depth=self.window_size,
        )
        self.new_sequence_candidates[new_seq_id] = new_seq
    else:
        new_seq = self.new_sequence_candidates[new_seq_id]

    # Link each matching history position to this new sequence
    for history_pos in matching_positions:
        match_key = (new_seq_id, history_pos)
        if match_key in self.potential_history_matches:
            continue  # Already tracking

        # Track this history position match
        self.potential_history_matches[match_key] = PotentialHistoryMatch(
            history_position=history_pos,
            new_seq_id=new_seq_id
        )
        new_seq.matching_history_positions.add(history_pos)

def _check_for_new_uniq_matches(self, current_window_hash: str):
    """Start tracking potential matches against known unique sequences."""
    # Check if any unique sequences start with this window hash
    if current_window_hash not in self.unique_sequences:
        return

    # Get all sequences that start with this hash
    seq_dict = self.unique_sequences[current_window_hash]

    # LRU update: move this start_window_hash to end (most recently used)
    self.unique_sequences.move_to_end(current_window_hash)

    for full_hash, uniq_seq in seq_dict.items():
        # Start tracking potential duplicate of this sequence
        match_id = f"uniq_{self.line_num_input}_{full_hash[:8]}"

        self.potential_uniq_matches[match_id] = PotentialUniqSeqMatch(
            candidate_seq=uniq_seq,
            current_start_line=self.line_num_output + len(self.line_buffer) - self.window_size + 1,
            next_window_index=1,  # Start at index 1 (window_hashes[0] already matched via start_window_hash)
            window_size=self.window_size
        )

def _handle_duplicate(self, match: PotentialUniqSeqMatch):
    """
    Handle confirmed duplicate sequence.

    Marks lines in buffer for skipping, emits annotation, archives content.
    """
    seq_meta = match.candidate_seq

    # Update statistics
    lines_matched = match.get_lines_matched()
    seq_meta.repeat_count += 1
    self.lines_skipped += lines_matched

    # Calculate line numbers for annotation
    if self.line_number_mode == "relative":
        # Relative to current output position
        start_ref = -(self.line_num_output - seq_meta.start_line)
        end_ref = start_ref + seq_meta.sequence_length - 1
    else:
        # Absolute line numbers
        start_ref = seq_meta.start_line
        end_ref = seq_meta.start_line + seq_meta.sequence_length - 1

    # Archive if enabled
    archive_filename = None
    if self.archive_dir:
        archive_filename = self._archive_sequence(
            seq_meta,
            match.current_start_line,
            lines_matched
        )

    # Emit annotation if enabled
    if self.skip_annotation:
        annotation = self._format_annotation(
            start_ref,
            end_ref,
            seq_meta,
            archive_filename
        )
        output.write(annotation + "\n")
        self.annotations_emitted += 1

    # Mark lines for removal from buffer
    buffer_depth = match.get_buffer_depth(self.line_num_output)
    for _ in range(buffer_depth):
        if self.line_buffer:
            self.line_buffer.popleft()

def _archive_sequence(
    self,
    seq_meta: SequenceMetadata,
    start_line: int,
    length: int
) -> str:
    """
    Archive skipped sequence to disk.

    Returns:
        Archive filename (relative to archive_dir)
    """
    from datetime import datetime, timezone

    # Format filename using format string
    timestamp = datetime.now(timezone.utc).isoformat().replace(':', '_')

    filename = self._format_string(
        self.archive_filename,
        start=start_line,
        end=start_line + length - 1,
        count=length,
        hash=seq_meta.full_sequence_hash[:8],
        hash_full=seq_meta.full_sequence_hash,
        timestamp=timestamp,
        seq_num=len(self.unique_sequences),
        instance_num=seq_meta.repeat_count
    )

    # Sanitize filename
    filename = self._sanitize_filename(filename)
    filepath = self.archive_dir / filename

    # Only write if file doesn't exist (idempotent)
    if not filepath.exists():
        # Get the sequence content from buffer
        # TODO: Extract correct lines from buffer
        content = []  # Get from buffer based on match position

        with open(filepath, 'w') as f:
            f.writelines(line + '\n' if not line.endswith('\n') else line
                        for line in content)

        self.sequences_archived += 1

    return filename

def _sanitize_filename(self, filename: str) -> str:
    """Replace unsafe filename characters."""
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    return filename

def _format_annotation(
    self,
    start_ref: int,
    end_ref: int,
    seq_meta: SequenceMetadata,
    archive_filename: Optional[str]
) -> str:
    """Format annotation text using format string."""
    return self._format_string(
        self.skip_annotation,
        start=start_ref,
        end=end_ref,
        count=seq_meta.sequence_length,
        hash=seq_meta.full_sequence_hash[:8],
        hash_full=seq_meta.full_sequence_hash,
        filename=archive_filename or "",
        seq_num=len(self.unique_sequences),
        instance_num=seq_meta.repeat_count
    )

def _format_string(self, template: str, **variables) -> str:
    """Apply format variables to template string."""
    return template.format(**variables)
```

### CLI Updates (cli.py)

**New command-line options**:
```python
@app.command()
def main(
    # ... existing parameters ...

    # New parameters:
    annotate_skips: bool = typer.Option(
        False,
        "--annotate-skips",
        "-a",
        help="Insert annotation when skipping duplicate sequences",
    ),
    annotation_format: str = typer.Option(
        None,  # Default computed based on mode
        "--annotation-format",
        help="Format string for skip annotations (supports: {start}, {end}, {count}, {hash}, {filename})",
    ),
    line_numbers: Optional[str] = typer.Option(
        None,
        "--line-numbers",
        help="Line number format: 'absolute' (1-indexed) or 'relative' (back N lines). Auto-detected if not specified.",
    ),
    archive_dir: Optional[Path] = typer.Option(
        None,
        "--archive-dir",
        "-A",
        help="Directory to archive skipped sequences (creates if doesn't exist). Enables archiving.",
    ),
    archive_filename: str = typer.Option(
        "uniqseq-{hash}.txt",
        "--archive-filename",
        help="Filename format for archived sequences (supports: {start}, {end}, {count}, {hash}, {timestamp}, {seq_num}, {instance_num})",
    ),
    max_history: Optional[int] = typer.Option(
        None,  # Auto: unlimited for files, 100k for stdin
        "--max-history",
        "-m",
        help="Maximum lines of history to track. Use 'unlimited' for unbounded. Auto: unlimited for files, 100000 for stdin.",
    ),
):
```

**Default annotation format computation**:
```python
# Constants
DEFAULT_MAX_HISTORY_STREAMING = 100000  # 100k lines of history = 3.2 MB

# Determine line number mode
is_file_mode = input_file is not None
if line_numbers is None:
    line_numbers = "absolute" if is_file_mode else "relative"

# Set default annotation format based on mode
if annotation_format is None:
    if line_numbers == "relative":
        annotation_format = "[... skipped duplicate lines back {start}-{end} ...]"
    else:
        annotation_format = "[... skipped duplicate lines {start}-{end} ...]"

# Set default max_history based on mode
if max_history is None:
    max_history = None if is_file_mode else DEFAULT_MAX_HISTORY_STREAMING  # None = unlimited
elif max_history == "unlimited":  # Handle string "unlimited" from CLI
    max_history = None
```

**Parameter interactions**:
- `--archive-dir <path>`: Enables archiving to specified directory (no annotation unless `--annotate-skips`)
- `--annotate-skips`: Enables inline annotations (no archiving unless `--archive-dir`)
- Both together: Annotates with `{filename}` variable populated
- `--annotation-format`: Requires `--annotate-skips` to have effect
- `--archive-filename`: Requires `--archive-dir` to have effect
- `--line-numbers`: Forces absolute/relative mode (overrides auto-detection)
- `--max-history unlimited`: Unbounded history (use with caution on stdin)

**Example CLI usage**:
```bash
# Basic annotation
uniqseq --annotate-skips input.log > output.log

# Custom annotation format
uniqseq --annotate-skips \
  --annotation-format "[SKIP {start}-{end}]" \
  input.log > output.log

# Archive only (no inline annotation)
uniqseq --archive-dir ./skipped input.log > output.log

# Archive with annotation
uniqseq --annotate-skips --archive-dir ./skipped input.log > output.log

# Full customization
uniqseq \
  --annotate-skips \
  --annotation-format "[Duplicate removed: {count} lines, see {filename}]" \
  --archive-dir ./archive \
  --archive-filename "skip-{timestamp}-{hash}.txt" \
  input.log > output.log
```

## Implementation Details

### Hash-Based Deduplication of Archives

**Goal**: Don't create duplicate archive files for identical sequences

**Mechanism**: Use sequence hash in filename
- Same sequence → same hash → same filename
- File existence check prevents duplicate writes
- Hash collision extremely unlikely (Blake2b 128-bit)

**Archive file structure**:
```
./archive/
  dedup-a3f5c8d9.txt  # First occurrence archived
  dedup-b7e2f1a4.txt  # Different sequence
  dedup-c9d8e6f2.txt  # Another unique sequence
```

If same sequence hash appears again:
- Filename resolves to `dedup-a3f5c8d9.txt`
- File already exists → skip write
- Annotation still references filename

### Line Number Tracking

**Challenge**: Track absolute line numbers for start/end of skipped sequences

**Current state**: `self.line_num` tracks current line being processed

**Calculation**:
```python
# When duplicate detected at line N with window_size W:
start_line = self.line_num - self.window_size + 1
end_line = self.line_num

# Example: line_num=1243, window_size=10
# → start=1234, end=1243 (10 lines: 1234-1243 inclusive)
```

**Edge case**: History clearing
- Line numbers continue monotonically (don't reset)
- Archive files may reference line numbers from original input

### Timestamp Generation

**Format**: ISO 8601 format for sortability and clarity
```python
from datetime import datetime, timezone

timestamp = datetime.now(timezone.utc).isoformat()
# → "2025-11-20T14:32:15.123456+00:00"
```

**Timezone**: Use UTC for consistency across systems

**Precision**: Include microseconds for uniqueness (unlikely but possible multiple skips in same second)

### Sequence Number Tracking

**Two counters for different purposes**:

1. **`{seq_num}`**: Global counter across all unique sequences
   ```python
   # In __init__:
   self.unique_skips_count = 0

   # When archiving NEW sequence (file doesn't exist):
   self.unique_skips_count += 1
   ```
   - Increments once per unique hash (when first archived)
   - Same sequence appearing multiple times → same seq_num
   - Useful for ordering: `skip-0001-{hash}.txt`, `skip-0002-{hash}.txt`

2. **`{instance_num}`**: Per-hash duplicate counter
   ```python
   # In __init__:
   self.sequence_skip_counts = {}  # hash -> count

   # When duplicate detected:
   self.sequence_skip_counts[hash] = self.sequence_skip_counts.get(hash, 0) + 1
   instance_num = self.sequence_skip_counts[hash]
   ```
   - Counts only duplicate occurrences (excludes first/unique occurrence)
   - First duplicate of hash ABC → instance_num=1
   - Second duplicate of hash ABC → instance_num=2
   - Useful for annotations: "3rd time this sequence was skipped"

## Statistics Impact

**New statistics to track**:
```python
def get_stats(self) -> dict:
    return {
        # ... existing stats ...
        "annotations_emitted": self.annotations_emitted,  # How many annotations written
        "sequences_archived": self.unique_skips_count,    # How many unique files created
    }
```

**Stats table output** (when annotation/archiving enabled):
```
Deduplication Statistics
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ Metric                   ┃    Value ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ Total lines processed    │   77,966 │
│ Lines emitted            │   40,811 │
│ Lines skipped            │   37,155 │
│ Annotations inserted     │      312 │  ← NEW
│ Sequences archived       │      127 │  ← NEW
│ Redundancy               │   47.7%  │
│ Unique sequences tracked │    1,234 │
│ Window size              │       10 │
│ Max history              │   10,000 │
└──────────────────────────┴──────────┘
```

## Testing Strategy

### Unit Tests (test_deduplicator.py)

**New test cases**:

1. `test_annotation_basic`: Verify annotation format and placement
2. `test_annotation_format_variables`: Test all format specifiers
3. `test_annotation_disabled`: Confirm no annotations when disabled
4. `test_archive_creates_files`: Verify files created with correct content
5. `test_archive_idempotent`: Same sequence → no duplicate file writes
6. `test_archive_hash_in_filename`: Confirm hash appears in filename
7. `test_archive_custom_format`: Test custom filename format strings
8. `test_annotation_with_archive`: Verify {filename} variable populated
9. `test_annotation_without_archive`: Verify {filename} empty when no archiving
10. `test_line_numbers_accurate`: Verify start/end line numbers correct
11. `test_stats_with_annotation`: Check new statistics tracked correctly

**Testing approach**:
- Use `tempfile.TemporaryDirectory()` for archive testing
- StringIO for output capture (annotation verification)
- Synthetic test data (no real logs)

### Integration Tests

**CLI integration**:
1. Test all CLI flag combinations
2. Verify archive directory creation
3. Test error handling (invalid format strings, permission errors)

### Example Test Implementation

```python
def test_annotation_basic():
    """Test basic skip annotation."""
    dedup = StreamingDeduplicator(
        window_size=3,
        skip_annotation="[SKIP {start}-{end}]"
    )

    output = StringIO()

    # Process: A, B, C, A, B, C (duplicate)
    for line in ["A", "B", "C", "A", "B", "C"]:
        dedup.process_line(line, output)
    dedup.flush(output)

    result = output.getvalue()

    # Should see: A, B, C, [SKIP 4-6]
    assert "A\n" in result
    assert "B\n" in result
    assert "C\n" in result
    assert "[SKIP 4-6]" in result
    assert result.count("A") == 1  # Not duplicated

def test_archive_idempotent(tmp_path):
    """Test that identical sequences don't create duplicate files."""
    dedup = StreamingDeduplicator(
        window_size=3,
        archive_dir=tmp_path,
        archive_filename="dedup-{hash}.txt"
    )

    # Process same sequence twice
    for _ in range(2):
        for line in ["A", "B", "C"]:
            dedup.process_line(line, StringIO())

    # Should only create ONE archive file
    archive_files = list(tmp_path.glob("*.txt"))
    assert len(archive_files) == 1

    # Verify content
    content = archive_files[0].read_text()
    assert content == "A\nB\nC\n"
```

## Edge Cases and Error Handling

### 1. Archive Directory Creation

**Scenario**: User specifies `--archive-dir` but directory doesn't exist

**Behavior**: Create directory automatically (including parent directories)
```python
if self.archive_dir:
    self.archive_dir.mkdir(parents=True, exist_ok=True)
```

### 2. Archive Write Permissions

**Scenario**: Cannot write to archive directory (permissions, disk full)

**Behavior**: Catch exception, emit warning to stderr, continue processing
```python
try:
    filepath.write_text(content)
except OSError as e:
    console.print(f"[yellow]Warning: Could not archive sequence: {e}[/yellow]")
    # Continue without archiving
```

### 3. Invalid Format Strings

**Scenario**: User provides format string with invalid variable

**Examples**:
- `"[SKIP {start}-{end}-{invalid}]"` → KeyError
- `"[SKIP {start:invalid_spec}]"` → ValueError

**Behavior**: Validate format strings at initialization, fail fast with helpful error
```python
def validate_format_string(template: str, allowed_vars: set[str]) -> None:
    """Validate format string contains only allowed variables."""
    # Extract variable names from format string
    try:
        # Test with dummy values
        dummy_values = {var: "test" for var in allowed_vars}
        template.format(**dummy_values)
    except KeyError as e:
        raise ValueError(f"Invalid format variable in template: {e}")
```

### 4. Filename Collisions (Non-Hash)

**Scenario**: User uses timestamp-only filenames, gets collision

**Example**: `--archive-filename "{timestamp}.txt"` with multiple skips in same microsecond

**Behavior**:
- Hash-based names (default) avoid this entirely
- For custom names: add hash as fallback or allow overwrite
- Document best practice: always include `{hash}` in filename format

### 5. Very Long Format Strings

**Scenario**: User provides extremely long annotation format

**Behavior**: No artificial limit, but document best practices
- Annotations become part of output
- Very long annotations may interfere with downstream processing
- Recommend: Keep under 80 characters for readability

### 6. Archive File Size

**Scenario**: Skipped sequences could be very large (e.g., window_size=1000)

**Behavior**:
- No automatic limits (user controls via window_size)
- Document: Archive files can be large depending on window size
- Future consideration: Add `--max-archive-size` option to skip archiving large sequences

### 7. Special Characters in Filenames

**Scenario**: Format string produces invalid filename characters

**Example**: `--archive-filename "skip-{timestamp}.txt"` where timestamp includes `:`

**Behavior**: Sanitize filenames by replacing unsafe characters

**Hash serialization**: Hashes are already hexadecimal (0-9, a-f) - inherently filesystem-safe

**Timestamp sanitization**: Replace `:` with `_` for cross-platform compatibility
```python
def sanitize_filename(filename: str) -> str:
    """Replace unsafe filename characters."""
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    return filename

def format_timestamp() -> str:
    """Generate filesystem-safe ISO timestamp."""
    ts = datetime.now(timezone.utc).isoformat()
    return ts.replace(':', '_')  # 2025-11-20T14_32_15.123456+00_00
```

## Performance Considerations

### Annotation Overhead

**Impact**: Minimal - one additional string format + write per duplicate sequence

**Measurement**: Format operations are O(1), string write is O(n) in annotation length

**Estimate**: <1% overhead for typical use cases (annotations much rarer than line processing)

### Archive I/O Overhead

**Impact**: Moderate - file write per unique duplicate sequence

**Measurement**:
- File existence check: O(1) filesystem lookup
- File write: O(n) in sequence length, but only for *new* unique duplicates

**Mitigation strategies**:
1. File existence check prevents redundant writes (idempotent)
2. Writes happen only on duplicate detection (not every line)
3. Buffered I/O (Python defaults)

**Estimate**:
- Worst case: Every sequence is unique duplicate → W file writes per window
- Typical case: Most duplicates are repeats of same sequence → few file writes
- Example: 77k line file, 312 duplicates, 127 unique → only 127 file writes

### Memory Impact

**New memory usage**:
- Archive directory path: negligible (single Path object)
- Format strings: negligible (two small strings)
- Tracking variables: +2 integers (seq_num, annotation count)
- Per-hash instance counters: dict with O(U) entries where U = unique sequences skipped
  - Worst case: Same as sequence history (already tracked)
  - Typical: Much smaller (only duplicate sequences need counters)
  - Memory: ~50 bytes per entry (hash key + counter) × unique duplicates

**Total additional memory**:
- Base: <1 KB (paths, strings, counters)
- Instance tracking: ~50 bytes per unique duplicate sequence
- Typical: 1-2 MB additional for 20k unique duplicates
- Worst case: Comparable to existing sequence history

## Documentation Updates Required

### README.md

**Add Performance & Memory Section** (new section before Python Module):
```markdown
## Performance & Memory

uniqseq is designed for efficient streaming with minimal memory usage:

### Speed
- **Throughput**: ~20,000 lines/second on typical hardware
- **Algorithm**: O(1) duplicate detection per sequence via hash lookup
- **Total complexity**: O(N) where N = total input lines

### Memory Usage

Memory scales with **unique sequences**, not total file size:

| Component | Memory per Item | Typical Usage |
|-----------|----------------|---------------|
| Line buffer | ~100 bytes/line | 10 lines (window) = 1 KB |
| Sequence history | ~32 bytes/hash | 100k sequences = 3.2 MB |
| **Total** | | **~3-4 MB typical** |

**Default limits**:
- **File mode**: Unlimited history (scales with unique sequences in file)
- **Streaming mode**: 100,000 unique sequences max (3.2 MB)

**Example**: A 1GB log file with 1 million lines but only 5,000 unique 10-line patterns:
- Memory usage: ~160 KB (5k sequences × 32 bytes)
- Processing time: ~50 seconds
- Memory does NOT scale with file size

**For memory-constrained environments** (embedded systems, small containers):
```bash
# Limit to 10k sequences (320 KB memory)
uniqseq --max-history 10000 large.log > output.log

# Limit to 1k sequences (32 KB memory)
cat stream.log | uniqseq --max-history 1000 > output.log
```

**For maximum effectiveness** (unlimited history):
```bash
# Use all available memory for best deduplication
cat large.log | uniqseq --max-history unlimited > output.log
```
```

**Add Python Module Quickstart** (new section):
```markdown
## Using as a Python Module

uniqseq can be imported and used directly in Python code:

```python
from uniqseq import StreamingDeduplicator
from pathlib import Path

# Basic usage
dedup = StreamingDeduplicator(window_size=10)

with open("input.log", "r") as infile, open("output.log", "w") as outfile:
    for line in infile:
        dedup.process_line(line.rstrip("\n"), outfile)
    dedup.flush(outfile)

# Get statistics
stats = dedup.get_stats()
print(f"Removed {stats['redundancy_pct']:.1f}% redundancy")

# With annotation and archiving
dedup = StreamingDeduplicator(
    window_size=10,
    skip_annotation="[... skipped lines {start}-{end} ...]",
    archive_dir=Path("./duplicates"),
    archive_filename="dup-{hash}.txt"
)

# Process with progress callback
def progress(line_num, skipped, seq_count):
    if line_num % 1000 == 0:
        print(f"Processed {line_num:,} lines...", file=sys.stderr)

with open("input.log", "r") as infile:
    for line in infile:
        dedup.process_line(line.rstrip("\n"), sys.stdout, progress_callback=progress)
    dedup.flush(sys.stdout)
```

**Add section on annotation and archiving features**:
```markdown
## Skip Annotation

Optionally insert inline annotations showing where duplicate sequences were removed:

```bash
# File mode - absolute line numbers
uniqseq --annotate-skips session.log > clean.log
# Output: [... skipped duplicate lines 1234-1243 ...]

# Streaming mode - relative line numbers
cat session.log | uniqseq --annotate-skips > clean.log
# Output: [... skipped duplicate lines back 50-41 ...]

# Force absolute line numbers
uniqseq --annotate-skips --line-numbers absolute < input.log > output.log
```

Customize annotation format:
```bash
uniqseq --annotate-skips \
  --annotation-format "[DUPLICATE: {count} lines removed (hash={hash})]" \
  session.log > clean.log
```

Available format variables: `{start}`, `{end}`, `{count}`, `{hash}`, `{hash_full}`, `{timestamp}`, `{filename}`, `{seq_num}`, `{instance_num}`

## Archiving Skipped Content

Preserve skipped sequences to disk for later review:

```bash
# Archive only (no inline annotations)
uniqseq --archive-dir ./skipped session.log > clean.log

# Archive with annotations showing filenames
uniqseq --annotate-skips --archive-dir ./archive session.log > clean.log
# Output: [... skipped duplicate lines 1234-1243 (archived: uniqseq-a3f5c8d9.txt) ...]

# Custom archive filename format
uniqseq --archive-dir ./archive \
  --archive-filename "dup-{seq_num:04d}-{hash}.txt" \
  session.log > clean.log
```

Each unique sequence is saved once (hash-based deduplication). If the same sequence appears multiple times, it references the same archive file.

## History Depth

By default:
- **File mode**: Unlimited history (deduplicates entire file)
- **Streaming mode**: 100,000 unique sequences max (3.2 MB memory)

Override:
```bash
# Unlimited history for stdin
cat large.log | uniqseq --max-history unlimited > output.log

# Limit to 10k lines of history (320 KB memory)
uniqseq --max-history 10000 large.log > output.log

# Very small memory footprint - 1k lines of history (32 KB)
cat stream.log | uniqseq --max-history 1000 > output.log
```

Memory scales with unique sequences seen, not total file size. A 1GB file with only 5k unique patterns uses ~160 KB.
```

### IMPLEMENTATION.md

Add new sections:
- "Skip Annotation Design" under Design Decisions
- "Archive File Format" under Implementation Details
- "Relative Line Numbering" under Implementation Details
- Update "Statistics Tracking" section with new metrics
- Update "Performance Characteristics" with new default (100k history) and memory calculations
- Add "History Depth Strategy" section explaining file vs streaming mode defaults

### CLI Help Text

Expand help for new options with examples of format variables

## Algorithm Implementation Notes

**Critical Implementation Details:**

1. **PositionalFIFO maintains order without LRU reordering**:
   - Window hash history uses position-based indexing (monotonically increasing positions)
   - No LRU reordering - positions are fixed once assigned
   - Reverse index (`key_to_positions`) allows efficient lookup of all matching positions
   - Eviction removes oldest position when at capacity

2. **Window-by-window matching for precise comparison**:
   - Both NEW sequences and unique sequences store ALL window hashes
   - `PotentialUniqSeqMatch` tracks `next_window_index` and verifies EVERY window
   - Each new line generates a window hash that's compared to expected hash
   - Mismatch immediately terminates match - no gap in detection
   - **Simplicity over optimization**: Check every window (not just every `window_size` lines)
   - **Future optimization**: Could check every `window_size` lines, then do fine-grained matching only for disambiguation
   - This prevents line buffer from being held up by non-matching patterns

3. **History position tracking for NEW sequences**:
   - `PotentialHistoryMatch` tracks `history_position` (current position in history)
   - **Every new window hash** is compared to next position
   - Get next position's hash via `get_key(next_position)`
   - If current doesn't match next position's hash → mismatch, remove from tracking
   - Window hashes stored at boundaries for both history matching and future UniqSeq creation
   - Position tracking eliminates need for index arithmetic

4. **Named properties via dataclasses**:
   - Use `match.history_position` instead of `match[1]`
   - Type-safe and self-documenting
   - Note: `__slots__` NOT used for classes with dynamic list fields (`UniqSeq`, `PotentialHistoryMatch`) to allow list growth

5. **Line consumption and buffer management**:
   - Buffer ALL lines involved in active potential matches
   - Track `buffer_depth` for each match (how many lines deep it extends)
   - Emit lines only when beyond ALL active match depths
   - As lines emit, decrement buffer_depth for all matches
   - Anchor mismatch immediately removes match from tracking → reduces buffer depth

6. **Unique sequence two-level dict structure**:
   - Outer key: `start_window_hash` (used to trigger potential match tracking)
   - Inner key: `full_sequence_hash` (distinguishes sequences with same start)
   - Structure: `dict[str, dict[str, UniqSeq]]`
   - Allows multiple sequences starting with same window hash to coexist
   - Start hash is ESSENTIAL for knowing when to begin tracking potential matches

7. **Line numbering for annotations**:
   - Both absolute and relative modes reference OUTPUT line numbers
   - Absolute: `start_line` from UniqSeq (where first emitted)
   - Relative: Calculate offset from current `line_num_output`

## Design Decisions Summary (User-Confirmed)

✅ **History depth**:
- File mode: Unlimited by default
- Streaming mode: 100,000 lines of history by default (3.2 MB memory)
- User can override with `--max-history N` or `--max-history unlimited`
- Memory scales with unique sequences seen: ~32 bytes per unique sequence

✅ **Line numbering**:
- File mode: Absolute line numbers (1-indexed)
- Streaming mode: Relative format `[back N-M lines]`
- Auto-detected based on input source
- Override with `--line-numbers absolute|relative`

✅ **Module support**:
- All functionality available via Python import
- Document in README.md with quickstart examples

✅ **Archive directory**:
- No default directory
- Archiving enabled by explicit `--archive-dir <path>`

✅ **Filename format**:
- Default: `uniqseq-{hash}.txt`
- Hash is 8-char hex (filesystem-safe)
- Timestamp sanitized for cross-platform compatibility

✅ **Instance counter (`{instance_num}`)**:
- Counts only duplicate skips (excludes first occurrence)
- Per-hash tracking
- Use case: "This is the 3rd time this sequence was removed"

✅ **Annotation counting**:
- Separate stat: `annotations_emitted`
- Not included in `lines_emitted` (those are data lines only)

✅ **Archive file format**:
- Plain text (same as input)
- No metadata headers (keeps files simple and reusable)

✅ **Timestamp**:
- UTC timezone
- ISO 8601 format with `:` replaced by `_` for filenames

✅ **Archive directory structure**:
- Flat directory (all files in same level)
- Simple and predictable

✅ **Error handling**:
- Archive write failures: Warn to stderr, continue processing
- Deduplication continues even if archiving fails

## Remaining Open Questions

**None** - All design decisions confirmed and ready for implementation!

## Implementation Checklist

- [ ] Core deduplicator changes
  - [ ] Add annotation parameters to `__init__`
  - [ ] Implement `_archive_sequence` method
  - [ ] Implement `_format_annotation` method
  - [ ] Implement `_format_string` method
  - [ ] Add annotation emission in duplicate detection path
  - [ ] Add sequence number and annotation count tracking
  - [ ] Update `get_stats` with new metrics
- [ ] CLI changes
  - [ ] Add new command-line options
  - [ ] Add archive directory creation
  - [ ] Update stats display with new metrics
  - [ ] Add validation for format strings
  - [ ] Add error handling for archive failures
- [ ] Testing
  - [ ] Unit tests for annotation formatting
  - [ ] Unit tests for archiving logic
  - [ ] Unit tests for idempotent archive writes
  - [ ] Integration tests for CLI options
  - [ ] Edge case tests (permissions, invalid formats, etc.)
- [ ] Documentation
  - [ ] Update README.md with feature examples
  - [ ] Update IMPLEMENTATION.md with design details
  - [ ] Update CLI help text
  - [ ] Add docstrings to new methods
- [ ] Manual testing
  - [ ] Test with real session logs
  - [ ] Verify archive file contents
  - [ ] Test various format string combinations
  - [ ] Verify statistics accuracy

## Timeline Estimate

- Core implementation: 2-3 hours
- Testing: 2-3 hours
- Documentation: 1 hour
- Total: 5-7 hours

## Backward Compatibility

**Fully backward compatible**:
- All new features are opt-in via CLI flags
- Default behavior unchanged (no annotation, no archiving)
- Existing scripts and pipelines unaffected
- API additions only (no breaking changes to existing methods)

## Next Steps

1. **User review this document** - confirm design approach
2. **Answer open questions** - finalize format strings and defaults
3. **Approve for implementation** - or request changes
4. **Implement** - follow checklist above
5. **Test thoroughly** - all test cases pass
6. **Update documentation** - ensure production-ready docs
7. **Ready for release** - potentially as v0.2.0
