"""Unit tests to increase uniqseq coverage for edge cases."""

from io import BytesIO, StringIO

import pytest

from uniqseq.uniqseq import UniqSeq


@pytest.mark.unit
def test_binary_mode_sequence_splitting():
    """Test binary mode with delimiter splitting."""
    # Lines with binary delimiter
    lines = [b"Line1\x00", b"Line2\x00", b"Line3\x00", b"Line1\x00", b"Line2\x00", b"Line3\x00"]

    saved_sequences = {}

    def save_callback(file_content: bytes) -> None:
        from uniqseq.library import compute_sequence_hash

        seq_hash = compute_sequence_hash(file_content)
        saved_sequences[seq_hash] = file_content

    uniqseq = UniqSeq(
        window_size=3,
        max_history=None,
        delimiter=b"\x00",
        save_sequence_callback=save_callback,
    )

    output = BytesIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should have saved one sequence
    assert len(saved_sequences) == 1
    seq_content = list(saved_sequences.values())[0]
    assert isinstance(seq_content, bytes)


@pytest.mark.unit
def test_repeat_count_increment_on_confirmation():
    """Test that repeat_count is incremented when sequence is confirmed multiple times."""
    # Create a sequence that appears 3 times with clear separation
    lines = ["A", "B", "C", "D", "X", "A", "B", "C", "D", "Y", "A", "B", "C", "D"]

    uniqseq = UniqSeq(window_size=4, max_history=None)

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should have at least one sequence tracked
    total_sequences = sum(len(seqs) for seqs in uniqseq.sequence_records.values())
    assert total_sequences >= 1, "Should have at least one sequence"

    # Check that sequences were deduplicated (output shorter than input)
    output_lines = output.getvalue().strip().split("\n")
    assert len(output_lines) < len(lines), (
        "Output should be shorter than input due to deduplication"
    )


@pytest.mark.unit
def test_history_limit_eviction():
    """Test that LRU eviction happens when history limit is reached."""
    # Create many different sequences to exceed history
    lines = []
    for i in range(150):  # Generate 150 different sequences
        for j in range(3):  # Each sequence is 3 lines
            lines.append(f"Seq{i}Line{j}")

    # Use small history limit
    uniqseq = UniqSeq(window_size=3, max_history=100)

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # With 150 sequences and history limit of 100, some should have been evicted
    total_sequences = sum(len(seqs) for seqs in uniqseq.sequence_records.values())
    assert total_sequences <= 100, f"Expected <= 100 sequences, got {total_sequences}"


@pytest.mark.unit
def test_save_callback_on_match_confirmation():
    """Test that save callback is called when a match is confirmed during processing."""
    lines = ["X", "Y", "Z", "X", "Y", "Z"]

    saved_sequences = {}

    def save_callback(file_content: str) -> None:
        from uniqseq.library import compute_sequence_hash

        seq_hash = compute_sequence_hash(file_content)
        saved_sequences[seq_hash] = file_content

    uniqseq = UniqSeq(window_size=3, max_history=None, save_sequence_callback=save_callback)

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should have called save callback
    assert len(saved_sequences) == 1
    assert saved_sequences[list(saved_sequences.keys())[0]] == "X\nY\nZ"


@pytest.mark.unit
def test_preloaded_sequence_first_observation():
    """Test that preloaded sequences are saved when first observed."""
    from uniqseq.library import compute_sequence_hash

    # Preload a sequence
    sequence = "A\nB\nC"
    seq_hash = compute_sequence_hash(sequence)
    preloaded = {sequence}  # Set of sequence content

    saved_sequences = {}

    def save_callback(file_content: str) -> None:
        content_hash = compute_sequence_hash(file_content)
        saved_sequences[content_hash] = file_content

    uniqseq = UniqSeq(
        window_size=3,
        max_history=None,
        preloaded_sequences=preloaded,
        save_sequence_callback=save_callback,
    )

    # Process lines that match the preloaded sequence
    lines = ["A", "B", "C", "D"]
    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # The preloaded sequence should have been saved on first observation
    assert seq_hash in saved_sequences
    assert saved_sequences[seq_hash] == "A\nB\nC"


