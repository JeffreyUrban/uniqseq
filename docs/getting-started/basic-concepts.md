# Basic Concepts

Understand the core concepts behind `uniqseq`.

## What is a Sequence?

A **sequence** is one or more consecutive lines that repeat in your input.

### Single-Line Sequences (Window Size 1)

The default behavior - find duplicate lines:

```
Input:           Output:
A                A
B                B
A  ← duplicate   C
C
```

### Multi-Line Sequences (Window Size > 1)

With `--window-size 3`, uniqseq looks for repeating 3-line patterns:

```
Input:              Output:
Line 1              Line 1
Line 2              Line 2
Line 3              Line 3
Line 4              Line 4
Line 1  ┐           Line 5
Line 2  │ duplicate
Line 3  ┘
Line 4
Line 5
```

The sequence "Line 1, Line 2, Line 3" repeats, so the second occurrence is removed.

## How Deduplication Works

### 1. Sliding Window

uniqseq uses a sliding window to scan through your input:

```
Window Size 3:
[Line 1]  ← Check if seen before
[Line 2]
[Line 3]

 [Line 2]  ← Move window down
 [Line 3]
 [Line 4]

  [Line 3]  ← Move window down
  [Line 4]
  [Line 5]
```

### 2. Hash-Based Detection

For each window position, uniqseq:

1. **Computes a hash** of the lines in the window
2. **Checks** if this hash was seen before
3. **Keeps or removes** lines based on whether it's a duplicate

This makes deduplication very fast, even for large files.

### 3. First-Occurrence Preservation

When uniqseq finds a duplicate, it always **keeps the first occurrence** and removes later ones:

```
First occurrence  → KEEP
Second occurrence → REMOVE
Third occurrence  → REMOVE
```

## Key Parameters

### Window Size

**`--window-size N`** - How many consecutive lines to consider as a unit

- **`--window-size 1`** (default): Deduplicate individual lines
- **`--window-size 3`**: Deduplicate 3-line sequences
- **`--window-size 5`**: Deduplicate 5-line sequences

**Rule of thumb**: Set window size to match the number of lines in the pattern you want to remove.

### Skip Characters

**`--skip-chars N`** - Ignore first N characters of each line when comparing

Useful for lines that differ only in prefixes like timestamps:

```
Before skip-chars:
[2024-01-15 10:30:01] Error: Connection failed  ← Different
[2024-01-15 10:30:05] Error: Connection failed  ← Different

After --skip-chars 21:
Error: Connection failed  ← Same!
Error: Connection failed  ← Same! (duplicate)
```

The first 21 characters (`[2024-01-15 10:30:01] `) are ignored during comparison.

## Pattern Filtering

### Track Patterns (`--track`)

Only deduplicate lines matching a regex pattern:

```bash
$ uniqseq app.log --track "^ERROR"
```

- **ERROR lines**: Deduplicated
- **INFO lines**: Passed through unchanged

### Bypass Patterns (`--bypass`)

Never deduplicate lines matching a regex pattern:

```bash
$ uniqseq app.log --bypass "^WARN"
```

- **WARN lines**: Always included, never deduplicated
- **Other lines**: Deduplicated normally

## Memory Efficiency

uniqseq is designed for **streaming** - it processes input line-by-line without loading the entire file into memory.

**Memory usage depends only on**:

- Window size (larger windows need more memory per entry)
- Number of unique sequences (not total lines)

This means you can process GB-sized files with minimal memory.

## Next Steps

- **[Quick Start](quick-start.md)** - Try uniqseq with simple examples
- **[Choosing Window Size](../guides/choosing-window-size.md)** - Guide for selecting the right window size
- **[Common Patterns](../guides/common-patterns.md)** - Copy-paste ready examples
- **[Use Cases](../use-cases/ci-logs/multi-line-sequences.md)** - See real-world applications
- **[Algorithm Details](../about/algorithm.md)** - Deep dive into how it works
