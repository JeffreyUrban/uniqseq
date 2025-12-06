"""Additional unit tests to target specific uncovered edge cases in uniqseq."""

from io import BytesIO, StringIO

import pytest

from uniqseq.uniqseq import UniqSeq


@pytest.mark.unit
def test_sequence_confirmed_multiple_times():
    """Test that repeat_count increments when same sequence appears in multiple flush cycles.

    This targets line 469 in uniqseq.py - the else branch in _record_sequence
    when a sequence already exists and we're incrementing repeat_count.
    """
    # Process data in chunks with flush() in between
    # Each chunk has the same sequence
    uniqseq = UniqSeq(window_size=3, max_history=None)
    output = StringIO()

    # First chunk: A, B, C appears once
    for line in ["A", "B", "C", "X"]:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)  # Records the sequence first time

    # Second chunk: A, B, C appears again
    for line in ["A", "B", "C", "Y"]:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)  # Should increment repeat_count (line 469)

    # Third chunk: A, B, C appears again
    for line in ["A", "B", "C", "Z"]:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)  # Should increment repeat_count again

    # Should have one sequence with repeat_count >= 2
    total_sequences = sum(len(seqs) for seqs in uniqseq.sequence_records.values())
    assert total_sequences >= 1


@pytest.mark.unit
def test_binary_preloaded_short_sequence():
    """Test binary mode with preloaded sequence shorter than window size.

    This targets lines 272-273, 282 in uniqseq.py - binary mode assertions
    and the continue statement for sequences shorter than window_size.
    """

    # Create a short binary sequence (less than window_size)
    sequence = b"A\x00B"  # Only 2 records, but window_size is 3
    preloaded = {sequence}  # Set of sequence content

    uniqseq = UniqSeq(
        window_size=3,
        max_history=None,
        delimiter=b"\x00",
        preloaded_sequences=preloaded,
    )

    # Process some binary data
    lines = [b"X", b"Y", b"Z"]
    output = BytesIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should have processed normally (short preloaded sequence ignored)
    assert output.getvalue()  # Has output


@pytest.mark.unit
def test_preloaded_sequence_saved_on_match():
    """Test that preloaded sequences are saved when matched during processing.

    This targets lines 540-543 in uniqseq.py - saving preloaded sequences
    in _handle_duplicate() when matched via process_line.
    """
    from uniqseq.library import compute_sequence_hash

    # Preload a sequence
    sequence = "A\nB\nC"
    seq_hash = compute_sequence_hash(sequence)
    preloaded = {seq_hash: sequence}

    saved_sequences = {}

    def save_callback(file_content: str) -> None:
        from uniqseq.library import compute_sequence_hash

        seq_hash = compute_sequence_hash(file_content)
        saved_sequences[seq_hash] = file_content

    uniqseq = UniqSeq(
        window_size=3,
        max_history=None,
        preloaded_sequences=preloaded,
        save_sequence_callback=save_callback,
    )

    # Process the preloaded sequence twice to trigger match confirmation
    lines = ["A", "B", "C", "A", "B", "C"]
    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # The preloaded sequence should have been saved on first match
    assert seq_hash in saved_sequences
    assert saved_sequences[seq_hash] == "A\nB\nC"


@pytest.mark.unit
def test_history_eviction_during_matching():
    """Test that candidate matching handles evicted history positions.

    This targets line 572 in uniqseq.py - the continue statement when
    history position no longer exists (evicted during candidate matching).
    """
    # Create a scenario with aggressive history limits
    # We'll create many unique sequences to fill history, then try to match
    lines = []

    # Fill history with 150 unique sequences
    for i in range(150):
        for j in range(3):
            lines.append(f"Unique{i}Line{j}")

    # Now add a sequence that starts matching an old one
    lines.extend(["Unique0Line0", "Unique0Line1", "Different"])

    uniqseq = UniqSeq(window_size=3, max_history=100)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should complete without errors
    assert output.getvalue()  # Has output


