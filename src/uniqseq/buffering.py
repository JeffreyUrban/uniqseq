"""Buffer depth calculation and management."""

from .matching import ActiveMatchManager


def calculate_min_buffer_depth(
    active_matches: ActiveMatchManager,
    window_size: int,
    line_num_input_tracked: int,
    line_buffer_length: int,
) -> int:
    """Calculate minimum buffer depth required to accommodate active matches.

    Args:
        active_matches: Manager containing active matches
        window_size: Size of the sliding window
        line_num_input_tracked: Current tracked input line number
        line_buffer_length: Current length of line buffer

    Returns:
        Minimum number of lines that must remain in buffer
    """
    min_required_depth = window_size

    for match in active_matches:
        # Calculate how many lines this match spans
        match_length = window_size + (match.next_window_index - 1)

        # Calculate buffer depth based on tracked line numbers
        buffer_first_tracked = line_num_input_tracked - line_buffer_length + 1
        match_first_tracked = match.tracked_line_at_start
        match_last_tracked = match.tracked_line_at_start + match_length - 1

        # Calculate overlap between buffer and match
        overlap_start = max(buffer_first_tracked, match_first_tracked)
        overlap_end = min(line_num_input_tracked, match_last_tracked)

        if overlap_end >= overlap_start:
            # Match has lines in buffer - calculate depth from start of match to end of buffer
            buffer_depth = line_num_input_tracked - overlap_start + 1
            if buffer_depth > min_required_depth:
                min_required_depth = buffer_depth

    return min_required_depth
