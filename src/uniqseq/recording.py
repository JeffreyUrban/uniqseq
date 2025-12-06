"""Sequence recording and retrieval with LRU eviction."""

from collections import Counter, OrderedDict
from collections.abc import Callable, Iterator
from typing import Optional, Union

from .history import PositionalFIFO

# Sentinel value for preloaded sequences that were never observed in output
PRELOADED_SEQUENCE_LINE = float("-inf")

# Sentinel value for sequences whose first occurrence was never output (e.g., in inverse mode)
# Use a distinct large negative number (not -inf, since -inf - 1 == -inf)
NEVER_OUTPUT_LINE = -999_999_999.0


class SequenceRegistry:
    """Registry for managing RecordedSequence objects with LRU eviction.

    Tracks sequences in LRU order and evicts least recently used when capacity is reached.
    Preloaded sequences are never evicted.
    """

    def __init__(self, max_sequences: Optional[int] = None):
        """Initialize the registry.

        Args:
            max_sequences: Maximum number of sequences to track (None for unlimited)
        """
        self.max_sequences = max_sequences
        # OrderedDict for LRU tracking: RecordedSequence -> None
        self._sequences: OrderedDict[RecordedSequence, None] = OrderedDict()
        # Fast lookup by first hash: first_hash -> list of sequences
        self._by_first_hash: dict[str, list[RecordedSequence]] = {}

    def add(self, sequence: "RecordedSequence") -> None:
        """Add a sequence to the registry with LRU eviction if needed.

        Args:
            sequence: The sequence to add
        """
        is_preloaded = sequence.first_output_line == PRELOADED_SEQUENCE_LINE

        # Check if we need to evict (count only non-preloaded sequences)
        if self.max_sequences is not None and not is_preloaded:
            # Count non-preloaded sequences
            non_preloaded_count = sum(
                1 for seq in self._sequences if seq.first_output_line != PRELOADED_SEQUENCE_LINE
            )

            # If max is 0, don't add any non-preloaded sequences
            if self.max_sequences == 0:
                return

            while non_preloaded_count >= self.max_sequences:
                # Evict least recently used non-preloaded sequence
                evicted = False
                for seq in list(self._sequences.keys()):
                    if seq.first_output_line != PRELOADED_SEQUENCE_LINE:
                        # Found a non-preloaded sequence to evict
                        del self._sequences[seq]
                        # Remove from first_hash index
                        first_hash = seq.get_window_hash(0)
                        if first_hash and first_hash in self._by_first_hash:
                            self._by_first_hash[first_hash].remove(seq)
                            if not self._by_first_hash[first_hash]:
                                del self._by_first_hash[first_hash]
                        evicted = True
                        non_preloaded_count -= 1
                        break

                if not evicted:
                    # All sequences are preloaded, can't evict
                    break

        # Add to LRU tracker
        self._sequences[sequence] = None

        # Add to first_hash index
        first_hash = sequence.get_window_hash(0)
        if first_hash:
            if first_hash not in self._by_first_hash:
                self._by_first_hash[first_hash] = []
            self._by_first_hash[first_hash].append(sequence)

    def mark_accessed(self, sequence: "RecordedSequence") -> None:
        """Mark a sequence as recently accessed (move to end of LRU).

        Args:
            sequence: The sequence that was accessed
        """
        if sequence in self._sequences:
            self._sequences.move_to_end(sequence)

    def get_by_first_hash(self, first_hash: str) -> "list[RecordedSequence]":
        """Get all sequences with a given first window hash.

        Args:
            first_hash: The first window hash to look up

        Returns:
            List of sequences (empty if none found)
        """
        return self._by_first_hash.get(first_hash, [])

    def __iter__(self) -> Iterator["RecordedSequence"]:
        """Iterate over all sequences in LRU order (oldest first)."""
        return iter(self._sequences.keys())

    def __len__(self) -> int:
        """Return the number of sequences in the registry."""
        return len(self._sequences)

    def __contains__(self, sequence: "RecordedSequence") -> bool:
        """Check if a sequence is in the registry."""
        return sequence in self._sequences


class RecordedSequence:
    """A recorded sequence - fully known sequence in the library.

    All data beyond KnownSequence interface is private.
    """

    def __init__(
        self,
        first_output_line: Union[int, float],
        window_hashes: list[str],
        counts: Optional[dict[tuple[int, int], int]],
    ):
        self.first_output_line = first_output_line
        self._window_hashes = window_hashes
        # Maps (start_window_offset, end_window_offset) -> count of matches for that subsequence
        self.subsequence_match_counts: Counter[tuple[int, int]] = Counter()
        if counts:
            for key, count in counts.items():
                self.subsequence_match_counts[key] = count

    def get_window_hash(self, window_index_in_recorded_sequence: int) -> Optional[str]:
        """Lookup window hash at index in this recorded sequence."""
        if 0 <= window_index_in_recorded_sequence < len(self._window_hashes):
            return self._window_hashes[window_index_in_recorded_sequence]
        return None

    def get_sequence_position(self, window_index: int, window_size: int) -> Union[int, float]:
        """Get the position of a window within this sequence for overlap checking.

        Args:
            window_index: Index of the window within this sequence
            window_size: Size of the window

        Returns:
            Position value for overlap checking
        """
        import math

        if not math.isfinite(self.first_output_line):
            # Preloaded sequence without position - return -inf to allow matching
            return -float("inf")
        # Position is first_output_line offset by window_index
        return int(self.first_output_line) + window_index

    def get_output_line_for_window(self, window_index: int) -> Union[int, float, str]:
        """Get the output line number where a window was first emitted.

        Args:
            window_index: Index of the window within this sequence

        Returns:
            Output line number (1-indexed), float for special cases, or "preloaded"
        """
        import math

        if not math.isfinite(self.first_output_line):
            return "preloaded"
        return int(self.first_output_line) + window_index

    def record_match(
        self,
        number_of_windows_matched: int,
        match_start_window_offset_in_recorded_sequence: int = 0,
        matched_lines: Optional[list[Union[str, bytes]]] = None,
        save_callback: Optional[Callable[[Union[str, bytes]], None]] = None,
        delimiter: Union[str, bytes, None] = None,
    ) -> None:
        """Record match count.

        Args:
            number_of_windows_matched: How many consecutive windows were matched
            match_start_window_offset_in_recorded_sequence: Which window in this
                sequence the match started from
            matched_lines: Matched lines for saving
            save_callback: Callback for saving sequences
            delimiter: Delimiter for joining lines (needed for saving)
        """
        # Track which subsequence (start, end) was matched
        end_window_offset = (
            match_start_window_offset_in_recorded_sequence + number_of_windows_matched
        )
        self.subsequence_match_counts[
            (match_start_window_offset_in_recorded_sequence, end_window_offset)
        ] += 1

        # Handle saving for preloaded/recorded sequences if callback provided
        if save_callback and matched_lines and delimiter is not None:
            file_content = delimiter.join(matched_lines)  # type: ignore[arg-type]
            save_callback(file_content)


