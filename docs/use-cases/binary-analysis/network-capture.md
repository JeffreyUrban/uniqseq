# Binary Analysis: Network Protocol Capture

Deduplicate binary network captures to identify unique protocol messages and reduce storage for packet analysis workflows.

## The Problem

Network packet captures contain massive amounts of repeated data:

- **Protocol handshakes repeat** - Same TCP/TLS setup sequences
- **Keepalive messages** - Repeated heartbeat packets
- **Duplicate requests** - Load balancers sending identical probes
- **Large capture files** - Gigabytes of pcap data with high redundancy

**Binary deduplication** can significantly reduce capture file sizes for analysis and storage.

## Input Data

???+ note "network-capture.bin"
    Binary file containing **6 network packets** (445 bytes):

    - 3× HTTP GET requests (identical)
    - 2× HTTP POST requests (identical)
    - 1× HTTP Response (unique)

    Packets delimited by null bytes (`0x00`).

    **Hex dump (first 20 lines)**:
    ```text
    00000000: 3200 0147 4554 202f 6170 692f 7573 6572  2..GET /api/user
    00000010: 7320 4854 5450 2f31 2e31 0d0a 486f 7374  s HTTP/1.1..Host
    00000020: 3a20 6170 692e 6578 616d 706c 652e 636f  : api.example.co
    00000030: 6d0d 0a0d 0a00 6400 0250 4f53 5420 2f61  m.....d..POST /a
    ...
    ```

    **Packet structure**:
    ```
    [length:2][type:1][HTTP data][0x00 delimiter]
    ```

## Output Data

???+ success "expected-output.bin"
    Deduplicated binary file with **3 unique packets** (235 bytes):

    - 1× HTTP GET (2 duplicates removed)
    - 1× HTTP POST (1 duplicate removed)
    - 1× HTTP Response (kept)

    **Result**: **47% size reduction** (445 → 235 bytes)

## Solution

=== "CLI"

    <!-- verify-file: output.bin expected: expected-output.bin -->
    <!-- termynal -->
    ```console
    $ uniqseq network-capture.bin \
        --byte-mode \
        --delimiter-hex 00 \
        --window-size 1 \
        --quiet > deduplicated.bin
    ```

    **Options:**

    - `--byte-mode`: Process binary data (not text lines)
    - `--delimiter-hex 00`: Split on null byte (0x00) instead of newline
    - `--window-size 1`: Deduplicate individual packets
    - `--quiet`: Suppress statistics output

