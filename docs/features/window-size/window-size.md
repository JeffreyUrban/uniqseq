# Window Size

The `--window-size` parameter controls the minimum number of consecutive lines that must match to be considered a repeated sequence. This is the most fundamental parameter for controlling what uniqseq detects.

## What It Does

Window size determines how long a pattern must be before uniqseq considers it a sequence:

- **Smaller windows** (3-5 lines): Detects shorter repeating patterns
- **Larger windows** (10+ lines): Only detects longer repeating patterns
- **Default** (10 lines): Balanced for typical multi-line output

**Key insight**: Sequences shorter than the window size are **never detected as duplicates**, even if they repeat.

## Example: Test Retry Output

This example shows test output where a failed test gets retried. The same 4-line error message appears twice.

???+ note "Input: Test failure that gets retried"
    ```text hl_lines="1-4"
    --8<-- "features/window-size/fixtures/input.txt"
    ```

    **First occurrence** (lines 1-4): Initial test failure
    **Duplicate** (lines 8-11): Same error after retry

### Window Size 3: Detects the Duplicate

With `--window-size 3`, uniqseq can detect sequences as short as 3 lines. Since our 4-line error is longer than 3, it gets detected and removed.

=== "CLI"

    <!-- verify-file: output-w3.txt expected: expected-w3.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 > output-w3.txt
    ```

=== "Python"

    <!-- verify-file: output-w3.txt expected: expected-w3.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(window_size=3)  # (1)!

    with open("input.txt") as f:
        with open("output-w3.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Detect sequences of 3 or more lines

???+ success "Output: Duplicate removed"
    ```text hl_lines="1-4"
    --8<-- "features/window-size/fixtures/expected-w3.txt"
    ```

    **Result**: The duplicate error (lines 8-12) was removed. Only the first occurrence remains, reducing output from 13 lines to 8 lines.

### Window Size 5: Still Detects It

With `--window-size 5`, the duplicate is still detected. Although the error itself is only 4 lines, each occurrence is followed by an empty line, creating matching 5-line windows at both positions (lines 1-5 and 8-12).

=== "CLI"

    <!-- verify-file: output-w5.txt expected: expected-w5.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 5 > output-w5.txt
    ```

=== "Python"

    <!-- verify-file: output-w5.txt expected: expected-w5.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(window_size=5)  # (1)!

    with open("input.txt") as f:
        with open("output-w5.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Window size of 5 lines

???+ success "Output: Same result"
    ```text hl_lines="1-5"
    --8<-- "features/window-size/fixtures/expected-w5.txt"
    ```

    **Result**: Same as window size 3 - the duplicate was removed because both 5-line windows (including the empty line) match.

### Window Size 10: Misses It

With `--window-size 10`, the 5-line windows are too short to form a complete match. No duplicates are detected.

=== "CLI"

    <!-- verify-file: output-w10.txt expected: expected-w10.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 10 > output-w10.txt
    ```

=== "Python"

    <!-- verify-file: output-w10.txt expected: expected-w10.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(window_size=10)  # (1)!

    with open("input.txt") as f:
        with open("output-w10.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Default: detect sequences of 10 or more lines

???+ success "Output: No duplicates removed"
    ```text hl_lines="1-5 8-12"
    --8<-- "features/window-size/fixtures/expected-w10.txt"
    ```

    **Result**: All 13 lines kept - the 5-line windows are too short to match a 10-line window requirement.

## How It Works

### The Sliding Window

uniqseq uses a **sliding window** that moves through your input one line at a time. Here's how it would process our test retry example with a 5-line window:

```
Window size 5, processing line by line:

Position 1-5 (first window includes error + empty line):
┌──────────────────────────────────┐
│ FAIL: test_authentication       │
│   File "tests/auth.py", line 42  │
│     assert response.status...    │
│ AssertionError: Expected 200...  │
│ (empty line)                     │
└──────────────────────────────────┘
→ Hash this window, record position 1

Position 2-6:
     FAIL: test_authentication
┌──────────────────────────────────┐
│   File "tests/auth.py", line 42  │  ← Window slides down
│     assert response.status...    │
│ AssertionError: Expected 200...  │
│ (empty line)                     │
│ Retrying failed test...          │
└──────────────────────────────────┘
→ Hash differs, keep sliding...

Position 8-12 (duplicate + empty line):
┌──────────────────────────────────┐
│ FAIL: test_authentication       │  ← Check hash
│   File "tests/auth.py", line 42  │    Match found!
│     assert response.status...    │    (same as position 1)
│ AssertionError: Expected 200...  │
│ (empty line)                     │
└──────────────────────────────────┘
→ Duplicate detected! Skip these 5 lines
```

When the window at position 8 matches the window we saw at position 1, uniqseq knows lines 8-12 are a duplicate and skips them.

### Why Window Size Matters

**Window size defines the minimum detectable pattern length:**

- A sequence **can** be detected if it contains at least `window_size` matching lines
- A sequence **cannot** be detected if it's shorter than `window_size`
- The window must fit completely within the matching region

In our example:
- Lines 1-5 match lines 8-12 (5-line windows including empty lines)
- Window size 3, 4, or 5: ✅ Detects the duplicate (window fits within the 5-line match)
- Window size 10: ❌ Misses the duplicate (window is larger than the 5-line match)

## Choosing the Right Window Size

### Too Small (e.g., 1-2 lines)

```bash
uniqseq log.txt --window-size 1
```

- ✅ Catches even single-line duplicates
- ⚠️ May remove lines you want to keep
- ⚠️ More false positives

### Just Right (e.g., 3-10 lines)

```bash
uniqseq log.txt --window-size 5
```

- ✅ Matches typical pattern lengths
- ✅ Good balance of detection vs preservation
- ✅ Recommended starting point

### Too Large (e.g., 20+ lines)

```bash
uniqseq log.txt --window-size 20
```

- ✅ Very conservative - only large patterns
- ⚠️ Misses shorter duplicates
- ⚠️ May not detect anything

## Rule of Thumb

**Set window size to the shortest pattern you want to remove.**

- 3-line error messages → `--window-size 3`
- 5-line stack traces → `--window-size 5`
- 10-line test output → `--window-size 10` (default)
- 20-line verbose blocks → `--window-size 20`

## See Also

- [Choosing Window Size Guide](../../guides/choosing-window-size.md) - Detailed guide for selecting optimal window size
- [CLI Reference](../../reference/cli.md) - Complete `--window-size` documentation
- [Basic Concepts](../../getting-started/basic-concepts.md) - Understanding sequences
- [Algorithm Details](../../about/algorithm.md) - How the sliding window works
