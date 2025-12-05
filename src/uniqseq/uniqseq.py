"""Core logic for uniqseq."""

import hashlib
import re
import sys
from collections import OrderedDict, deque, Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import BinaryIO, Optional, TextIO, Union

MIN_SEQUENCE_LENGTH = 10
DEFAULT_MAX_HISTORY = 100000  # 100k window hashes = ~3.2 MB memory
DEFAULT_MAX_UNIQUE_SEQUENCES = 10000  # 10k sequences = ~320 KB memory
DEFAULT_MAX_CANDIDATES = 100  # Default limit for concurrent candidates

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
    def __init__(self, first_output_line: Union[int, float], window_hashes: list[str], counts: Optional[dict[int, int]]):
        self.first_output_line = first_output_line
        self._window_hashes = window_hashes
        self.subsequence_match_counts = Counter()  # count of matches at that subsequence length
        if counts:
            for index, count in counts:
                self.subsequence_match_counts[index] = count

    def get_window_hash(self, index: int) -> Optional[str]:
        """Lookup window hash at index."""
        if 0 <= index < len(self._window_hashes):
            return self._window_hashes[index]
        return None

    def record_match(self, index: int) -> None:
        """Record match count at index."""
        self.subsequence_match_counts[index] += 1


class SubsequenceMatch:
    """Base class to track an active match.

    Not to be instantiated. Use subclasses.
    """

    output_cursor_at_start: int  # Output cursor when match started
    tracked_line_at_start: int  # Tracked input line number when match started
    next_window_index: int = 1  # Which window to check next

    # TODO: Consider refactoring, since we likely don't need to get hashes for arbitrary indices
    def get_window_hash(self, index: int) -> Optional[str]:
        raise NotImplementedError("Use subclass")

    def record_match(self, index: int) -> None:
        raise NotImplementedError("Use subclass")


class RecordedSubsequenceMatch(SubsequenceMatch):
    def __init__(self, output_cursor_at_start, tracked_line_at_start, recorded_sequence: RecordedSequence):
        self.output_cursor_at_start: Union[int, float] = output_cursor_at_start
        self.tracked_line_at_start: int = tracked_line_at_start
        self.next_window_index: int = 1
        self._recorded_sequence: RecordedSequence = recorded_sequence

    def get_window_hash(self, index: int) -> Optional[str]:
        return self._recorded_sequence.get_window_hash(index)

    def record_match(self, index: int) -> None:
        return self._recorded_sequence.record_match(index)


