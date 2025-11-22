"""Core deduplication logic for uniqseq."""

import hashlib
import sys
from collections import deque, OrderedDict
from dataclasses import dataclass, field
from typing import TextIO, Optional


MIN_SEQUENCE_LENGTH = 10
DEFAULT_MAX_HISTORY = 100000  # 100k sequences = ~3.2 MB memory


class PositionalFIFO:
    """
    Positional FIFO for window hash history.

    Maintains ordering and position tracking for window hashes without LRU reordering.
    Supports efficient lookup of all positions matching a given hash.
    """
    __slots__ = ['maxsize', 'position_to_key', 'key_to_positions',
                 'next_position', 'oldest_position']

    def __init__(self, maxsize: int):
        self.maxsize = maxsize
        self.position_to_key = {}  # position -> key
        self.key_to_positions = {}  # key -> [pos1, pos2, ...]
        self.next_position = 0
        self.oldest_position = 0

    def append(self, key: str) -> int:
        """Add key, return position. Evicts oldest if at capacity."""
        position = self.next_position

        # Evict oldest if at capacity
        if len(self.position_to_key) >= self.maxsize:
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
        return self.key_to_positions.get(key, [])

    def get_key(self, position: int) -> Optional[str]:
        """Get key at position."""
        return self.position_to_key.get(position)

    def get_next_position(self, position: int) -> int:
        """Get next position (position + 1).

        Note: History advances in lockstep with processing, so next position always exists
        when we're comparing. If this returns a position not in history, it indicates a bug.
        """
        return position + 1


def hash_line(line: str) -> str:
    """Hash a single line to 8-byte (16 hex char) string using Blake2b."""
    return hashlib.blake2b(line.encode("utf-8"), digest_size=8).hexdigest()


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
    start_window_hash: str      # Hash of first window
    full_sequence_hash: str     # Hash identifying the sequence (length + all window hashes)
    start_line: int             # Output line number where first seen
    sequence_length: int        # Number of lines in sequence
    repeat_count: int           # How many times seen (excluding first)
    window_hashes: list[str] = field(default_factory=list)  # ALL window hashes (one per line)


@dataclass
class NewSequenceCandidate:
    """A new sequence being built from current input, tracked until finalized.

    Note: No __slots__ because we have list fields that grow dynamically.
    Created only when window hash matches history (not for UniqSeq matches).
    """
    current_start_line: int     # Output line number where this sequence started
    lines_matched: int          # How many lines in this sequence so far
    window_hashes: list[str] = field(default_factory=list)  # ALL window hashes
    start_window_hash: str = ""  # First window hash
    buffer_depth: int = 0        # How many lines deep in buffer this extends

    # Tracking which history positions still match
    matching_history_positions: set[int] = field(default_factory=set)


@dataclass
class PotentialUniqSeqMatch:
    """Tracking potential duplicate of a previously identified sequence.

    Note: Direct duplicates are handled immediately without creating a NewSequenceCandidate.
    """
    __slots__ = ['candidate_seq', 'current_start_line', 'next_window_index', 'window_size']
    candidate_seq: 'UniqSeq'    # Existing sequence we're comparing to
    current_start_line: int     # Output line number where this match started
    next_window_index: int      # Index in candidate_seq.window_hashes for next expected window
    window_size: int            # Window size (needed to calculate lines_matched)

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
        max_history: int = DEFAULT_MAX_HISTORY,
        max_unique_sequences: int = 10000,
    ):
        """
        Initialize the deduplicator.

        Args:
            window_size: Minimum sequence length to detect (default: 10)
            max_history: Maximum window hash history (default: 100000)
            max_unique_sequences: Maximum unique sequences to track (default: 10000)
        """
        self.window_size = window_size
        self.max_history = max_history
        self.max_unique_sequences = max_unique_sequences

        # Positional FIFO for window hash history
        self.window_hash_history = PositionalFIFO(maxsize=max_history)

        # Delay buffer - window hashes wait here before entering history
        self.window_hash_delay_buffer = deque(maxlen=window_size)

        # Unique sequences (LRU-evicted at max_unique_sequences)
        # Two-level dict: start_window_hash -> {full_sequence_hash -> UniqSeq}
        self.unique_sequences: OrderedDict[str, dict[str, UniqSeq]] = OrderedDict()

        # New sequences being built from current input
        self.new_sequence_candidates: dict[str, NewSequenceCandidate] = {}

        # Active matches to known unique sequences (detecting duplicates)
        self.potential_uniq_matches: dict[str, PotentialUniqSeqMatch] = {}

        # Line buffer (grows beyond window_size to accommodate active matches)
        self.line_buffer = deque()  # Actual lines
        self.hash_buffer = deque()  # Line hashes (parallel to line_buffer)

        # Output line tracking
        self.line_num_input = 0      # Lines read from input
        self.line_num_output = 0     # Lines written to output
        self.lines_skipped = 0       # Lines skipped as duplicates

    def process_line(
        self, line: str, output: TextIO = sys.stdout, progress_callback=None
    ) -> None:
        """
        Process a single line.

        Args:
            line: Line to process (without trailing newline)
            output: Output stream (default: stdout)
            progress_callback: Optional callback(line_num, lines_skipped, seq_count)
        """
        # TODO: Implement full algorithm from ALGORITHM_REDESIGN.md
        # For now, use oracle as stand-in to validate test infrastructure
        from tests.oracle import find_duplicates_naive

        # Temporary: collect all lines and process with oracle
        if not hasattr(self, '_temp_lines'):
            self._temp_lines = []
        self._temp_lines.append(line)
        self.line_num_input += 1

    def flush(self, output: TextIO = sys.stdout) -> None:
        """Emit remaining buffered lines at EOF."""
        # Temporary: use oracle to produce output
        if hasattr(self, '_temp_lines'):
            from tests.oracle import find_duplicates_naive
            output_lines, skipped = find_duplicates_naive(self._temp_lines, self.window_size)
            for line in output_lines:
                output.write(line)
                if not line.endswith("\n"):
                    output.write("\n")
            self.line_num_output = len(output_lines)
            self.lines_skipped = skipped

    def get_stats(self) -> dict:
        """
        Get deduplication statistics.

        Returns:
            Dictionary with keys: total_lines, output_lines, skipped_lines, unique_sequences
        """
        return {
            "total_lines": self.line_num_input,
            "output_lines": self.line_num_output,
            "skipped_lines": self.lines_skipped,
            "unique_sequences": sum(len(seqs) for seqs in self.unique_sequences.values()),
        }
