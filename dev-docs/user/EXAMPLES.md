# Usage Examples and Composition Patterns

**Purpose**: Comprehensive examples for using uniqseq, including composition with standard Unix tools.

## Quick Start Examples

### Basic Deduplication

```bash
# Deduplicate a log file
uniqseq session.log > clean.log

# Process stdin
cat verbose.log | uniqseq > clean.log

# Multiple files
uniqseq file1.log file2.log file3.log > combined-clean.log
```

### Real-Time Monitoring

```bash
# Deduplicate live log stream
tail -f app.log | uniqseq

# With filtering (see below)
tail -f app.log | grep 'ERROR' | uniqseq

# Live pattern discovery with library
tail -f app.log | uniqseq --library-dir patterns/ --annotate
```

---

## Hash Transform Examples

The `--hash-transform` flag pipes each line through a Unix filter for hashing, while preserving the original line in output.

### Skip Fixed-Width Timestamps

```bash
# Simple case: Use --skip-chars (no subprocess overhead)
uniqseq --skip-chars 23 app.log > clean.log

# Input:  "2025-11-22 10:30:15 | ERROR: failed"
# Hashed: "ERROR: failed"
# Output: "2025-11-22 10:30:15 | ERROR: failed"
```

### Skip Variable-Width Prefixes

```bash
# Skip until delimiter with sed
uniqseq --hash-transform "sed 's/^[^|]*| //'" app.log > clean.log

# Input:  "2025-11-22 10:30:15.123 | ERROR: failed"
# Hashed: "ERROR: failed"
# Output: "2025-11-22 10:30:15.123 | ERROR: failed"

# Skip ISO timestamp with sed
uniqseq --hash-transform "sed -E 's/^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+ //'" \
        app.log > clean.log
```

### Extract Specific Fields

```bash
# Hash only the error message (field 3)
uniqseq --hash-transform 'awk -F"|" "{print \$3}"' app.log > clean.log

# Input:  "timestamp | level | ERROR: connection failed"
# Hashed: " ERROR: connection failed"
# Output: "timestamp | level | ERROR: connection failed"
```

### Case-Insensitive Deduplication

```bash
# Convert to lowercase for hashing (case-insensitive matching)
uniqseq --hash-transform 'tr "[:upper:]" "[:lower:]"' app.log > clean.log

# Input 1: "ERROR: Failed to connect"
# Input 2: "error: failed to connect"
# Hashed: "error: failed to connect" (both)
# Output: Only first occurrence (case preserved in output)
```

### Whitespace Normalization

```bash
# Normalize whitespace for matching (ignore spacing differences)
uniqseq --hash-transform "sed 's/[[:space:]]+/ /g'" app.log > clean.log

# Input 1: "ERROR:    Multiple    spaces"
# Input 2: "ERROR: Multiple spaces"
# Hashed: "ERROR: Multiple spaces" (both, normalized)
# Output: Only first occurrence (original spacing preserved)

# Remove all whitespace for matching
uniqseq --hash-transform "tr -d '[:space:]'" app.log > clean.log
```

### Common Use Cases Summary

Here are the most common hash transform patterns:

```bash
# Case-insensitive matching
--hash-transform "tr '[:upper:]' '[:lower:]'"

# Skip timestamps (variable-width)
--hash-transform "cut -d'|' -f2-"

# Extract specific fields
--hash-transform "awk '{print \$3, \$4}'"

# Normalize whitespace
--hash-transform "sed 's/[[:space:]]+/ /g'"

# Remove prefix up to delimiter
--hash-transform "sed 's/^[^|]*| //'"

# Case-insensitive + whitespace normalization (combine multiple transforms)
--hash-transform "tr '[:upper:]' '[:lower:]' | sed 's/[[:space:]]+/ /g'"
```

### Custom Processing Scripts

```bash
# Custom normalization script
cat > normalize.sh << 'EOF'
#!/bin/bash
# Normalize log line: remove timestamps, IDs, normalize whitespace
sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+//g' | \
  sed -E 's/id=[0-9]+/id=X/g' | \
  tr -s ' '
EOF
chmod +x normalize.sh

# Use custom script for hashing
uniqseq --hash-transform './normalize.sh' app.log > clean.log
```

### Hash Transform with Binary Mode

Hash transforms work with binary mode, allowing you to normalize binary records before hashing while preserving the original bytes in output.

#### Binary-Safe Commands

Some shell commands work correctly with binary data (no text assumptions):

```bash
# Extract byte ranges (skip first 16 bytes - e.g., skip header)
uniqseq --byte-mode --delimiter-hex 00 \
  --hash-transform "tail -c +17" file.bin > clean.bin

# Extract specific byte range (bytes 10-30)
uniqseq --byte-mode --delimiter-hex 00 \
  --hash-transform "dd bs=1 skip=10 count=20 2>/dev/null" file.bin > clean.bin

# Extract first N bytes (hash only header)
uniqseq --byte-mode --delimiter-hex 00 \
  --hash-transform "head -c 32" file.bin > clean.bin

# Custom binary normalization tool
uniqseq --byte-mode --delimiter-hex 00 \
  --hash-transform "./normalize-binary-record" protocol.dat > clean.dat

# Hex manipulation (normalize byte patterns)
uniqseq --byte-mode --delimiter-hex 0a \
  --hash-transform "xxd -p | sed 's/cafebabe/deadbeef/' | xxd -r -p" data.bin > clean.bin
```

