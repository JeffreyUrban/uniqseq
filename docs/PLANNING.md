# Future Features - Planning Document

**Status**: Planning
**Current Version**: v0.1.0
**Target Versions**: v0.2.0 through v1.0.0

This document describes planned enhancement features for future releases of uniqseq. All features listed here are **not yet implemented** but are designed to build on the stable v0.1.0 core algorithm.

## Ordering Principle

Features are ordered by **foundational impact** - those affecting core architecture or enabling other features come first. This ensures:
- Core flexibility changes happen before dependent features
- File format stabilization before features that use it
- Lower-risk additive features come after architectural changes

---

## Feature Roadmap

Features are ordered by foundational impact - those that affect core architecture or enable other features come first.

### v0.2.0 - Core Flexibility Enhancements (Planned)
**Priority**: High
**Estimated Effort**: Medium
**Dependencies**: Core algorithm (✅ implemented in v0.1.0)
**Foundational Impact**: High - affects memory model, comparison logic, and enables future features

**Features**:
- Unlimited mode for history length and sequence count
- Raw bytes mode (non-text data support)
- Arbitrary delimiter support (beyond newlines)
- Single character/byte modes
- Skip comparison until after index/delimiter (timestamp handling)

**Why foundational**: These modify core comparison and buffering logic. Other features (libraries, archiving) will need to work with these modes.

### v0.3.0 - Input/Output Format Extensions (Planned)
**Priority**: Medium-High
**Estimated Effort**: Medium-High
**Dependencies**: v0.2.0 core flexibility
**Foundational Impact**: Medium-High - defines persistent format for sequences

**Features**:
- File-based sequence library format (content + metadata)
- Multiple input modes (file/directory/list of files)
- Implicit hashes in input/output
- Separate sequence content and metadata files

**Why foundational**: Establishes stable format for sequence interchange. v0.4.0 features (annotations, archiving) will reference this format.

### v0.4.0 - Filtering and Preprocessing (Planned)
**Priority**: Medium
**Estimated Effort**: Medium
**Dependencies**: v0.2.0 core flexibility
**Foundational Impact**: Medium - affects input pipeline

**Features**:
- Filter-in and filter-out lists for lines
- Research popular tool patterns (grep, sed, awk, ripgrep)
- Composable filter expressions

**Why before annotations/archiving**: Filtering affects what sequences are detected. Annotations/archiving should work with filtered data.

### v0.5.0 - Inline Annotations (Planned)
**Priority**: Medium
**Estimated Effort**: Medium
**Dependencies**: v0.3.0 file format
**Foundational Impact**: Low - purely additive output feature

**Features**:
- Optional inline markers showing where duplicate sequences were skipped
- Format specifiers for annotations
- Line numbering modes (absolute/relative)

**Why after format extensions**: Annotations reference sequence metadata established in v0.3.0.

### v0.6.0 - Content Archiving (Planned)
**Priority**: Low
**Estimated Effort**: Medium
**Dependencies**: v0.3.0 file format
**Foundational Impact**: Low - purely additive archival feature

**Features**:
- Persist skipped sequences to disk
- Hash-based naming
- Configurable archive formats

**Why after format extensions**: Archiving uses sequence file format from v0.3.0.

### v1.0.0 - Advanced Use Cases (Future)
**Priority**: Low
**Estimated Effort**: High
**Dependencies**: All previous features
**Foundational Impact**: Low - specialized applications

**Features**:
- Portable sequence libraries (import/export patterns)
- Efficient single-pass search applications
- Bio/genetics sequence library comparison
- Domain-specific optimizations

---

## v0.2.0: Core Flexibility Enhancements

### Unlimited Mode Options

**Overview**: Remove hard limits on history depth and unique sequence count for scenarios where complete deduplication across entire input is required.

**Use Cases**:
1. **Complete file deduplication**: Process entire large files without history truncation
2. **Long-running streams**: Handle very long sessions without losing old patterns
3. **Archival processing**: Ensure no duplicates missed due to memory limits

**CLI Options**:
```bash
--unlimited-history          # No limit on window hash history (default: 100k for stdin)
--unlimited-sequences        # No limit on unique sequences stored (default: unlimited)
--max-memory <size>          # Soft limit in MB, warn when exceeded (optional)
```

**Implementation Considerations**:
- Memory grows unbounded - users must monitor system resources
- Provide memory usage warnings when limits exceeded
- Statistics should show current memory usage
- Consider memory-mapped storage for very large histories

**Example**:
```bash
# Process entire 10GB log file with complete history
uniqseq --unlimited-history huge-session.log > deduplicated.log
```

---

### Raw Bytes Mode

**Overview**: Support binary data (non-text files) by treating input as raw byte stream instead of text lines.

**Use Cases**:
1. **Binary log formats**: Protocol buffers, msgpack, custom binary formats
2. **Data deduplication**: Deduplicate binary data blocks
3. **Mixed encoding**: Files with inconsistent or unknown text encoding

**CLI Options**:
```bash
--bytes                      # Treat input as raw bytes, not text
--delimiter <hex>            # Delimiter in hex (default: 0x0a for newline)
```

**Implementation Considerations**:
- Switch from text mode to binary mode file reading
- Hash raw bytes directly (no UTF-8 decoding)
- Line buffer becomes byte buffer
- All I/O in binary mode
- Delimiter can be arbitrary byte sequence

**Example**:
```bash
# Deduplicate binary log with custom delimiter
uniqseq --bytes --delimiter 0x00 binary-data.bin > deduped.bin
```

---

### Arbitrary Delimiter Support

**Overview**: Support delimiters other than newline for defining "lines" (records).

