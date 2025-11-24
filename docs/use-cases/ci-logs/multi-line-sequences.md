# CI Build Logs: Removing Duplicate Error Traces

Your CI/CD pipeline generates verbose logs with repeated error messages during retries. Remove duplicate 3-line error traces to focus on unique issues.

## Input Data

!!! note "ci-build.log" open
    ```text hl_lines="3-5 7-9"
    [2024-01-15 10:30:01] INFO: Starting build
    [2024-01-15 10:30:02] INFO: Running tests
    [2024-01-15 10:30:03] ERROR: Test failed: test_authentication
    [2024-01-15 10:30:03]   File "test_auth.py", line 42
    [2024-01-15 10:30:03]   AssertionError: Expected 200, got 401
    [2024-01-15 10:30:04] INFO: Retrying tests
    [2024-01-15 10:30:05] ERROR: Test failed: test_authentication
    [2024-01-15 10:30:05]   File "test_auth.py", line 42
    [2024-01-15 10:30:05]   AssertionError: Expected 200, got 401
    [2024-01-15 10:30:06] INFO: Build failed
    ```

    Highlighted lines show both occurrences of the 3-line error trace.

## Output Data

!!! success "Output after deduplication" open
    ```text hl_lines="3-5"
    [2024-01-15 10:30:01] INFO: Starting build
    [2024-01-15 10:30:02] INFO: Running tests
    [2024-01-15 10:30:03] ERROR: Test failed: test_authentication
    [2024-01-15 10:30:03]   File "test_auth.py", line 42
    [2024-01-15 10:30:03]   AssertionError: Expected 200, got 401
    [2024-01-15 10:30:04] INFO: Retrying tests
    ```
    <div style="height: 1px; background: linear-gradient(to right, transparent, #e57373, transparent); margin: -16px 0;"></div>
    ```text
    [2024-01-15 10:30:06] INFO: Build failed
    ```

    **Result**: 3 duplicate lines removed, first occurrence kept

## Solution

=== "CLI"

    <!-- verify-file: output.log expected: expected-ci-build-output.log -->
    ```console
    $ uniqseq ci-build.log \
        --window-size 3 \
        --skip-chars 21 \
        --quiet > output.log
    ```

    **Options:**

    - `--window-size 3`: Match 3-line sequences
    - `--skip-chars 21`: Ignore timestamp prefix when comparing

=== "Python"

    ```python
    from io import StringIO
    from uniqseq import StreamingDeduplicator

    dedup = StreamingDeduplicator(
        window_size=3,  # (1)!
        skip_chars=21,  # (2)!
    )

    with open("docs/examples/fixtures/ci-build.log") as f:
        output = StringIO()
        for line in f:
            dedup.process_line(line.rstrip("\n"), output)
        dedup.flush(output)

    result = output.getvalue()
    assert len(result.strip().split("\n")) == 7  # 10 input - 3 duplicates
    ```

    1. Match 3-line sequences
    2. Skip first 21 chars (timestamp)

## How It Works

The timestamps differ (`10:30:03` vs `10:30:05`), so the lines aren't identical. We need:

1. **`--window-size 3`**: Detect that lines 3-5 and lines 7-9 are the same 3-line pattern
2. **`--skip-chars 21`**: Ignore the timestamp prefix `[2024-01-15 10:30:03] ` when comparing

### Visual Breakdown

```text
Line comparison with --skip-chars 21:

[2024-01-15 10:30:03] ERROR: Test failed: test_authentication
└────────┬─────────┘ └──────────────────┬─────────────────────┘
    skip (21)              compare this part

[2024-01-15 10:30:05] ERROR: Test failed: test_authentication
└────────┬─────────┘ └──────────────────┬─────────────────────┘
    skip (21)              compare this part
                                   ↓
                            Match found!
```
