"""Match divergence detection and handling."""

from collections import defaultdict, deque
from collections.abc import Callable
from typing import Optional, Union

from .hashing import BufferedLine
from .matching import ActiveMatchManager, SubsequenceMatch
from .output import print_explain, write_annotation


def handle_diverged_matches(
    all_diverged: list[SubsequenceMatch],
    active_matches: ActiveMatchManager,
    line_buffer: deque[BufferedLine],
    diverged_match_ranges: list[tuple[int, int, Union[int, float, str], int]],
    output_buffer: deque[Union[str, bytes]],
    window_size: int,
    save_sequence_callback: Optional[Callable[[Union[str, bytes]], None]],
    annotate: bool,
    annotation_format: str,
    delimiter: Union[str, bytes],
    inverse: bool,
    explain: bool,
) -> None:
    """Handle diverged matches with smart deduplication.

    Strategy:
    1. Filter out incomplete subsequences (matches that end at same position but started later)
    2. Group matches by starting position
    3. For each group, check if any active match from same position is still running
    4. If no active matches from that position, record the longest diverged match
    5. Among matches of same length, record the earliest (by first_output_line)

    Args:
        all_diverged: List of diverged matches
        active_matches: Currently active matches
        line_buffer: Buffer of lines being processed
        diverged_match_ranges: List to append duplicate ranges to
        output_buffer: Buffer for output lines
        window_size: Window size for deduplication
        save_sequence_callback: Optional callback for saving sequences
        annotate: Whether to add annotations
        annotation_format: Template for annotations
        delimiter: Delimiter being used
        inverse: Whether in inverse mode
        explain: Whether to print explanations
    """
    if not all_diverged:
        return

    # Filter out incomplete subsequences
    # When multiple matches end at the same position, keep only the longest (earliest start)

    # Calculate match info for all diverged matches
    match_info = []  # List of (match, match_length, match_end)
    end_positions = set()
    for match in all_diverged:
        length = match.next_window_index
        match_start = match.tracked_line_at_start
        match_length = window_size + (length - 1)
        match_end = match_start + match_length - 1
        end_positions.add(match_end)
        match_info.append((match, match_length, match_end))

    # All diverged matches should end at the same position
    if len(end_positions) > 1:
        raise ValueError("diverged matches found at different ending positions")

    # Find the maximum length among all matches
    max_length = max(info[1] for info in match_info)  # info[1] is match_length

    # Keep only matches with maximum length
    all_diverged = [info[0] for info in match_info if info[1] == max_length]

    # Group diverged matches by starting position (INPUT line, not output line)
    by_start_pos: dict[int, list[SubsequenceMatch]] = defaultdict(list)
    for match in all_diverged:
        by_start_pos[match.tracked_line_at_start].append(match)

    # Process each starting position IN ORDER (earliest first)
    for start_pos in sorted(by_start_pos.keys()):
        matches_at_pos = by_start_pos[start_pos]

        # Check if any active match is still running from this starting position
        has_active_from_pos = any(m.tracked_line_at_start == start_pos for m in active_matches)

        if has_active_from_pos:
            # Don't record yet - longer match may still be running
            continue

        # Find longest match(es) from this position
        max_length_at_pos = max(m.next_window_index for m in matches_at_pos)
        longest_matches = [m for m in matches_at_pos if m.next_window_index == max_length_at_pos]

        # If multiple matches of same length, pick earliest (by first_output_line)
        if len(longest_matches) == 1:
            match_to_record = longest_matches[0]
        else:
            # Pick earliest based on sequence first_output_line
            def sort_key(match: SubsequenceMatch) -> tuple[int, Union[int, float, str]]:
                orig_line = match.get_original_line()
                if orig_line == "preloaded":
                    return (0, 0)  # Preloaded sequences come first
                elif orig_line == "pending":
                    return (2, 0)  # Pending sequences come last
                else:
                    return (1, orig_line)  # Regular sequences sorted by line number

            match_to_record = min(longest_matches, key=sort_key)

        # Calculate actual number of lines matched
        matched_length = match_to_record.next_window_index
        lines_matched = window_size + (matched_length - 1)

        # Extract matched lines from buffer if save callback is configured
        matched_lines = None
        if save_sequence_callback and lines_matched <= len(line_buffer):
            matched_lines = [line_buffer[i].line for i in range(lines_matched)]

        # Record this match (polymorphic - will save for HistorySubsequenceMatch only)
        match_to_record.record_match(matched_length, matched_lines, save_sequence_callback)

        # Handle line skipping/outputting based on mode
        handle_matched_lines(
            lines_matched,
            match_to_record,
            line_buffer,
            diverged_match_ranges,
            output_buffer,
            annotate,
            annotation_format,
            delimiter,
            window_size,
            inverse,
            explain,
        )


