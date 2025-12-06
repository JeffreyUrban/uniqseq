# Design Decisions

Why uniqseq works the way it does.

## Core Principles

### 1. Streaming First

**Decision**: All features work with unbounded streams and bounded memory.

**Why**: Real-world use cases like `tail -f server.log | uniqseq` require streaming. We don't want uniqseq to fail or slow down as files get larger.

**Impact**:
- ✅ Can process GB-sized files with minimal memory
- ✅ Works with live log streams
- ✅ Predictable performance
- ⚠️ Some features (like "show only duplicates") delayed until stream ends

### 2. Unix Philosophy

**Decision**: Do one thing well - deduplicate multi-line sequences.

**Why**: There are already excellent tools for:
- Pattern extraction (grep, awk)
- Log parsing (Drain, logparser)
- Text transformation (sed)

uniqseq focuses on what they don't do: finding and removing repeated multi-line patterns.

**Impact**:
- ✅ Simpler, faster tool
- ✅ Composes well with existing Unix tools
- ✅ Easier to understand and maintain
- ❌ Won't add features better served by other tools

### 3. Position-Aware Matching

**Decision**: Track WHERE sequences occur, not just THAT they occurred.

**Why**: Without position tracking, overlapping sequences cause incorrect deduplication:

```
Bad approach (hash-only):
A B C     ← Seen hash ABC
A B C D   ← Hash ABC seen, skip all?
          ❌ Skips line D incorrectly!

Good approach (position-aware):
A B C     ← Seen at position 0
A B C D   ← Overlaps with position 0, don't skip D
          ✓ Correctly keeps D
```

**Impact**:
- ✅ Accurate deduplication in complex scenarios
- ✅ Handles overlapping sequences correctly
- ⚠️ Slightly more complex implementation

## Feature Decisions

### ✅ Included: Skip Characters

**Feature**: `--skip-chars N` ignores first N characters when comparing lines.

**Why**: Extremely common use case - logs with timestamps:

```
[2024-01-15 10:30:01] Error: Connection failed
[2024-01-15 10:30:05] Error: Connection failed
                      └─ Same error, different timestamp
```

**Alternatives considered**:
- Use external preprocessing (`sed`, `awk`)
- **Problem**: Inefficient, breaks streaming, complex to compose

**Decision**: Built-in feature with simple integer parameter.

### ✅ Included: Pattern Filtering (Track/Bypass)

**Feature**: `--track` and `--bypass` filter which lines to deduplicate.

**Why**: The "stream reassembly problem" - you can't efficiently filter and reassemble streams:

```
Goal: Deduplicate ERROR lines, keep DEBUG lines

Attempt with grep:
grep 'ERROR' | uniqseq | ???
              └─ DEBUG lines lost!

With track:
uniqseq --track '^ERROR'
└─ ERROR lines deduplicated, DEBUG lines passed through
```

**Decision**: Built-in features for filtering.

### ✅ Included: Window Size

**Feature**: `--window-size N` sets sequence length.

**Why**: Different use cases need different sequence lengths:

- **Duplicate single lines**: `--window-size 1` (default)
- **3-line stack traces**: `--window-size 3`
- **10-line error blocks**: `--window-size 10`

**Decision**: Core parameter, essential for usefulness.

### ❌ Excluded: Multi-File Comparison

**Feature**: Compare sequences across multiple files.

**Why excluded**: Violates streaming principle - would require loading all files.

**Alternative**:
```bash
# Concatenate first, then deduplicate
cat file1.log file2.log | uniqseq
```

**Decision**: Composition works perfectly, no need for built-in feature.

### ❌ Excluded: Custom Sort Orders

**Feature**: Sort output by various criteria.

**Why excluded**: Unix already has `sort`:

```bash
# Want sorted output?
uniqseq input.log | sort
```

**Decision**: Use `sort`, don't reinvent it.

## Memory Management

### History Limits

**Decision**: Default maximum of 10,000 unique sequences tracked.

**Why**:
- Prevents unbounded memory growth
- 10k is enough for most real-world cases
- Configurable via `--max-entries` if needed

**Trade-off**:
- ✅ Predictable memory usage
- ⚠️ Very old sequences forgotten after limit reached
- ✅ Streaming still works for unlimited input

### Hash Function Choice

**Decision**: Use BLAKE2b for sequence hashing.

**Why**:
- Fast cryptographic hash function
- Low collision rate
- Part of Python standard library (no external dependencies)
- Consistent across platforms

**Alternatives considered**:
- Python's built-in `hash()` - not consistent across runs
- MD5/SHA - slower, less performant than BLAKE2b
- xxHash - faster but requires external dependency

## CLI Design

### Why Flags Over Positional Args?

**Decision**: All options are flags (`--window-size 3`), not positional.

**Why**:
- Clearer what each parameter does
- Optional parameters easy to add
- Better shell completion
- Follows modern CLI conventions

### Why No Config Files?

**Decision**: No `.uniqseqrc` or config files.

**Why**:
- Tool used in one-off commands and pipelines
- Shell aliases work fine for common patterns:
  ```bash
  alias uniqseq-logs='uniqseq --window-size 3 --skip-chars 21'
  ```
- Avoids "spooky action at a distance"

## Library vs CLI

### Why Both?

**Decision**: Provide both Python library and CLI tool.

**Why**:
- **CLI**: Most users want command-line tool
- **Library**: Some users need Python integration
- Same implementation, minimal extra code

**Benefit**: Users can start with CLI, graduate to library if needed.

## Next Steps

- **[Algorithm Details](algorithm.md)** - How it's implemented
- **[Contributing](contributing.md)** - Help improve uniqseq