#### Use Cases for Binary Hash Transforms

1. **Protocol Normalization**: Binary network protocols with sequence numbers or timestamps
   ```bash
   # Skip first 8 bytes (timestamp + sequence number in protocol)
   --hash-transform "tail -c +9"
   ```

2. **Binary Record Headers**: Extract payload, skip headers
   ```bash
   # Skip 64-byte header, hash only payload
   --hash-transform "tail -c +65"
   ```

3. **Binary Field Extraction**: Extract specific fields from binary records
   ```bash
   # Extract bytes 20-50 (specific field in binary format)
   --hash-transform "dd bs=1 skip=20 count=30 2>/dev/null"
   ```

4. **Custom Binary Tools**: Use specialized binary processing tools
   ```bash
   # Custom tool that normalizes binary records
   --hash-transform "./extract-payload-from-binary-record"
   ```

#### Important Cautions

**⚠️ Text-based commands will likely FAIL with binary data:**

```bash
# ❌ BAD: Text commands on binary data
--hash-transform "tr '[:upper:]' '[:lower:]'"  # Assumes valid text encoding
--hash-transform "sed 's/foo/bar/'"            # May break on null bytes
--hash-transform "awk '{print \$2}'"           # Expects text fields
--hash-transform "grep pattern"                # Text pattern matching
```

**Why text commands fail:**
- Binary data contains null bytes (`\0`) which terminate C strings
- Binary data may contain control characters that confuse text tools
- Binary data is not valid UTF-8/ASCII
- Text tools assume newline-delimited records

**✅ Safe approach for binary data:**

1. **Use binary-aware commands**: `head -c`, `tail -c`, `dd`, `xxd`
2. **Use custom binary tools**: Write your own binary processor
3. **No text assumptions**: Don't use text-based filters (`tr`, `sed`, `awk`, `grep`)
4. **Test thoroughly**: Binary data can have unexpected byte sequences

#### When NOT to Use Hash Transform with Binary Mode

**Better alternatives exist:**

```bash
# Instead of binary hash transform, preprocess outside uniqseq
cat binary.dat | your-binary-transform | uniqseq --byte-mode --delimiter-hex 00

# Or use binary-aware tools first
xxd -p binary.dat | sed 's/pattern/replacement/' | xxd -r -p | \
  uniqseq --byte-mode --delimiter-hex 00
```

**Preprocessing is better when:**
- Transform is complex (multiple steps)
- Transform might fail (better error handling outside)
- Transform changes record structure (filtering/splitting)
- You need to validate transform correctness

#### Summary: Binary Hash Transform Guidelines

**Use hash transform with binary mode when:**
- ✅ Using binary-safe commands (`head -c`, `tail -c`, `dd`, `xxd`)
- ✅ Simple byte extraction/skipping
- ✅ Custom binary tools you control
- ✅ You've tested with your specific binary format

**Avoid when:**
- ❌ Using text-based filters (`tr`, `sed`, `awk`, `grep`)
- ❌ Binary format contains null bytes and text tools are involved
- ❌ Not sure if command handles binary safely
- ❌ Complex multi-step transformations (preprocess instead)

### Important: Transform Requirements

**The transform MUST output exactly one line per input line.**

**✅ Valid transforms**:
```bash
--hash-transform 'cut -c 24-'                # Remove prefix
--hash-transform "sed 's/^[^|]*| //'"        # Remove until delimiter
--hash-transform 'tr "[:upper:]" "[:lower:]"' # Case conversion
--hash-transform 'awk "{print \$2}"'         # Extract field
```

**✅ Empty output is valid** (hashes as empty line):
```bash
--hash-transform 'grep "ERROR"'              # Lines without ERROR hash as empty
```

**❌ Invalid transforms** (will cause errors):
```bash
--hash-transform "sed 's/,/\n/g'"            # Splits lines (multiple output lines)
--hash-transform 'head -5'                   # Limits output (breaks after 5 lines)
```

**Error message example**:
```
Error: Hash transform produced multiple lines (expected exactly one).

The --hash-transform command must output exactly one line per input line.
Empty output lines are valid, but the transform cannot split lines.

For splitting lines, preprocess the input before piping to uniqseq.
```

---

## Custom Delimiters

### Text Mode Delimiters (`--delimiter`)

Use `--delimiter` to process records separated by custom text delimiters instead of newlines.

**Supports any arbitrary string delimiter**. Escape sequences `\n`, `\t`, `\0` are interpreted.

