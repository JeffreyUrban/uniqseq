"""Compare algorithm output against reference implementation."""

from io import StringIO

import pytest

from tests.oracle import find_duplicates_naive
from tests.random_sequences import generate_random_sequence
from uniqseq.uniqseq import UniqSeq


@pytest.mark.property
class TestAgainstOracle:
    """Compare algorithm output against reference implementation."""

    @pytest.mark.parametrize("alphabet_size", [2, 5, 10])
    @pytest.mark.parametrize("num_lines", [50, 100, 200])
    def test_random_matches_oracle(self, alphabet_size, num_lines):
        """Random input matches naive implementation."""
        lines = generate_random_sequence(num_lines, alphabet_size, seed=42)

        # Run our algorithm
        uniqseq = UniqSeq(window_size=10)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Run oracle
        oracle_output, oracle_skipped = find_duplicates_naive(lines, window_size=10)

        # Compare outputs
        assert output_lines == oracle_output
        assert uniqseq.lines_skipped == oracle_skipped

    @pytest.mark.parametrize("window_size", [5, 10])
    def test_various_window_sizes_match_oracle(self, window_size):
        """Different window sizes match oracle (excluding window_size=2 edge case)."""
        lines = generate_random_sequence(100, alphabet_size=5, seed=123)

        # Run our algorithm
        uniqseq = UniqSeq(window_size=window_size)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Run oracle
        oracle_output, oracle_skipped = find_duplicates_naive(lines, window_size=window_size)

        # Compare
        assert output_lines == oracle_output
        assert uniqseq.lines_skipped == oracle_skipped

    def test_known_pattern_matches_oracle(self):
        """Known pattern with duplicates matches oracle."""
        lines = [
            "A",
            "B",
            "C",  # First occurrence
            "D",
            "E",
            "A",
            "B",
            "C",  # Duplicate sequence
            "F",
            "G",
        ]

        # Run our algorithm
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Run oracle
        oracle_output, oracle_skipped = find_duplicates_naive(lines, window_size=3)

        # Compare
        assert output_lines == oracle_output
        assert uniqseq.lines_skipped == oracle_skipped

    def test_overlapping_patterns_match_oracle(self):
        """Overlapping patterns match oracle."""
        lines = [
            "A",
            "B",
            "C",
            "D",  # First occurrence
            "B",
            "C",
            "D",
            "E",  # Overlapping, different sequence
            "A",
            "B",
            "C",
            "D",  # Duplicate of first
        ]

        # Run our algorithm
        uniqseq = UniqSeq(window_size=4)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Run oracle
        oracle_output, oracle_skipped = find_duplicates_naive(lines, window_size=4)

        # Compare
        assert output_lines == oracle_output
        assert uniqseq.lines_skipped == oracle_skipped

    def test_no_duplicates_matches_oracle(self):
        """Input with no duplicates matches oracle."""
        lines = [str(i) for i in range(100)]  # All unique

        # Run our algorithm
        uniqseq = UniqSeq(window_size=10)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Run oracle
        oracle_output, oracle_skipped = find_duplicates_naive(lines, window_size=10)

        # Compare
        assert output_lines == oracle_output
        assert uniqseq.lines_skipped == oracle_skipped
        assert uniqseq.lines_skipped == 0  # No duplicates

    def test_all_duplicates_matches_oracle(self):
        """Input that's entirely duplicates matches oracle."""
        # Same 5-line sequence repeated 10 times
        base_sequence = ["A", "B", "C", "D", "E"]
        lines = base_sequence * 10

        # Run our algorithm
        uniqseq = UniqSeq(window_size=5)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Run oracle
        oracle_output, oracle_skipped = find_duplicates_naive(lines, window_size=5)

        # Compare
        assert output_lines == oracle_output
        assert uniqseq.lines_skipped == oracle_skipped

    @pytest.mark.slow
    def test_large_random_matches_oracle(self):
        """Large random input matches oracle (slow test)."""
        lines = generate_random_sequence(1000, alphabet_size=5, seed=999)

        # Run our algorithm
        uniqseq = UniqSeq(window_size=10)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Run oracle
        oracle_output, oracle_skipped = find_duplicates_naive(lines, window_size=10)

        # Compare
        assert output_lines == oracle_output
        assert uniqseq.lines_skipped == oracle_skipped

    def test_alternating_pattern_matches_oracle(self):
        """Alternating pattern matches oracle."""
        lines = ["A", "B"] * 20  # A, B, A, B, A, B, ...

        # Run our algorithm
        uniqseq = UniqSeq(window_size=2)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Run oracle
        oracle_output, oracle_skipped = find_duplicates_naive(lines, window_size=2)

        # Compare
        assert output_lines == oracle_output
        assert uniqseq.lines_skipped == oracle_skipped

    def test_partial_match_then_diverge_matches_oracle(self):
        """Partial match that diverges matches oracle."""
        lines = [
            "A",
            "B",
            "C",
            "D",
            "E",  # First sequence
            "A",
            "B",
            "C",
            "X",
            "Y",  # Partial match, then diverges
        ]

        # Run our algorithm
        uniqseq = UniqSeq(window_size=5)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Run oracle
        oracle_output, oracle_skipped = find_duplicates_naive(lines, window_size=5)

        # Compare
        assert output_lines == oracle_output
        assert uniqseq.lines_skipped == oracle_skipped
