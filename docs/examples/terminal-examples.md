# Terminal Examples

Real-world examples using `uniqseq` from the command line.

## Example Files

The examples below use these files:

```
fixtures/
├── repeated.txt          # Simple repeated sequence
└── server.log            # Server log with repeated errors
```

## Basic Deduplication

### Input File

```text title="fixtures/repeated.txt"
--8<-- "examples/fixtures/repeated.txt"
```

[View file](fixtures/repeated.txt){ .md-button }

### Running uniqseq

Remove repeated 3-line sequences:

```console
$ uniqseq repeated.txt --window-size 3
A
B
C
D
```

The repeated sequence `A`, `B`, `C` is detected and removed, keeping only the first occurrence.

## Server Log Processing

### Input File

```text title="fixtures/server.log"
--8<-- "examples/fixtures/server.log"
```

[View file](fixtures/server.log){ .md-button }

### Deduplicate Error Sequences

Remove repeated error blocks (3-line sequences):

```console
$ uniqseq server.log --window-size 3 --quiet
INFO: Starting application
ERROR: Connection failed
  at line 10
  retry in 5s
INFO: Retrying
INFO: Success
```

The second occurrence of the 3-line error sequence is removed.

### Track Only Errors

Use `--track` to deduplicate only ERROR lines:

```console
$ uniqseq server.log --track "^ERROR" --window-size 1 --quiet
INFO: Starting application
ERROR: Connection failed
  at line 10
  retry in 5s
INFO: Retrying
  at line 10
  retry in 5s
INFO: Success
```

Only the duplicate ERROR line is removed; stack trace lines pass through unchanged.

## Using as a Unix Filter

Read from stdin and write to stdout:

```console
$ printf "A\nB\nA\nB\nC\n" | uniqseq --window-size 2 --quiet
A
B
C
```

*Additional terminal examples to be added*
