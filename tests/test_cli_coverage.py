"""Tests to increase CLI coverage for edge cases and error paths."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import pytest


def run_uniqseq(args: list[str], input_data: Optional[str] = None) -> tuple[int, str, str]:
    """Run uniqseq CLI and return (exit_code, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, "-m", "uniqseq"] + args,
        input=input_data,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


@pytest.mark.integration
def test_json_stats_format():
    """Test JSON statistics format output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        input_file.write_text("A\nB\nC\nA\nB\nC\nD\n")

        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--window-size", "3", "--stats-format", "json"]
        )

        assert exit_code == 0
        # Stats should be in stderr for JSON format
        # May have header lines, extract JSON starting with '{'
        json_start = stderr.find("{")
        assert json_start >= 0, "No JSON found in stderr"
        json_str = stderr[json_start:]
        stats = json.loads(json_str)
        # Check for nested structure
        assert "statistics" in stats
        assert "lines" in stats["statistics"]
        assert "total" in stats["statistics"]["lines"]
        assert "skipped" in stats["statistics"]["lines"]
        assert "configuration" in stats
        assert "window_size" in stats["configuration"]


@pytest.mark.integration
def test_binary_mode_with_null_delimiter():
    """Test binary mode with null byte delimiter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.bin"
        # Write binary data with null delimiters
        input_file.write_bytes(
            b"Record1\x00Record2\x00Record3\x00Record1\x00Record2\x00Record3\x00"
        )

        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--byte-mode", "--delimiter-hex", "00", "--window-size", "3"],
        )

        assert exit_code == 0
        # Binary output should be written to stdout
        output_data = stdout.encode("latin-1")  # Preserve bytes
        assert b"Record1" in output_data or len(output_data) > 0


@pytest.mark.integration
def test_skip_chars_feature():
    """Test --skip-chars feature for timestamp removal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        # Lines with timestamps that should be skipped
        input_file.write_text(
            "2024-01-01 10:00:00 Message A\n"
            "2024-01-01 10:00:01 Message B\n"
            "2024-01-01 10:00:02 Message C\n"
            "2024-01-01 10:00:03 Message A\n"  # Duplicate after skipping timestamp
            "2024-01-01 10:00:04 Message B\n"
            "2024-01-01 10:00:05 Message C\n"
        )

        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--skip-chars", "20", "--window-size", "3"]
        )

        assert exit_code == 0
        # Should have detected the repeated sequence after skipping timestamps
        lines = stdout.strip().split("\n")
        assert len(lines) == 3  # First occurrence of A, B, C


@pytest.mark.integration
def test_hash_transform_with_command():
    """Test hash transform with a valid command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        # Input with timestamps that we'll remove via hash transform
        input_file.write_text(
            "2024-01-01 Message A\n"
            "2024-01-02 Message B\n"
            "2024-01-03 Message C\n"
            "2024-01-04 Message A\n"  # Duplicate message
            "2024-01-05 Message B\n"
            "2024-01-06 Message C\n"
        )

        # Use cut to remove first 11 characters (timestamp + space)
        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--hash-transform", "cut -c 12-", "--window-size", "3"]
        )

        assert exit_code == 0
        # Should have detected duplicate messages after transform
        lines = stdout.strip().split("\n")
        assert len(lines) == 3  # Only first occurrence of A, B, C


@pytest.mark.integration
def test_library_loading_with_invalid_utf8():
    """Test error handling when library contains invalid UTF-8 files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        lib_dir = tmpdir / "lib"
        sequences_dir = lib_dir / "sequences"
        sequences_dir.mkdir(parents=True)

        # Create a file with invalid UTF-8
        invalid_file = sequences_dir / "a1b2c3d4e5f67890a1b2c3d4e5f67890.uniqseq"
        invalid_file.write_bytes(b"\xff\xfe Invalid UTF-8 \x80\x81")

        input_file = tmpdir / "input.log"
        input_file.write_text("Line 1\nLine 2\nLine 3\n")

        # Try to use library with invalid file (text mode)
        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--library-dir", str(lib_dir), "--window-size", "3"]
        )

        # Should fail with error about loading library
        assert exit_code != 0
        assert "Error loading library" in stderr or "not UTF-8" in stderr


@pytest.mark.integration
def test_quiet_mode():
    """Test --quiet flag suppresses statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        input_file.write_text("A\nB\nC\nA\nB\nC\n")

        exit_code, stdout, stderr = run_uniqseq([str(input_file), "--window-size", "3", "--quiet"])

        assert exit_code == 0
        # No statistics table should be in stderr
        assert "Deduplication Statistics" not in stderr
        assert "Total lines processed" not in stderr


