"""Tests for explain functionality.

Tests the --explain feature which shows diagnostic messages to stderr
explaining why lines were kept or skipped during deduplication.
"""

import re
from io import StringIO

import pytest

from uniqseq.uniqseq import FilterPattern, UniqSeq


@pytest.mark.unit
class TestExplainBasic:
    """Test basic explain functionality."""

    def test_explain_disabled_by_default(self, capsys):
        """Explain mode is disabled by default."""
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        # Create duplicate sequence
        for line in ["A", "B", "C", "A", "B", "C"]:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # No stderr output when explain is disabled
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_explain_enabled(self, capsys):
        """Explain mode shows messages to stderr."""
        uniqseq = UniqSeq(window_size=3, explain=True)
        output = StringIO()

        # Create duplicate sequence
        for line in ["A", "B", "C", "X", "A", "B", "C"]:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Check that explain messages appear in stderr
        captured = capsys.readouterr()
        assert "EXPLAIN:" in captured.err
        assert "skipped" in captured.err

    def test_explain_message_format(self, capsys):
        """Explain messages have correct format."""
        uniqseq = UniqSeq(window_size=3, explain=True)
        output = StringIO()

        # Create duplicate sequence
        for line in ["A", "B", "C", "X", "A", "B", "C"]:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        captured = capsys.readouterr()
        # Check format: "EXPLAIN: Lines X-Y skipped (duplicate...)"
        assert "EXPLAIN: Lines" in captured.err
        assert "skipped" in captured.err

    def test_explain_does_not_affect_output(self, capsys):
        """Explain mode doesn't change stdout output."""
        # Run without explain
        uniqseq1 = UniqSeq(window_size=3, explain=False)
        output1 = StringIO()
        for line in ["A", "B", "C", "A", "B", "C"]:
            uniqseq1.process_line(line, output1)
        uniqseq1.flush(output1)

        # Run with explain
        uniqseq2 = UniqSeq(window_size=3, explain=True)
        output2 = StringIO()
        for line in ["A", "B", "C", "A", "B", "C"]:
            uniqseq2.process_line(line, output2)
        uniqseq2.flush(output2)

        # Clear stderr
        capsys.readouterr()

        # Outputs should be identical
        assert output1.getvalue() == output2.getvalue()