**Use Cases**:
1. **Null-terminated records**: Common in Unix tools (find -print0, xargs -0)
2. **Custom formats**: CSV with embedded newlines, multi-line JSON
3. **Binary protocols**: Records separated by magic bytes

**CLI Options**:
```bash
--delimiter <string>         # Record delimiter (default: \n)
--delimiter-hex <hex>        # Delimiter as hex bytes (e.g., 0x00)
--delimiter-regex <pattern>  # Delimiter as regex (advanced)
```

**Implementation Considerations**:
- Modify line reading to split on custom delimiter
- Support both text and binary delimiters
- Preserve delimiter in output or strip based on flag
- Handle empty records (consecutive delimiters)

**Example**:
```bash
# Process null-terminated records
find . -print0 | uniqseq --delimiter '\0' > deduped.txt

# Custom delimiter
uniqseq --delimiter '---' multipart-file.txt > deduped.txt
```

---

### Single Character/Byte Modes

**Overview**: Operate on individual characters or bytes instead of lines, useful for specialized applications.

**Use Cases**:
1. **DNA/RNA sequences**: Single-character alphabet (A, C, G, T/U)
2. **Signal processing**: Byte-level pattern detection
3. **Compression research**: Finding repeated byte patterns

**CLI Options**:
```bash
--char-mode                  # Treat each character as a record
--byte-mode                  # Treat each byte as a record (binary)
--window-size <N>            # Number of chars/bytes per window (default: 10)
```

**Implementation Considerations**:
- Character mode: UTF-8 aware character iteration
- Byte mode: Raw byte iteration
- Window becomes sequence of N characters/bytes
- Much higher throughput requirements (millions of records/sec)
- Memory usage scales with character/byte diversity

**Example**:
```bash
# DNA sequence deduplication (10-base windows)
uniqseq --char-mode --window-size 10 genome.fasta > unique-sequences.fasta
```

---

### Skip Comparison Until Index/Delimiter

**Overview**: Ignore prefix of each line (e.g., timestamps, line numbers) when computing hashes for deduplication.

**Use Cases**:
1. **Timestamped logs**: Ignore timestamps, deduplicate based on message content
2. **Numbered output**: Ignore line numbers added by other tools
3. **Prefixed data**: Skip fixed-width metadata columns

**CLI Options**:
```bash
--skip-chars <N>             # Skip first N characters of each line
--skip-until <delimiter>     # Skip until delimiter (inclusive)
--skip-regex <pattern>       # Skip prefix matching regex
```

**Implementation Considerations**:
- Slice line before hashing: `hash(line[skip_chars:])`
- Preserve full line in buffer for output
- Handle lines shorter than skip length (hash empty string or skip line entirely)
- Delimiter mode: find delimiter, hash everything after

**Timestamp Handling Example**:
```bash
# Log format: "2025-11-22 10:30:15 | actual message"
uniqseq --skip-until ' | ' session.log > deduped.log

# Fixed-width timestamp (23 chars)
uniqseq --skip-chars 23 session.log > deduped.log
```

**Research**: Study how existing tools handle this:
- `grep`: Uses `-o` for match extraction
- `awk`: Field-based processing with delimiters
- `cut`: Character/field ranges
- `sed`: Regex-based substitution before processing

---

## v0.3.0: Input/Output Format Extensions

### File-Based Sequence Library Format

**Overview**: Define persistent file format for storing sequences with metadata, enabling reuse and interchange.

**Use Cases**:
1. **Sequence reuse**: Save discovered sequences for processing future inputs
2. **Analysis**: Examine what sequences were found without reprocessing
3. **Interchange**: Share sequence libraries across teams or tools

**File Format Design**:

**Option 1: Single file with embedded content**
```
uniqseq-library-v1
window_size: 10
sequence_count: 42

# Sequence 1
hash: a3f5c8d9e1b2c4f6
length: 15
repeat_count: 3
content:
  line 1 content
  line 2 content
  ...
  line 15 content

# Sequence 2
hash: b4c6d8e0f2a4b6c8
...
```

**Option 2: Separate content and metadata files**
```
# patterns.meta (metadata only)
{"version": "1.0", "window_size": 10}
{"hash": "a3f5c8d9", "length": 15, "repeat_count": 3, "content_file": "seq_a3f5c8d9.txt"}
{"hash": "b4c6d8e0", "length": 12, "repeat_count": 5, "content_file": "seq_b4c6d8e0.txt"}

# seq_a3f5c8d9.txt (actual content)
line 1 content
line 2 content
...
```

**Implicit Hash Design**: Hash not stored explicitly, derived from content
- Pro: Self-verifying (recompute hash from content)
- Pro: Cannot corrupt hash/content relationship
- Con: Slower loading (must rehash all content)

**CLI Options**:
```bash
--save-sequences <path>      # Save discovered sequences to file/directory
--load-sequences <path>      # Load sequences from file/directory
--format <format>            # single-file|separate-files|json (default: single-file)
--verify-hashes              # Recompute hashes when loading (slower but safer)
```

**Example**:
```bash
# First pass: discover and save sequences
uniqseq --save-sequences patterns.lib session.log > deduped.log

# Later: load sequences to skip reprocessing
uniqseq --load-sequences patterns.lib new-session.log > deduped2.log
```

---

### Multiple Input Modes

**Overview**: Accept various input sources beyond stdin/single-file.

**Use Cases**:
1. **Batch processing**: Deduplicate across multiple files in one pass
2. **Directory scanning**: Process all files matching pattern
3. **Sequence libraries**: Use files as sequence definitions

**CLI Options**:
```bash
uniqseq file1.log file2.log file3.log     # Multiple files
uniqseq --directory <dir> --pattern "*.log"  # Directory + glob
uniqseq --file-list <path>                # File containing list of paths
uniqseq --sequences-from-files <dir>      # Each file is a sequence
```

