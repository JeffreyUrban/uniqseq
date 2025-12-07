"""Unit tests for preloading module."""

from collections import defaultdict

import pytest

from uniqseq.preloading import (
    deduplicate_nested_sequences,
    index_sequence_windows,
    initialize_preloaded_sequences,
    is_nested_in,
)
from uniqseq.recording import PRELOADED_SEQUENCE_LINE, RecordedSequence, SequenceRegistry


@pytest.mark.unit
class TestIsNestedIn:
    """Test the is_nested_in helper function."""

    def test_exact_match(self):
        """Test needle exactly matches haystack."""
        needle = ("a", "b", "c")
        haystack = ("a", "b", "c")
        assert is_nested_in(needle, haystack) is True

    def test_nested_at_beginning(self):
        """Test needle appears at beginning of haystack."""
        needle = ("a", "b")
        haystack = ("a", "b", "c", "d")
        assert is_nested_in(needle, haystack) is True

    def test_nested_at_end(self):
        """Test needle appears at end of haystack."""
        needle = ("c", "d")
        haystack = ("a", "b", "c", "d")
        assert is_nested_in(needle, haystack) is True

    def test_nested_in_middle(self):
        """Test needle appears in middle of haystack."""
        needle = ("b", "c")
        haystack = ("a", "b", "c", "d")
        assert is_nested_in(needle, haystack) is True

    def test_not_nested_different_elements(self):
        """Test needle not in haystack (different elements)."""
        needle = ("x", "y")
        haystack = ("a", "b", "c", "d")
        assert is_nested_in(needle, haystack) is False

    def test_not_nested_partial_match(self):
        """Test needle has partial but not complete match."""
        needle = ("b", "d")
        haystack = ("a", "b", "c", "d")
        assert is_nested_in(needle, haystack) is False

    def test_needle_longer_than_haystack(self):
        """Test needle is longer than haystack."""
        needle = ("a", "b", "c", "d", "e")
        haystack = ("a", "b", "c")
        assert is_nested_in(needle, haystack) is False

    def test_empty_needle(self):
        """Test empty needle (edge case - should return True)."""
        needle = ()
        haystack = ("a", "b", "c")
        assert is_nested_in(needle, haystack) is True

    def test_empty_haystack(self):
        """Test empty haystack with non-empty needle."""
        needle = ("a",)
        haystack = ()
        assert is_nested_in(needle, haystack) is False

    def test_both_empty(self):
        """Test both needle and haystack empty."""
        needle = ()
        haystack = ()
        assert is_nested_in(needle, haystack) is True

    def test_single_element_match(self):
        """Test single element needle in haystack."""
        needle = ("b",)
        haystack = ("a", "b", "c")
        assert is_nested_in(needle, haystack) is True

    def test_single_element_no_match(self):
        """Test single element needle not in haystack."""
        needle = ("x",)
        haystack = ("a", "b", "c")
        assert is_nested_in(needle, haystack) is False

    def test_repeated_elements(self):
        """Test needle with repeated elements."""
        needle = ("a", "a")
        haystack = ("a", "a", "b")
        assert is_nested_in(needle, haystack) is True

    def test_repeated_elements_no_match(self):
        """Test needle with repeated elements not contiguous."""
        needle = ("a", "a")
        haystack = ("a", "b", "a")
        assert is_nested_in(needle, haystack) is False


