# Binary Analysis: Memory Dump Forensics

Analyze memory dumps and firmware images to identify repeated structures, strings, and allocated blocks for security research and malware analysis.

## The Problem

Memory dumps and firmware images contain significant redundancy:

- **Repeated allocations** - Same strings or structs allocated many times
- **Template structures** - Identical object instances in memory
- **String pools** - Duplicate string constants
- **Padding and alignment** - Repeated fill bytes
- **Large dump sizes** - Multi-gigabyte memory images are expensive to analyze

**Deduplication** helps identify unique structures and reduces analysis overhead.

## Input Data

???+ note "memory-dump.bin"
    Binary memory dump (**374 bytes**) containing repeated memory structures:

    - String allocations (4 identical instances)
    - Struct data (3 identical instances)
    - Buffer blocks (2 identical instances)
    - Unique heap metadata (1 instance)

    Blocks separated by padding bytes (`0xFF`).

    **Hex dump (first 20 lines)**:
    ```text
    00000000: 7573 6572 5f73 6573 7369 6f6e 5f41 4141  user_session_AAA
    00000010: 4141 4141 4141 4141 4141 4141 4141 4141  AAAAAAAAAAAAAAAA
    00000020: 4141 4100 0078 5634 12ff ffff ffff ffff  AA..xV4.........
    00000030: ffef bead de01 0000 0000 0100 0002 434f  ..............CO
    00000040: 4e46 4947 0000 ffff ffff ffff ffff ff75  NFIG...........u
    ...
    ```

## Output Data

???+ success "expected-memory-dedup.bin"
    Deduplicated memory dump (**242 bytes**):

    - 1× String allocation (3 duplicates removed)
    - 1× Struct data (2 duplicates removed)
    - 1× Buffer block (1 duplicate removed)
    - 1× Heap metadata (kept)

    **Result**: **35% size reduction** (374 → 242 bytes)

## Solution

=== "CLI"

    <!-- verify-file: output.bin expected: expected-memory-dedup.bin -->
    <!-- termynal -->
    ```console
    $ uniqseq memory-dump.bin \
        --byte-mode \
        --delimiter-hex ff \
        --window-size 1 \
        --quiet > deduped-memory.bin
    ```

    **Options:**

    - `--byte-mode`: Process binary memory data
    - `--delimiter-hex ff`: Split on padding byte (0xFF)
    - `--window-size 1`: Deduplicate individual memory blocks
    - `--quiet`: Suppress statistics output

=== "Python"

    <!-- verify-file: output.bin expected: expected-memory-dedup.bin -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        delimiter=b"\xff",    # (1)!
        window_size=1,        # (2)!
    )

    with open("memory-dump.bin", "rb") as f:
        with open("output.bin", "wb") as out:
            data = f.read()
            # Split on delimiter, keeping empty chunks (consecutive delimiters)
            blocks = data.split(b'\xff')
            # Process all but last block (last is after trailing delimiter)
            for block in blocks[:-1]:
                uniqseq.process_line(block, out)
            # Process last block if non-empty
            if blocks[-1]:
                uniqseq.process_line(blocks[-1], out)
            uniqseq.flush(out)
    ```

    1. Use bytes delimiter for binary mode
    2. Deduplicate individual memory blocks

## How It Works

Binary deduplication identifies identical memory structures:

```text
Before (374 bytes with duplicates):
[String: "user_session_AAA..."] <-- Keep
[Padding: 0xFFFFFFFF...]
[Struct: {0xDEADBEEF, ...}]    <-- Keep
[Padding: 0xFFFFFFFF...]
[String: "user_session_AAA..."] <-- Duplicate, remove
[Padding: 0xFFFFFFFF...]
[Buffer: "Buffer: AAA..."]      <-- Keep
...
(more duplicates)

After (242 bytes, unique only):
[String: "user_session_AAA..."]
[Struct: {0xDEADBEEF, ...}]
[Buffer: "Buffer: AAA..."]
[Heap metadata: {0x7fff0000, ...}]
```

## Real-World Workflows

### Firmware Analysis

Extract unique strings and structures from firmware images:

```bash
# Analyze firmware image
uniqseq firmware.bin \
    --byte-mode \
    --delimiter-hex 00 \
    --window-size 1 \
    --quiet > unique-firmware-strings.bin

# Convert to readable strings
strings unique-firmware-strings.bin > firmware-strings.txt

