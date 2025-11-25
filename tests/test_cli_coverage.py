"""Tests to increase CLI coverage for edge cases and error paths."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import pytest
from typer.testing import CliRunner, Result

from uniqseq.cli import app

# Ensure consistent terminal width
os.environ.setdefault("COLUMNS", "120")

# Initialize CliRunner for unit tests
runner = CliRunner()

# Environment variables for consistent test output
TEST_ENV = {
    "COLUMNS": "120",
    "NO_COLOR": "1",
}

# ANSI escape code pattern
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_ESCAPE.sub("", text)


def get_stderr(result: Result) -> str:
    """Get stderr from CliRunner result, handling Click version differences.

    Click 8.2+ captures stderr separately by default.
    Click 8.1.x requires accessing result.output (mixed stdout+stderr).
    """
    try:
        return result.stderr
    except ValueError:
        # Click 8.1.x: stderr not separately captured, use output
        return result.output


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

        # Window size must be >= 1 (test with 0)
        exit_code, stdout, stderr = run_uniqseq([str(input_file), "--window-size", "0"])
        assert exit_code != 0
        # Check for range validation error (ANSI codes may break up flag names)
        assert "not in the range" in stderr.lower() or "invalid value" in stderr.lower()

        # Window size must be positive (test with negative)
        exit_code, stdout, stderr = run_uniqseq([str(input_file), "--window-size", "-1"])
        assert exit_code != 0
        assert "not in the range" in stderr.lower() or "invalid value" in stderr.lower()

        # Window size must be an integer (test with non-integer)
        exit_code, stdout, stderr = run_uniqseq([str(input_file), "--window-size", "abc"])
        assert exit_code != 0
        assert "invalid" in stderr.lower() or "integer" in stderr.lower()


@pytest.mark.integration
def test_max_history_validation():
    """Test that max history validation works."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        input_file.write_text("Line 1\nLine 2\n")

        # Max history must be >= 0 (negative values are invalid)
        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--max-history", "-1", "--window-size", "3"]
        )

        assert exit_code != 0
        assert "not in the range" in stderr.lower() or "invalid value" in stderr.lower()


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


@pytest.mark.integration
def test_track_flag_allowlist_mode():
    """Test --track flag creates allowlist mode (only tracked lines deduplicated)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        # Mix of ERROR and INFO lines with duplicates
        input_file.write_text(
            "ERROR: Failed to connect\n"
            "INFO: Starting process\n"
            "ERROR: Timeout occurred\n"
            "INFO: Processing data\n"
            "ERROR: Failed to connect\n"  # Duplicate ERROR
            "ERROR: Timeout occurred\n"  # Duplicate ERROR
            "INFO: Starting process\n"  # Duplicate INFO (should pass through)
            "INFO: Processing data\n"  # Duplicate INFO (should pass through)
        )

        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--track", "^ERROR", "--window-size", "2"]
        )

        assert exit_code == 0
        result_lines = stdout.strip().split("\n")

        # First two ERROR lines should be kept, duplicates removed
        # All INFO lines should pass through (not tracked)
        assert "ERROR: Failed to connect" in result_lines
        assert "ERROR: Timeout occurred" in result_lines
        assert result_lines.count("INFO: Starting process") == 2  # Both pass through
        assert result_lines.count("INFO: Processing data") == 2  # Both pass through
        assert result_lines.count("ERROR: Failed to connect") == 1  # Dedup
        assert result_lines.count("ERROR: Timeout occurred") == 1  # Dedup


@pytest.mark.integration
def test_bypass_flag_passthrough():
    """Test --bypass flag passes through matching lines unchanged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        # Mix of ERROR and INFO lines with duplicates
        input_file.write_text(
            "ERROR: Failed to connect\n"
            "INFO: Starting process\n"
            "ERROR: Timeout occurred\n"
            "INFO: Processing data\n"
            "ERROR: Failed to connect\n"  # Duplicate ERROR (should be deduped)
            "ERROR: Timeout occurred\n"  # Duplicate ERROR (should be deduped)
            "INFO: Starting process\n"  # Duplicate INFO (should pass through)
            "INFO: Processing data\n"  # Duplicate INFO (should pass through)
        )

        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--bypass", "^INFO", "--window-size", "2"]
        )

        assert exit_code == 0
        result_lines = stdout.strip().split("\n")

        # INFO lines should all pass through (bypassed from uniqseq)
        assert result_lines.count("INFO: Starting process") == 2
        assert result_lines.count("INFO: Processing data") == 2
        # ERROR lines should be deduplicated
        assert result_lines.count("ERROR: Failed to connect") == 1
        assert result_lines.count("ERROR: Timeout occurred") == 1


