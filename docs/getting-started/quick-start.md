# Quick Start

Get started with `uniqseq` in 5 minutes.

## Installation

```bash
pip install uniqseq
```

## Basic Usage

### Remove Duplicate Lines

The simplest use case - remove duplicate single lines:

```bash
$ echo -e "A\nB\nC\nB\nD" | uniqseq
A
B
C
D
```

Unlike `uniq`, uniqseq finds duplicates anywhere in the input, not just adjacent lines.

### Remove Duplicate Sequences

Detect and remove repeated 3-line sequences:

```bash
$ uniqseq input.log --window-size 3
```

**Example**: If your log file contains:

```
[10:30:01] Starting task
[10:30:02] Processing...
[10:30:03] Task complete
[10:30:05] Starting task
[10:30:06] Processing...
[10:30:07] Task complete
```

The output keeps only the first occurrence:

```
[10:30:01] Starting task
[10:30:02] Processing...
[10:30:03] Task complete
```

### Skip Timestamp Prefixes

When lines differ only by timestamps, use `--skip-chars` to ignore them:

```bash
$ uniqseq build.log --window-size 3 --skip-chars 21
```

This skips the first 21 characters (e.g., `[2024-01-15 10:30:03]`) when comparing lines.

## Common Patterns

### Clean Build Logs

```bash
$ uniqseq ci-build.log --window-size 3 --skip-chars 21 > clean.log
```

### Process Live Output

```bash
$ tail -f server.log | uniqseq
```

### Track Only Errors

```bash
$ uniqseq app.log --track "^ERROR"
```

## Next Steps

- **[Basic Concepts](basic-concepts.md)** - Understand how uniqseq works
- **[Common Patterns](../guides/common-patterns.md)** - Copy-paste ready examples
- **[Troubleshooting](../guides/troubleshooting.md)** - Solutions to common problems
- **[Use Cases](../use-cases/ci-logs/multi-line-sequences.md)** - Real-world examples
- **[CLI Reference](../reference/cli.md)** - Complete command-line options
