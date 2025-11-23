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
tail -f app.log | uniqseq --streaming

# With filtering (see below)
tail -f app.log | grep 'ERROR' | uniqseq --streaming

# Live pattern discovery
tail -f app.log | uniqseq --streaming \
                         --save-patterns patterns/ --format directory \
                         --annotate
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

### Binary Analysis with Pattern Saving

```bash
# Save discovered binary patterns
uniqseq --byte-mode \
        --delimiter-hex 0x00 \
        --save-patterns patterns/ --format directory \
        capture.bin > deduped.bin

# Inspect patterns
hexdump -C patterns/a3f5c8d9.bin
strings patterns/a3f5c8d9.bin
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

# For FASTA files (skip headers)
grep -v '^>' genome.fasta | tr -d '\n' | \
  python3 -c 'import sys; [print(c) for c in sys.stdin.read()]' | \
  uniqseq --window-size 15 --save-patterns kmers.lib
```

**Use cases**:
- DNA/RNA k-mer analysis (single-character alphabet)
- Repeated character patterns in text
- Typography analysis

**Note**: For byte-by-byte analysis (non-UTF-8), use `--byte-mode` instead.

---

## Pattern Library Workflows

### Building Reusable Pattern Libraries

```bash
# Day 1: Discover patterns
uniqseq --save-patterns build-patterns.lib build-001.log > clean-001.log

# Day 2: Load and update patterns (incremental)
uniqseq --load-patterns build-patterns.lib \
        --save-patterns build-patterns-v2.lib \
        build-002.log > clean-002.log

# Day 3: Continue incremental updates
uniqseq --load-patterns build-patterns-v2.lib \
        --save-patterns build-patterns-v3.lib \
        build-003.log > clean-003.log
```

### Directory Format for Live Inspection

```bash
# Save patterns to directory (hash-based filenames)
uniqseq --save-patterns patterns/ --format directory \
        --streaming \
        app.log > clean.log

# In another terminal: Monitor discovered patterns
watch -n 1 'ls -lt patterns/ | head -20'

# Inspect specific pattern
cat patterns/a3f5c8d9e1b2c4f6.txt

# Count total patterns
ls patterns/*.txt | wc -l
```

### Finding New Issues Only

```bash
# Load known patterns, show only novel sequences
uniqseq --load-patterns known-patterns.lib \
        --inverse \
        new-build.log > new-issues-only.log
```

---

## Filtering Examples

Filtering affects what gets deduplicated, not what gets output. Filtered-out lines pass through unchanged.

### Include/Exclude by Pattern

```bash
# Only deduplicate ERROR/WARN lines (DEBUG/INFO pass through)
uniqseq --filter-in 'ERROR|WARN' app.log > clean.log

# Exclude DEBUG from deduplication (but keep in output)
uniqseq --filter-out 'DEBUG' app.log > clean.log

# Combine: Only deduplicate errors, exclude known noise
uniqseq --filter-in 'ERROR|FATAL' \
        --filter-out 'DeprecationWarning' \
        app.log > clean.log
```

### Patterns from File

```bash
# Create filter file
cat > important-patterns.txt << EOF
ERROR
FATAL
CRITICAL
Exception
EOF

# Use patterns from file
uniqseq --filter-in-file important-patterns.txt app.log > clean.log
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

**Note**: Pre-filtering with grep removes lines entirely. Use `--filter-in/--filter-out` if you want filtered-out lines to remain in output.

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
tail -f app.log | uniqseq --streaming | promtail --config loki.yml

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
uniqseq --load-patterns known-patterns.lib input.log > novel.log

# Find anomalies in novel content only
logreduce novel.log > anomalies.txt
```

### 4. Interactive Troubleshooting

**Problem**: Live logs too verbose to read.

**Solution**: Real-time deduplication with pattern inspection.

```bash
# Terminal 1: Deduplicate live logs
tail -f app.log | uniqseq --streaming \
                         --save-patterns patterns/ --format directory \
                         --annotate

# Terminal 2: Monitor discovered patterns
watch -n 1 'ls -lt patterns/ | head -20'

# Terminal 3: Inspect specific pattern
cat patterns/a3f5c8d9e1b2c4f6.txt
```