@pytest.mark.integration
def test_track_and_bypass_sequential_evaluation():
    """Test --track and --bypass together with sequential evaluation (first match wins)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        input_file.write_text(
            "ERROR: Critical failure\n"  # 1 (tracked)
            "ERROR: Database error\n"  # 2 (tracked)
            "INFO: Started\n"  # 3 (bypassed - passes through)
            "WARN: Something odd\n"  # 4 (not matched - passes through, allowlist mode)
            "ERROR: Critical failure\n"  # 5 (tracked - sequence duplicate!)
            "ERROR: Database error\n"  # 6 (tracked - sequence duplicate!)
            "INFO: Processing\n"  # 7 (bypassed - passes through)
        )

        # Track CRITICAL and Database errors, bypass INFO
        exit_code, stdout, stderr = run_uniqseq(
            [
                str(input_file),
                "--track",
                "Critical|Database",
                "--bypass",
                "^INFO",
                "--window-size",
                "2",
            ]
        )

        assert exit_code == 0
        result_lines = stdout.strip().split("\n")

        # First two ERROR lines should be kept, sequence duplicate removed
        assert result_lines.count("ERROR: Critical failure") == 1
        assert result_lines.count("ERROR: Database error") == 1
        # INFO lines should pass through (bypassed)
        assert result_lines.count("INFO: Started") == 1
        assert result_lines.count("INFO: Processing") == 1
        # WARN should pass through (allowlist mode - not tracked)
        assert result_lines.count("WARN: Something odd") == 1
        # Total: 5 lines (2 ERROR + 2 INFO + 1 WARN, duplicate ERROR sequence removed)
        assert len(result_lines) == 5


@pytest.mark.integration
def test_track_bypass_ordering_preserved():
    """Test that input ordering is preserved with interleaved tracked/bypassed lines."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        input_file.write_text(
            "ERROR: Failed\n"  # 1 (track)
            "INFO: Start\n"  # 2 (pass through - allowlist mode)
            "ERROR: Timeout\n"  # 3 (track)
            "INFO: Process\n"  # 4 (pass through - allowlist mode)
            "ERROR: Failed\n"  # 5 (track - sequence duplicate)
            "ERROR: Timeout\n"  # 6 (track - sequence duplicate)
            "INFO: Done\n"  # 7 (pass through - allowlist mode)
        )

        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--track", "ERROR", "--window-size", "2"]
        )

        assert exit_code == 0
        result_lines = stdout.strip().split("\n")

        # Check ordering is preserved and duplicates removed
        assert result_lines[0] == "ERROR: Failed"
        assert result_lines[1] == "INFO: Start"
        assert result_lines[2] == "ERROR: Timeout"
        assert result_lines[3] == "INFO: Process"
        # Lines 5 and 6 form duplicate sequence (skipped)
        assert result_lines[4] == "INFO: Done"
        assert len(result_lines) == 5


@pytest.mark.integration
def test_track_invalid_regex_error():
    """Test that invalid regex in --track produces clear error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        input_file.write_text("Line 1\nLine 2\n")

        # Invalid regex: unclosed bracket
        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--track", "[invalid", "--window-size", "2"]
        )

        assert exit_code != 0
        assert "invalid" in stderr.lower() or "error" in stderr.lower()
        assert "track" in stderr.lower()


@pytest.mark.integration
def test_bypass_invalid_regex_error():
    """Test that invalid regex in --bypass produces clear error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        input_file.write_text("Line 1\nLine 2\n")

        # Invalid regex: unclosed group
        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--bypass", "(unclosed", "--window-size", "2"]
        )

        assert exit_code != 0
        assert "invalid" in stderr.lower() or "error" in stderr.lower()
        assert "bypass" in stderr.lower()


