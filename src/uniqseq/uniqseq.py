"""Core logic for uniqseq."""

import sys
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Iterator
from typing import BinaryIO, Optional, TextIO, Union

from .divergence import handle_diverged_matches
from .emission import handle_line_emission
from .filtering import FilterPattern, evaluate_filter, get_bypass_description
from .hashing import BufferedLine
from .history import PositionalFIFO
from .indexing import add_to_history_and_index
from .matching import (
    ActiveMatchManager,
    check_for_new_matches,
    update_active_matches,
)
from .output import print_explain
from .preloading import initialize_preloaded_sequences
from .processing import calculate_window_hash, prepare_line_for_deduplication
from .recording import (
    HistorySequence,
    RecordedSequence,
    SequenceRegistry,
)

MIN_SEQUENCE_LENGTH = 10
DEFAULT_MAX_HISTORY = 100000  # 100k window hashes = ~3.2 MB memory
DEFAULT_MAX_UNIQUE_SEQUENCES = 10000  # 10k sequences = ~320 KB memory
DEFAULT_MAX_CANDIDATES = 1000  # Default limit for concurrent candidates

# Public API exports
__all__ = [
    "UniqSeq",
    "FilterPattern",
    "MIN_SEQUENCE_LENGTH",
    "DEFAULT_MAX_HISTORY",
    "DEFAULT_MAX_UNIQUE_SEQUENCES",
    "DEFAULT_MAX_CANDIDATES",
]


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
        self.sequence_records = SequenceRegistry(max_sequences=max_unique_sequences)

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

        # Active matches being tracked (with max_candidates enforcement)
        self.active_matches = ActiveMatchManager(max_candidates=max_candidates)

        # Diverged matches (lines that are duplicates and can be skipped when consumed)
        # List of (start_tracked_line, end_tracked_line, orig_line, repeat_count)
        self.diverged_match_ranges: list[tuple[int, int, Union[int, float, str], int]] = []

        # Load preloaded sequences into unique_sequences
        if preloaded_sequences:
            initialize_preloaded_sequences(
                preloaded_sequences,
                self.sequence_records,
                self.sequence_window_index,
                self.delimiter,
                self.window_size,
            )

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

        # Output buffer for iterator API
        self._output_buffer: deque[Union[str, bytes]] = deque()

    def process_lines(
        self,
        lines: Iterable[Union[str, bytes]],
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
    ) -> Iterator[Union[str, bytes]]:
        """
        Process lines through duplicate detection, yielding non-duplicate lines.

        This is the preferred Pythonic API for using UniqSeq. It processes an iterable
        of lines and yields lines that should be output (non-duplicates in normal mode,
        duplicates in inverse mode).

        Args:
            lines: Iterable of lines to process (without trailing newline/delimiter)
            progress_callback: Optional callback(line_num, lines_skipped, seq_count)
                             called every 1000 lines with current statistics

        Yields:
            Lines that pass deduplication (str or bytes matching input type)

        Example:
            >>> from uniqseq import UniqSeq
            >>> deduplicator = UniqSeq(window_size=3)
            >>> input_lines = ["A", "B", "C", "A", "B", "C"]
            >>> output = list(deduplicator.process_lines(input_lines))
            >>> print(output)
            ['A', 'B', 'C']
        """
        for line in lines:
            # Process the line (adds output to buffer)
            self._process_line_internal(line, progress_callback)

            # Yield any lines that were added to output buffer
            while self._output_buffer:
                yield self._output_buffer.popleft()

        # Flush remaining lines at end of input
        self.flush()
        while self._output_buffer:
            yield self._output_buffer.popleft()

    def process_line(
        self,
        line: Union[str, bytes],
        output: Union[TextIO, "BinaryIO"] = sys.stdout,
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
    ) -> None:
        """
        Process a single line, writing output to a stream (backward compatibility wrapper).

        For new code, prefer using process_lines() iterator which is more Pythonic.

        Args:
            line: Line to process (without trailing newline/delimiter, str or bytes)
            output: Output stream (default: stdout)
            progress_callback: Optional callback(line_num, lines_skipped, seq_count)
                             called every 1000 lines with current statistics
        """
        # Process the line (adds to buffer)
        self._process_line_internal(line, progress_callback)

        # Write buffer contents to stream
        while self._output_buffer:
            output_line = self._output_buffer.popleft()
            if isinstance(output_line, bytes):
                assert isinstance(self.delimiter, bytes), "Delimiter must be bytes in binary mode"
                output.write(output_line + self.delimiter)  # type: ignore
            else:
                assert isinstance(self.delimiter, str), "Delimiter must be str in text mode"
                output.write(output_line + self.delimiter)  # type: ignore

    def flush_to_stream(self, output: Union[TextIO, "BinaryIO"] = sys.stdout) -> None:
        """
        Flush remaining buffered lines to a stream (backward compatibility wrapper).

        For new code, prefer using process_lines() iterator which handles flushing automatically.

        Args:
            output: Output stream (default: stdout)
        """
        # Flush internal buffers
        self.flush()

        # Write buffer contents to stream
        while self._output_buffer:
            output_line = self._output_buffer.popleft()
            if isinstance(output_line, bytes):
                assert isinstance(self.delimiter, bytes), "Delimiter must be bytes in binary mode"
                output.write(output_line + self.delimiter)  # type: ignore
            else:
                assert isinstance(self.delimiter, str), "Delimiter must be str in text mode"
                output.write(output_line + self.delimiter)  # type: ignore

    def _process_line_internal(
        self,
        line: Union[str, bytes],
        progress_callback: Optional[Callable[[int, int, int], None]] = None,
    ) -> None:
        """
        Internal method to process a single line through multi-phase duplicate detection.

        This method adds output to the internal buffer instead of writing to a stream.
        For the public API, use process_lines() iterator or process_line() stream wrapper.

        Args:
            line: Line to process (without trailing newline/delimiter, str or bytes)
            progress_callback: Optional callback(line_num, lines_skipped, seq_count)
                             called every 1000 lines with current statistics
        """
        self.line_num_input += 1

        # === FILTER EVALUATION: Determine if line should be deduplicated ===
        filter_action, matched_pattern = evaluate_filter(line, self.filter_patterns)
        should_deduplicate = filter_action in ("track", None)

        # Filtered lines go to separate buffer, bypassing deduplication pipeline
        if not should_deduplicate:
            action_desc = get_bypass_description(filter_action, matched_pattern)
            print_explain(f"Line {self.line_num_input} bypassed ({action_desc})", self.explain)
            self.filtered_lines.append((self.line_num_input, line))
            self._emit_merged_lines()
            return

        # For lines that participate in deduplication, prepare and buffer the line
        self.line_num_input_tracked += 1
        buffered_line = prepare_line_for_deduplication(
            line,
            self.line_num_input,
            self.line_num_input_tracked,
            self.skip_chars,
            self.hash_transform,
        )
        self.line_buffer.append(buffered_line)

        # Need full window before processing deduplication
        if len(self.line_buffer) < self.window_size:
            return

        # Calculate window hash and update history sequence position for overlap checking
        current_window_hash, current_window_start = calculate_window_hash(
            self.line_buffer, self.window_size
        )
        # Must be done BEFORE updating matches, so they can check overlap correctly
        self.history_sequence.current_input_position = current_window_start

        # === PHASE 1: Update existing active matches and collect divergences ===
        all_diverged = update_active_matches(self.active_matches, current_window_hash)

        # Handle all diverged matches with smart deduplication
        handle_diverged_matches(
            all_diverged,
            self.active_matches,
            self.line_buffer,
            self.diverged_match_ranges,
            self._output_buffer,
            self.window_size,
            self.save_sequence_callback,
            self.annotate,
            self.annotation_format,
            self.delimiter,
            self.inverse,
            self.explain,
        )

        # === PHASE 2: Start new potential matches ===
        check_for_new_matches(
            current_window_hash,
            self.sequence_window_index,
            self.active_matches,
            self.line_num_input_tracked,
            self.line_num_output,
            self.window_size,
            self.delimiter,
        )

        # === PHASE 4: Add to history ===
        # The overlap check in check_for_new_matches prevents matching against
        # overlapping positions, so we can add to history immediately
        add_to_history_and_index(
            current_window_hash,
            self.window_hash_history,
            self.history_sequence,
            self.sequence_window_index,
        )

        # === PHASE 5: Emit lines not consumed by active matches ===
        self._emit_merged_lines()

        # === PHASE 6: Call progress callback if provided ===
        if progress_callback and self.line_num_input % 1000 == 0:
            seq_count = len(self.sequence_records)
            progress_callback(self.line_num_input, self.lines_skipped, seq_count)

    def _calculate_min_buffer_depth(self) -> int:
        """Calculate minimum buffer depth required to accommodate active matches.

        Returns:
            Minimum number of lines that must remain in buffer
        """
        min_required_depth = self.window_size

        for match in self.active_matches:
            # Calculate how many lines this match spans
            match_length = self.window_size + (match.next_window_index - 1)

            # Calculate buffer depth based on tracked line numbers
            buffer_first_tracked = self.line_num_input_tracked - len(self.line_buffer) + 1
            match_first_tracked = match.tracked_line_at_start
            match_last_tracked = match.tracked_line_at_start + match_length - 1

            # Calculate overlap between buffer and match
            overlap_start = max(buffer_first_tracked, match_first_tracked)
            overlap_end = min(self.line_num_input_tracked, match_last_tracked)

            if overlap_end >= overlap_start:
                # Match has lines in buffer - calculate depth from start of match to end of buffer
                buffer_depth = self.line_num_input_tracked - overlap_start + 1
                if buffer_depth > min_required_depth:
                    min_required_depth = buffer_depth

        return min_required_depth

    def _emit_merged_lines(self) -> None:
        """Emit lines from both deduplication and filtered buffers to output buffer.

        Merges deduplicated lines and filtered lines, adding them to the output buffer
        in the order they appeared in the input stream.
        """
        # Calculate minimum buffer depth required
        min_required_depth = self._calculate_min_buffer_depth()

        # Emit lines in order by comparing line numbers from both buffers
        while True:
            # Determine what we can emit from deduplication buffer
            dedup_can_emit = len(self.line_buffer) > min_required_depth
            dedup_line_num: Union[int, float] = (
                self.line_buffer[0].input_line_num if dedup_can_emit else float("inf")
            )

            # Filtered lines can only be emitted if they come before buffered lines
            filtered_can_emit = len(self.filtered_lines) > 0
            filtered_line_num: Union[int, float]
            if filtered_can_emit and len(self.line_buffer) > 0:
                # Check if filtered line comes before EARLIEST line in buffer
                filtered_line_num = self.filtered_lines[0][0]
                filtered_can_emit = filtered_line_num < self.line_buffer[0].input_line_num
            else:
                filtered_line_num = self.filtered_lines[0][0] if filtered_can_emit else float("inf")

            # Emit whichever has the lower line number (earlier in input)
            if dedup_can_emit and dedup_line_num <= filtered_line_num:
                # Emit from deduplication buffer
                buffered_line = self.line_buffer.popleft()
                output_delta, skip_delta = handle_line_emission(
                    buffered_line,
                    self.diverged_match_ranges,
                    self._output_buffer,
                    self.window_hash_history.position_to_entry,
                    self.inverse,
                    self.explain,
                )
                self.line_num_output += output_delta
                self.lines_skipped += skip_delta
                # Update history entry with actual line number if needed
                if output_delta > 0:
                    hist_pos = buffered_line.tracked_line_num - 1
                    entry = self.window_hash_history.position_to_entry.get(hist_pos)
                    if entry and entry.first_output_line == -1:
                        entry.first_output_line = self.line_num_output
            elif filtered_can_emit and filtered_line_num < dedup_line_num:
                # Emit from filtered buffer
                _, line = self.filtered_lines.popleft()
                self._write_line(line)
                self.line_num_output += 1
            else:
                # Nothing to emit
                break

    def flush(self) -> None:
        """Emit remaining buffered lines to output buffer at EOF."""
        # Handle any remaining active matches at EOF
        if self.active_matches:
            diverged_at_eof = list(self.active_matches)
            self.active_matches.clear()
            handle_diverged_matches(
                diverged_at_eof,
                self.active_matches,
                self.line_buffer,
                self.diverged_match_ranges,
                self._output_buffer,
                self.window_size,
                self.save_sequence_callback,
                self.annotate,
                self.annotation_format,
                self.delimiter,
                self.inverse,
                self.explain,
            )

        # Flush remaining lines from both buffers in order
        while self.line_buffer or self.filtered_lines:
            dedup_line_num = (
                self.line_buffer[0].input_line_num if self.line_buffer else float("inf")
            )
            filtered_line_num = self.filtered_lines[0][0] if self.filtered_lines else float("inf")

            # Emit whichever has the lower line number
            if dedup_line_num <= filtered_line_num:
                buffered_line = self.line_buffer.popleft()
                output_delta, skip_delta = handle_line_emission(
                    buffered_line,
                    self.diverged_match_ranges,
                    self._output_buffer,
                    self.window_hash_history.position_to_entry,
                    self.inverse,
                    self.explain,
                )
                self.line_num_output += output_delta
                self.lines_skipped += skip_delta

                # Update history entry with actual line number if needed
                if output_delta > 0:
                    hist_pos = buffered_line.tracked_line_num - 1
                    entry = self.window_hash_history.position_to_entry.get(hist_pos)
                    if entry and entry.first_output_line == -1:
                        entry.first_output_line = self.line_num_output
            else:
                _, line = self.filtered_lines.popleft()
                self._write_line(line)
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
            "unique_sequences": len(self.sequence_records),
        }

    def _write_line(self, line: Union[str, bytes]) -> None:
        """Add a line to the output buffer.

        Args:
            line: Line to write (str or bytes, without delimiter)
        """
        # Append line to output buffer (no delimiter - that's added when writing to stream)
        self._output_buffer.append(line)