@pytest.mark.unit
class TestDeduplicateNestedSequences:
    """Test the deduplicate_nested_sequences function."""

    def test_empty_list(self):
        """Test with empty list."""
        result = deduplicate_nested_sequences([])
        assert result == []

    def test_single_sequence(self):
        """Test with single sequence."""
        sequences = [("a", "b", "c")]
        result = deduplicate_nested_sequences(sequences)
        assert result == [("a", "b", "c")]

    def test_no_nesting(self):
        """Test sequences with no nesting."""
        sequences = [
            ("a", "b", "c"),
            ("d", "e", "f"),
            ("g", "h", "i"),
        ]
        result = deduplicate_nested_sequences(sequences)
        assert len(result) == 3
        assert set(result) == set(sequences)

    def test_remove_nested_shorter(self):
        """Test that shorter nested sequence is removed."""
        sequences = [
            ("a", "b", "c", "d"),  # Longer
            ("b", "c"),  # Nested in first
        ]
        result = deduplicate_nested_sequences(sequences)
        assert len(result) == 1
        assert result[0] == ("a", "b", "c", "d")

    def test_remove_nested_at_beginning(self):
        """Test nested sequence at beginning is removed."""
        sequences = [
            ("a", "b", "c", "d"),  # Longer
            ("a", "b"),  # Nested at beginning
        ]
        result = deduplicate_nested_sequences(sequences)
        assert len(result) == 1
        assert result[0] == ("a", "b", "c", "d")

    def test_remove_nested_at_end(self):
        """Test nested sequence at end is removed."""
        sequences = [
            ("a", "b", "c", "d"),  # Longer
            ("c", "d"),  # Nested at end
        ]
        result = deduplicate_nested_sequences(sequences)
        assert len(result) == 1
        assert result[0] == ("a", "b", "c", "d")

    def test_multiple_nested_sequences(self):
        """Test multiple sequences nested in one longer sequence."""
        sequences = [
            ("a", "b", "c", "d", "e"),  # Longest
            ("a", "b"),  # Nested
            ("b", "c", "d"),  # Nested
            ("d", "e"),  # Nested
        ]
        result = deduplicate_nested_sequences(sequences)
        assert len(result) == 1
        assert result[0] == ("a", "b", "c", "d", "e")

    def test_identical_sequences_keep_first(self):
        """Test identical sequences - keep first."""
        sequences = [
            ("a", "b", "c"),
            ("a", "b", "c"),
            ("a", "b", "c"),
        ]
        result = deduplicate_nested_sequences(sequences)
        assert len(result) == 1
        assert result[0] == ("a", "b", "c")

    def test_mixed_nested_and_unique(self):
        """Test mix of nested and unique sequences."""
        sequences = [
            ("a", "b", "c", "d"),  # Keep
            ("x", "y", "z"),  # Keep
            ("b", "c"),  # Nested in first
        ]
        result = deduplicate_nested_sequences(sequences)
        assert len(result) == 2
        assert ("a", "b", "c", "d") in result
        assert ("x", "y", "z") in result

    def test_chain_of_nesting(self):
        """Test sequences nested in each other."""
        sequences = [
            ("a", "b", "c", "d", "e", "f"),  # Longest
            ("b", "c", "d", "e"),  # Nested in longest
            ("c", "d"),  # Nested in both above
        ]
        result = deduplicate_nested_sequences(sequences)
        assert len(result) == 1
        assert result[0] == ("a", "b", "c", "d", "e", "f")

    def test_order_preserved(self):
        """Test that order of kept sequences is preserved."""
        sequences = [
            ("x", "y", "z"),
            ("a", "b", "c"),
            ("m", "n", "o"),
        ]
        result = deduplicate_nested_sequences(sequences)
        # Should preserve order
        assert result == sequences

    def test_multiple_identical_keeps_lowest_index(self):
        """Test multiple identical sequences keeps the one with lowest index."""
        sequences = [
            ("a", "b", "c"),  # Index 0
            ("x", "y"),
            ("a", "b", "c"),  # Index 2 - should be removed
        ]
        result = deduplicate_nested_sequences(sequences)
        assert len(result) == 2
        assert ("a", "b", "c") in result
        assert ("x", "y") in result

    def test_already_removed_sequence_skipped(self):
        """Test that already-removed sequences are skipped in nested check."""
        # This tests line 98 - the early continue when i not in to_keep
        # Need a case where sequence at index i is removed, then we iterate to it
        sequences = [
            ("b", "c"),  # Index 0 - will be removed when comparing with index 1
            ("a", "b", "c", "d"),  # Index 1 - longer, contains index 0
            ("a", "b"),  # Index 2 - will be removed when comparing with index 1
        ]
        result = deduplicate_nested_sequences(sequences)
        # When we get to outer loop i=0, it's already been removed by i=1's comparison
        # So line 98 (continue) should execute
        assert len(result) == 1
        assert result[0] == ("a", "b", "c", "d")


