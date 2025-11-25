# Custom Delimiters

The `--delimiter` and `--delimiter-hex` options allow using custom record separators instead of newlines. This enables deduplication of comma-separated values, null-terminated records, or any custom format.

## What It Does

Delimiters define record boundaries:

- **Default (newline)**: Records separated by `\n`
- **--delimiter TEXT**: Use custom text separator (e.g., `,` for CSV)
- **--delimiter-hex HEX**: Use binary separator (e.g., `00` for null bytes)
- **Use case**: Process non-line-oriented data formats

**Key insight**: Changing the delimiter changes what constitutes a "line" for deduplication purposes.

## Example: Comma-Separated Records

This example shows 20 comma-separated records where a 10-record sequence repeats. With newline delimiter, all records appear as one "line". With comma delimiter, records are properly separated.

???+ note "Input: Comma-separated records"
    ```text
    --8<-- "features/delimiters/fixtures/input.txt"
    ```

    **Pattern**: Records A-J, then A-J again (20 records total)

### With Default Newline Delimiter: No Deduplication

Without `--delimiter`, the entire input is treated as a single line. No deduplication occurs.

=== "CLI"

    <!-- verify-file: output-newline.txt expected: expected-newline.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 10 > output-newline.txt
    ```

=== "Python"

    <!-- verify-file: output-newline.txt expected: expected-newline.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=10,
        delimiter="\n"  # (1)!
    )

    with open("input.txt") as f:
        with open("output-newline.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Default: newline delimiter

???+ warning "Output: Everything kept (single line)"
    ```text
    --8<-- "features/delimiters/fixtures/expected-newline.txt"
    ```

    **Result**: All content kept. Input contains only one "line" (no newlines), so window size never reached.

### With Comma Delimiter: Duplicates Removed

With `--delimiter ","`, input is split into 20 records. The 10-record sequence A-J repeats, so the duplicate is removed.

=== "CLI"

    <!-- verify-file: output-comma.txt expected: expected-comma.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --delimiter "," --window-size 10 \
        > output-comma.txt
    ```

=== "Python"

    <!-- verify-file: output-comma.txt expected: expected-comma.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=10,
        delimiter=","  # (1)!
    )

    with open("input.txt") as f:
        content = f.read().strip()  # (2)!
        with open("output-comma.txt", "w") as out:
            for record in content.split(","):
                if record:  # Skip empty records
                    uniqseq.process_line(record, out)
            uniqseq.flush(out)
    ```

    1. Use comma as record separator
    2. Strip whitespace to avoid trailing newlines

???+ success "Output: Duplicate sequence removed"
    ```text
    --8<-- "features/delimiters/fixtures/expected-comma.txt"
    ```

    **Result**: Only 10 records remain (A-J). The duplicate 10-record sequence was removed.

## How It Works

### Record Splitting

Delimiters define how input is split into records:

```
Input: "A,B,C,D,E,F,G,H,I,J,A,B,C,D,E,F,G,H,I,J"

Default delimiter (\n):
  → 1 record: "A,B,C,D,E,F,G,H,I,J,A,B,C,D,E,F,G,H,I,J"

Comma delimiter (,):
  → 20 records: ["A", "B", "C", ..., "J", "A", "B", ..., "J"]

Window size 10:
  → First window: [A, B, C, D, E, F, G, H, I, J]
  → Second window: [A, B, C, D, E, F, G, H, I, J] (duplicate!)
```

Deduplication operates on records, not bytes. The delimiter defines record boundaries.

## Common Use Cases

### CSV/TSV Files

```bash
# Comma-separated values
uniqseq data.csv --delimiter "," --window-size 5

# Tab-separated values
uniqseq data.tsv --delimiter $'\t' --window-size 5
```

### Null-Terminated Records

```bash
# Process find output
find /path -type f -print0 | uniqseq --delimiter-hex 00 --window-size 3

# Null-separated records in file
uniqseq records.dat --delimiter $'\0' --window-size 5

# Binary mode with hex delimiter
uniqseq binary.dat --byte-mode --delimiter-hex 00 --window-size 5
```

### Custom Multi-Character Delimiters

```bash
# Triple-pipe separator
uniqseq log.txt --delimiter "|||" --window-size 3

# Custom record separator
uniqseq data.txt --delimiter "---END---" --window-size 5
```

### JSON Arrays

```bash
# Comma-separated JSON objects (one-per-line not required)
cat items.json | tr -d '\n' | uniqseq --delimiter "},{" --window-size 3
```

## Text vs Binary Mode

**Text mode** (default):
- Delimiters are strings
- Line-oriented processing
- Use `--delimiter` flag

```bash
uniqseq log.txt --delimiter ","
```

**Binary mode** (`--byte-mode`):
- Delimiters are byte sequences
- Binary-safe processing
- Use `--delimiter-hex` flag

```bash
uniqseq data.bin --byte-mode --delimiter-hex 00
```

## Delimiter Syntax

### Text Delimiters

```bash
# Single character
--delimiter ","

# Multiple characters
--delimiter "|||"

# Escape sequences (shell-dependent)
--delimiter $'\n'   # Newline (bash)
--delimiter $'\t'   # Tab (bash)
--delimiter $'\0'   # Null (bash)
```

### Hex Delimiters

```bash
# Null byte
--delimiter-hex 00

# Newline
--delimiter-hex 0a

# Carriage return + newline
--delimiter-hex 0d0a

# Custom byte sequence
--delimiter-hex 010203

# With 0x prefix (optional)
--delimiter-hex 0x00
```

**Requirements**:
- Even number of hex digits (each byte = 2 digits)
- Case insensitive (FF = ff)
- No spaces between bytes

## Choosing the Right Delimiter

### Match Your Data Format

Inspect your data to find the record separator:

```bash
# Show non-printable characters
cat -A file.txt

# Show hex dump
hexdump -C file.dat | head

# Count delimiters
grep -o "," file.csv | wc -l
```

### Common Patterns

| Format | Delimiter | Example |
|--------|-----------|---------|
| CSV | `--delimiter ","` | `value1,value2,value3` |
| TSV | `--delimiter $'\t'` | `col1\tcol2\tcol3` |
| find -print0 | `--delimiter-hex 00` | `file1\0file2\0file3` |
| Log records | `--delimiter "---"` | Custom separator |
| JSON array | `--delimiter "},{"`| Comma-separated objects |

## Rule of Thumb

**Use custom delimiters when your data uses non-newline record separators.**

- CSV/TSV: Use appropriate text delimiter
- Null-terminated: Use `--delimiter-hex 00`
- Custom format: Match the actual separator
- Binary data: Use `--byte-mode` with hex delimiter

## See Also

- [CLI Reference](../../reference/cli.md) - Complete delimiter documentation
- [Common Patterns](../../guides/common-patterns.md) - More delimiter examples