```bash
# Null-delimited records (common from find -print0)
find logs/ -name "*.log" -print0 | uniqseq --delimiter '\0' > unique_files.txt

# Comma-separated records
echo "A,B,C,D,E,F,G,H,I,J,A,B,C,D,E,F,G,H,I,J" | uniqseq --delimiter ',' --quiet
# Output: A,B,C,D,E,F,G,H,I,J

# Tab-delimited data
uniqseq --delimiter '\t' data.tsv > clean.tsv

# Multi-character delimiters
uniqseq --delimiter '|||' pipe-separated.txt > clean.txt

# Delimiters with escape sequences
uniqseq --delimiter '\t|\t' tab-pipe-tab.txt > clean.txt
```

### Binary Mode Delimiters (`--delimiter-hex`)

Use `--delimiter-hex` for binary files with delimiters specified as hex bytes. Requires `--byte-mode`.

**Hex format options**:
- Plain hex: `00`, `0a`, `0d0a`
- With 0x prefix: `0x00`, `0x0a`, `0x0d0a`
- Case insensitive: `FF` or `ff`
- Multi-byte: `0d0a` for CRLF (two bytes)

```bash
# Null byte delimiter (0x00)
uniqseq --byte-mode --delimiter-hex 00 file.bin > clean.bin
uniqseq --byte-mode --delimiter-hex 0x00 file.bin > clean.bin  # Same

# CRLF line endings (Windows-style \r\n = 0x0d0a)
uniqseq --byte-mode --delimiter-hex 0d0a windows_file.txt > clean.txt

# ASCII control characters - Record Separator (0x1e)
uniqseq --byte-mode --delimiter-hex 1e protocol.dat > clean.dat

# Start of Header (0x01) - common in binary protocols
uniqseq --byte-mode --delimiter-hex 01 network_capture.bin > clean.bin
```

### When to Use Each

**Use `--delimiter` (text mode)**:
- Processing text files
- Simple delimiters: comma, tab, pipe, null
- UTF-8 encoded content
- Examples: CSV files, null-delimited text, custom separators

**Use `--delimiter-hex` (binary mode)**:
- Processing binary files or mixed encodings
- Need precise byte-level control
- Multi-byte delimiters (like CRLF)
- Binary protocols with specific byte markers
- Examples: Network captures, Windows files, binary protocols

**Key differences**:

| Feature  | `--delimiter`                 | `--delimiter-hex`               |
|----------|-------------------------------|---------------------------------|
| Mode     | Text (default)                | Binary (requires `--byte-mode`) |
| Format   | String with escape sequences  | Hex string (e.g., "00", "0x0a") |
| Use Case | Text files, simple delimiters | Binary files, precise bytes     |
| Examples | `\n`, `\t`, `\0`, `,`, `\|`   | `00`, `0d0a`, `1e`, `0x0a`      |

**Validation rules**:
- `--delimiter` and `--delimiter-hex` are mutually exclusive
- `--delimiter-hex` requires `--byte-mode`
- Hex strings must have even length (each byte = 2 hex chars)

---

## Binary Data Processing

### Binary Protocols with Delimiters

```bash
# Null-terminated records (common in network captures)
uniqseq --byte-mode --delimiter-hex 00 capture.bin > deduped.bin

# Custom magic byte delimiter
uniqseq --byte-mode --delimiter-hex FF protocol.bin > deduped.bin
```

### Fixed-Length Binary Messages

```bash
# Each message is exactly 128 bytes
# Preprocess: Add delimiter after each 128-byte block
dd if=capture.bin bs=128 conv=sync | \
  perl -pe 's/(.{128})/$1\x00/gs' | \
  uniqseq --byte-mode --delimiter-hex 0x00 > deduped.bin
```

### Finding Repeated Byte Patterns

```bash
# Find repeated 256-byte sequences (unstructured data)
uniqseq --byte-mode --window-size 256 memory-dump.bin > unique-patterns.bin

# Use case: Memory dumps, firmware analysis, finding repeated data blocks
# Note: This does NOT respect message boundaries
```

### Binary Analysis with Pattern Libraries

```bash
# Save discovered binary patterns to library
uniqseq --byte-mode \
        --delimiter-hex 0x00 \
        --library-dir patterns/ \
        capture.bin > deduped.bin

# Inspect patterns (native format)
hexdump -C patterns/sequences/a3f5c8d9e1b2c4f6a7b8c9d0e1f2a3b4.uniqseq
strings patterns/sequences/a3f5c8d9e1b2c4f6a7b8c9d0e1f2a3b4.uniqseq
```

---

## Character-by-Character Deduplication (UTF-8)

For finding repeated character sequences within text (not line sequences).

### Split to Character Stream

```bash
# Python helper for UTF-8 aware character splitting
cat input.txt | python3 << 'EOF' | uniqseq --window-size 10 | python3 << 'EOF'
# === SPLIT SCRIPT ===
import sys
for line in sys.stdin:
    for char in line.rstrip('\n'):
        print(char)
    print('§NEWLINE§')
EOF

# === REASSEMBLE SCRIPT ===
import sys
output = []
for line in sys.stdin:
    line = line.rstrip('\n')
    if line == '§NEWLINE§':
        print(''.join(output))
        output = []
    else:
        output.append(line)
if output:
    print(''.join(output))
EOF
```

