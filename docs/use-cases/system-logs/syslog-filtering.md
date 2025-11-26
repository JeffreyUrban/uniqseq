# System Logs: Reducing Syslog Noise

Remove repeated syslog messages to focus on unique events, reducing noise from systemd, CRON, and other recurring services.

## The Problem

Linux syslog generates massive volumes of repetitive messages:

- **systemd start/stop** - Service lifecycle messages repeat constantly
- **CRON jobs** - Scheduled tasks create identical log entries
- **Firewall blocks** - Same attacks repeat from same IPs
- **Failed logins** - Brute force attempts create duplicate entries

This makes it hard to spot unique events requiring attention.

## Input Data

???+ note "syslog.log"
    ```text hl_lines="1-2 6-7 12-13 3 8 4 10 5 9"
    --8<-- "use-cases/system-logs/fixtures/syslog.log"
    ```

    The log contains **13 entries**, but many are duplicates:

    - systemd apt activities (lines 1-2, 6-7, 12-13) - appears 3×
    - CRON entries (lines 3, 8) - appears 2× (different PIDs but same command)
    - Firewall blocks (lines 4, 10) - same source IP blocked twice
    - SSH failures (lines 5, 9) - same failed login attempt

## Output Data

???+ success "expected-output.log"
    ```text
    --8<-- "use-cases/system-logs/fixtures/expected-output.log"
    ```

    **Result**: 6 duplicate entries removed → 7 unique log events

## Solution

=== "CLI"

    <!-- verify-file: output.log expected: expected-output.log -->
    <!-- termynal -->
    ```console
    $ uniqseq syslog.log \
        --skip-chars 16 \
        --window-size 1 \
        --quiet > output.log
    ```

    **Options:**

    - `--skip-chars 16`: Skip timestamp `Jan 15 10:30:XX ` (16 chars)
    - `--window-size 1`: Deduplicate individual log lines
    - `--quiet`: Suppress statistics

=== "Python"

    <!-- verify-file: output.log expected: expected-output.log -->
    ```python
    from uniqseq import UniqSeq

    uniqseq = UniqSeq(
        skip_chars=16,  # (1)!
        window_size=1,  # (2)!
    )

    with open("syslog.log") as f:
        with open("output.log", "w") as out:
            for line in f:
                uniqseq.process_line(line.rstrip("\n"), out)
            uniqseq.flush(out)
    ```

    1. Skip 16-character timestamp prefix when comparing
    2. Deduplicate individual lines (not multi-line sequences)

## How It Works

Syslog lines have timestamps that make every line look unique:

```text
Jan 15 10:30:01 server1 systemd[1]: Starting Daily apt...
Jan 15 10:30:15 server1 systemd[1]: Starting Daily apt...
└────┬─────────┘
   Skip this
   (16 chars)
```

By using `--skip-chars 16`, uniqseq ignores the timestamp when comparing lines, so the two systemd messages above are recognized as duplicates.

### Impact Analysis

**Before:**
```bash
$ wc -l < syslog.log
13
```

**After:**
```bash
$ wc -l < output.log
7
```

**46% reduction** in log volume by removing timestamp-varying duplicates.

## Real-World Workflows

### Live Syslog Monitoring

Deduplicate syslog in real-time:

```bash
tail -f /var/log/syslog | \
    uniqseq --skip-chars 16 --window-size 1
```

### Focus on Security Events

Track only security-related duplicates:

```bash
uniqseq /var/log/syslog \
    --track 'sshd|sudo|kernel.*BLOCK' \
    --skip-chars 16 \
    --window-size 1 > security-unique.log
```

### Aggregate Multiple Servers

Combine and deduplicate logs from multiple servers:

```bash
cat server1-syslog server2-syslog server3-syslog | \
    uniqseq --skip-chars 16 --window-size 1 > all-unique.log
```

### Historical Analysis

Find recurring issues across log archives:

```bash
zcat /var/log/syslog.*.gz | \
    uniqseq --skip-chars 16 \
            --window-size 1 \
            --annotate > recurring-issues.log
```

The `--annotate` flag shows how many times each pattern appeared.

### Normalize PIDs and Timestamps

For even more aggressive deduplication, normalize PIDs:

```bash
uniqseq /var/log/syslog \
    --hash-transform 'sed "s/\[[0-9]*\]/[PID]/g"' \
    --skip-chars 16 \
    --window-size 1 > highly-deduped.log
```

This treats all systemd messages as identical regardless of PID.

## Common Patterns

**Daily CRON noise**:
```bash
# Remove duplicate CRON messages
uniqseq /var/log/syslog --skip-chars 16 --window-size 1 | \
    grep -v CRON > syslog-no-cron.log
```

**Firewall block storms**:
```bash
# Deduplicate firewall blocks, keep other messages
uniqseq /var/log/syslog \
    --track 'kernel.*BLOCK' \
    --skip-chars 16 \
    --window-size 1
```

**Service restart spam**:
```bash
# Skip systemd service messages entirely
uniqseq /var/log/syslog \
    --skip-chars 16 \
    --window-size 1 | \
    grep -v 'systemd\[1\]'
```

## See Also

- [Skip Chars](../../features/skip-chars/skip-chars.md) - Ignoring variable prefixes
- [Pattern Filtering](../../features/pattern-filtering/pattern-filtering.md) - Track/bypass patterns
- [Hash Transform](../../features/hash-transform/hash-transform.md) - Normalizing before comparison
