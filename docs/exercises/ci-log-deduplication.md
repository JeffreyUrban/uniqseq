# Exercise: CI Build Log Deduplication

## Scenario

Your CI/CD pipeline is generating verbose logs with repeated error messages. You want to clean them up to focus on unique issues.

## Input Data

??? note "View [`fixtures/ci-build.log`](../examples/fixtures/ci-build.log)"
    ```text title="examples/fixtures/ci-build.log"
    --8<-- "examples/fixtures/ci-build.log"
    ```

## Exercise 1: Remove Repeated Error Sequences

**Goal**: Remove duplicate 3-line error traces (ignoring timestamps)

=== "Input"

    ```text
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

=== "Output"

    ```diff
      [2024-01-15 10:30:01] INFO: Starting build
      [2024-01-15 10:30:02] INFO: Running tests
      [2024-01-15 10:30:03] ERROR: Test failed: test_authentication
      [2024-01-15 10:30:03]   File "test_auth.py", line 42
      [2024-01-15 10:30:03]   AssertionError: Expected 200, got 401
      [2024-01-15 10:30:04] INFO: Retrying tests
    - [2024-01-15 10:30:05] ERROR: Test failed: test_authentication
    - [2024-01-15 10:30:05]   File "test_auth.py", line 42
    - [2024-01-15 10:30:05]   AssertionError: Expected 200, got 401
      [2024-01-15 10:30:06] INFO: Build failed
    ```

    **Result**: 3 duplicate lines removed

### Solution

=== "CLI"

    <!-- termynal -->
    ```console
    $ uniqseq ci-build.log --window-size 3 --skip-chars 21 --quiet  # (1)!
    [2024-01-15 10:30:01] INFO: Starting build
    [2024-01-15 10:30:02] INFO: Running tests
    [2024-01-15 10:30:03] ERROR: Test failed: test_authentication
    [2024-01-15 10:30:03]   File "test_auth.py", line 42
    [2024-01-15 10:30:03]   AssertionError: Expected 200, got 401
    [2024-01-15 10:30:04] INFO: Retrying tests
    [2024-01-15 10:30:06] INFO: Build failed
    ```

    1. `--window-size 3` detects 3-line repeated sequences; `--skip-chars 21` ignores timestamps

=== "Python"

    <!-- skip: next -->
    ```python
    from io import StringIO
    from uniqseq import StreamingDeduplicator

    dedup = StreamingDeduplicator(
        window_size=3,  # (1)!
        skip_chars=21   # (2)!
    )

    with open("ci-build.log") as f:
        output = StringIO()
        for line in f:
            dedup.process_line(line.rstrip("\n"), output)
        dedup.flush(output)

    print(output.getvalue())
    ```

    1. Match 3-line sequences
    2. Skip first 21 chars (timestamp)

## Exercise 2: Single-Line Deduplication with Timestamps

**Goal**: Remove duplicate single lines that differ only in timestamp

=== "Input"

    ```text
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

=== "Output"

    ```diff
      [2024-01-15 10:30:01] INFO: Starting build
      [2024-01-15 10:30:02] INFO: Running tests
      [2024-01-15 10:30:03] ERROR: Test failed: test_authentication
    - [2024-01-15 10:30:03]   File "test_auth.py", line 42
    - [2024-01-15 10:30:03]   AssertionError: Expected 200, got 401
      [2024-01-15 10:30:04] INFO: Retrying tests
    - [2024-01-15 10:30:05] ERROR: Test failed: test_authentication
    - [2024-01-15 10:30:05]   File "test_auth.py", line 42
    - [2024-01-15 10:30:05]   AssertionError: Expected 200, got 401
      [2024-01-15 10:30:06] INFO: Build failed
    ```

    **Result**: 5 duplicate lines removed (window-size 1, comparing after skipping timestamps)

### Solution

=== "CLI"

    <!-- termynal -->
    ```console
    $ uniqseq ci-build.log --skip-chars 21 --window-size 1 --quiet  # (1)!
    [2024-01-15 10:30:01] INFO: Starting build
    [2024-01-15 10:30:02] INFO: Running tests
    [2024-01-15 10:30:03] ERROR: Test failed: test_authentication
    [2024-01-15 10:30:03]   File "test_auth.py", line 42
    [2024-01-15 10:30:03]   AssertionError: Expected 200, got 401
    [2024-01-15 10:30:04] INFO: Retrying tests
    [2024-01-15 10:30:06] INFO: Build failed
    ```

    1. `--skip-chars 21` ignores first 21 characters (timestamp) when comparing

=== "Python"

    <!-- skip: next -->
    ```python
    from io import StringIO
    from uniqseq import StreamingDeduplicator

    dedup = StreamingDeduplicator(
        window_size=1,
        skip_chars=21  # (1)!
    )

    with open("ci-build.log") as f:
        output = StringIO()
        for line in f:
            dedup.process_line(line.rstrip("\n"), output)
        dedup.flush(output)

    print(output.getvalue())
    ```

    1. Skip first 21 chars (timestamp: `[2024-01-15 10:30:05] `)

## Visual Explanation: --skip-chars

```text
Line matching with --skip-chars 21:

[2024-01-15 10:30:03] ERROR: Test failed
└────────┬─────────┘ └──────────┬──────────┘
    skipped (21)         compared for matching

[2024-01-15 10:30:05] ERROR: Test failed
└────────┬─────────┘ └──────────┬──────────┘
    skipped (21)         compared for matching
                         ↓
                      Match found! → Second line removed
```

## Key Concepts

!!! tip "Window Size"
    Set `--window-size` to the number of consecutive lines in your repeated pattern.

!!! tip "Skip Characters"
    Use `--skip-chars` to ignore prefixes like timestamps or log levels when finding duplicates.

!!! warning "Timestamps Preserved"
    `--skip-chars` only affects **matching**, not **output**. Original lines (including timestamps) are written to output.
