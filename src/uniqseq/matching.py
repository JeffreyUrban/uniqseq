"""Sequence matching and active match management."""

from collections.abc import Callable, Iterator
from typing import Optional, Union

from .recording import RecordedSequence


class ActiveMatchManager:
    """Manages active matches with max_candidates enforcement.

    Ensures that the number of concurrent matches doesn't exceed max_candidates.
    Prioritizes recorded sequence matches over history matches.
    """

    def __init__(self, max_candidates: Optional[int] = None):
        """Initialize the manager.

        Args:
            max_candidates: Maximum concurrent matches allowed (None for unlimited)
        """
        self.max_candidates = max_candidates
        self._matches: set[SubsequenceMatch] = set()

    def try_add(self, match: "SubsequenceMatch") -> bool:
        """Try to add a match, respecting max_candidates limit.

        Args:
            match: The match to add

        Returns:
            True if added, False if at capacity
        """
        # Check if at capacity
        if self.max_candidates is not None and len(self._matches) >= self.max_candidates:
            return False

        self._matches.add(match)
        return True

    def discard(self, match: "SubsequenceMatch") -> None:
        """Remove a match from the active set.

        Args:
            match: The match to remove
        """
        self._matches.discard(match)

    def clear(self) -> None:
        """Remove all matches."""
        self._matches.clear()

    def __iter__(self) -> Iterator["SubsequenceMatch"]:
        """Iterate over active matches."""
        return iter(self._matches)

    def __len__(self) -> int:
        """Return the number of active matches."""
        return len(self._matches)

    def __contains__(self, match: "SubsequenceMatch") -> bool:
        """Check if a match is active."""
        return match in self._matches


class SubsequenceMatch:
    """Base class to track an active match.

    Not to be instantiated. Use subclasses.
    """

    output_cursor_at_start: Union[int, float]  # Output cursor when match started
    tracked_line_at_start: int  # Tracked input line number when match started
    next_window_index: int = 1  # Which window to check next

    def get_window_hash(self, offset_from_match_start: int) -> Optional[str]:
        raise NotImplementedError("Use subclass")

    def record_match(
        self,
        number_of_windows_matched: int,
        matched_lines: Optional[list[Union[str, bytes]]] = None,
        save_callback: Optional[Callable[[Union[str, bytes]], None]] = None,
    ) -> None:
        raise NotImplementedError("Use subclass")

    def get_original_line(self) -> Union[int, float, str]:
        """Get the original line number or identifier for this match.

        Returns:
            Line number, float (for special cases like preloaded), or string identifier
        """
        raise NotImplementedError("Use subclass")


class RecordedSubsequenceMatch(SubsequenceMatch):
    def __init__(
        self,
        output_cursor_at_start: Union[int, float],
        tracked_line_at_start: int,
        recorded_sequence: RecordedSequence,
        delimiter: Union[str, bytes],
        match_start_window_offset_in_recorded_sequence: int = 0,
    ):
        self.output_cursor_at_start: Union[int, float] = output_cursor_at_start
        self.tracked_line_at_start: int = tracked_line_at_start
        self.next_window_index: int = 1
        self._recorded_sequence: RecordedSequence = recorded_sequence
        self._delimiter = delimiter
        self._match_start_window_offset: int = match_start_window_offset_in_recorded_sequence

    def get_window_hash(self, offset_from_match_start: int) -> Optional[str]:
        # Offset from match start + where match started in sequence = actual window position
        return self._recorded_sequence.get_window_hash(
            self._match_start_window_offset + offset_from_match_start
        )

    def record_match(
        self,
        number_of_windows_matched: int,
        matched_lines: Optional[list[Union[str, bytes]]] = None,
        save_callback: Optional[Callable[[Union[str, bytes]], None]] = None,
    ) -> None:
        # Delegate to the recorded sequence's record_match (polymorphic behavior)
        # Use positional argument to work with both RecordedSequence and HistorySequence
        self._recorded_sequence.record_match(
            number_of_windows_matched,
            self._match_start_window_offset,
            matched_lines=matched_lines,
            save_callback=save_callback,
            delimiter=self._delimiter,
        )

    def get_original_line(self) -> Union[int, float, str]:
        """Get the original line number or identifier for this match.

        Returns the output line number where this match started, accounting for where
        in the recorded sequence the match began.
        """
        return self._recorded_sequence.get_output_line_for_window(self._match_start_window_offset)
