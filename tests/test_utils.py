"""Test utilities and helper functions."""

from io import StringIO

from uniqseq.deduplicator import StreamingDeduplicator


def process_lines(lines: list[str], **dedup_kwargs) -> tuple[str, StreamingDeduplicator]:
    """Helper to process lines and return output + deduplicator.

    Args:
        lines: Lines to process
        **dedup_kwargs: Arguments for StreamingDeduplicator

    Returns:
        (output_string, deduplicator_instance)
    """
    dedup = StreamingDeduplicator(**dedup_kwargs)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)
    dedup.flush(output)

    return output.getvalue(), dedup


def count_output_lines(output: str) -> int:
    """Count non-empty lines in output."""
    return len([line for line in output.split("\n") if line.strip()])


def assert_lines_equal(actual: str, expected: list[str]):
    """Assert output matches expected lines."""
    actual_lines = [line for line in actual.split("\n") if line.strip()]
    assert actual_lines == expected