@pytest.mark.integration
def test_filter_patterns_incompatible_with_byte_mode():
    """Test that filter patterns (--track, --bypass) are incompatible with --byte-mode."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_file = tmpdir / "input.log"
        input_file.write_text("Line 1\nLine 2\n")

        # Test --track with byte mode
        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--track", "pattern", "--byte-mode", "--window-size", "2"]
        )

        assert exit_code != 0
        assert "byte-mode" in stderr.lower() or "incompatible" in stderr.lower()

        # Test --bypass with byte mode
        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--bypass", "pattern", "--byte-mode", "--window-size", "2"]
        )

        assert exit_code != 0
        assert "byte-mode" in stderr.lower() or "incompatible" in stderr.lower()


@pytest.mark.integration
def test_track_file_loads_patterns(tmp_path):
    """Test --track-file loads patterns from file."""
    # Create pattern file
    pattern_file = tmp_path / "track_patterns.txt"
    pattern_file.write_text("# Track patterns\nERROR\nCRITICAL\n\n# Comment\nFATAL\n")

    # Create input with mixed lines
    input_file = tmp_path / "input.txt"
    input_file.write_text(
        "ERROR: Failed\n"
        "INFO: Message\n"
        "CRITICAL: Issue\n"
        "DEBUG: Detail\n"
        "FATAL: Crash\n"
        "ERROR: Failed\n"  # Duplicate
        "CRITICAL: Issue\n"  # Duplicate
    )

    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--track-file", str(pattern_file), "--window-size", "2"]
    )

    assert exit_code == 0
    result_lines = stdout.strip().split("\n")

    # ERROR, CRITICAL, FATAL should be tracked (deduplicated)
    assert result_lines.count("ERROR: Failed") == 1
    assert result_lines.count("CRITICAL: Issue") == 1
    assert result_lines.count("FATAL: Crash") == 1

    # INFO and DEBUG should pass through (not tracked)
    assert "INFO: Message" in result_lines
    assert "DEBUG: Detail" in result_lines


@pytest.mark.integration
def test_bypass_file_loads_patterns(tmp_path):
    """Test --bypass-file loads patterns from file."""
    # Create pattern file
    pattern_file = tmp_path / "bypass_patterns.txt"
    pattern_file.write_text("# Bypass patterns\nDEBUG\nTRACE\n")

    # Create input with repeating sequences
    input_file = tmp_path / "input.txt"
    input_file.write_text(
        "DEBUG: Detail 1\n"
        "TRACE: Info\n"
        "ERROR: Failed\n"
        "ERROR: Timeout\n"
        "DEBUG: Detail 1\n"  # Bypass (not deduplicated)
        "TRACE: Info\n"  # Bypass (not deduplicated)
        "ERROR: Failed\n"  # Duplicate sequence
        "ERROR: Timeout\n"  # Duplicate sequence
    )

    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--bypass-file", str(pattern_file), "--window-size", "2"]
    )

    assert exit_code == 0
    result_lines = stdout.strip().split("\n")

    # DEBUG and TRACE should bypass (all occurrences output)
    assert result_lines.count("DEBUG: Detail 1") == 2
    assert result_lines.count("TRACE: Info") == 2

    # ERROR lines should be deduplicated
    assert result_lines.count("ERROR: Failed") == 1
    assert result_lines.count("ERROR: Timeout") == 1


@pytest.mark.integration
def test_pattern_file_with_invalid_regex(tmp_path):
    """Test pattern file with invalid regex produces error."""
    # Create pattern file with invalid regex
    pattern_file = tmp_path / "bad_patterns.txt"
    pattern_file.write_text("ERROR\n[unclosed\n")

    input_file = tmp_path / "input.txt"
    input_file.write_text("ERROR: Test\n")

    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--track-file", str(pattern_file), "--window-size", "2"]
    )

    assert exit_code != 0
    assert "invalid" in stderr.lower() or "error" in stderr.lower()
    assert "[unclosed" in stderr


@pytest.mark.integration
def test_multiple_pattern_files(tmp_path):
    """Test multiple pattern files are loaded in order."""
    # Create two pattern files
    file1 = tmp_path / "patterns1.txt"
    file1.write_text("ERROR\n")

    file2 = tmp_path / "patterns2.txt"
    file2.write_text("CRITICAL\n")

    # Create input
    input_file = tmp_path / "input.txt"
    input_file.write_text(
        "ERROR: Msg\n"
        "CRITICAL: Msg\n"
        "INFO: Msg\n"
        "ERROR: Msg\n"  # Duplicate
        "CRITICAL: Msg\n"  # Duplicate
    )

    exit_code, stdout, stderr = run_uniqseq(
        [
            str(input_file),
            "--track-file",
            str(file1),
            "--track-file",
            str(file2),
            "--window-size",
            "2",
        ]
    )

    assert exit_code == 0
    result_lines = stdout.strip().split("\n")

    # ERROR and CRITICAL tracked (deduplicated)
    assert result_lines.count("ERROR: Msg") == 1
    assert result_lines.count("CRITICAL: Msg") == 1

    # INFO not tracked (passes through)
    assert "INFO: Msg" in result_lines


@pytest.mark.integration
def test_mixed_inline_and_file_patterns(tmp_path):
    """Test mixing inline patterns with file patterns."""
    # Create pattern file
    pattern_file = tmp_path / "patterns.txt"
    pattern_file.write_text("WARN\n")

    # Create input
    input_file = tmp_path / "input.txt"
    input_file.write_text(
        "ERROR: Msg\n"
        "WARN: Msg\n"
        "CRITICAL: Msg\n"
        "INFO: Msg\n"
        "ERROR: Msg\n"  # Duplicate
        "WARN: Msg\n"  # Duplicate
        "CRITICAL: Msg\n"  # Duplicate
    )

    # Inline ERROR, file WARN, inline CRITICAL
    exit_code, stdout, stderr = run_uniqseq(
        [
            str(input_file),
            "--track",
            "ERROR",
            "--track-file",
            str(pattern_file),
            "--track",
            "CRITICAL",
            "--window-size",
            "2",
        ]
    )

    assert exit_code == 0
    result_lines = stdout.strip().split("\n")

    # All tracked patterns deduplicated
    assert result_lines.count("ERROR: Msg") == 1
    assert result_lines.count("WARN: Msg") == 1
    assert result_lines.count("CRITICAL: Msg") == 1

    # INFO not tracked
    assert "INFO: Msg" in result_lines


@pytest.mark.integration
def test_pattern_file_empty(tmp_path):
    """Test pattern file that's empty (only comments/blanks)."""
    # Create empty pattern file (only comments)
    pattern_file = tmp_path / "empty_patterns.txt"
    pattern_file.write_text("# Just comments\n\n# More comments\n")

    input_file = tmp_path / "input.txt"
    input_file.write_text("Line 1\nLine 2\nLine 1\nLine 2\n")

    # Empty pattern file should work but have no effect
    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--track-file", str(pattern_file), "--window-size", "2"]
    )

    assert exit_code == 0
    # Should deduplicate normally since no patterns matched
    result_lines = stdout.strip().split("\n")
    assert len(result_lines) == 2  # First occurrence of the 2-line sequence


