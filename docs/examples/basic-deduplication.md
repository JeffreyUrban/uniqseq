# Basic Deduplication

This page demonstrates basic deduplication of repeated line sequences.

## Simple Sequence Deduplication

Remove a repeated 3-line sequence:

```python
from io import StringIO
from uniqseq import StreamingDeduplicator

dedup = StreamingDeduplicator(window_size=3)
lines = ["A", "B", "C", "A", "B", "C", "D"]

output = StringIO()
for line in lines:
    dedup.process_line(line, output)
dedup.flush(output)

result = output.getvalue().strip().split("\n")
assert result == ["A", "B", "C", "D"]
```

## Single Line Deduplication

With `window_size=1`, deduplicate individual repeated lines (even if not adjacent):

```python
from io import StringIO
from uniqseq import StreamingDeduplicator

dedup = StreamingDeduplicator(window_size=1)
lines = ["A", "B", "B", "C", "A", "D"]

output = StringIO()
for line in lines:
    dedup.process_line(line, output)
dedup.flush(output)

result = output.getvalue().strip().split("\n")
assert result == ["A", "B", "C", "D"]
```

Note: Both duplicate "B" and the second "A" are removed, even though the second "A" is not adjacent to the first.

## No Duplicates Case

If there are no repeated sequences, all lines are preserved:

```python
from io import StringIO
from uniqseq import StreamingDeduplicator

dedup = StreamingDeduplicator(window_size=2)
lines = ["A", "B", "C", "D", "E"]

output = StringIO()
for line in lines:
    dedup.process_line(line, output)
dedup.flush(output)

result = output.getvalue().strip().split("\n")
assert result == ["A", "B", "C", "D", "E"]
```

*Additional content and CLI examples to be added in Phase 3*