### Example: DNA Sequence Analysis

```bash
# DNA sequence: Find repeated 15-character k-mers
# Input: ATCGATCGATCG...

# Split by character
echo "ATCGATCGATCGATCGATCGATCG" | \
  python3 -c 'import sys; [print(c) for c in sys.stdin.read().rstrip()]' | \
  uniqseq --window-size 15 | \
  python3 -c 'import sys; print("".join(line.rstrip() for line in sys.stdin))'

# For FASTA files (skip headers) - save to library
grep -v '^>' genome.fasta | tr -d '\n' | \
  python3 -c 'import sys; [print(c) for c in sys.stdin.read()]' | \
  uniqseq --window-size 15 --library-dir kmers-lib/
```

**Use cases**:
- DNA/RNA k-mer analysis (single-character alphabet)
- Repeated character patterns in text
- Typography analysis

**Note**: For byte-by-byte analysis (non-UTF-8), use `--byte-mode` instead.

---

## Pattern Library Workflows

Pattern libraries allow saving and reusing discovered sequences across multiple runs. Sequences are stored in native format (file content IS the sequence) with Blake2b hash-based filenames for fast lookup.

### Library Structure

```bash
library_dir/
  sequences/
    2b040e40757ae905b4a930cba6787c29.uniqseq    # Sequence file (native format)
    5f3a8c1d9e2b4f7a6c8d0e1f2a3b4c5d.uniqseq
    ...
  metadata-20241122-103000-123456/
    config.json        # Run metadata and statistics
    progress.json      # Real-time progress (updated every 1000 lines)
```

### Building an Incremental Library

Use `--library-dir` to both load existing sequences AND save new discoveries to the same library:

```bash
# Day 1: Discover patterns from production logs
uniqseq prod-2024-11-22.log --library-dir ./prod-lib > clean.log

# View the library structure
ls -R prod-lib/
prod-lib/:
sequences/  metadata-20241122-103000-456789/

prod-lib/sequences/:
2b040e40757ae905b4a930cba6787c29.uniqseq
5f3a8c1d9e2b4f7a6c8d0e1f2a3b4c5d.uniqseq

# Inspect a sequence (native format - just cat it!)
cat prod-lib/sequences/2b040e40757ae905b4a930cba6787c29.uniqseq
ERROR: Connection failed
Retrying...
ERROR: Timeout

# View metadata (audit trail, output-only)
cat prod-lib/metadata-20241122-103000-456789/config.json
{
  "timestamp": "2024-11-22T10:30:00Z",
  "window_size": 10,
  "mode": "text",
  "delimiter": "\\n",
  "max_history": "unlimited",
  "sequences_discovered": 47,
  "sequences_preloaded": 0,
  "sequences_saved": 47,
  "total_records_processed": 125000,
  "records_skipped": 98000
}

# Day 2: Load existing sequences + save new discoveries
uniqseq prod-2024-11-23.log --library-dir ./prod-lib > clean.log
# - Loads all sequences from prod-lib/sequences/
# - Saves newly discovered sequences to prod-lib/sequences/
# - Creates metadata-20241123-160000-789012/config.json

# Day 3: Continue accumulating
uniqseq prod-2024-11-24.log --library-dir ./prod-lib > clean.log
# Library grows incrementally with all observed sequences
```

### Loading Sequences (Read-Only)

Use `--read-sequences` to load sequences without modifying the source directory:

```bash
# Create custom pattern files (any filename, any extension)
mkdir my-patterns

# Sequences stored in native format (with newlines between records)
cat > my-patterns/error-retries.txt << 'EOF'
ERROR: Connection failed
Retrying...
ERROR: Timeout
EOF

cat > my-patterns/warning-sequence.txt << 'EOF'
WARNING: Slow response
Timeout exceeded
Request aborted
EOF

# Load sequences without saving (read-only mode)
uniqseq --read-sequences ./my-patterns app.log > filtered.log
# - Sequences from my-patterns/ are treated as "already seen"
# - No modifications to my-patterns/ directory
# - First observation of each sequence is skipped

# Load from multiple directories
uniqseq \
  --read-sequences ./error-patterns \
  --read-sequences ./security-patterns \
  app.log > filtered.log
```

### Combined Mode: Load + Save

Combine `--read-sequences` (read-only) with `--library-dir` (read-write) for pause/resume workflows:

```bash
# Load patterns from two sources + save all observed sequences
uniqseq \
  --read-sequences ./error-patterns \
  --read-sequences ./security-patterns \
  --library-dir ./mylib \
  input.log > clean.log

# Behavior:
# 1. Pre-loads sequences from ./error-patterns/ (read-only)
# 2. Pre-loads sequences from ./security-patterns/ (read-only)
# 3. Pre-loads sequences from ./mylib/sequences/ (existing library)
# 4. Saves newly observed sequences (not already in ./mylib/) to ./mylib/sequences/
# 5. Creates ./mylib/metadata-<timestamp>/config.json with run statistics
```

