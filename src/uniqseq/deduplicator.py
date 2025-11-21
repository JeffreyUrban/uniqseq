"""Core deduplication logic for uniqseq."""

import hashlib
import sys
from collections import deque
from typing import TextIO


MIN_SEQUENCE_LENGTH = 10
DEFAULT_MAX_HISTORY = 100000  # 100k sequences = ~3.2 MB memory


def hash_line(line: str) -> str:
    """Hash a single line to fixed-length hex string."""
    return hashlib.blake2b(line.encode("utf-8"), digest_size=8).hexdigest()


def hash_sequence(line_hashes: list) -> str:
    """Hash a sequence of line hashes."""
    combined = "".join(line_hashes)
    return hashlib.blake2b(combined.encode("ascii"), digest_size=16).hexdigest()


class StreamingDeduplicator:
    """
    Streaming line sequence deduplicator.

    Simple algorithm: maintain rolling window, check each window against history.
    """

    def __init__(
        self,
        window_size: int = MIN_SEQUENCE_LENGTH,
        max_history: int = DEFAULT_MAX_HISTORY,
    ):
        """
        Initialize the deduplicator.

        Args:
            window_size: Minimum sequence length to detect (default: 10)
            max_history: Maximum number of unique sequences to track (default: 10000)
        """
        self.window_size = window_size
        self.max_history = max_history

        # FIFO buffer for current window
        self.line_buffer = deque(maxlen=window_size)  # Actual lines
        self.hash_buffer = deque(maxlen=window_size)  # Line hashes

        # History of seen sequences
        self.sequence_history = set()  # Just track seen sequence hashes

        # Stats
        self.line_num = 0
        self.lines_emitted = 0
        self.lines_skipped = 0

    def process_line(
        self, line: str, output: TextIO = sys.stdout, progress_callback=None
    ) -> None:
        """
        Process a single line.

        Emits non-duplicate lines to output immediately.

        Args:
            line: Line to process (without trailing newline)
            output: Output stream (default: stdout)
            progress_callback: Optional callback(line_num, lines_skipped, seq_count)
        """
        self.line_num += 1
        line_hash = hash_line(line)

        # Update progress if callback provided
        if progress_callback and self.line_num % 1000 == 0:
            progress_callback(
                self.line_num, self.lines_skipped, len(self.sequence_history)
            )

        # Add to buffer
        self.line_buffer.append(line)
        self.hash_buffer.append(line_hash)

        # Need full window before checking for duplicates
        if len(self.hash_buffer) < self.window_size:
            return

        # Check if current window matches history
        seq_hash = hash_sequence(list(self.hash_buffer))

        if seq_hash in self.sequence_history:
            # Duplicate detected! Discard buffer
            self.line_buffer.clear()
            self.hash_buffer.clear()
            self.lines_skipped += self.window_size
        else:
            # New unique sequence - add to history
            self.sequence_history.add(seq_hash)

            # Limit history growth
            if len(self.sequence_history) > self.max_history:
                # Clear history and rebuild from scratch
                # (Alternative: use LRU cache, but this is simpler)
                self.sequence_history.clear()

            # Emit oldest line from buffer (FIFO)
            emitted_line = self.line_buffer.popleft()
            self.hash_buffer.popleft()
            output.write(emitted_line)
            if not emitted_line.endswith("\n"):
                output.write("\n")
            self.lines_emitted += 1

    def flush(self, output: TextIO = sys.stdout) -> None:
        """Emit remaining buffered lines at EOF."""
        while self.line_buffer:
            line = self.line_buffer.popleft()
            output.write(line)
            if not line.endswith("\n"):
                output.write("\n")
            self.lines_emitted += 1

    def get_stats(self) -> dict:
        """
        Get deduplication statistics.

        Returns:
            Dictionary with keys: total, emitted, skipped, redundancy_pct, unique_sequences
        """
        total = self.line_num
        redundancy = 100 * self.lines_skipped / total if total > 0 else 0

        return {
            "total": total,
            "emitted": self.lines_emitted,
            "skipped": self.lines_skipped,
            "redundancy_pct": redundancy,
            "unique_sequences": len(self.sequence_history),
        }
