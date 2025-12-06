"""Tests for max_candidates and max_unique_sequences limit enforcement.

These tests verify that the limits actually prevent deduplication when reached.
"""

from io import StringIO

import pytest

from uniqseq.uniqseq import UniqSeq


@pytest.mark.unit
def test_max_candidates_enforcement():
    """Test that ActiveMatchManager enforces max_candidates limit.

    This is a direct unit test of the ActiveMatchManager class to verify
    that it correctly limits the number of concurrent matches.
    """
    from unittest.mock import Mock

    from uniqseq.uniqseq import ActiveMatchManager

    # Create manager with limit of 2
    manager = ActiveMatchManager(max_candidates=2)

    # Create mock match objects
    match1 = Mock()
    match2 = Mock()
    match3 = Mock()

    # Should be able to add first two matches
    assert manager.try_add(match1) is True
    assert len(manager) == 1

    assert manager.try_add(match2) is True
    assert len(manager) == 2

    # Should NOT be able to add third match (at capacity)
    assert manager.try_add(match3) is False
    assert len(manager) == 2

    # Remove one match
    manager.discard(match1)
    assert len(manager) == 1

    # Now should be able to add the third match
    assert manager.try_add(match3) is True
    assert len(manager) == 2


@pytest.mark.unit
def test_max_unique_sequences_enforcement():
    """Test that SequenceRegistry enforces max_unique_sequences limit.

    This is a direct unit test of the SequenceRegistry class to verify
    that it correctly limits the number of recorded sequences with LRU eviction.
    """
    from uniqseq.uniqseq import PRELOADED_SEQUENCE_LINE, RecordedSequence, SequenceRegistry

    # Create registry with limit of 2
    registry = SequenceRegistry(max_sequences=2)

    # Create mock sequences
    seq1 = RecordedSequence(first_output_line=1, window_hashes=["a", "b", "c"], counts=None)
    seq2 = RecordedSequence(first_output_line=2, window_hashes=["d", "e", "f"], counts=None)
    seq3 = RecordedSequence(first_output_line=3, window_hashes=["g", "h", "i"], counts=None)

    # Should be able to add first two sequences
    registry.add(seq1)
    assert len(registry) == 1

    registry.add(seq2)
    assert len(registry) == 2

    # Adding third sequence should evict the first (LRU)
    registry.add(seq3)
    assert len(registry) == 2
    assert seq1 not in registry  # Evicted (least recently used)
    assert seq2 in registry
    assert seq3 in registry

    # Access seq2 to make it recently used
    registry.mark_accessed(seq2)

    # Add another sequence - should evict seq3 (now LRU)
    seq4 = RecordedSequence(first_output_line=4, window_hashes=["j", "k", "l"], counts=None)
    registry.add(seq4)
    assert len(registry) == 2
    assert seq3 not in registry  # Evicted
    assert seq2 in registry  # Kept (recently accessed)
    assert seq4 in registry  # New

    # Test that preloaded sequences are never evicted and don't count toward limit
    registry_with_preload = SequenceRegistry(max_sequences=2)
    preloaded_seq = RecordedSequence(
        first_output_line=PRELOADED_SEQUENCE_LINE, window_hashes=["x", "y", "z"], counts=None
    )
    reg_seq1 = RecordedSequence(first_output_line=1, window_hashes=["a", "b"], counts=None)
    reg_seq2 = RecordedSequence(first_output_line=2, window_hashes=["c", "d"], counts=None)
    reg_seq3 = RecordedSequence(first_output_line=3, window_hashes=["e", "f"], counts=None)

    # Add preloaded sequence
    registry_with_preload.add(preloaded_seq)
    assert len(registry_with_preload) == 1

    # Add first regular sequence (total: 2, non-preloaded: 1)
    registry_with_preload.add(reg_seq1)
    assert len(registry_with_preload) == 2

    # Add second regular sequence (total: 3, non-preloaded: 2) - within limit
    registry_with_preload.add(reg_seq2)
    assert len(registry_with_preload) == 3  # 1 preloaded + 2 regular
    assert preloaded_seq in registry_with_preload
    assert reg_seq1 in registry_with_preload
    assert reg_seq2 in registry_with_preload

    # Add third regular sequence - should evict reg_seq1 (LRU non-preloaded)
    registry_with_preload.add(reg_seq3)
    assert len(registry_with_preload) == 3  # 1 preloaded + 2 regular
    assert preloaded_seq in registry_with_preload  # Never evicted
    assert reg_seq1 not in registry_with_preload  # Evicted (LRU)
    assert reg_seq2 in registry_with_preload
    assert reg_seq3 in registry_with_preload


@pytest.mark.unit
def test_unlimited_candidates():
    """Test that unlimited candidates allows full deduplication.

    This is a control test to verify that without limits, all patterns
    are properly deduplicated.
    """
    # Same input as above tests
    input_lines = [
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
    ]

    input_data = "\n".join(input_lines) + "\n"
    output = StringIO()

    # No limits - should deduplicate perfectly
    uniqseq = UniqSeq(
        window_size=3,
        max_history=None,
        max_unique_sequences=None,
        max_candidates=None,
        delimiter="\n",
    )

    for line in input_data.split("\n")[:-1]:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)

    output_lines = output.getvalue().strip().split("\n")

    # With no limits, should deduplicate perfectly: only first occurrences
    assert len(output_lines) == 9, (
        f"Expected perfect deduplication (9 lines), got {len(output_lines)}"
    )


@pytest.mark.unit
def test_unlimited_unique_sequences():
    """Test that unlimited unique_sequences allows full deduplication.

    This is a control test to verify that without limits, all sequences
    are properly recorded and deduplicated.
    """
    # Same input as above tests
    input_lines = [
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
        "A",
        "B",
        "C",
        "D",
        "E",
        "F",
        "G",
        "H",
        "I",
    ]

    input_data = "\n".join(input_lines) + "\n"
    output = StringIO()

    # No limits - should deduplicate perfectly
    uniqseq = UniqSeq(
        window_size=3,
        max_history=None,
        max_unique_sequences=None,
        max_candidates=None,
        delimiter="\n",
    )

    for line in input_data.split("\n")[:-1]:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)

    output_lines = output.getvalue().strip().split("\n")

    # Should deduplicate perfectly
    assert len(output_lines) == 9, (
        f"Expected perfect deduplication (9 lines), got {len(output_lines)}"
    )

    # Verify sequence was recorded (actual count is 1 due to contiguous matching)
    stats = uniqseq.get_stats()
    assert stats["unique_sequences"] >= 1, (
        f"Expected at least 1 recorded sequence, got {stats['unique_sequences']}"
    )
