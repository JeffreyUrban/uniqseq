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


@dataclass
class KnownSequence:
    """Base class for sequences we can match against.

    Common interface for all sequence types. Subclasses cannot expose
    any fields beyond what's defined here.
    """

    first_window_hash: str  # Hash of first window
    first_output_line: Union[int, float] = field(
        default=float("-inf")
    )  # For determining "earliest"
    subsequence_match_counts: dict[int, int] = field(
        default_factory=dict
    )  # Length -> count of matches at that subsequence length

    def get_window_hash(self, index: int) -> Optional[str]:
        """Lookup window hash at index. Returns None if index out of range."""
        raise NotImplementedError("Subclasses must implement get_window_hash")


@dataclass
class RecordedSequence(KnownSequence):
    """A recorded sequence - fully known sequence in the library.

    Immutable sequence data (except subsequence_match_counts which grows).
    All data beyond KnownSequence interface is private.
    """

    _window_hashes: list[str] = field(default_factory=list, repr=False)

    def get_window_hash(self, index: int) -> Optional[str]:
        """Lookup window hash at index."""
        if 0 <= index < len(self._window_hashes):
            return self._window_hashes[index]
        return None


@dataclass
class HistorySequence(KnownSequence):
    """A sequence being discovered from history matches.

    Mutable - grows as we match more lines.
    All data beyond KnownSequence interface is private.
    """

    _window_hashes: list[str] = field(default_factory=list, repr=False)
    _first_tracked_line: int = field(default=0, repr=False)
    _buffer_depth: int = field(default=0, repr=False)
    _matching_history_positions: set[int] = field(default_factory=set, repr=False)
    _original_first_history_position: int = field(default=0, repr=False)
    _history: Optional['WindowHashHistory'] = field(default=None, repr=False)

    def get_window_hash(self, index: int) -> Optional[str]:
        """Lookup window hash at index."""
        if 0 <= index < len(self._window_hashes):
            return self._window_hashes[index]
        return None


@dataclass
class SubsequenceMatch:
    """Tracks an active match against a KnownSequence.

    Simple wrapper - no polymorphism needed.
    The matching logic checks the type of known_sequence.
    """

    known_sequence: KnownSequence  # The sequence we're matching against
    output_cursor_at_start: int  # Output cursor when match started
    next_window_index: int = 1  # For RecordedSequence: which window to check next


# Type aliases for backward compatibility TODO: Remove
SequenceRecord = RecordedSequence
NewSequenceCandidate = HistorySequence