### Multi-System Pattern Sharing

```bash
# Production: Build library
uniqseq /var/log/app.log --library-dir /tmp/prod-lib

# Copy sequences to development (just the sequences directory)
scp -r prod:/tmp/prod-lib/sequences ./prod-patterns

# Development: Apply production patterns (read-only)
uniqseq --read-sequences ./prod-patterns dev-logs.log > clean.log
# Shows only sequences not seen in production

# Or: Apply production patterns + save new observations
uniqseq \
  --read-sequences ./prod-patterns \
  --library-dir ./dev-lib \
  dev-logs.log > clean.log
# - Loads prod patterns (read-only)
# - Saves new dev-only patterns to ./dev-lib/
```

### Pause/Resume Workflow

The library enables pausing and resuming deduplication across runs:

```bash
# Process first part of large file
head -n 100000 huge.log | uniqseq --library-dir ./lib > part1.log

# Resume processing (library remembers what we've seen)
tail -n +100001 huge.log | uniqseq --library-dir ./lib > part2.log

# Or process multiple sources incrementally
uniqseq source1.log --library-dir ./lib > clean1.log
uniqseq source2.log --library-dir ./lib > clean2.log
uniqseq source3.log --library-dir ./lib > clean3.log
# Each run adds to the library's knowledge
```

### Monitoring Long-Running Jobs

When processing large files with `--library-dir`, uniqseq creates a `progress.json` file that's updated every 1000 lines for real-time monitoring:

```bash
# Start long-running job in background
uniqseq huge.log --library-dir ./mylib > clean.log &

# Monitor progress in real-time (separate terminal)
watch -n 1 'jq . mylib/metadata-*/progress.json'

# Example output:
{
  "last_update": "2024-11-23T15:30:45Z",
  "total_sequences": 1247,
  "sequences_preloaded": 800,
  "sequences_discovered": 447,
  "sequences_saved": 1100,
  "total_records_processed": 125000,
  "records_skipped": 98000
}

# Or count sequence files
watch -n 1 'ls mylib/sequences/ | wc -l'

# Or monitor library growth
watch -n 1 'du -sh mylib/'
```

The `progress.json` file uses atomic writes (temp file + rename) to prevent partial reads during monitoring.

### Finding New Patterns Only

Use `--inverse` with `--read-sequences` to show only sequences NOT in the library:

```bash
# Load known patterns, show only novel sequences
uniqseq \
  --read-sequences ./known-patterns \
  --inverse \
  new-build.log > new-issues-only.log

# Inverse mode: output sequences NOT in the pre-loaded set
# Useful for identifying new error patterns in builds
```

---

## Filtering Examples

**Status**: Basic pattern filtering (Phase 1) is implemented. Pattern files and advanced features coming in future phases.

Filtering controls which lines participate in deduplication. Lines that don't match filter patterns pass through unchanged (not deduplicated).

### Track Patterns (Allowlist Mode)

Use `--track` to deduplicate only lines matching specific patterns. All other lines pass through unchanged.

```bash
# Only deduplicate ERROR/WARN lines (DEBUG/INFO pass through unchanged)
uniqseq --track 'ERROR|WARN' app.log > clean.log

# Deduplicate critical messages only
uniqseq --track 'CRITICAL|FATAL' app.log > clean.log

# Multiple track patterns (evaluated in order)
uniqseq --track 'ERROR' --track 'WARN' --track 'FATAL' app.log > clean.log
```

**How it works**:
- Lines matching any `--track` pattern are deduplicated
- Lines NOT matching any `--track` pattern pass through unchanged
- This creates a "allowlist" - only tracked patterns are deduplicated
- Use for focusing on specific types of messages (errors, warnings, etc.)

### Bypass Patterns (Denylist Mode)

Use `--bypass` to exclude lines from deduplication. Matching lines pass through unchanged.

```bash
# Exclude DEBUG from deduplication (but keep in output)
uniqseq --bypass 'DEBUG' app.log > clean.log

# Bypass multiple patterns
uniqseq --bypass 'DEBUG|TRACE|VERBOSE' app.log > clean.log

# Bypass known noisy patterns
uniqseq --bypass 'Starting\s+\w+|Finished\s+\w+' app.log > clean.log
```

**How it works**:
- Lines matching any `--bypass` pattern pass through unchanged
- Lines NOT matching any `--bypass` pattern are deduplicated
- Use for excluding noisy content that shouldn't be deduplicated

### Combining Track and Bypass

Combine both pattern types for fine-grained control:

```bash
# Track critical errors, bypass deprecation warnings
uniqseq --track 'ERROR|CRITICAL' \
        --bypass 'DeprecationWarning' \
        app.log > clean.log

# Example: Complex filtering
# - Track only ERROR and FATAL messages
# - But bypass known harmless errors
uniqseq --track 'ERROR|FATAL' \
        --bypass 'ERROR.*connection_pool.*healthy' \
        --bypass 'FATAL.*test_mode' \
        production.log > clean.log
```

