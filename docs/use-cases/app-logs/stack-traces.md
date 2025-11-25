# Application Logs: Removing Repeated Stack Traces

Your application retries failed operations, logging the same error stack trace multiple times. Remove duplicate stack traces to make logs more readable while preserving unique errors.

## Input Data

???+ note "app.log"
    ```hl_lines="2-4 6-8 10-12"
    --8<-- "use-cases/app-logs/fixtures/app.log"
    ```

    Highlighted lines show three identical 3-line stack traces (ERROR + 2 stack frames) occurring during connection retries.

## Output Data

???+ success "output.log"
    ```text hl_lines="2-4"
    --8<-- "use-cases/app-logs/fixtures/expected-output.log"
    ```

    **Result**: 6 duplicate lines removed. First stack trace kept, retries collapsed to just their INFO messages.

## Solution

=== "CLI"

    <!-- verify-file: output.log expected: expected-output.log -->
    <!-- termynal -->
    ```console
    $ uniqseq app.log \
        --window-size 3 \
        --skip-chars 20 \
        --quiet > output.log
    ```

    **Options:**

    - `--window-size 3`: Match 3-line sequences (ERROR + 2 stack frames)
    - `--skip-chars 20`: Ignore timestamp prefix when comparing

=== "Python"

    <!-- verify-file: output.log expected: expected-output.log -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=3,  # (1)!
        skip_chars=20,  # (2)!
    )

    with open("app.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Match 3-line sequences (error + stack trace)
    2. Skip first 20 chars (timestamp)

## How It Works

Each error produces a 3-line sequence:
1. `ERROR: Database connection failed`
2. `at db.connect (db.js:45)`
3. `at app.init (app.js:12)`

This pattern repeats three times with different timestamps. We need:

1. **`--window-size 3`**: Detect that these 3-line stack traces are identical
2. **`--skip-chars 20`**: Ignore the timestamp prefix `2024-11-25 10:15:02 ` when comparing

### Visual Breakdown

```
Input (14 lines):                  Output (8 lines):
 1. INFO Starting              →   1. INFO Starting
 2. ERROR Database failed      →   2. ERROR Database failed
 3.   at db.connect            →   3.   at db.connect
 4.   at app.init              →   4.   at app.init
 5. INFO Retrying (1/3)        →   5. INFO Retrying (1/3)
 6. ERROR Database failed      ✗   (duplicate stack trace removed)
 7.   at db.connect            ✗
 8.   at app.init              ✗
 9. INFO Retrying (2/3)        →   6. INFO Retrying (2/3)
10. ERROR Database failed      ✗   (duplicate stack trace removed)
11.   at db.connect            ✗
12.   at app.init              ✗
13. WARN Max retries           →   7. WARN Max retries
14. INFO Shutting down         →   8. INFO Shutting down
```

The cleaned log clearly shows:
- One stack trace (the actual error)
- Retry attempts progressing (1/3, 2/3)
- Final outcome (max retries exceeded)

## Benefits

**Before deduplication**: 14 lines with repetitive stack traces obscuring the flow

**After deduplication**: 8 lines with clear progression of events

This makes it easier to:
- Understand the error sequence
- Count retry attempts
- Focus on unique issues
- Reduce log storage

## Real-World Usage

```bash
# Process application logs in real-time
tail -f /var/log/app.log | uniqseq --window-size 3 --skip-chars 20

# Clean up archived logs
for log in /var/log/app/*.log; do
    uniqseq "$log" --window-size 3 --skip-chars 20 > "${log}.clean"
done

# Combine with pattern filtering to deduplicate only errors
uniqseq app.log --track "ERROR" --window-size 3 --skip-chars 20
```

## See Also

- [CI Build Logs](../ci-logs/multi-line-sequences.md) - Similar multi-line deduplication
- [Ignoring Prefixes](../../features/skip-chars/skip-chars.md) - How skip-chars works
- [Window Size](../../features/window-size/window-size.md) - Choosing the right window