**Sequences-from-files Mode**: Treat each input file as a single sequence to match
```bash
# Have 100 known error sequences in separate files
# Match any of them in new log
uniqseq --sequences-from-files ./known-errors/ new.log > filtered.log
```

**Implementation Considerations**:
- Maintain separate statistics per input file
- Option to emit source filename in output
- Handle files with different delimiters/encodings
- Memory: load all sequence files upfront or stream?

**Example**:
```bash
# Process all build logs in directory
uniqseq --directory ./logs --pattern "build-*.log" > all-deduped.log

# Use error library to filter new logs
uniqseq --sequences-from-files ./error-patterns/ new-session.log > clean.log
```

---

## v0.4.0: Filtering and Preprocessing

### Filter-In and Filter-Out Lists

**Overview**: Include or exclude lines matching patterns before deduplication.

**Use Cases**:
1. **Noise reduction**: Filter out known noisy lines before detecting sequences
2. **Focused deduplication**: Only deduplicate specific log levels
3. **Pipeline composition**: Combine with other filters

**CLI Options**:
```bash
--filter-in <pattern>        # Only process lines matching pattern (can specify multiple)
--filter-out <pattern>       # Exclude lines matching pattern (can specify multiple)
--filter-in-file <path>      # Patterns from file (one per line)
--filter-out-file <path>     # Exclusion patterns from file
--filter-mode <mode>         # regex|glob|literal (default: regex)
```

**Interaction with Deduplication**:
- Filters applied BEFORE windowing
- Filtered-out lines not counted in window
- Output includes only non-filtered lines (filtered lines never emitted)

**Research Popular Tool Patterns**:

1. **grep**: Basic line filtering
   ```bash
   grep -E 'pattern'           # Include matching
   grep -v 'pattern'           # Exclude matching
   grep -f patterns.txt        # Patterns from file
   ```

2. **ripgrep (rg)**: Modern grep with better defaults
   ```bash
   rg --type-add 'log:*.log' --type log 'ERROR'
   rg --ignore-file .rgignore
   ```

3. **awk**: Field-based filtering
   ```bash
   awk '/pattern/ { print }'
   awk '$3 == "ERROR"'         # Field-based
   ```

4. **sed**: Stream editing with patterns
   ```bash
   sed '/pattern/d'            # Delete matching lines
   sed -n '/pattern/p'         # Print only matching
   ```

**Design Decision**: Use ripgrep-style syntax (most modern, widely understood)
```bash
# Combine filtering with deduplication
uniqseq --filter-in 'ERROR|WARN' --filter-out 'DEBUG' session.log > deduped.log

# Multiple patterns from file
uniqseq --filter-in-file important-patterns.txt session.log > deduped.log
```

**Composable Filter Expressions**:
```bash
--filter-expr 'level in (ERROR, WARN) and not source.startswith("test")'
```

---

## v0.5.0: Inline Annotations

### Overview

When enabled via `--annotate` flag, insert formatted annotation lines in the output stream when duplicate sequences are skipped.

**Note**: This feature builds on v0.3.0 file format for sequence metadata references.

### Use Cases

1. **Transparency**: Users can see where deduplication occurred without having to diff files
2. **Debugging**: Quick reference to what was removed (line ranges)
3. **Auditability**: Track what content was removed inline with output

### Default Annotation Format

```
[... skipped duplicate lines 1234-1243 ...]
```

### Line Numbering Modes

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
```bash
uniqseq --annotate --line-numbers absolute file.log   # Force absolute
uniqseq --annotate --line-numbers relative file.log   # Force relative
```

### CLI Options

```bash
--annotate                    # Enable annotations (default: disabled)
--line-numbers <mode>         # absolute|relative (auto-detect if not specified)
--annotation-format <string>  # Custom format string (see format specifiers below)
```

### Format Specifiers

Annotation text supports format specifiers:

| Specifier   | Description                           | Example    |
|-------------|---------------------------------------|------------|
| `{start}`   | First line number of skipped sequence | `1234`     |
| `{end}`     | Last line number of skipped sequence  | `1243`     |
| `{count}`   | Number of lines in sequence           | `10`       |
| `{hash}`    | Sequence hash (8-char hex)            | `a3f5c8d9` |

**Format string examples**:

```bash
# Default
uniqseq --annotate file.log
# Output: [... skipped duplicate lines 1234-1243 ...]

# Verbose
uniqseq --annotate --annotation-format "[DUPLICATE: {count} lines ({start}-{end}), hash={hash}]" file.log
# Output: [DUPLICATE: 10 lines (1234-1243), hash=a3f5c8d9]

# Minimal
uniqseq --annotate --annotation-format "[skip {start}-{end}]" file.log
# Output: [skip 1234-1243]
```

### Design Considerations

**Annotations go to stdout** (part of data stream, not UI):
- Rationale: Annotations are part of the processed output, not status messages
- UI messages (statistics, progress) go to stderr
- Allows piping annotated output to another tool

**Distinguishable from actual content**:
- Bracketed format: `[... ... ...]`
- Descriptive text: "skipped duplicate lines"
- Unlikely to match actual log content

### Implementation Notes

**StreamingDeduplicator changes**:
- Add `annotation_enabled` parameter (default: False)
- Add `annotation_format` parameter (default: template string)
- Add `line_number_mode` parameter ('auto', 'absolute', 'relative')
- Emit annotation line to output when skipping sequence

**CLI changes**:
- Add `--annotate` flag
- Add `--line-numbers` option
- Add `--annotation-format` option
- Pass parameters to StreamingDeduplicator

---