**Pattern evaluation order matters** - see Sequential Pattern Evaluation below.

### Sequential Pattern Evaluation

Patterns are evaluated in command-line order. **First match wins**.

```bash
# Example 1: Order determines behavior
uniqseq --track 'CRITICAL' --bypass 'ERROR' app.log
# "CRITICAL ERROR" → deduplicated (--track matches first)
# "ERROR WARNING" → passes through (--bypass matches first)
# "INFO" → passes through (no match in allowlist mode)

uniqseq --bypass 'ERROR' --track 'CRITICAL' app.log
# "CRITICAL ERROR" → passes through (--bypass matches first)
# "ERROR WARNING" → passes through (--bypass matches first)
# "CRITICAL" → deduplicated (--track matches)

# Example 2: Multiple patterns of same type
uniqseq --track 'ERROR' --track 'WARN' --track 'FATAL' app.log
# Evaluation order: ERROR, then WARN, then FATAL
# First matching pattern wins

# Example 3: Refining filters
uniqseq --bypass 'DEBUG' --track 'DEBUG CRITICAL' app.log
# "DEBUG INFO" → passes through (--bypass matches first)
# "DEBUG CRITICAL" → deduplicated (--track matches second)
# This allows overriding broad bypass patterns with specific track patterns
```

### Pattern Files

Load patterns from files for reusable filter configurations:

**Pattern file format**:
- One regex pattern per line
- Lines starting with `#` are comments
- Blank lines are ignored
- Leading/trailing whitespace is stripped

**Example: error-patterns.txt**
```
# Common error signatures
ERROR
CRITICAL
FATAL
Exception
Traceback

# Include specific error codes
E[0-9]{4}
```

**Example: noise-patterns.txt**
```
# Known noisy output to exclude
DEBUG
TRACE
VERBOSE
Starting\s+\w+
Finished\s+\w+

# Skip comment lines in logs
^#.*
```

**Usage examples**:

```bash
# Load track patterns from file
uniqseq --track-file error-patterns.txt app.log > clean.log

# Load bypass patterns from file
uniqseq --bypass-file noise-patterns.txt verbose-app.log > clean.log

# Multiple pattern files
uniqseq \
  --track-file error-patterns.txt \
  --track-file security-events.txt \
  audit.log > clean.log

# Mix files and inline patterns
# Evaluation order: inline track, track files, inline bypass, bypass files
uniqseq \
  --track 'URGENT' \
  --track-file error-patterns.txt \
  --bypass 'TEST' \
  --bypass-file noise-patterns.txt \
  app.log > clean.log
```

**Pattern file benefits**:
- Reusable filter configurations across different log files
- Share common patterns across team
- Version control filter rules
- Easier to maintain complex filter sets
- Comments document why patterns exist

### Real-World Filtering Examples

**Application logs** (focus on errors, bypass debug):
```bash
# Deduplicate only ERROR/WARN, let everything else through
uniqseq --track 'ERROR|WARN' app.log > clean.log

# Alternative: Bypass debug/trace, deduplicate everything else
uniqseq --bypass 'DEBUG|TRACE' app.log > clean.log
```

**System logs** (exclude known noise):
```bash
# Bypass systemd startup messages, deduplicate the rest
uniqseq --bypass 'systemd.*Starting|systemd.*Started' /var/log/syslog > clean.log
```

**Build logs** (track errors and warnings only):
```bash
# Only deduplicate compiler warnings/errors
uniqseq --track 'warning:|error:|fatal error:' build.log > clean.log
```

**Mixed log streams** (complex filtering):
```bash
# Track security events and errors, bypass verbose logging
uniqseq --track 'authentication|authorization|permission' \
        --track 'ERROR|FATAL|CRITICAL' \
        --bypass 'DEBUG|TRACE|VERBOSE' \
        combined.log > clean.log
```

---

## Annotations and Inverse Mode

### Basic Annotations

Show where duplicates were skipped with inline markers:

```bash
uniqseq --annotate app.log
```

**Output**:
```
Line 1
Line 2
Line 3
[DUPLICATE: Lines 4-6 matched lines 1-3 (sequence seen 2 times)]
Line 7
```

### Custom Annotation Format

Use template variables to create custom markers:

**Available Variables**:
- `{start}` - First line number of skipped sequence
- `{end}` - Last line number of skipped sequence
- `{match_start}` - First line number of matched (original) sequence
- `{match_end}` - Last line number of matched sequence
- `{count}` - Total times the sequence has been seen
- `{window_size}` - Current window size setting

**Examples**:

```bash
# Compact format
uniqseq --annotate --annotation-format '... {count}x duplicate skipped ...' app.log

# Machine-readable format
uniqseq --annotate --annotation-format 'SKIP|{start}|{end}|{count}' app.log

# Detailed format
uniqseq --annotate \
        --annotation-format 'Skipped lines {start}-{end} (matched {match_start}-{match_end}, seen {count} times)' \
        app.log
```