class HistorySubsequenceMatch(SubsequenceMatch):
    def __init__(
        self,
        output_cursor_at_start: int,
        tracked_line_at_start: int,
        first_position: int,
        history: PositionalFIFO,
        sequence_records: dict[str, list[RecordedSequence]],
    ):
        self.output_cursor_at_start: int = output_cursor_at_start
        self.tracked_line_at_start: int = tracked_line_at_start
        self.next_window_index: int = 1
        self._first_position: int = first_position
        self._history: PositionalFIFO = history
        self._sequence_records = sequence_records

    def get_window_hash(self, index: int) -> Optional[str]:
        """Lookup window hash at index."""
        return self._history.get_key(self._first_position + index)

    def record_match(self, index: int) -> None:
        """Record match count at index."""
        # Create a new RecordedSequence for this history match
        window_hashes = [self.get_window_hash(i) for i in range(index)]
        record = RecordedSequence(
            first_output_line=self.output_cursor_at_start,
            window_hashes=window_hashes,
            counts=None,
        )
        # Add to the sequence records for future matching
        first_hash = self.get_window_hash(0)
        if first_hash not in self._sequence_records:
            self._sequence_records[first_hash] = []
        self._sequence_records[first_hash].append(record)


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
        preloaded_sequences: Optional[dict[str, Union[str, bytes]]] = None,
        save_sequence_callback: Optional[Callable[[str, list[Union[str, bytes]]], None]] = None,
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
            preloaded_sequences: Optional dict mapping sequence_hash -> sequence_content
                               to treat as "already seen". These sequences are skipped on
                               first observation and have unlimited retention (never evicted)
            save_sequence_callback: Optional callback(sequence_hash, sequence_lines) called when
                                  a sequence should be saved to library. Receives the full
                                  sequence hash and list of lines in the sequence.
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
        self.saved_sequences: set[str] = set()  # Track which sequences have been saved
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

        # Active matches being tracked
        self.active_matches: set[SubsequenceMatch] = set()

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

    def _initialize_preloaded_sequences(
        self, preloaded_sequences: dict[str, Union[str, bytes]]
    ) -> None:
        """Initialize preloaded sequences into unique_sequences structure.

        TODO: Need to deduplicate subsequences (the same from the start, to the end of the shorter one), keeping only
        one longest.

        Args:
            preloaded_sequences: Dict mapping sequence_hash -> sequence_content
        """
        for seq_hash, sequence in preloaded_sequences.items():
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
            window_hashes = []
            for i in range(sequence_length - self.window_size + 1):
                window_hash = hash_window(self.window_size, line_hashes[i : i + self.window_size])
                window_hashes.append(window_hash)

            # Get first window hash
            first_window_hash = window_hashes[0]

            # Create RecordedSequence object with PRELOADED_SEQUENCE_LINE as first_output_line
            seq_rec = RecordedSequence(
                first_output_line=PRELOADED_SEQUENCE_LINE,
                window_hashes=window_hashes,
                counts=None,  # Preloaded sequences start with 0 matches
            )

            # Add to sequence library
            if first_window_hash not in self.sequence_records:
                self.sequence_records[first_window_hash] = []
            self.sequence_records[first_window_hash].append(seq_rec)

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

        # === PHASE 1: Update existing active matches and collect divergences ===
        all_diverged = self._update_active_matches(current_window_hash)

        # Handle all diverged matches with smart deduplication
        self._handle_diverged_matches(all_diverged, output)

        # === PHASE 2: Start new potential matches ===
        self._check_for_new_uniq_matches(current_window_hash, output)

        # === PHASE 4: Add to history ===
        # The overlap check in _check_for_new_uniq_matches prevents matching against
        # overlapping positions, so we can add to history immediately
        self.window_hash_history.append(current_window_hash)

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
            # Buffer contains lines from (line_num_input_tracked - len(line_buffer) + 1) to line_num_input_tracked
            # Match covers lines from tracked_line_at_start to (tracked_line_at_start + match_length - 1)
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

                if self.inverse:
                    # Inverse mode: skip unique lines (these are first occurrences or truly unique)
                    self.lines_skipped += 1
                    self._print_explain(f"Line {buffered_line.input_line_num} skipped (unique in inverse mode)")
                else:
                    # Normal mode: emit unique lines
                    self._write_line(output, buffered_line.line)
                    self.line_num_output += 1
                    # Explain only outputs messages about duplicates, not unique lines
                    pass
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
            # Convert active matches to diverged format (match, matched_length)
            diverged_at_eof = [
                (match, match.next_window_index) for match in self.active_matches
            ]
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

                if self.inverse:
                    # Inverse mode: skip unique lines at EOF
                    self.lines_skipped += 1
                    self._print_explain(f"Line {buffered_line.input_line_num} skipped at EOF (unique in inverse mode)")
                else:
                    # Normal mode: emit unique lines
                    self._write_line(output, buffered_line.line)
                    self.line_num_output += 1
                    # Explain only outputs messages about duplicates, not unique lines
                    pass
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

    def _update_active_matches(
        self, current_window_hash: str
    ) -> list[tuple[SubsequenceMatch, int]]:
        """Update all active matches.
        TODO: SubsequenceMatch already keeps track of the matched_length via next_window_index.

        Returns:
            List of (match, matched_length) tuples for matches that diverged
        """
        diverged = []

        for match in list(self.active_matches):
            # All active matches are SubsequenceMatch (polymorphic subclasses)
            expected = match.get_window_hash(match.next_window_index)

            if expected is None or current_window_hash != expected:
                # Diverged or reached end
                diverged.append((match, match.next_window_index))
                self.active_matches.discard(match)
            else:
                # Continue matching
                match.next_window_index += 1

        return diverged

    def _handle_diverged_matches(
        self,
        all_diverged: list[tuple[SubsequenceMatch, int]],
        output: Union[TextIO, BinaryIO],
    ) -> None:
        """Handle diverged matches with smart deduplication.

        Strategy:
        1. Group matches by starting position
        2. For each group, check if any active match from same position is still running
        3. If no active matches from that position, record the longest diverged match
        4. Among matches of same length, record the earliest (by first_output_line)

        Args:
            all_diverged: List of (match, matched_length) tuples
            output: Output stream for line emission
        """
        if not all_diverged:
            return

        # Group diverged matches by starting position (INPUT line, not output line)
        from collections import defaultdict
        by_start_pos: dict[int, list[tuple[SubsequenceMatch, int]]] = defaultdict(list)
        for match, length in all_diverged:
            by_start_pos[match.tracked_line_at_start].append((match, length))

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
            max_length = max(length for _, length in matches_at_pos)
            longest_matches = [(m, l) for m, l in matches_at_pos if l == max_length]

            # If multiple matches of same length, pick earliest (by first_output_line)
            # For RecordedSubsequenceMatch, this comes from the RecordedSequence
            # For HistorySubsequenceMatch, we don't have a sequence yet
            if len(longest_matches) == 1:
                match_to_record, matched_length = longest_matches[0]
            else:
                # Pick earliest based on sequence first_output_line (if available)
                def get_first_output_line(m: SubsequenceMatch) -> Union[int, float]:
                    if isinstance(m, RecordedSubsequenceMatch):
                        return m._recorded_sequence.first_output_line
                    else:
                        # HistorySubsequenceMatch - use match start position as tiebreaker
                        return m.output_cursor_at_start

                match_to_record, matched_length = min(
                    longest_matches, key=lambda x: get_first_output_line(x[0])
                )

            # Record this match at this window index
            match_to_record.record_match(matched_length)

            # Calculate actual number of lines matched
            # matched_length is next_window_index (number of windows matched)
            # Each window covers window_size lines, but they overlap
            # So: first window = window_size lines, each additional window = 1 line
            lines_matched = self.window_size + (matched_length - 1)

            # Call save callback if configured and sequence not yet saved
            if self.save_sequence_callback and lines_matched <= len(self.line_buffer):
                # Extract the matched lines from buffer
                matched_lines = [
                    self.line_buffer[i].line for i in range(lines_matched)
                ]

                # Compute sequence hash
                from uniqseq.library import compute_sequence_hash
                if isinstance(self.delimiter, bytes):
                    seq_content = self.delimiter.join(matched_lines)
                else:
                    seq_content = self.delimiter.join(matched_lines)
                seq_hash = compute_sequence_hash(seq_content, self.delimiter, self.window_size)

                # Call callback if not already saved
                if seq_hash not in self.saved_sequences:
                    self.save_sequence_callback(seq_hash, matched_lines)
                    self.saved_sequences.add(seq_hash)

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
            if isinstance(match, RecordedSubsequenceMatch):
                orig_line = int(match._recorded_sequence.first_output_line)
            else:
                # HistorySubsequenceMatch - use output_cursor_at_start as approximation
                orig_line = int(match.output_cursor_at_start)

            # Calculate match_end (original sequence had same length as duplicate)
            match_end = orig_line + matched_length - 1

            # Get repeat count from the match
            # For now, use a placeholder - proper count tracking requires more work
            repeat_count = 2  # At least 2 (original + this duplicate)

            annotation_info = (dup_start, dup_end, orig_line, match_end, repeat_count)

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
            if isinstance(match, RecordedSubsequenceMatch):
                orig_line = int(match._recorded_sequence.first_output_line)
            else:
                orig_line = int(match.output_cursor_at_start)

            if self.inverse:
                # Inverse mode: emitting duplicates
                if matched_length == 1:
                    self._print_explain(f"Line {start_line} emitted (duplicate in inverse mode, matched line {orig_line})")
                else:
                    self._print_explain(f"Lines {start_line}-{end_line} emitted (duplicate in inverse mode, matched lines {orig_line}-{orig_line + matched_length - 1})")
            else:
                # Normal mode: skipping duplicates
                if matched_length == 1:
                    self._print_explain(f"Line {start_line} skipped (duplicate of line {orig_line})")
                else:
                    self._print_explain(f"Lines {start_line}-{end_line} skipped (duplicate of lines {orig_line}-{orig_line + matched_length - 1}, seen 2x)")

        # Process the matched lines
        for _ in range(matched_length):
            if not self.line_buffer:
                break

            buffered_line = self.line_buffer.popleft()

            if self.inverse:
                # Inverse mode: emit duplicate lines
                self._write_line(output, buffered_line.line)
                self.line_num_output += 1
            else:
                # Normal mode: skip duplicate lines
                self.lines_skipped += 1

    def _check_for_new_uniq_matches(
        self, current_window_hash: str, output: Union[TextIO, BinaryIO] = sys.stdout
    ) -> None:
        """Check for new matches against known sequences or history."""
        # Phase 3a: Check against known sequences
        if current_window_hash in self.sequence_records:
            # Found potential match(es) against known sequence(s)
            current_window_start = self.line_num_input_tracked - self.window_size + 1

            for seq in self.sequence_records[current_window_hash]:
                # Filter out overlapping sequences
                # seq.first_output_line is the output line number, but we need the tracked input line number
                # For sequences created from history, first_output_line approximately equals the tracked position
                # Skip if sequence would overlap with current window
                # Handle infinity (preloaded sequences may have inf as first_output_line)
                import math
                if not math.isfinite(seq.first_output_line):
                    # Preloaded sequence without position info - don't filter it
                    pass
                elif int(seq.first_output_line) + self.window_size > current_window_start:
                    # Overlapping sequence, skip it
                    continue

                # Create RecordedSubsequenceMatch to track this match
                # Match starts at the first line of the current window
                match = RecordedSubsequenceMatch(
                    output_cursor_at_start=self.line_num_output,
                    tracked_line_at_start=self.line_num_input_tracked - self.window_size + 1,
                    recorded_sequence=seq,
                )
                # Track for future updates
                self.active_matches.add(match)

        # Phase 3b: Check against history to create new HistorySubsequenceMatch instances
        history_positions = self.window_hash_history.find_all_positions(current_window_hash)

        if history_positions:
            # Filter out overlapping positions
            # Position P in history corresponds to tracked line P (0-indexed history, 1-indexed lines)
            # A window at position P covers tracked lines [P, P+1, ..., P+window_size-1]
            # Current window starts at current_window_start and covers [current_window_start, ..., current_window_start+window_size-1]
            # Windows overlap if: P + window_size > current_window_start
            # So we only include: P + window_size <= current_window_start
            current_window_start = self.line_num_input_tracked - self.window_size + 1
            non_overlapping = [
                pos for pos in history_positions if pos + self.window_size < current_window_start
            ]

            for first_pos in non_overlapping:
                # Create HistorySubsequenceMatch to track this match
                # Match starts at the first line of the current window
                match = HistorySubsequenceMatch(
                    output_cursor_at_start=self.line_num_output,
                    tracked_line_at_start=self.line_num_input_tracked - self.window_size + 1,
                    first_position=first_pos,
                    history=self.window_hash_history,
                    sequence_records=self.sequence_records,
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
