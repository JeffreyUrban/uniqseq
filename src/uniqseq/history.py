"""History management for window hashes."""

from dataclasses import dataclass
from typing import Optional


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

    def append(self, key: str) -> tuple[int, Optional[tuple[str, int]]]:
        """Add key, return position and evicted entry info.

        Returns:
            Tuple of (new_position, evicted_info) where evicted_info is None
            or (evicted_key, evicted_position) if an entry was evicted.
        """
        position = self.next_position
        evicted_info: Optional[tuple[str, int]] = None

        # Evict oldest if at capacity (skip if unlimited)
        if self.maxsize is not None and len(self.position_to_entry) >= self.maxsize:
            old_entry = self.position_to_entry[self.oldest_position]
            old_key = old_entry.window_hash
            evicted_position = self.oldest_position

            self.key_to_positions[old_key].remove(self.oldest_position)
            if not self.key_to_positions[old_key]:
                del self.key_to_positions[old_key]
            del self.position_to_entry[self.oldest_position]
            self.oldest_position += 1

            evicted_info = (old_key, evicted_position)

        # Add new entry (first_output_line will be set later when first line is emitted)
        entry = HistoryEntry(window_hash=key, first_output_line=None)
        self.position_to_entry[position] = entry
        if key not in self.key_to_positions:
            self.key_to_positions[key] = []
        self.key_to_positions[key].append(position)
        self.next_position += 1

        return position, evicted_info

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