### Extract Annotations Only

Get just the annotation markers for analysis:

```bash
# Extract skip markers
uniqseq --annotate --annotation-format 'SKIP|{start}|{end}|{count}' app.log | \
  grep '^SKIP'

# Count duplicates
uniqseq --annotate app.log | grep '^\[DUPLICATE' | wc -l

# Analyze duplicate frequency
uniqseq --annotate --annotation-format '{count}' app.log | \
  grep -E '^[0-9]+$' | \
  sort -n | \
  uniq -c
```

### Inverse Mode (Show Only Duplicates)

Flip the output to see only duplicate sequences:

```bash
# Show only duplicates
uniqseq --inverse app.log > duplicates.log

# Analyze duplicate patterns
uniqseq --inverse --window-size 5 app.log | less

# Count duplicate lines vs unique lines
wc -l app.log  # Total
uniqseq app.log | wc -l  # Unique
uniqseq --inverse app.log | wc -l  # Duplicates
```

### Combining Inverse Mode with Filters

```bash
# Find only duplicate error messages
uniqseq --track 'ERROR' --inverse app.log > duplicate-errors.log

# Exclude debug, show duplicates of everything else
uniqseq --bypass 'DEBUG' --inverse app.log > duplicate-messages.log
```

### Annotations + Inverse Mode

**Note**: Annotations are disabled in inverse mode (since inverse mode shows duplicates, not skips).

```bash
# This works - annotations show what was skipped
uniqseq --annotate app.log > output.log

# Annotations ignored in inverse mode
uniqseq --annotate --inverse app.log  # annotations not shown
```

### Debugging Workflow with Annotations

```bash
# Step 1: See what's being deduplicated
uniqseq --annotate app.log > annotated.log

# Step 2: Review annotations
grep '\[DUPLICATE' annotated.log

# Step 3: Extract actual duplicates for analysis
uniqseq --inverse app.log > duplicates.log

# Step 4: Normal deduplication
uniqseq app.log > clean.log
```

### Real-World Annotation Uses

**Documentation Generation**:
```bash
# Add markers showing where content was condensed
uniqseq --annotate \
        --annotation-format '... ({count} similar entries omitted) ...' \
        session-transcript.log > documentation.log
```

**Log Analysis**:
```bash
# Track repetition counts for monitoring
uniqseq --annotate --annotation-format 'DUP_COUNT:{count}' app.log | \
  grep 'DUP_COUNT' | \
  awk -F: '{sum+=$2; count++} END {print "Average duplicates:", sum/count}'
```

**Quality Assurance**:
```bash
# Find frequently repeated errors (potential bugs)
uniqseq --annotate --annotation-format 'COUNT:{count}|{start}' app.log | \
  grep 'COUNT' | \
  sort -t: -k2 -rn | \
  head -10  # Top 10 most repeated sequences
```

---

## Composition with Unix Tools

### Multiple Files (Aggregation)

```bash
# Process all files matching pattern
cat logs/*.log | uniqseq > clean.log

# Recursive file search
find logs/ -name "*.log" -exec cat {} + | uniqseq > clean.log

# Files from list
xargs cat < file-list.txt | uniqseq > clean.log
```

### Pre-filtering with grep/ripgrep

```bash
# Only process lines containing ERROR
grep 'ERROR' app.log | uniqseq > clean-errors.log

# Exclude DEBUG lines before deduplication
grep -v 'DEBUG' app.log | uniqseq > clean.log

# Chain multiple filters
grep -E 'ERROR|WARN' app.log | \
  grep -v 'DeprecationWarning' | \
  uniqseq > clean.log

# Use ripgrep for better performance
rg 'ERROR|WARN' app.log | uniqseq > clean.log
```

**Note**: Pre-filtering with grep removes lines entirely. Use `--track/--bypass` if you want filtered-out lines to remain in output.

### Result Analysis

```bash
# Show what was removed
diff input.log clean.log

# Count reduction
echo "Original: $(wc -l < input.log)"
echo "Deduplicated: $(wc -l < clean.log)"

# Calculate percentage
python3 << EOF
original = $(wc -l < input.log)
deduplicated = $(wc -l < clean.log)
reduction = 100 * (original - deduplicated) / original
print(f"Reduction: {reduction:.1f}%")
EOF
```

---

## Complementary Workflows with Other Tools

### 1. Preprocess Logs for Loki/Elasticsearch

**Problem**: Redundant logs waste storage and slow queries.

**Solution**: Deduplicate before ingestion.

```bash
# Deduplicate before sending to Loki
tail -f app.log | uniqseq | promtail --config loki.yml

# For Elasticsearch/Filebeat
uniqseq app.log | filebeat -c filebeat.yml

# Typical results: 70-90% storage reduction
```

### 2. Combine with Template Extraction (Drain, Spell)