## v0.6.0: Content Archiving

### Overview

Optionally write each unique skipped sequence to a file in a specified directory for audit/debugging purposes.

**Note**: This feature uses v0.3.0 file format for storing archived sequences.

### Use Cases

1. **Archival**: Preserve skipped content for later review without duplicating identical sequences
2. **Auditability**: Track exactly what was removed
3. **Debugging**: Examine skipped sequences offline

### Enabling Archiving

```bash
uniqseq --archive-dir <path> file.log
```

**No default directory**: Archiving is opt-in via the `--archive-dir` parameter
- Directory is created if it doesn't exist (including parent directories)
- If directory exists, continue without error

### Key Properties

**Hash-based naming**: Use sequence hash in filename to avoid duplicating identical content
- Same sequence seen multiple times → written once
- Different sequences → separate files

**Idempotent**: If file exists, don't write again
- Check file existence before writing
- Same hash = same content, no need to rewrite

**Self-documenting**: Files contain the actual skipped lines for reference
- Plain text files
- Original line content preserved

### Default Filename Format

```
uniqseq-{hash}.txt
```

Where `{hash}` is the 8-character hex sequence hash (filesystem-safe).

### CLI Options

```bash
--archive-dir <path>              # Enable archiving to directory
--archive-filename-format <string>  # Custom filename format (see format specifiers below)
```

### Format Specifiers

Archive filenames support format specifiers:

| Specifier        | Description                           | Example               |
|------------------|---------------------------------------|-----------------------|
| `{hash}`         | Sequence hash (8-char hex, filesystem-safe) | `a3f5c8d9`            |
| `{hash_full}`    | Full sequence hash (32-char hex)      | `a3f5c8d9e1b2c4f6...` |
| `{start}`        | First line number of skipped sequence | `00001234`            |
| `{end}`          | Last line number of skipped sequence  | `00001243`            |
| `{count}`        | Number of lines in sequence           | `0010`                |
| `{timestamp}`    | ISO timestamp (sanitized for filenames) | `2025-11-20T14_32_15` |
| `{seq_num}`      | Nth unique sequence skipped           | `0042`                |

**Format string examples**:

```bash
# Default
uniqseq --archive-dir ./archive file.log
# Files: archive/uniqseq-a3f5c8d9.txt

# Descriptive
uniqseq --archive-dir ./archive --archive-filename-format "skipped-{start:08d}-{end:08d}-{hash}.txt" file.log
# Files: archive/skipped-00001234-00001243-a3f5c8d9.txt

# Timestamped
uniqseq --archive-dir ./archive --archive-filename-format "{timestamp}-{hash}.txt" file.log
# Files: archive/2025-11-20T14_32_15-a3f5c8d9.txt

# Numbered
uniqseq --archive-dir ./archive --archive-filename-format "skip-{seq_num:04d}-{hash}.txt" file.log
# Files: archive/skip-0001-a3f5c8d9.txt, archive/skip-0002-e1f2a3b4.txt
```

### File Content Format

```
Lines 1234-1243 (10 lines, hash: a3f5c8d9)
Skipped from: /path/to/file.log
Timestamp: 2025-11-20T14:32:15

--- BEGIN SEQUENCE ---
line content 1
line content 2
...
line content 10
--- END SEQUENCE ---
```

### Implementation Notes

**StreamingDeduplicator changes**:
- Add `archive_dir` parameter (default: None)
- Add `archive_filename_format` parameter (default: template string)
- Track written archive files by hash to avoid duplicates
- Write to archive file when skipping sequence (if enabled)

**CLI changes**:
- Add `--archive-dir` option
- Add `--archive-filename-format` option
- Create directory if it doesn't exist
- Pass parameters to StreamingDeduplicator

**Error handling**:
- Warn if archive directory not writable
- Continue processing even if archive write fails
- Log errors to stderr

---

## v1.0.0: Advanced Use Cases and Optimizations

This release focuses on specialized applications, performance optimizations, and integration with domain-specific use cases.

### Portable Sequence Libraries

**Overview**: Save discovered unique sequence patterns to a library file and load them at startup for immediate matching across runs.

### Use Cases

1. **Pre-load common patterns**: Faster deduplication by reusing discovered patterns
2. **Share patterns**: Distribute pattern libraries across team/deployments
3. **Domain-specific libraries**: Build specialized libraries for build output, test logs, etc.

### Planned Features

**Export unique_sequences to file**:
```bash
uniqseq --export-library patterns.json file.log
```

**Load patterns at startup**:
```bash
uniqseq --import-library patterns.json new_file.log
```

**Merge libraries from multiple runs**:
```bash
uniqseq-merge-lib lib1.json lib2.json -o merged.json
```

**Pattern library management**:
```bash
uniqseq-lib list patterns.json           # List patterns
uniqseq-lib filter patterns.json --min-count 5   # Filter by repeat count
uniqseq-lib combine lib1.json lib2.json  # Combine libraries
```

### Library File Format (Proposed)

JSON format with version information:

```json
{
  "version": "1.0",
  "created": "2025-11-20T14:32:15Z",
  "source": "/path/to/file.log",
  "window_size": 10,
  "patterns": [
    {
      "start_window_hash": "a3f5c8d9",
      "full_sequence_hash": "a3f5c8d9e1b2c4f6a1b2c3d4e5f6a7b8",
      "sequence_length": 10,
      "repeat_count": 3,
      "window_hashes": ["abc123...", "def456...", ...]
    }
  ]
}
```

### CLI Options (Proposed)

```bash
--export-library <path>     # Export patterns to file after processing
--import-library <path>     # Load patterns from file before processing
--library-mode <mode>       # merge|replace (default: merge)
```

### Implementation Notes