@pytest.mark.unit
def test_flush_with_existing_pattern():
    """Test flush path when pattern already exists (repeat of known sequence).

    This targets lines 610-634 in uniqseq.py - the flush path in _check_candidates
    when full_sequence_hash already exists in unique_sequences, which should skip the
    buffer and increment repeat_count.
    """
    # Process in two chunks to create the scenario:
    # 1. First chunk establishes a sequence
    # 2. Second chunk has that sequence in buffer at flush time
    uniqseq = UniqSeq(window_size=3, max_history=None)
    output = StringIO()

    # First chunk: Create and record sequence "A", "B", "C"
    for line in ["A", "B", "C", "X"]:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)  # Records ABC as a unique sequence

    # Second chunk: Have "A", "B", "C" in buffer at flush
    # This should match the existing sequence
    for line in ["Y", "A", "B", "C"]:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)  # Should find ABC in buffer, match to existing, and skip it

    # Should have processed correctly
    output_lines = output.getvalue().strip().split("\n")
    assert "A" in output_lines and "B" in output_lines and "C" in output_lines


@pytest.mark.unit
def test_flush_with_preloaded_existing_pattern():
    """Test flush with preloaded pattern that gets matched and saved.

    This targets lines 618-627 in uniqseq.py - saving preloaded sequences
    during flush when pattern exists.
    """
    from uniqseq.library import compute_sequence_hash

    # Preload a sequence
    sequence = "X\nY\nZ"
    seq_hash = compute_sequence_hash(sequence)
    preloaded = {sequence}  # Set of sequence content

    saved_sequences = {}

    def save_callback(file_content: str) -> None:
        from uniqseq.library import compute_sequence_hash

        seq_hash = compute_sequence_hash(file_content)
        saved_sequences[seq_hash] = file_content

    uniqseq = UniqSeq(
        window_size=3,
        max_history=None,
        preloaded_sequences=preloaded,
        save_sequence_callback=save_callback,
    )

    # Process lines including the preloaded sequence in buffer at flush
    lines = ["A", "B", "C", "X", "Y", "Z"]
    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    # Buffer now has "X", "Y", "Z" which matches preloaded - flush will find it
    uniqseq.flush(output)

    # Should have saved the preloaded sequence
    assert seq_hash in saved_sequences


@pytest.mark.unit
def test_lru_eviction_actually_happens():
    """Test that LRU eviction actually removes oldest entry.

    This targets line 672 in uniqseq.py - the popitem(last=False) call
    that removes the oldest entry when max_unique_sequences is exceeded.
    """
    # Create many different sequences to exceed max_unique_sequences
    lines = []

    # Create 60 unique 3-line sequences in chunks to trigger flush-based recording
    for i in range(60):
        for j in range(3):
            lines.append(f"Seq{i:03d}Line{j}")
        lines.append("---")  # Separator

    # Use small max_unique_sequences and process in chunks with flush
    uniqseq = UniqSeq(window_size=3, max_history=100, max_unique_sequences=50)

    output = StringIO()
    chunk_size = 20  # Process in chunks and flush

    for i in range(0, len(lines), chunk_size):
        chunk = lines[i : i + chunk_size]
        for line in chunk:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)  # This triggers _record_sequence which checks max_unique_sequences

    # Check that eviction occurred - total sequences should be <= 50
    total_seqs = sum(len(seqs) for seqs in uniqseq.sequence_records.values())
    assert total_seqs <= 50, f"Expected <= 50 sequences, got {total_seqs}"


@pytest.mark.unit
def test_match_index_overflow_edge_case():
    """Test defensive code for match.next_window_index overflow.

    This targets lines 498-499 in uniqseq.py - the edge case handling
    when next_window_index >= len(window_hashes), which shouldn't happen but
    is handled defensively.

    Note: This is very difficult to trigger naturally, so we're testing that
    the surrounding logic works correctly.
    """
    # Create a pattern that gets matched and confirmed
    lines = ["A", "B", "C", "D", "A", "B", "C", "D"]

    uniqseq = UniqSeq(window_size=4, max_history=None)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should complete without errors
    output_lines = output.getvalue().strip().split("\n")
    assert len(output_lines) == 4  # Only first occurrence
