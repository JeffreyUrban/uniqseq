"""Tests for the UniqSeq class."""

import re
from io import StringIO

import pytest

from uniqseq.uniqseq import FilterPattern, UniqSeq


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

    # Process with uniqseq
    uniqseq = UniqSeq(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Check results
    result_lines = output.getvalue().strip().split("\n")
    stats = uniqseq.get_stats()

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

    uniqseq = UniqSeq(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result_lines = output.getvalue().strip().split("\n")
    stats = uniqseq.get_stats()

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

    uniqseq = UniqSeq(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

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

    uniqseq = UniqSeq(window_size=5, max_history=1000)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result_lines = output.getvalue().strip().split("\n")
    stats = uniqseq.get_stats()

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

    uniqseq = UniqSeq(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    stats = uniqseq.get_stats()

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

    uniqseq = UniqSeq(window_size=window_size, max_history=100)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    stats = uniqseq.get_stats()

    # History should have been cleared at some point
    assert stats["unique_sequences"] <= 100, (
        f"History exceeded max_history: {stats['unique_sequences']}"
    )


def test_empty_input():
    """Test with empty input."""
    uniqseq = UniqSeq(window_size=10, max_history=1000)
    output = StringIO()

    uniqseq.flush(output)

    result = output.getvalue()
    stats = uniqseq.get_stats()

    assert result == "", "Expected empty output for empty input"
    assert stats["total"] == 0, "Expected 0 total lines"
    assert stats["emitted"] == 0, "Expected 0 output lines"
    assert stats["skipped"] == 0, "Expected 0 skipped lines"


def test_single_line():
    """Test with single line input."""
    uniqseq = UniqSeq(window_size=10, max_history=1000)
    output = StringIO()

    uniqseq.process_line("single line", output)
    uniqseq.flush(output)

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

    uniqseq = UniqSeq(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result_lines = output.getvalue().strip().split("\n")
    stats = uniqseq.get_stats()

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

    uniqseq = UniqSeq(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line.rstrip("\n"), output)

    uniqseq.flush(output)

    result = output.getvalue()
    result_lines = [l for l in result.split("\n") if l]

    # All lines should have been deduplicated (same content after stripping)
    assert len(result_lines) == 10, f"Expected 10 output lines, got {len(result_lines)}"


def test_progress_callback():
    """Test that progress callback is called correctly."""
    lines = []
    for i in range(2500):  # More than 2 * 1000 to trigger multiple callbacks
        lines.append(f"line-{i % 100}")

    uniqseq = UniqSeq(window_size=10, max_history=1000)
    output = StringIO()

    callback_calls = []

    def progress_callback(line_num, lines_skipped, seq_count):
        callback_calls.append((line_num, lines_skipped, seq_count))

    for line in lines:
        uniqseq.process_line(line, output, progress_callback=progress_callback)

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

        uniqseq = UniqSeq(window_size=window_size, max_history=1000)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

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

    uniqseq = UniqSeq(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result_lines = output.getvalue().strip().split("\n")
    stats = uniqseq.get_stats()

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

    uniqseq = UniqSeq(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

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

    uniqseq = UniqSeq(window_size=10, max_history=1000)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result_lines = output.getvalue().strip().split("\n")
    stats = uniqseq.get_stats()

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
    uniqseq = UniqSeq(window_size=10, max_history=None)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Check results
    result_lines = output.getvalue().strip().split("\n")
    stats = uniqseq.get_stats()

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
    uniqseq = UniqSeq(window_size=10, max_history=1000, skip_chars=20)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Check results
    result_lines = output.getvalue().strip().split("\n")
    stats = uniqseq.get_stats()

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
    uniqseq = UniqSeq(window_size=10, max_history=1000, skip_chars=0)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Check results
    result_lines = output.getvalue().strip().split("\n")
    stats = uniqseq.get_stats()

    # All lines should be unique (different timestamps)
    assert len(result_lines) == 10, f"Expected 10 output lines, got {len(result_lines)}"
    assert stats["skipped"] == 0, f"Expected 0 skipped lines, got {stats['skipped']}"


@pytest.mark.unit
def test_binary_mode_basic():
    """Test binary mode with bytes input."""
    from io import BytesIO

    lines = [f"line{i}".encode() for i in range(10)]

    # Create uniqseq and process bytes
    uniqseq = UniqSeq(window_size=10, max_history=1000, delimiter=b"\n")
    output = BytesIO()

    # Process lines twice (should deduplicate second occurrence)
    for line in lines * 2:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Check results
    result = output.getvalue()
    result_lines = result.strip().split(b"\n")
    stats = uniqseq.get_stats()

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

    uniqseq = UniqSeq(window_size=10, max_history=1000, delimiter=b"\n")
    output = BytesIO()

    # Process twice
    for line in lines * 2:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result = output.getvalue()
    stats = uniqseq.get_stats()

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
    uniqseq = UniqSeq(window_size=10, max_history=1000, skip_chars=20, delimiter=b"\n")
    output = BytesIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    stats = uniqseq.get_stats()

    # Should deduplicate second sequence (same after skipping timestamp)
    assert stats["total"] == 20
    assert stats["skipped"] == 10


@pytest.mark.unit
def test_hash_line_with_bytes():
    """Test hash_line with bytes input."""
    from uniqseq.uniqseq import hash_line

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
    from uniqseq.uniqseq import hash_line

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


@pytest.mark.unit
def test_history_eviction_during_matching():
    """Test that matching handles history eviction correctly (covers uniqseq.py line 458)."""
    # Create a uniqseq with very small history to force eviction
    uniqseq = UniqSeq(window_size=3, max_history=5)
    output = StringIO()

    # Create a pattern that will trigger eviction during matching
    # First, fill history with window hashes
    for i in range(10):
        uniqseq.process_line(f"line{i}", output)

    # Now add a pattern that might match against evicted history
    # This should handle the case where next_window_hash is None
    for i in range(10):
        uniqseq.process_line(f"repeat{i}", output)

    uniqseq.flush(output)

    # Verify we got output (the test is mainly about not crashing)
    assert len(output.getvalue()) > 0


@pytest.mark.unit
def test_max_unique_sequences_limit():
    """Test that unique sequences are evicted when limit is reached (covers uniqseq.py line 537)."""
    # Create uniqseq with very small unique sequence limit
    uniqseq = UniqSeq(window_size=2, max_unique_sequences=3)
    output = StringIO()

    # Create multiple unique sequences to exceed the limit
    # Each sequence is different, so they'll all be stored
    sequences = [
        ["A", "B"],
        ["C", "D"],
        ["E", "F"],
        ["G", "H"],  # This will trigger eviction of oldest
        ["I", "J"],  # This will trigger another eviction
    ]

    for seq in sequences:
        for line in seq:
            uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Verify sequences were tracked and oldest was evicted
    # Should have max_unique_sequences limit enforced
    assert len(uniqseq.sequence_records) <= 3


# ===== Filter Pattern Tests =====


@pytest.mark.unit
def test_filter_bypass_bypasses_dedup():
    """Test that bypass patterns bypass deduplication."""
    # Create filter pattern: bypass lines starting with DEBUG
    patterns = [FilterPattern(pattern="^DEBUG", action="bypass", regex=re.compile("^DEBUG"))]

    # Input with DEBUG lines repeated
    lines = [
        "INFO: Starting",
        "DEBUG: Detail 1",  # bypassed
        "INFO: Processing",
        "DEBUG: Detail 1",  # bypassed (duplicate but should still output)
        "INFO: Complete",
    ]

    uniqseq = UniqSeq(window_size=2, max_history=100, filter_patterns=patterns)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result = output.getvalue()

    # All DEBUG lines should be in output (bypassed, not deduplicated)
    assert result.count("DEBUG: Detail 1") == 2
    # INFO lines should be deduplicated normally
    assert result.count("INFO: Starting") == 1


@pytest.mark.unit
def test_filter_track_includes_for_dedup():
    """Test that track patterns work for grouped content.

    Note: Phase 1 limitation - track patterns work when all lines are tracked.
    Mixed track/non-track scenarios have known issues with windowing that will
    be addressed in future phases.
    """
    # Create filter pattern: track all lines (effectively no filtering)
    patterns = [FilterPattern(pattern=".*", action="track", regex=re.compile(".*"))]

    # Input with duplicate sequences
    lines = [
        "Line A",
        "Line B",
        "Line A",  # duplicate sequence
        "Line B",
        "Line C",
    ]

    uniqseq = UniqSeq(window_size=2, max_history=100, filter_patterns=patterns)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result = output.getvalue()

    # Sequences should be deduplicated normally
    assert result.count("Line A") == 1
    assert result.count("Line B") == 1
    assert result.count("Line C") == 1


@pytest.mark.unit
def test_filter_no_match_defaults_to_dedup():
    """Test that lines not matching any pattern are deduplicated."""
    # Create filter pattern: only bypass DEBUG
    patterns = [FilterPattern(pattern="^DEBUG", action="bypass", regex=re.compile("^DEBUG"))]

    # Input with duplicate INFO lines
    lines = [
        "INFO: Message A",
        "INFO: Message B",
        "DEBUG: Detail",  # bypassed
        "INFO: Message A",  # duplicate, should be skipped
        "INFO: Message B",  # duplicate, should be skipped
    ]

    uniqseq = UniqSeq(window_size=2, max_history=100, filter_patterns=patterns)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result = output.getvalue()

    # INFO lines should be deduplicated (default behavior)
    assert result.count("INFO: Message A") == 1
    assert result.count("INFO: Message B") == 1
    # DEBUG line should pass through
    assert result.count("DEBUG: Detail") == 1


@pytest.mark.unit
def test_filter_sequential_evaluation():
    """Test that patterns are evaluated in order (first match wins)."""
    # Pattern order: bypass DEBUG, then track ERROR
    # Line "DEBUG ERROR" should match DEBUG first (bypassed)
    patterns = [
        FilterPattern(pattern="DEBUG", action="bypass", regex=re.compile("DEBUG")),
        FilterPattern(pattern="ERROR", action="track", regex=re.compile("ERROR")),
    ]

    # Use grouped lines to ensure windowing works correctly
    lines = [
        "DEBUG message",  # matches DEBUG -> bypassed
        "DEBUG ERROR",  # matches DEBUG first -> bypassed
        "DEBUG message",  # matches DEBUG -> bypassed (duplicate but still output)
        "ERROR message",  # matches ERROR -> tracked
        "ERROR timeout",  # matches ERROR -> tracked
        "ERROR message",  # matches ERROR -> tracked (duplicate sequence, skipped)
        "ERROR timeout",
    ]

    uniqseq = UniqSeq(window_size=2, max_history=100, filter_patterns=patterns)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result = output.getvalue()

    # DEBUG lines bypassed (all occurrences output)
    assert result.count("DEBUG message") == 2
    assert result.count("DEBUG ERROR") == 1
    # ERROR tracked and deduplicated (first sequence kept, duplicate skipped)
    assert result.count("ERROR message") == 1
    assert result.count("ERROR timeout") == 1


@pytest.mark.unit
def test_filter_interleaved_ordering():
    """Test that ordering is preserved with interleaved filtered/unfiltered lines."""
    # Track ERROR lines, let INFO pass through
    patterns = [FilterPattern(pattern="^ERROR", action="track", regex=re.compile("^ERROR"))]

    lines = [
        "ERROR: Failed",  # 1 (uniqseq)
        "INFO: Starting",  # 2 (pass through)
        "ERROR: Timeout",  # 3 (uniqseq)
        "INFO: Processing",  # 4 (pass through)
        "ERROR: Failed",  # 5 (uniqseq - duplicate)
        "ERROR: Timeout",  # 6 (uniqseq - duplicate)
        "INFO: Complete",  # 7 (pass through)
    ]

    uniqseq = UniqSeq(window_size=2, max_history=100, filter_patterns=patterns)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result = output.getvalue()
    result_lines = [line for line in result.strip().split("\n") if line]

    # Verify correct ordering
    assert result_lines[0] == "ERROR: Failed"
    assert result_lines[1] == "INFO: Starting"
    assert result_lines[2] == "ERROR: Timeout"
    assert result_lines[3] == "INFO: Processing"
    assert result_lines[4] == "INFO: Complete"
    # Total 5 lines (duplicate ERROR sequence skipped)
    assert len(result_lines) == 5


@pytest.mark.unit
def test_filter_empty_patterns_list():
    """Test that empty patterns list behaves like no filtering."""
    uniqseq = UniqSeq(window_size=2, max_history=100, filter_patterns=[])
    output = StringIO()

    lines = [
        "Line A",
        "Line B",
        "Line A",  # duplicate
        "Line B",  # duplicate
    ]

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result = output.getvalue()
    result_lines = [line for line in result.strip().split("\n") if line]

    # Should deduplicate normally
    assert len(result_lines) == 2
    assert result.count("Line A") == 1
    assert result.count("Line B") == 1


@pytest.mark.unit
def test_inverse_mode_keeps_duplicates():
    """Test that inverse mode outputs only duplicate sequences."""
    # Input with a duplicate sequence
    lines = ["A", "B", "C", "A", "B", "C", "D"]

    # Test inverse mode
    output = StringIO()
    uniqseq = UniqSeq(window_size=3, inverse=True)

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result = output.getvalue()
    result_lines = result.strip().split("\n") if result.strip() else []

    # Should only output the duplicate occurrence (lines 4-6: A, B, C)
    assert len(result_lines) == 3
    assert result_lines == ["A", "B", "C"]

    # Stats check
    assert uniqseq.line_num_output == 3  # 3 duplicate lines emitted
    assert uniqseq.lines_skipped == 4  # 4 unique lines skipped (first A,B,C + D)


@pytest.mark.unit
def test_inverse_mode_removes_unique():
    """Test that inverse mode skips unique sequences."""
    # Input with all unique lines
    lines = ["A", "B", "C", "D", "E"]

    output = StringIO()
    uniqseq = UniqSeq(window_size=3, inverse=True)

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result = output.getvalue()

    # Should output nothing (no duplicates)
    assert result == ""
    assert uniqseq.line_num_output == 0
    assert uniqseq.lines_skipped == 5  # All lines skipped


@pytest.mark.unit
def test_inverse_mode_with_filtering():
    """Test that inverse mode works with filtering patterns."""
    # Create filter pattern: track ERROR
    patterns = [FilterPattern(pattern="^ERROR", action="track", regex=re.compile("^ERROR"))]

    lines = [
        "ERROR: Failed",
        "ERROR: Timeout",
        "INFO: Processing",
        "ERROR: Failed",  # Duplicate sequence starts
        "ERROR: Timeout",  # Duplicate sequence
        "DEBUG: Detail",
    ]

    output = StringIO()
    uniqseq = UniqSeq(window_size=2, filter_patterns=patterns, inverse=True)

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    result = output.getvalue()
    result_lines = result.strip().split("\n") if result.strip() else []

    # Inverse mode with track pattern:
    # - ERROR lines are tracked and deduplicated
    # - In inverse mode, duplicate ERROR sequence is output
    # - INFO and DEBUG pass through (not tracked)
    assert "ERROR: Failed" in result_lines  # Duplicate sequence emitted
    assert "ERROR: Timeout" in result_lines  # Duplicate sequence emitted
    assert "INFO: Processing" in result_lines  # Passed through (filtered)
    assert "DEBUG: Detail" in result_lines  # Passed through (filtered)


@pytest.mark.unit
def test_annotate_basic():
    """Test that annotations are added when duplicates are skipped."""
    # Create input with clear duplicate (using 10-line sequences)
    lines = []
    for i in range(10):
        lines.append(f"line-{i}")
    for i in range(5):
        lines.append(f"other-{i}")
    for i in range(10):  # Duplicate sequence
        lines.append(f"line-{i}")

    output = StringIO()
    uniqseq = UniqSeq(window_size=10, annotate=True)

    for line in lines:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)

    result = output.getvalue()

    # Should contain an annotation marker
    assert "[DUPLICATE:" in result
    assert "matched lines" in result
    assert "sequence seen" in result

    # Check that the annotation contains line numbers
    # The duplicate lines are 16-25, matching original lines 1-10
    assert "16-25" in result or "Lines 16-25" in result


@pytest.mark.unit
def test_annotate_disabled_by_default():
    """Test that annotations are not added when annotate=False."""
    lines = []
    for i in range(10):
        lines.append(f"line-{i}")
    for i in range(10):  # Duplicate
        lines.append(f"line-{i}")

    output = StringIO()
    uniqseq = UniqSeq(window_size=10, annotate=False)

    for line in lines:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)

    result = output.getvalue()

    # Should NOT contain annotation markers
    assert "[DUPLICATE:" not in result


@pytest.mark.unit
def test_annotate_not_in_inverse_mode():
    """Test that annotations are not added in inverse mode."""
    lines = []
    for i in range(10):
        lines.append(f"line-{i}")
    for i in range(10):  # Duplicate
        lines.append(f"line-{i}")

    output = StringIO()
    uniqseq = UniqSeq(window_size=10, annotate=True, inverse=True)

    for line in lines:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)

    result = output.getvalue()

    # In inverse mode, duplicates are emitted, not skipped, so no annotations
    assert "[DUPLICATE:" not in result


@pytest.mark.unit
def test_custom_annotation_format():
    """Test custom annotation format with template variables."""
    lines = []
    for i in range(10):
        lines.append(f"line-{i}")
    for i in range(5):
        lines.append(f"other-{i}")
    for i in range(10):  # Duplicate
        lines.append(f"line-{i}")

    output = StringIO()
    custom_format = "SKIP|{start}|{end}|{count}"
    uniqseq = UniqSeq(window_size=10, annotate=True, annotation_format=custom_format)

    for line in lines:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)

    result = output.getvalue()

    # Should contain custom format
    assert "SKIP|" in result
    assert "|2" in result  # count=2
    # Should NOT contain default format
    assert "[DUPLICATE:" not in result


@pytest.mark.unit
def test_annotation_format_all_variables():
    """Test annotation format with all available variables."""
    lines = []
    for i in range(10):
        lines.append(f"line-{i}")
    for i in range(10):  # Duplicate
        lines.append(f"line-{i}")

    output = StringIO()
    custom_format = (
        "Lines {start}-{end} match {match_start}-{match_end} (seen {count}x, window={window_size})"
    )
    uniqseq = UniqSeq(window_size=10, annotate=True, annotation_format=custom_format)

    for line in lines:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)

    result = output.getvalue()

    # Check all variables are substituted
    assert "Lines 11-20" in result  # start-end
    # Note: match_start/match_end use output line numbers, not input line numbers
    # in the NewSequenceCandidate path at EOF
    assert "match 9-18" in result or "match 1-10" in result  # match_start-match_end
    assert "seen 2x" in result  # count
    assert "window=10" in result  # window_size


@pytest.mark.unit
def test_annotation_format_minimal():
    """Test minimal annotation format."""
    lines = []
    for i in range(10):
        lines.append(f"line-{i}")
    for i in range(10):  # Duplicate
        lines.append(f"line-{i}")

    output = StringIO()
    minimal_format = "... skipped {count}x ..."
    uniqseq = UniqSeq(window_size=10, annotate=True, annotation_format=minimal_format)

    for line in lines:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)

    result = output.getvalue()

    assert "... skipped 2x ..." in result


@pytest.mark.unit
def test_preloaded_sequence_saving_on_first_observation():
    """Test that preloaded sequences are saved when first observed."""
    # Create a preloaded sequence as a string with delimiters
    # (matching the format from library.load_sequences_from_directory)
    lines = [f"line-{i}" for i in range(10)]
    sequence_str = "\n".join(lines)  # String with delimiters, no trailing delimiter

    preloaded = {sequence_str}  # Set of sequence content

    # Track saved sequences (mimic CLI behavior with hash-based deduplication)
    from uniqseq.library import compute_sequence_hash

    saved_sequences = {}

    def save_callback(file_content: str):
        seq_hash = compute_sequence_hash(file_content)
        if seq_hash in saved_sequences:
            return  # Already saved
        saved_sequences[seq_hash] = file_content

    output = StringIO()
    uniqseq = UniqSeq(
        window_size=10,
        preloaded_sequences=preloaded,
        save_sequence_callback=save_callback,
    )

    # Process the sequence (first observation of preloaded sequence)
    for line in lines:
        uniqseq.process_line(line, output)

    # Add some other lines
    for i in range(5):
        uniqseq.process_line(f"other-{i}", output)

    # Process the sequence again (second observation)
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Verify the preloaded sequence was saved on first observation
    # Note: The hash in saved_sequences will be the content hash
    assert len(saved_sequences) == 1
    saved_hash = list(saved_sequences.keys())[0]
    assert saved_sequences[saved_hash] == sequence_str


@pytest.mark.unit
def test_preloaded_sequence_extended_versions_saved():
    """Test that preloaded sequences and their extended versions are saved (supersets are new sequences)."""
    # Create a preloaded sequence as a string with delimiters
    lines = [f"line-{i}" for i in range(10)]
    sequence_str = "\n".join(lines)

    preloaded = {sequence_str}

    # Track save callback invocations (mimic CLI behavior with hash-based deduplication)
    from uniqseq.library import compute_sequence_hash

    save_count = 0
    saved_hashes = set()

    def save_callback(file_content: str):
        nonlocal save_count
        seq_hash = compute_sequence_hash(file_content)
        if seq_hash in saved_hashes:
            return  # Already saved
        saved_hashes.add(seq_hash)
        save_count += 1

    output = StringIO()
    uniqseq = UniqSeq(
        window_size=10,
        preloaded_sequences=preloaded,
        save_sequence_callback=save_callback,
    )

    # Process the sequence three times
    for _ in range(3):
        for line in lines:
            uniqseq.process_line(line, output)
        for i in range(3):
            uniqseq.process_line(f"sep-{i}", output)

    uniqseq.flush(output)

    # Should be saved twice: once for the original 10-line preloaded sequence,
    # and once for the extended sequence (superset is a new sequence)
    assert save_count == 2


@pytest.mark.unit
def test_annotation_format_invalid_variable():
    """Test annotation format with invalid template variable raises error."""
    lines = []
    for i in range(10):
        lines.append(f"line-{i}")
    for i in range(10):
        lines.append(f"line-{i}")  # Duplicate

    output = StringIO()
    # Use invalid variable name
    bad_format = "Lines {start}-{end} with {invalid_var}"
    uniqseq = UniqSeq(window_size=10, annotate=True, annotation_format=bad_format)

    # Should raise KeyError when trying to format annotation
    with pytest.raises(KeyError):
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)