**File format stability**:
- Use semantic versioning for library format
- Backward compatibility for minor version bumps
- Migration tools for major version changes

**Performance considerations**:
- Large libraries may increase startup time
- Consider lazy loading or indexing for very large libraries
- Memory usage scales with library size

**Security considerations**:
- Validate library file format
- Hash verification to prevent tampering
- Consider signing libraries for production use

---

### Bio/Genetics Sequence Library Comparison

**Overview**: Compare `uniqseq` with bioinformatics sequence deduplication tools to identify potential improvements and unique applications.

**Popular Bio Tools**:

1. **CD-HIT** (Cluster Database at High Identity with Tolerance)
   - Purpose: Clustering protein/DNA sequences by similarity
   - Algorithm: Greedy incremental clustering
   - Key feature: Similarity threshold (not exact matching)
   - Performance: Handles millions of sequences

2. **USEARCH** / **VSEARCH**
   - Purpose: Sequence analysis (clustering, dedup, search)
   - Algorithm: Ultra-fast sequence alignment
   - Key feature: Fuzzy matching with edit distance
   - Performance: Highly optimized for large datasets

3. **seqkit rmdup**
   - Purpose: Remove duplicate sequences from FASTA/FASTQ
   - Algorithm: Hash-based exact matching
   - Key feature: ID-based or sequence-based dedup
   - Performance: Fast, handles large files

4. **BBMap dedupe.sh**
   - Purpose: Remove duplicate reads from sequencing data
   - Algorithm: Hash-based with k-mer filtering
   - Key feature: Handles sequencing errors
   - Performance: Streaming with bounded memory

**Comparison with uniqseq**:

| Feature | Bio Tools | uniqseq |
|---------|-----------|---------|
| **Matching** | Similarity-based (edit distance) | Exact sequence matching |
| **Unit** | Individual sequences/reads | Multi-line sequences |
| **Order** | Usually not preserved | Always preserved |
| **Use case** | Biological sequences | Text logs, terminal output |
| **Format** | FASTA/FASTQ | Line-based text |
| **Memory** | Varies (often high) | Bounded (configurable) |

**Potential Bio Applications for uniqseq**:

1. **Exact duplicate detection**: Faster than similarity-based tools when only exact matches needed
2. **Multi-read patterns**: Detect repeated multi-line FASTQ records
3. **Quality control logs**: Deduplicate verbose pipeline output
4. **Metadata deduplication**: Process annotation files, not sequences

**Research Questions**:
- Can uniqseq's position-based tracking improve bio tools?
- Is there value in preserving read order for downstream analysis?
- Could character-mode uniqseq compete with seqkit for simple exact dedup?

---

### Efficient Single-Pass Search Applications

**Overview**: Leverage uniqseq's streaming architecture for novel search and pattern detection use cases.

**Concept**: The deduplicator already finds repeated patterns - can we expose this for search?

**Potential Applications**:

1. **Log Pattern Discovery**
   - Input: Large log file
   - Output: All repeated multi-line patterns with occurrence counts
   - Use case: Identify common error sequences without knowing patterns upfront
   ```bash
   uniqseq --discover-patterns --min-repeats 3 server.log > patterns.txt
   ```

2. **Diff Summarization**
   - Input: Two versions of verbose output
   - Output: Unique content (what changed) with duplicates removed
   - Use case: Focus on actual changes, ignore repeated boilerplate
   ```bash
   diff old.log new.log | uniqseq --diff-mode > changes-only.txt
   ```

3. **Content-Addressed Storage**
   - Input: Stream of records
   - Output: Hash-to-content mapping for deduplication
   - Use case: Deduplicate before writing to storage
   ```bash
   uniqseq --export-hashes --archive-dir ./content session.log > references.txt
   ```

4. **Anomaly Detection**
   - Input: Log stream
   - Output: Only sequences that appear exactly once (anomalies)
   - Use case: Find unusual patterns in otherwise repetitive output
   ```bash
   uniqseq --unique-only --min-window 5 monitoring.log > anomalies.txt
   ```

5. **Template Extraction**
   - Input: Logs with variable data
   - Output: Templates (repeated structures) and variables
   - Use case: Log parsing and schema discovery
   ```bash
   uniqseq --extract-templates --variable-detection timestamps.log > templates.txt
   ```

**Implementation Considerations**:
- Most of these require exposing internal data structures (unique_sequences, repeat counts)
- Some need inverse operations (keep unique, skip repeated)
- Template extraction requires fuzzy matching (beyond exact hashing)

---

### Illustrative Examples and Use Cases

Comprehensive examples demonstrating realistic workflows with multiple features combined.

#### Example 1: Build Log Deduplication Pipeline

**Scenario**: CI/CD system generates verbose build logs with many repeated warnings

```bash
# First run: Discover repeated patterns, save library
uniqseq --window-size 8 \
        --skip-until '] ' \                    # Skip timestamps "[2025-11-22 10:30:15] message"
        --filter-out 'DEBUG' \                 # Ignore debug lines
        --save-sequences build-patterns.lib \
        --annotate \
        build-2025-11-22.log > clean-build.log

# Subsequent builds: Use pattern library for faster processing
uniqseq --load-sequences build-patterns.lib \
        --skip-until '] ' \
        --filter-out 'DEBUG' \
        --annotate \
        build-2025-11-23.log > clean-build-2.log

# Extract just the unique errors/warnings
uniqseq --load-sequences build-patterns.lib \
        --filter-in 'ERROR|WARN' \
        --unique-only \                         # Only sequences appearing once (novel errors)
        build-2025-11-23.log > new-issues.log
```

**Result**:
- 80% reduction in log size (typical for build output)
- Annotations show where duplicates were removed
- Pattern library speeds up future builds
- Novel errors highlighted automatically

