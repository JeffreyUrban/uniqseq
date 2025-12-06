"""Buffer emission and line output helpers."""

from collections import deque
from typing import Union

from .hashing import BufferedLine
from .history import HistoryEntry
from .output import print_explain


def handle_line_emission(
    buffered_line: BufferedLine,
    diverged_match_ranges: list[tuple[int, int, Union[int, float, str], int]],
    output_buffer: deque[Union[str, bytes]],
    position_to_entry: dict[int, HistoryEntry],
    inverse: bool,
    explain: bool,
) -> tuple[int, int]:
    """Handle emission or skipping of a line based on duplicate status.

    Args:
        buffered_line: The line to emit or skip
        diverged_match_ranges: Ranges of duplicate lines to skip
        output_buffer: Buffer to write output lines to
        position_to_entry: History entries for updating output line numbers
        inverse: Whether in inverse mode
        explain: Whether to print explanations

    Returns:
        Tuple of (line_num_output_delta, lines_skipped_delta)
    """
    line_num_output_delta = 0
    lines_skipped_delta = 0

    # Check if this line is part of a diverged match (duplicate)
    is_duplicate = False
    for start, end, orig_line, count in diverged_match_ranges:
        if start <= buffered_line.tracked_line_num <= end:
            is_duplicate = True
            # Remove this range if we've consumed all its lines
            if buffered_line.tracked_line_num == end:
                diverged_match_ranges.remove((start, end, orig_line, count))
            break

    if is_duplicate:
        if inverse:
            # Inverse mode: emit duplicate lines
            output_buffer.append(buffered_line.line)
            line_num_output_delta = 1
        else:
            # Normal mode: skip duplicate lines
            lines_skipped_delta = 1
    else:
        # Unique line
        if inverse:
            # Inverse mode: skip unique lines
            lines_skipped_delta = 1
            print_explain(
                f"Line {buffered_line.input_line_num} skipped (unique in inverse mode)",
                explain,
            )
        else:
            # Normal mode: emit unique lines
            output_buffer.append(buffered_line.line)
            line_num_output_delta = 1
            # Update history entry for window starting at this line
            hist_pos = buffered_line.tracked_line_num - 1
            entry = position_to_entry.get(hist_pos)
            if entry and entry.first_output_line is None:
                # Mark for update - caller needs to provide actual line number
                entry.first_output_line = -1

    return line_num_output_delta, lines_skipped_delta
