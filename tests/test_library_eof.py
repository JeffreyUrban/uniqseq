"""Tests for library functionality with EOF-detected sequences.

Tests that sequences detected only at EOF (via flush()) are properly saved to the library.
"""

from io import BytesIO, StringIO

import pytest

from uniqseq.uniqseq import UniqSeq


@pytest.mark.unit
def test_eof_sequence_saved_to_library():
    """Test that sequences detected at EOF are saved to library via callback."""
    # Input: ABCD repeated twice (window size 4)
    # First occurrence at lines 1-4, second at lines 5-8
    # The second occurrence will be detected at EOF during flush()
    # Lines WITHOUT delimiters (as process_line expects)
    lines = ["A", "B", "C", "D", "A", "B", "C", "D"]

    saved_sequences = {}

    def save_callback(file_content: str) -> None:
        from uniqseq.library import compute_sequence_hash

        seq_hash = compute_sequence_hash(file_content)
        saved_sequences[seq_hash] = file_content

    uniqseq = UniqSeq(
        window_size=4,
        max_history=None,
        save_sequence_callback=save_callback,
    )

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should have saved the ABCD sequence
    assert len(saved_sequences) == 1

    # Get the saved sequence
    seq_hash = list(saved_sequences.keys())[0]
    seq_lines = saved_sequences[seq_hash]

    # Verify content (lines without delimiters)
    assert seq_lines == "A\nB\nC\nD"


@pytest.mark.unit
def test_eof_preloaded_sequence_saved_if_not_in_library():
    """Test that EOF-detected preloaded sequences ARE saved if not already in library."""
    # Lines WITHOUT delimiters (as process_line expects)
    lines = ["A", "B", "C", "D", "A", "B", "C", "D"]

    # Use library function to compute hash (now correct)
    from uniqseq.library import compute_sequence_hash

    sequence_content = "A\nB\nC\nD"
    seq_hash = compute_sequence_hash(sequence_content)

    # Preload the sequence (e.g., from --read-sequences)
    preloaded = {seq_hash: sequence_content}

    saved_sequences = {}

    def save_callback(file_content: str) -> None:
        from uniqseq.library import compute_sequence_hash

        seq_hash = compute_sequence_hash(file_content)
        saved_sequences[seq_hash] = file_content

    uniqseq = UniqSeq(
        window_size=4,
        max_history=None,
        preloaded_sequences=preloaded,
        save_sequence_callback=save_callback,
    )

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # SHOULD have saved the preloaded sequence to library (since not already there)
    assert len(saved_sequences) == 1
    assert seq_hash in saved_sequences
    assert saved_sequences[seq_hash] == "A\nB\nC\nD"


@pytest.mark.unit
def test_eof_sequence_not_saved_if_already_saved():
    """Test that EOF-detected sequences are not saved again if already in library."""
    # Lines WITHOUT delimiters (as process_line expects)
    lines = ["A", "B", "C", "D", "A", "B", "C", "D"]

    # Preload the sequence (new API uses set of sequence content, not dict)
    sequence = "A\nB\nC\nD"
    preloaded = {sequence}

    save_call_count = 0
    saved_hashes = set()

    def save_callback(file_content: str) -> None:
        from uniqseq.library import compute_sequence_hash

        seq_hash = compute_sequence_hash(file_content)
        if seq_hash in saved_hashes:
            return  # Already saved
        saved_hashes.add(seq_hash)
        nonlocal save_call_count
        save_call_count += 1

    uniqseq = UniqSeq(
        window_size=4,
        max_history=None,
        preloaded_sequences=preloaded,
        save_sequence_callback=save_callback,
    )

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should have called save callback once on first observation of preloaded sequence
    # Even though preloaded, it still gets saved on first match (hash-based deduplication prevents duplicates)
    assert save_call_count == 1


@pytest.mark.unit
def test_eof_multiple_sequences_saved():
    """Test that multiple sequences detected at EOF are all saved."""
    # Input has two different sequences that both appear at EOF
    # Window size 2: AB appears twice, CD appears twice
    lines = ["A\n", "B\n", "A\n", "B\n", "C\n", "D\n", "C\n", "D\n"]

    saved_sequences = {}

    def save_callback(file_content: str) -> None:
        from uniqseq.library import compute_sequence_hash

        seq_hash = compute_sequence_hash(file_content)
        saved_sequences[seq_hash] = file_content

    uniqseq = UniqSeq(
        window_size=2,
        max_history=None,
        save_sequence_callback=save_callback,
    )

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should have saved both sequences
    assert len(saved_sequences) == 2

    # Verify both sequences are present
    saved_contents = list(saved_sequences.values())
    assert "A\n\nB\n" in saved_contents
    assert "C\n\nD\n" in saved_contents


@pytest.mark.unit
def test_eof_sequence_only_saved_once():
    """Test that a sequence is only saved once even if repeated at EOF."""
    # Input: ABC repeated 3 times
    lines = ["A\n", "B\n", "C\n", "A\n", "B\n", "C\n", "A\n", "B\n", "C\n"]

    save_count = {}

    def save_callback(file_content: str) -> None:
        from uniqseq.library import compute_sequence_hash

        seq_hash = compute_sequence_hash(file_content)
        save_count[seq_hash] = save_count.get(seq_hash, 0) + 1

    uniqseq = UniqSeq(
        window_size=3,
        max_history=None,
        save_sequence_callback=save_callback,
    )

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should have saved the sequence exactly once
    assert len(save_count) == 1
    seq_hash = list(save_count.keys())[0]
    assert save_count[seq_hash] == 1


@pytest.mark.unit
def test_eof_sequence_with_byte_mode():
    """Test EOF sequence saving in byte mode."""
    lines = [b"A\n", b"B\n", b"C\n", b"A\n", b"B\n", b"C\n"]

    saved_sequences = {}

    def save_callback(file_content: bytes) -> None:
        from uniqseq.library import compute_sequence_hash

        seq_hash = compute_sequence_hash(file_content)
        saved_sequences[seq_hash] = file_content

    uniqseq = UniqSeq(
        window_size=3,
        max_history=None,
        delimiter=b"\n",
        save_sequence_callback=save_callback,
    )

    output = BytesIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should have saved the sequence
    assert len(saved_sequences) == 1

    seq_hash = list(saved_sequences.keys())[0]
    seq_lines = saved_sequences[seq_hash]

    # Verify content is bytes
    assert seq_lines == b"A\n\nB\n\nC\n"
    assert isinstance(seq_lines, bytes)


@pytest.mark.unit
def test_eof_and_normal_sequences_both_saved():
    """Test that sequences detected both normally and at EOF are saved."""
    # First sequence (AB) detected normally
    # Second sequence (CD) detected at EOF
    # Window size 2
    lines = ["A\n", "B\n", "X\n", "A\n", "B\n", "C\n", "D\n", "C\n", "D\n"]

    saved_sequences = {}

    def save_callback(file_content: str) -> None:
        from uniqseq.library import compute_sequence_hash

        seq_hash = compute_sequence_hash(file_content)
        saved_sequences[seq_hash] = file_content

    uniqseq = UniqSeq(
        window_size=2,
        max_history=None,
        save_sequence_callback=save_callback,
    )

    output = StringIO()
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    # Should have saved both sequences
    assert len(saved_sequences) == 2

    saved_contents = list(saved_sequences.values())
    assert "A\n\nB\n" in saved_contents
    assert "C\n\nD\n" in saved_contents
