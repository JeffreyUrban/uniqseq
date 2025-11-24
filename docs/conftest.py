"""Sybil configuration for testing code examples in documentation."""

import subprocess
from pathlib import Path

from sybil import Sybil
from sybil.parsers.markdown import CodeBlockParser, PythonCodeBlockParser, SkipParser


def evaluate_console_block(example):
    """
    Evaluate console code blocks with $ prompts.

    Format:
        $ command
        expected output line 1
        expected output line 2
        $ another command
        more expected output

    Commands are run from docs/examples/fixtures/ directory.
    """
    # Get the fixtures directory - search upward from the file location
    current_path = Path(example.path).parent
    fixtures_dir = None

    # Try local fixtures first
    if (current_path / "fixtures").exists():
        fixtures_dir = current_path / "fixtures"
    else:
        # Search upward for docs directory, then look for examples/fixtures
        while current_path.name != "docs" and current_path.parent != current_path:
            current_path = current_path.parent

        # Now we should be at docs directory
        if current_path.name == "docs":
            shared_fixtures = current_path / "examples" / "fixtures"
            if shared_fixtures.exists():
                fixtures_dir = shared_fixtures

    if fixtures_dir is None:
        raise FileNotFoundError(
            f"Fixtures directory not found starting from {Path(example.path).parent}"
        )

    lines = example.parsed.strip().split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # Skip empty lines
        if not line.strip():
            i += 1
            continue

        # Process command lines (starting with $)
        if line.startswith("$ "):
            command = line[2:].strip()

            # Strip annotation comments (e.g., # (1)!)
            if " #" in command:
                # Only strip if it looks like an annotation comment
                comment_part = command.split(" #", 1)[1].strip()
                if comment_part.startswith("(") and comment_part.endswith(")!"):
                    command = command.split(" #", 1)[0].strip()

            # Collect expected output (lines until next $ or end)
            expected_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("$ "):
                if lines[i].strip():  # Skip empty lines in expected output
                    expected_lines.append(lines[i])
                i += 1

            expected_output = "\n".join(expected_lines)

            # Run the command from fixtures directory
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=fixtures_dir,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                actual_output = result.stdout.strip()

                # Compare outputs
                if expected_output:
                    assert actual_output == expected_output, (
                        f"\nCommand: {command}\n"
                        f"Expected:\n{expected_output}\n"
                        f"Actual:\n{actual_output}"
                    )
            except subprocess.TimeoutExpired as e:
                raise AssertionError(f"Command timed out: {command}") from e
            except subprocess.CalledProcessError as e:
                raise AssertionError(
                    f"Command failed: {command}\nExit code: {e.returncode}\nStderr: {e.stderr}"
                ) from e
        else:
            # Unexpected format
            raise ValueError(f"Expected line to start with '$ ', got: {line}")


pytest_collect_file = Sybil(
    parsers=[
        PythonCodeBlockParser(),
        CodeBlockParser(language="console", evaluator=evaluate_console_block),
        SkipParser(),
    ],
    patterns=["*.md"],
    fixtures=["tmp_path"],
).pytest()
