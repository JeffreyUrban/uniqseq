# CI/CD: Cleaning Test Retry Output

CI pipelines often retry flaky tests multiple times, filling logs with duplicate failure messages. Remove duplicate test failures to see unique issues clearly.

## The Problem

Modern CI systems retry failed tests to handle transient failures. This creates verbose logs where the same test failure appears 3-5 times:

- **Obscures real issues** - Hard to see unique failures among retries
- **Slows log review** - Developers scroll past duplicate failures
- **Wastes storage** - Identical error traces repeated multiple times

## Input Data

???+ note "ci-output.log"
    ```hl_lines="2-4 9-11 15-17 5-7 13-14 18-20"
    --8<-- "use-cases/ci-cd/fixtures/ci-output.log"
    ```

    The test suite retries 2 failed tests 3 times each, producing:

    - **`test_authentication`** failure (lines 2-4, 9-11, 15-17) - appears 3×
    - **`test_user_profile`** failure (lines 5-7, 12-14, 18-20) - appears 3×

## Output Data

???+ success "expected-output.log"
    ```text hl_lines="2-4 5-7"
    --8<-- "use-cases/ci-cd/fixtures/expected-output.log"
    ```

    **Result**: Duplicate retry attempts removed → see each unique failure once

## Solution

=== "CLI"

    <!-- verify-file: output.log expected: expected-output.log -->
    <!-- termynal -->
    ```console
    $ uniqseq ci-output.log \
        --window-size 3 \
        --quiet > output.log
    ```

    **Options:**

    - `--window-size 3`: Match 3-line test failure patterns
    - `--quiet`: Suppress statistics

=== "Python"

    <!-- verify-file: output.log expected: expected-output.log -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,  # (1)!
    )

    with open("ci-output.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Match 3-line test failure sequences

## How It Works

Each test failure has a consistent 3-line format:

```text
✗ test_name [attempt N/3]
  Error message
  File location
```

With `--window-size 3`, uniqseq detects when this pattern repeats (even with different attempt numbers) and keeps only the first occurrence.

### Impact Analysis

**Before:**
```bash
$ grep "^✗" ci-output.log | wc -l
6    # 6 test failures (3 retries × 2 unique failures)
```

**After:**
```bash
$ grep "^✗" output.log | wc -l
2    # 2 unique failures
```

**67% reduction** in log size from removing retry duplicates.

## Real-World Workflow

### See What Was Deduplicated

Use `--annotate` to show where retries were removed:

```bash
uniqseq ci-output.log --window-size 3 --annotate
```

Output includes markers like:
```text
[DUPLICATE: Lines 9-11 matched lines 2-4 (sequence seen 2 times)]
```

### Track Flaky Tests

Use `--inverse` to see ONLY the retry attempts (what was deduplicated):

```bash
uniqseq ci-output.log --window-size 3 --inverse > retries-only.log
```

This shows which tests failed multiple times - potential flaky tests to investigate.

### Statistics Output

See deduplication metrics:

```bash
uniqseq ci-output.log --window-size 3
```

Shows:
```text
┌─────────────────────────────┬──────────┐
│ Total Records Processed     │ 21       │
│ Unique Records (kept)       │ 15       │
│ Duplicate Records (skipped) │ 6        │
│ Reduction                   │ 28.6%    │
└─────────────────────────────┴──────────┘
```

## See Also

- [Window Size](../../features/window-size/window-size.md) - Choosing the right window size
- [Annotations](../../features/annotations/annotations.md) - Marking removed duplicates
- [Inverse Mode](../../features/inverse/inverse.md) - Showing only duplicates
