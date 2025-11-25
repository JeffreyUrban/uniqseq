# History Management

The `--max-history` and `--unlimited-history` options control how many window hashes uniqseq remembers. This determines how far back in the input it can detect duplicates.

## What It Does

History depth controls the deduplication memory:

- **Limited history** (`--max-history N`): Remembers last N window hashes
- **Unlimited history** (`--unlimited-history`): Remembers all window hashes
- **Default**: File input uses unlimited; stdin uses 100,000

**Key insight**: When history is full, the oldest entries are evicted. Duplicates of evicted sequences won't be detected.

## Example: Long-Running Log Analysis

This example shows log entries where an error appears early, then many other log entries appear, then the same error repeats. With limited history, the early error is forgotten.

???+ note "Input: Error appears early and late"
    ```text hl_lines="1-3 16-18"
    --8<-- "features/history/fixtures/input.txt"
    ```

    **First occurrence** (lines 1-3): Database error
    **Many intermediate entries** (lines 4-15): Various log messages
    **Duplicate** (lines 16-18): Same database error

### Limited History: Misses the Duplicate

With `--max-history 5`, only the 5 most recent window hashes are kept. When the duplicate error appears, the original error's hashes have been evicted from history.

=== "CLI"

    <!-- verify-file: output-limited.txt expected: expected-limited.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 --max-history 5 > output-limited.txt
    ```

=== "Python"

    <!-- verify-file: output-limited.txt expected: expected-limited.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,
        max_history=5  # (1)!
    )

    with open("input.txt") as f:
        with open("output-limited.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Very small history - only remembers 5 window hashes

???+ warning "Output: Duplicate NOT removed"
    ```text hl_lines="1-3 16-18"
    --8<-- "features/history/fixtures/expected-limited.txt"
    ```

    **Result**: All 23 lines kept. The duplicate error (lines 16-18) was NOT detected because the original error's hashes were evicted from the limited history.

### Unlimited History: Detects the Duplicate

With `--unlimited-history`, all window hashes are kept indefinitely. The duplicate error is detected no matter how far apart the occurrences are.

=== "CLI"

    <!-- verify-file: output-unlimited.txt expected: expected-unlimited.txt -->
    <!-- termynal -->
    ```console
    $ uniqseq input.txt --window-size 3 --unlimited-history \
        > output-unlimited.txt
    ```

=== "Python"

    <!-- verify-file: output-unlimited.txt expected: expected-unlimited.txt -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,
        max_history=None  # (1)!
    )

    with open("input.txt") as f:
        with open("output-unlimited.txt", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Unlimited history - remembers all window hashes

???+ success "Output: Duplicate removed"
    ```text hl_lines="1-3"
    --8<-- "features/history/fixtures/expected-unlimited.txt"
    ```

    **Result**: Only 20 lines. The duplicate error (lines 16-18) was detected and removed because unlimited history retained all window hashes.

## How It Works

### The History Window

uniqseq maintains a FIFO (first-in, first-out) history of window hashes:

```
Limited history (max_history=5):

Process lines 1-3 (first error):
  History: [hash-A]

Process lines 4-6 (cache warning):
  History: [hash-A, hash-B]

Process lines 7-9 (batch job):
  History: [hash-A, hash-B, hash-C]

Process lines 10-12 (memory debug):
  History: [hash-A, hash-B, hash-C, hash-D]

Process lines 13-15 (disk alert):
  History: [hash-A, hash-B, hash-C, hash-D, hash-E]
  ↓
  History is full (5 entries)

Process lines 16-18 (error again):
  Need to add hash-A, but history is full
  ↓
  Evict oldest: [hash-B, hash-C, hash-D, hash-E, hash-A]
  ↓
  hash-A not found in pre-eviction history!
  ↓
  Treated as NEW, not duplicate
```

With unlimited history, hash-A would still be in history when lines 16-18 are processed, so the duplicate would be detected.

### Memory Implications

**Limited history**:
- Memory usage: ~32 bytes × max_history
- Default 100,000: ~3.2 MB
- Suitable for: Streaming, real-time logs

**Unlimited history**:
- Memory usage: ~32 bytes × unique window hashes
- Grows with input diversity
- Suitable for: File processing, batch jobs

## Choosing the Right History Depth

### Default Behavior (Recommended)

```bash
# File input: Auto-detects unlimited history
uniqseq logfile.txt

# Stdin: Uses default max_history=100,000
tail -f app.log | uniqseq
```

- ✅ Handles most use cases automatically
- ✅ Optimizes for input type
- ✅ No configuration needed

### Limited History (Streaming)

```bash
# Smaller history for memory-constrained environments
uniqseq --max-history 10000 large-stream.log

# Very small for demonstration/testing
uniqseq --max-history 100 test.log
```

- ✅ Bounded memory usage
- ✅ Suitable for infinite streams
- ⚠️ May miss distant duplicates

### Unlimited History (Batch Processing)

```bash
# Process complete files with guaranteed deduplication
uniqseq --unlimited-history archive.log > clean.log

# Or use with stdin explicitly
tail -n 10000 app.log | uniqseq --unlimited-history
```

- ✅ Detects all duplicates
- ✅ Best for file processing
- ⚠️ Memory grows with unique content

## Rule of Thumb

**For streaming/real-time**: Use default or limited history
**For batch/files**: Use unlimited history (default for files)
**For testing/demos**: Use small max-history to see eviction behavior

## See Also

- [CLI Reference](../../reference/cli.md) - Complete history options documentation
- [Performance Guide](../../guides/performance.md) - Memory usage and optimization
- [Algorithm Details](../../about/algorithm.md) - How history tracking works
