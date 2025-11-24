# File Processing Examples

Examples demonstrating file input/output operations.

## Processing a Log File

Create a log file with repeated error sequences and deduplicate it:

```python
from pathlib import Path
from io import StringIO
from uniqseq import StreamingDeduplicator

# Create sample log file
log_content = """ERROR: Connection failed
  at line 10
  retry in 5s
INFO: Retrying
ERROR: Connection failed
  at line 10
  retry in 5s
INFO: Success
"""

input_file = tmp_path / "app.log"
input_file.write_text(log_content)

# Process the file
output_file = tmp_path / "deduped.log"
dedup = StreamingDeduplicator(window_size=3)

with open(input_file) as f_in, open(output_file, "w") as f_out:
    for line in f_in:
        dedup.process_line(line.rstrip("\n"), f_out)
    dedup.flush(f_out)

# Verify output
result = output_file.read_text()
expected = """ERROR: Connection failed
  at line 10
  retry in 5s
INFO: Retrying
INFO: Success
"""

assert result == expected
```

## Batch Processing Multiple Files

Process multiple log files and verify each output:

```python
from pathlib import Path
from uniqseq import StreamingDeduplicator

# Create multiple input files
files = {
    "app1.log": "A\nB\nC\nA\nB\nC\nD\n",
    "app2.log": "X\nY\nX\nY\nZ\n",
}

for filename, content in files.items():
    (tmp_path / filename).write_text(content)

# Process each file
expected_outputs = {
    "app1.log": "A\nB\nC\nD\n",
    "app2.log": "X\nY\nZ\n",
}

for filename, expected in expected_outputs.items():
    input_file = tmp_path / filename
    output_file = tmp_path / f"deduped_{filename}"

    dedup = StreamingDeduplicator(window_size=2)
    with open(input_file) as f_in, open(output_file, "w") as f_out:
        for line in f_in:
            dedup.process_line(line.rstrip("\n"), f_out)
        dedup.flush(f_out)

    result = output_file.read_text()
    assert result == expected, f"Failed for {filename}"
```

## Working with Golden Files

You can also compare against pre-defined golden files from the test fixtures:

```python
from pathlib import Path
from uniqseq import StreamingDeduplicator

# Simulate reading a golden reference file
# (In real tests, this would come from tests/fixtures/)
golden = tmp_path / "golden.txt"
golden.write_text("Line 1\nLine 2\nLine 3\n")

# Create test input with duplicates
input_file = tmp_path / "input.txt"
input_file.write_text("Line 1\nLine 2\nLine 3\nLine 1\nLine 2\nLine 3\n")

# Process and compare to golden
output_file = tmp_path / "output.txt"
dedup = StreamingDeduplicator(window_size=3)

with open(input_file) as f_in, open(output_file, "w") as f_out:
    for line in f_in:
        dedup.process_line(line.rstrip("\n"), f_out)
    dedup.flush(f_out)

# Verify output matches golden file
assert output_file.read_text() == golden.read_text()
```

*Additional file processing examples to be added in Phase 3*