class HistorySequence(RecordedSequence):
    """Virtual sequence representing all of history.

    This is a special RecordedSequence that delegates to the history FIFO,
    allowing history to be treated uniformly with other recorded sequences.
    """

    def __init__(
        self,
        history: PositionalFIFO,
        sequence_records: SequenceRegistry,
        sequence_window_index: dict[str, list[tuple[RecordedSequence, int]]],
        delimiter: Union[str, bytes],
        window_size: int,
    ):
        # Don't call super().__init__ - we override everything
        self.first_output_line = 0  # History starts at line 0
        self._history = history
        self._sequence_records = sequence_records
        self._sequence_window_index = sequence_window_index
        self._delimiter = delimiter
        self._window_size = window_size
        # Track current input position to prevent overlap
        self.current_input_position: Optional[int] = None
        # No window_hashes or match_counts - history manages this differently

    def get_window_hash(self, history_fifo_position: int) -> Optional[str]:
        """Lookup window hash at history position.

        Returns None if the requested position overlaps with current input window.
        """
        # Check if this position overlaps with current input
        if self.current_input_position is not None:
            # History position `history_fifo_position` was added at tracked line
            # `history_fifo_position + 1`. That window covers tracked lines
            # [history_fifo_position+1, history_fifo_position+window_size].
            # Current input window starts at current_input_position (tracked line number)
            # They overlap if history window extends into or past current window start:
            # history_fifo_position + window_size >= current_input_position
            if history_fifo_position + self._window_size >= self.current_input_position:
                return None

        return self._history.get_key(history_fifo_position)

    def get_sequence_position(self, window_index: int, window_size: int) -> Union[int, float]:
        """Get the position of a window within history for overlap checking.

        History position `window_index` was added at tracked line `window_index + 1`.
        Returns the tracked line number where this window starts.
        """
        return window_index + 1

    def get_output_line_for_window(self, window_index: int) -> Union[int, float, str]:
        """Get the output line number where a history window was first emitted.

        Args:
            window_index: History position

        Returns:
            Output line number (1-indexed), or "pending" if not yet emitted
        """
        entry = self._history.get_entry(window_index)
        if entry and entry.first_output_line is not None:
            return entry.first_output_line
        # Not yet emitted - this should not happen due to overlap checks,
        # but return explicit string rather than misleading numeric value
        return "pending"

    def record_match(
        self,
        number_of_windows_matched: int,
        match_start_position_in_history: int = 0,
        matched_lines: Optional[list[Union[str, bytes]]] = None,
        save_callback: Optional[Callable[[Union[str, bytes]], None]] = None,
        delimiter: Union[str, bytes, None] = None,
    ) -> None:
        """Record a match from history - creates a new RecordedSequence.

        Args:
            number_of_windows_matched: How many consecutive windows were matched
            match_start_position_in_history: Which position in history FIFO the match started from
            matched_lines: The matched lines (for saving)
            save_callback: Optional callback for saving sequences
            delimiter: Delimiter for joining lines (use instance delimiter if not provided)
        """
        # Use instance delimiter if not provided
        if delimiter is None:
            delimiter = self._delimiter
        # Collect window hashes from history
        window_hashes = []
        for i in range(number_of_windows_matched):
            h = self.get_window_hash(match_start_position_in_history + i)
            if h is None:
                break
            window_hashes.append(h)

        if not window_hashes:
            return

        # Create a new RecordedSequence for this discovered pattern
        # Use the history position as the first_output_line
        history_entry = self._history.get_entry(match_start_position_in_history)
        first_output_line = (
            history_entry.first_output_line
            if history_entry and history_entry.first_output_line is not None
            else match_start_position_in_history
        )

        record = RecordedSequence(
            first_output_line=first_output_line,
            window_hashes=window_hashes,
            counts=None,
        )

        # Add to sequence registry
        self._sequence_records.add(record)

        # Index all windows of this new sequence
        for i, window_hash in enumerate(window_hashes):
            self._sequence_window_index[window_hash].append((record, i))

        # Save if callback provided
        if save_callback and matched_lines:
            file_content = self._delimiter.join(matched_lines)  # type: ignore[arg-type]
            save_callback(file_content)