def handle_matched_lines(
    matched_length: int,
    match: SubsequenceMatch,
    line_buffer: deque[BufferedLine],
    diverged_match_ranges: list[tuple[int, int, Union[int, float, str], int]],
    output_buffer: deque[Union[str, bytes]],
    annotate: bool,
    annotation_format: str,
    delimiter: Union[str, bytes],
    window_size: int,
    inverse: bool,
    explain: bool,
) -> None:
    """Skip or emit matched lines from the buffer based on mode.

    Args:
        matched_length: Number of lines that were matched
        match: The match object containing original position info
        line_buffer: Buffer of lines being processed
        diverged_match_ranges: List to append duplicate ranges to
        output_buffer: Buffer for output lines
        annotate: Whether to add annotations
        annotation_format: Template for annotations
        delimiter: Delimiter being used
        window_size: Window size for deduplication
        inverse: Whether in inverse mode
        explain: Whether to print explanations
    """
    if matched_length <= 0 or matched_length > len(line_buffer):
        return

    # Collect annotation info before modifying buffer
    should_annotate = annotate and not inverse and matched_length > 0
    annotation_info = None

    if should_annotate and len(line_buffer) >= matched_length:
        dup_start = line_buffer[0].input_line_num
        dup_end = line_buffer[matched_length - 1].input_line_num

        # Get original match position
        orig_line = match.get_original_line()

        # Only annotate if orig_line is numeric (skip preloaded/pending)
        if isinstance(orig_line, (int, float)):
            # Calculate match_end (original sequence had same length as duplicate)
            match_end = int(orig_line) + matched_length - 1

            # Get repeat count from the match
            repeat_count = 2  # At least 2 (original + this duplicate)

            annotation_info = (dup_start, dup_end, int(orig_line), match_end, repeat_count)

    # Write annotation before processing lines (if applicable)
    if annotation_info:
        write_annotation(
            output_buffer,
            annotation_format,
            delimiter,
            start=annotation_info[0],
            end=annotation_info[1],
            match_start=annotation_info[2],
            match_end=annotation_info[3],
            count=annotation_info[4],
            window_size=window_size,
        )

    # Output explain message for the entire matched sequence
    if explain and matched_length > 0 and len(line_buffer) >= matched_length:
        start_line = line_buffer[0].input_line_num
        end_line = line_buffer[matched_length - 1].input_line_num

        # Get original match info for explain message
        orig_line = match.get_original_line()

        if inverse:
            # Inverse mode: emitting duplicates
            if matched_length == 1:
                print_explain(
                    f"Line {start_line} emitted (duplicate in inverse mode, matched {orig_line})",
                    explain,
                )
            else:
                if orig_line == "preloaded":
                    print_explain(
                        f"Lines {start_line}-{end_line} emitted "
                        f"(duplicate in inverse mode, matched preloaded sequence)",
                        explain,
                    )
                else:
                    assert isinstance(orig_line, (int, float))
                    end_orig = int(orig_line) + matched_length - 1
                    print_explain(
                        f"Lines {start_line}-{end_line} emitted (duplicate in inverse mode, "
                        f"matched lines {int(orig_line)}-{end_orig})",
                        explain,
                    )
        else:
            # Normal mode: skipping duplicates
            if matched_length == 1:
                print_explain(f"Line {start_line} skipped (duplicate of {orig_line})", explain)
            else:
                if orig_line == "preloaded":
                    print_explain(
                        f"Lines {start_line}-{end_line} skipped "
                        f"(duplicate of preloaded sequence, seen 2x)",
                        explain,
                    )
                else:
                    assert isinstance(orig_line, (int, float))
                    end_orig = int(orig_line) + matched_length - 1
                    print_explain(
                        f"Lines {start_line}-{end_line} skipped "
                        f"(duplicate of lines {int(orig_line)}-{end_orig}, seen 2x)",
                        explain,
                    )

    # Record the diverged match range (don't consume lines yet -
    # let emit_merged_lines handle that)

    # Calculate the tracked line range for this match
    start_tracked_line = match.tracked_line_at_start
    end_tracked_line = match.tracked_line_at_start + matched_length - 1

    # Get original line for match info (needed for diverged_match_ranges)
    orig_line_for_range = match.get_original_line()

    # Record this diverged match so emit_merged_lines knows to skip these lines
    diverged_match_ranges.append((start_tracked_line, end_tracked_line, orig_line_for_range, 2))