# Analyze for hardcoded credentials, URLs, etc.
grep -E "(password|api_key|http)" firmware-strings.txt
```

### Malware Memory Analysis

Identify unique malware artifacts in memory dumps:

```bash
# Extract process memory
volatility -f memory.dmp --profile=Win10x64 memdump -p 1234 -D .

# Deduplicate memory blocks
uniqseq 1234.dmp \
    --byte-mode \
    --delimiter-hex ff \
    --window-size 1 \
    --stats-format json \
    > unique-blocks.bin \
    2> analysis-stats.json

# Check redundancy
jq '.statistics.redundancy_pct' analysis-stats.json
```

Output: `67.5%` (high redundancy indicates many repeated structures)

### Heap Spray Detection

Detect heap spray attacks by finding repeated allocations:

```bash
# Analyze process heap
uniqseq heap-dump.bin \
    --byte-mode \
    --delimiter-hex 00 \
    --annotate | \
    grep "DUPLICATE" | \
    wc -l
```

High duplicate count may indicate heap spray attack.

### String Pool Analysis

Extract unique strings from memory:

```bash
# Dump memory, extract null-terminated strings
uniqseq memory.dmp \
    --byte-mode \
    --delimiter-hex 00 \
    --quiet | \
    strings -n 8 | \
    head -20
```

Shows 20 longest unique strings from memory.

### Struct Pattern Discovery

Find repeated data structures:

```bash
# Identify 16-byte aligned structures
uniqseq memory.bin \
    --byte-mode \
    --delimiter-hex "00000000" \
    --window-size 1 \
    --stats-format json \
    --quiet 2>&1 | \
    jq '.statistics'
```

Statistics reveal how many repeated structures exist.

## Advanced Patterns

### Multi-Block Sequences

Find repeated allocation patterns:

```bash
# Detect sequences of 3 consecutive blocks
uniqseq memory-dump.bin \
    --byte-mode \
    --delimiter-hex ff \
    --window-size 3 \
    --annotate | \
    grep "DUPLICATE"
```

Identifies repeated multi-block patterns (e.g., object hierarchies).

### Variable Data Normalization

Normalize pointers before comparison:

```bash
# Replace 8-byte pointers with placeholder
uniqseq memory.bin \
    --byte-mode \
    --delimiter-hex 00 \
    --hash-transform 'sed "s/\x00\x00\x00\x00\x7f\x00\x00\x00/XXXXXXXX/g"' \
    --quiet
```

Groups structures with different pointer values but identical layout.

### Save Unique Blocks

Build library of unique memory structures:

```bash
# Extract unique blocks to library
uniqseq memory-dump.bin \
    --byte-mode \
    --delimiter-hex ff \
    --library-dir ./unique-structures \
    --quiet > /dev/null

# Each file in library is a unique block
ls -lh unique-structures/
```

### Compare Memory Snapshots

Detect new allocations between snapshots:

```bash
# Baseline: Deduplicate snapshot 1
uniqseq snapshot1.bin --byte-mode --delimiter-hex ff \
    --library-dir ./baseline --quiet > /dev/null

# Analysis: Find new blocks in snapshot 2
uniqseq snapshot2.bin --byte-mode --delimiter-hex ff \
    --library-dir ./baseline --annotate | \
    grep "NEW PATTERN"
```

Shows memory blocks allocated between snapshots.

## Forensics Use Cases

### Credential Extraction

Find repeated credential structures:

```bash
# Extract blocks matching credential patterns
uniqseq memory.dmp --byte-mode --delimiter-hex 00 --quiet | \
    strings | \
    grep -E "(password|token|key)" | \
    uniq
```

### Rootkit Detection

Identify injected code patterns:

```bash
# Compare process memory against known clean state
uniqseq suspicious-process.dmp \
    --byte-mode --delimiter-hex ff \
    --library-dir ./clean-baseline \
    --inverse | \  # Show only known patterns
    wc -l
```

Low match count indicates many unknown blocks (possible injection).

### Memory Leak Analysis

Track repeated object allocations:

```bash
#!/bin/bash
# Analyze memory leaks

for snapshot in snapshot-*.bin; do
    echo "=== $snapshot ==="
    uniqseq "$snapshot" --byte-mode --delimiter-hex 00 \
        --stats-format json --quiet 2>&1 | \
        jq -r '.statistics |
            "Unique blocks: \(.lines.emitted)
             Duplicate blocks: \(.lines.skipped)
             Redundancy: \(.redundancy_pct)%"'