@pytest.mark.integration
def test_inverse_mode_cli(tmp_path):
    """Test --inverse flag via CLI."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\nA\nB\nC\nD\n")

    exit_code, stdout, stderr = run_uniqseq([str(input_file), "--window-size", "3", "--inverse"])

    assert exit_code == 0
    result_lines = stdout.strip().split("\n")

    # Inverse mode: only output duplicate sequence (second A-B-C)
    assert len(result_lines) == 3
    assert result_lines == ["A", "B", "C"]


@pytest.mark.integration
def test_inverse_mode_no_duplicates(tmp_path):
    """Test --inverse with no duplicates outputs nothing."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\nD\nE\n")

    exit_code, stdout, stderr = run_uniqseq([str(input_file), "--window-size", "3", "--inverse"])

    assert exit_code == 0
    assert stdout == ""  # No duplicates, so no output


@pytest.mark.integration
def test_annotate_flag_cli(tmp_path):
    """Test --annotate flag via CLI."""
    input_file = tmp_path / "input.txt"
    # Create 10-line sequences with duplicate
    lines = []
    for i in range(10):
        lines.append(f"line-{i}")
    for i in range(5):
        lines.append(f"other-{i}")
    for i in range(10):
        lines.append(f"line-{i}")  # Duplicate
    input_file.write_text("\n".join(lines) + "\n")

    exit_code, stdout, stderr = run_uniqseq([str(input_file), "--window-size", "10", "--annotate"])

    assert exit_code == 0
    assert "[DUPLICATE:" in stdout
    assert "matched lines" in stdout
    assert "sequence seen" in stdout


