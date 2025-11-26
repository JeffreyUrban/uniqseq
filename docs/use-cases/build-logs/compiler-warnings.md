# Build Logs: Deduplicating Compiler Warnings

Large C++ projects often generate hundreds of repeated compiler warnings across multiple build targets. Remove duplicate warning sequences to identify unique issues that need attention.

## The Problem

Modern C++ builds compile the same headers repeatedly across different translation units, producing identical warnings multiple times. This makes it difficult to:

- **Count unique warnings** - Same warning repeated 50 times looks like 50 issues
- **Prioritize fixes** - Can't tell which warnings are most common
- **Track progress** - Hard to see if warning count is actually decreasing

## Input Data

???+ note "build.log"
    ```hl_lines="1-3 13-15 4-6 16-18 7-9 21-23"
    --8<-- "use-cases/build-logs/fixtures/build.log"
    ```

    The build log shows **8 warnings**, but only **4 are unique**:

    - Lines 1-3 and 13-15: `unused variable 'token'` (appears 2×)
    - Lines 4-6 and 16-18: `implicit conversion` (appears 2×)
    - Lines 7-9 and 19-21: `comparison of different signs` (appears 2×)
    - Lines 10-12 and 24-26: `variable is uninitialized` (appears 2×)

## Output Data

???+ success "expected-output.log"
    ```text hl_lines="1-3 4-6 7-9 10-12"
    --8<-- "use-cases/build-logs/fixtures/expected-output.log"
    ```

    **Result**: 12 duplicate lines removed → only unique warnings remain

## Solution

=== "CLI"

    <!-- verify-file: output.log expected: expected-output.log -->
    <!-- termynal -->
    ```console
    $ uniqseq build.log \
        --window-size 3 \
        --quiet > output.log
    ```

    **Options:**

    - `--window-size 3`: Match 3-line warning patterns (file:line + code + caret)
    - `--quiet`: Suppress statistics (keep only deduplicated warnings)

=== "Python"

    <!-- verify-file: output.log expected: expected-output.log -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,  # (1)!
    )

    with open("build.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Match 3-line warning sequences (each warning spans 3 lines)

## How It Works

Each compiler warning follows a consistent 3-line pattern:

```text
file.cpp:line:col: warning: message
    code snippet
           ^
```

By setting `--window-size 3`, uniqseq detects when this exact 3-line pattern repeats anywhere in the build log.

### Why This Matters

**Before deduplication:**
```text
$ grep "warning:" build.log | wc -l
8
```

**After deduplication:**
```text
$ grep "warning:" output.log | wc -l
4
```

**Impact**: Identify that you have **4 unique issues**, not 8. Fix these 4 warnings and eliminate all 8 occurrences.

## Real-World Workflow

### Build with Library Tracking

Track warnings across multiple builds to identify new issues:

```bash
# Build 1: Baseline
uniqseq build-001.log --window-size 3 --library-dir warnings-lib/ \
    > clean-001.log

# Build 2: After changes - loads existing warnings
uniqseq build-002.log --window-size 3 --library-dir warnings-lib/ \
    > clean-002.log
```

The library remembers all seen warnings. New warnings in build 2 will be kept, known warnings removed.

### Find New Warnings Only

Show only warnings NOT in the baseline:

```bash
# Create baseline from known warnings
uniqseq baseline.log --window-size 3 --library-dir baseline-lib/ > /dev/null

# Show only new warnings
uniqseq new-build.log \
    --window-size 3 \
    --read-sequences baseline-lib/sequences/ \
    --inverse > new-warnings-only.log
```

### CI Integration

Fail the build if new warnings are introduced:

```bash
#!/bin/bash
# Save known warnings to library
uniqseq build.log --window-size 3 --library-dir warnings-lib/ > clean.log

# Count new warnings discovered
NEW_WARNINGS=$(jq '.sequences_discovered' \
    warnings-lib/metadata-*/config.json | tail -1)

if [ "$NEW_WARNINGS" -gt 5 ]; then
    echo "ERROR: $NEW_WARNINGS new warnings introduced (max 5 allowed)"
    exit 1
fi
```

## See Also

- [Window Size](../../features/window-size/window-size.md) - How to choose the right window size
- [Pattern Libraries](../../features/library-dir/library-dir.md) - Tracking patterns across builds
- [Inverse Mode](../../features/inverse/inverse.md) - Finding only new patterns
