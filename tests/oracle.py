"""Oracle implementation for testing - simple but obviously correct."""

from dataclasses import dataclass, field
from typing import Any, Optional


def find_duplicates_naive(lines: list[str], window_size: int) -> tuple[list[str], int]:
    """Naive but obviously correct duplicate detection.

    Finds all sequences of window_size+ lines that appear more than once, where the first and last instance don't
    overlap with each other, and therefore constitute at least one repeat.
    Returns deduplicated output and count of skipped lines.

    This is SLOW (O(n²)) but serves as ground truth for testing.

    Algorithm:
    1. For each position i in input:
       a. Search all positions starting at i + window_size, for window-size sequences matching
       the window-size sequence position i to position i + window_size - 1
       b. If found duplicate, mark all entries of that sequence as to be skipped
    2. Emit all lines not marked as skipped

    Args:
        lines: Input lines
        window_size: Minimum sequence length to consider

    Returns:
        (deduplicated_output, skipped_line_count)
    """
    skipped = _find_skipped_positions(lines, window_size)

    output = []
    skipped_count = 0
    for i, line in enumerate(lines):
        if skipped[i]:
            skipped_count += 1
        else:
            output.append(line)

    return output, skipped_count


def _find_duplicate_windows(lines: list[str], window_size: int) -> list[tuple[int, int]]:
    """Helper to find all duplicated windows.

    Returns:
        List of (first_pos, duplicate_pos) tuples indicating duplicate windows
    """
    duplicates = []

    for i in range(len(lines)):
        if i + window_size > len(lines):
            break

        for seq_start in range(i + window_size, len(lines) - window_size + 1):
            if all(lines[i + j] == lines[seq_start + j] for j in range(window_size)):
                duplicates.append((i, seq_start))

    return duplicates


def _find_skipped_positions(lines: list[str], window_size: int) -> list[bool]:
    """Helper to find which positions should be skipped.

    Returns:
        List of booleans indicating which positions are skipped
    """
    skipped = [False] * len(lines)
    duplicates = _find_duplicate_windows(lines, window_size)

    for _, seq_start in duplicates:
        skipped[seq_start : seq_start + window_size] = [True] * window_size

    return skipped


@dataclass
class SequenceOccurrence:
    """Represents one occurrence of a sequence."""

    start_line: int  # 0-based line number where sequence starts
    length: int  # Number of lines in this occurrence
    is_duplicate: bool  # True if this occurrence was skipped as duplicate


@dataclass
class SequenceInfo:
    """Comprehensive information about a detected sequence."""

    sequence: list[str]  # The actual lines in the sequence
    sequence_hash: str  # Hash representation (for reference)
    first_occurrence_line: int  # Line number of first occurrence
    occurrences: list[SequenceOccurrence] = field(default_factory=list)

    @property
    def total_occurrences(self) -> int:
        """Total number of times this sequence appeared."""
        return len(self.occurrences)

    @property
    def duplicate_count(self) -> int:
        """Number of occurrences that were duplicates (skipped)."""
        return sum(1 for occ in self.occurrences if occ.is_duplicate)

    @property
    def lines_skipped(self) -> int:
        """Total lines skipped from duplicate occurrences."""
        return sum(occ.length for occ in self.occurrences if occ.is_duplicate)


@dataclass
class LineProcessingInfo:
    """Information about how a single line was processed."""

    line_number: int  # 0-based input line number
    line_content: str  # The actual line
    was_output: bool  # True if this line was output
    was_skipped: bool  # True if this line was skipped as part of duplicate
    output_position: Optional[int]  # Position in output (0-based), None if skipped
    part_of_sequence: Optional[str]  # Hash of sequence this line belongs to (if duplicate)
    reason: str  # Human-readable reason ("output", "skipped_duplicate", "buffered_then_output")
    buffer_depth_at_output: Optional[
        int
    ]  # Max buffer depth when this line was output (None if skipped)
    lines_in_buffer_when_output: Optional[int]  # How many lines were buffered when this was output