@pytest.mark.integration
def test_annotate_with_quiet(tmp_path):
    """Test --annotate with --quiet (annotations should still appear)."""
    input_file = tmp_path / "input.txt"
    lines = []
    for i in range(10):
        lines.append(f"line-{i}")
    for i in range(10):
        lines.append(f"line-{i}")  # Duplicate
    input_file.write_text("\n".join(lines) + "\n")

    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--window-size", "10", "--annotate", "--quiet"]
    )

    assert exit_code == 0
    # Annotations are part of data output, not stats, so they should appear even with --quiet
    assert "[DUPLICATE:" in stdout


@pytest.mark.integration
def test_annotation_format_cli(tmp_path):
    """Test --annotation-format flag via CLI."""
    input_file = tmp_path / "input.txt"
    lines = []
    for i in range(10):
        lines.append(f"line-{i}")
    for i in range(10):
        lines.append(f"line-{i}")  # Duplicate
    input_file.write_text("\n".join(lines) + "\n")

    exit_code, stdout, stderr = run_uniqseq(
        [
            str(input_file),
            "--window-size",
            "10",
            "--annotate",
            "--annotation-format",
            "SKIP|{start}|{end}|{count}",
        ]
    )

    assert exit_code == 0
    assert "SKIP|" in stdout
    assert "|2" in stdout  # count=2
    # Should NOT contain default format
    assert "[DUPLICATE:" not in stdout


@pytest.mark.integration
def test_annotation_format_requires_annotate(tmp_path):
    """Test that --annotation-format requires --annotate."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--annotation-format", "SKIP|{start}|{end}"]
    )

    # Should fail with validation error
    assert exit_code != 0  # Non-zero exit code for error
    # Strip ANSI codes for reliable matching
    assert "--annotation-format requires --annotate" in strip_ansi(stderr)


@pytest.mark.integration
def test_pattern_file_not_found(tmp_path):
    """Test pattern file that doesn't exist."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    # Non-existent pattern file
    pattern_file = tmp_path / "nonexistent.txt"

    exit_code, stdout, stderr = run_uniqseq([str(input_file), "--track-file", str(pattern_file)])

    # Should fail with file error (typer validates file exists)
    assert exit_code != 0
    assert "does not exist" in stderr


@pytest.mark.integration
def test_pattern_file_permission_denied(tmp_path):
    """Test pattern file with no read permission."""
    import os
    import stat

    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    # Create pattern file with no read permission
    pattern_file = tmp_path / "no_read.txt"
    pattern_file.write_text("A\n")
    os.chmod(pattern_file, stat.S_IWUSR)  # Write-only, no read

    try:
        exit_code, stdout, stderr = run_uniqseq(
            [str(input_file), "--track-file", str(pattern_file)]
        )

        # Should fail with permission error (typer validates file is readable)
        assert exit_code != 0
        assert "not readable" in stderr
    finally:
        # Restore permissions for cleanup
        os.chmod(pattern_file, stat.S_IRUSR | stat.S_IWUSR)


@pytest.mark.integration
def test_track_file_invalid_regex(tmp_path):
    """Test track file with invalid regex pattern."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    # Create pattern file with invalid regex
    pattern_file = tmp_path / "bad_patterns.txt"
    pattern_file.write_text("[unclosed\n")

    exit_code, stdout, stderr = run_uniqseq([str(input_file), "--track-file", str(pattern_file)])

    # Should fail with regex error
    assert exit_code != 0
    assert "Invalid track pattern" in stderr
    # Filename may be wrapped with newlines in rich console output
    assert ".txt" in stderr  # Check file extension is mentioned


@pytest.mark.integration
def test_bypass_file_invalid_regex(tmp_path):
    """Test bypass file with invalid regex pattern."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    # Create pattern file with invalid regex
    pattern_file = tmp_path / "bad_patterns.txt"
    pattern_file.write_text("*invalid\n")

    exit_code, stdout, stderr = run_uniqseq([str(input_file), "--bypass-file", str(pattern_file)])

    # Should fail with regex error
    assert exit_code != 0
    assert "Invalid bypass pattern" in stderr
    # Filename may be wrapped with newlines in rich console output
    assert ".txt" in stderr  # Check file extension is mentioned