# Old class kept for backward compatibility during transition TODO: Remove
@dataclass
class PotentialSeqRecMatch:
    """Tracking potential duplicate of a previously identified sequence.

    Note: Direct duplicates are handled immediately without creating a HistorySequence.
    """

    __slots__ = ["matched_sequence", "output_cursor_at_start", "next_window_index", "window_size"]
    matched_sequence: RecordedSequence  # Existing sequence we're comparing to
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
        self.sequence_records: OrderedDict[str, dict[str, SequenceRecord]] = OrderedDict()

        # Load preloaded sequences into unique_sequences
        if preloaded_sequences:
            self._initialize_preloaded_sequences(preloaded_sequences)

        # Active matches against any KnownSequence (both RecordedSequence and HistorySequence)
        # Unified structure for tracking all active matches
        self.sequence_candidates: dict[str, KnownSequence] = {}

        # Old dicts kept temporarily for backward compatibility during transition
        # TODO: Remove after refactoring complete
        self.new_sequence_candidates: dict[str, NewSequenceCandidate] = {}
        self.potential_uniq_matches: dict[str, PotentialSeqRecMatch] = {}

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

        TODO: Need to deduplicate subsequences (starting the same), keeping only one longest.

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
                window_hashes=window_hashes,
            )
            # Preloaded sequences start with 0 duplicates (empty dict)

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

        # === PHASE 1: Update existing potential matches and collect divergences ===
        # NEW UNIFIED APPROACH (when sequence_candidates is populated)
        if self.sequence_candidates:
            all_diverged = self._update_sequence_candidates(current_window_hash)
        else:
            # OLD APPROACH (during transition) TODO: Remove
            diverged_recorded = self._update_potential_uniq_matches(current_window_hash)
            diverged_history = self._update_new_sequence_candidates(current_window_hash)
            all_diverged = diverged_recorded + diverged_history

        # Handle all diverged matches together
        if all_diverged:
            # DEBUG: Log all divergences
            import os

            if os.getenv("UNIQSEQ_DEBUG"):
                with open("/tmp/uniqseq_debug.log", "a") as f:
                    f.write(
                        f"Handling {len(all_diverged)} diverged matches "
                        f"({len(diverged_recorded)} recorded, {len(diverged_history)} history)\n"
                    )
                    for seq, length in all_diverged:
                        seq_type = type(seq).__name__
                        f.write(
                            f"  {seq_type} seq_length={seq.sequence_length}, diverged_at={length}\n"
                        )
            # Handle all subsequence matches uniformly
            self._handle_subsequence_matches(all_diverged, current_window_hash, output)

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
            if candidate.buffer_depth > min_required_depth:
                min_required_depth = candidate.buffer_depth

        # Check potential uniq matches
        line_num_output = self.line_num_output  # Cache for match calculations
        for match in self.potential_uniq_matches.values():
            buffer_depth = match.get_buffer_depth(line_num_output)
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
                else:
                    # Normal mode: emit unique lines
                    self._write_line(output, buffered_line.line)
                    self.line_num_output += 1
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
        # Finalize any remaining new sequence candidates
        # (they've reached EOF, so no more lines to match)
        # At EOF, candidates' lines fill the entire buffer, so skip them all
        # BUT: Only if the candidate represents a complete duplicate sequence
        # that was DETECTABLE at the position where it starts

        # Process both old approach (new_sequence_candidates) and new unified approach (sequence_candidates with HistorySequence)
        candidates_to_process = list(self.new_sequence_candidates.values())

        # Add HistorySequence instances from unified dict
        for cand in self.sequence_candidates.values():
            if isinstance(cand, HistorySequence):
                candidates_to_process.append(cand)

        for candidate in candidates_to_process:
            # Calculate how many tracked lines from candidate start to EOF
            lines_from_start_to_eof = self.line_num_input_tracked - candidate.first_tracked_line

            # Only consider if this has enough lines from start
            if lines_from_start_to_eof >= self.window_size:
                # Check: at the first position where we could match without overlap,
                # were there enough remaining lines to form a complete duplicate?
                should_skip = False
                for hist_pos in candidate.matching_history_positions:
                    # First non-overlapping position after history position P is: P + window_size
                    # This is the earliest position where the oracle could detect a duplicate
                    first_check_pos = hist_pos + self.window_size

                    # From that position to EOF, how many tracked lines are there?
                    lines_from_first_check = self.line_num_input_tracked - first_check_pos

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
        # Also clear unified dict (keep only RecordedSequence instances, remove HistorySequence)
        self.sequence_candidates = {
            k: v for k, v in self.sequence_candidates.items() if not isinstance(v, HistorySequence)
        }

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
                window_hashes=candidate.window_hashes.copy(),
            )
            # Record first duplicate at this length
            seq_rec.subsequence_match_counts[candidate.length] = 1
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
            # Increment repeat count at this subsequence length
            seq_rec = self.sequence_records[candidate.first_window_hash][full_sequence_hash]
            seq_rec.subsequence_match_counts[candidate.length] = (
                seq_rec.subsequence_match_counts.get(candidate.length, 0) + 1
            )

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

    def _update_sequence_candidates(
        self, current_window_hash: str
    ) -> list[tuple[KnownSequence, int]]:
        """Update all sequence candidates using polymorphic methods.

        Returns:
            List of (sequence, matched_length) tuples for sequences that diverged
        """
        diverged = []

        for candidate_id, seq in list(self.sequence_candidates.items()):
            # Use polymorphic advance_match method (no type checking needed!)
            if seq.advance_match(current_window_hash):
                continue  # Still matching
            else:
                # Diverged
                diverged.append((seq, seq.get_matched_length()))
                del self.sequence_candidates[candidate_id]

        return diverged

    # OLD METHOD - kept for compatibility during transition
    def _update_potential_uniq_matches(
        self, current_window_hash: str
    ) -> list[tuple[KnownSequence, int]]:
        """Update matches against known unique sequences using window-by-window comparison.

        Returns:
            List of (sequence, matched_length) tuples for matches that diverged
        """
        to_remove = []
        diverged_matches = []  # List of (sequence, matched_length) tuples

        for match_id, match in list(self.potential_uniq_matches.items()):
            # Get expected hash (None if we're beyond the end of the sequence)
            if match.next_window_index < len(match.matched_sequence.window_hashes):
                expected_hash = match.matched_sequence.window_hashes[match.next_window_index]
            else:
                expected_hash = None

            if current_window_hash != expected_hash:
                # Mismatch or end of sequence - track as diverged match
                # next_window_index is the number of window hashes matched (one per line)
                matched_length = match.next_window_index
                diverged_matches.append((match.matched_sequence, matched_length))
                to_remove.append(match_id)
                continue

            # Window matches! Move to next window
            match.next_window_index += 1

        # Clean up non-matching and completed matches
        for match_id in to_remove:
            del self.potential_uniq_matches[match_id]

        return diverged_matches

    def _handle_subsequence_matches(
        self,
        diverged_matches: list[tuple[KnownSequence, int]],
        current_window_hash: str,
        output: Union[TextIO, BinaryIO] = sys.stdout,
    ) -> None:
        """Handle subsequence matches after divergence from known sequences.

        Handles both RecordedSequence and HistorySequence uniformly:
        - For RecordedSequence: increment subsequence_match_counts
        - For HistorySequence: finalize as new RecordedSequence

        When comparing which sequence is earliest, HistorySequence is always "latest".

        Args:
            diverged_matches: List of (sequence, matched_length) tuples for matches that diverged
            current_window_hash: The window hash where divergence occurred
            output: Output stream
        """
        if not diverged_matches:
            return

        # Find the longest diverged match
        longest_match = max(diverged_matches, key=lambda x: x[1])
        longest_length = longest_match[1]

        # Among all diverged matches of the longest length, pick the earliest sequence
        # (the one with the earliest first_output_line)
        longest_diverged = [m for m in diverged_matches if m[1] == longest_length]
        if len(longest_diverged) > 1:
            # Multiple matches at the same length - pick the earliest
            longest_seq = min(longest_diverged, key=lambda x: x[0].first_output_line)[0]
        else:
            longest_seq = longest_diverged[0][0]

        # Step 2: Check if there are longer active matches
        has_longer_match = False
        longer_match_type = None
        longer_match_length = None

        # Check remaining PotentialSeqRecMatches (they're still active)
        for match in self.potential_uniq_matches.values():
            # next_window_index is the number of lines matched
            match_length = match.next_window_index
            if match_length > longest_length:
                has_longer_match = True
                longer_match_type = "PotentialSeqRecMatch"
                longer_match_length = match_length
                break

        # Check BufferedCandidates (history matches)
        # Special case: ignore candidates that also diverged at same length
        if not has_longer_match:
            position_to_entry = self.window_hash_history.position_to_entry
            for candidate in self.new_sequence_candidates.values():
                if not candidate.matching_history_positions:
                    continue

                # Check if this candidate will continue matching the current window
                # (same logic as _update_new_sequence_candidates but just checking)
                will_continue = False
                for hist_pos in candidate.matching_history_positions:
                    next_pos = hist_pos + 1
                    entry = position_to_entry.get(next_pos)
                    if entry is not None and entry.window_hash == current_window_hash:
                        will_continue = True
                        break

                # Only count as longer if it will continue AND currently has length >= longest_length
                # (length will become length+1 after update, so >= means it will be > after)
                if will_continue and candidate.length >= longest_length:
                    has_longer_match = True
                    longer_match_type = "BufferedCandidate"
                    longer_match_length = candidate.length + 1  # Will be this after update
                    break

        # If there are longer matches, discard the diverged matches (subsumed)
        if has_longer_match:
            # DEBUG
            import os

            if os.getenv("UNIQSEQ_DEBUG"):
                with open("/tmp/uniqseq_debug.log", "a") as f:
                    f.write(
                        f"  -> Discarding (has longer {longer_match_type} match_length={longer_match_length})\n"
                    )
            return

        # Step 3: No longer matches - record the subsequence match
        # DEBUG
        import os

        if os.getenv("UNIQSEQ_DEBUG"):
            with open("/tmp/uniqseq_debug.log", "a") as f:
                seq_type = type(longest_seq).__name__
                f.write(
                    f"  -> Recording subsequence match: length={longest_length}, type={seq_type}\n"
                )

        # Finalize the match (polymorphic - handles RecordedSequence and HistorySequence differently)
        longest_seq.finalize_match(longest_length, self)

        # Emit or dispose the matched lines based on mode
        # The matched lines are at the start of the buffer
        lines_to_process = longest_length

        # Collect line numbers for annotation (before popping)
        should_annotate = self.annotate and not self.inverse and lines_to_process > 0
        if should_annotate:
            dup_start = self.line_buffer[0].input_line_num
            dup_end = self.line_buffer[
                min(lines_to_process - 1, len(self.line_buffer) - 1)
            ].input_line_num
            match_start = int(longest_seq.first_output_line)
            match_end = int(longest_seq.first_output_line + lines_to_process - 1)
            total_dup_count = sum(longest_seq.subsequence_match_counts.values())

        for _ in range(lines_to_process):
            if self.line_buffer:
                buffered_line = self.line_buffer.popleft()

                if self.inverse:
                    # Inverse mode: emit duplicate lines, UNLESS they match preloaded sequences
                    if longest_seq.first_output_line != PRELOADED_SEQUENCE_LINE:
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
            self._write_annotation(
                output, dup_start, dup_end, match_start, match_end, total_dup_count
            )
            # Explain message
            self._print_explain(
                f"Lines {dup_start}-{dup_end} skipped "
                f"(subsequence match of {longest_length} lines, seen {total_dup_count}x)"
            )

        # Clear all active tracking (subsequence match consumed part of the buffer)
        self.new_sequence_candidates.clear()
        self.potential_uniq_matches.clear()

    def _update_new_sequence_candidates(
        self, current_window_hash: str
    ) -> list[tuple[NewSequenceCandidate, int]]:
        """Update new sequence candidates by checking if current window continues the match.

        Returns:
            List of (candidate, matched_length) tuples for candidates that diverged
        """
        # OPTIMIZATION: Direct access to internal dict for faster lookups
        position_to_entry = self.window_hash_history.position_to_entry
        diverged_candidates = []

        for _candidate_id, candidate in list(self.new_sequence_candidates.items()):
            if not candidate.matching_history_positions:
                continue  # Early skip for empty candidate

            # OPTIMIZATION: Set comprehension with direct dict access
            # Replaces nested loop + method calls (get_next_position/get_key)
            still_matching = {
                hist_pos + 1  # Inline: get_next_position(hist_pos)
                for hist_pos in candidate.matching_history_positions
                if (entry := position_to_entry.get(hist_pos + 1)) is not None
                and entry.window_hash == current_window_hash
            }

            # Update candidate
            if still_matching:
                # At least one history position still matches
                candidate.matching_history_positions = still_matching
                candidate.length += 1
                candidate.buffer_depth += 1
                candidate.window_hashes.append(current_window_hash)
            else:
                # No more matching positions - candidate has diverged
                diverged_candidates.append((candidate, candidate.length))
                # Mark for cleanup (will be removed by caller)
                candidate.matching_history_positions.clear()

        return diverged_candidates

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

    # TODO: This entire method is about full matches and should be removed in subsequence model
    def _finalize_new_sequence(
        self, candidate: NewSequenceCandidate, output: Union[TextIO, BinaryIO]
    ) -> None:
        """Finalize a new sequence candidate - always results in duplicate handling."""
        raise NotImplementedError(
            "_finalize_new_sequence should not be called in subsequence model"
        )
        # # TODO: OLD FULL-MATCH CODE - REMOVE
        # # Calculate full sequence hash
        # full_sequence_hash = hash_window(candidate.length, candidate.window_hashes)
        #
        # # Check if this sequence already exists in unique_sequences
        # # (includes both observed sequences and preloaded sequences)
        # if candidate.first_window_hash in self.sequence_records:
        #     if full_sequence_hash in self.sequence_records[candidate.first_window_hash]:
        # Pattern exists - this is a repeat of a known sequence
        # existing_seq = self.sequence_records[candidate.first_window_hash][
        # full_sequence_hash
        # ]
        # Increment subsequence match count at this length
        # existing_seq.subsequence_match_counts[candidate.length] = (
        # existing_seq.subsequence_match_counts.get(candidate.length, 0) + 1
        # )
        # total_duplicate_count = sum(existing_seq.subsequence_match_counts.values())
        #                 # If this is a preloaded sequence being observed for the first time, save it
        # if (
        # existing_seq.first_output_line == PRELOADED_SEQUENCE_LINE
        # and total_duplicate_count == 1
        # and self.save_sequence_callback
        # and full_sequence_hash not in self.saved_sequences
        # ):
        # Extract sequence lines from buffer
        # sequence_lines = [
        # bl.line for bl in list(self.line_buffer)[-candidate.length - 1 : -1]
        # ]
        # self.save_sequence_callback(full_sequence_hash, sequence_lines)
        # self.saved_sequences.add(full_sequence_hash)
        #                 # Skip current buffer (it's a duplicate)
        # Write annotation if enabled (before skipping)
        # Note: Can only annotate if first occurrence has been emitted
        # (first_output_line is valid)
        # if (
        # self.annotate
        # and not self.inverse
        # and candidate.length > 0
        # and existing_seq.first_output_line != float("-inf")
        # ):
        # Duplicate lines are at positions [-count-1 : -1] (excluding newest)
        # if candidate.length < len(self.line_buffer):
        # dup_start = self.line_buffer[-candidate.length - 1].input_line_num
        # dup_end = self.line_buffer[-2].input_line_num
        # else:
        # Edge case: would skip almost all buffer
        # dup_start = self.line_buffer[0].input_line_num
        # dup_end = (
        # self.line_buffer[-2].input_line_num
        # if len(self.line_buffer) >= 2
        # else self.line_buffer[0].input_line_num
        # )
        # match_start = int(existing_seq.first_output_line)
        # match_end = match_start + candidate.length - 1
        # self._write_annotation(
        # output,
        # dup_start,
        # dup_end,
        # match_start,
        # match_end,
        # total_duplicate_count,
        # )
        # Explain message
        # self._print_explain(
        # f"Lines {dup_start}-{dup_end} skipped "
        # f"(duplicate of lines {match_start}-{match_end}, "
        # f"seen {total_duplicate_count}x)"
        # )
        # else:
        # No annotation, but still explain if enabled
        # if candidate.length < len(self.line_buffer):
        # dup_start = self.line_buffer[-candidate.length - 1].input_line_num
        # dup_end = self.line_buffer[-2].input_line_num
        # else:
        # dup_start = self.line_buffer[0].input_line_num
        # dup_end = (
        # self.line_buffer[-2].input_line_num
        # if len(self.line_buffer) >= 2
        # else self.line_buffer[0].input_line_num
        # )
        # match_start = (
        # int(existing_seq.first_output_line)
        # if existing_seq.first_output_line != float("-inf")
        # else 0
        # )
        # match_end = match_start + candidate.length - 1 if match_start > 0 else 0
        # self._print_explain(
        # f"Lines {dup_start}-{dup_end} skipped "
        # f"(duplicate, seen {total_duplicate_count}x)"
        # )
        #                 # self._skip_buffer_lines(candidate.length, output)
        # Clear all other candidates since buffer state changed
        # self.new_sequence_candidates.clear()
        # self.potential_uniq_matches.clear()
        # return
        #         # Pattern is new - create SequenceRecord for first (historical) occurrence
        # Note: The candidate represents the CURRENT occurrence (which is a duplicate)
        # The SequenceRecord represents the FIRST occurrence (in history)
        # Look up first_output_line from history (using original first position)
        # first_output_line: Union[int, float] = NEVER_OUTPUT_LINE
        # if candidate.original_first_history_position >= 0:
        # Look up the output line number from history
        # hist_entry = self.window_hash_history.get_entry(
        # candidate.original_first_history_position
        # )
        # if hist_entry and hist_entry.first_output_line is not None:
        # first_output_line = hist_entry.first_output_line
        #         # seq_rec = SequenceRecord(
        # first_window_hash=candidate.first_window_hash,
        # full_sequence_hash=full_sequence_hash,
        # first_output_line=first_output_line,
        # sequence_length=candidate.length,
        # window_hashes=candidate.window_hashes.copy(),
        # )
        # Record first duplicate at this length (current occurrence)
        # seq_rec.subsequence_match_counts[candidate.length] = 1
        #         # Add to unique_sequences
        # if candidate.first_window_hash not in self.sequence_records:
        # self.sequence_records[candidate.first_window_hash] = {}
        # self.sequence_records[candidate.first_window_hash][full_sequence_hash] = seq_rec
        #         # Save to library if callback is set (new sequence discovered)
        # if self.save_sequence_callback and full_sequence_hash not in self.saved_sequences:
        # Extract sequence lines from buffer (historical occurrence)
        # sequence_lines = [bl.line for bl in list(self.line_buffer)[-candidate.length - 1 : -1]]
        # self.save_sequence_callback(full_sequence_hash, sequence_lines)
        # self.saved_sequences.add(full_sequence_hash)
        #         # Skip current buffer (it's a duplicate of the historical occurrence)
        # Write annotation if enabled (before skipping)
        # Note: Can only annotate if first occurrence has been emitted (first_output_line is valid)
        # if (
        # self.annotate
        # and not self.inverse
        # and candidate.length > 0
        # and seq_rec.first_output_line != float("-inf")
        # ):
        # Duplicate lines are at positions [-count-1 : -1] (excluding newest)
        # if candidate.length < len(self.line_buffer):
        # dup_start = self.line_buffer[-candidate.length - 1].input_line_num
        # dup_end = self.line_buffer[-2].input_line_num
        # else:
        # Edge case: would skip almost all buffer
        # dup_start = self.line_buffer[0].input_line_num
        # dup_end = (
        # self.line_buffer[-2].input_line_num
        # if len(self.line_buffer) >= 2
        # else self.line_buffer[0].input_line_num
        # )
        # Use seq_rec.first_output_line (output line numbers from first occurrence)
        # match_start = int(seq_rec.first_output_line)
        # match_end = match_start + candidate.length - 1
        # total_dup_count = sum(seq_rec.subsequence_match_counts.values())
        # self._write_annotation(
        # output, dup_start, dup_end, match_start, match_end, total_dup_count
        # )
        # Explain message
        # self._print_explain(
        # f"Lines {dup_start}-{dup_end} skipped "
        # f"(duplicate of lines {match_start}-{match_end}, "
        # f"seen {total_dup_count}x)"
        # )
        # else:
        # No annotation, but still explain if enabled
        # if candidate.length < len(self.line_buffer):
        # dup_start = self.line_buffer[-candidate.length - 1].input_line_num
        # dup_end = self.line_buffer[-2].input_line_num
        # else:
        # dup_start = self.line_buffer[0].input_line_num
        # dup_end = (
        # self.line_buffer[-2].input_line_num
        # if len(self.line_buffer) >= 2
        # else self.line_buffer[0].input_line_num
        # )
        # total_dup_count = sum(seq_rec.subsequence_match_counts.values())
        # self._print_explain(
        # f"Lines {dup_start}-{dup_end} skipped (duplicate, seen {total_dup_count}x)"
        # )
        #         # self._skip_buffer_lines(candidate.length, output)
        #         # Clear all other candidates since buffer state changed
        # self.new_sequence_candidates.clear()
        # self.potential_uniq_matches.clear()
        #         # LRU eviction if needed
        # total_seqs = sum(len(seqs) for seqs in self.sequence_records.values())
        # if self.max_unique_sequences is not None and total_seqs > self.max_unique_sequences:
        # Remove oldest (first) entry
        # self.sequence_records.popitem(last=False)
        #     def _skip_buffer_lines(self, count: int, output: Union[TextIO, BinaryIO] = sys.stdout) -> None:
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

                # OLD APPROACH (using PotentialSeqRecMatch) - Keep for confirmed_duplicate handling only
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
                # else: OLD code commented out - using new unified approach below
                #     self.potential_uniq_matches[match_id] = match

                # NEW UNIFIED APPROACH (using RecordedSequence)
                # Create a RecordedSequence with tracking state
                candidate = RecordedSequence(
                    first_window_hash=seq.first_window_hash,
                    sequence_length=seq.sequence_length,
                    window_hashes=seq.window_hashes,
                    first_output_line=seq.first_output_line,
                    full_sequence_hash=seq.full_sequence_hash,
                    subsequence_match_counts=seq.subsequence_match_counts,
                    output_cursor_at_start=self.line_num_output,
                    next_window_index=1,  # Already matched first window
                )

                # Check if this sequence is already complete (length == window_size)
                if candidate.next_window_index >= len(candidate.window_hashes):
                    # Immediately confirmed subsequence match at full length
                    # Keep using old structure for now to avoid breaking the handling code
                    pass  # confirmed_duplicate already set above
                else:
                    # Track for future updates in unified dict
                    self.sequence_candidates[match_id] = candidate

        # Handle immediately confirmed duplicate (matched lines at END of buffer)
        if confirmed_duplicate:
            # Increment repeat count at this subsequence length
            seq = confirmed_duplicate.matched_sequence
            match_length = confirmed_duplicate.get_length()
            seq.subsequence_match_counts[match_length] = (
                seq.subsequence_match_counts.get(match_length, 0) + 1
            )
            total_dup_count = sum(seq.subsequence_match_counts.values())

            # If this is a preloaded sequence being observed for the first time, save it
            if (
                seq.first_output_line == PRELOADED_SEQUENCE_LINE
                and total_dup_count == 1
                and self.save_sequence_callback
                and seq.full_sequence_hash not in self.saved_sequences
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
                repeat_count = total_dup_count

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
            # Overlap check: Compare history positions (tracked line indices) with current position
            # Use tracked line count since history only contains tracked lines
            # Overlap if: P < (line_num_input_tracked - window_size + 1) + window_size
            # Simplifying: P < line_num_input_tracked
            current_window_start = self.line_num_input_tracked - self.window_size + 1
            non_overlapping = [
                pos for pos in history_positions if pos + self.window_size <= current_window_start
            ]

            if non_overlapping:
                # Found potential match(es) in history (non-overlapping)
                # Use input line number for stable candidate ID across output emissions
                candidate_id = f"new_{self.line_num_input}"

                if candidate_id not in self.new_sequence_candidates:
                    # Start new candidate
                    # tracked_start: where the matched window starts in tracked sequence
                    # line_num_input_tracked is current tracked line, so window starts at:
                    # line_num_input_tracked - window_size
                    # (since buffer has window_size lines before current)
                    tracked_start = self.line_num_input_tracked - self.window_size

                    # OPTIMIZATION: Limit concurrent candidates for performance
                    # Keep candidates with earliest start (longest potential match)
                    if (
                        self.max_candidates is not None
                        and len(self.new_sequence_candidates) >= self.max_candidates
                    ):
                        # Find candidate with latest start (worst for longest match)
                        worst_id = max(
                            self.new_sequence_candidates.keys(),
                            key=lambda k: self.new_sequence_candidates[k].first_tracked_line,
                        )
                        worst_start = self.new_sequence_candidates[worst_id].first_tracked_line

                        # Only evict if new candidate is better (earlier start)
                        if tracked_start < worst_start:
                            del self.new_sequence_candidates[worst_id]
                        else:
                            # New candidate is worse, skip it
                            return

                    # OLD APPROACH - commented out because NewSequenceCandidate is now alias for HistorySequence
                    # self.new_sequence_candidates[candidate_id] = NewSequenceCandidate(...)

                    # NEW UNIFIED APPROACH (using HistorySequence)
                    # Get first output line from history for this sequence
                    first_history_pos = min(non_overlapping)
                    first_output_line = self.window_hash_history.position_to_entry[
                        first_history_pos
                    ].first_output_line

                    hist_seq = HistorySequence(
                        first_window_hash=current_window_hash,
                        sequence_length=self.window_size,
                        window_hashes=[current_window_hash],
                        first_output_line=first_output_line,
                        output_cursor_at_start=self.line_num_output,
                        first_tracked_line=tracked_start,
                        buffer_depth=len(self.line_buffer) - 1,
                        matching_history_positions=set(non_overlapping),
                        original_first_history_position=first_history_pos,
                        history=self.window_hash_history,  # Store reference to history
                    )

                    # Track in unified dict
                    self.sequence_candidates[candidate_id] = hist_seq

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
