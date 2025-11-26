"""Core logic for uniqseq."""

import hashlib
import re
import sys
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import BinaryIO, Optional, TextIO, Union

MIN_SEQUENCE_LENGTH = 10
DEFAULT_MAX_HISTORY = 100000  # 100k window hashes = ~3.2 MB memory
DEFAULT_MAX_UNIQUE_SEQUENCES = 10000  # 10k sequences = ~320 KB memory

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
    input_line_num: int  # Input line number (1-indexed)


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


@dataclass
class SequenceRecord:
    """A unique sequence identified during processing.

    Note: No __slots__ because we have a list field (window_hashes) that grows dynamically.
    """

    first_window_hash: str  # Hash of first window
    full_sequence_hash: str  # Hash identifying the sequence (length + all window hashes)
    first_output_line: Union[
        int, float
    ]  # Output line number where first line appeared (or PRELOADED_SEQUENCE_LINE if preloaded)
    sequence_length: int  # Number of lines in sequence
    duplicate_count: int  # How many duplicates seen (excluding first occurrence)
    window_hashes: list[str] = field(default_factory=list)  # ALL window hashes (one per line)


@dataclass
class NewSequenceCandidate:
    """A new sequence being built from current input, tracked until finalized.

    Note: No __slots__ because we have list fields that grow dynamically.
    Created only when window hash matches history (not for SequenceRecord matches).
    """

    output_cursor_at_start: int  # Output cursor position when candidate was created
    first_input_line: int  # Input line number where sequence starts (0-indexed)
    length: int  # Number of lines matched so far
    window_hashes: list[str] = field(default_factory=list)  # ALL window hashes
    first_window_hash: str = ""  # First window hash
    buffer_depth: int = 0  # How many lines deep in buffer this extends

    # Tracking which history positions still match
    matching_history_positions: set[int] = field(default_factory=set)
    # Original first matching position (for output line lookup after finalization)
    original_first_history_position: int = 0


