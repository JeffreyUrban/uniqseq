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
    from uniqseq import StreamingDeduplicator

    dedup = StreamingDeduplicator(
        window_size=2,
        delimiter=b"\n"  # (1)!
    )

    with open("input.bin", "rb") as f:  # (2)!
        with open("output.bin", "wb") as out:
            for line in f:
                dedup.process_line(line.rstrip(b"\n"), out)
            dedup.flush(out)
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
