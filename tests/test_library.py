"""Tests for library functionality (loading, saving, metadata).

Tests the sequence library I/O functions including:
- Computing sequence hashes
- Saving sequences to files
- Loading sequences from files
- Loading sequences from directories
- Saving metadata
"""

import json
import tempfile
from pathlib import Path

import pytest

from uniqseq.library import (
    compute_sequence_hash,
    load_sequence_file,
    load_sequences_from_directory,
    save_metadata,
    save_sequence_file,
)


@pytest.mark.unit
def test_compute_sequence_hash_text_mode():
    """Test computing hash for text sequences."""
    sequence = "A\nB\nC\nD"
    delimiter = "\n"
    window_size = 4

    seq_hash = compute_sequence_hash(sequence, delimiter, window_size)

    # Hash should be 32 hex characters (blake2b digest_size=16)
    assert len(seq_hash) == 32
    assert all(c in "0123456789abcdef" for c in seq_hash)

    # Same sequence should produce same hash
    seq_hash2 = compute_sequence_hash(sequence, delimiter, window_size)
    assert seq_hash == seq_hash2

    # Different sequence should produce different hash
    different_seq = "A\nB\nC\nE"
    different_hash = compute_sequence_hash(different_seq, delimiter, window_size)
    assert seq_hash != different_hash


@pytest.mark.unit
def test_compute_sequence_hash_byte_mode():
    """Test computing hash for byte sequences."""
    sequence = b"A\nB\nC\nD"
    delimiter = b"\n"
    window_size = 4

    seq_hash = compute_sequence_hash(sequence, delimiter, window_size)

    # Hash should be 32 hex characters
    assert len(seq_hash) == 32
    assert all(c in "0123456789abcdef" for c in seq_hash)

    # Same sequence should produce same hash
    seq_hash2 = compute_sequence_hash(sequence, delimiter, window_size)
    assert seq_hash == seq_hash2


@pytest.mark.unit
def test_compute_sequence_hash_different_window_sizes():
    """Test that different window sizes produce different hashes."""
    sequence = "A\nB\nC\nD"
    delimiter = "\n"

    hash_w2 = compute_sequence_hash(sequence, delimiter, window_size=2)
    hash_w4 = compute_sequence_hash(sequence, delimiter, window_size=4)

    # Different window sizes should produce different hashes
    assert hash_w2 != hash_w4


@pytest.mark.unit
def test_save_and_load_sequence_text_mode():
    """Test saving and loading text sequences."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sequences_dir = Path(tmpdir) / "sequences"
        sequence = "A\nB\nC\nD"
        delimiter = "\n"
        window_size = 4

        # Save sequence
        file_path = save_sequence_file(
            sequence, delimiter, sequences_dir, window_size, byte_mode=False
        )

        # Check file was created
        assert file_path.exists()
        assert file_path.suffix == ".uniqseq"

        # Load sequence back
        loaded_sequence = load_sequence_file(file_path, delimiter, byte_mode=False)

        # Should match original
        assert loaded_sequence == sequence


@pytest.mark.unit
def test_save_and_load_sequence_byte_mode():
    """Test saving and loading byte sequences."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sequences_dir = Path(tmpdir) / "sequences"
        sequence = b"A\nB\nC\nD"
        delimiter = b"\n"
        window_size = 4

        # Save sequence
        file_path = save_sequence_file(
            sequence, delimiter, sequences_dir, window_size, byte_mode=True
        )

        # Check file was created
        assert file_path.exists()
        assert file_path.suffix == ".uniqseq"

        # Load sequence back
        loaded_sequence = load_sequence_file(file_path, delimiter, byte_mode=True)

        # Should match original
        assert loaded_sequence == sequence


@pytest.mark.unit
def test_save_sequence_creates_directory():
    """Test that save_sequence_file creates directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sequences_dir = Path(tmpdir) / "new_dir" / "sequences"
        sequence = "A\nB\nC"
        delimiter = "\n"
        window_size = 3

        # Directory shouldn't exist yet
        assert not sequences_dir.exists()

        # Save sequence
        file_path = save_sequence_file(sequence, delimiter, sequences_dir, window_size)

        # Directory should now exist
        assert sequences_dir.exists()
        assert file_path.exists()


@pytest.mark.unit
def test_load_sequence_file_not_utf8():
    """Test that loading non-UTF8 file in text mode raises ValueError."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a file with non-UTF8 content
        file_path = Path(tmpdir) / "test.uniqseq"
        file_path.write_bytes(b"\xff\xfe\xfd")

        # Should raise ValueError when trying to load in text mode
        with pytest.raises(ValueError, match="Cannot read sequence file.*not UTF-8"):
            load_sequence_file(file_path, "\n", byte_mode=False)