@pytest.mark.integration
def test_hash_transform_timeout(tmp_path):
    """Test hash transform command that times out."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    # Command that will sleep longer than timeout
    exit_code, stdout, stderr = run_uniqseq([str(input_file), "--hash-transform", "sleep 10"])

    # Should fail with timeout error
    assert exit_code != 0
    assert "timed out" in stderr.lower()


@pytest.mark.integration
def test_hash_transform_embedded_delimiter(tmp_path):
    """Test hash transform that outputs embedded delimiters."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    # Command that echoes multiple lines (creates embedded newline)
    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--hash-transform", "printf 'line1\\nline2'"]
    )

    # Should fail with multiple lines error
    assert exit_code != 0
    assert "multiple lines" in stderr.lower()


@pytest.mark.integration
def test_hash_transform_with_empty_file(tmp_path):
    """Test hash transform with empty input file."""
    input_file = tmp_path / "empty.txt"
    input_file.write_text("")

    exit_code, stdout, stderr = run_uniqseq([str(input_file), "--hash-transform", "tr 'a-z' 'A-Z'"])

    # Should succeed with no output
    assert exit_code == 0
    assert stdout == ""


@pytest.mark.integration
def test_hash_transform_case_insensitive_dedup(tmp_path):
    """Test hash transform for case-insensitive deduplication."""
    input_file = tmp_path / "input.txt"
    # Same words different cases - should deduplicate when case-normalized
    input_file.write_text("Hello\nWorld\nhello\nworld\n")

    # Transform to lowercase for hashing, but preserve original output
    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--hash-transform", "tr 'A-Z' 'a-z'", "--window-size", "2"]
    )

    assert exit_code == 0
    # First 2 lines (Hello, World) unique, next 2 (hello, world) are duplicates
    lines = [l for l in stdout.split("\n") if l]
    # Original case preserved in output
    assert lines[0] == "Hello"
    assert lines[1] == "World"
    assert len(lines) == 2  # hello, world were duplicates and skipped


# Unit tests using CliRunner (not subprocess) for coverage
@pytest.mark.unit
def test_track_inline_pattern_unit(tmp_path):
    """Test --track inline pattern via CliRunner for coverage."""
    input_file = tmp_path / "input.txt"
    # Need 2-line sequences
    input_file.write_text("ERROR: A\nERROR: B\nINFO: C\nINFO: D\nERROR: A\nERROR: B\n")

    result = runner.invoke(
        app, [str(input_file), "--track", "^ERROR", "--window-size", "2", "--quiet"], env=TEST_ENV
    )

    assert result.exit_code == 0
    # First ERROR sequence unique, second is duplicate
    # INFO lines pass through (not tracked)
    assert "ERROR: A" in result.stdout
    assert "ERROR: B" in result.stdout
    assert result.stdout.count("ERROR: A") == 1  # Second occurrence skipped


@pytest.mark.unit
def test_bypass_inline_pattern_unit(tmp_path):
    """Test --bypass inline pattern via CliRunner for coverage."""
    input_file = tmp_path / "input.txt"
    # DEBUG bypasses dedup, INFO gets deduplicated
    input_file.write_text(
        "DEBUG: A\nDEBUG: B\nINFO: C\nINFO: D\nDEBUG: A\nDEBUG: B\nINFO: C\nINFO: D\n"
    )

    result = runner.invoke(
        app, [str(input_file), "--bypass", "^DEBUG", "--window-size", "2", "--quiet"], env=TEST_ENV
    )

    assert result.exit_code == 0
    # DEBUG lines bypass dedup, both sequences appear
    assert result.stdout.count("DEBUG: A") == 2
    # INFO lines get deduplicated
    assert result.stdout.count("INFO: C") == 1


