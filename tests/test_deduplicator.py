"""Tests for the StreamingDeduplicator class."""

from io import StringIO

import pytest

from uniqseq.deduplicator import StreamingDeduplicator


def test_basic_deduplication():
    """Test basic sequence deduplication."""
    # Create input with duplicate sequences (10 lines each)
    lines = []

    # First unique sequence (lines 1-10)
    for i in range(10):
        lines.append(f"unique-1-line-{i}")

    # Second unique sequence (lines 11-20)
    for i in range(10):
        lines.append(f"unique-2-line-{i}")

    # Duplicate of first sequence (lines 21-30) - should be skipped
    for i in range(10):
        lines.append(f"unique-1-line-{i}")

    # Third unique sequence (lines 31-40)
    for i in range(10):
        lines.append(f"unique-3-line-{i}")

    # Duplicate of second sequence (lines 41-50) - should be skipped
    for i in range(10):
        lines.append(f"unique-2-line-{i}")

    # Process with deduplicator
    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    # Check results
    result_lines = output.getvalue().strip().split("\n")
    stats = dedup.get_stats()

    # Expected: 30 lines (first 3 unique sequences)
    # 20 lines should be skipped (2 duplicate sequences)
    assert len(result_lines) == 30, f"Expected 30 output lines, got {len(result_lines)}"
    assert stats["skipped"] == 20, f"Expected 20 skipped lines, got {stats['skipped']}"


def test_no_duplicates():
    """Test with no duplicate sequences."""
    lines = []

    # All unique sequences
    for seq in range(5):
        for i in range(10):
            lines.append(f"seq-{seq}-line-{i}")

    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    result_lines = output.getvalue().strip().split("\n")
    stats = dedup.get_stats()

    # Expected: all lines preserved
    assert len(result_lines) == len(lines), (
        f"Expected {len(lines)} output lines, got {len(result_lines)}"
    )
    assert stats["skipped"] == 0, f"Expected 0 skipped lines, got {stats['skipped']}"


def test_short_sequences():
    """Test that sequences shorter than window size are not deduplicated."""
    lines = []

    # Two identical 5-line sequences (but window is 10)
    for _ in range(2):
        for i in range(5):
            lines.append(f"short-line-{i}")

    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    result_lines = output.getvalue().strip().split("\n")

    # Expected: all lines preserved (sequences too short)
    assert len(result_lines) == len(lines), (
        f"Expected {len(lines)} output lines, got {len(result_lines)}"
    )


def test_custom_window_size():
    """Test deduplication with custom window size."""
    lines = []

    # Create sequences of 5 lines
    for seq in range(3):
        for i in range(5):
            lines.append(f"seq-{seq % 2}-line-{i}")  # Repeat sequence 0

    dedup = StreamingDeduplicator(window_size=5, max_history=1000)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    result_lines = output.getvalue().strip().split("\n")
    stats = dedup.get_stats()

    # Should detect duplicate 5-line sequences
    assert len(result_lines) < len(lines), "Expected some deduplication"
    assert stats["skipped"] > 0, "Expected some lines to be skipped"


def test_stats():
    """Test statistics reporting."""
    lines = []

    # Create simple duplicate pattern
    for _ in range(2):
        for i in range(10):
            lines.append(f"line-{i}")

    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    stats = dedup.get_stats()

    assert stats["total"] == 20, f"Expected 20 total lines, got {stats['total']}"
    assert stats["emitted"] == 10, f"Expected 10 output lines, got {stats['emitted']}"
    assert stats["skipped"] == 10, f"Expected 10 skipped lines, got {stats['skipped']}"
    assert stats["unique_sequences"] >= 0, "Should track unique sequences"


def test_history_limit():
    """Test that history is limited to max_history."""
    # Create many unique sequences to exceed max_history
    lines = []
    num_sequences = 150  # Exceeds max_history of 100
    window_size = 10

    for seq in range(num_sequences):
        for i in range(window_size):
            lines.append(f"seq-{seq}-line-{i}")

    dedup = StreamingDeduplicator(window_size=window_size, max_history=100)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    stats = dedup.get_stats()

    # History should have been cleared at some point
    assert stats["unique_sequences"] <= 100, (
        f"History exceeded max_history: {stats['unique_sequences']}"
    )


def test_empty_input():
    """Test with empty input."""
    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = StringIO()

    dedup.flush(output)

    result = output.getvalue()
    stats = dedup.get_stats()

    assert result == "", "Expected empty output for empty input"
    assert stats["total"] == 0, "Expected 0 total lines"
    assert stats["emitted"] == 0, "Expected 0 output lines"
    assert stats["skipped"] == 0, "Expected 0 skipped lines"


