"""Output formatting including annotations and explanations."""

import sys
from collections import deque
from typing import Union


def print_explain(message: str, explain: bool) -> None:
    """Print explanation message to stderr if explain mode is enabled.

    Args:
        message: The explanation message to print
        explain: Whether explain mode is enabled
    """
    if explain:
        print(f"EXPLAIN: {message}", file=sys.stderr)


def write_annotation(
    output_buffer: deque[Union[str, bytes]],
    annotation_format: str,
    delimiter: Union[str, bytes],
    start: int,
    end: int,
    match_start: int,
    match_end: int,
    count: int,
    window_size: int,
) -> None:
    """Add an annotation marker to the output buffer.

    Args:
        output_buffer: The output buffer to write to
        annotation_format: Template string for annotation
        delimiter: Delimiter being used (str or bytes)
        start: First line number of skipped sequence
        end: Last line number of skipped sequence
        match_start: First line number of matched sequence
        match_end: Last line number of matched sequence
        count: Total times sequence has been seen
        window_size: Window size for deduplication
    """
    # Substitute template variables
    annotation = annotation_format.format(
        start=start,
        end=end,
        match_start=match_start,
        match_end=match_end,
        count=count,
        window_size=window_size,
    )

    # Add annotation to output buffer
    # Convert to bytes if in binary mode
    if isinstance(delimiter, bytes):
        output_buffer.append(annotation.encode("utf-8"))
    else:
        output_buffer.append(annotation)