---

#### Example 2: Binary Protocol Deduplication

**Scenario**: Network capture with repeated protocol messages (null-delimited binary records)

```bash
# Deduplicate binary protocol messages
uniqseq --bytes \
        --delimiter-hex 0x00 \                 # Null-terminated messages
        --window-size 5 \                      # 5-message windows
        --archive-dir ./unique-messages \      # Save unique messages
        --unlimited-history \                  # Don't lose patterns
        capture.bin > deduped-capture.bin

# Later: Use archived messages as filter
uniqseq --sequences-from-files ./unique-messages \
        --bytes \
        --delimiter-hex 0x00 \
        new-capture.bin > filtered-new.bin
```

**Result**:
- Binary data handled natively
- Unique protocol messages archived for analysis
- Can filter future captures using known message library

---

#### Example 3: DNA Sequence Analysis

**Scenario**: Find repeated k-mers in genome data (character-mode)

```bash
# Find repeated 15-base sequences in FASTA file
# (after stripping FASTA headers)
grep -v '^>' genome.fasta | tr -d '\n' | \
uniqseq --char-mode \
        --window-size 15 \                     # 15-base k-mers
        --save-sequences kmers.lib \
        --unlimited-history > unique-genome.txt

# Statistics show how many 15-mers were repeated
```

**Result**:
- Character-mode processes individual bases
- Discovers all repeated k-mers
- Could compare with bio tools (CD-HIT, seqkit) for performance

---

#### Example 4: Multi-File Log Aggregation

**Scenario**: Multiple microservices generating logs, deduplicate across all

```bash
# Process all service logs in one pass
uniqseq --directory ./service-logs \
        --pattern "service-*.log" \
        --skip-until ' | ' \                    # Skip timestamps
        --filter-in 'ERROR|FATAL' \             # Only errors
        --annotate \
        --annotation-format '[{count} lines from {filename}:{start}-{end}]' \
        > aggregated-errors.log

# Output shows which service each error came from
```

**Result**:
- Single deduplicated view across all services
- Annotations include source filename
- Only errors/fatals included

---

#### Example 5: Session Recording Cleanup

**Scenario**: Terminal session recording has repeated command outputs (original uniqseq use case)

```bash
# Clean up terminal session recording
uniqseq --window-size 10 \
        --progress \                           # Show progress for long session
        --annotate \
        --annotation-format '[skipped {count} lines]' \
        session-recording.txt > clean-session.txt

# Pipe to pager for review
uniqseq --window-size 10 --annotate session.txt | less

# Save for documentation (with stats)
uniqseq --window-size 10 session.txt > clean.txt 2> stats.txt
```

**Result**:
- Readable session without repeated outputs
- Annotations show where content was skipped
- Statistics show redundancy percentage

---

#### Example 6: Custom Delimiter Processing

**Scenario**: Multi-line JSON records separated by "---" delimiter

```bash
# Deduplicate JSON records with custom delimiter
uniqseq --delimiter '---' \
        --window-size 3 \                      # 3 JSON objects per window
        --archive-dir ./unique-json \
        multi-record.json > deduped.json

# Each archived file contains one unique JSON sequence
```

**Result**:
- Custom delimiter handled correctly
- Unique JSON sequences archived for analysis

---

#### Example 7: Timestamp-Prefixed Log Deduplication

**Scenario**: Logs with varying timestamp formats

```bash
# Option 1: Skip fixed-width timestamp (23 chars)
uniqseq --skip-chars 23 --window-size 10 app.log > clean.log

# Option 2: Skip until delimiter
uniqseq --skip-until ' - ' --window-size 10 app.log > clean.log

# Option 3: Skip using regex (advanced)
uniqseq --skip-regex '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{3}Z ' \
        --window-size 10 \
        app.log > clean.log
```

**Result**:
- Timestamps ignored during deduplication
- Messages with same content but different timestamps deduplicated
- Full lines (including timestamps) preserved in output

---

## Feature Compatibility Matrix

This matrix shows which features work together and any constraints.

| Feature | Compatible With | Incompatible With | Notes |
|---------|----------------|-------------------|-------|
| **Unlimited history** | All features | (memory limits only) | Monitor memory usage |
| **Raw bytes mode** | Delimiter-hex, single-byte, archiving | Skip-until (text-based), filters (regex) | Text features require text mode |
| **Arbitrary delimiter** | All text/byte features | Single char/byte mode | Char/byte mode has implicit delimiter |
| **Single char mode** | Skip-chars, filters | Raw bytes, arbitrary delimiter | Character = UTF-8 aware |
| **Single byte mode** | Delimiter-hex | Text-based skip/filter | Byte = raw binary |
| **Skip-until/chars** | All text features | Raw bytes, single byte | Requires text parsing |
| **File format (v0.3.0)** | All features | None | Foundation for save/load |
| **Multiple inputs** | All features | None | Can process multiple files with any settings |
| **Filter-in/out** | All text features | Raw bytes, single byte | Regex requires text |
| **Annotations** | All modes | None | Adapts format to mode (text vs binary) |
| **Archiving** | All modes | None | Archives content in native format |
| **Sequence libraries** | All modes | None | Library includes mode metadata |

### Key Compatibility Rules

1. **Text vs Binary Modes**:
   - `--bytes` enables binary mode → text features disabled (skip-until, regex filters)
   - Text mode (default) → all text features available
   - Choice is mutually exclusive

2. **Character/Byte Modes vs Delimiters**:
   - `--char-mode` / `--byte-mode` → delimiter is implicit (each char/byte)
   - Cannot combine with `--delimiter` (would be redundant)

