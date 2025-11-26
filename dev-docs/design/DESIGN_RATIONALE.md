# Design Rationale and Trade-offs

**Purpose**: Document why features were included, excluded, or deferred. Explains design decisions and trade-offs.

## Core Design Principles

### 1. Unix Composition Over Feature Bloat

**Principle**: Prefer documented composition patterns over built-in features when composition is efficient and clear.

**Rationale**:
- Smaller, faster tool with less code to maintain
- Users leverage existing knowledge of Unix tools
- Better citizen of Unix ecosystem
- Easier testing with fewer feature interactions

**Application**:
- ✅ Keep features when composition is inefficient, complex, or breaks streaming
- ❌ Cut features when standard tools can achieve the same result simply
- 📖 Document all composition patterns with tested examples

---

### 2. Streaming First

**Principle**: All features must work with unbounded streams and bounded memory.

**Rationale**:
- Real-time monitoring (`tail -f | uniqseq`)
- Predictable memory usage
- Scalable to any input size
- True Unix filter behavior

**Application**:
- History limits (default 100k for stdin, unlimited for files)
- Configurable via `--unlimited-history` when needed
- Features that require full input are deferred or cut

---

### 3. Core Competency Focus

**Principle**: Focus on multi-line sequence deduplication, not general text processing.

**Rationale**:
- Clear value proposition vs existing tools
- Avoid scope creep into areas with better specialized tools
- Maintainable codebase with clear boundaries

**Application**:
- ✅ Features that enhance sequence detection/matching
- ❌ Features better served by grep, awk, sed, Drain, etc.

---

## Feature Inclusion Decisions

### ✅ Kept: Hash Transform (`--hash-transform`)

**Alternative considered**: Built-in flags for common cases (`--skip-until`, `--skip-regex`)

**Decision**: Keep both simple flag (`--skip-chars`) and powerful flag (`--hash-transform`).

**Rationale**:
- Simple case (80%): `--skip-chars N` - fast, no subprocess, covers fixed-width timestamps
- Complex cases (20%): `--hash-transform <cmd>` - full Unix filter power
- Single subprocess (not per-line), streaming-friendly
- Avoids maintaining many similar skip/normalize flags

**Trade-offs**:
- Pro: Flexible, composable, future-proof
- Pro: Users can bring custom normalization scripts
- Con: Slightly more complex than individual flags
- Con: Transform must follow strict 1:1 line contract

**Implementation requirements**:
- Spawn subprocess once, pipe all lines through it
- Validate 1:1 line contract (exactly one output per input)
- Clear error messages when contract violated
- Document valid/invalid transforms

---

### ✅ Kept: Track/Bypass

**Alternative considered**: Preprocess with `grep`, compose streams afterward.

**Decision**: Keep track/bypass built-in.

**Rationale**: **Stream reassembly problem** - Cannot efficiently compose this with streaming constraints.

**The Problem**:
```bash
# Goal: Deduplicate only ERROR lines, but keep DEBUG lines in output

# Attempt 1: Pre-filter with grep
grep 'ERROR' input.log | uniqseq > errors.log
# ❌ Lost DEBUG lines entirely

# Attempt 2: Split, process, merge
cat -n input.log > numbered.log
grep 'ERROR' numbered.log | uniqseq > deduped-errors.log
grep -v 'ERROR' numbered.log > passthrough.log
# ??? How to merge by line number while streaming?
# No standard tool does this efficiently
```

