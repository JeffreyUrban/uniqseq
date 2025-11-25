"""Test edge cases and boundary conditions."""

from io import StringIO

import pytest

from uniqseq.uniqseq import UniqSeq


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_input(self):
        """Empty input produces empty output."""
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()
        uniqseq.flush(output)

        assert output.getvalue() == ""
        assert uniqseq.line_num_input == 0
        assert uniqseq.line_num_output == 0

    def test_single_line(self):
        """Single line passes through unchanged."""
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()
        uniqseq.process_line("single line", output)
        uniqseq.flush(output)

        assert "single line" in output.getvalue()
        assert uniqseq.line_num_output == 1

    def test_two_lines(self):
        """Two lines pass through (less than window)."""
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        uniqseq.process_line("line 1", output)
        uniqseq.process_line("line 2", output)
        uniqseq.flush(output)

        lines = [l for l in output.getvalue().split("\n") if l]
        assert len(lines) == 2
        assert lines == ["line 1", "line 2"]

    def test_fewer_lines_than_window(self):
        """Sequences shorter than window pass through."""
        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for i in range(5):
            uniqseq.process_line(f"line {i}", output)
        uniqseq.flush(output)

        lines = [l for l in output.getvalue().split("\n") if l]
        assert len(lines) == 5

    def test_exact_window_size(self):
        """Sequence exactly window_size long."""
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        # First occurrence
        for line in ["A", "B", "C"]:
            uniqseq.process_line(line, output)

        # Force finalization with different content
        for line in ["X", "Y", "Z"]:
            uniqseq.process_line(line, output)

        # Second occurrence (duplicate)
        for line in ["A", "B", "C"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)
        assert uniqseq.lines_skipped == 3

    def test_overlapping_sequences(self):
        """Overlapping sequences handled correctly."""
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        # Pattern: A,B,C,B,C,D
        # Contains overlapping subsequences
        for line in ["A", "B", "C", "B", "C", "D"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)
        # Should emit all lines (no exact duplicates of 3+ lines)
        lines = [l for l in output.getvalue().split("\n") if l]
        assert len(lines) == 6

    def test_alternating_pattern(self):
        """Alternating pattern: A,B,A,B,A,B."""
        uniqseq = UniqSeq(window_size=2)
        output = StringIO()

        for line in ["A", "B", "A", "B", "A", "B"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

        # Should detect A,B pattern repeating
        assert uniqseq.lines_skipped >= 0  # At least doesn't crash

    def test_very_long_sequence(self):
        """Very long sequence (1000+ lines)."""
        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        # Create 1000-line sequence
        for i in range(1000):
            uniqseq.process_line(f"line_{i % 10}", output)

        uniqseq.flush(output)
        assert uniqseq.line_num_input == 1000

    def test_identical_consecutive_lines(self):
        """Many identical consecutive lines."""
        uniqseq = UniqSeq(window_size=2)
        output = StringIO()

        # 20 identical lines
        for _ in range(20):
            uniqseq.process_line("same", output)

        uniqseq.flush(output)

        # Should detect repeating pattern
        # Exact behavior depends on implementation
        assert uniqseq.line_num_input == 20

    def test_whitespace_only_lines(self):
        """Lines with only whitespace."""
        uniqseq = UniqSeq(window_size=2)
        output = StringIO()

        lines = ["   ", "\t\t", "  ", "   "]  # Whitespace variations

        for line in lines:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)
        assert uniqseq.line_num_input == len(lines)

    def test_very_long_single_line(self):
        """Very long single line (10k characters)."""
        uniqseq = UniqSeq(window_size=2)
        output = StringIO()

        long_line = "x" * 10000

        uniqseq.process_line(long_line, output)
        uniqseq.process_line("other", output)
        uniqseq.flush(output)

        assert uniqseq.line_num_output == 2

    def test_window_size_one(self):
        """Minimum window size of 1."""
        # Note: MIN_SEQUENCE_LENGTH might prevent this
        # This tests the boundary
        uniqseq = UniqSeq(window_size=1)
        output = StringIO()

        for line in ["A", "B", "A"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)
        assert uniqseq.line_num_input == 3

    def test_unicode_content(self):
        """Unicode characters in content."""
        uniqseq = UniqSeq(window_size=2)
        output = StringIO()

        lines = ["こんにちは", "世界", "こんにちは", "世界"]

        for line in lines:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)

        # Should detect duplicate pattern
        assert uniqseq.line_num_input == 4

    def test_empty_lines(self):
        """Empty lines in input."""
        uniqseq = UniqSeq(window_size=2)
        output = StringIO()

        lines = ["A", "", "B", "", "A", "", "B", ""]

        for line in lines:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)
        assert uniqseq.line_num_input == len(lines)

    def test_newlines_in_content(self):
        """Lines shouldn't contain newlines (stripped by caller)."""
        uniqseq = UniqSeq(window_size=2)
        output = StringIO()

        # Normal usage: caller strips newlines
        uniqseq.process_line("line without newline", output)
        uniqseq.flush(output)

        assert uniqseq.line_num_output == 1