3. **Skip Features Compatibility**:
   - `--skip-chars` and `--skip-until` can be combined (skip-chars first, then find delimiter)
   - Both require text mode
   - Both affect hashing but not output (full lines preserved)

4. **Filter Features Compatibility**:
   - `--filter-in` and `--filter-out` can be combined (filter-out applied after filter-in)
   - Both require text mode (regex patterns)
   - Filtered lines never enter deduplication pipeline

5. **Archive/Library Compatibility**:
   - Sequence libraries include mode metadata (window_size, delimiter, skip settings)
   - Library must be loaded with compatible settings (same mode, compatible delimiter)
   - Archives store content in native format (binary archives for binary mode)

---

## Feature Redundancy Analysis

### Identified Redundancies

1. **Multiple Skip Methods** (intentional, not redundant):
   - `--skip-chars <N>`: Fixed-width prefix
   - `--skip-until <delim>`: Variable-width prefix
   - `--skip-regex <pattern>`: Complex prefix patterns
   - **Rationale**: Different use cases, can be combined (chars → until → regex)

2. **Delimiter Specification** (normalized):
   - `--delimiter <string>`: Text delimiter (default)
   - `--delimiter-hex <hex>`: Binary delimiter
   - `--delimiter-regex <pattern>`: Regex delimiter (advanced)
   - **Resolution**: CLI accepts all forms, normalizes internally to binary representation
   - **Rule**: Only one delimiter form allowed per invocation

3. **Filter File vs Inline** (complementary):
   - `--filter-in <pattern>` vs `--filter-in-file <path>`
   - **Rationale**: Inline for quick filters, file for complex filter lists
   - **Rule**: Can specify both (all patterns combined)

4. **Unlimited vs Max-Memory** (complementary):
   - `--unlimited-history` removes history limit
   - `--max-memory <MB>` sets soft warning limit
   - **Rationale**: Unlimited removes hard limit, max-memory provides safety warning
   - **Rule**: Can be combined

### Resolved Redundancies

1. **Save/Load Sequences vs Export/Import Library**:
   - Originally planned as separate features
   - **Resolution**: Use consistent terminology: `--save-sequences`, `--load-sequences`
   - v0.3.0 file format covers both use cases

2. **Archive-dir vs Save-sequences**:
   - `--archive-dir`: Saves skipped sequences (duplicates)
   - `--save-sequences`: Saves discovered unique sequences (patterns)
   - **Resolution**: Different purposes, both valuable
   - **Clarification**: Archive = skipped content, Save = unique patterns

---

## Coherent Feature Groupings

Features are grouped by their interaction patterns and dependencies.

### Group 1: Input Modes (v0.2.0 - mutually exclusive)

Choose ONE input mode:
- **Text mode** (default): Line-based text processing
- **Binary mode** (`--bytes`): Raw byte processing
- **Character mode** (`--char-mode`): UTF-8 character-by-character
- **Byte mode** (`--byte-mode`): Byte-by-byte processing

### Group 2: Record Delimiters (v0.2.0 - one per mode)

Each mode has delimiter options:
- **Text mode**: `--delimiter <string>` (default: `\n`)
- **Binary mode**: `--delimiter-hex <hex>` (default: `0x0a`)
- **Char/byte modes**: No delimiter (each unit is a record)

### Group 3: Preprocessing (v0.2.0 + v0.4.0 - pipeline stages)

Applied in order before hashing:
1. **Line filtering** (v0.4.0): `--filter-in`, `--filter-out` (removes lines from pipeline)
2. **Prefix skipping** (v0.2.0): `--skip-chars`, `--skip-until` (affects hashing only)

### Group 4: Storage and Format (v0.3.0 - foundational)

Persistent storage options:
- **Sequence library format**: Single-file or separate content/metadata
- **Implicit hashes**: Hash derived from content (self-verifying)
- **Save/load**: `--save-sequences`, `--load-sequences`
- **Multiple inputs**: `--directory`, `--file-list`, `--sequences-from-files`

### Group 5: Output Enhancement (v0.5.0, v0.6.0 - additive)

Optional output features:
- **Annotations** (v0.5.0): `--annotate`, `--annotation-format`
- **Archiving** (v0.6.0): `--archive-dir`, `--archive-filename-format`

### Group 6: Advanced Features (v1.0.0 - specialized)

Domain-specific applications:
- **Pattern libraries**: Import/export/merge
- **Search applications**: Pattern discovery, anomaly detection
- **Bio integration**: Compare with bio tools, k-mer analysis

---

## CLI Design Principles

To ensure features work coherently together:

1. **Mode Selection**: Exactly one input mode (text, bytes, char, byte)
2. **Pipeline Order**: Filter → Skip → Hash → Match → Output
3. **Additive Features**: Annotations and archiving don't affect deduplication logic
4. **Format Consistency**: Library files include all settings needed to reproduce
5. **Error Handling**: Incompatible options detected early with clear error messages

### Example Error Messages

```
Error: --skip-until requires text mode (incompatible with --bytes)
Suggestion: Use --delimiter-hex for binary mode, or omit --bytes for text mode

Error: Cannot specify both --delimiter and --char-mode
Suggestion: --char-mode has implicit delimiter (each character). Use one or the other.

Error: --filter-in requires text mode (incompatible with --byte-mode)
Suggestion: Remove --byte-mode or use binary-compatible filtering

Warning: --unlimited-history may cause high memory usage
Current memory: 1.2 GB
Suggestion: Monitor memory with --max-memory <limit> or --progress
```

---

## Complete Workflow Example

Combining multiple features from different versions:

