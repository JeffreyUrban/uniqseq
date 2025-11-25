"""Unit tests for PositionalFIFO data structure."""

import pytest

from uniqseq.uniqseq import PositionalFIFO


@pytest.mark.unit
class TestPositionalFIFO:
    """Test the PositionalFIFO data structure."""

    def test_append_and_retrieve(self):
        """Can append items and retrieve by position."""
        fifo = PositionalFIFO(maxsize=100)
        pos1 = fifo.append("hash1")
        pos2 = fifo.append("hash2")

        assert pos1 == 0
        assert pos2 == 1
        assert fifo.get_key(0) == "hash1"
        assert fifo.get_key(1) == "hash2"

    def test_find_all_positions(self):
        """Can find all positions matching a key."""
        fifo = PositionalFIFO(maxsize=100)
        fifo.append("A")
        fifo.append("B")
        fifo.append("A")
        fifo.append("C")
        fifo.append("A")

        positions = fifo.find_all_positions("A")
        assert positions == [0, 2, 4]

    def test_find_all_positions_empty(self):
        """find_all_positions returns empty list for non-existent key."""
        fifo = PositionalFIFO(maxsize=100)
        fifo.append("A")
        fifo.append("B")

        positions = fifo.find_all_positions("C")
        assert positions == []

    def test_get_next_position(self):
        """get_next_position returns position + 1."""
        fifo = PositionalFIFO(maxsize=100)
        fifo.append("hash1")
        fifo.append("hash2")

        assert fifo.get_next_position(0) == 1
        assert fifo.get_next_position(1) == 2
        assert fifo.get_next_position(99) == 100

    def test_eviction_at_capacity(self):
        """Oldest entries evicted when maxsize reached."""
        fifo = PositionalFIFO(maxsize=3)
        fifo.append("A")  # pos 0
        fifo.append("B")  # pos 1
        fifo.append("C")  # pos 2
        fifo.append("D")  # pos 3, evicts pos 0

        assert fifo.get_key(0) is None  # Evicted
        assert fifo.get_key(1) == "B"
        assert fifo.get_key(2) == "C"
        assert fifo.get_key(3) == "D"

    def test_find_positions_after_eviction(self):
        """find_all_positions excludes evicted entries."""
        fifo = PositionalFIFO(maxsize=3)
        fifo.append("A")  # pos 0
        fifo.append("B")  # pos 1
        fifo.append("A")  # pos 2
        fifo.append("C")  # pos 3, evicts pos 0

        positions = fifo.find_all_positions("A")
        assert positions == [2]  # pos 0 evicted

    def test_empty_fifo(self):
        """Operations on empty FIFO behave correctly."""
        fifo = PositionalFIFO(maxsize=10)

        assert fifo.get_key(0) is None
        assert fifo.find_all_positions("any") == []

    def test_multiple_evictions(self):
        """Multiple evictions work correctly."""
        fifo = PositionalFIFO(maxsize=2)

        # Add 5 items, should evict first 3
        for i in range(5):
            fifo.append(f"item_{i}")

        # Only last 2 should remain
        assert fifo.get_key(0) is None
        assert fifo.get_key(1) is None
        assert fifo.get_key(2) is None
        assert fifo.get_key(3) == "item_3"
        assert fifo.get_key(4) == "item_4"

    def test_same_key_multiple_positions(self):
        """Same key can appear at multiple positions."""
        fifo = PositionalFIFO(maxsize=10)

        fifo.append("X")  # 0
        fifo.append("Y")  # 1
        fifo.append("X")  # 2
        fifo.append("Z")  # 3
        fifo.append("X")  # 4

        positions = fifo.find_all_positions("X")
        assert len(positions) == 3
        assert positions == [0, 2, 4]

    def test_sequential_positions(self):
        """Positions increment sequentially."""
        fifo = PositionalFIFO(maxsize=100)

        positions = []
        for i in range(10):
            pos = fifo.append(f"val_{i}")
            positions.append(pos)

        assert positions == list(range(10))
