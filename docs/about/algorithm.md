# How uniqseq Works

A detailed look at the algorithm behind uniqseq.

## Core Algorithm

uniqseq uses a **sliding window** approach combined with **hash-based duplicate detection** to efficiently find and remove repeated sequences.

### The Process

1. **Read line by line** (streaming, no need to load entire file)
2. **Maintain a sliding window** of N lines (where N = window size)
3. **Compute a hash** for each window position
4. **Check if hash seen before** in the history
5. **Keep or skip** lines based on whether they're part of a duplicate sequence

## Key Concepts

### Position-Based Tracking

Unlike simple hash tables that only track "seen before", uniqseq tracks **WHERE** each sequence occurs:

```
Position 0: Hash ABC → Lines 1-3
Position 1: Hash BCD → Lines 2-4
Position 2: Hash CDE → Lines 3-5
...
Position 100: Hash ABC → Lines 101-103 (duplicate!)
```

This positional tracking enables:
- **Accurate duplicate detection** even with overlapping sequences
- **First-occurrence preservation** - always keep the earliest match
- **Multi-candidate evaluation** - handle complex matching scenarios

### Two-Phase Matching

#### Phase 1: New Sequence Detection

When processing lines, uniqseq looks for **new sequences** forming:

```
Line 1 ─┐
Line 2  │ Window 1 (hash: H1)
Line 3 ─┘
Line 4 ─┐
Line 5  │ Window 2 (hash: H2)
Line 6 ─┘
```

If hash H1 appears again later, it marks the start of a potential duplicate.

#### Phase 2: Known Sequence Matching

Once a sequence is identified, uniqseq stores it as a "known sequence" and directly compares future windows against it:

```
Stored Sequence:
  Line 1
  Line 2
  Line 3

Future Input:
  Line 1  ← Match!
  Line 2  ← Match!
  Line 3  ← Match! (Duplicate found, skip)
```

### Subsequence Matching

uniqseq uses **subsequence matching** - it continues matching beyond the initial window size to find extended sequences:

```
Known 3-line sequence:
  Line 1
  Line 2
  Line 3

Future Input (continues matching):
  Line 1  ← Match!
  Line 2  ← Match!
  Line 3  ← Match!
  Line 4  ← Still matching! (extended)
  Line 5  ← Still matching! (extended)
  Line 6  ← No match, stop here
```

**Key behaviors**:

1. **Matching continues**: When a known sequence is matched, uniqseq keeps comparing subsequent lines
2. **Extended sequences are saved**: The 5-line extended sequence (Lines 1-5) is saved as a NEW sequence with a different hash
3. **No exact-length requirement**: Sequences don't need to match the exact window size, just start with a known pattern

**Example with library mode**:

```
Initial run discovers:
  ERROR: Connection failed
  Retrying in 5s
  → Saved as sequence A

Second run encounters:
  ERROR: Connection failed
  Retrying in 5s
  Failed after 3 retries
  → Matches sequence A, continues matching
  → Saved as new sequence B (extended version)

Both sequences coexist in library:
  - Sequence A: 2 lines
  - Sequence B: 3 lines (superset of A)
```

This allows uniqseq to:
- Discover progressively longer patterns
- Build libraries that grow over time
- Recognize both short and long versions of similar sequences

### Overlap Prevention

uniqseq prevents matching overlapping windows using position arithmetic:

```
Sequence matched at position 10 (lines 10-12, window size 3)
→ Next matchable position: 10 + 3 = 13

Lines 11-13 cannot match (position 11 < 13)
Lines 12-14 cannot match (position 12 < 13)
Lines 13-15 can match (position 13 >= 13) ✓
```

This ensures clean, non-overlapping deduplication.

## Memory Efficiency

### Bounded History

uniqseq uses a **configurable maximum history size** (default 100,000 entries):

```
History FIFO:
┌─────────────────────────┐
│ Pos 0: Hash A          │
│ Pos 1: Hash B          │
│ ...                     │
│ Pos 99999: Hash Z      │  ← When full, oldest entry
└─────────────────────────┘     removed (Pos 0)
```

The `--max-history` option controls this limit (or `--unlimited-history` for file processing).

### Bounded Unique Sequences

uniqseq also limits the **number of unique sequences tracked** (default 10,000 sequences):

```
Unique Sequences LRU Cache:
┌─────────────────────────┐
│ Seq 1: "Error\nLog\n"  │  ← Most recently used
│ Seq 2: "Info\nOK\n"    │
│ ...                     │
│ Seq 9999: "Old\nMsg"   │
│ Seq 10000: "Rare\nSeq" │  ← Least recently used,
└─────────────────────────┘     evicted when new sequence added
```

The `--max-unique-sequences` option controls this limit. When the limit is reached, the least recently used sequence is evicted to make room for new sequences. Use `--unlimited-unique-sequences` for unbounded tracking (suitable for file processing).

Together, these bounds keep memory usage predictable and bounded regardless of input size.

### Streaming Architecture

uniqseq processes one line at a time:

```
Input Stream → [Window Buffer] → [Hash & Match] → Output Stream
               (fixed size)      (bounded history)
```

**Memory usage**:
- Window buffer: `window_size` lines
- History: Up to `max_history` hashes (default: 100,000)
- Unique sequences: Up to `max_unique_sequences` sequences (default: 10,000)
- Active candidates: Up to `max_candidates` concurrent candidates (default: 100)

This enables processing GB-sized files with minimal memory.

## Performance Characteristics

### Time Complexity

- **Per line**: O(window_size × num_candidates)
  - Where `num_candidates` is limited by `max_candidates` (default: 100)
  - Typically 1-2 candidates for most inputs, but can spike with complex patterns
  - Lower `max_candidates` improves performance but may miss some patterns
- **Amortized**: O(n) for n lines

### Space Complexity

- **History**: O(max_history) - bounded, configurable (default: 100,000)
- **Unique sequences**: O(max_unique_sequences × avg_seq_length) - bounded, configurable (default: 10,000)
- **Window buffer**: O(window_size) - very small

### Hash Function

uniqseq uses **BLAKE2b** (via Python's hashlib):
- Fast cryptographic hash function
- Low collision rate
- Part of Python standard library (no external dependencies)
- Consistent across platforms

## Skip Characters Feature

The `--skip-chars N` feature works by **normalizing** each line before hashing:

```python
Original line:  "[2024-01-15 10:30:01] Error: Connection failed"
Skip first 21:  "Error: Connection failed"
                └─ This is what gets hashed
```

This happens **before hashing**, so timestamps don't affect duplicate detection.

## Pattern Filtering

### Track Mode (`--track`)

Only lines matching the pattern are considered for deduplication:

```
Input:
  ERROR: Failed  ← Tracked (deduplicated)
  INFO: Success  ← Not tracked (passed through)
  ERROR: Failed  ← Tracked (duplicate, removed)
  INFO: Success  ← Not tracked (passed through)
```

### Bypass Mode (`--bypass`)

Lines matching the pattern are never deduplicated:

```
Input:
  WARN: Issue    ← Bypassed (always kept)
  ERROR: Failed  ← Deduplicated
  WARN: Issue    ← Bypassed (always kept, even if duplicate)
  ERROR: Failed  ← Duplicate (removed)
```

## Oracle Compatibility

uniqseq's algorithm is validated against an **oracle implementation** - a simple, obviously-correct but slower reference implementation.

All edge cases and complex scenarios are verified to match oracle behavior exactly.

## Next Steps

- **[Design Decisions](design-decisions.md)** - Why these choices were made
- **[Basic Concepts](../getting-started/basic-concepts.md)** - User-focused concepts