def test_single_line():
    """Test with single line input."""
    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = StringIO()

    dedup.process_line("single line", output)
    dedup.flush(output)

    result_lines = output.getvalue().strip().split("\n")

    assert len(result_lines) == 1, "Expected 1 output line"
    assert result_lines[0] == "single line", "Line content should be preserved"


def test_multiple_duplicates():
    """Test multiple different duplicate sequences."""
    lines = []

    # Pattern A (10 lines) - appears 3 times
    for _ in range(3):
        for i in range(10):
            lines.append(f"pattern-A-{i}")

    # Pattern B (10 lines) - appears 2 times
    for _ in range(2):
        for i in range(10):
            lines.append(f"pattern-B-{i}")

    # Pattern C (10 lines) - appears once (unique)
    for i in range(10):
        lines.append(f"pattern-C-{i}")

    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    result_lines = output.getvalue().strip().split("\n")
    stats = dedup.get_stats()

    # Expected: 30 lines output (first occurrence of A, B, and C = 10 + 10 + 10)
    # 30 lines skipped (2 duplicates of A = 20 lines, 1 duplicate of B = 10 lines)
    assert len(result_lines) == 30, f"Expected 30 output lines, got {len(result_lines)}"
    assert stats["skipped"] == 30, f"Expected 30 skipped lines, got {stats['skipped']}"


def test_newline_handling():
    """Test that lines with and without newlines are handled correctly."""
    lines = []

    # Create sequence with various line endings
    for i in range(10):
        lines.append(f"line-{i}")  # No newline

    # Duplicate with newlines
    for i in range(10):
        lines.append(f"line-{i}\n")  # With newline

    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        dedup.process_line(line.rstrip("\n"), output)

    dedup.flush(output)

    result = output.getvalue()
    result_lines = [l for l in result.split("\n") if l]

    # All lines should have been deduplicated (same content after stripping)
    assert len(result_lines) == 10, f"Expected 10 output lines, got {len(result_lines)}"


@pytest.mark.skip(reason="Progress callback not yet implemented in new algorithm")
def test_progress_callback():
    """Test that progress callback is called correctly."""
    lines = []
    for i in range(2500):  # More than 2 * 1000 to trigger multiple callbacks
        lines.append(f"line-{i % 100}")

    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = StringIO()

    callback_calls = []

    def progress_callback(line_num, lines_skipped, seq_count):
        callback_calls.append((line_num, lines_skipped, seq_count))

    for line in lines:
        dedup.process_line(line, output, progress_callback=progress_callback)

    # Should have been called at least twice (at 1000 and 2000)
    assert len(callback_calls) >= 2, (
        f"Expected at least 2 callback calls, got {len(callback_calls)}"
    )

    # Verify callback was called with correct line numbers
    assert callback_calls[0][0] == 1000, "First callback should be at line 1000"
    assert callback_calls[1][0] == 2000, "Second callback should be at line 2000"


def test_varying_window_sizes():
    """Test deduplication with different window sizes."""
    # Create pattern that repeats at different sequence lengths
    base_pattern = ["A", "B", "C", "D", "E"]

    for window_size in [2, 3, 5]:
        lines = []

        # Repeat pattern 3 times
        for _ in range(3):
            lines.extend(base_pattern)

        dedup = StreamingDeduplicator(window_size=window_size, max_history=1000)
        output = StringIO()

        for line in lines:
            dedup.process_line(line, output)

        dedup.flush(output)

        result_lines = output.getvalue().strip().split("\n")

        # Should detect duplicates based on window size
        assert len(result_lines) < len(lines), f"Window size {window_size}: Expected deduplication"


def test_interleaved_patterns():
    """Test handling of interleaved duplicate patterns."""
    lines = []

    # Pattern A
    pattern_a = [f"A-{i}" for i in range(10)]
    # Pattern B
    pattern_b = [f"B-{i}" for i in range(10)]

    # Interleave: A, B, A (duplicate), B (duplicate)
    lines.extend(pattern_a)
    lines.extend(pattern_b)
    lines.extend(pattern_a)  # Duplicate
    lines.extend(pattern_b)  # Duplicate

    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    result_lines = output.getvalue().strip().split("\n")
    stats = dedup.get_stats()

    # Expected: 20 lines (first A + first B)
    # Skipped: 20 lines (duplicate A + duplicate B)
    assert len(result_lines) == 20, f"Expected 20 output lines, got {len(result_lines)}"
    assert stats["skipped"] == 20, f"Expected 20 skipped lines, got {stats['skipped']}"


