# Data Processing: CSV Deduplication

Remove duplicate records from CSV files while preserving the first occurrence of each unique record.

## The Problem

CSV exports from databases or APIs often contain duplicate records due to:

- **Data sync issues** - Same records exported multiple times
- **Join operations** - SQL joins creating duplicate rows
- **Merge operations** - Combining files with overlapping data

Traditional tools like `sort | uniq` only work on complete lines, not custom delimiters.

## Input Data

???+ note "records.csv"
    ```csv hl_lines="1 6 2 7 3 8"
    --8<-- "use-cases/data-processing/fixtures/records.csv"
    ```

    The file contains **10 records**, but **3 are duplicates**:

    - `user_001` (lines 1 and 6)
    - `user_002` (lines 2 and 7)
    - `user_003` (lines 3 and 8)

## Output Data

???+ success "expected-output.csv"
    ```csv hl_lines="1-4"
    --8<-- "use-cases/data-processing/fixtures/expected-output.csv"
    ```

    **Result**: 3 duplicate records removed → 7 unique records

## Solution

=== "CLI"

    <!-- verify-file: output.csv expected: expected-output.csv -->
    <!-- termynal -->
    ```console
    $ cat records.csv | tr '\n' ',' | \
        uniqseq --delimiter ',' --quiet | \
        tr ',' '\n' > output.csv
    ```

    **How it works:**

    1. `tr '\n' ','` - Convert newlines to commas (make one line)
    2. `uniqseq --delimiter ','` - Deduplicate comma-separated records
    3. `tr ',' '\n'` - Convert commas back to newlines

=== "Python"

    <!-- verify-file: output.csv expected: expected-output.csv -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        delimiter=",",  # (1)!
    )

    from io import StringIO

    with open("records.csv") as f:
        # Convert file to single line with commas
        content = f.read().replace("\n", ",")

        # Process as comma-delimited stream
        output = StringIO()
        for record in content.split(","):
            if record:  # Skip empty
                uniqseq.process_line(record, output)
        uniqseq.flush(output)

        # Convert back to CSV format
        result = output.getvalue().replace(",", "\n")

        with open("output.csv", "w") as out:
            out.write(result)
    ```

    1. Use comma as the record delimiter instead of newline

## How It Works

By default, uniqseq treats newlines as record delimiters. For CSV:

1. **Convert format**: Transform CSV so each record becomes a "line" with `,` delimiter
2. **Deduplicate**: Use `--delimiter ','` to treat commas as record boundaries
3. **Restore format**: Convert back to standard CSV with newlines

### Alternative: Single-Line CSV

If your CSV is already single-line (one record per comma):

```bash
echo "A,B,C,D,A,B,C,E" | uniqseq --delimiter ',' --quiet
# Output: A,B,C,D,E
```

## Real-World Workflows

### TSV Files

For tab-separated values:

```bash
cat records.tsv | tr '\n' '\t' | \
    uniqseq --delimiter '\t' --quiet | \
    tr '\t' '\n' > output.tsv
```

### Multi-Column Deduplication

Deduplicate based on specific columns using `--hash-transform`:

```bash
# Deduplicate based on column 1 only (user ID)
cat records.csv | \
    uniqseq --hash-transform "cut -d',' -f1" \
           --quiet > output.csv
```

This keeps first occurrence of each unique user ID, even if other columns differ.

### Large Files

For files too large for memory, process in chunks:

```bash
split -l 10000 huge.csv chunk_
for file in chunk_*; do
    cat $file | tr '\n' ',' | \
        uniqseq --delimiter ',' --library-dir dedup-lib/ --quiet | \
        tr ',' '\n' >> output.csv
done
```

The library tracks seen records across chunks.

## See Also

- [Custom Delimiters](../../features/delimiters/delimiters.md) - Using different record separators
- [Hash Transform](../../features/hash-transform/hash-transform.md) - Column-specific deduplication
- [Pattern Libraries](../../features/library-dir/library-dir.md) - Processing large files in chunks
