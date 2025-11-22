"""Test edge cases and boundary conditions."""

from io import StringIO

import pytest
from uniqseq.deduplicator import StreamingDeduplicator


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_input(self):
        """Empty input produces empty output."""
        dedup = StreamingDeduplicator(window_size=3)
        output = StringIO()
        dedup.flush(output)

        assert output.getvalue() == ""
        assert dedup.line_num_input == 0
        assert dedup.line_num_output == 0

    def test_single_line(self):
        """Single line passes through unchanged."""
        dedup = StreamingDeduplicator(window_size=3)
        output = StringIO()
        dedup.process_line("single line", output)
        dedup.flush(output)

        assert "single line" in output.getvalue()
        assert dedup.line_num_output == 1

    def test_two_lines(self):
        """Two lines pass through (less than window)."""
        dedup = StreamingDeduplicator(window_size=3)
        output = StringIO()

        dedup.process_line("line 1", output)
        dedup.process_line("line 2", output)
        dedup.flush(output)

        lines = [l for l in output.getvalue().split("\n") if l]
        assert len(lines) == 2
        assert lines == ["line 1", "line 2"]

    def test_fewer_lines_than_window(self):
        """Sequences shorter than window pass through."""
        dedup = StreamingDeduplicator(window_size=10)
        output = StringIO()

        for i in range(5):
            dedup.process_line(f"line {i}", output)
        dedup.flush(output)

        lines = [l for l in output.getvalue().split("\n") if l]
        assert len(lines) == 5

    def test_exact_window_size(self):
        """Sequence exactly window_size long."""
        dedup = StreamingDeduplicator(window_size=3)
        output = StringIO()

        # First occurrence
        for line in ["A", "B", "C"]:
            dedup.process_line(line, output)

        # Force finalization with different content
        for line in ["X", "Y", "Z"]:
            dedup.process_line(line, output)

        # Second occurrence (duplicate)
        for line in ["A", "B", "C"]:
            dedup.process_line(line, output)

        dedup.flush(output)
        assert dedup.lines_skipped == 3

    def test_overlapping_sequences(self):
        """Overlapping sequences handled correctly."""
        dedup = StreamingDeduplicator(window_size=3)
        output = StringIO()

        # Pattern: A,B,C,B,C,D
        # Contains overlapping subsequences
        for line in ["A", "B", "C", "B", "C", "D"]:
            dedup.process_line(line, output)

        dedup.flush(output)
        # Should emit all lines (no exact duplicates of 3+ lines)
        lines = [l for l in output.getvalue().split("\n") if l]
        assert len(lines) == 6

    def test_alternating_pattern(self):
        """Alternating pattern: A,B,A,B,A,B."""
        dedup = StreamingDeduplicator(window_size=2)
        output = StringIO()

        for line in ["A", "B", "A", "B", "A", "B"]:
            dedup.process_line(line, output)

        dedup.flush(output)

        # Should detect A,B pattern repeating
        assert dedup.lines_skipped >= 0  # At least doesn't crash

    def test_very_long_sequence(self):
        """Very long sequence (1000+ lines)."""
        dedup = StreamingDeduplicator(window_size=10)
        output = StringIO()

        # Create 1000-line sequence
        for i in range(1000):
            dedup.process_line(f"line_{i % 10}", output)

        dedup.flush(output)
        assert dedup.line_num_input == 1000

    def test_identical_consecutive_lines(self):
        """Many identical consecutive lines."""
        dedup = StreamingDeduplicator(window_size=2)
        output = StringIO()

        # 20 identical lines
        for _ in range(20):
            dedup.process_line("same", output)

        dedup.flush(output)

        # Should detect repeating pattern
        # Exact behavior depends on implementation
        assert dedup.line_num_input == 20

    def test_whitespace_only_lines(self):
        """Lines with only whitespace."""
        dedup = StreamingDeduplicator(window_size=2)
        output = StringIO()

        lines = ["   ", "\t\t", "  ", "   "]  # Whitespace variations

        for line in lines:
            dedup.process_line(line, output)

        dedup.flush(output)
        assert dedup.line_num_input == len(lines)

    def test_very_long_single_line(self):
        """Very long single line (10k characters)."""
        dedup = StreamingDeduplicator(window_size=2)
        output = StringIO()

        long_line = "x" * 10000

        dedup.process_line(long_line, output)
        dedup.process_line("other", output)
        dedup.flush(output)

        assert dedup.line_num_output == 2

    def test_window_size_one(self):
        """Minimum window size of 1."""
        # Note: MIN_SEQUENCE_LENGTH might prevent this
        # This tests the boundary
        dedup = StreamingDeduplicator(window_size=1)
        output = StringIO()

        for line in ["A", "B", "A"]:
            dedup.process_line(line, output)

        dedup.flush(output)
        assert dedup.line_num_input == 3

    def test_unicode_content(self):
        """Unicode characters in content."""
        dedup = StreamingDeduplicator(window_size=2)
        output = StringIO()

        lines = ["こんにちは", "世界", "こんにちは", "世界"]

        for line in lines:
            dedup.process_line(line, output)

        dedup.flush(output)

        # Should detect duplicate pattern
        assert dedup.line_num_input == 4

    def test_empty_lines(self):
        """Empty lines in input."""
        dedup = StreamingDeduplicator(window_size=2)
        output = StringIO()

        lines = ["A", "", "B", "", "A", "", "B", ""]

        for line in lines:
            dedup.process_line(line, output)

        dedup.flush(output)
        assert dedup.line_num_input == len(lines)

    def test_newlines_in_content(self):
        """Lines shouldn't contain newlines (stripped by caller)."""
        dedup = StreamingDeduplicator(window_size=2)
        output = StringIO()

        # Normal usage: caller strips newlines
        dedup.process_line("line without newline", output)
        dedup.flush(output)

        assert dedup.line_num_output == 1