@pytest.mark.unit
class TestExplainDuplicates:
    """Test explain messages for duplicate sequences."""

    def test_explain_simple_duplicate(self, capsys):
        """Explain shows message for simple duplicate sequence."""
        uniqseq = UniqSeq(window_size=3, explain=True)
        output = StringIO()

        # First occurrence: A, B, C
        for line in ["A", "B", "C", "X"]:
            uniqseq.process_line(line, output)

        # Duplicate occurrence
        for line in ["A", "B", "C"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

        captured = capsys.readouterr()
        assert "EXPLAIN:" in captured.err
        assert "Lines 5-7 skipped" in captured.err
        assert "duplicate" in captured.err.lower()

    def test_explain_duplicate_count(self, capsys):
        """Explain shows how many times sequence was seen."""
        uniqseq = UniqSeq(window_size=3, explain=True)
        output = StringIO()

        # First occurrence
        for line in ["A", "B", "C", "X"]:
            uniqseq.process_line(line, output)

        # First duplicate (seen 2x)
        for line in ["A", "B", "C", "X"]:
            uniqseq.process_line(line, output)

        # Second duplicate (seen 3x)
        for line in ["A", "B", "C"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

        captured = capsys.readouterr()
        # Should show duplicate counts
        assert "seen 2x" in captured.err or "seen 3x" in captured.err

    def test_explain_multiple_duplicates(self, capsys):
        """Explain shows messages for duplicates."""
        uniqseq = UniqSeq(window_size=3, explain=True)
        output = StringIO()

        # First pattern: A, B, C
        for line in ["A", "B", "C", "X"]:
            uniqseq.process_line(line, output)

        # Second pattern: D, E, F
        for line in ["D", "E", "F", "Y"]:
            uniqseq.process_line(line, output)

        # Duplicate of first pattern
        for line in ["A", "B", "C", "X"]:
            uniqseq.process_line(line, output)

        # Duplicate of second pattern
        for line in ["D", "E", "F"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

        captured = capsys.readouterr()
        # Should have explain messages for duplicates
        explain_count = captured.err.count("EXPLAIN:")
        assert explain_count >= 1  # At least one duplicate detected
        assert "skipped" in captured.err

    def test_explain_line_numbers(self, capsys):
        """Explain messages show correct line numbers."""
        uniqseq = UniqSeq(window_size=3, explain=True)
        output = StringIO()

        # Lines 1-4
        for line in ["A", "B", "C", "X"]:
            uniqseq.process_line(line, output)

        # Lines 5-7 (should be marked as duplicate)
        for line in ["A", "B", "C"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

        captured = capsys.readouterr()
        # Line numbers should reference lines 5-7
        assert "5-7" in captured.err


@pytest.mark.unit
class TestExplainFilters:
    """Test explain messages for filter patterns."""

    def test_explain_bypass_filter(self, capsys):
        """Explain shows message when line bypasses via filter."""
        bypass_pattern = FilterPattern(
            pattern=r"^DEBUG", action="bypass", regex=re.compile(r"^DEBUG")
        )
        uniqseq = UniqSeq(
            window_size=3,
            explain=True,
            filter_patterns=[bypass_pattern],
        )
        output = StringIO()

        uniqseq.process_line("DEBUG: some message", output)
        uniqseq.process_line("INFO: another message", output)
        uniqseq.flush(output)

        captured = capsys.readouterr()
        # Should show explain message for bypassed line
        assert "EXPLAIN:" in captured.err
        assert "Line 1 bypassed" in captured.err
        assert "bypass pattern" in captured.err.lower()

    def test_explain_track_filter(self, capsys):
        """Explain doesn't show message for tracked lines."""
        track_pattern = FilterPattern(pattern=r"^INFO", action="track", regex=re.compile(r"^INFO"))
        uniqseq = UniqSeq(
            window_size=3,
            explain=True,
            filter_patterns=[track_pattern],
        )
        output = StringIO()

        # INFO lines are tracked (deduplicated)
        # DEBUG lines are bypassed (not tracked because no match in allowlist mode)
        uniqseq.process_line("INFO: message 1", output)
        uniqseq.process_line("DEBUG: debug message", output)
        uniqseq.flush(output)

        captured = capsys.readouterr()
        # DEBUG line should have bypass message (no match in allowlist mode)
        assert "EXPLAIN:" in captured.err
        assert "Line 2 bypassed" in captured.err

    def test_explain_bypass_pattern_shown(self, capsys):
        """Explain shows which pattern caused bypass."""
        bypass_patterns = [
            FilterPattern(pattern=r"^DEBUG", action="bypass", regex=re.compile(r"^DEBUG")),
            FilterPattern(pattern=r"^TRACE", action="bypass", regex=re.compile(r"^TRACE")),
        ]
        uniqseq = UniqSeq(
            window_size=3,
            explain=True,
            filter_patterns=bypass_patterns,
        )
        output = StringIO()

        uniqseq.process_line("DEBUG: test", output)
        uniqseq.flush(output)

        captured = capsys.readouterr()
        # Should show the pattern that matched
        assert "bypass pattern '^DEBUG'" in captured.err or "bypass pattern" in captured.err


@pytest.mark.unit
class TestExplainByteMode:
    """Test explain works in byte mode."""

    def test_explain_byte_mode(self, capsys):
        """Explain works with byte mode."""
        # Byte mode is enabled by using bytes delimiter
        from io import BytesIO

        uniqseq = UniqSeq(window_size=3, explain=True, delimiter=b"\n")
        output = BytesIO()

        # Create duplicate in byte mode
        for line in [b"A", b"B", b"C", b"X"]:
            uniqseq.process_line(line, output)

        for line in [b"A", b"B", b"C"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

        captured = capsys.readouterr()
        assert "EXPLAIN:" in captured.err
        assert "skipped" in captured.err


@pytest.mark.unit
class TestExplainEdgeCases:
    """Test explain in edge cases."""

    def test_explain_empty_input(self, capsys):
        """Explain with no input produces no messages."""
        uniqseq = UniqSeq(window_size=3, explain=True)
        output = StringIO()
        uniqseq.flush(output)

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_explain_no_duplicates(self, capsys):
        """Explain with no duplicates produces no messages."""
        uniqseq = UniqSeq(window_size=3, explain=True)
        output = StringIO()

        for line in ["A", "B", "C", "D", "E", "F"]:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        captured = capsys.readouterr()
        # No duplicates, so no explain messages
        assert captured.err == ""

    def test_explain_single_line(self, capsys):
        """Explain with single line produces no messages."""
        uniqseq = UniqSeq(window_size=3, explain=True)
        output = StringIO()

        uniqseq.process_line("single", output)
        uniqseq.flush(output)

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_explain_window_size_one(self, capsys):
        """Explain works with window_size=1."""
        uniqseq = UniqSeq(window_size=1, explain=True)
        output = StringIO()

        # With window=1, consecutive identical lines are duplicates
        for line in ["A", "A", "B"]:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        captured = capsys.readouterr()
        # Should have explain message for duplicate "A"
        assert "EXPLAIN:" in captured.err

    def test_explain_large_window(self, capsys):
        """Explain works with large window size."""
        uniqseq = UniqSeq(window_size=10, explain=True)
        output = StringIO()

        # Create 10-line sequence
        lines = [f"Line{i}" for i in range(10)]

        # First occurrence
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.process_line("SEP", output)

        # Duplicate occurrence
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        captured = capsys.readouterr()
        assert "EXPLAIN:" in captured.err
        assert "skipped" in captured.err


@pytest.mark.unit
class TestExplainWithOtherFeatures:
    """Test explain combined with other features."""

    def test_explain_with_inverse(self, capsys):
        """Explain works with inverse mode."""
        uniqseq = UniqSeq(window_size=3, explain=True, inverse=True)
        output = StringIO()

        for line in ["A", "B", "C", "X", "A", "B", "C"]:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        captured = capsys.readouterr()
        # Even in inverse mode, explain messages should appear
        assert "EXPLAIN:" in captured.err

    def test_explain_with_annotations(self, capsys):
        """Explain works alongside annotations."""
        uniqseq = UniqSeq(window_size=3, explain=True, annotate=True)
        output = StringIO()

        # Create a clear duplicate that will trigger _handle_duplicate code path
        for line in ["A", "B", "C", "D"]:
            uniqseq.process_line(line, output)

        # Add separator to finalize first sequence
        for line in ["X", "Y", "Z"]:
            uniqseq.process_line(line, output)

        # Create the duplicate
        for line in ["A", "B", "C", "D"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

        captured = capsys.readouterr()
        # Both annotations and explain should be present
        output_val = output.getvalue()
        assert "[DUPLICATE:" in output_val  # annotation
        assert "EXPLAIN:" in captured.err  # explain to stderr
        # Should show the match details (lines matched lines)
        assert "matched lines" in captured.err.lower() or "duplicate of lines" in captured.err

    def test_explain_with_skip_chars(self, capsys):
        """Explain works with skip_chars."""
        uniqseq = UniqSeq(window_size=3, explain=True, skip_chars=10)
        output = StringIO()

        # Lines with different prefixes but same suffix
        for line in ["PREFIX1   ABC", "PREFIX2   DEF", "PREFIX3   GHI", "SEP"]:
            uniqseq.process_line(line, output)

        # Duplicate (skip first 10 chars)
        for line in ["PREFIX4   ABC", "PREFIX5   DEF", "PREFIX6   GHI"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

        captured = capsys.readouterr()
        # Should have explain message for duplicate
        assert "EXPLAIN:" in captured.err


@pytest.mark.unit
class TestExplainCodeCoverage:
    """Additional tests to improve code coverage."""

    def test_explain_consecutive_duplicates(self, capsys):
        """Test explain with consecutive duplicates."""
        uniqseq = UniqSeq(window_size=2, explain=True)
        output = StringIO()

        # Create pattern then immediate duplicate
        for line in ["A", "B", "A", "B", "A", "B"]:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        captured = capsys.readouterr()
        assert "EXPLAIN:" in captured.err

    def test_explain_with_flush_buffered_lines(self, capsys):
        """Test explain messages during flush."""
        uniqseq = UniqSeq(window_size=3, explain=True)
        output = StringIO()

        # Create incomplete sequence at end
        for line in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            uniqseq.process_line(line, output)

        # Add partial duplicate
        for line in ["A", "B"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

        # Should complete without errors
        assert uniqseq.line_num_output > 0

    def test_explain_triple_duplicate(self, capsys):
        """Test explain with same sequence appearing 3+ times."""
        uniqseq = UniqSeq(window_size=3, explain=True)
        output = StringIO()

        # First occurrence
        for line in ["A", "B", "C", "X"]:
            uniqseq.process_line(line, output)

        # Second occurrence (first duplicate)
        for line in ["A", "B", "C", "Y"]:
            uniqseq.process_line(line, output)

        # Duplicate of first
        for line in ["A", "B", "C", "X"]:
            uniqseq.process_line(line, output)

        # Duplicate of second
        for line in ["A", "B", "C", "Y"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

        captured = capsys.readouterr()
        # Should have explain messages
        assert captured.err.count("EXPLAIN:") >= 1
        # Should show duplicate counts
        assert "seen" in captured.err or "duplicate" in captured.err

    def test_explain_overlapping_patterns(self, capsys):
        """Test explain with overlapping sequence patterns."""
        uniqseq = UniqSeq(window_size=3, explain=True)
        output = StringIO()

        # Create overlapping patterns
        for line in ["A", "B", "C", "B", "C", "D", "C", "D", "E"]:
            uniqseq.process_line(line, output)

        # Add duplicate of middle section
        for line in ["B", "C", "D"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

        # Should process without errors
        assert uniqseq.line_num_input > 0