**Why composition fails**:
1. Need to split stream by track/bypass pattern
2. Process tracked/bypassed stream through uniqseq
3. Merge both streams in original order
4. Must maintain streaming (can't load all into memory)
5. Must preserve line order exactly

**No standard Unix tool solves this**: `sort -m` requires sorted input, `join` requires keys, custom scripts break streaming.

**Implementation approach**:
- Mark lines as tracked vs bypassed
- Tracked lines: enter deduplication pipeline
- Bypassed lines: pass through to output immediately
- Output maintains original order

**Trade-offs**:
- Pro: Solves stream reassembly problem
- Pro: High user value (common use case)
- Con: Adds feature complexity to uniqseq
- Con: Could argue "just filter before and after" (but loses context)

---

### ✅ Kept: Inverse Mode (`--inverse`)

**Alternative considered**: Use `diff` or `comm` to find duplicates.

**Decision**: Keep inverse mode built-in.

**Rationale**: Hard to replicate externally without losing sequence awareness.

**The Problem**:
```bash
# Goal: Show only sequences that were duplicated

# Attempt: Compare original and deduplicated
uniqseq input.log > unique.log
diff input.log unique.log > duplicates.log
# ❌ Shows line-by-line diff, not sequence-level awareness

# Attempt: Use comm
comm -23 <(sort input.log) <(sort unique.log)
# ❌ Loses order, shows individual lines not sequences
```

**Why composition fails**:
- External tools operate on lines, not sequences
- Algorithm knows which sequences repeated, we throw that info away
- Reconstructing sequence information externally is complex

**Implementation approach**:
- Simple logic flip: emit lines consumed by matches, skip unique lines
- Annotations can show which sequences were kept

**Trade-offs**:
- Pro: Simple to implement (algorithm has the data)
- Pro: Maintains sequence awareness in output
- Con: Adds another mode flag

---

### ✅ Kept: Binary Mode (`--byte-mode`)

**Alternative considered**: Preprocess with `xxd` or similar tools.

**Decision**: Keep binary mode built-in.

**Rationale**: Composition is inefficient and lossy.

**The Problem**:
```bash
# Attempt: Convert to hex, deduplicate, convert back
xxd -p -c 1 binary.dat | uniqseq | xxd -r -p > clean.bin
# ❌ Slow (xxd not optimized for streaming)
# ❌ Lossy (binary data may not be valid UTF-8)
# ❌ Awkward workflow
```

**Why composition fails**:
- Text mode assumes UTF-8 encoding
- Binary data often not valid UTF-8
- Conversion overhead significant
- Need different delimiter semantics (byte-oriented vs text-oriented)

**Implementation approach**:
- Switch to binary I/O mode
- Hash raw bytes directly
- Support hex delimiters (`--delimiter-hex 0x00`)
- Output is binary (matching input format)

**Trade-offs**:
- Pro: Native binary support, no conversion
- Pro: Efficient (no xxd overhead)
- Pro: Lossless (no encoding issues)
- Con: Separate code path for binary vs text

**Use cases**:
- Network protocol analysis
- Firmware deduplication
- Memory dump analysis
- Protobuf message streams

---

### ✅ Kept: Sequence Libraries

**Alternative considered**: Users manually manage discovered patterns.

**Decision**: Keep pattern save/load built-in with directory-based native format.

**Rationale**: Core value proposition, enables key workflows.

**Use cases**:
1. **Incremental processing**: Load yesterday's patterns, process today's logs
2. **Cross-system reuse**: Share pattern libraries across team/deployments
3. **Live troubleshooting**: Inspect patterns while processing (native format, cat-able)
4. **Flexible loading**: Pre-load from multiple directories with `--read-sequences`

**Implementation approach**:
- **Directory-based**: Single parent directory with `sequences/` and timestamped `metadata-<timestamp>/` subdirectories
- **Native format**: File content IS the sequence (no JSON, no base64) - human-readable with standard tools
- **Hash-based filenames**: `<hash>.uniqseq` for saved sequences (enables fast lookup, idempotent saving)
- **Pre-loaded sequences**: Loaded into separate set with unlimited retention (never evicted)
- **Composable modes**: `--read-sequences` for read-only, `--library-dir` for load+save, or both together
- **Metadata output-only**: Config files for audit trail, not read by uniqseq (user responsible for compatibility)

**Trade-offs**:
- Pro: Native format enables inspection with `cat`, `less`, `grep` (no JSON parsing)
- Pro: Flexible loading from multiple sources (`--read-sequences` can be specified multiple times)
- Pro: Simpler than JSON format (no serialization, no base64 for binary)
- Pro: Idempotent saving (check if file exists before writing)
- Pro: Unlimited retention for pre-loaded sequences (predictable behavior)
- Con: No built-in validation (user must ensure compatible settings)
- Con: Delimiter handling complexity (files must not end with trailing delimiter)

---

## Feature Exclusion Decisions

### ❌ Cut: Directory Scanning (`--directory`, `--pattern`)

**Reason**: Efficiently achievable with standard tools.

**Composition approach**:
```bash
# Directory + pattern
cat logs/*.log | uniqseq

# Recursive search
find logs/ -name "*.log" -exec cat {} + | uniqseq

# With sorting
find logs/ -name "*.log" | sort | xargs cat | uniqseq
```

**Why composition works**:
- Standard `find`, `cat`, `xargs` are efficient
- Pattern matching is well-understood
- Streaming-friendly
- No loss of functionality

**Trade-off**:
- Pro: Smaller tool, less code to maintain
- Pro: Users leverage existing find/glob knowledge
- Con: Slightly more verbose (but documented)

**Documentation requirement**: Document patterns in EXAMPLES.md

---

### ❌ Cut: Skip-Until, Skip-Regex

**Reason**: Covered by `--hash-transform` with better flexibility.

**Composition approach**:
```bash
# Skip until delimiter
uniqseq --hash-transform "sed 's/^[^|]*| //'" input.log

# Skip regex pattern
uniqseq --hash-transform "sed -E 's/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+ //'" input.log
```

**Why composition works**:
- `--hash-transform` provides full Unix filter power
- One subprocess per session (efficient)
- User can use any tool (sed, awk, custom script)

**Kept alternative**: `--skip-chars N` for simple fixed-width case (no subprocess).

**Trade-off**:
- Pro: One powerful flag instead of many similar flags
- Pro: Future-proof (users can bring custom transforms)
- Con: Slightly less discoverable than specific flags
- Con: Must document transform contract

---

### ❌ Cut: Filter Expressions (`--filter-expr`)

**Example**: `--filter-expr 'level in (ERROR, WARN) and not source.startswith("test")'`

**Reason**: Scope creep - building an expression language parser.

**Composition approach**:
```bash
# Use standard Unix tools
grep -E 'ERROR|WARN' logs | grep -v 'test' | uniqseq
```

**Why composition works**:
- `grep`, `awk` already provide pattern matching
- Users know these tools
- Pipe composition is standard Unix pattern
- No need to design/maintain expression language

**Trade-off**:
- Pro: Avoids expression language complexity (parsing, eval, security)
- Pro: Leverages user knowledge of existing tools
- Con: More verbose (but clearer)

**Documentation requirement**: Document composition patterns in EXAMPLES.md

---

### ❌ Cut: Template Extraction

**Example**: `--extract-templates --variable-detection`

**Reason**: Different problem domain - log parsing vs deduplication.

**Alternative tools**: Drain, Spell, angle, logparser

**Comparison**:

| Tool | Approach | Use Case |
|------|----------|----------|
| **uniqseq** | Exact sequence matching | Remove duplicate sequences |
| **Drain** | Fuzzy tree clustering | Extract log templates |
| **Spell** | Longest common subsequence | Parse semi-structured logs |

**Complementary workflows**:
```bash
# Deduplicate before template extraction (reduce input size)
uniqseq logs | drain3 > templates.txt

# Extract templates before deduplication (normalize first)
drain3 logs | uniqseq > clean.log
```

**Trade-off**:
- Pro: Stay focused on core competency (exact deduplication)
- Pro: Avoid overlap with specialized tools
- Con: Users must learn multiple tools (but with clear boundaries)

**Documentation requirement**: Document complementary workflows in EXAMPLES.md

---

### ❌ Cut: Character Mode (`--char-mode`)

**Reason**: Achievable via preprocessing, less common use case.

**Composition approach**:
```bash
# UTF-8 character-by-character
cat input.txt | \
  python3 -c 'import sys; [print(c) for line in sys.stdin for c in line.rstrip("\n")]; print("§NL§")' | \
  uniqseq --window-size 10 | \
  python3 -c 'import sys; output=[]; [output.append(line.rstrip()) if line.rstrip()!="§NL§" else (print("".join(output)), output.clear()) for line in sys.stdin]'
```

**Why composition works**:
- Preprocessing handles character splitting
- Python handles UTF-8 correctly (multi-byte characters)
- Main deduplication logic unchanged

**Why not built-in**:
- Less common than line-based or byte-based deduplication
- Preprocessing is straightforward (documented)
- Avoids complexity in core algorithm

**Kept alternative**: `--byte-mode` for binary byte-by-byte (more common use case)

**Trade-off**:
- Pro: Simpler core algorithm
- Pro: Byte mode covers most binary use cases
- Con: Character mode requires preprocessing (but documented)

**Documentation requirement**: Document preprocessing pattern in EXAMPLES.md

---

### ❌ Cut: Bio Tool Features

**Examples**: k-mer analysis, fuzzy matching, FASTA/FASTQ parsing

**Reason**: Domain-specific tools are better optimized.

**Alternative tools**: seqkit, CD-HIT, USEARCH/VSEARCH, BBMap

**Comparison**:

| Tool | Approach | Use Case |
|------|----------|----------|
| **uniqseq** | Exact multi-line matching | Text logs, general deduplication |
| **seqkit** | Bio-specific algorithms | FASTA/FASTQ deduplication |
| **CD-HIT** | Similarity clustering | Protein/DNA clustering |
| **USEARCH** | Ultra-fast alignment | Large-scale sequence analysis |

**When to use uniqseq for bio data**:
- Exact duplicate detection (faster than similarity tools when only exact matches needed)
- Quality control logs (deduplicate verbose pipeline output)
- Metadata files (annotations, not sequences)

**When to use bio tools**:
- Similarity-based clustering
- FASTA/FASTQ format handling
- Large-scale genomic analysis

**Trade-off**:
- Pro: Avoid competing with domain-specific tools
- Pro: Stay focused on general text/binary deduplication
- Con: Can't market to bioinformatics users (accept this)

**Documentation requirement**: Document comparison with bio tools, when to use alternatives

---

## Implementation Trade-offs

### Hash Transform Subprocess Management

**Design**: Single subprocess per session, piped lines.

**Alternative considered**: No subprocess (built-in transforms only).

**Trade-offs**:

| Approach | Pros | Cons |
|----------|------|------|
| **Single subprocess** | Flexible (any Unix filter), efficient (one spawn), streaming | Subprocess management complexity, 1:1 contract validation |
| **Built-in transforms** | Fast (no IPC), simple (no process management) | Limited flexibility, many flags (`--skip-chars`, `--skip-until`, `--skip-regex`, ...) |
| **Per-line subprocess** | Simple implementation | Extremely slow (fork per line) |

**Decision**: Single subprocess with strict 1:1 contract.

**Requirements**:
- Clear error messages when contract violated
- Graceful subprocess death handling
- Documentation of valid/invalid transforms

---

### Sequence Library Format

**Design**: Support both single-file and directory formats.

**Alternative considered**: Single format only.

**Trade-offs**:

| Format | Pros | Cons | Use Case |
|--------|------|------|----------|
| **Single file** | Atomic writes, versionable, simple | Slower lookup, harder to inspect individual sequences | CI/CD, version control |
| **Directory** | Fast hash-based lookup, live inspection, incremental | Many files, not atomic | Live troubleshooting, long-running monitoring |

**Decision**: Support both, auto-detect on load.

**Implementation**:
- Default: single file (simpler for most users)
- Opt-in: directory via `--format directory` or trailing `/`
- Load: auto-detect (directory vs file)

---

### Filtering Implementation

**Design**: Built-in filtering with regex patterns.

**Alternative considered**: External grep composition.

**Trade-offs**:

| Approach | Pros | Cons |
|----------|------|------|
| **Built-in** | Solves stream reassembly, filtered lines in output | Adds complexity to uniqseq |
| **External grep** | Simpler uniqseq, leverage existing tools | Loses filtered-out lines or requires complex merging |

**Decision**: Built-in, due to stream reassembly problem.

**Implementation**:
- Regex patterns (compatible with grep -E)
- Track-from-file (patterns from file)
- Applied before windowing (filtered lines don't count in windows)
- Filtered-out lines pass through to output unchanged

---

## Tool Comparisons

### vs. Traditional Line Deduplicators

| Tool | Scope | Order | Memory | When to Use |
|------|-------|-------|--------|-------------|
| `uniq` | Adjacent duplicate lines | ✅ Preserved | O(1) | Adjacent duplicates only |
| `sort -u` | All duplicate lines | ❌ Sorted | O(N) | Don't care about order |
| `awk '!seen[$0]++'` | All duplicate lines | ✅ Preserved | O(N) | Line-based, order matters |
| **uniqseq** | **Multi-line sequences** | **✅ Preserved** | **O(H) bounded** | **Repeated multi-line patterns** |

### vs. Log Analysis Tools

| Tool | Purpose | When to Use uniqseq | When to Use Alternative |
|------|---------|---------------------|------------------------|
| **Drain** | Template extraction | Deduplicate before extraction (reduce noise) | Extract templates (fuzzy matching) |
| **Spell** | Log parsing | Deduplicate first (smaller input) | Parse semi-structured logs |
| **logreduce** | Anomaly detection | Remove known patterns first | Find unusual entries |
| **Loki** | Log aggregation | Preprocess before ingestion (reduce storage) | Query/aggregate at scale |
| **grep/awk/sed** | Text processing | Complement with filtering/transformation | Pattern matching, field extraction |

### vs. Bio Tools

| Tool | Purpose | When to Use uniqseq | When to Use Alternative |
|------|---------|---------------------|------------------------|
| **seqkit** | FASTA/FASTQ processing | QC logs, metadata files | Bio sequence files |
| **CD-HIT** | Similarity clustering | Exact duplicates (preprocessing) | Fuzzy clustering by similarity |
| **USEARCH** | Sequence alignment | N/A (different domain) | Large-scale genomic analysis |

---

## Removed Features and Rationale

### Features Removed During Planning

**1. `--min-repeats N` (Removed from)**

**Original proposal**: Only deduplicate sequences seen N+ times.

**Why removed**:
- Adds implementation complexity (requires counting before deciding to skip)
- Use case unclear - when would you want to keep first N duplicates?
- Better achieved through composition:
  ```bash
  # Keep sequences with 2+ occurrences
  uniqseq --inverse --save-patterns lib.json input.log
  # Then filter library by count >= N
  ```
- Pattern libraries provide better solution with `count` metadata

**Alternative**: Use `--inverse` mode + pattern library filtering ( library tools).

---

**2. Multi-file Diff (Removed from)**

**Original proposal**: `--diff <file1> <file2>` to show unique sequences per file.

**Why removed**:
- Not a core competency feature (deduplication, not comparison)
- Achievable via composition with pattern libraries:
  ```bash
  # Save patterns per file
  uniqseq file1.log --save-patterns file1.json
  uniqseq file2.log --save-patterns file2.json

  # Compare libraries ( tools)
  uniqseq-lib diff file1.json file2.json
  ```
- Use case better served by dedicated diff tools or library comparison
- Unclear what "diff" means for sequences (set difference? symmetric difference?)

**Alternative**: Pattern library tools (`uniqseq-lib diff`,+).

---

**3. Context Lines `-A/-B/-C` (Removed from)**

**Original proposal**: Show N lines before/after duplicates (borrowed from grep).

**Why removed**:
- **Unclear semantics**: What does "context around duplicates" mean for sequences?
  - Context around where duplicates were skipped? (but non-skipped lines are already in output)
  - Context included in sequences? (changes deduplication behavior)
- **Overlaps with annotations**: `--annotate` already shows where duplicates were skipped
- **Not analogous to grep**: grep shows context around matches; for dedup, "matches" are things we skip
- **Use case unclear**: If you want to see what was removed, use `--annotate`

**Example confusion**:
```bash
# What would this do?
uniqseq -C 2 input.log

# Show 2 lines before/after each skipped sequence?
#   But non-skipped lines are already in output!
```

**Alternative**: Use `--annotate` for visibility into what was skipped.

---

### Features Clarified During Planning

**1. Sequence Libraries - Native Format, Not JSON**

**Original proposal**: Store sequences in JSON format with base64 encoding for binary mode.

**Why changed**:
- **Native format is simpler** - file content IS the sequence, no parsing needed
- **Human-readable** - can inspect with `cat`, `less`, `grep` (no JSON required)
- **No base64 complexity** - binary sequences stored as raw bytes
- **Standard tools work** - Unix tools can directly process sequence files
- **Delimiter handling** - files must not end with trailing delimiter (split() correctness)

**Decision**: Directory-based storage with native format sequence files (`<hash>.uniqseq`).

**2. Sequence Libraries - Directory Structure, Not Single File**

**Original proposal**: Support both single-file (JSON) and directory formats, auto-detect on load.

**Why changed**:
- **Single parent directory is simpler** - `--library-dir <path>` instead of separate `--save-patterns` and `--load-patterns`
- **Timestamped metadata** - Each run creates `metadata-<timestamp>/` subdirectory (audit trail, no overwrites)
- **Sequences directory** - All sequence files in `sequences/` subdirectory with `.uniqseq` extension
- **Composable with read-only** - `--read-sequences` for flexible loading from any directory

**Decision**: Single directory structure with `sequences/` and `metadata-<timestamp>/` subdirectories.

**3. Pre-loaded Sequences - Separate Set, Not Regular History**

**Original proposal**: Load patterns into regular FIFO history.

**Why changed**:
- **Unlimited retention** - Pre-loaded sequences never evicted (predictable behavior)
- **Multiple sources** - `--read-sequences` can be specified multiple times (composable)
- **Treated as "already seen"** - First observation is skipped (not output)
- **Library saves observed** - `--library-dir` saves pre-loaded sequences when observed in input

**Decision**: Separate pre-loaded sequence set with unlimited retention, checked during deduplication.

---

**4. Multiple Filters - Sequential Evaluation**

**Original proposal**: All `--track` use OR logic, all `--bypass` use OR logic.

**Why changed**:
- **Less flexible** - can't express "exclude X unless it's also Y"
- **Doesn't match user mental model** - users think in terms of ordered rules

**Decision**: Sequential evaluation (like iptables), first match wins.

**Example**:
```bash
# Exclude debug, but include critical debug
uniqseq --bypass 'DEBUG' --track 'DEBUG CRITICAL' app.log
```

This is intuitive and matches how firewall rules work.

---

## See Also

- **PLANNING_REFINED.md** - Feature roadmap
- **EXAMPLES.md** - Usage examples and composition patterns
- **IMPLEMENTATION.md** - Implementation overview
- **ALGORITHM_DESIGN.md** - Core algorithm details
