"""Unit tests for hash functions."""

import pytest

from uniqseq.uniqseq import hash_line, hash_window


@pytest.mark.unit
class TestHashing:
    """Test hash function behavior."""

    def test_hash_line_deterministic(self):
        """Same line produces same hash."""
        line = "test line content"
        hash1 = hash_line(line)
        hash2 = hash_line(line)
        assert hash1 == hash2

    def test_hash_line_different_content(self):
        """Different lines produce different hashes."""
        hash1 = hash_line("line 1")
        hash2 = hash_line("line 2")
        assert hash1 != hash2

    def test_hash_line_size(self):
        """Line hash is 8 bytes (16 hex chars)."""
        hash_val = hash_line("test")
        assert len(hash_val) == 16
        # Verify it's valid hex
        int(hash_val, 16)  # Raises if not valid hex

    def test_hash_line_empty_string(self):
        """Empty string produces valid hash."""
        hash_val = hash_line("")
        assert len(hash_val) == 16

    def test_hash_line_special_characters(self):
        """Special characters handled correctly."""
        lines = [
            "line with spaces",
            "line\twith\ttabs",
            "line\nwith\nnewlines",
            "unicode: café",
            "emoji: 🔥",
        ]

        hashes = [hash_line(line) for line in lines]

        # All should be valid and different
        assert len(set(hashes)) == len(lines)
        for h in hashes:
            assert len(h) == 16

    def test_hash_window_deterministic(self):
        """Same window produces same hash."""
        hashes = ["h1", "h2", "h3"]
        hash1 = hash_window(10, hashes)
        hash2 = hash_window(10, hashes)
        assert hash1 == hash2

    def test_hash_window_size(self):
        """Window hash is 16 bytes (32 hex chars)."""
        window_hashes = ["abc123", "def456", "ghi789"]
        hash_val = hash_window(10, window_hashes)
        assert len(hash_val) == 32
        # Verify it's valid hex
        int(hash_val, 16)

    def test_hash_window_order_matters(self):
        """Window hash changes if order changes."""
        hash1 = hash_window(10, ["h1", "h2", "h3"])
        hash2 = hash_window(10, ["h3", "h2", "h1"])
        assert hash1 != hash2

    def test_hash_window_length_affects_hash(self):
        """Sequence length affects window hash."""
        hashes = ["h1", "h2", "h3"]
        hash1 = hash_window(10, hashes)
        hash2 = hash_window(15, hashes)
        assert hash1 != hash2

    def test_hash_window_empty_list(self):
        """Empty window list produces valid hash."""
        hash_val = hash_window(10, [])
        assert len(hash_val) == 32

    def test_hash_window_single_hash(self):
        """Single hash in window."""
        hash_val = hash_window(5, ["single"])
        assert len(hash_val) == 32

    def test_hash_line_collision_resistance(self):
        """Very similar lines produce different hashes."""
        lines = [
            "test line 1",
            "test line 2",
            "test line 3",
            "Test line 1",  # Different case
            "test line 1 ",  # Trailing space
        ]

        hashes = [hash_line(line) for line in lines]
        # All should be unique
        assert len(set(hashes)) == len(lines)
