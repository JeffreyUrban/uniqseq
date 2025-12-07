"""Window hash indexing and history management."""

from .history import PositionalFIFO
from .recording import HistorySequence, RecordedSequence


def add_to_history_and_index(
    current_window_hash: str,
    window_hash_history: PositionalFIFO,
    history_sequence: HistorySequence,
    sequence_window_index: dict[str, list[tuple[RecordedSequence, int]]],
) -> None:
    """Add current window to history and update the window index.

    Handles eviction cleanup when history entries are removed.

    Args:
        current_window_hash: Hash of current window to add
        window_hash_history: FIFO history of window hashes
        history_sequence: Virtual sequence representing history
        sequence_window_index: Index mapping window hashes to (sequence, position) pairs
    """
    # Add to history (may evict old entry)
    history_position, evicted_info = window_hash_history.append(current_window_hash)

    # Clean up sequence_window_index if a history entry was evicted
    if evicted_info is not None:
        evicted_key, evicted_position = evicted_info
        # Remove the evicted (history_sequence, position) from the window index
        if evicted_key in sequence_window_index:
            # Filter out entries matching the evicted position
            sequence_window_index[evicted_key] = [
                (seq, pos)
                for seq, pos in sequence_window_index[evicted_key]
                if not (seq is history_sequence and pos == evicted_position)
            ]
            # Remove the key entirely if no entries remain
            if not sequence_window_index[evicted_key]:
                del sequence_window_index[evicted_key]

    # Index this window in the window index (maps to history_sequence at this position)
    sequence_window_index[current_window_hash].append((history_sequence, history_position))
