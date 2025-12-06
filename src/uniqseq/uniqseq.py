"""Core logic for uniqseq."""

import hashlib
import re
import sys
from collections import Counter, defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import BinaryIO, Optional, TextIO, Union

MIN_SEQUENCE_LENGTH = 10
DEFAULT_MAX_HISTORY = 100000  # 100k window hashes = ~3.2 MB memory
DEFAULT_MAX_UNIQUE_SEQUENCES = 10000  # 10k sequences = ~320 KB memory
DEFAULT_MAX_CANDIDATES = 1000  # Default limit for concurrent candidates

# Sentinel value for preloaded sequences that were never observed in output
PRELOADED_SEQUENCE_LINE = float("-inf")

# Sentinel value for sequences whose first occurrence was never output (e.g., in inverse mode)
# Use a distinct large negative number (not -inf, since -inf - 1 == -inf)
NEVER_OUTPUT_LINE = -999_999_999.0


@dataclass
class BufferedLine:
    """A line in the buffer with its metadata."""

    line: Union[str, bytes]  # The actual line content
    line_hash: str  # Hash of the line
    input_line_num: int  # Input line number (1-indexed, includes all lines)
    tracked_line_num: int  # Tracked line number (1-indexed, tracked lines only)


@dataclass
class HistoryEntry:
    """An entry in the window hash history.

    Each entry corresponds to a window starting at a specific input position.
    Tracks where the first line of that window appeared in the output.
    """

    window_hash: str  # Hash of the window
    first_output_line: Optional[int] = (
        None  # Output line where window's first line was emitted (None until emitted)
    )


class PositionalFIFO:
    """
    Positional FIFO for window hash history.

    Maintains ordering and position tracking for window hashes without LRU reordering.
    Supports efficient lookup of all positions matching a given hash.
    Supports unlimited mode (maxsize=None) for unbounded growth.
    """

    __slots__ = [
        "maxsize",
        "position_to_entry",
        "key_to_positions",
        "next_position",
        "oldest_position",
    ]

    def __init__(self, maxsize: Optional[int]):
        """Initialize PositionalFIFO.

        Args:
            maxsize: Maximum size (int) or None for unlimited
        """
        self.maxsize = maxsize
        self.position_to_entry: dict[int, HistoryEntry] = {}  # position -> HistoryEntry
        self.key_to_positions: dict[str, list[int]] = {}  # window_hash -> [pos1, pos2, ...]
        self.next_position = 0
        self.oldest_position = 0

    def append(self, key: str) -> int:
        """Add key, return position. Evicts oldest if at capacity (unless unlimited)."""
        position = self.next_position

        # Evict oldest if at capacity (skip if unlimited)
        if self.maxsize is not None and len(self.position_to_entry) >= self.maxsize:
            old_entry = self.position_to_entry[self.oldest_position]
            old_key = old_entry.window_hash
            self.key_to_positions[old_key].remove(self.oldest_position)
            if not self.key_to_positions[old_key]:
                del self.key_to_positions[old_key]
            del self.position_to_entry[self.oldest_position]
            self.oldest_position += 1

        # Add new entry (first_output_line will be set later when first line is emitted)
        entry = HistoryEntry(window_hash=key, first_output_line=None)
        self.position_to_entry[position] = entry
        if key not in self.key_to_positions:
            self.key_to_positions[key] = []
        self.key_to_positions[key].append(position)
        self.next_position += 1

        return position

    def find_all_positions(self, key: str) -> list[int]:
        """Get all positions with this key."""
        result = self.key_to_positions.get(key, [])
        return list(result)  # Return copy to avoid mutation issues

    def get_key(self, position: int) -> Optional[str]:
        """Get window hash at position."""
        entry = self.position_to_entry.get(position)
        return entry.window_hash if entry else None

    def get_entry(self, position: int) -> Optional[HistoryEntry]:
        """Get history entry at position."""
        return self.position_to_entry.get(position)

    def get_next_position(self, position: int) -> int:
        """Get next position (position + 1).

        Note: History advances in lockstep with processing, so next position always exists
        when we're comparing. If this returns a position not in history, it indicates a bug.
        """
        return position + 1


def hash_line(line: Union[str, bytes], skip_chars: int = 0) -> str:
    """Hash a single line to 8-byte (16 hex char) string using Blake2b.

    Args:
        line: The line to hash (str or bytes)
        skip_chars: Number of characters/bytes to skip from the beginning before hashing

    Returns:
        16-character hex string (Blake2b 8-byte digest)
    """
    # Skip prefix if requested
    content = line[skip_chars:] if skip_chars > 0 else line

    # Convert to bytes if needed
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content

    return hashlib.blake2b(content_bytes, digest_size=8).hexdigest()


