# Feature: --skip-chars

Ignore a prefix when comparing lines for duplicates.

## What It Does

When lines have prefixes that change (like timestamps, line numbers, or log levels), `--skip-chars N` tells uniqseq to skip the first N characters when checking for duplicates.

!!! note "Output Preserves Original Lines"
    The skipped characters are only ignored for **matching** - the original full lines are written to output.

## Simple Example

=== "Input"

    ```text
    10:00 Started
    10:05 Started
    10:12 Request
    ```

=== "Output (without --skip-chars)"

    ```text
    10:00 Started
    10:05 Started  ← NOT removed (timestamps differ)
    10:12 Request
    ```

=== "Output (with --skip-chars 6)"

    ```text
    10:00 Started
    10:12 Request
    ```

## How It Works

```text
Matching with --skip-chars 6:

10:00 Started
└─┬─┘ └──┬────┘
 skip  compare

10:05 Started
└─┬─┘ └──┬────┘
 skip  compare
        ↓
   Match found! → Second line removed
```

## Usage

=== "CLI"

    <!-- termynal -->
    ```console
    $ printf "10:00 Started\n10:05 Started\n10:12 Request\n" | uniqseq --skip-chars 6 --quiet
    10:00 Started
    10:12 Request
    ```

=== "Python"

    ```python
    from io import StringIO
    from uniqseq import StreamingDeduplicator

    dedup = StreamingDeduplicator(skip_chars=6)

    lines = [
        "10:00 Started",
        "10:05 Started",
        "10:12 Request",
    ]

    output = StringIO()
    for line in lines:
        dedup.process_line(line, output)
    dedup.flush(output)

    print(output.getvalue())
    # Output:
    # 10:00 Started
    # 10:12 Request
    ```

## Common Use Cases

- **Timestamps**: Log files with `[2024-01-15 10:30:03]` prefixes
- **Line numbers**: Compiler output with `file.py:42:` prefixes
- **Log levels**: Messages with `INFO: ` or `ERROR: ` prefixes

## Tips

!!! tip "Calculating Skip Length"
    Count the characters you want to skip, including spaces:
    ```
    [2024-01-15 10:30:03] ERROR: Connection failed
    └────────┬─────────┘
         21 chars
    ```
    Use `--skip-chars 21`

!!! warning "All Lines Must Have Prefix"
    If some lines are shorter than N characters, they'll be treated as empty strings for matching purposes.