@pytest.mark.unit
def test_track_file_pattern_unit(tmp_path):
    """Test --track-file via CliRunner for coverage."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("ERROR: A\nERROR: B\nINFO: C\nINFO: D\nERROR: A\nERROR: B\n")

    pattern_file = tmp_path / "patterns.txt"
    pattern_file.write_text("^ERROR\n")

    result = runner.invoke(
        app,
        [str(input_file), "--track-file", str(pattern_file), "--window-size", "2", "--quiet"],
        env=TEST_ENV,
    )

    assert result.exit_code == 0
    assert result.stdout.count("ERROR: A") == 1  # Deduplicated


@pytest.mark.unit
def test_bypass_file_pattern_unit(tmp_path):
    """Test --bypass-file via CliRunner for coverage."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("DEBUG: A\nDEBUG: B\nINFO: C\nINFO: D\nDEBUG: A\nDEBUG: B\n")

    pattern_file = tmp_path / "patterns.txt"
    pattern_file.write_text("^DEBUG\n")

    result = runner.invoke(
        app,
        [str(input_file), "--bypass-file", str(pattern_file), "--window-size", "2", "--quiet"],
        env=TEST_ENV,
    )

    assert result.exit_code == 0
    assert result.stdout.count("DEBUG: A") == 2  # Bypassed dedup


@pytest.mark.unit
def test_filters_with_byte_mode_error(tmp_path):
    """Test that filters with byte mode produces error."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    result = runner.invoke(app, [str(input_file), "--track", "A", "--byte-mode"], env=TEST_ENV)

    assert result.exit_code != 0
    stderr = get_stderr(result)
    assert "text mode" in stderr.lower() or "byte mode" in stderr.lower()


@pytest.mark.unit
def test_annotation_format_requires_annotate_unit(tmp_path):
    """Test --annotation-format requires --annotate via CliRunner for coverage."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    result = runner.invoke(
        app, [str(input_file), "--annotation-format", "SKIP|{count}"], env=TEST_ENV
    )

    assert result.exit_code != 0
    # Strip ANSI codes for reliable matching
    stderr = get_stderr(result)
    assert "--annotation-format requires --annotate" in strip_ansi(stderr)


@pytest.mark.unit
def test_track_invalid_regex_unit(tmp_path):
    """Test --track with invalid regex via CliRunner for coverage."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    result = runner.invoke(app, [str(input_file), "--track", "[unclosed"], env=TEST_ENV)

    assert result.exit_code != 0
    stderr = get_stderr(result)
    assert "Invalid track pattern" in stderr


@pytest.mark.unit
def test_bypass_invalid_regex_unit(tmp_path):
    """Test --bypass with invalid regex via CliRunner for coverage."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    result = runner.invoke(app, [str(input_file), "--bypass", "*invalid"], env=TEST_ENV)

    assert result.exit_code != 0
    stderr = get_stderr(result)
    assert "Invalid bypass pattern" in stderr


@pytest.mark.unit
def test_track_file_invalid_regex_unit(tmp_path):
    """Test --track-file with invalid regex via CliRunner for coverage."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    pattern_file = tmp_path / "bad.txt"
    pattern_file.write_text("[unclosed\n")

    result = runner.invoke(app, [str(input_file), "--track-file", str(pattern_file)], env=TEST_ENV)

    assert result.exit_code != 0
    stderr = get_stderr(result)
    assert "Invalid track pattern" in stderr


@pytest.mark.unit
def test_bypass_file_invalid_regex_unit(tmp_path):
    """Test --bypass-file with invalid regex via CliRunner for coverage."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("A\nB\nC\n")

    pattern_file = tmp_path / "bad.txt"
    pattern_file.write_text("*invalid\n")

    result = runner.invoke(app, [str(input_file), "--bypass-file", str(pattern_file)], env=TEST_ENV)

    assert result.exit_code != 0
    stderr = get_stderr(result)
    assert "Invalid bypass pattern" in stderr