=== "Python"

    <!-- verify-file: output.bin expected: expected-output.bin -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        delimiter=b"\x00",    # (1)!
        window_size=1,        # (2)!
    )

    with open("network-capture.bin", "rb") as f:
        with open("output.bin", "wb") as out:
            data = f.read()
            # Split on delimiter, keeping empty chunks (consecutive delimiters)
            chunks = data.split(b'\x00')
            # Process all but last chunk (last is after trailing delimiter)
            for chunk in chunks[:-1]:
                uniqseq.process_line(chunk, out)
            # Process last chunk if non-empty
            if chunks[-1]:
                uniqseq.process_line(chunks[-1], out)
            uniqseq.flush(out)
    ```

    1. Use bytes delimiter for binary mode
    2. Deduplicate individual packets

## How It Works

Byte mode processes binary data using custom delimiters instead of text newlines:

```text
Before (6 packets, 445 bytes):
[GET packet #1]  <-- Keep
[POST packet #1] <-- Keep
[GET packet #2]  <-- Duplicate, remove
[Response #1]    <-- Keep (unique)
[POST packet #2] <-- Duplicate, remove
[GET packet #3]  <-- Duplicate, remove

After (3 packets, 235 bytes):
[GET packet]
[POST packet]
[Response]
```

Each packet is hashed and compared, with duplicates removed.

## Real-World Workflows

### Deduplicate tcpdump Output

Reduce pcap file size for analysis:

```bash
# Convert pcap to binary stream, deduplicate
tcpdump -r capture.pcap -w - | \
    uniqseq --byte-mode --delimiter-hex 0a --quiet | \
    tcpdump -r - -w deduplicated.pcap
```

### Protocol Message Analysis

Extract unique protocol messages from network logs:

```bash
# Deduplicate binary protocol logs
uniqseq protocol.bin \
    --byte-mode \
    --delimiter-hex 00 \
    --window-size 1 \
    --quiet > unique-messages.bin

# Analyze unique messages
hexdump -C unique-messages.bin | less
```

### Find Repeated Heartbeats

Identify and remove keepalive packets:

```bash
# Show how many duplicates were removed
uniqseq capture.bin \
    --byte-mode \
    --delimiter-hex 00 \
    --stats-format json \
    --quiet 2>&1 | \
    jq '.statistics.lines.skipped'
```

Output: `150` (150 duplicate packets removed)

### DNS Query Deduplication

Deduplicate DNS query logs:

```bash
# DNS messages use length prefixes, delimited by custom markers
uniqseq dns-queries.bin \
    --byte-mode \
    --delimiter-hex 0a \
    --window-size 1 \
    --quiet > unique-dns-queries.bin
```

### HTTP/2 Frame Analysis

Analyze HTTP/2 binary frames:

```bash
# HTTP/2 frames delimited by frame boundaries
uniqseq http2-frames.bin \
    --byte-mode \
    --delimiter-hex 00 \
    --window-size 3 \
    --quiet > unique-http2-sequences.bin
```

Use `--window-size 3` to capture frame sequences (request → response → ack).

## Advanced Patterns

### Multi-Packet Sequences

Deduplicate conversation patterns (multi-packet windows):

```bash
# Find unique 3-packet sequences
uniqseq network-capture.bin \
    --byte-mode \
    --delimiter-hex 00 \
    --window-size 3 \
    --quiet
```

Identifies unique request/response/acknowledgment patterns.

### Protocol Normalization

Normalize variable fields before deduplication:

```bash
# Remove timestamps from packets before comparing
uniqseq capture.bin \
    --byte-mode \
    --delimiter-hex 00 \
    --hash-transform 'sed "s/timestamp=[0-9]*/timestamp=XXX/g"' \
    --quiet
```

Groups packets with different timestamps but identical structure.

### Hex Delimiter Discovery

Find the right delimiter for your binary format:

```bash
# Try different delimiters
for delim in 00 0a 0d 1a ff; do
    echo "Delimiter: 0x$delim"
    uniqseq data.bin --byte-mode --delimiter-hex $delim --quiet | wc -c
done
```

Choose the delimiter that produces the most logical chunk sizes.

### Save Binary Statistics

Track deduplication metrics for binary data:

```bash
# Process binary capture with stats
uniqseq network.pcap \
    --byte-mode \
    --delimiter-hex 00 \
    --stats-format json \
    --quiet \
    > deduplicated.pcap \
    2> capture-stats.json

# Check compression ratio
jq '.statistics.redundancy_pct' capture-stats.json
```

## Performance Benefits

### Storage Reduction

```bash
# Before deduplication
$ ls -lh network-capture.bin
445 bytes

# After deduplication
$ ls -lh deduplicated.bin
235 bytes  # 47% reduction
```

For real packet captures with repeated handshakes and keepalives, **60-80% reduction** is common.

### Faster Analysis

```bash
# Time to search through full capture
$ time grep -a "GET" network-capture.bin
real    0m0.050s

# Time to search through deduplicated capture
$ time grep -a "GET" deduplicated.bin
real    0m0.025s  # 50% faster
```

## Binary Data Formats

### Common Use Cases

| Protocol | Delimiter | Window Size | Use Case |
|----------|-----------|-------------|----------|
| HTTP packets | `0x00` or `0x0a` | 1 | Deduplicate requests |
| DNS queries | `0x0a` | 1 | Unique query patterns |
| TLS handshakes | `0x00` | 3-5 | Handshake sequences |
| Custom protocols | Variable | 1-3 | Protocol-specific |
| Binary logs | `0x0a` or `0x00` | 1 | Application logs |

### Delimiter Selection

**Common binary delimiters**:
- `0x00` (null byte) - C-style string termination
- `0x0a` (newline) - Line-oriented binary
- `0x0d0a` (CRLF) - Network protocols
- `0x1a` (EOF marker) - Some file formats
- `0xff` (all bits set) - Custom protocols

### Working with pcap Files

For pcap files, you may need preprocessing:

```bash
# Extract payloads from pcap
tcpdump -r capture.pcap -w - -x | \
    # Process hex output
    grep "0x" | \
    # Convert to binary
    xxd -r -p | \
    # Deduplicate
    uniqseq --byte-mode --delimiter-hex 00 --quiet
```

## Integration Examples

### Wireshark Workflow

```bash
# Export packets from Wireshark
tshark -r capture.pcap -T fields -e frame.protocols > packets.txt

# Deduplicate protocol sequences
uniqseq packets.txt --window-size 3 --quiet > unique-conversations.txt
```

### Zeek (Bro) Logs

```bash
# Deduplicate Zeek binary logs
uniqseq conn.log \
    --byte-mode \
    --delimiter-hex 0a \
    --quiet > conn-deduped.log
```

### Custom Protocol Analysis

<!-- skip: next -->
```python
from uniqseq import UniqSeq

# Analyze custom binary protocol
uniqseq = UniqSeq(delimiter=b"\xff", window_size=1)

with open("protocol.bin", "rb") as f:
    with open("unique-messages.bin", "wb") as out:
        data = f.read()
        for packet in data.split(b'\xff'):
            if len(packet) > 0:
                uniqseq.process_line(packet, out)
                uniqseq.process_line(b'\xff', out)
        uniqseq.flush(out)

# Print statistics
stats = uniqseq.get_stats()
print(f"Unique packets: {stats['emitted']}")
print(f"Duplicate packets removed: {stats['skipped']}")
```

## When to Use This

**Good candidates:**
- ✅ Network captures with repeated handshakes
- ✅ Protocol dumps with keepalive messages
- ✅ Binary log files with structured data
- ✅ IoT device communication logs
- ✅ Game network traffic analysis

**Not recommended:**
- ❌ Encrypted traffic (all bytes appear random)
- ❌ Compressed binary data (low entropy)
- ❌ Random data / cryptographic material
- ❌ Small binary files (<1KB)

## See Also

- [Byte Mode](../../features/byte-mode/byte-mode.md) - Binary data processing
- [Custom Delimiters](../../features/delimiters/delimiters.md) - Delimiter configuration
- [Window Size](../../features/window-size/window-size.md) - Multi-packet sequences
- [Memory Forensics](./memory-forensics.md) - Binary memory dump analysis