**Problem**: Template extractors slow down with redundant input.

**Solution**: Deduplicate first to reduce input size.

```bash
# Remove duplicates before template extraction
uniqseq verbose.log | drain3 > templates.txt

# 80% smaller input → faster processing
```

**Alternative: Normalize then deduplicate**:
```bash
# Extract templates first (normalize), then deduplicate
drain3 verbose.log > normalized.log
uniqseq normalized.log > clean.log
```

### 3. Anomaly Detection After Deduplication

**Problem**: Anomaly detectors overwhelmed by repeated patterns.

**Solution**: Remove known patterns first.

```bash
# Remove known patterns
uniqseq --read-sequences ./known-patterns input.log > novel.log

# Find anomalies in novel content only
logreduce novel.log > anomalies.txt
```

### 4. Interactive Troubleshooting

**Problem**: Live logs too verbose to read.

**Solution**: Real-time deduplication with pattern library inspection.

```bash
# Terminal 1: Deduplicate live logs with library
tail -f app.log | uniqseq --library-dir patterns/ --annotate

# Terminal 2: Monitor discovered patterns
watch -n 1 'ls -lt patterns/sequences/ | head -20'

# Terminal 3: Inspect specific pattern (native format)
cat patterns/sequences/2b040e40757ae905b4a930cba6787c29.uniqseq
```

### 5. Build Output Analysis

**Problem**: Build logs repeat warnings/errors, hard to find new issues.

**Solution**: Incremental pattern library across builds.

```bash
# Build 1: Discover patterns
uniqseq build-001.log --library-dir build-lib/ > clean-001.log

# Build 2: Load existing + discover new patterns
uniqseq build-002.log --library-dir build-lib/ > clean-002.log

# Find new issues only (show sequences NOT in library)
uniqseq --read-sequences build-lib/sequences/ \
        --inverse \
        build-002.log > new-issues.log
```

### 6. CI/CD Integration

```bash
# In CI pipeline: Load baseline, save new patterns
uniqseq build.log \
        --read-sequences baseline-lib/sequences/ \
        --library-dir new-patterns-lib/ \
        > clean.log

# Check metadata for number of new patterns discovered
python3 << 'EOF'
import json
from pathlib import Path
import sys

# Find most recent metadata
metadata_dirs = sorted(Path('new-patterns-lib').glob('metadata-*'))
if metadata_dirs:
    config = json.load(open(metadata_dirs[-1] / 'config.json'))
    new_patterns = config['sequences_discovered']
    if new_patterns > 100:
        print(f"Too many new patterns: {new_patterns}")
        sys.exit(1)
EOF
```

---

## Advanced Examples

### Case-Insensitive Deduplication with Annotations

```bash
uniqseq --hash-transform 'tr "[:upper:]" "[:lower:]"' \
        --annotate \
        --annotation-format 'Skipped {count} duplicate lines' \
        app.log > clean.log
```

### Multi-Stage Pipeline

```bash
# Stage 1: Pre-filter to errors only
# Stage 2: Skip timestamps for deduplication
# Stage 3: Save patterns to library
# Stage 4: Annotate output

grep 'ERROR' app.log | \
  uniqseq --skip-chars 23 \
          --library-dir error-lib/ \
          --annotate \
          > clean-errors.log
```

---

## Performance Tips

### Streaming vs Batch

```bash
# Batch: Faster for files (unlimited history by default)
uniqseq large-file.log > clean.log

# Streaming: Bounded memory for continuous streams
tail -f app.log | uniqseq

# Explicit unlimited history for complete deduplication
uniqseq --unlimited-history huge-file.log > clean.log
```

### Pattern Library Reuse

```bash
# First run: Discover patterns
uniqseq day1.log --library-dir patterns-lib/ > clean1.log

# Subsequent runs: Load patterns + discover new ones
uniqseq day2.log --library-dir patterns-lib/ > clean2.log
uniqseq day3.log --library-dir patterns-lib/ > clean3.log

# Library grows incrementally, speeds up matching for known patterns
```

---

## Common Patterns

### Log Cleanup for Documentation

```bash
# Clean terminal session for README
uniqseq --annotate session.log > clean-session.log

# Remove annotations for final documentation
uniqseq session.log > clean-session.log
```

### Debugging Deduplication

```bash
# Show what's being deduplicated
uniqseq --annotate \
        --annotation-format 'SKIPPED: {count} times, lines {start}-{end}' \
        input.log > output.log

# Show only the duplicates
uniqseq --inverse input.log > duplicates-only.log

# Detailed analysis with custom format
uniqseq --annotate \
        --annotation-format 'Lines {start}-{end} duplicate of {match_start}-{match_end} (seen {count}x)' \
        input.log | grep 'duplicate of'
```

---

## See Also

- **PLANNING_REFINED.md** - Feature roadmap
- **DESIGN_RATIONALE.md** - Why features were included/excluded
- **IMPLEMENTATION.md** - Implementation overview
- **ALGORITHM_DESIGN.md** - Core algorithm details
