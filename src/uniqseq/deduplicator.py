"""Core deduplication logic for uniqseq."""

import hashlib
import sys
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import BinaryIO, Optional, TextIO, Union

MIN_SEQUENCE_LENGTH = 10
DEFAULT_MAX_HISTORY = 100000  # 100k sequences = ~3.2 MB memory


class PositionalFIFO:
    """
    Positional FIFO for window hash history.

    Maintains ordering and position tracking for window hashes without LRU reordering.
    Supports efficient lookup of all positions matching a given hash.
    Supports unlimited mode (maxsize=None) for unbounded growth.
    """

    __slots__ = [
        "maxsize",
        "position_to_key",
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
        self.position_to_key: dict[int, str] = {}  # position -> key
        self.key_to_positions: dict[str, list[int]] = {}  # key -> [pos1, pos2, ...]
        self.next_position = 0
        self.oldest_position = 0

    def append(self, key: str) -> int:
        """Add key, return position. Evicts oldest if at capacity (unless unlimited)."""
        position = self.next_position

        # Evict oldest if at capacity (skip if unlimited)
        if self.maxsize is not None and len(self.position_to_key) >= self.maxsize:
            old_key = self.position_to_key[self.oldest_position]
            self.key_to_positions[old_key].remove(self.oldest_position)
            if not self.key_to_positions[old_key]:
                del self.key_to_positions[old_key]
            del self.position_to_key[self.oldest_position]
            self.oldest_position += 1

        # Add new entry
        self.position_to_key[position] = key
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
        """Get key at position."""
        return self.position_to_key.get(position)

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
class UniqSeq:
    """A unique sequence pattern identified during processing.

    Note: No __slots__ because we have a list field (window_hashes) that grows dynamically.
    """

    start_window_hash: str  # Hash of first window
    full_sequence_hash: str  # Hash identifying the sequence (length + all window hashes)
    start_line: int  # Output line number where first seen
    sequence_length: int  # Number of lines in sequence
    repeat_count: int  # How many times seen (excluding first)
    window_hashes: list[str] = field(default_factory=list)  # ALL window hashes (one per line)


@dataclass
class NewSequenceCandidate:
    """A new sequence being built from current input, tracked until finalized.

    Note: No __slots__ because we have list fields that grow dynamically.
    Created only when window hash matches history (not for UniqSeq matches).
    """

    current_start_line: int  # Output line number where this sequence started
    input_start_line: int  # Input line number where this sequence started (0-indexed)
    lines_matched: int  # How many lines in this sequence so far
    window_hashes: list[str] = field(default_factory=list)  # ALL window hashes
    start_window_hash: str = ""  # First window hash
    buffer_depth: int = 0  # How many lines deep in buffer this extends

    # Tracking which history positions still match
    matching_history_positions: set[int] = field(default_factory=set)


@dataclass
class PotentialUniqSeqMatch:
    """Tracking potential duplicate of a previously identified sequence.

    Note: Direct duplicates are handled immediately without creating a NewSequenceCandidate.
    """

    __slots__ = ["candidate_seq", "current_start_line", "next_window_index", "window_size"]
    candidate_seq: "UniqSeq"  # Existing sequence we're comparing to
    current_start_line: int  # Output line number where this match started
    next_window_index: int  # Index in candidate_seq.window_hashes for next expected window
    window_size: int  # Window size (needed to calculate lines_matched)

    def get_lines_matched(self) -> int:
        """Calculate how many lines matched so far."""
        return self.window_size + (self.next_window_index - 1)

    def get_buffer_depth(self, line_num_output: int) -> int:
        """Calculate how deep in buffer this match extends."""
        lines_matched = self.get_lines_matched()
        return (self.current_start_line - line_num_output) + lines_matched


class StreamingDeduplicator:
    """
    Streaming line sequence deduplicator with context-aware matching.

    Tracks WHERE sequences occur to enable proper duplicate detection.
    """

    def __init__(
        self,
        window_size: int = MIN_SEQUENCE_LENGTH,
        max_history: Optional[int] = DEFAULT_MAX_HISTORY,
        max_unique_sequences: int = 10000,
        skip_chars: int = 0,
    ):
        """
        Initialize the deduplicator.

        Args:
            window_size: Minimum sequence length to detect (default: 10)
            max_history: Maximum window hash history (default: 100000), or None for unlimited
            max_unique_sequences: Maximum unique sequences to track (default: 10000)
            skip_chars: Number of characters to skip from line start when hashing (default: 0)
        """
        self.window_size = window_size
        self.max_history = max_history
        self.max_unique_sequences = max_unique_sequences
        self.skip_chars = skip_chars

        # Positional FIFO for window hash history
        self.window_hash_history = PositionalFIFO(maxsize=max_history)

        # Delay buffer - window hashes wait here before entering history
        # The overlap check in _check_for_new_uniq_matches handles preventing
        # matches against overlapping positions, so we can add to history immediately
        self.window_hash_delay_buffer: deque[str] = deque(maxlen=1)  # Size 1 = immediate entry

        # Unique sequences (LRU-evicted at max_unique_sequences)
        # Two-level dict: start_window_hash -> {full_sequence_hash -> UniqSeq}
        self.unique_sequences: OrderedDict[str, dict[str, UniqSeq]] = OrderedDict()

        # New sequences being built from current input
        self.new_sequence_candidates: dict[str, NewSequenceCandidate] = {}

        # Active matches to known unique sequences (detecting duplicates)
        self.potential_uniq_matches: dict[str, PotentialUniqSeqMatch] = {}

        # Line buffer (grows beyond window_size to accommodate active matches)
        self.line_buffer: deque[Union[str, bytes]] = deque()  # Actual lines (str or bytes)
        self.hash_buffer: deque[str] = deque()  # Line hashes (parallel to line_buffer)

        # Output line tracking
        self.line_num_input = 0  # Lines read from input
        self.line_num_output = 0  # Lines written to output
        self.lines_skipped = 0  # Lines skipped as duplicates

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
        """
        self.line_num_input += 1

        # Hash the line (with prefix skipping if configured)
        line_hash = hash_line(line, self.skip_chars)

        # Add to buffers
        self.line_buffer.append(line)
        self.hash_buffer.append(line_hash)

        # Need full window before processing
        if len(self.hash_buffer) < self.window_size:
            return

        # Calculate window hash for current position
        window_line_hashes = list(self.hash_buffer)[-self.window_size :]
        current_window_hash = hash_window(self.window_size, window_line_hashes)

        # === PHASE 1: Update existing potential matches ===
        self._update_potential_uniq_matches(current_window_hash)

        # === PHASE 1b: Update new sequence candidates state ===
        self._update_new_sequence_candidates(current_window_hash)

        # === PHASE 2: Check if any new sequences should be finalized ===
        self._check_for_finalization()

        # === PHASE 3: Start new potential matches ===
        self._check_for_new_uniq_matches(current_window_hash)

        # === PHASE 4: Add to history (with 1-cycle delay to prevent matching current window) ===
        if len(self.window_hash_delay_buffer) == 1:
            # Delay buffer has 1 item - add it to history before it gets evicted
            evicted_hash = self.window_hash_delay_buffer[0]
            self.window_hash_history.append(evicted_hash)

        self.window_hash_delay_buffer.append(current_window_hash)

        # === PHASE 5: Emit lines not consumed by active matches ===
        self._emit_available_lines(output)

    def flush(self, output: Union[TextIO, BinaryIO] = sys.stdout) -> None:
        """Emit remaining buffered lines at EOF."""
        # Finalize any remaining new sequence candidates
        # (they've reached EOF, so no more lines to match)
        # At EOF, candidates' lines fill the entire buffer, so skip them all
        # BUT: Only if the candidate represents a complete duplicate sequence
        # that was DETECTABLE at the position where it starts
        for candidate in list(self.new_sequence_candidates.values()):
            # Calculate how many lines from candidate start to EOF
            lines_from_start_to_eof = self.line_num_input - candidate.input_start_line

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
                    # Skip all candidate lines from the buffer
                    for _ in range(min(candidate.lines_matched, len(self.line_buffer))):
                        self.line_buffer.pop()
                        self.hash_buffer.pop()
                        self.lines_skipped += 1

                    # Create UniqSeq for this pattern (if not already exists)
                    self._record_sequence_pattern(candidate)

        self.new_sequence_candidates.clear()

        # Flush remaining buffer
        while self.line_buffer:
            line = self.line_buffer.popleft()
            self.hash_buffer.popleft()
            self._write_line(output, line)
            self.line_num_output += 1

    def _record_sequence_pattern(self, candidate: NewSequenceCandidate) -> None:
        """Record a sequence pattern in unique_sequences without skipping buffer."""
        full_sequence_hash = hash_window(candidate.lines_matched, candidate.window_hashes)

        if candidate.start_window_hash not in self.unique_sequences:
            self.unique_sequences[candidate.start_window_hash] = {}

        if full_sequence_hash not in self.unique_sequences[candidate.start_window_hash]:
            # Create new UniqSeq for first occurrence
            new_seq = UniqSeq(
                start_window_hash=candidate.start_window_hash,
                full_sequence_hash=full_sequence_hash,
                start_line=candidate.current_start_line - candidate.lines_matched,
                sequence_length=candidate.lines_matched,
                repeat_count=1,
                window_hashes=candidate.window_hashes.copy(),
            )
            self.unique_sequences[candidate.start_window_hash][full_sequence_hash] = new_seq
        else:
            # Increment repeat count
            self.unique_sequences[candidate.start_window_hash][full_sequence_hash].repeat_count += 1

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
            "unique_sequences": sum(len(seqs) for seqs in self.unique_sequences.values()),
        }

    def _update_potential_uniq_matches(self, current_window_hash: str) -> None:
        """Update matches against known unique sequences using window-by-window comparison."""
        to_remove = []
        confirmed_duplicate = None

        for match_id, match in list(self.potential_uniq_matches.items()):
            # Check if we've already matched all windows
            if match.next_window_index >= len(match.candidate_seq.window_hashes):
                # Already matched everything - this shouldn't happen, but handle it
                to_remove.append(match_id)
                continue

            # Verify current window hash matches expected hash
            expected_hash = match.candidate_seq.window_hashes[match.next_window_index]

            if current_window_hash != expected_hash:
                # Mismatch! This is not a duplicate - remove from tracking
                to_remove.append(match_id)
                continue

            # Window matches! Move to next window
            match.next_window_index += 1

            # Check if we've matched all windows (reached full sequence length)
            if match.next_window_index >= len(match.candidate_seq.window_hashes):
                # CONFIRMED DUPLICATE!
                confirmed_duplicate = match
                to_remove.append(match_id)
                break

        # Clean up non-matching and completed matches
        for match_id in to_remove:
            del self.potential_uniq_matches[match_id]

        # Handle confirmed duplicate
        if confirmed_duplicate:
            self._handle_duplicate(confirmed_duplicate)

    def _handle_duplicate(self, match: PotentialUniqSeqMatch) -> None:
        """Handle a confirmed duplicate sequence."""
        # Increment repeat count for the unique sequence
        match.candidate_seq.repeat_count += 1

        # Discard buffered lines (they're duplicates)
        lines_to_skip = match.get_lines_matched()
        for _ in range(lines_to_skip):
            if self.line_buffer:
                self.line_buffer.popleft()
                self.hash_buffer.popleft()
                self.lines_skipped += 1

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
                candidate.lines_matched += 1
                candidate.buffer_depth += 1
                candidate.window_hashes.append(current_window_hash)
            else:
                # No more matching positions - candidate should be finalized
                # (Don't update it, just mark for finalization in Phase 2)
                candidate.matching_history_positions.clear()

    def _check_for_finalization(self) -> None:
        """Check if any new sequence candidates should be finalized as unique sequences."""
        # Use list() to avoid "dictionary changed size during iteration" error
        # (finalization clears candidates dict)
        for _candidate_id, candidate in list(self.new_sequence_candidates.items()):
            # Check if all matching history positions have been exhausted
            if not candidate.matching_history_positions:
                # No more potential matches - this is a new unique sequence!
                self._finalize_new_sequence(candidate)
                # _finalize_new_sequence clears all candidates, so we're done
                return

    def _finalize_new_sequence(self, candidate: NewSequenceCandidate) -> None:
        """Finalize a new sequence candidate - always results in duplicate handling."""
        # Calculate full sequence hash
        full_sequence_hash = hash_window(candidate.lines_matched, candidate.window_hashes)

        # Check if this pattern already exists in unique_sequences
        if candidate.start_window_hash in self.unique_sequences:
            if full_sequence_hash in self.unique_sequences[candidate.start_window_hash]:
                # Pattern exists - this is a repeat of a known sequence
                existing_seq = self.unique_sequences[candidate.start_window_hash][
                    full_sequence_hash
                ]
                existing_seq.repeat_count += 1
                # Skip current buffer (it's a duplicate)
                self._skip_buffer_lines(candidate.lines_matched)
                # Clear all other candidates since buffer state changed
                self.new_sequence_candidates.clear()
                self.potential_uniq_matches.clear()
                return

        # Pattern is new - create UniqSeq for first (historical) occurrence
        # Note: The candidate represents the CURRENT occurrence (which is a duplicate)
        # The UniqSeq represents the FIRST occurrence (in history)
        new_seq = UniqSeq(
            start_window_hash=candidate.start_window_hash,
            full_sequence_hash=full_sequence_hash,
            # Historical position
            start_line=candidate.current_start_line - candidate.lines_matched,
            sequence_length=candidate.lines_matched,
            repeat_count=1,  # Current occurrence is first repeat
            window_hashes=candidate.window_hashes.copy(),
        )

        # Add to unique_sequences
        if candidate.start_window_hash not in self.unique_sequences:
            self.unique_sequences[candidate.start_window_hash] = {}
        self.unique_sequences[candidate.start_window_hash][full_sequence_hash] = new_seq

        # Skip current buffer (it's a duplicate of the historical occurrence)
        self._skip_buffer_lines(candidate.lines_matched)

        # Clear all other candidates since buffer state changed
        self.new_sequence_candidates.clear()
        self.potential_uniq_matches.clear()

        # LRU eviction if needed
        total_seqs = sum(len(seqs) for seqs in self.unique_sequences.values())
        if total_seqs > self.max_unique_sequences:
            # Remove oldest (first) entry
            self.unique_sequences.popitem(last=False)

    def _skip_buffer_lines(self, count: int) -> None:
        """Skip lines from near the end of buffer (excluding the newest line).

        This is called after a candidate fails to match the current line.
        The candidate's lines are in the buffer, but NOT including the current line
        which was just added and caused the mismatch.

        So we need to remove lines at positions buffer[-count-1 : -1].
        """
        if count <= 0 or count >= len(self.line_buffer):
            # Edge case: skip all but the newest line
            while len(self.line_buffer) > 1:
                self.line_buffer.pop()
                self.hash_buffer.pop()
                self.lines_skipped += 1
            return

        # Remove lines at positions [-count-1 : -1]
        # Convert deque to list, remove range, convert back
        line_list = list(self.line_buffer)
        hash_list = list(self.hash_buffer)

        # Remove the range
        del line_list[-count - 1 : -1]
        del hash_list[-count - 1 : -1]

        self.lines_skipped += count

        # Replace deque contents
        self.line_buffer.clear()
        self.line_buffer.extend(line_list)
        self.hash_buffer.clear()
        self.hash_buffer.extend(hash_list)

    def _check_for_new_uniq_matches(self, current_window_hash: str) -> None:
        """Check for new matches against known unique sequences or history."""
        # Phase 3a: Check against known unique sequences
        if current_window_hash in self.unique_sequences:
            # Found potential match(es) against known unique sequence(s)
            for seq in self.unique_sequences[current_window_hash].values():
                # Start tracking this potential duplicate
                match_id = f"uniq_{self.line_num_output}_{seq.start_line}"
                self.potential_uniq_matches[match_id] = PotentialUniqSeqMatch(
                    candidate_seq=seq,
                    current_start_line=self.line_num_output,
                    next_window_index=1,  # Already matched first window
                    window_size=self.window_size,
                )

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
                        current_start_line=self.line_num_output,
                        input_start_line=input_start,
                        lines_matched=self.window_size,
                        window_hashes=[current_window_hash],
                        start_window_hash=current_window_hash,
                        buffer_depth=len(self.line_buffer) - 1,
                        matching_history_positions=set(non_overlapping),
                    )

    def _write_line(self, output: Union[TextIO, BinaryIO], line: Union[str, bytes]) -> None:
        """Write a line to output with appropriate newline handling.

        Args:
            output: Output stream (text or binary)
            line: Line to write (str or bytes)
        """
        if isinstance(line, bytes):
            # Binary mode: write bytes, add newline if not present
            output.write(line)  # type: ignore
            if not line.endswith(b"\n"):
                output.write(b"\n")  # type: ignore
        else:
            # Text mode: write str, add newline if not present
            output.write(line)  # type: ignore
            if not line.endswith("\n"):
                output.write("\n")  # type: ignore

    def _emit_available_lines(self, output: Union[TextIO, BinaryIO]) -> None:
        """Emit lines from buffer that are not part of any active match."""
        # Find minimum buffer depth across all active matches
        # Default: maintain window_size buffer when no active matches
        min_required_depth = self.window_size

        # Check new sequence candidates
        for candidate in self.new_sequence_candidates.values():
            min_required_depth = max(min_required_depth, candidate.buffer_depth)

        # Check potential uniq matches
        for match in self.potential_uniq_matches.values():
            buffer_depth = match.get_buffer_depth(self.line_num_output)
            min_required_depth = max(min_required_depth, buffer_depth)

        # Emit lines from front of buffer that are beyond min_required_depth
        while len(self.line_buffer) > min_required_depth:
            line = self.line_buffer.popleft()
            self.hash_buffer.popleft()
            self._write_line(output, line)
            self.line_num_output += 1