def hash_window(sequence_length: int, window_hashes: list[str]) -> str:
    """Hash a window of line hashes to 16-byte (32 hex char) string.

    Args:
        sequence_length: Total length of the sequence (for hash uniqueness)
        window_hashes: List of line hashes in the window

    Returns:
        32-character hex string (Blake2b 16-byte digest)
    """
    # Include sequence length to distinguish windows of different sequence lengths
    combined = str(sequence_length) + ":" + "".join(window_hashes)
    return hashlib.blake2b(combined.encode("ascii"), digest_size=16).hexdigest()


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
        sequence_records: dict[str, list[RecordedSequence]],
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

        first_hash = window_hashes[0]

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

        # Add to sequence records
        if first_hash not in self._sequence_records:
            self._sequence_records[first_hash] = []
        self._sequence_records[first_hash].append(record)

        # Index all windows of this new sequence
        for i, window_hash in enumerate(window_hashes):
            self._sequence_window_index[window_hash].append((record, i))

        # Save if callback provided
        if save_callback and matched_lines:
            file_content = self._delimiter.join(matched_lines)  # type: ignore[arg-type]
            save_callback(file_content)


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


@dataclass
class FilterPattern:
    """A filter pattern with its action.

    Patterns are evaluated sequentially. First match wins.
    """

    __slots__ = ["pattern", "action", "regex"]
    pattern: str  # Original pattern string
    action: str  # "track" or "bypass"
    regex: re.Pattern[str]  # Compiled regex pattern


