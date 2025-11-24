# Command-Line Usage

Examples demonstrating the `uniqseq` command-line interface.

## Basic CLI Usage

Process a file using the uniqseq command:

```python
from pathlib import Path
from typer.testing import CliRunner
from uniqseq.cli import app

runner = CliRunner()

with runner.isolated_filesystem():
    # Create input file
    Path("input.txt").write_text("A\nB\nC\nA\nB\nC\nD\n")

    # Run uniqseq command
    result = runner.invoke(app, ["input.txt", "--window-size", "3"])

    assert result.exit_code == 0
    assert result.stdout == "A\nB\nC\nD\n"
```

## Using stdin/stdout (Unix Filter Style)

Process input from stdin and write to stdout:

```python
from typer.testing import CliRunner
from uniqseq.cli import app

runner = CliRunner()

input_text = "Line 1\nLine 2\nLine 1\nLine 2\nLine 3\n"

result = runner.invoke(app, ["--window-size", "2"], input=input_text)

assert result.exit_code == 0
assert result.stdout == "Line 1\nLine 2\nLine 3\n"
```

## Redirecting Output

Capture stdout to save results to a file:

```python
from pathlib import Path
from typer.testing import CliRunner
from uniqseq.cli import app

runner = CliRunner()

with runner.isolated_filesystem():
    # Create input file
    Path("input.txt").write_text("X\nY\nZ\nX\nY\nZ\nW\n")

    # Run and capture output
    result = runner.invoke(app, [
        "input.txt",
        "--window-size", "3"
    ])

    assert result.exit_code == 0
    assert result.stdout == "X\nY\nZ\nW\n"

    # In a real shell, you would redirect: uniqseq input.txt > output.txt
```

## Pattern Filtering with --track

Only deduplicate lines matching a pattern:

```python
from pathlib import Path
from typer.testing import CliRunner
from uniqseq.cli import app

runner = CliRunner()

with runner.isolated_filesystem():
    # Log file with errors and info messages
    input_text = """ERROR: Failed
INFO: Retrying
ERROR: Failed
INFO: Success
"""
    Path("app.log").write_text(input_text)

    # Only deduplicate ERROR lines
    result = runner.invoke(app, [
        "app.log",
        "--track", "^ERROR",
        "--window-size", "1"
    ])

    assert result.exit_code == 0
    # First ERROR kept, second ERROR removed, INFO lines passed through
    assert "ERROR: Failed" in result.stdout
    assert result.stdout.count("ERROR: Failed") == 1
    assert "INFO: Retrying" in result.stdout
    assert "INFO: Success" in result.stdout
```

## Annotation Mode

Show where duplicates were removed:

```python
from pathlib import Path
from typer.testing import CliRunner
from uniqseq.cli import app

runner = CliRunner()

with runner.isolated_filesystem():
    Path("input.txt").write_text("A\nB\nA\nB\nC\n")

    result = runner.invoke(app, [
        "input.txt",
        "--annotate",
        "--window-size", "2"
    ])

    assert result.exit_code == 0
    # Should contain the original lines and a DUPLICATE annotation
    assert "A\nB\n" in result.stdout
    assert "[DUPLICATE:" in result.stdout
    assert "C\n" in result.stdout
```

## Inverse Mode

Show only the duplicates that were removed:

```python
from typer.testing import CliRunner
from uniqseq.cli import app

runner = CliRunner()

input_text = "A\nB\nC\nA\nB\nC\nD\n"

result = runner.invoke(app, [
    "--inverse",
    "--window-size", "3"
], input=input_text)

assert result.exit_code == 0
# Should output only the duplicate sequence
assert result.stdout == "A\nB\nC\n"
```

*Additional CLI examples to be added in Phase 3*
