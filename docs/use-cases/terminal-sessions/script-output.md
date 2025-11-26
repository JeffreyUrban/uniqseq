# Terminal Sessions: Cleaning Script Output

Remove repeated command sequences from terminal session logs to create clean, concise documentation.

## The Problem

When demonstrating software workflows, you often run the same commands multiple times during development:

- **Testing commands** - Run same command repeatedly while debugging
- **Showing retries** - Demonstrate retry behavior clutters output
- **Recording sessions** - Terminal session captures include duplicate commands
- **Creating docs** - Need clean examples without repetition

## Input Data

???+ note "verbose-session.log"
    ```console hl_lines="1-8 24-31 10-16 32-38"
    --8<-- "use-cases/terminal-sessions/fixtures/verbose-session.log"
    ```

    A terminal session where `migrate` and `test` commands were run twice:

    - Lines 1-8: First `python manage.py migrate` (5 lines)
    - Lines 24-31: Duplicate `python manage.py migrate` (5 lines)
    - Lines 10-16: First `python manage.py test` (5 lines)
    - Lines 32-38: Duplicate `python manage.py test` (5 lines)

## Output Data

???+ success "expected-clean-session.log"
    ```text
    --8<-- "use-cases/terminal-sessions/fixtures/expected-clean-session.log"
    ```

    **Result**: Duplicate command sequences removed → clean session log

## Solution

=== "CLI"

    <!-- verify-file: output.log expected: expected-clean-session.log -->
    <!-- termynal -->
    ```console
    $ uniqseq verbose-session.log \
        --window-size 5 \
        --quiet > output.log
    ```

    **Options:**

    - `--window-size 5`: Match 5-line command sequences
    - `--quiet`: Suppress statistics

=== "Python"

    <!-- verify-file: output.log expected: expected-clean-session.log -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        window_size=5,  # (1)!
    )

    with open("verbose-session.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Match 5-line sequences (typical command + output length)

## How It Works

Terminal commands typically produce multi-line output. By setting `--window-size 5`, uniqseq detects when a 5-line pattern (command + output) repeats and removes the duplicate.

### Choosing Window Size

The window size should match your command's output length:

```bash
# Short commands (1-2 lines output): window-size 3
uniqseq session.log --window-size 3

# Medium commands (3-5 lines output): window-size 5
uniqseq session.log --window-size 5

# Long commands (10+ lines output): window-size 10
uniqseq session.log --window-size 10
```

## Real-World Workflows

### Create README Examples

Clean up terminal sessions for documentation:

```bash
# Record session with script/asciinema
script session.log

# ... run commands, some repeated during testing ...

# Clean for documentation
uniqseq session.log --window-size 5 > clean-session.log
```

### Show What Was Removed

Use `--annotate` to mark where duplicates were removed:

```bash
uniqseq session.log --window-size 5 --annotate > annotated.log
```

Output includes markers:
```text
[DUPLICATE: Lines 24-31 matched lines 1-8 (sequence seen 2 times)]
```

### Interactive Debugging Cleanup

Remove test command repetitions while debugging:

```bash
# You ran: python test.py
# Output: 20 lines of test results
# You ran it 5 times debugging

# Clean to show just once
uniqseq debug-session.log --window-size 20 > clean-debug.log
```

### Aggregate Multiple Sessions

Combine multiple terminal sessions and remove cross-session duplicates:

```bash
cat session-01.log session-02.log session-03.log | \
    uniqseq --window-size 5 > combined-clean.log
```

## Tips

**Variable Output**: If command output varies slightly (timestamps, IDs), use `--skip-chars` or `--hash-transform`:

```bash
# Skip timestamp prefix in each line
uniqseq session.log --window-size 5 --skip-chars 20

# Normalize timestamps before comparison
uniqseq session.log --window-size 5 \
    --hash-transform "sed 's/[0-9]\{2\}:[0-9]\{2\}:[0-9]\{2\}//g'"
```

**Preserve Important Repetitions**: Use `--bypass` to keep certain commands even if repeated:

```bash
# Keep all ERROR lines even if they repeat
uniqseq session.log --window-size 5 --bypass 'ERROR'
```

## See Also

- [Window Size](../../features/window-size/window-size.md) - Choosing the right window size
- [Annotations](../../features/annotations/annotations.md) - Showing what was removed
- [Skip Chars](../../features/skip-chars/skip-chars.md) - Ignoring variable prefixes
