# CI Build Logs: Removing Duplicate Error Traces

Your CI/CD pipeline generates verbose logs with repeated error messages during retries. Remove duplicate 3-line error traces to focus on unique issues.

## Input Data

???+ note "ci-build.log"
    ```hl_lines="3-5 7-9"
    --8<-- "use-cases/ci-logs/fixtures/ci-build.log"
    ```

    Highlighted lines show both occurrences of the 3-line error trace.

## Output Data

???+ success "output.log"
    ```text hl_lines="3-5"
    --8<-- "use-cases/ci-logs/fixtures/expected-output.log"
    ```

    **Result**: 3 duplicate lines removed, first occurrence kept

## Solution

=== "CLI"

    <!-- verify-file: output.log expected: expected-output.log -->
    <!-- termynal -->
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

    <!-- verify-file: output.log expected: expected-output.log -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,  # (1)!
        skip_chars=21,  # (2)!
    )

    with open("ci-build.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
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
