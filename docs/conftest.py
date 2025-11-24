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
    # Get the fixtures directory relative to the docs directory
    fixtures_dir = Path(example.path).parent / "fixtures"

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
