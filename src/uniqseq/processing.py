"""Line and window processing helpers."""

from collections import deque
from collections.abc import Callable
from typing import Optional, Union

from .hashing import BufferedLine, hash_line, hash_window


def prepare_line_for_deduplication(
    line: Union[str, bytes],
    line_num_input: int,
    line_num_input_tracked: int,
    skip_chars: int,
    hash_transform: Optional[Callable[[Union[str, bytes]], Union[str, bytes]]],
) -> BufferedLine:
    """Prepare a line for deduplication by hashing and creating BufferedLine.

    Args:
        line: Original line (without delimiter)
        line_num_input: Overall input line number
        line_num_input_tracked: Tracked input line number (only lines participating in dedup)
        skip_chars: Number of characters to skip when hashing
        hash_transform: Optional transformation function to apply before hashing

    Returns:
        BufferedLine ready to add to deduplication buffer
    """
    # Determine what to hash (apply transform if configured)
    line_for_hashing: Union[str, bytes]
    if hash_transform is not None:
        # Apply transform for hashing (but keep original line for output)
        line_for_hashing = hash_transform(line)
    else:
        line_for_hashing = line

    # Hash the line (with prefix skipping if configured)
    line_hash = hash_line(line_for_hashing, skip_chars)

    # Create buffered line with metadata
    return BufferedLine(
        line=line,
        line_hash=line_hash,
        input_line_num=line_num_input,
        tracked_line_num=line_num_input_tracked,
    )


def calculate_window_hash(line_buffer: deque[BufferedLine], window_size: int) -> tuple[str, int]:
    """Calculate window hash for current position.

    Args:
        line_buffer: Buffer of lines being processed
        window_size: Size of the sliding window

    Returns:
        Tuple of (window_hash, current_window_start_position)
    """
    # Get line hashes for the most recent window_size lines
    window_line_hashes = [bl.line_hash for bl in list(line_buffer)[-window_size:]]
    window_hash = hash_window(window_size, window_line_hashes)

    # Calculate window start position (tracked line number)
    current_window_start = line_buffer[-1].tracked_line_num - window_size + 1

    return window_hash, current_window_start