def test_partial_matches():
    """Test that partial sequence matches don't trigger deduplication."""
    lines = []

    # Original sequence
    for i in range(10):
        lines.append(f"line-{i}")

    # Partial match (only 9 lines match)
    for i in range(9):
        lines.append(f"line-{i}")
    lines.append("different-line")

    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    result_lines = output.getvalue().strip().split("\n")

    # Should not deduplicate partial match - all lines should be output
    assert len(result_lines) == 20, (
        f"Expected 20 output lines (no deduplication), got {len(result_lines)}"
    )


def test_long_input():
    """Test performance with longer input."""
    lines = []

    # Create 10 unique sequences of 10 lines each
    for seq in range(10):
        for i in range(10):
            lines.append(f"sequence-{seq}-line-{i}")

    # Repeat all sequences (should all be deduplicated)
    original_length = len(lines)
    lines.extend(lines[:])  # Duplicate everything

    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    result_lines = output.getvalue().strip().split("\n")
    stats = dedup.get_stats()

    # Should have original length output, and skipped the duplicates
    assert len(result_lines) == original_length, (
        f"Expected {original_length} output lines, got {len(result_lines)}"
    )
    assert stats["skipped"] == original_length, f"Expected {original_length} skipped lines"


@pytest.mark.unit
def test_unlimited_history():
    """Test unlimited history mode (max_history=None)."""
    # Create input with duplicate sequences
    lines = []

    # First unique sequence (lines 1-10)
    for i in range(10):
        lines.append(f"seq-1-line-{i}")

    # Second unique sequence (lines 11-20)
    for i in range(10):
        lines.append(f"seq-2-line-{i}")

    # Duplicate of first sequence (lines 21-30) - should be skipped
    for i in range(10):
        lines.append(f"seq-1-line-{i}")

    # Process with unlimited history
    dedup = StreamingDeduplicator(window_size=10, max_history=None)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    # Check results
    result_lines = output.getvalue().strip().split("\n")
    stats = dedup.get_stats()

    # Expected: 20 lines (first 2 unique sequences)
    # 10 lines should be skipped (1 duplicate sequence)
    assert len(result_lines) == 20, f"Expected 20 output lines, got {len(result_lines)}"
    assert stats["skipped"] == 10, f"Expected 10 skipped lines, got {stats['skipped']}"


@pytest.mark.unit
def test_skip_chars():
    """Test skip_chars skips prefix when hashing."""
    # Lines with timestamps
    lines = []

    # Same content with different timestamps (first 20 chars)
    for i in range(10):
        lines.append(f"2024-01-15 10:23:{i:02d} ERROR: Connection failed")

    # Repeat with different timestamps
    for i in range(10, 20):
        lines.append(f"2024-01-15 10:23:{i:02d} ERROR: Connection failed")

    # Process with skip_chars=20 (skip timestamp)
    dedup = StreamingDeduplicator(window_size=10, max_history=1000, skip_chars=20)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    # Check results
    result_lines = output.getvalue().strip().split("\n")
    stats = dedup.get_stats()

    # Expected: 10 lines (first occurrence), 10 skipped (duplicates)
    assert len(result_lines) == 10, f"Expected 10 output lines, got {len(result_lines)}"
    assert stats["skipped"] == 10, f"Expected 10 skipped lines, got {stats['skipped']}"


@pytest.mark.unit
def test_skip_chars_zero():
    """Test skip_chars=0 (default) doesn't skip anything."""
    lines = []

    # Lines with timestamps - each unique without skipping
    for i in range(10):
        lines.append(f"2024-01-15 10:23:{i:02d} ERROR: Connection failed")

    # Process with skip_chars=0 (default)
    dedup = StreamingDeduplicator(window_size=10, max_history=1000, skip_chars=0)
    output = StringIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    # Check results
    result_lines = output.getvalue().strip().split("\n")
    stats = dedup.get_stats()

    # All lines should be unique (different timestamps)
    assert len(result_lines) == 10, f"Expected 10 output lines, got {len(result_lines)}"
    assert stats["skipped"] == 0, f"Expected 0 skipped lines, got {stats['skipped']}"


@pytest.mark.unit
def test_binary_mode_basic():
    """Test binary mode with bytes input."""
    from io import BytesIO

    lines = [f"line{i}".encode() for i in range(10)]

    # Create deduplicator and process bytes
    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = BytesIO()

    # Process lines twice (should deduplicate second occurrence)
    for line in lines * 2:
        dedup.process_line(line, output)

    dedup.flush(output)

    # Check results
    result = output.getvalue()
    result_lines = result.strip().split(b"\n")
    stats = dedup.get_stats()

    # Should only have first 10 lines (second occurrence deduplicated)
    assert len(result_lines) == 10
    assert stats["total"] == 20
    assert stats["emitted"] == 10
    assert stats["skipped"] == 10


