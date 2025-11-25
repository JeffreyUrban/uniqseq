# Byte Mode

The `--byte-mode` flag processes files in binary mode, handling data that may
contain null bytes, mixed character encodings, or invalid UTF-8 sequences.
This is essential for processing binary logs, protocol dumps, or files with
mixed encodings.

## What It Does

Byte mode changes how uniqseq reads and processes data:

- **Text mode** (default): Assumes valid UTF-8, reads files as text
- **Byte mode**: Reads files as binary, handles any byte sequence
- **Use case**: Binary logs, mixed encodings, null-terminated records

**Key insight**: Use byte mode when your data contains binary content or
when text mode fails with encoding errors.

## Example: Binary Log with Null Bytes

This example shows a log file where records contain null bytes (`\x00`)
embedded in the data. Text mode may fail or corrupt the data, but byte mode
handles it correctly.

???+ note "Input: Binary log with null bytes"
    ```text hl_lines="1-2 4-5"
    ERROR: Connection^@failed
      at database.connect()
    INFO: Retrying connection
    ERROR: Connection^@failed
      at database.connect()
    WARN: Max retries exceeded
    ```

    **Duplicate sequence** (lines 1-2 repeat as lines 4-5): Error with stack trace

    Note: `^@` represents a null byte (`\x00`) in the display

### Text Mode: May Fail

Without `--byte-mode`, files with null bytes may cause encoding errors:

```bash
# This may fail with encoding errors
uniqseq input.bin --window-size 2
# Error: UnicodeDecodeError: 'utf-8' codec can't decode...
```

**Result**: Processing fails or data is corrupted

### Byte Mode: Handles Binary Data

With `--byte-mode`, null bytes and other binary data are handled correctly:

=== "CLI"

    <!-- verify-file: output.bin expected: expected-output.bin -->
    <!-- termynal -->
    ```console
    $ uniqseq input.bin \
        --byte-mode \
        --window-size 2 \
        --quiet > output.bin
    ```

=== "Python"

    <!-- verify-file: output.bin expected: expected-output.bin -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=2,
        delimiter=b"\n"  # (1)!
    )

    with open("input.bin", "rb") as f:  # (2)!
        with open("output.bin", "wb") as out:
            for line in f:
                uniqseq.process_line(line.rstrip(b"\n"), out)
            uniqseq.flush(out)
    ```

    1. Use bytes delimiter for binary mode (b"\n" instead of "\n")
    2. Open files in binary mode (`rb`, `wb`)

???+ success "Output: Deduplicated binary log"
    ```text hl_lines="1-2"
    ERROR: Connection^@failed
      at database.connect()
    INFO: Retrying connection
    WARN: Max retries exceeded
    ```

    **Result**: 2 duplicate lines removed (6 lines → 4 lines). The second
    error with stack trace was detected and removed.

## Example: Processing Hexdump Files

**Use case**: You have a network packet capture saved as hexdump text. The
trace contains repeated keepalive packets that clutter the analysis. You want
to remove the duplicate keepalives while preserving unique traffic.

### Network Trace with Repeated Keepalives

```bash
# 1. View your hexdump (shows hex + ASCII on right)
cat network-trace.hex
# 00000000: 4142 430a 4445 460a 4142 430a 4445 460a  ABC.DEF.ABC.DEF.
# 00000010: 4748 490a                                GHI.

# Input contains:
#   - ABC (keepalive packet)    ← appears twice
#   - DEF (keepalive packet)    ← appears twice
#   - GHI (real traffic)        ← unique

# 2. Convert hex to binary, remove duplicate keepalives, back to hex
xxd -r network-trace.hex | \
    uniqseq --byte-mode --window-size 2 | \
    xxd > network-trace-clean.hex

# 3. View cleaned trace - duplicate keepalives removed
cat network-trace-clean.hex
# 00000000: 4142 430a 4445 460a 4748 490a       ABC.DEF.GHI.

# Output contains:
#   - ABC (keepalive) - kept first occurrence
#   - DEF (keepalive) - kept first occurrence
#   - GHI (real traffic) - kept
```

**What happened**:
- Detected 2-line sequence (ABC, DEF) that repeated
- Removed the second occurrence of the keepalive pair
- Preserved unique traffic (GHI)

**Why this matters**: Network traces often contain hundreds of repeated
keepalive packets. Removing them makes it easier to focus on actual traffic
and reduces trace file size.

## How It Works

### Binary Mode Processing

```
Text Mode:              Byte Mode:
┌──────────────┐       ┌──────────────┐
│ Read as UTF-8│       │ Read as bytes│
│ May fail     │       │ Never fails  │
│ on null bytes│       │ (any bytes)  │
└──────────────┘       └──────────────┘
       │                      │
       ▼                      ▼