@dataclass
class PotentialSeqRecMatch:
    """Tracking potential duplicate of a previously identified sequence.

    Note: Direct duplicates are handled immediately without creating a NewSequenceCandidate.
    """

    __slots__ = ["matched_sequence", "output_cursor_at_start", "next_window_index", "window_size"]
    matched_sequence: "SequenceRecord"  # Existing sequence we're comparing to
    output_cursor_at_start: int  # Output cursor position when match started
    next_window_index: int  # Index in matched_sequence.window_hashes for next expected window
    window_size: int  # Window size (needed to calculate length)

    def get_length(self) -> int:
        """Calculate how many lines matched so far."""
        return self.window_size + (self.next_window_index - 1)

    def get_buffer_depth(self, line_num_output: int) -> int:
        """Calculate how deep in buffer this match extends."""
        length = self.get_length()
        return (self.output_cursor_at_start - line_num_output) + length


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
        max_unique_sequences: int = DEFAULT_MAX_UNIQUE_SEQUENCES,
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
            max_unique_sequences: Maximum unique sequences to track (default: 10000)
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
        self.sequence_records: OrderedDict[str, dict[str, SequenceRecord]] = OrderedDict()

        # Load preloaded sequences into unique_sequences
        if preloaded_sequences:
            self._initialize_preloaded_sequences(preloaded_sequences)

        # New sequences being built from current input
        self.new_sequence_candidates: dict[str, NewSequenceCandidate] = {}

        # Active matches to known unique sequences (detecting duplicates)
        self.potential_uniq_matches: dict[str, PotentialSeqRecMatch] = {}

        # Line buffer (grows beyond window_size to accommodate active matches)
        self.line_buffer: deque[BufferedLine] = deque()

        # Filtered lines buffer (separate from deduplication pipeline)
        # Stores (input_line_num, line) tuples for lines that bypass deduplication
        self.filtered_lines: deque[tuple[int, Union[str, bytes]]] = deque()

        # Output line tracking
        self.line_num_input = 0  # Lines read from input
        self.line_num_output = 0  # Lines written to output
        self.lines_skipped = 0  # Lines skipped as duplicates

    def _initialize_preloaded_sequences(
        self, preloaded_sequences: dict[str, Union[str, bytes]]
    ) -> None:
        """Initialize preloaded sequences into unique_sequences structure.

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

            # Create SequenceRecord object with PRELOADED_SEQUENCE_LINE as first_output_line
            seq_rec = SequenceRecord(
                first_window_hash=first_window_hash,
                full_sequence_hash=seq_hash,
                first_output_line=PRELOADED_SEQUENCE_LINE,
                sequence_length=sequence_length,
                duplicate_count=0,  # Preloaded sequences start with 0 duplicates
                window_hashes=window_hashes,
            )

            # Add to unique_sequences
            if first_window_hash not in self.sequence_records:
                self.sequence_records[first_window_hash] = {}
            self.sequence_records[first_window_hash][seq_hash] = seq_rec

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

        # Add to deduplication buffer with metadata
        buffered_line = BufferedLine(
            line=line,
            line_hash=line_hash,
            input_line_num=self.line_num_input,
        )
        self.line_buffer.append(buffered_line)

        # Need full window before processing deduplication
        if len(self.line_buffer) < self.window_size:
            return

        # Calculate window hash for current position
        window_line_hashes = [bl.line_hash for bl in list(self.line_buffer)[-self.window_size :]]
        current_window_hash = hash_window(self.window_size, window_line_hashes)

        # === PHASE 1: Update existing potential matches ===
        self._update_potential_uniq_matches(current_window_hash, output)

        # === PHASE 1b: Update new sequence candidates state ===
        self._update_new_sequence_candidates(current_window_hash)

        # === PHASE 2: Check if any new sequences should be finalized ===
        self._check_for_finalization(output)

        # === PHASE 3: Start new potential matches ===
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

        # Check new sequence candidates
        for candidate in self.new_sequence_candidates.values():
            min_required_depth = max(min_required_depth, candidate.buffer_depth)

        # Check potential uniq matches
        for match in self.potential_uniq_matches.values():
            buffer_depth = match.get_buffer_depth(self.line_num_output)
            min_required_depth = max(min_required_depth, buffer_depth)

        # Emit lines in order by comparing line numbers from both buffers
        while True:
            # Determine what we can emit from deduplication buffer
            dedup_can_emit = len(self.line_buffer) > min_required_depth
            dedup_line_num = self.line_buffer[0].input_line_num if dedup_can_emit else float("inf")

            # Filtered lines can only be emitted if they come before buffered uniqseq lines
            # This ensures we don't emit filtered lines ahead of earlier uniqseq lines
            filtered_can_emit = len(self.filtered_lines) > 0
            filtered_line_num: Union[int, float]
            if filtered_can_emit and self.line_buffer:
                # Check if filtered line comes before EARLIEST uniqseq line in buffer
                filtered_line_num = self.filtered_lines[0][0]
                earliest_dedup_line = self.line_buffer[0].input_line_num
                # Only emit filtered if it comes before earliest buffered uniqseq line
                filtered_can_emit = filtered_line_num < earliest_dedup_line
            else:
                filtered_line_num = self.filtered_lines[0][0] if filtered_can_emit else float("inf")

            # Emit whichever has the lower line number (earlier in input)
            if dedup_can_emit and dedup_line_num <= filtered_line_num:
                # Emit from deduplication buffer
                buffered_line = self.line_buffer.popleft()

                if self.inverse:
                    # Inverse mode: skip unique lines (these are first occurrences or truly unique)
                    self.lines_skipped += 1
                else:
                    # Normal mode: emit unique lines
                    self._write_line(output, buffered_line.line)
                    self.line_num_output += 1
                    # Update history entry for window starting at this line
                    # History position P corresponds to input line P+1 (0-indexed to 1-indexed)
                    hist_pos = buffered_line.input_line_num - 1
                    entry = self.window_hash_history.get_entry(hist_pos)
                    if entry and entry.first_output_line is None:
                        entry.first_output_line = self.line_num_output
            elif filtered_can_emit and filtered_line_num < dedup_line_num:
                # Emit from filtered buffer
                _, line = self.filtered_lines.popleft()
                self._write_line(output, line)
                self.line_num_output += 1
            else:
                # Nothing to emit
                break

    def flush(self, output: Union[TextIO, BinaryIO] = sys.stdout) -> None:
        """Emit remaining buffered lines at EOF."""
        # Finalize any remaining new sequence candidates
        # (they've reached EOF, so no more lines to match)
        # At EOF, candidates' lines fill the entire buffer, so skip them all
        # BUT: Only if the candidate represents a complete duplicate sequence
        # that was DETECTABLE at the position where it starts
        for candidate in list(self.new_sequence_candidates.values()):
            # Calculate how many lines from candidate start to EOF
            lines_from_start_to_eof = self.line_num_input - candidate.first_input_line

            # Only consider if this has enough lines from start
            if lines_from_start_to_eof >= self.window_size:
                # Check: at the first position where we could match without overlap,
                # were there enough remaining lines to form a complete duplicate?
                should_skip = False
                for hist_pos in candidate.matching_history_positions:
                    # First non-overlapping position after history position P is: P + window_size
                    # This is the earliest position where the oracle could detect a duplicate
                    first_check_pos = hist_pos + self.window_size

                    # From that position to EOF, how many lines are there?
                    lines_from_first_check = self.line_num_input - first_check_pos

                    # If there were >= window_size lines, the oracle would have detected and skipped
                    if lines_from_first_check >= self.window_size:
                        should_skip = True
                        break

                if should_skip:
                    # Extract sequence lines before popping (for library saving)
                    num_lines = min(candidate.length, len(self.line_buffer))
                    sequence_lines = (
                        [bl.line for bl in list(self.line_buffer)[-num_lines:]]
                        if num_lines > 0
                        else []
                    )

                    # Collect line numbers for annotation and explain (before popping)
                    should_annotate = self.annotate and not self.inverse and num_lines > 0
                    if num_lines > 0 and len(self.line_buffer) >= num_lines:
                        # Lines are at END of buffer
                        dup_start = self.line_buffer[-num_lines].input_line_num
                        dup_end = self.line_buffer[-1].input_line_num
                        # Use candidate's start line as the match position
                        # (this is approximate - we don't have exact original line numbers here)
                        match_start = candidate.output_cursor_at_start
                        match_end = candidate.output_cursor_at_start + num_lines - 1
                        # We don't have a repeat count for candidates, use 2 as minimum
                        repeat_count = 2
                    else:
                        # Fallback values if buffer doesn't have enough lines
                        dup_start = dup_end = match_start = match_end = 0
                        repeat_count = 2

                    # Handle candidate lines based on mode
                    # Normal mode: skip duplicates
                    # Inverse mode: emit duplicates

                    # In inverse mode, collect lines before popping to emit in correct order
                    if self.inverse and num_lines > 0:
                        lines_to_emit = [bl.line for bl in list(self.line_buffer)[-num_lines:]]

                    for _ in range(num_lines):
                        buffered_line = self.line_buffer.pop()

                        if not self.inverse:
                            # Normal mode: skip duplicate lines
                            self.lines_skipped += 1

                    # Emit collected lines in correct order for inverse mode
                    if self.inverse and num_lines > 0:
                        for line in lines_to_emit:
                            self._write_line(output, line)
                            self.line_num_output += 1

                    # Write annotation after skipping duplicates (normal mode only)
                    if should_annotate:
                        self._write_annotation(
                            output, dup_start, dup_end, match_start, match_end, repeat_count
                        )
                        # Explain message
                        self._print_explain(
                            f"Lines {dup_start}-{dup_end} skipped "
                            f"(duplicate of lines {match_start}-{match_end}, seen {repeat_count}x)"
                        )
                    else:
                        # No annotation, but still explain if enabled
                        if num_lines > 0:
                            self._print_explain(
                                f"Lines {dup_start}-{dup_end} skipped "
                                f"(duplicate, seen {repeat_count}x)"
                            )

                    # Create SequenceRecord for this sequence (if not already exists)
                    self._record_sequence(candidate, sequence_lines, output)

        self.new_sequence_candidates.clear()

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
                else:
                    # Normal mode: emit unique lines
                    self._write_line(output, buffered_line.line)
                    self.line_num_output += 1
            else:
                _, line = self.filtered_lines.popleft()
                self._write_line(output, line)
                self.line_num_output += 1

    def _record_sequence(
        self,
        candidate: NewSequenceCandidate,
        sequence_lines: Optional[list[Union[str, bytes]]] = None,
        output: Union[TextIO, BinaryIO] = sys.stdout,
    ) -> None:
        """Record a sequence in unique_sequences.

        Args:
            candidate: The sequence candidate to record
            sequence_lines: Optional list of actual line content (for library saving)
            output: Output stream for writing lines in inverse mode
        """
        full_sequence_hash = hash_window(candidate.length, candidate.window_hashes)

        if candidate.first_window_hash not in self.sequence_records:
            self.sequence_records[candidate.first_window_hash] = {}

        if full_sequence_hash not in self.sequence_records[candidate.first_window_hash]:
            # Create new SequenceRecord for first occurrence
            seq_rec = SequenceRecord(
                first_window_hash=candidate.first_window_hash,
                full_sequence_hash=full_sequence_hash,
                first_output_line=candidate.output_cursor_at_start - candidate.length,
                sequence_length=candidate.length,
                duplicate_count=1,
                window_hashes=candidate.window_hashes.copy(),
            )
            self.sequence_records[candidate.first_window_hash][full_sequence_hash] = seq_rec

            # Save to library if callback is set and lines are available
            if (
                self.save_sequence_callback
                and sequence_lines
                and full_sequence_hash not in self.saved_sequences
            ):
                self.save_sequence_callback(full_sequence_hash, sequence_lines)
                self.saved_sequences.add(full_sequence_hash)
        else:
            # Increment repeat count
            self.sequence_records[candidate.first_window_hash][
                full_sequence_hash
            ].duplicate_count += 1

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

    def _update_potential_uniq_matches(
        self, current_window_hash: str, output: Union[TextIO, BinaryIO] = sys.stdout
    ) -> None:
        """Update matches against known unique sequences using window-by-window comparison."""
        to_remove = []
        confirmed_duplicate = None

        for match_id, match in list(self.potential_uniq_matches.items()):
            # Check if we've already matched all windows
            if match.next_window_index >= len(match.matched_sequence.window_hashes):
                # Already matched everything - this shouldn't happen, but handle it
                to_remove.append(match_id)
                continue

            # Verify current window hash matches expected hash
            expected_hash = match.matched_sequence.window_hashes[match.next_window_index]

            if current_window_hash != expected_hash:
                # Mismatch! This is not a duplicate - remove from tracking
                to_remove.append(match_id)
                continue

            # Window matches! Move to next window
            match.next_window_index += 1

            # Check if we've matched all windows (reached full sequence length)
            if match.next_window_index >= len(match.matched_sequence.window_hashes):
                # CONFIRMED DUPLICATE!
                confirmed_duplicate = match
                to_remove.append(match_id)
                break

        # Clean up non-matching and completed matches
        for match_id in to_remove:
            del self.potential_uniq_matches[match_id]

        # Handle confirmed duplicate
        if confirmed_duplicate:
            self._handle_duplicate(confirmed_duplicate, output)

    def _handle_duplicate(
        self, match: PotentialSeqRecMatch, output: Union[TextIO, BinaryIO] = sys.stdout
    ) -> None:
        """Handle a confirmed duplicate sequence."""
        # Increment repeat count for the unique sequence
        match.matched_sequence.duplicate_count += 1

        # If this is a preloaded sequence being observed for the first time, save it
        if (
            match.matched_sequence.first_output_line == PRELOADED_SEQUENCE_LINE
            and match.matched_sequence.duplicate_count == 1
            and self.save_sequence_callback
            and match.matched_sequence.full_sequence_hash not in self.saved_sequences
        ):
            # Extract sequence lines from buffer
            lines_to_extract = match.get_length()
            sequence_lines = [bl.line for bl in list(self.line_buffer)[:lines_to_extract]]
            self.save_sequence_callback(match.matched_sequence.full_sequence_hash, sequence_lines)
            self.saved_sequences.add(match.matched_sequence.full_sequence_hash)

        # Handle buffered lines based on mode
        # Normal mode: discard duplicates
        # Inverse mode: emit duplicates
        lines_to_process = match.get_length()

        # Collect line numbers for annotation (before popping)
        should_annotate = self.annotate and not self.inverse and lines_to_process > 0
        if should_annotate:
            dup_start = self.line_buffer[0].input_line_num
            dup_end = self.line_buffer[
                min(lines_to_process - 1, len(self.line_buffer) - 1)
            ].input_line_num
            match_start = int(match.matched_sequence.first_output_line)
            match_end = int(match.matched_sequence.first_output_line + lines_to_process - 1)
            repeat_count = match.matched_sequence.duplicate_count

        for _ in range(lines_to_process):
            if self.line_buffer:
                buffered_line = self.line_buffer.popleft()

                if self.inverse:
                    # Inverse mode: emit duplicate lines, UNLESS they match preloaded sequences
                    if match.matched_sequence.first_output_line != PRELOADED_SEQUENCE_LINE:
                        self._write_line(output, buffered_line.line)
                        self.line_num_output += 1
                    else:
                        # Preloaded sequence matches should never be output
                        self.lines_skipped += 1
                else:
                    # Normal mode: skip duplicate lines
                    self.lines_skipped += 1

        # Write annotation after skipping duplicates (normal mode only)
        if should_annotate:
            self._write_annotation(output, dup_start, dup_end, match_start, match_end, repeat_count)
            # Explain message
            self._print_explain(
                f"Lines {dup_start}-{dup_end} skipped "
                f"(duplicate of lines {match_start}-{match_end}, seen {repeat_count}x)"
            )
        else:
            # No annotation, but still explain if enabled
            if lines_to_process > 0:
                # Calculate the line numbers that were just skipped
                # These were popped from line_buffer already, so we need to reconstruct
                dup_end = self.line_num_input
                dup_start = dup_end - lines_to_process + 1
                self._print_explain(
                    f"Lines {dup_start}-{dup_end} skipped "
                    f"(duplicate, seen {match.matched_sequence.duplicate_count}x)"
                )

        # Clear all active tracking (duplicate consumed the buffer)
        self.new_sequence_candidates.clear()
        self.potential_uniq_matches.clear()

    def _update_new_sequence_candidates(self, current_window_hash: str) -> None:
        """Update new sequence candidates by checking if current window continues the match."""
        for _candidate_id, candidate in self.new_sequence_candidates.items():
            # Check each matching history position to see if it continues to match
            still_matching = set()

            for hist_pos in candidate.matching_history_positions:
                # Get next expected position in history
                next_hist_pos = self.window_hash_history.get_next_position(hist_pos)

                # Get window hash at next position
                next_window_hash = self.window_hash_history.get_key(next_hist_pos)

                if next_window_hash is None:
                    # History position no longer exists (evicted) - can't continue matching
                    continue

                if next_window_hash == current_window_hash:
                    # Still matching! Keep tracking this position
                    still_matching.add(next_hist_pos)

            # Update candidate
            if still_matching:
                # At least one history position still matches
                candidate.matching_history_positions = still_matching
                candidate.length += 1
                candidate.buffer_depth += 1
                candidate.window_hashes.append(current_window_hash)
            else:
                # No more matching positions - candidate should be finalized
                # (Don't update it, just mark for finalization in Phase 2)
                candidate.matching_history_positions.clear()

    def _check_for_finalization(self, output: Union[TextIO, BinaryIO]) -> None:
        """Check if any new sequence candidates should be finalized as unique sequences."""
        # Use list() to avoid "dictionary changed size during iteration" error
        # (finalization clears candidates dict)
        for _candidate_id, candidate in list(self.new_sequence_candidates.items()):
            # Check if all matching history positions have been exhausted
            if not candidate.matching_history_positions:
                # No more potential matches - this is a new unique sequence!
                self._finalize_new_sequence(candidate, output)
                # _finalize_new_sequence clears all candidates, so we're done
                return

    def _finalize_new_sequence(
        self, candidate: NewSequenceCandidate, output: Union[TextIO, BinaryIO]
    ) -> None:
        """Finalize a new sequence candidate - always results in duplicate handling."""
        # Calculate full sequence hash
        full_sequence_hash = hash_window(candidate.length, candidate.window_hashes)

        # Check if this sequence already exists in unique_sequences
        # (includes both observed sequences and preloaded sequences)
        if candidate.first_window_hash in self.sequence_records:
            if full_sequence_hash in self.sequence_records[candidate.first_window_hash]:
                # Pattern exists - this is a repeat of a known sequence
                existing_seq = self.sequence_records[candidate.first_window_hash][
                    full_sequence_hash
                ]
                existing_seq.duplicate_count += 1

                # If this is a preloaded sequence being observed for the first time, save it
                if (
                    existing_seq.first_output_line == PRELOADED_SEQUENCE_LINE
                    and existing_seq.duplicate_count == 1
                    and self.save_sequence_callback
                    and full_sequence_hash not in self.saved_sequences
                ):
                    # Extract sequence lines from buffer
                    sequence_lines = [
                        bl.line for bl in list(self.line_buffer)[-candidate.length - 1 : -1]
                    ]
                    self.save_sequence_callback(full_sequence_hash, sequence_lines)
                    self.saved_sequences.add(full_sequence_hash)

                # Skip current buffer (it's a duplicate)
                # Write annotation if enabled (before skipping)
                # Note: Can only annotate if first occurrence has been emitted
                # (first_output_line is valid)
                if (
                    self.annotate
                    and not self.inverse
                    and candidate.length > 0
                    and existing_seq.first_output_line != float("-inf")
                ):
                    # Duplicate lines are at positions [-count-1 : -1] (excluding newest)
                    if candidate.length < len(self.line_buffer):
                        dup_start = self.line_buffer[-candidate.length - 1].input_line_num
                        dup_end = self.line_buffer[-2].input_line_num
                    else:
                        # Edge case: would skip almost all buffer
                        dup_start = self.line_buffer[0].input_line_num
                        dup_end = (
                            self.line_buffer[-2].input_line_num
                            if len(self.line_buffer) >= 2
                            else self.line_buffer[0].input_line_num
                        )
                    match_start = int(existing_seq.first_output_line)
                    match_end = match_start + candidate.length - 1
                    self._write_annotation(
                        output,
                        dup_start,
                        dup_end,
                        match_start,
                        match_end,
                        existing_seq.duplicate_count,
                    )
                    # Explain message
                    self._print_explain(
                        f"Lines {dup_start}-{dup_end} skipped "
                        f"(duplicate of lines {match_start}-{match_end}, "
                        f"seen {existing_seq.duplicate_count}x)"
                    )
                else:
                    # No annotation, but still explain if enabled
                    if candidate.length < len(self.line_buffer):
                        dup_start = self.line_buffer[-candidate.length - 1].input_line_num
                        dup_end = self.line_buffer[-2].input_line_num
                    else:
                        dup_start = self.line_buffer[0].input_line_num
                        dup_end = (
                            self.line_buffer[-2].input_line_num
                            if len(self.line_buffer) >= 2
                            else self.line_buffer[0].input_line_num
                        )
                    match_start = (
                        int(existing_seq.first_output_line)
                        if existing_seq.first_output_line != float("-inf")
                        else 0
                    )
                    match_end = match_start + candidate.length - 1 if match_start > 0 else 0
                    self._print_explain(
                        f"Lines {dup_start}-{dup_end} skipped "
                        f"(duplicate, seen {existing_seq.duplicate_count}x)"
                    )

                self._skip_buffer_lines(candidate.length, output)
                # Clear all other candidates since buffer state changed
                self.new_sequence_candidates.clear()
                self.potential_uniq_matches.clear()
                return

        # Pattern is new - create SequenceRecord for first (historical) occurrence
        # Note: The candidate represents the CURRENT occurrence (which is a duplicate)
        # The SequenceRecord represents the FIRST occurrence (in history)
        # Look up first_output_line from history (using original first position)
        first_output_line: Union[int, float] = NEVER_OUTPUT_LINE
        if candidate.original_first_history_position >= 0:
            # Look up the output line number from history
            hist_entry = self.window_hash_history.get_entry(
                candidate.original_first_history_position
            )
            if hist_entry and hist_entry.first_output_line is not None:
                first_output_line = hist_entry.first_output_line

        seq_rec = SequenceRecord(
            first_window_hash=candidate.first_window_hash,
            full_sequence_hash=full_sequence_hash,
            first_output_line=first_output_line,
            sequence_length=candidate.length,
            duplicate_count=1,  # Current occurrence is first duplicate
            window_hashes=candidate.window_hashes.copy(),
        )

        # Add to unique_sequences
        if candidate.first_window_hash not in self.sequence_records:
            self.sequence_records[candidate.first_window_hash] = {}
        self.sequence_records[candidate.first_window_hash][full_sequence_hash] = seq_rec

        # Save to library if callback is set (new sequence discovered)
        if self.save_sequence_callback and full_sequence_hash not in self.saved_sequences:
            # Extract sequence lines from buffer (historical occurrence)
            sequence_lines = [bl.line for bl in list(self.line_buffer)[-candidate.length - 1 : -1]]
            self.save_sequence_callback(full_sequence_hash, sequence_lines)
            self.saved_sequences.add(full_sequence_hash)

        # Skip current buffer (it's a duplicate of the historical occurrence)
        # Write annotation if enabled (before skipping)
        # Note: Can only annotate if first occurrence has been emitted (first_output_line is valid)
        if (
            self.annotate
            and not self.inverse
            and candidate.length > 0
            and seq_rec.first_output_line != float("-inf")
        ):
            # Duplicate lines are at positions [-count-1 : -1] (excluding newest)
            if candidate.length < len(self.line_buffer):
                dup_start = self.line_buffer[-candidate.length - 1].input_line_num
                dup_end = self.line_buffer[-2].input_line_num
            else:
                # Edge case: would skip almost all buffer
                dup_start = self.line_buffer[0].input_line_num
                dup_end = (
                    self.line_buffer[-2].input_line_num
                    if len(self.line_buffer) >= 2
                    else self.line_buffer[0].input_line_num
                )
            # Use seq_rec.first_output_line (output line numbers from first occurrence)
            match_start = int(seq_rec.first_output_line)
            match_end = match_start + candidate.length - 1
            self._write_annotation(
                output, dup_start, dup_end, match_start, match_end, seq_rec.duplicate_count
            )
            # Explain message
            self._print_explain(
                f"Lines {dup_start}-{dup_end} skipped "
                f"(duplicate of lines {match_start}-{match_end}, "
                f"seen {seq_rec.duplicate_count}x)"
            )
        else:
            # No annotation, but still explain if enabled
            if candidate.length < len(self.line_buffer):
                dup_start = self.line_buffer[-candidate.length - 1].input_line_num
                dup_end = self.line_buffer[-2].input_line_num
            else:
                dup_start = self.line_buffer[0].input_line_num
                dup_end = (
                    self.line_buffer[-2].input_line_num
                    if len(self.line_buffer) >= 2
                    else self.line_buffer[0].input_line_num
                )
            self._print_explain(
                f"Lines {dup_start}-{dup_end} skipped (duplicate, seen {seq_rec.duplicate_count}x)"
            )

        self._skip_buffer_lines(candidate.length, output)

        # Clear all other candidates since buffer state changed
        self.new_sequence_candidates.clear()
        self.potential_uniq_matches.clear()

        # LRU eviction if needed
        total_seqs = sum(len(seqs) for seqs in self.sequence_records.values())
        if total_seqs > self.max_unique_sequences:
            # Remove oldest (first) entry
            self.sequence_records.popitem(last=False)

    def _skip_buffer_lines(self, count: int, output: Union[TextIO, BinaryIO] = sys.stdout) -> None:
        """Skip lines from near the end of buffer (excluding the newest line).

        This is called after a candidate fails to match the current line.
        The candidate's lines are in the buffer, but NOT including the current line
        which was just added and caused the mismatch.

        So we need to remove lines at positions buffer[-count-1 : -1].
        In inverse mode, these duplicate lines are emitted before removal.
        """
        if count <= 0 or count >= len(self.line_buffer):
            # Edge case: skip all but the newest line
            while len(self.line_buffer) > 1:
                buffered_line = self.line_buffer.pop()

                if self.inverse:
                    # Inverse mode: emit duplicate lines
                    self._write_line(output, buffered_line.line)
                    self.line_num_output += 1
                else:
                    # Normal mode: skip duplicate lines
                    self.lines_skipped += 1
            return

        # Remove lines at positions [-count-1 : -1]
        # Convert deque to list, remove range, convert back
        line_list = list(self.line_buffer)

        # Extract lines to potentially emit in inverse mode
        lines_to_process = line_list[-count - 1 : -1]

        # Remove the range
        del line_list[-count - 1 : -1]

        if self.inverse:
            # Inverse mode: emit duplicate lines
            for buffered_line in lines_to_process:
                self._write_line(output, buffered_line.line)
                self.line_num_output += 1
        else:
            # Normal mode: skip duplicate lines
            self.lines_skipped += count

        # Replace deque contents
        self.line_buffer.clear()
        self.line_buffer.extend(line_list)

    def _check_for_new_uniq_matches(
        self, current_window_hash: str, output: Union[TextIO, BinaryIO] = sys.stdout
    ) -> None:
        """Check for new matches against known unique sequences or history."""
        # Phase 3a: Check against known unique sequences
        confirmed_duplicate = None
        if current_window_hash in self.sequence_records:
            # Found potential match(es) against known unique sequence(s)
            for seq in self.sequence_records[current_window_hash].values():
                # Start tracking this potential duplicate
                match_id = f"uniq_{self.line_num_output}_{seq.first_output_line}"
                match = PotentialSeqRecMatch(
                    matched_sequence=seq,
                    output_cursor_at_start=self.line_num_output,
                    next_window_index=1,  # Already matched first window
                    window_size=self.window_size,
                )

                # Check if this sequence is already complete (length == window_size)
                if match.next_window_index >= len(seq.window_hashes):
                    # Immediately confirmed duplicate!
                    # The matched lines are at the END of the buffer (window just processed)
                    confirmed_duplicate = match
                    break
                else:
                    # Track for future updates
                    self.potential_uniq_matches[match_id] = match

        # Handle immediately confirmed duplicate (matched lines at END of buffer)
        if confirmed_duplicate:
            # Increment repeat count
            confirmed_duplicate.matched_sequence.duplicate_count += 1

            # If this is a preloaded sequence being observed for the first time, save it
            if (
                confirmed_duplicate.matched_sequence.first_output_line == PRELOADED_SEQUENCE_LINE
                and confirmed_duplicate.matched_sequence.duplicate_count == 1
                and self.save_sequence_callback
                and confirmed_duplicate.matched_sequence.full_sequence_hash
                not in self.saved_sequences
            ):
                # Extract sequence lines from end of buffer
                lines_to_extract = confirmed_duplicate.get_length()
                sequence_lines = [bl.line for bl in list(self.line_buffer)[-lines_to_extract:]]
                self.save_sequence_callback(
                    confirmed_duplicate.matched_sequence.full_sequence_hash, sequence_lines
                )
                self.saved_sequences.add(confirmed_duplicate.matched_sequence.full_sequence_hash)

            # Skip lines from END of buffer INCLUDING the newest line
            # (different from _skip_buffer_lines which excludes the newest line)
            lines_to_skip = confirmed_duplicate.get_length()

            # Collect line numbers for annotation (before popping)
            # Can only annotate if first occurrence has been emitted (first_output_line is valid)
            should_annotate = (
                self.annotate
                and not self.inverse
                and lines_to_skip > 0
                and confirmed_duplicate.matched_sequence.first_output_line != float("-inf")
            )
            if should_annotate:
                # Lines are at END of buffer
                dup_start = self.line_buffer[-lines_to_skip].input_line_num
                dup_end = self.line_buffer[-1].input_line_num
                match_start = int(confirmed_duplicate.matched_sequence.first_output_line)
                match_end = int(
                    confirmed_duplicate.matched_sequence.first_output_line + lines_to_skip - 1
                )
                repeat_count = confirmed_duplicate.matched_sequence.duplicate_count

            # In inverse mode, collect lines before popping to emit in correct order
            if self.inverse and lines_to_skip > 0:
                lines_to_emit = [bl.line for bl in list(self.line_buffer)[-lines_to_skip:]]

            for _ in range(lines_to_skip):
                if len(self.line_buffer) > 0:
                    self.line_buffer.pop()  # Remove from end

                    if not self.inverse:
                        # Normal mode: skip duplicate lines
                        self.lines_skipped += 1

            # Emit collected lines in correct order for inverse mode
            if self.inverse and lines_to_skip > 0:
                # Check if this matches a preloaded sequence
                if (
                    confirmed_duplicate.matched_sequence.first_output_line
                    != PRELOADED_SEQUENCE_LINE
                ):
                    for line in lines_to_emit:
                        self._write_line(output, line)
                        self.line_num_output += 1
                else:
                    # Preloaded sequence matches should never be output
                    self.lines_skipped += lines_to_skip

            # Write annotation after skipping duplicates (normal mode only)
            if should_annotate:
                self._write_annotation(
                    output, dup_start, dup_end, match_start, match_end, repeat_count
                )

            # Clear all active tracking
            self.new_sequence_candidates.clear()
            self.potential_uniq_matches.clear()
            return

        # Phase 3b: Check against history (for new sequence candidates)
        history_positions = self.window_hash_history.find_all_positions(current_window_hash)

        if history_positions:
            # Filter out positions that would overlap with current position
            # Don't match if start lines overlap within window_size
            # History position P corresponds to window ending at line P + window_size - 1
            # Current window ends at line_num_input (current input line being processed)
            # So the start of current window is line_num_input - window_size + 1
            # And start of history window is P
            # Overlap if: P < (line_num_input - window_size + 1) + window_size
            # Simplifying: P < line_num_input
            current_window_start = self.line_num_input - self.window_size + 1
            non_overlapping = [
                pos for pos in history_positions if pos + self.window_size <= current_window_start
            ]

            if non_overlapping:
                # Found potential match(es) in history (non-overlapping)
                # Use input line number for stable candidate ID across output emissions
                candidate_id = f"new_{self.line_num_input}"

                if candidate_id not in self.new_sequence_candidates:
                    # Start new candidate
                    # input_start_line: where the matched window starts in the input
                    # line_num_input is current line (just processed), so window starts at:
                    # line_num_input - window_size
                    # (since buffer has window_size lines before current)
                    input_start = self.line_num_input - self.window_size
                    self.new_sequence_candidates[candidate_id] = NewSequenceCandidate(
                        output_cursor_at_start=self.line_num_output,
                        first_input_line=input_start,
                        length=self.window_size,
                        window_hashes=[current_window_hash],
                        first_window_hash=current_window_hash,
                        buffer_depth=len(self.line_buffer) - 1,
                        matching_history_positions=set(non_overlapping),
                        original_first_history_position=min(non_overlapping)
                        if non_overlapping
                        else 0,
                    )

    def _write_line(self, output: Union[TextIO, BinaryIO], line: Union[str, bytes]) -> None:
        """Write a line to output with appropriate delimiter.

        Args:
            output: Output stream (text or binary)
            line: Line to write (str or bytes)
        """
        if isinstance(line, bytes):
            # Binary mode: write bytes with delimiter
            assert isinstance(self.delimiter, bytes), "Delimiter must be bytes in binary mode"
            output.write(line)  # type: ignore
            output.write(self.delimiter)  # type: ignore
        else:
            # Text mode: write str with delimiter
            assert isinstance(self.delimiter, str), "Delimiter must be str in text mode"
            output.write(line)  # type: ignore
            output.write(self.delimiter)  # type: ignore

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
            output.write(annotation.encode("utf-8"))  # type: ignore
            output.write(self.delimiter)  # type: ignore
        else:
            output.write(annotation)  # type: ignore
            output.write(self.delimiter)  # type: ignore