```bash
# v0.2.0 + v0.3.0 + v0.4.0 + v0.5.0 + v0.6.0 features
uniqseq \
  --directory ./app-logs \                           # v0.3.0: Multiple inputs
  --pattern "app-*.log" \                            # v0.3.0: File pattern matching
  --skip-until ' | ' \                               # v0.2.0: Skip timestamp prefix
  --filter-in 'ERROR|WARN|FATAL' \                   # v0.4.0: Include only errors/warnings
  --filter-out 'DeprecationWarning' \                # v0.4.0: Exclude known noise
  --window-size 8 \                                  # Core: Sequence detection
  --unlimited-history \                              # v0.2.0: Complete deduplication
  --save-sequences error-patterns.lib \              # v0.3.0: Save discovered patterns
  --annotate \                                       # v0.5.0: Show where duplicates removed
  --annotation-format '[{count} lines, hash {hash}]' \ # v0.5.0: Custom annotation
  --archive-dir ./unique-errors \                    # v0.6.0: Archive unique errors
  --progress \                                       # Core: Show progress
  > deduplicated-errors.log 2> stats.txt             # Output + statistics
```

**What this does**:
1. Scans `./app-logs` for files matching `app-*.log`
2. Strips timestamps from each line before hashing (` | ` delimiter)
3. Only processes lines with ERROR, WARN, or FATAL (filters out INFO, DEBUG)
4. Excludes known DeprecationWarning noise
5. Detects repeated 8-line sequences with unlimited history
6. Saves discovered error patterns to `error-patterns.lib`
7. Annotates output showing how many lines were skipped
8. Archives each unique error sequence to `./unique-errors/`
9. Shows progress bar during processing
10. Outputs clean log to stdout, statistics to stderr

**Result**:
- Deduplicated error log across all app instances
- Pattern library for future runs
- Archive of all unique errors for analysis
- Annotations showing deduplication effectiveness
- Statistics on redundancy percentage

---

## Implementation Priority Rationale

### Why v0.2.0: Core Flexibility Enhancements First?
- **Foundational impact**: Affects core comparison and memory model
- **Enables future features**: Libraries, archiving, and filtering all need these modes
- **Immediate value**: Users can process binary data, use unlimited history
- **Risk mitigation**: Changes to core algorithm early, before other features depend on it

**Key features**:
- Unlimited history removes artificial constraints
- Raw bytes/arbitrary delimiters expand use cases beyond text logs
- Single char/byte modes enable DNA analysis, binary protocols
- Skip-until/chars solves timestamp problem (very common user request)

### Why v0.3.0: Input/Output Format Extensions Second?
- **Foundational for persistence**: Defines how sequences are stored and loaded
- **Enables v0.5.0+ features**: Annotations and archiving reference this format
- **Moderate complexity**: File format design requires careful versioning
- **Architectural impact**: Establishes interchange format for ecosystem

**Key features**:
- Sequence library format (single-file vs separate)
- Implicit hashes (self-verifying content)
- Multiple input modes (directory, file-list, sequences-from-files)

### Why v0.4.0: Filtering and Preprocessing Third?
- **Affects input pipeline**: Applied before deduplication
- **Builds on v0.2.0**: Works with all input modes (text, binary, char)
- **Moderate complexity**: Pattern matching and filter composition
- **User value**: Noise reduction makes deduplication more effective

**Key features**:
- Filter-in/filter-out with regex patterns
- Research and adopt grep/ripgrep/awk conventions
- Composable filter expressions

### Why v0.5.0: Inline Annotations Fourth?
- **Depends on v0.3.0**: References sequence metadata format
- **Lower architectural impact**: Purely additive output feature
- **User value**: Visibility into deduplication process
- **Low complexity**: Minimal changes to core algorithm

**Key features**:
- Format specifiers for annotations
- Line numbering modes (absolute/relative)
- Customizable annotation templates

### Why v0.6.0: Content Archiving Fifth?
- **Depends on v0.3.0**: Uses sequence file format for archives
- **Lower priority**: Less commonly needed than annotations
- **Standalone value**: Can be used without annotations
- **Low complexity**: Archive writing is independent of core logic

**Key features**:
- Hash-based filename generation
- Idempotent writes
- Configurable archive formats

### Why v1.0.0: Advanced Use Cases Last?
- **Depends on all previous**: Uses stable formats, modes, and features
- **High complexity**: Requires mature ecosystem
- **Specialized applications**: Not needed by most users
- **Optional optimizations**: Core algorithm works well without these

**Key features**:
- Portable sequence libraries (import/export/merge)
- Efficient single-pass search applications
- Bio/genetics tool comparisons
- Domain-specific optimizations

---

## Design Principles for All Features

1. **Opt-in by default**: New features disabled unless explicitly requested
2. **Backward compatible**: Old workflows continue to work unchanged
3. **Composable**: Features work independently or together
4. **Unix philosophy**: Each feature does one thing well
5. **Performance**: No impact when features are disabled
6. **Error resilience**: Continue processing even if optional features fail

---

## Contributing

Feature implementations should follow these guidelines:

**Before implementation**:
1. Review this planning document
2. Discuss approach with maintainers
3. Update planning doc with implementation details

**During implementation**:
1. Write tests first (TDD)
2. Maintain backward compatibility
3. Document CLI options and format specifiers
4. Update IMPLEMENTATION.md with usage examples

**After implementation**:
1. Update version number
2. Move feature from this doc to IMPLEMENTATION.md
3. Add changelog entry
4. Update README with new capabilities

---

## Questions and Discussion

For questions about planned features or to suggest new ones, please:
1. Check existing GitHub issues
2. Open new issue with `enhancement` label
3. Reference this planning document
4. Describe use case and proposed approach

**Note**: This document describes planned work and may change based on user feedback, technical constraints, or changing priorities.
