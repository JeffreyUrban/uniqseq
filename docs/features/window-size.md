# Feature: --window-size

Detect and remove repeated sequences of multiple consecutive lines.

## What It Does

By default, uniqseq detects repeated single lines. With `--window-size N`, it detects repeated sequences of N consecutive lines.

## Simple Example

=== "Input"

    ```text
    A
    B
    C
    A
    B
    C
    D
    ```

=== "Output (--window-size 1, default)"

    ```text
    A
    B
    C
    D
    ```
    Individual lines deduplicated

=== "Output (--window-size 3)"

    ```text
    A
    B
    C
    D
    ```
    The 3-line sequence A-B-C removed as a unit

## How It Works

With `--window-size 3`, uniqseq checks each 3-line sliding window:

```text
Lines 1-3: A / B / C  → First occurrence (kept)
Lines 2-4: B / C / A  → Unique (kept)
Lines 3-5: C / A / B  → Unique (kept)
Lines 4-6: A / B / C  → MATCH with lines 1-3 (removed!)
```

## Usage

=== "CLI"

    <!-- termynal -->
    ```console
    $ printf "A\nB\nC\nA\nB\nC\nD\n" | uniqseq --window-size 3 --quiet
    A
    B
    C
    D
    ```

=== "Python"

    ```python
    from io import StringIO
    from uniqseq import StreamingDeduplicator

    dedup = StreamingDeduplicator(window_size=3)

    lines = ["A", "B", "C", "A", "B", "C", "D"]

    output = StringIO()
    for line in lines:
        dedup.process_line(line, output)
    dedup.flush(output)

    print(output.getvalue())
    # Output:
    # A
    # B
    # C
    # D
    ```

## Common Use Cases

- **Stack traces**: Multi-line error traces (typically 3-10 lines)
- **Test output**: Setup/test/teardown sequences
- **Log patterns**: Multi-line request/response logs
- **Git conflicts**: Repeated conflict markers with context

## Tips

!!! tip "Choosing Window Size"
    Set window-size to the number of lines in your repeated pattern:
    - Stack trace: 3-5 lines → `--window-size 3`
    - HTTP request/response: 10 lines → `--window-size 10`
    - Test suite: 20 lines → `--window-size 20`

!!! tip "Window Size 1 is Default"
    `uniqseq` without `--window-size` is equivalent to `uniqseq --window-size 1`

!!! warning "Lines Must Be Consecutive"
    The N lines must appear together both times. If there's a different line between them, it won't match.