@pytest.mark.unit
def test_load_sequences_from_directory_text_mode():
    """Test loading multiple sequences from a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sequences_dir = Path(tmpdir) / "sequences"
        sequences_dir.mkdir(parents=True)

        delimiter = "\n"
        window_size = 3

        # Create some sequence files
        seq1 = "A\nB\nC"
        seq2 = "X\nY\nZ"

        save_sequence_file(seq1, delimiter, sequences_dir, window_size)
        save_sequence_file(seq2, delimiter, sequences_dir, window_size)

        # Load all sequences
        sequences = load_sequences_from_directory(
            sequences_dir, delimiter, window_size, byte_mode=False
        )

        # Should have 2 sequences
        assert len(sequences) == 2

        # Sequences should be present (order doesn't matter)
        assert seq1 in sequences.values()
        assert seq2 in sequences.values()


@pytest.mark.unit
def test_load_sequences_from_directory_byte_mode():
    """Test loading byte sequences from a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sequences_dir = Path(tmpdir) / "sequences"
        sequences_dir.mkdir(parents=True)

        delimiter = b"\n"
        window_size = 3

        # Create some sequence files
        seq1 = b"A\nB\nC"
        seq2 = b"X\nY\nZ"

        save_sequence_file(seq1, delimiter, sequences_dir, window_size, byte_mode=True)
        save_sequence_file(seq2, delimiter, sequences_dir, window_size, byte_mode=True)

        # Load all sequences
        sequences = load_sequences_from_directory(
            sequences_dir, delimiter, window_size, byte_mode=True
        )

        # Should have 2 sequences
        assert len(sequences) == 2

        # Sequences should be present
        assert seq1 in sequences.values()
        assert seq2 in sequences.values()


@pytest.mark.unit
def test_load_sequences_from_directory_skips_noise_files():
    """Test that noise files (.DS_Store, README.md, etc.) are skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sequences_dir = Path(tmpdir) / "sequences"
        sequences_dir.mkdir(parents=True)

        delimiter = "\n"
        window_size = 3

        # Create a valid sequence
        seq1 = "A\nB\nC"
        save_sequence_file(seq1, delimiter, sequences_dir, window_size)

        # Create noise files
        (sequences_dir / ".DS_Store").write_text("noise")
        (sequences_dir / "README.md").write_text("# README")
        (sequences_dir / ".gitignore").write_text("*.tmp")

        # Load sequences
        sequences = load_sequences_from_directory(sequences_dir, delimiter, window_size)

        # Should only have 1 sequence (noise files skipped)
        assert len(sequences) == 1
        assert seq1 in sequences.values()


@pytest.mark.unit
def test_load_sequences_from_directory_skips_subdirectories():
    """Test that subdirectories are skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sequences_dir = Path(tmpdir) / "sequences"
        sequences_dir.mkdir(parents=True)

        delimiter = "\n"
        window_size = 3

        # Create a valid sequence
        seq1 = "A\nB\nC"
        save_sequence_file(seq1, delimiter, sequences_dir, window_size)

        # Create a subdirectory
        subdir = sequences_dir / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("content")

        # Load sequences
        sequences = load_sequences_from_directory(sequences_dir, delimiter, window_size)

        # Should only have 1 sequence (subdirectory skipped)
        assert len(sequences) == 1


@pytest.mark.unit
def test_load_sequences_from_nonexistent_directory():
    """Test loading from nonexistent directory returns empty dict."""
    nonexistent = Path("/nonexistent/path/sequences")
    sequences = load_sequences_from_directory(nonexistent, "\n", window_size=3)

    assert sequences == {}