@pytest.mark.integration
def test_window_size_one_string_lines(tmp_path):
    """Test window_size=1 with string lines (single-line deduplication)."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("Line A\nLine B\nLine A\nLine C\nLine B\nLine D\n")

    exit_code, stdout, stderr = run_uniqseq([str(input_file), "--window-size", "1", "--quiet"])

    assert exit_code == 0
    lines = stdout.strip().split("\n")
    # Should deduplicate single lines like standard uniq
    assert lines == ["Line A", "Line B", "Line C", "Line D"]


@pytest.mark.integration
def test_window_size_one_with_skip_chars(tmp_path):
    """Test window_size=1 with --skip-chars (timestamps, etc)."""
    input_file = tmp_path / "input.txt"
    # Lines with timestamps that should be deduplicated when skipping first 6 chars
    input_file.write_text(
        "2024-01-01 Error\n"
        "2024-01-02 Warning\n"
        "2024-01-03 Error\n"
        "2024-01-04 Warning\n"
        "2024-01-05 Info\n"
    )

    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--window-size", "1", "--skip-chars", "11", "--quiet"]
    )

    assert exit_code == 0
    lines = stdout.strip().split("\n")
    # Should keep first occurrence of each unique message (after skipping timestamp)
    assert len(lines) == 3
    assert "Error" in lines[0]
    assert "Warning" in lines[1]
    assert "Info" in lines[2]


@pytest.mark.integration
def test_window_size_one_bytes_mode(tmp_path):
    """Test window_size=1 with byte mode."""
    input_file = tmp_path / "input.bin"
    # Binary data with repeated sequences (single bytes with window=1)
    data = b"A\x00B\x00A\x00C\x00B\x00D\x00"
    input_file.write_bytes(data)

    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--window-size", "1", "--byte-mode", "--delimiter-hex", "00", "--quiet"]
    )

    assert exit_code == 0
    # Should deduplicate single "lines" (bytes separated by \x00)
    # stdout is string, encode to bytes for splitting
    output_bytes = stdout.encode("utf-8")
    output_chunks = output_bytes.split(b"\x00")
    # Filter out empty chunks
    output_chunks = [chunk for chunk in output_chunks if chunk]
    assert output_chunks == [b"A", b"B", b"C", b"D"]


@pytest.mark.integration
def test_window_size_one_with_bypass(tmp_path):
    """Test window_size=1 with --bypass filter deduplicates non-bypassed lines."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("ERROR: A\nINFO: B\nERROR: A\nWARN: C\nINFO: B\nERROR: D\n")

    # Test that window_size=1 works with --bypass filter
    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--window-size", "1", "--bypass", "^INFO", "--quiet"]
    )

    assert exit_code == 0
    lines = stdout.strip().split("\n")
    # INFO lines bypassed (both kept), ERROR and WARN deduplicated
    assert len(lines) == 5  # 3 unique (ERROR A, WARN C, ERROR D) + 2 bypassed INFO
    # Verify bypassed lines appear twice
    assert lines.count("INFO: B") == 2
    # Verify deduplicated lines appear once
    assert lines.count("ERROR: A") == 1
    assert lines.count("WARN: C") == 1
    assert lines.count("ERROR: D") == 1


@pytest.mark.integration
def test_window_size_one_with_annotate(tmp_path):
    """Test window_size=1 with --annotate deduplicates and annotates correctly."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("Line A\nLine B\nLine A\nLine C\nLine B\nLine D\n")

    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--window-size", "1", "--annotate", "--quiet"]
    )

    assert exit_code == 0
    lines = stdout.strip().split("\n")
    # 4 unique lines + 2 annotations
    assert len(lines) == 6
    # Verify unique lines present
    assert "Line A" in stdout
    assert "Line B" in stdout
    assert "Line C" in stdout
    assert "Line D" in stdout
    # Verify annotations present with correct line numbers
    assert stdout.count("[DUPLICATE:") == 2
    assert "matched lines 1-1" in stdout  # First Line A at output line 1
    assert "matched lines 2-2" in stdout  # First Line B at output line 2


@pytest.mark.integration
def test_window_size_one_with_track(tmp_path):
    """Test window_size=1 with --track filter deduplicates tracked lines."""
    input_file = tmp_path / "input.txt"
    input_file.write_text("ERROR: A\nINFO: B\nERROR: A\nWARN: C\nERROR: A\nINFO: D\n")

    # Only track ERROR lines for deduplication
    exit_code, stdout, stderr = run_uniqseq(
        [str(input_file), "--window-size", "1", "--track", "^ERROR", "--quiet"]
    )

    assert exit_code == 0
    lines = stdout.strip().split("\n")
    # ERROR A appears 3 times, should be deduplicated to 1
    # INFO lines not tracked, both pass through
    # WARN line not tracked, passes through
    assert len(lines) == 4  # ERROR A (1) + INFO B + WARN C + INFO D
    assert lines.count("ERROR: A") == 1
    assert "INFO: B" in stdout
    assert "WARN: C" in stdout
    assert "INFO: D" in stdout