@dataclass
class OracleResult:
    """Complete oracle analysis results."""

    input_lines: list[str]
    output_lines: list[str]
    window_size: int
    total_lines_input: int
    total_lines_output: int
    total_lines_skipped: int
    sequences: list[SequenceInfo]  # All detected sequences (duplicates only)
    unique_sequence_count: int  # Number of unique sequences seen
    line_processing: list[LineProcessingInfo]  # Detailed per-line processing info

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "input_lines": self.input_lines,
            "output_lines": self.output_lines,
            "window_size": self.window_size,
            "total_lines_input": self.total_lines_input,
            "total_lines_output": self.total_lines_output,
            "total_lines_skipped": self.total_lines_skipped,
            "unique_sequence_count": self.unique_sequence_count,
            "sequences": [
                {
                    "sequence": seq.sequence,
                    "sequence_hash": seq.sequence_hash,
                    "first_occurrence_line": seq.first_occurrence_line,
                    "total_occurrences": seq.total_occurrences,
                    "duplicate_count": seq.duplicate_count,
                    "lines_skipped": seq.lines_skipped,
                    "occurrences": [
                        {
                            "start_line": occ.start_line,
                            "length": occ.length,
                            "is_duplicate": occ.is_duplicate,
                        }
                        for occ in seq.occurrences
                    ],
                }
                for seq in self.sequences
            ],
            "line_processing": [
                {
                    "line_number": info.line_number,
                    "line_content": info.line_content,
                    "was_output": info.was_output,
                    "was_skipped": info.was_skipped,
                    "output_position": info.output_position,
                    "part_of_sequence": info.part_of_sequence,
                    "reason": info.reason,
                    "buffer_depth_at_output": info.buffer_depth_at_output,
                    "lines_in_buffer_when_output": info.lines_in_buffer_when_output,
                }
                for info in self.line_processing
            ],
        }


def compute_sequence_hash(lines: list[str]) -> str:
    """Compute simple hash for sequence identification."""
    import hashlib

    content = "\n".join(lines).encode("utf-8")
    return hashlib.blake2b(content, digest_size=16).hexdigest()


def analyze_sequences_detailed(lines: list[str], window_size: int) -> OracleResult:
    """Comprehensive analysis tracking all sequences and their occurrences.

    This is the enhanced oracle that provides complete information about:
    - Every unique sequence detected
    - All occurrences of each sequence (first and duplicates)
    - Positions and lengths of all occurrences
    - Final output and skip counts
    - Line-by-line processing information (when each line is output vs skipped)
    - Buffer depth tracking (simulates actual buffering behavior)

    Args:
        lines: Input lines
        window_size: Minimum sequence length to consider

    Returns:
        OracleResult with complete analysis
    """
    # Use shared helpers
    skipped = _find_skipped_positions(lines, window_size)
    duplicates = _find_duplicate_windows(lines, window_size)

    # Build sequence tracking info
    # Only consider pairs where first_pos is not skipped (it's a true first occurrence)
    sequences_dict: dict[str, SequenceInfo] = {}
    for first_pos, dup_pos in duplicates:
        # Skip if first_pos is itself marked as skipped
        if skipped[first_pos]:
            continue

        seq = lines[first_pos : first_pos + window_size]
        seq_hash = compute_sequence_hash(seq)

        if seq_hash not in sequences_dict:
            sequences_dict[seq_hash] = SequenceInfo(
                sequence=seq,
                sequence_hash=seq_hash,
                first_occurrence_line=first_pos,
                occurrences=[
                    SequenceOccurrence(start_line=first_pos, length=window_size, is_duplicate=False)
                ],
            )

        sequences_dict[seq_hash].occurrences.append(
            SequenceOccurrence(start_line=dup_pos, length=window_size, is_duplicate=True)
        )

    # Build output and line processing info
    output = []
    line_processing = []
    skipped_count = 0

    for i, line in enumerate(lines):
        if skipped[i]:
            skipped_count += 1
            seq_hash = None
            for hash_val, seq_info in sequences_dict.items():
                for occ in seq_info.occurrences:
                    if occ.is_duplicate and occ.start_line <= i < occ.start_line + occ.length:
                        seq_hash = hash_val
                        break
                if seq_hash:
                    break

            line_processing.append(
                LineProcessingInfo(
                    line_number=i,
                    line_content=line,
                    was_output=False,
                    was_skipped=True,
                    output_position=None,
                    part_of_sequence=seq_hash,
                    reason="skipped_duplicate",
                    buffer_depth_at_output=None,
                    lines_in_buffer_when_output=None,
                )
            )
        else:
            output_pos = len(output)
            output.append(line)
            buffer_depth = min(i, window_size - 1)
            lines_in_buffer = buffer_depth + 1

            line_processing.append(
                LineProcessingInfo(
                    line_number=i,
                    line_content=line,
                    was_output=True,
                    was_skipped=False,
                    output_position=output_pos,
                    part_of_sequence=None,
                    reason="output_no_match",
                    buffer_depth_at_output=buffer_depth,
                    lines_in_buffer_when_output=lines_in_buffer,
                )
            )

    return OracleResult(
        input_lines=lines,
        output_lines=output,
        window_size=window_size,
        total_lines_input=len(lines),
        total_lines_output=len(output),
        total_lines_skipped=skipped_count,
        sequences=list(sequences_dict.values()),
        unique_sequence_count=len(sequences_dict),
        line_processing=line_processing,
    )