@pytest.mark.unit
class TestIndexSequenceWindows:
    """Test the index_sequence_windows function."""

    def test_single_window_sequence(self):
        """Test indexing sequence with single window."""
        seq = RecordedSequence(
            first_output_line=PRELOADED_SEQUENCE_LINE,
            window_hashes=["hash1"],
            counts=None,
        )
        index = defaultdict(list)

        index_sequence_windows(seq, index)

        assert len(index) == 1
        assert "hash1" in index
        assert len(index["hash1"]) == 1
        assert index["hash1"][0] == (seq, 0)

    def test_multiple_window_sequence(self):
        """Test indexing sequence with multiple windows."""
        seq = RecordedSequence(
            first_output_line=PRELOADED_SEQUENCE_LINE,
            window_hashes=["hash1", "hash2", "hash3"],
            counts=None,
        )
        index = defaultdict(list)

        index_sequence_windows(seq, index)

        assert len(index) == 3
        assert index["hash1"][0] == (seq, 0)
        assert index["hash2"][0] == (seq, 1)
        assert index["hash3"][0] == (seq, 2)

    def test_empty_sequence(self):
        """Test indexing sequence with no windows."""
        seq = RecordedSequence(
            first_output_line=PRELOADED_SEQUENCE_LINE,
            window_hashes=[],
            counts=None,
        )
        index = defaultdict(list)

        index_sequence_windows(seq, index)

        assert len(index) == 0

    def test_duplicate_hashes(self):
        """Test sequence with duplicate window hashes."""
        seq = RecordedSequence(
            first_output_line=PRELOADED_SEQUENCE_LINE,
            window_hashes=["hash1", "hash2", "hash1"],
            counts=None,
        )
        index = defaultdict(list)

        index_sequence_windows(seq, index)

        # Same hash appears twice at different positions
        assert len(index["hash1"]) == 2
        assert (seq, 0) in index["hash1"]
        assert (seq, 2) in index["hash1"]