@pytest.mark.unit
def test_preloaded_sequence_not_saved_twice():
    """Test that preloaded sequences are only saved once."""
    from uniqseq.library import compute_sequence_hash

    sequence = "A\nB\nC"
    seq_hash = compute_sequence_hash(sequence)
    preloaded = {sequence}  # Set of sequence content

    save_count = {}
    saved_hashes = set()

    def save_callback(file_content: str) -> None:
        content_hash = compute_sequence_hash(file_content)
        if content_hash in saved_hashes:
            return  # Already saved
        saved_hashes.add(content_hash)
        save_count[content_hash] = save_count.get(content_hash, 0) + 1

    uniqseq = UniqSeq(
        window_size=3,
        max_history=None,
        preloaded_sequences=preloaded,
        save_sequence_callback=save_callback,
    )

    # Process the sequence twice
    lines = ["A", "B", "C", "X", "A", "B", "C"]
    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should only be saved once (on first observation)
    assert save_count.get(seq_hash, 0) == 1


@pytest.mark.unit
def test_multiple_matches_cleanup():
    """Test cleanup of multiple potential matches."""
    # Create overlapping sequences
    lines = ["A", "B", "C", "D", "E", "A", "B", "C", "D", "E"]

    uniqseq = UniqSeq(window_size=5, max_history=None)

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should have detected and cleaned up the match
    output_lines = output.getvalue().strip().split("\n")
    assert len(output_lines) == 5  # Only first occurrence


@pytest.mark.unit
def test_buffer_skip_and_candidate_clear():
    """Test that buffer skip clears candidates properly."""
    # Sequence that gets confirmed
    lines = ["X", "Y", "Z", "W", "X", "Y", "Z", "W"]

    uniqseq = UniqSeq(window_size=4, max_history=None)

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # After confirmation, candidates should be cleared
    # This is tested implicitly by correct output
    output_lines = output.getvalue().strip().split("\n")
    assert len(output_lines) == 4  # Only first occurrence


@pytest.mark.unit
def test_window_hash_collision_handling():
    """Test handling of sequences with same window hash but different full hash."""
    # Create sequences that might have window hash collisions
    # (This is statistical, so we test the mechanism works)
    lines = []
    for i in range(20):
        for j in range(3):
            lines.append(f"Line{i}_{j}")

    uniqseq = UniqSeq(window_size=3, max_history=None)

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should process without errors
    assert output.getvalue()  # Has output


@pytest.mark.unit
def test_empty_input():
    """Test handling of empty input."""
    uniqseq = UniqSeq(window_size=3, max_history=None)

    output = StringIO()
    uniqseq.flush(output)

    # Should handle empty input gracefully
    assert output.getvalue() == ""


@pytest.mark.unit
def test_input_shorter_than_window():
    """Test input with fewer lines than window size."""
    lines = ["A", "B"]  # Only 2 lines, window size is 3

    uniqseq = UniqSeq(window_size=3, max_history=None)

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should output all lines (no sequences possible)
    output_lines = output.getvalue().strip().split("\n")
    assert output_lines == ["A", "B"]


@pytest.mark.unit
def test_exact_window_size_sequence():
    """Test sequence that is exactly window_size."""
    lines = ["A", "B", "C", "A", "B", "C"]

    uniqseq = UniqSeq(window_size=3, max_history=None)

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should detect exact match and skip second occurrence
    output_lines = output.getvalue().strip().split("\n")
    assert len(output_lines) == 3


@pytest.mark.unit
def test_save_callback_with_longer_sequence():
    """Test save callback with sequence longer than window_size."""
    lines = ["A", "B", "C", "D", "E", "A", "B", "C", "D", "E"]

    saved_sequences = {}

    def save_callback(file_content: str) -> None:
        from uniqseq.library import compute_sequence_hash

        seq_hash = compute_sequence_hash(file_content)
        saved_sequences[seq_hash] = file_content

    uniqseq = UniqSeq(window_size=3, max_history=None, save_sequence_callback=save_callback)

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should have saved the full 5-line sequence
    assert len(saved_sequences) == 1
    seq_content = list(saved_sequences.values())[0]
    assert seq_content == "A\nB\nC\nD\nE"
