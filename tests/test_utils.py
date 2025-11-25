"""Test utilities and helper functions."""

from io import StringIO

from uniqseq.uniqseq import UniqSeq


def process_lines(lines: list[str], **uniqseq_kwargs) -> tuple[str, UniqSeq]:
    """Helper to process lines and return output + uniqseq.

    Args:
        lines: Lines to process
        **uniqseq_kwargs: Arguments for UniqSeq

    Returns:
        (output_string, uniqseq_instance)
    """
    uniqseq = UniqSeq(**uniqseq_kwargs)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)

    return output.getvalue(), uniqseq


def count_output_lines(output: str) -> int:
    """Count non-empty lines in output."""
    return len([line for line in output.split("\n") if line.strip()])


def assert_lines_equal(actual: str, expected: list[str]):
    """Assert output matches expected lines."""
    actual_lines = [line for line in actual.split("\n") if line.strip()]
    assert actual_lines == expected
