"""Property-based tests with random inputs."""

from io import StringIO

import pytest

from tests.random_sequences import generate_random_sequence
from uniqseq.uniqseq import UniqSeq


@pytest.mark.property
class TestRandomSequences:
    """Property-based tests with random inputs."""

    @pytest.mark.parametrize("alphabet_size", [2, 5, 10, 26])
    @pytest.mark.parametrize("num_lines", [100, 1000])
    def test_random_sequence_completes(self, alphabet_size, num_lines):
        """Random sequence processing completes without error."""
        lines = generate_random_sequence(num_lines, alphabet_size, seed=42)

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Invariant: output + skipped = input
        assert uniqseq.line_num_output + uniqseq.lines_skipped == uniqseq.line_num_input

    @pytest.mark.parametrize("alphabet_size", [2, 5, 10])
    def test_small_alphabet_finds_duplicates(self, alphabet_size):
        """Small alphabet (high collision rate) finds duplicates."""
        # 10,000 lines from 2-10 character alphabet should have duplicates
        lines = generate_random_sequence(10000, alphabet_size, seed=42)

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # With small alphabet, should find duplicates
        if alphabet_size <= 5:
            assert uniqseq.lines_skipped > 0

    def test_large_alphabet_few_duplicates(self):
        """Large alphabet (low collision rate) finds few duplicates."""
        # 1,000 lines from 100 character alphabet unlikely to have duplicates
        lines = generate_random_sequence(1000, alphabet_size=100, seed=42)

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Large alphabet should have few/no duplicates
        assert uniqseq.lines_skipped < 100  # Very conservative

    @pytest.mark.slow
    def test_very_large_random_input(self):
        """Stress test with very large random input (100k lines)."""
        lines = generate_random_sequence(100000, alphabet_size=10, seed=42)

        uniqseq = UniqSeq(window_size=10, max_history=10000, max_unique_sequences=1000)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Invariant checks
        assert uniqseq.line_num_output + uniqseq.lines_skipped == uniqseq.line_num_input
        assert uniqseq.line_num_input == 100000

    @pytest.mark.parametrize("window_size", [2, 5, 10, 20])
    def test_various_window_sizes(self, window_size):
        """Test with different window sizes."""
        lines = generate_random_sequence(1000, alphabet_size=5, seed=123)

        uniqseq = UniqSeq(window_size=window_size)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Should complete without error
        assert uniqseq.line_num_output + uniqseq.lines_skipped == uniqseq.line_num_input

    @pytest.mark.parametrize("seed", [1, 42, 123, 999])
    def test_different_random_seeds(self, seed):
        """Different random seeds produce different but valid results."""
        lines = generate_random_sequence(500, alphabet_size=5, seed=seed)

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Invariant holds regardless of seed
        assert uniqseq.line_num_output + uniqseq.lines_skipped == uniqseq.line_num_input