@pytest.mark.integration
def test_stdin_input():
    """Test reading from stdin."""
    input_data = "A\nB\nC\nA\nB\nC\nD\n"

    exit_code, stdout, stderr = run_uniqseq(["--window-size", "3"], input_data=input_data)

    assert exit_code == 0
    assert "A" in stdout
    assert "B" in stdout
    assert "C" in stdout
    assert "D" in stdout
    # Second occurrence should be deduplicated
    lines = stdout.strip().split("\n")
    assert len(lines) == 4  # A, B, C, D (second A, B, C removed)


@pytest.mark.integration
def test_multiple_read_sequences_directories():
    """Test loading sequences from multiple --read-sequences directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create two pattern directories
        patterns1 = tmpdir / "patterns1"
        patterns1.mkdir()
        (patterns1 / "pattern1.txt").write_text("Seq A\nSeq B\nSeq C")

        patterns2 = tmpdir / "patterns2"
        patterns2.mkdir()
        (patterns2 / "pattern2.txt").write_text("Seq X\nSeq Y\nSeq Z")

        # Create input with both patterns
        input_file = tmpdir / "input.log"
        input_file.write_text("Start\nSeq A\nSeq B\nSeq C\nMiddle\nSeq X\nSeq Y\nSeq Z\nEnd\n")

        exit_code, stdout, stderr = run_uniqseq(
            [
                str(input_file),
                "--read-sequences",
                str(patterns1),
                "--read-sequences",
                str(patterns2),
                "--window-size",
                "3",
            ]
        )

        assert exit_code == 0
        # Both patterns should be skipped (preloaded)
        output = stdout
        assert "Start" in output
        assert "Middle" in output
        assert "End" in output


@pytest.mark.integration
def test_window_size_validation():
    """Test that window size validation works."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        input_file.write_text("Line 1\nLine 2\n")

        # Window size must be >= 2
        exit_code, stdout, stderr = run_uniqseq([str(input_file), "--window-size", "1"])

        assert exit_code != 0
        assert "window-size" in stderr.lower() or "must be at least" in stderr.lower()


@pytest.mark.integration
def test_max_history_validation():
    """Test that max history validation works."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        input_file.write_text("Line 1\nLine 2\n")

        # Max history must be >= 100
        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--max-history", "50", "--window-size", "3"]
        )

        assert exit_code != 0
        assert "max-history" in stderr.lower() or "at least 100" in stderr.lower()


@pytest.mark.integration
def test_conflicting_delimiter_options():
    """Test that --delimiter and --delimiter-hex are mutually exclusive."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        input_file.write_text("Line 1\nLine 2\n")

        exit_code, stdout, stderr = run_uniqseq(
            [
                str(input_file),
                "--delimiter",
                ",",
                "--delimiter-hex",
                "0a",
                "--byte-mode",
                "--window-size",
                "3",
            ]
        )

        assert exit_code != 0
        assert "mutually exclusive" in stderr.lower()


@pytest.mark.integration
def test_delimiter_hex_requires_byte_mode():
    """Test that --delimiter-hex requires --byte-mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        input_file.write_text("Line 1\nLine 2\n")

        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--delimiter-hex", "0a", "--window-size", "3"]
        )

        assert exit_code != 0
        assert "byte-mode" in stderr.lower() or "requires" in stderr.lower()