@pytest.mark.unit
def test_binary_mode_null_bytes():
    """Test binary mode with null bytes."""
    from io import BytesIO

    # Lines containing null bytes
    lines = [f"line{i}\x00data".encode() for i in range(10)]

    dedup = StreamingDeduplicator(window_size=10, max_history=1000)
    output = BytesIO()

    # Process twice
    for line in lines * 2:
        dedup.process_line(line, output)

    dedup.flush(output)

    result = output.getvalue()
    stats = dedup.get_stats()

    # Should handle null bytes correctly
    assert result.count(b"\x00") == 10  # Only first occurrence
    assert stats["skipped"] == 10


@pytest.mark.unit
def test_binary_mode_with_skip_chars():
    """Test binary mode with skip_chars."""
    from io import BytesIO

    lines = []
    for i in range(10):
        # Add varying prefix, same suffix
        timestamp = f"2024-01-15 10:23:{i:02d} "
        msg = "ERROR: Connection failed"
        lines.append((timestamp + msg).encode("utf-8"))

    # Repeat with different timestamps
    for i in range(10, 20):
        timestamp = f"2024-01-15 10:23:{i:02d} "
        msg = "ERROR: Connection failed"
        lines.append((timestamp + msg).encode("utf-8"))

    # Skip first 20 bytes (timestamp)
    dedup = StreamingDeduplicator(window_size=10, max_history=1000, skip_chars=20)
    output = BytesIO()

    for line in lines:
        dedup.process_line(line, output)

    dedup.flush(output)

    stats = dedup.get_stats()

    # Should deduplicate second sequence (same after skipping timestamp)
    assert stats["total"] == 20
    assert stats["skipped"] == 10


@pytest.mark.unit
def test_hash_line_with_bytes():
    """Test hash_line with bytes input."""
    from uniqseq.deduplicator import hash_line

    # Test with bytes
    line_bytes = b"test line"
    hash1 = hash_line(line_bytes)
    hash2 = hash_line(line_bytes)

    assert hash1 == hash2
    assert len(hash1) == 16  # 8 bytes = 16 hex chars

    # Test with skip_chars
    line_with_prefix = b"PREFIX: test line"
    hash3 = hash_line(line_with_prefix, skip_chars=8)
    assert hash3 == hash1  # Should match after skipping "PREFIX: "


@pytest.mark.unit
def test_hash_line_str_vs_bytes():
    """Test that hash_line produces same result for str and bytes."""
    from uniqseq.deduplicator import hash_line

    text = "test line with unicode: é"
    hash_str = hash_line(text)
    hash_bytes = hash_line(text.encode("utf-8"))

    # Should produce identical hashes
    assert hash_str == hash_bytes


@pytest.mark.unit
def test_parse_hex_delimiter():
    """Test parse_hex_delimiter function."""
    from uniqseq.cli import parse_hex_delimiter

    # Basic hex
    assert parse_hex_delimiter("00") == b"\x00"
    assert parse_hex_delimiter("0a") == b"\n"
    assert parse_hex_delimiter("0d0a") == b"\r\n"

    # With 0x prefix
    assert parse_hex_delimiter("0x00") == b"\x00"
    assert parse_hex_delimiter("0X0a") == b"\n"

    # Multiple bytes
    assert parse_hex_delimiter("010203") == b"\x01\x02\x03"

    # Case insensitive
    assert parse_hex_delimiter("FF") == b"\xff"
    assert parse_hex_delimiter("ff") == b"\xff"
    assert parse_hex_delimiter("0xFF") == b"\xff"


@pytest.mark.unit
def test_parse_hex_delimiter_errors():
    """Test parse_hex_delimiter error cases."""
    import pytest

    from uniqseq.cli import parse_hex_delimiter

    # Empty string
    with pytest.raises(ValueError, match="Empty hex delimiter"):
        parse_hex_delimiter("")

    # Odd length
    with pytest.raises(ValueError, match="even number of characters"):
        parse_hex_delimiter("0")

    with pytest.raises(ValueError, match="even number of characters"):
        parse_hex_delimiter("000")

    # Invalid hex
    with pytest.raises(ValueError, match="Invalid hex delimiter"):
        parse_hex_delimiter("ZZ")

    with pytest.raises(ValueError, match="Invalid hex delimiter"):
        parse_hex_delimiter("GG")