done
```

Increasing duplicate count over time may indicate memory leak.

### Binary Diff for Firmware

Compare firmware versions:

```bash
# Extract unique blocks from firmware v1
uniqseq firmware-v1.bin --byte-mode --delimiter-hex ff \
    --library-dir ./v1-blocks --quiet > /dev/null

# Find differences in firmware v2
uniqseq firmware-v2.bin --byte-mode --delimiter-hex ff \
    --library-dir ./v1-blocks --annotate | \
    grep "NEW PATTERN" > firmware-changes.txt

# Analyze what changed
wc -l firmware-changes.txt
```

## Performance Benefits

### Reduced Analysis Time

```bash
# Before: Analyze full memory dump
$ time strings memory-full.dmp | wc -l
real    0m45.2s
12,450,000 strings

# After: Analyze deduplicated dump
$ time uniqseq memory-full.dmp --byte-mode --delimiter-hex 00 --quiet |
    strings | wc -l
real    0m15.8s  # 3× faster
4,150,000 strings (67% reduction)
```

### Storage Savings

```bash
# Original dump
$ ls -lh process-dump.bin
2.4G

# Deduplicated
$ uniqseq process-dump.bin --byte-mode --delimiter-hex ff --quiet | wc -c
805306368  # 768 MB → 68% reduction
```

## Common Delimiters

| Delimiter | Use Case | Example |
|-----------|----------|---------|
| `0x00` | Null-terminated strings | C strings, paths |
| `0xFF` | Memory padding/alignment | Heap allocations |
| `0x00000000` | 4-byte aligned structures | 32-bit pointers |
| `0x0000000000000000` | 8-byte aligned structures | 64-bit pointers |
| `0xCC` | Debug fill pattern | MSVC debug heap |
| `0xCD` | Uninitialized memory | MSVC runtime |

### Detecting the Right Delimiter

```bash
# Find most common byte value (likely delimiter)
xxd -p memory.bin | \
    fold -w2 | \
    sort | \
    uniq -c | \
    sort -rn | \
    head -5
```

## Integration Examples

### Volatility Plugin

```bash
# Extract process memory with Volatility
volatility -f memory.dmp --profile=Win10x64 memdump -p $PID -D ./dumps

# Deduplicate for analysis
for dump in dumps/*.dmp; do
    uniqseq "$dump" --byte-mode --delimiter-hex ff \
        --quiet > "dedup/$(basename $dump)"
done
```

### radare2 Analysis

```bash
# Load deduplicated binary in radare2
uniqseq firmware.bin --byte-mode --delimiter-hex 00 --quiet > firmware-dedup.bin

r2 -a arm -b 32 firmware-dedup.bin
# Analyze with /x, afl, pdf commands
```

### Binary Ninja

<!-- skip: next -->
```python
# Python script for Binary Ninja
from uniqseq import UniqSeq

# Deduplicate before loading
uniqseq = UniqSeq(delimiter=b"\xff")
with open("large-firmware.bin", "rb") as f:
    with open("firmware-dedup.bin", "wb") as out:
        data = f.read()
        for block in data.split(b'\xff'):
            if block:
                uniqseq.process_line(block, out)
                uniqseq.process_line(b'\xff', out)
        uniqseq.flush(out)

# Load deduplicated firmware in Binary Ninja
bv = binaryninja.open_view("firmware-dedup.bin")
```

## When to Use This

**Good candidates:**
- ✅ Memory dumps with repeated allocations
- ✅ Firmware images with string tables
- ✅ Process heap analysis for malware
- ✅ Rootkit detection (compare against baseline)
- ✅ Memory leak investigation

**Not recommended:**
- ❌ Encrypted memory regions
- ❌ Compressed firmware images
- ❌ Small dumps (<10 MB)
- ❌ Heavily obfuscated malware

## See Also

- [Byte Mode](../../features/byte-mode/byte-mode.md) - Binary data processing
- [Custom Delimiters](../../features/delimiters/delimiters.md) - Delimiter configuration
- [Library Mode](../../features/library-dir/library-dir.md) - Saving unique blocks
- [Network Capture](./network-capture.md) - Binary protocol analysis
