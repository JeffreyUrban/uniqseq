"""CLI integration tests for library functionality.

Tests the CLI with --read-sequences and --library-dir flags.
"""

import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from uniqseq.cli import app
from uniqseq.library import save_sequence_file

runner = CliRunner()


@pytest.mark.integration
def test_cli_with_read_sequences():
    """Test CLI with --read-sequences flag."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a sequences directory with a preloaded sequence
        seq_dir = Path(tmpdir) / "sequences"
        seq_dir.mkdir()

        # Save a preloaded sequence "A\nB\nC"
        save_sequence_file("A\nB\nC", seq_dir)

        # Create input file with preloaded sequence appearing TWICE (second should be skipped)
        input_file = Path(tmpdir) / "input.txt"
        input_file.write_text("A\nB\nC\nA\nB\nC\nD\nE\nF\n")

        # Run CLI
        result = runner.invoke(
            app,
            [
                str(input_file),
                "--window-size",
                "3",
                "--read-sequences",
                str(seq_dir),
            ],
        )

        assert result.exit_code == 0

        # Both ABC occurrences skipped (preloaded so treated as already seen)
        # Only DEF should be output
        output = result.stdout

        # ABC should not appear as output lines (preloaded, both occurrences skipped)
        # Check for lines with newlines to avoid matching in informational messages
        assert "A\n" not in output
        assert "B\n" not in output
        assert "C\n" not in output

        # DEF should appear as output lines
        assert "D\n" in output
        assert "E\n" in output
        assert "F\n" in output


@pytest.mark.integration
def test_cli_with_library_dir_new():
    """Test CLI with --library-dir on new library."""
    with tempfile.TemporaryDirectory() as tmpdir:
        library_dir = Path(tmpdir) / "library"

        # Create input file with duplicate sequence
        input_file = Path(tmpdir) / "input.txt"
        input_file.write_text("A\nB\nC\nA\nB\nC\nD\nE\nF\n")

        # Run CLI
        result = runner.invoke(
            app,
            [
                str(input_file),
                "--window-size",
                "3",
                "--library-dir",
                str(library_dir),
            ],
        )

        assert result.exit_code == 0

        # Check that library was created
        sequences_dir = library_dir / "sequences"
        assert sequences_dir.exists()

        # Check that sequence file was created
        sequence_files = list(sequences_dir.glob("*.uniqseq"))
        assert len(sequence_files) > 0

        # Check that metadata was created
        metadata_dirs = list(library_dir.glob("metadata-*"))
        assert len(metadata_dirs) == 1
        assert (metadata_dirs[0] / "config.json").exists()


@pytest.mark.integration
def test_cli_with_library_dir_existing():
    """Test CLI with --library-dir on existing library."""
    with tempfile.TemporaryDirectory() as tmpdir:
        library_dir = Path(tmpdir) / "library"
        seq_dir = library_dir / "sequences"
        seq_dir.mkdir(parents=True)

        # Preload a sequence
        save_sequence_file("A\nB\nC", seq_dir)

        # Create input file with preloaded sequence
        input_file = Path(tmpdir) / "input.txt"
        input_file.write_text("A\nB\nC\nD\nE\nF\n")

        # Run CLI
        result = runner.invoke(
            app,
            [
                str(input_file),
                "--window-size",
                "3",
                "--library-dir",
                str(library_dir),
            ],
        )

        assert result.exit_code == 0

        # ABC should be skipped (preloaded)
        output = result.stdout
        assert "D\n" in output
        assert "E\n" in output
        assert "F\n" in output


@pytest.mark.integration
def test_cli_with_both_read_sequences_and_library_dir():
    """Test CLI with both --read-sequences and --library-dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create read-sequences directory
        read_dir = Path(tmpdir) / "read_sequences"
        read_dir.mkdir()
        save_sequence_file("A\nB\nC", read_dir)

        # Create library directory
        library_dir = Path(tmpdir) / "library"

        # Create input file
        input_file = Path(tmpdir) / "input.txt"
        input_file.write_text("A\nB\nC\nD\nE\nF\nD\nE\nF\n")

        # Run CLI
        result = runner.invoke(
            app,
            [
                str(input_file),
                "--window-size",
                "3",
                "--read-sequences",
                str(read_dir),
                "--library-dir",
                str(library_dir),
            ],
        )

        assert result.exit_code == 0

        # ABC should be skipped (from read-sequences)
        # DEF should be detected and saved to library
        sequences_dir = library_dir / "sequences"
        sequence_files = list(sequences_dir.glob("*.uniqseq"))

        # Should have saved ABC (from read-sequences, now observed) and DEF (newly discovered)
        assert len(sequence_files) >= 2


@pytest.mark.integration
def test_cli_with_read_sequences_error():
    """Test CLI error handling when read-sequences directory has invalid file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create sequences directory with invalid UTF-8 file
        seq_dir = Path(tmpdir) / "sequences"
        seq_dir.mkdir()

        # Create invalid file
        invalid_file = seq_dir / "invalid.uniqseq"
        invalid_file.write_bytes(b"\xff\xfe\xfd")

        # Create input file
        input_file = Path(tmpdir) / "input.txt"
        input_file.write_text("A\nB\nC\n")

        # Run CLI - should fail
        result = runner.invoke(
            app,
            [
                str(input_file),
                "--window-size",
                "3",
                "--read-sequences",
                str(seq_dir),
            ],
        )

        assert result.exit_code == 1
        assert "Error loading sequences" in result.output


@pytest.mark.integration
def test_cli_with_library_dir_byte_mode():
    """Test CLI with --library-dir in byte mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        library_dir = Path(tmpdir) / "library"

        # Create binary input file
        input_file = Path(tmpdir) / "input.bin"
        input_file.write_bytes(b"A\nB\nC\nA\nB\nC\nD\nE\nF\n")

        # Run CLI in byte mode
        result = runner.invoke(
            app,
            [
                str(input_file),
                "--window-size",
                "3",
                "--byte-mode",
                "--library-dir",
                str(library_dir),
            ],
        )

        assert result.exit_code == 0

        # Check that library was created with byte sequences
        sequences_dir = library_dir / "sequences"
        assert sequences_dir.exists()

        sequence_files = list(sequences_dir.glob("*.uniqseq"))
        assert len(sequence_files) > 0

        # Verify files contain bytes
        for seq_file in sequence_files:
            content = seq_file.read_bytes()
            assert isinstance(content, bytes)