┌──────────────┐       ┌──────────────┐
│ Hash text    │       │ Hash bytes   │
│ strings      │       │ directly     │
└──────────────┘       └──────────────┘
```

### Delimiter Handling

In byte mode, use `--delimiter-hex` instead of `--delimiter`:

| Mode | Delimiter Flag | Example |
|------|----------------|---------|
| Text | `--delimiter "\n"` | Newline (default) |
| Text | `--delimiter ","` | Comma |
| Byte | `--delimiter-hex 0a` | Newline (0x0A) |
| Byte | `--delimiter-hex 00` | Null byte (0x00) |
| Byte | `--delimiter-hex 0d0a` | CRLF (0x0D 0x0A) |

**Example with null delimiter**:

```bash
# Process null-delimited records
uniqseq data.bin --byte-mode --delimiter-hex 00
```

## Common Use Cases

### Binary Log Files

```bash
# Process systemd journal export (null-delimited)
journalctl -o export | uniqseq --byte-mode --delimiter-hex 0a

# Process binary application logs
uniqseq app.binlog --byte-mode --window-size 5
```

### Mixed Encodings

```bash
# Handle files with mixed UTF-8 and Latin-1
uniqseq legacy.log --byte-mode --skip-chars 20

# Process logs from multiple sources with different encodings
cat *.log | uniqseq --byte-mode
```

### Protocol Dumps

```bash
# Deduplicate network protocol traces
uniqseq protocol.dump --byte-mode --window-size 10

# Process hex dumps with null-terminated records
xxd -r hexdump.txt | uniqseq --byte-mode --delimiter-hex 00
```

### Hexdump Format Inspection

When working with binary data, hexdump tools help visualize and verify
deduplication:

```bash
# View binary data before deduplication
xxd input.bin | head -20

# Deduplicate and inspect output in hex format
uniqseq input.bin --byte-mode --window-size 2 > output.bin
xxd output.bin

# Side-by-side comparison of input vs output
diff <(xxd input.bin) <(xxd output.bin)

# Convert hex dump back to binary, deduplicate, convert back to hex
xxd -r dump.hex | uniqseq --byte-mode | xxd > clean.hex
```

**Example workflow**:

```bash
# 1. Create binary test data with repeated sequences
printf '\x41\x42\x43\x0a\x41\x42\x43\x0a\x44\x45\x46\x0a' > test.bin

# 2. View as hexdump
xxd test.bin
# Output:
# 00000000: 4142 430a 4142 430a 4445 460a            ABC.ABC.DEF.

# 3. Deduplicate (remove second ABC sequence)
uniqseq test.bin --byte-mode --window-size 3 --quiet > clean.bin

# 4. Verify deduplicated output
xxd clean.bin
# Output:
# 00000000: 4142 430a 4445 460a                      ABC.DEF.

# 5. Compare sizes
ls -lh test.bin clean.bin
```

**Working with hexdump text format**:

```bash
# Convert text hexdump to binary, deduplicate, convert back
cat data.hex | xxd -r -p | uniqseq --byte-mode | xxd -p > clean.hex

# Process hexdump with addresses (canonical format)
xxd -r dump.txt | uniqseq --byte-mode --window-size 4 | xxd > clean.txt
```

## Combining with Other Features

### With Skip-Chars

```bash
# Skip binary header (first 4 bytes) before comparison
uniqseq data.bin --byte-mode --skip-chars 4 --window-size 3
```

### With Hash Transform

```bash
# Extract payload after binary header (skip first 4 bytes)
uniqseq data.bin --byte-mode \
    --hash-transform "tail -c +5" \
    --window-size 3
```

**Note**: Hash transform commands must handle binary data correctly.
Use commands like `tail -c`, `head -c`, `cut -b` for binary-safe processing.

## Limitations

### Incompatible with Text Features

The following features require text mode and cannot be used with `--byte-mode`:

- **Pattern filtering** (`--track`, `--bypass`): Requires regex on text
- **Text delimiters** (`--delimiter`): Use `--delimiter-hex` instead

**Example errors**:

```bash
# ERROR: Filter patterns require text mode
uniqseq data.bin --byte-mode --track "ERROR"

# ERROR: Use --delimiter-hex in byte mode
uniqseq data.bin --byte-mode --delimiter ","
```

### Output Handling

Byte mode output may contain non-printable characters:

```bash
# Redirect to file for safety
uniqseq data.bin --byte-mode > output.bin

# Use hexdump to inspect
xxd output.bin | less

# Use od for octal dump
od -c output.bin | less
```

## When to Use Byte Mode

**Use byte mode when:**
- Files contain null bytes or other binary data
- Working with mixed character encodings
- Processing binary protocols or dumps
- Text mode fails with encoding errors
- You need null-delimited records (`\0`)

**Use text mode (default) when:**
- Files are valid UTF-8 text
- You need pattern filtering (--track/--bypass)
- You want readable output
- Working with standard log files

## Performance Note

Byte mode has similar performance to text mode:
- No encoding/decoding overhead
- Direct binary comparison
- Same memory usage per line
- Slightly faster for binary data (no UTF-8 validation)

## See Also

- [Custom Delimiters](../delimiters/delimiters.md) - Using non-newline delimiters
- [Hash Transformations](../hash-transform/hash-transform.md) - Binary-safe commands
- [CLI Reference](../../reference/cli.md) - Complete byte-mode documentation