@pytest.mark.unit
class TestInitializePreloadedSequences:
    """Test the initialize_preloaded_sequences function."""

    def test_empty_preload_set(self):
        """Test with empty preload set."""
        registry = SequenceRegistry(max_sequences=None)
        index = defaultdict(list)

        initialize_preloaded_sequences(
            preloaded_sequences=set(),
            sequence_records=registry,
            sequence_window_index=index,
            delimiter="\n",
            window_size=3,
        )

        assert len(registry) == 0
        assert len(index) == 0

    def test_single_sequence_text(self):
        """Test preloading single text sequence."""
        registry = SequenceRegistry(max_sequences=None)
        index = defaultdict(list)

        seq_content = "line1\nline2\nline3\nline4"
        initialize_preloaded_sequences(
            preloaded_sequences={seq_content},
            sequence_records=registry,
            sequence_window_index=index,
            delimiter="\n",
            window_size=3,
        )

        assert len(registry) == 1
        # Sequence has 4 lines, so 2 windows (4-3+1=2)
        assert len(index) > 0

    def test_single_sequence_bytes(self):
        """Test preloading single bytes sequence."""
        registry = SequenceRegistry(max_sequences=None)
        index = defaultdict(list)

        seq_content = b"line1\nline2\nline3\nline4"
        initialize_preloaded_sequences(
            preloaded_sequences={seq_content},
            sequence_records=registry,
            sequence_window_index=index,
            delimiter=b"\n",
            window_size=3,
        )

        assert len(registry) == 1

    def test_skip_short_sequence(self):
        """Test that sequences shorter than window_size are skipped."""
        registry = SequenceRegistry(max_sequences=None)
        index = defaultdict(list)

        # Only 2 lines, but window_size=3
        seq_content = "line1\nline2"
        initialize_preloaded_sequences(
            preloaded_sequences={seq_content},
            sequence_records=registry,
            sequence_window_index=index,
            delimiter="\n",
            window_size=3,
        )

        assert len(registry) == 0
        assert len(index) == 0

    def test_deduplicate_nested_sequences_in_preload(self):
        """Test that nested sequences are deduplicated."""
        registry = SequenceRegistry(max_sequences=None)
        index = defaultdict(list)

        # Second sequence is nested in first
        seq1 = "line1\nline2\nline3\nline4\nline5"
        seq2 = "line2\nline3\nline4"

        initialize_preloaded_sequences(
            preloaded_sequences={seq1, seq2},
            sequence_records=registry,
            sequence_window_index=index,
            delimiter="\n",
            window_size=3,
        )

        # Should only keep the longer sequence
        assert len(registry) == 1

    def test_deduplicate_identical_sequences(self):
        """Test that identical sequences are deduplicated."""
        registry = SequenceRegistry(max_sequences=None)
        index = defaultdict(list)

        seq_content = "line1\nline2\nline3\nline4"

        initialize_preloaded_sequences(
            preloaded_sequences={seq_content, seq_content},
            sequence_records=registry,
            sequence_window_index=index,
            delimiter="\n",
            window_size=3,
        )

        # Should only keep one copy
        assert len(registry) == 1

    def test_multiple_unique_sequences(self):
        """Test preloading multiple non-nested sequences."""
        registry = SequenceRegistry(max_sequences=None)
        index = defaultdict(list)

        seq1 = "aaa\nbbb\nccc"
        seq2 = "xxx\nyyy\nzzz"

        initialize_preloaded_sequences(
            preloaded_sequences={seq1, seq2},
            sequence_records=registry,
            sequence_window_index=index,
            delimiter="\n",
            window_size=3,
        )

        # Should keep both
        assert len(registry) == 2

    def test_custom_delimiter(self):
        """Test with custom delimiter."""
        registry = SequenceRegistry(max_sequences=None)
        index = defaultdict(list)

        seq_content = "line1|line2|line3|line4"

        initialize_preloaded_sequences(
            preloaded_sequences={seq_content},
            sequence_records=registry,
            sequence_window_index=index,
            delimiter="|",
            window_size=3,
        )

        assert len(registry) == 1

    def test_preloaded_sequences_marked_correctly(self):
        """Test that preloaded sequences have correct first_output_line."""
        registry = SequenceRegistry(max_sequences=None)
        index = defaultdict(list)

        seq_content = "line1\nline2\nline3\nline4"

        initialize_preloaded_sequences(
            preloaded_sequences={seq_content},
            sequence_records=registry,
            sequence_window_index=index,
            delimiter="\n",
            window_size=3,
        )

        # Check that the sequence is marked as preloaded
        for seq in registry:
            assert seq.first_output_line == PRELOADED_SEQUENCE_LINE

    def test_window_index_populated(self):
        """Test that window index is correctly populated."""
        registry = SequenceRegistry(max_sequences=None)
        index = defaultdict(list)

        seq_content = "line1\nline2\nline3\nline4"

        initialize_preloaded_sequences(
            preloaded_sequences={seq_content},
            sequence_records=registry,
            sequence_window_index=index,
            delimiter="\n",
            window_size=3,
        )

        # Sequence has 4 lines, so should have 2 windows (4-3+1=2)
        # Each window should be in the index
        assert len(index) > 0

        # Verify that each index entry points to the sequence
        for _hash_key, entries in index.items():
            assert len(entries) > 0
            for seq, _window_idx in entries:
                assert seq in registry