class UniqSeq:
    """
    Streaming line sequence uniqseq with context-aware matching.

    Tracks WHERE sequences occur to enable proper duplicate detection.
    """

    def __init__(
        self,
        window_size: int = MIN_SEQUENCE_LENGTH,
        max_history: Optional[int] = DEFAULT_MAX_HISTORY,
        max_unique_sequences: Optional[int] = DEFAULT_MAX_UNIQUE_SEQUENCES,
        max_candidates: Optional[int] = DEFAULT_MAX_CANDIDATES,
        skip_chars: int = 0,
        hash_transform: Optional[Callable[[Union[str, bytes]], Union[str, bytes]]] = None,
        delimiter: Union[str, bytes] = "\n",
        preloaded_sequences: Optional[set[Union[str, bytes]]] = None,
        save_sequence_callback: Optional[Callable[[Union[str, bytes]], None]] = None,
        filter_patterns: Optional[list[FilterPattern]] = None,
        inverse: bool = False,
        annotate: bool = False,
        annotation_format: Optional[str] = None,
        explain: bool = False,
    ):
        """
        Initialize uniqseq.

        Args:
            window_size: Minimum sequence length to detect (default: 10)
            max_history: Maximum window hash history (default: 100000), or None for unlimited
            max_unique_sequences: Maximum unique sequences to track (default: 10000),
                                or None for unlimited
            max_candidates: Maximum concurrent candidates to track (default: 100),
                          or None for unlimited. Lower values improve performance but may
                          miss some patterns.
            skip_chars: Number of characters to skip from line start when hashing (default: 0)
            hash_transform: Optional function to transform line before hashing (default: None)
                          Function receives line (str or bytes) and returns transformed line
                          (str or bytes). Must return exactly one line per input
                          (no filtering/splitting)
            delimiter: Delimiter to use when writing output (default: "\n")
                      Should be str for text mode, bytes for binary mode
            preloaded_sequences: Optional set of sequence_content strings/bytes
                               to treat as "already seen". These sequences are skipped on
                               first observation and have unlimited retention (never evicted)
            save_sequence_callback: Optional callback(file_content) called when
                                  a sequence should be saved to library. Receives the raw
                                  file content (with delimiters).
                                  The callback computes its own hash.
            filter_patterns: Optional list of FilterPattern objects for sequential pattern matching.
                           Patterns are evaluated in order; first match determines action.
                           "track" = include for deduplication, "bypass" = pass through unchanged.
            inverse: If True, inverse mode: keep duplicates, remove unique sequences
                       (default: False)
            annotate: If True, add inline markers showing where duplicates were skipped
                     (default: False)
            annotation_format: Custom annotation template string. Variables: {start}, {end},
                             {match_start}, {match_end}, {count}, {window_size} (default: None)
            explain: If True, output explanations to stderr showing why lines were kept or skipped
                    (default: False)
        """
        self.window_size = window_size
        self.max_history = max_history
        self.max_unique_sequences = max_unique_sequences
        self.max_candidates = max_candidates
        self.skip_chars = skip_chars
        self.hash_transform = hash_transform
        self.delimiter = delimiter
        self.save_sequence_callback = save_sequence_callback
        self.filter_patterns = filter_patterns or []  # Sequential pattern matching
        self.inverse = inverse  # Inverse mode: keep duplicates, remove unique
        self.annotate = annotate  # Add inline markers for skipped duplicates
        # Set default annotation format if not provided
        self.annotation_format = annotation_format or (
            "[DUPLICATE: Lines {start}-{end} matched lines "
            "{match_start}-{match_end} (sequence seen {count} times)]"
        )
        self.explain = explain  # Show explanations to stderr

        # Positional FIFO for window hash history (tracks window hashes and output line numbers)
        self.window_hash_history = PositionalFIFO(maxsize=max_history)

        # Unique sequences (LRU-evicted at max_unique_sequences)
        # Two-level dict: first_window_hash -> {full_sequence_hash -> SequenceRecord}
        # Library of known sequences, keyed by first window hash
        self.sequence_records: dict[str, list[RecordedSequence]] = {}

        # Window index: maps every window hash in every sequence to (sequence, window_index)
        # This allows matching against any subsequence within a known sequence
        self.sequence_window_index: dict[str, list[tuple[RecordedSequence, int]]] = defaultdict(
            list
        )

        # Virtual sequence representing all of history (created after sequence_window_index)
        self.history_sequence = HistorySequence(
            self.window_hash_history,
            self.sequence_records,
            self.sequence_window_index,
            self.delimiter,
            self.window_size,
        )

        # Active matches being tracked
        self.active_matches: set[SubsequenceMatch] = set()

        # Diverged matches (lines that are duplicates and can be skipped when consumed)
        # List of (start_tracked_line, end_tracked_line, orig_line, repeat_count)
        self.diverged_match_ranges: list[tuple[int, int, Union[int, float, str], int]] = []

        # Load preloaded sequences into unique_sequences
        if preloaded_sequences:
            self._initialize_preloaded_sequences(preloaded_sequences)

        # Line buffer (grows beyond window_size to accommodate active matches)
        self.line_buffer: deque[BufferedLine] = deque()

        # Filtered lines buffer (separate from deduplication pipeline)
        # Stores (input_line_num, line) tuples for lines that bypass deduplication
        self.filtered_lines: deque[tuple[int, Union[str, bytes]]] = deque()

        # Output line tracking
        self.line_num_input = 0  # Lines read from input (all lines)
        self.line_num_input_tracked = 0  # Tracked lines read from input (excludes filtered)
        self.line_num_output = 0  # Lines written to output
        self.lines_skipped = 0  # Lines skipped as duplicates

    def _initialize_preloaded_sequences(self, preloaded_sequences: set[Union[str, bytes]]) -> None:
        """Initialize preloaded sequences into unique_sequences structure.

        Deduplicates fully nested subsequences:
        - Removes any sequence that is fully nested within a longer sequence
        - Among identical sequences, keeps only one

        Args:
            preloaded_sequences: Set of sequence_content strings/bytes
        """
        # First pass: compute window hashes for all sequences
        sequence_data = []  # List of (window_hashes,)

        for sequence in preloaded_sequences:
            # Split sequence into lines (WITHOUT delimiters to match process_line input)
            if isinstance(sequence, bytes):
                assert isinstance(self.delimiter, bytes)
                lines_without_delim: list[Union[str, bytes]] = list(sequence.split(self.delimiter))
            else:
                assert isinstance(self.delimiter, str)
                lines_without_delim = list(sequence.split(self.delimiter))

            sequence_length = len(lines_without_delim)

            # Skip if sequence is shorter than window size
            if sequence_length < self.window_size:
                continue

            # Compute line hashes (lines don't have delimiters, matching process_line)
            line_hashes = [hash_line(line) for line in lines_without_delim]

            # Compute all window hashes for this sequence
            seq_window_hashes = []
            for i in range(sequence_length - self.window_size + 1):
                window_hash = hash_window(self.window_size, line_hashes[i : i + self.window_size])
                seq_window_hashes.append(window_hash)

            sequence_data.append(tuple(seq_window_hashes))

        # Second pass: deduplicate nested and identical sequences
        deduplicated = self._deduplicate_nested_sequences(sequence_data)

        # Third pass: create RecordedSequence objects and add to data structures
        for window_hashes_tuple in deduplicated:
            window_hashes: list[str] = list(window_hashes_tuple)
            # Create RecordedSequence object with PRELOADED_SEQUENCE_LINE as first_output_line
            seq_rec = RecordedSequence(
                first_output_line=PRELOADED_SEQUENCE_LINE,
                window_hashes=window_hashes,
                counts=None,  # Preloaded sequences start with 0 matches
            )

            # Add to sequence library
            first_window_hash = window_hashes[0]
            if first_window_hash not in self.sequence_records:
                self.sequence_records[first_window_hash] = []
            self.sequence_records[first_window_hash].append(seq_rec)

            # Add all windows to the window index
            self._index_sequence_windows(seq_rec)

    def _deduplicate_nested_sequences(
        self, sequences: list[tuple[str, ...]]
    ) -> list[tuple[str, ...]]:
        """Remove sequences fully nested in longer sequences, and deduplicate identical.

        Args:
            sequences: List of window hash tuples

        Returns:
            Deduplicated list with only non-nested sequences (keeping one from each identical group)
        """
        if not sequences:
            return []

        # Track which sequences to keep (by index)
        to_keep = set(range(len(sequences)))

        # Check each pair of sequences
        for i in range(len(sequences)):
            if i not in to_keep:
                continue  # Already marked for removal

            seq_i = sequences[i]

            for j in range(len(sequences)):
                if i == j or j not in to_keep:
                    continue

                seq_j = sequences[j]

                # Check if seq_i is fully nested in seq_j
                if self._is_nested_in(seq_i, seq_j):
                    if len(seq_i) < len(seq_j):
                        # seq_i is shorter and nested in seq_j - remove seq_i
                        to_keep.discard(i)
                        break  # No need to check further for seq_i
                    elif len(seq_i) == len(seq_j):
                        # Same length and nested means they're identical - keep lower index
                        if i > j:
                            to_keep.discard(i)
                            break

        return [sequences[i] for i in sorted(to_keep)]

    def _is_nested_in(self, needle: tuple[str, ...], haystack: tuple[str, ...]) -> bool:
        """Check if needle sequence appears as a contiguous subsequence in haystack.

        Args:
            needle: The sequence to search for
            haystack: The sequence to search in

        Returns:
            True if needle appears contiguously in haystack, False otherwise
        """
        if len(needle) > len(haystack):
            return False

        if len(needle) == 0:
            return True

        # Search for needle in haystack at each position
        for start in range(len(haystack) - len(needle) + 1):
            if haystack[start : start + len(needle)] == needle:
                return True

        return False

    def _index_sequence_windows(self, sequence: RecordedSequence) -> None:
        """Add all windows of a sequence to the window index.

        Args:
            sequence: The sequence to index
        """
        # For each window in the sequence, add (sequence, window_index) to the index
        index = 0
        while True:
            window_hash = sequence.get_window_hash(index)
            if window_hash is None:
                break
            self.sequence_window_index[window_hash].append((sequence, index))
            index += 1

    def _print_explain(self, message: str) -> None:
        """Print explanation message to stderr if explain mode is enabled.

        Args:
            message: The explanation message to print
        """
        if self.explain:
            print(f"EXPLAIN: {message}", file=sys.stderr)

    def _evaluate_filter(self, line: Union[str, bytes]) -> tuple[Optional[str], Optional[str]]:
        """Evaluate filter patterns against a line.

        Args:
            line: The line to evaluate (str or bytes)

        Returns:
            Tuple of (action, pattern_string):
            - action: "bypass", "track", "no_match_allowlist", or None
            - pattern_string: The matched pattern string, or None if no match

        Note:
            Patterns are evaluated in order. First match wins.
            When track patterns exist, they act as allowlist (only tracked lines deduplicated).
            When only bypass patterns exist, they act as denylist (all but bypassed deduplicated).
            Currently only supports text mode (str lines).
        """
        if not self.filter_patterns:
            return (None, None)

        # Convert bytes to str for pattern matching (filters require text mode)
        line_str = line.decode("utf-8") if isinstance(line, bytes) else line

        # Evaluate patterns in order
        for filter_pattern in self.filter_patterns:
            if filter_pattern.regex.search(line_str):
                return (filter_pattern.action, filter_pattern.pattern)

        # No match - check if we have track patterns (allowlist mode)
        has_track_patterns = any(p.action == "track" for p in self.filter_patterns)
        if has_track_patterns:
            # Allowlist mode: only tracked lines are deduplicated
            # No match means pass through
            return ("no_match_allowlist", None)

        # No track patterns (denylist mode): deduplicate by default
        return (None, None)

    def process_line(
        self,
        line: Union[str, bytes],
        output: Union[TextIO, "BinaryIO"] = sys.stdout,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
    ) -> None:
        """
        Process a single line through multi-phase duplicate detection.

        Args:
            line: Line to process (without trailing newline/delimiter, str or bytes)
            output: Output stream (default: stdout)
            progress_callback: Optional callback(line_num, lines_skipped, seq_count)
                             called every 1000 lines with current statistics
        """
        self.line_num_input += 1

        # === FILTER EVALUATION: Determine if line should be deduplicated ===
        filter_action, matched_pattern = self._evaluate_filter(line)
        should_deduplicate = filter_action in ("track", None)

        # Filtered lines go to separate buffer, bypassing deduplication pipeline
        if not should_deduplicate:
            if filter_action == "bypass" and matched_pattern:
                action_desc = f"matched bypass pattern '{matched_pattern}'"
            elif filter_action == "no_match_allowlist":
                action_desc = "no track pattern matched (allowlist mode)"
            else:
                action_desc = "bypassed"
            self._print_explain(f"Line {self.line_num_input} bypassed ({action_desc})")
            self.filtered_lines.append((self.line_num_input, line))
            self._emit_merged_lines(output)
            return

        # For lines that participate in deduplication, continue with normal processing
        # Determine what to hash (apply transform if configured)
        line_for_hashing: Union[str, bytes]
        if self.hash_transform is not None:
            # Apply transform for hashing (but keep original line for output)
            line_for_hashing = self.hash_transform(line)
        else:
            line_for_hashing = line

        # Hash the line (with prefix skipping if configured)
        line_hash = hash_line(line_for_hashing, self.skip_chars)

        # Increment tracked line counter
        self.line_num_input_tracked += 1

        # Add to deduplication buffer with metadata
        buffered_line = BufferedLine(
            line=line,
            line_hash=line_hash,
            input_line_num=self.line_num_input,
            tracked_line_num=self.line_num_input_tracked,
        )
        self.line_buffer.append(buffered_line)

        # Need full window before processing deduplication
        if len(self.line_buffer) < self.window_size:
            return

        # Calculate window hash for current position
        window_line_hashes = [bl.line_hash for bl in list(self.line_buffer)[-self.window_size :]]
        current_window_hash = hash_window(self.window_size, window_line_hashes)

        # Update history sequence's current input position for overlap checking
        # Must be done BEFORE updating matches, so they can check overlap correctly
        current_window_start = self.line_num_input_tracked - self.window_size + 1
        self.history_sequence.current_input_position = current_window_start

        # === PHASE 1: Update existing active matches and collect divergences ===
        all_diverged = self._update_active_matches(current_window_hash)

        # Handle all diverged matches with smart deduplication
        self._handle_diverged_matches(all_diverged, output)

        # === PHASE 2: Start new potential matches ===
        self._check_for_new_uniq_matches(current_window_hash, output)

        # === PHASE 4: Add to history ===
        # The overlap check in _check_for_new_uniq_matches prevents matching against
        # overlapping positions, so we can add to history immediately
        history_position = self.window_hash_history.append(current_window_hash)

        # Index this window in the window index (maps to history_sequence at this position)
        self.sequence_window_index[current_window_hash].append(
            (self.history_sequence, history_position)
        )

        # === PHASE 5: Emit lines not consumed by active matches ===
        self._emit_merged_lines(output)

        # === PHASE 6: Call progress callback if provided ===
        if progress_callback and self.line_num_input % 1000 == 0:
            seq_count = sum(len(seqs) for seqs in self.sequence_records.values())
            progress_callback(self.line_num_input, self.lines_skipped, seq_count)

    def _emit_merged_lines(self, output: Union[TextIO, BinaryIO]) -> None:
        """Emit lines from both deduplication and filtered buffers in input order.

        Merges deduplicated lines and filtered lines, emitting them in the order
        they appeared in the input stream.
        """
        # Find minimum buffer depth for deduplication buffer (same logic as before)
        min_required_depth = self.window_size

        # Check active matches and calculate their buffer depth requirements
        for match in self.active_matches:
            # Calculate how many lines this match spans
            # window_size lines for the first window, then (next_window_index - 1) additional lines
            match_length = self.window_size + (match.next_window_index - 1)

            # Calculate buffer depth based on tracked line numbers
            # Buffer contains lines from (line_num_input_tracked - len(line_buffer) + 1)
            # to line_num_input_tracked. Match covers lines from tracked_line_at_start
            # to (tracked_line_at_start + match_length - 1)
            buffer_first_tracked = self.line_num_input_tracked - len(self.line_buffer) + 1
            match_first_tracked = match.tracked_line_at_start
            match_last_tracked = match.tracked_line_at_start + match_length - 1

            # Calculate overlap between buffer and match
            overlap_start = max(buffer_first_tracked, match_first_tracked)
            overlap_end = min(self.line_num_input_tracked, match_last_tracked)

            if overlap_end >= overlap_start:
                # Match has lines in buffer - calculate depth from start of match to end of buffer
                # This allows lines BEFORE the match to be emitted
                buffer_depth = self.line_num_input_tracked - overlap_start + 1
                if buffer_depth > min_required_depth:
                    min_required_depth = buffer_depth

        # OPTIMIZATION: Direct access to position_to_entry for faster lookups
        position_to_entry = self.window_hash_history.position_to_entry

        # Emit lines in order by comparing line numbers from both buffers
        line_buffer = self.line_buffer
        filtered_lines = self.filtered_lines

        while True:
            # OPTIMIZATION: Cache buffer lengths
            line_buffer_len = len(line_buffer)
            filtered_lines_len = len(filtered_lines)

            # Determine what we can emit from deduplication buffer
            dedup_can_emit = line_buffer_len > min_required_depth
            dedup_line_num: Union[int, float]
            if dedup_can_emit:
                first_line = line_buffer[0]
                dedup_line_num = first_line.input_line_num
            else:
                dedup_line_num = float("inf")

            # Filtered lines can only be emitted if they come before buffered uniqseq lines
            # This ensures we don't emit filtered lines ahead of earlier uniqseq lines
            filtered_can_emit = filtered_lines_len > 0
            filtered_line_num: Union[int, float]
            if filtered_can_emit and line_buffer_len > 0:
                # Check if filtered line comes before EARLIEST uniqseq line in buffer
                filtered_line_num = filtered_lines[0][0]
                earliest_dedup_line = line_buffer[0].input_line_num
                # Only emit filtered if it comes before earliest buffered uniqseq line
                filtered_can_emit = filtered_line_num < earliest_dedup_line
            elif filtered_can_emit:
                filtered_line_num = filtered_lines[0][0]
            else:
                filtered_line_num = float("inf")

            # Emit whichever has the lower line number (earlier in input)
            if dedup_can_emit and dedup_line_num <= filtered_line_num:
                # Emit from deduplication buffer
                buffered_line = line_buffer.popleft()

                # Check if this line is part of a diverged match (duplicate)
                is_duplicate = False
                for start, end, orig_line, count in self.diverged_match_ranges:
                    if start <= buffered_line.tracked_line_num <= end:
                        is_duplicate = True
                        # Remove this range if we've consumed all its lines
                        if buffered_line.tracked_line_num == end:
                            self.diverged_match_ranges.remove((start, end, orig_line, count))
                        break

                if is_duplicate:
                    if self.inverse:
                        # Inverse mode: emit duplicate lines
                        self._write_line(output, buffered_line.line)
                        self.line_num_output += 1
                    else:
                        # Normal mode: skip duplicate lines
                        self.lines_skipped += 1
                else:
                    # Unique line
                    if self.inverse:
                        # Inverse mode: skip unique lines
                        self.lines_skipped += 1
                        self._print_explain(
                            f"Line {buffered_line.input_line_num} skipped (unique in inverse mode)"
                        )
                    else:
                        # Normal mode: emit unique lines
                        self._write_line(output, buffered_line.line)
                        self.line_num_output += 1
                        # Explain only outputs messages about duplicates, not unique lines
                    # Update history entry for window starting at this line
                    # History position P corresponds to tracked line P+1 (0-indexed to 1-indexed)
                    # Use tracked_line_num instead of input_line_num to handle non-tracked lines
                    hist_pos = buffered_line.tracked_line_num - 1
                    entry = position_to_entry.get(hist_pos)
                    if entry and entry.first_output_line is None:
                        entry.first_output_line = self.line_num_output
            elif filtered_can_emit and filtered_line_num < dedup_line_num:
                # Emit from filtered buffer
                _, line = filtered_lines.popleft()
                self._write_line(output, line)
                self.line_num_output += 1
            else:
                # Nothing to emit
                break

    def flush(self, output: Union[TextIO, BinaryIO] = sys.stdout) -> None:
        """Emit remaining buffered lines at EOF."""
        # Handle any remaining active matches at EOF
        # These matches reached EOF without diverging, so they represent
        # complete matches up to the end of the input
        if self.active_matches:
            # Convert active matches to list for handling
            diverged_at_eof = list(self.active_matches)
            # Clear active matches before handling
            self.active_matches.clear()
            # Handle them like normal diverged matches
            self._handle_diverged_matches(diverged_at_eof, output)

        # Flush remaining lines from both buffers in order
        while self.line_buffer or self.filtered_lines:
            # Get line numbers from both buffers
            dedup_line_num = (
                self.line_buffer[0].input_line_num if self.line_buffer else float("inf")
            )
            filtered_line_num = self.filtered_lines[0][0] if self.filtered_lines else float("inf")

            # Emit whichever has the lower line number
            if dedup_line_num <= filtered_line_num:
                buffered_line = self.line_buffer.popleft()

                # Check if this line is part of a diverged match (duplicate)
                is_duplicate = False
                for start, end, orig_line, count in self.diverged_match_ranges:
                    if start <= buffered_line.tracked_line_num <= end:
                        is_duplicate = True
                        # Remove this range if we've consumed all its lines
                        if buffered_line.tracked_line_num == end:
                            self.diverged_match_ranges.remove((start, end, orig_line, count))
                        break

                if is_duplicate:
                    if self.inverse:
                        # Inverse mode: emit duplicate lines
                        self._write_line(output, buffered_line.line)
                        self.line_num_output += 1
                    else:
                        # Normal mode: skip duplicate lines
                        self.lines_skipped += 1
                else:
                    # Unique line
                    if self.inverse:
                        # Inverse mode: skip unique lines at EOF
                        self.lines_skipped += 1
                        self._print_explain(
                            f"Line {buffered_line.input_line_num} skipped at EOF "
                            "(unique in inverse mode)"
                        )
                    else:
                        # Normal mode: emit unique lines
                        self._write_line(output, buffered_line.line)
                        self.line_num_output += 1
                        # Explain only outputs messages about duplicates, not unique lines
            else:
                _, line = self.filtered_lines.popleft()
                self._write_line(output, line)
                self.line_num_output += 1

    def get_stats(self) -> dict[str, Union[int, float]]:
        """
        Get deduplication statistics.

        Returns:
            Dictionary with keys: total, emitted, skipped, redundancy_pct, unique_sequences
        """
        redundancy_pct = (
            100 * self.lines_skipped / self.line_num_input if self.line_num_input > 0 else 0.0
        )
        return {
            "total": self.line_num_input,
            "emitted": self.line_num_output,
            "skipped": self.lines_skipped,
            "redundancy_pct": redundancy_pct,
            "unique_sequences": sum(len(seqs) for seqs in self.sequence_records.values()),
        }

    def _update_active_matches(self, current_window_hash: str) -> list[SubsequenceMatch]:
        """Update all active matches.

        Returns:
            List of matches that diverged (matched_length available via match.next_window_index)
        """
        diverged = []

        for match in list(self.active_matches):
            # All active matches are SubsequenceMatch (polymorphic subclasses)
            expected = match.get_window_hash(match.next_window_index)

            if expected is None or current_window_hash != expected:
                # Diverged or reached end
                diverged.append(match)
                self.active_matches.discard(match)
            else:
                # Continue matching
                match.next_window_index += 1

        return diverged

    def _handle_diverged_matches(
        self,
        all_diverged: list[SubsequenceMatch],
        output: Union[TextIO, BinaryIO],
    ) -> None:
        """Handle diverged matches with smart deduplication.

        Strategy:
        1. Filter out incomplete subsequences (matches that end at same position but started later)
        2. Group matches by starting position
        3. For each group, check if any active match from same position is still running
        4. If no active matches from that position, record the longest diverged match
        5. Among matches of same length, record the earliest (by first_output_line)

        Args:
            all_diverged: List of diverged matches (matched_length available
                via match.next_window_index)
            output: Output stream for line emission
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
            match_length = self.window_size + (length - 1)
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
        # This ensures that when overlapping matches occur, we process the earliest one first
        # and later matches will fail the buffer size check
        for start_pos in sorted(by_start_pos.keys()):
            matches_at_pos = by_start_pos[start_pos]

            # Check if any active match is still running from this starting position
            has_active_from_pos = any(
                m.tracked_line_at_start == start_pos for m in self.active_matches
            )

            if has_active_from_pos:
                # Don't record yet - longer match may still be running
                continue

            # Find longest match(es) from this position
            max_length = max(m.next_window_index for m in matches_at_pos)
            longest_matches = [m for m in matches_at_pos if m.next_window_index == max_length]

            # If multiple matches of same length, pick earliest (by first_output_line)
            # For RecordedSubsequenceMatch, this comes from the RecordedSequence
            # For HistorySubsequenceMatch, we don't have a sequence yet
            if len(longest_matches) == 1:
                match_to_record = longest_matches[0]
            else:
                # Pick earliest based on sequence first_output_line (if available)
                # Choose the match with the earliest original line number
                # Preloaded sequences sort first (priority 0), then by line number, then pending
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
            # next_window_index is the number of windows matched
            # Each window covers window_size lines, but they overlap
            # So: first window = window_size lines, each additional window = 1 line
            matched_length = match_to_record.next_window_index
            lines_matched = self.window_size + (matched_length - 1)

            # Extract matched lines from buffer if save callback is configured
            matched_lines = None
            if self.save_sequence_callback and lines_matched <= len(self.line_buffer):
                matched_lines = [self.line_buffer[i].line for i in range(lines_matched)]

            # Record this match (polymorphic - will save for HistorySubsequenceMatch only)
            match_to_record.record_match(matched_length, matched_lines, self.save_sequence_callback)

            # Handle line skipping/outputting based on mode
            # The matched lines are at the START of the buffer
            self._handle_matched_lines(lines_matched, match_to_record, output)

    def _handle_matched_lines(
        self, matched_length: int, match: SubsequenceMatch, output: Union[TextIO, BinaryIO]
    ) -> None:
        """Skip or emit matched lines from the buffer based on mode.

        Args:
            matched_length: Number of lines that were matched
            match: The match object containing original position info
            output: Output stream
        """
        if matched_length <= 0 or matched_length > len(self.line_buffer):
            return

        # Collect annotation info before modifying buffer
        should_annotate = self.annotate and not self.inverse and matched_length > 0
        annotation_info = None

        if should_annotate and len(self.line_buffer) >= matched_length:
            dup_start = self.line_buffer[0].input_line_num
            dup_end = self.line_buffer[matched_length - 1].input_line_num

            # Get original match position
            orig_line = match.get_original_line()

            # Only annotate if orig_line is numeric (skip preloaded/pending)
            if isinstance(orig_line, (int, float)):
                # Calculate match_end (original sequence had same length as duplicate)
                match_end = int(orig_line) + matched_length - 1

                # Get repeat count from the match
                # For now, use a placeholder - proper count tracking requires more work
                repeat_count = 2  # At least 2 (original + this duplicate)

                annotation_info = (dup_start, dup_end, int(orig_line), match_end, repeat_count)

        # Write annotation before processing lines (if applicable)
        if annotation_info:
            self._write_annotation(
                output,
                start=annotation_info[0],
                end=annotation_info[1],
                match_start=annotation_info[2],
                match_end=annotation_info[3],
                count=annotation_info[4],
            )

        # Output explain message for the entire matched sequence
        if self.explain and matched_length > 0 and len(self.line_buffer) >= matched_length:
            start_line = self.line_buffer[0].input_line_num
            end_line = self.line_buffer[matched_length - 1].input_line_num

            # Get original match info for explain message
            orig_line = match.get_original_line()

            if self.inverse:
                # Inverse mode: emitting duplicates
                if matched_length == 1:
                    self._print_explain(
                        f"Line {start_line} emitted "
                        f"(duplicate in inverse mode, matched {orig_line})"
                    )
                else:
                    if orig_line == "preloaded":
                        self._print_explain(
                            f"Lines {start_line}-{end_line} emitted "
                            f"(duplicate in inverse mode, matched preloaded sequence)"
                        )
                    else:
                        assert isinstance(orig_line, (int, float))
                        end_orig = int(orig_line) + matched_length - 1
                        self._print_explain(
                            f"Lines {start_line}-{end_line} emitted (duplicate in inverse mode, "
                            f"matched lines {int(orig_line)}-{end_orig})"
                        )
            else:
                # Normal mode: skipping duplicates
                if matched_length == 1:
                    self._print_explain(f"Line {start_line} skipped (duplicate of {orig_line})")
                else:
                    if orig_line == "preloaded":
                        self._print_explain(
                            f"Lines {start_line}-{end_line} skipped "
                            f"(duplicate of preloaded sequence, seen 2x)"
                        )
                    else:
                        assert isinstance(orig_line, (int, float))
                        end_orig = int(orig_line) + matched_length - 1
                        self._print_explain(
                            f"Lines {start_line}-{end_line} skipped "
                            f"(duplicate of lines {int(orig_line)}-{end_orig}, seen 2x)"
                        )

        # Record the diverged match range (don't consume lines yet -
        # let _emit_merged_lines handle that)

        # Calculate the tracked line range for this match
        start_tracked_line = match.tracked_line_at_start
        end_tracked_line = match.tracked_line_at_start + matched_length - 1

        # Get original line for match info (needed for diverged_match_ranges)
        orig_line_for_range = match.get_original_line()

        # Record this diverged match so _emit_merged_lines knows to skip these lines
        self.diverged_match_ranges.append(
            (start_tracked_line, end_tracked_line, orig_line_for_range, 2)
        )

    def _check_for_new_uniq_matches(
        self, current_window_hash: str, output: Union[TextIO, BinaryIO] = sys.stdout
    ) -> None:
        """Check for new matches against all windows in all known sequences (including history)."""
        # Phase 3: Check against all windows in all sequences via the window index
        if current_window_hash not in self.sequence_window_index:
            return

        current_window_start = self.line_num_input_tracked - self.window_size + 1

        # Collect currently active (sequence, window_index) pairs to avoid redundant matches
        # All active matches are now RecordedSubsequenceMatch
        active_sequence_positions = {
            (m._recorded_sequence, m._match_start_window_offset + (m.next_window_index - 1))  # type: ignore[attr-defined]
            for m in self.active_matches
        }

        for seq, window_index in self.sequence_window_index[current_window_hash]:
            # Filter out overlapping sequences
            import math

            # Get sequence position using polymorphic method
            seq_position = seq.get_sequence_position(window_index, self.window_size)

            # Skip if overlapping with current window
            if (
                math.isfinite(seq_position)
                and seq_position + self.window_size > current_window_start
            ):
                continue

            # Skip if we already have an active match at this exact (sequence, position)
            if (seq, window_index) in active_sequence_positions:
                continue

            # Create RecordedSubsequenceMatch to track this match
            match = RecordedSubsequenceMatch(
                output_cursor_at_start=self.line_num_output,
                tracked_line_at_start=current_window_start,
                recorded_sequence=seq,
                delimiter=self.delimiter,
                match_start_window_offset_in_recorded_sequence=window_index,
            )
            # Track for future updates
            self.active_matches.add(match)

    def _write_line(self, output: Union[TextIO, BinaryIO], line: Union[str, bytes]) -> None:
        """Write a line to output with appropriate delimiter.

        Args:
            output: Output stream (text or binary)
            line: Line to write (str or bytes)
        """
        if isinstance(line, bytes):
            # Binary mode: write bytes with delimiter
            assert isinstance(self.delimiter, bytes), "Delimiter must be bytes in binary mode"
            output.write(line + self.delimiter)  # type: ignore
        else:
            # Text mode: write str with delimiter
            assert isinstance(self.delimiter, str), "Delimiter must be str in text mode"
            output.write(line + self.delimiter)  # type: ignore

    def _write_annotation(
        self,
        output: Union[TextIO, BinaryIO],
        start: int,
        end: int,
        match_start: int,
        match_end: int,
        count: int,
    ) -> None:
        """Write an annotation marker to output.

        Args:
            output: Output stream (text or binary)
            start: First line number of skipped sequence
            end: Last line number of skipped sequence
            match_start: First line number of matched sequence
            match_end: Last line number of matched sequence
            count: Total times sequence has been seen
        """
        if not self.annotate:
            return

        # Substitute template variables
        annotation = self.annotation_format.format(
            start=start,
            end=end,
            match_start=match_start,
            match_end=match_end,
            count=count,
            window_size=self.window_size,
        )

        # Write annotation using same delimiter as regular lines
        if isinstance(self.delimiter, bytes):
            output.write(annotation.encode("utf-8") + self.delimiter)  # type: ignore
        else:
            output.write(annotation + self.delimiter)  # type: ignore