### 5. Build Output Analysis

**Problem**: Build logs repeat warnings/errors, hard to find new issues.

**Solution**: Incremental pattern library across builds.

```bash
# Build 1: Discover patterns
uniqseq --save-patterns build-patterns.lib build-001.log > clean-001.log

# Build 2: Load + update patterns
uniqseq --load-patterns build-patterns.lib \
        --save-patterns build-patterns-v2.lib \
        build-002.log > clean-002.log

# Find new issues only
uniqseq --load-patterns build-patterns.lib \
        --inverse \
        build-002.log > new-issues.log
```

### 6. CI/CD Integration

```bash
# In CI pipeline: Check for new repeated patterns
uniqseq --load-patterns baseline-patterns.lib \
        --save-patterns new-patterns.lib \
        --stats-format json \
        build.log > clean.log 2> stats.json

# Parse stats to fail build if too many new patterns
python3 << EOF
import json
stats = json.load(open('stats.json'))
if stats['unique_sequences'] > 100:
    print(f"Too many new patterns: {stats['unique_sequences']}")
    exit(1)
EOF
```

---

## Advanced Examples

### Case-Insensitive Deduplication with Annotations

```bash
uniqseq --hash-transform 'tr "[:upper:]" "[:lower:]"' \
        --annotate \
        --annotation-format '[skipped {count} lines (hash {hash})]' \
        app.log > clean.log
```

### Multi-Stage Pipeline

```bash
# Stage 1: Pre-filter to errors only
# Stage 2: Skip timestamps for deduplication
# Stage 3: Save patterns
# Stage 4: Annotate output

grep 'ERROR' app.log | \
  uniqseq --skip-chars 23 \
          --save-patterns error-patterns.lib \
          --annotate \
          --min-repeats 3 \
          > clean-errors.log
```

### JSON Statistics for Monitoring

```bash
# Process logs and extract metrics
uniqseq --stats-format json app.log > clean.log 2> stats.json

# Parse with jq
jq '.redundancy_percentage' stats.json
jq '.unique_sequences' stats.json

# Alert if redundancy too high
REDUNDANCY=$(jq '.redundancy_percentage' stats.json)
if (( $(echo "$REDUNDANCY > 80" | bc -l) )); then
    echo "Warning: High redundancy ($REDUNDANCY%)"
fi
```

---

## Performance Tips

### Streaming vs Batch

```bash
# Batch: Faster for files (unlimited history by default)
uniqseq large-file.log > clean.log

# Streaming: Bounded memory for continuous streams
tail -f app.log | uniqseq --streaming

# Explicit unlimited history for complete deduplication
uniqseq --unlimited-history huge-file.log > clean.log
```

### Pattern Library Reuse

```bash
# First run: Discover patterns (slow)
uniqseq --save-patterns patterns.lib day1.log > clean1.log

# Subsequent runs: Load patterns (fast)
uniqseq --load-patterns patterns.lib day2.log > clean2.log
uniqseq --load-patterns patterns.lib day3.log > clean3.log

# Pattern library speeds up processing by 2-5x
```

### Directory vs Single File Format

```bash
# Single file: Better for version control, atomic writes
uniqseq --save-patterns patterns.lib input.log

# Directory: Better for live inspection, fast lookup
uniqseq --save-patterns patterns/ --format directory input.log

# Choose based on use case:
# - CI/CD, versioning → single file
# - Live troubleshooting, inspection → directory
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

### Noise Reduction

```bash
# Only deduplicate sequences that appear 5+ times
uniqseq --min-repeats 5 noisy-logs.log > clean.log
```

### Debugging Deduplication

```bash
# Show what's being deduplicated
uniqseq --annotate --annotation-format '[SKIPPED: {count} lines at {start}-{end}, hash {hash}]' \
        input.log > output.log

# Show only the duplicates
uniqseq --inverse input.log > duplicates-only.log
```

---

## See Also

- **PLANNING_REFINED.md** - Feature roadmap
- **DESIGN_RATIONALE.md** - Why features were included/excluded
- **IMPLEMENTATION.md** - Implementation overview
- **ALGORITHM_DESIGN.md** - Core algorithm details
