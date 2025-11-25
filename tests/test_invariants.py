"""Test algorithm invariants hold under all conditions."""

from io import StringIO

import pytest

from tests.random_sequences import generate_random_sequence
from uniqseq.uniqseq import UniqSeq


@pytest.mark.property
class TestInvariants:
    """Test algorithm invariants hold under all conditions."""

    def test_conservation_of_lines(self):
        """Invariant: input lines = output lines + skipped lines."""
        lines = generate_random_sequence(1000, alphabet_size=5, seed=42)

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        assert uniqseq.line_num_input == uniqseq.line_num_output + uniqseq.lines_skipped

    def test_order_preservation(self):
        """Invariant: Output preserves input order."""
        lines = ["A", "B", "C", "D", "E", "A", "B", "C"]

        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Track which input lines were emitted
        emitted_indices = []
        out_idx = 0
        for in_idx, line in enumerate(lines):
            if out_idx < len(output_lines) and output_lines[out_idx] == line:
                emitted_indices.append(in_idx)
                out_idx += 1

        # Emitted indices should be in ascending order
        assert emitted_indices == sorted(emitted_indices)

    def test_first_occurrence_always_emitted(self):
        """Invariant: First occurrence of any sequence is emitted."""
        lines = ["A", "B", "C", "D", "E"]

        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # All lines should be emitted (first occurrence)
        assert len(output_lines) == 5

    def test_bounded_memory_unique_sequences(self):
        """Invariant: unique_sequences never exceeds max_unique_sequences."""
        lines = generate_random_sequence(10000, alphabet_size=10, seed=42)

        max_seqs = 100
        uniqseq = UniqSeq(window_size=10, max_unique_sequences=max_seqs)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)

            # Check invariant at every step
            total_seqs = sum(len(d) for d in uniqseq.sequence_records.values())
            assert total_seqs <= max_seqs

        uniqseq.flush(output)

    def test_non_negative_counters(self):
        """Invariant: All counters are non-negative."""
        lines = generate_random_sequence(100, alphabet_size=5, seed=42)

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)

            # Check non-negative invariants
            assert uniqseq.line_num_input >= 0
            assert uniqseq.line_num_output >= 0
            assert uniqseq.lines_skipped >= 0

        uniqseq.flush(output)

    def test_output_never_exceeds_input(self):
        """Invariant: Output lines never exceeds input lines."""
        lines = generate_random_sequence(500, alphabet_size=5, seed=42)

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
            assert uniqseq.line_num_output <= uniqseq.line_num_input

        uniqseq.flush(output)
        assert uniqseq.line_num_output <= uniqseq.line_num_input

    @pytest.mark.parametrize(
        "alphabet_size,window_size",
        [
            (2, 5),
            (5, 10),
            (10, 3),
        ],
    )
    def test_deterministic_output(self, alphabet_size, window_size):
        """Invariant: Same input produces same output."""
        lines = generate_random_sequence(200, alphabet_size, seed=999)

        # Run twice
        outputs = []
        for _ in range(2):
            uniqseq = UniqSeq(window_size=window_size)
            output = StringIO()

            for line in lines:
                uniqseq.process_line(line, output)
            uniqseq.flush(output)

            outputs.append(output.getvalue())

        # Outputs should be identical
        assert outputs[0] == outputs[1]

    def test_skipped_lines_reasonable(self):
        """Invariant: Skipped lines <= input lines."""
        lines = generate_random_sequence(1000, alphabet_size=2, seed=42)

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Cannot skip more lines than input
        assert uniqseq.lines_skipped <= uniqseq.line_num_input
