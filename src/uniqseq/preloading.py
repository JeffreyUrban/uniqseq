"""Preloaded sequence initialization and deduplication."""

from typing import Union

from .hashing import hash_line, hash_window
from .recording import PRELOADED_SEQUENCE_LINE, RecordedSequence, SequenceRegistry


def initialize_preloaded_sequences(
    preloaded_sequences: set[Union[str, bytes]],
    sequence_records: SequenceRegistry,
    sequence_window_index: dict[str, list[tuple[RecordedSequence, int]]],
    delimiter: Union[str, bytes],
    window_size: int,
) -> None:
    """Initialize preloaded sequences into the sequence registry and window index.

    Deduplicates fully nested subsequences:
    - Removes any sequence that is fully nested within a longer sequence
    - Among identical sequences, keeps only one

    Args:
        preloaded_sequences: Set of sequence_content strings/bytes
        sequence_records: Registry to add sequences to
        sequence_window_index: Window index to populate
        delimiter: Delimiter used to split sequences into lines
        window_size: Minimum sequence length
    """
    # First pass: compute window hashes for all sequences
    sequence_data = []  # List of (window_hashes,)

    for sequence in preloaded_sequences:
        # Split sequence into lines (WITHOUT delimiters to match process_line input)
        if isinstance(sequence, bytes):
            assert isinstance(delimiter, bytes)
            lines_without_delim: list[Union[str, bytes]] = list(sequence.split(delimiter))
        else:
            assert isinstance(delimiter, str)
            lines_without_delim = list(sequence.split(delimiter))

        sequence_length = len(lines_without_delim)

        # Skip if sequence is shorter than window size
        if sequence_length < window_size:
            continue

        # Compute line hashes (lines don't have delimiters, matching process_line)
        line_hashes = [hash_line(line) for line in lines_without_delim]

        # Compute all window hashes for this sequence
        seq_window_hashes = []
        for i in range(sequence_length - window_size + 1):
            window_hash = hash_window(window_size, line_hashes[i : i + window_size])
            seq_window_hashes.append(window_hash)

        sequence_data.append(tuple(seq_window_hashes))

    # Second pass: deduplicate nested and identical sequences
    deduplicated = deduplicate_nested_sequences(sequence_data)

    # Third pass: create RecordedSequence objects and add to data structures
    for window_hashes_tuple in deduplicated:
        window_hashes: list[str] = list(window_hashes_tuple)
        # Create RecordedSequence object with PRELOADED_SEQUENCE_LINE as first_output_line
        seq_rec = RecordedSequence(
            first_output_line=PRELOADED_SEQUENCE_LINE,
            window_hashes=window_hashes,
            counts=None,  # Preloaded sequences start with 0 matches
        )

        # Add to sequence registry
        sequence_records.add(seq_rec)

        # Add all windows to the window index
        index_sequence_windows(seq_rec, sequence_window_index)


def deduplicate_nested_sequences(
    sequences: list[tuple[str, ...]],
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
            if is_nested_in(seq_i, seq_j):
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


def is_nested_in(needle: tuple[str, ...], haystack: tuple[str, ...]) -> bool:
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


def index_sequence_windows(
    sequence: RecordedSequence,
    sequence_window_index: dict[str, list[tuple[RecordedSequence, int]]],
) -> None:
    """Add all windows of a sequence to the window index.

    Args:
        sequence: The sequence to index
        sequence_window_index: Window index to populate
    """
    # For each window in the sequence, add (sequence, window_index) to the index
    index = 0
    while True:
        window_hash = sequence.get_window_hash(index)
        if window_hash is None:
            break
        sequence_window_index[window_hash].append((sequence, index))
        index += 1