@pytest.mark.unit
def test_load_sequences_renames_mismatched_files():
    """Test that .uniqseq files with wrong hash are renamed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sequences_dir = Path(tmpdir) / "sequences"
        sequences_dir.mkdir(parents=True)

        delimiter = "\n"
        window_size = 3

        # Create sequence with correct hash
        seq1 = "A\nB\nC"
        correct_path = save_sequence_file(seq1, delimiter, sequences_dir, window_size)
        correct_hash = correct_path.stem

        # Rename it to have wrong hash
        wrong_hash = "wronghash1234"
        wrong_path = sequences_dir / f"{wrong_hash}.uniqseq"
        correct_path.rename(wrong_path)

        # Load sequences
        sequences = load_sequences_from_directory(sequences_dir, delimiter, window_size)

        # Should have loaded the sequence
        assert len(sequences) == 1
        assert seq1 in sequences.values()

        # File should have been renamed back to correct hash
        assert not wrong_path.exists()
        assert (sequences_dir / f"{correct_hash}.uniqseq").exists()


@pytest.mark.unit
def test_save_metadata():
    """Test saving metadata file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        library_dir = Path(tmpdir) / "library"

        metadata_path = save_metadata(
            library_dir=library_dir,
            window_size=4,
            max_history=1000,
            delimiter="\n",
            byte_mode=False,
            sequences_discovered=50,
            sequences_preloaded=20,
            sequences_saved=70,
            total_records_processed=10000,
            records_skipped=5000,
        )

        # Check metadata file was created
        assert metadata_path.exists()
        assert metadata_path.name == "config.json"

        # Check it's in a timestamped directory
        assert metadata_path.parent.name.startswith("metadata-")

        # Load and verify metadata
        metadata = json.loads(metadata_path.read_text())

        assert metadata["window_size"] == 4
        assert metadata["max_history"] == 1000
        assert metadata["mode"] == "text"
        assert metadata["delimiter"] == "\\n"
        assert metadata["sequences_discovered"] == 50
        assert metadata["sequences_preloaded"] == 20
        assert metadata["sequences_saved"] == 70
        assert metadata["total_records_processed"] == 10000
        assert metadata["records_skipped"] == 5000
        assert "timestamp" in metadata


@pytest.mark.unit
def test_save_metadata_byte_mode():
    """Test saving metadata in byte mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        library_dir = Path(tmpdir) / "library"

        metadata_path = save_metadata(
            library_dir=library_dir,
            window_size=3,
            max_history=None,
            delimiter=b"\n",
            byte_mode=True,
            sequences_discovered=10,
            sequences_preloaded=5,
            sequences_saved=15,
            total_records_processed=1000,
            records_skipped=500,
        )

        # Load and verify metadata
        metadata = json.loads(metadata_path.read_text())

        assert metadata["mode"] == "binary"
        # Delimiter in hex format
        assert metadata["delimiter"] == "0a"  # \n in hex
        assert metadata["max_history"] == "unlimited"


@pytest.mark.unit
def test_load_sequences_from_directory_with_invalid_utf8_file():
    """Test that loading directory with non-UTF8 file raises helpful error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        sequences_dir = Path(tmpdir) / "sequences"
        sequences_dir.mkdir(parents=True)

        # Create a file with non-UTF8 content
        invalid_file = sequences_dir / "invalid.uniqseq"
        invalid_file.write_bytes(b"\xff\xfe\xfd")

        # Should raise ValueError with helpful message
        with pytest.raises(ValueError, match="Error loading sequence from.*not UTF-8"):
            load_sequences_from_directory(sequences_dir, "\n", window_size=3, byte_mode=False)


@pytest.mark.unit
def test_save_metadata_special_delimiters():
    """Test saving metadata with special delimiter characters."""
    with tempfile.TemporaryDirectory() as tmpdir:
        library_dir = Path(tmpdir) / "library"

        # Test tab delimiter
        metadata_path = save_metadata(
            library_dir=library_dir,
            window_size=3,
            max_history=100,
            delimiter="\t",
            byte_mode=False,
            sequences_discovered=1,
            sequences_preloaded=1,
            sequences_saved=2,
            total_records_processed=100,
            records_skipped=50,
        )

        metadata = json.loads(metadata_path.read_text())
        assert metadata["delimiter"] == "\\t"

        # Test null delimiter
        metadata_path2 = save_metadata(
            library_dir=library_dir,
            window_size=3,
            max_history=100,
            delimiter="\0",
            byte_mode=False,
            sequences_discovered=1,
            sequences_preloaded=1,
            sequences_saved=2,
            total_records_processed=100,
            records_skipped=50,
        )

        metadata2 = json.loads(metadata_path2.read_text())
        assert metadata2["delimiter"] == "\\0"
