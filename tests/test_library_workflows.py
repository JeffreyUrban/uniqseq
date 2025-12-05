"""Integration tests for real-world library workflows.

Tests multi-source loading, pause/resume, and read-only pattern loading.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import pytest


def run_uniqseq(args: list[str], output_file: Optional[Path] = None) -> tuple[int, str, str]:
    """Run uniqseq CLI and return (exit_code, stdout, stderr).

    Args:
        args: Command-line arguments to uniqseq
        output_file: If provided, redirect stdout to this file
    """
    if output_file:
        with open(output_file, "w") as f:
            result = subprocess.run(
                [sys.executable, "-m", "uniqseq"] + args,
                stdout=f,
                stderr=subprocess.PIPE,
                text=True,
            )
        return result.returncode, "", result.stderr
    else:
        result = subprocess.run(
            [sys.executable, "-m", "uniqseq"] + args,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr


@pytest.mark.integration
def test_incremental_library_building():
    """Test building a library incrementally across multiple sources."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        lib_dir = tmpdir / "lib"

        # Create test files with repeated sequences (window size 3)
        app1 = tmpdir / "app1.log"
        app1.write_text(
            "Line 1\n"
            "Line 2\n"
            "Line 3\n"
            "Line 4\n"
            "Line 1\n"
            "Line 2\n"
            "Line 3\n"
            "Line 4\n"
            "Different 1\n"
            "Another 1\n"
            "Another 2\n"
            "Another 3\n"
            "Another 1\n"
            "Another 2\n"
            "Another 3\n"
        )

        app2 = tmpdir / "app2.log"
        app2.write_text(
            "Line 1\n"
            "Line 2\n"
            "Line 3\n"
            "Line 4\n"
            "New line A\n"
            "Another 1\n"
            "Another 2\n"
            "Another 3\n"
            "Pattern X\n"
            "Pattern Y\n"
            "Pattern Z\n"
            "Pattern X\n"
            "Pattern Y\n"
            "Pattern Z\n"
        )

        app3 = tmpdir / "app3.log"
        app3.write_text(
            "Another 1\nAnother 2\nAnother 3\nPattern X\nPattern Y\nPattern Z\nFinal 1\n"
        )

        # Process first file
        out1 = tmpdir / "out1.log"
        exit_code, stdout, stderr = run_uniqseq(
            [str(app1), "--library-dir", str(lib_dir), "--window-size", "3"], output_file=out1
        )
        if exit_code != 0:
            print(f"STDOUT: {stdout}")
            print(f"STDERR: {stderr}")
        assert exit_code == 0

        # Check library created
        sequences_dir = lib_dir / "sequences"
        assert sequences_dir.exists()
        assert len(list(sequences_dir.glob("*.uniqseq"))) == 2  # Two sequences discovered

        # Check metadata
        metadata_dirs = list(lib_dir.glob("metadata-*"))
        assert len(metadata_dirs) == 1
        config1 = json.load(open(metadata_dirs[0] / "config.json"))
        assert config1["sequences_discovered"] == 2
        assert config1["sequences_preloaded"] == 0
        assert config1["sequences_saved"] == 2
        assert config1["window_size"] == 3

        # Process second file (should load existing + discover new)
        out2 = tmpdir / "out2.log"
        exit_code, stdout, stderr = run_uniqseq(
            [str(app2), "--library-dir", str(lib_dir), "--window-size", "3"], output_file=out2
        )
        if exit_code != 0:
            print(f"Second run STDOUT: {stdout}")
            print(f"Second run STDERR: {stderr}")
        assert exit_code == 0

        # Check library grew
        assert len(list(sequences_dir.glob("*.uniqseq"))) == 3  # Added Pattern X/Y/Z

        # Check second metadata
        metadata_dirs = sorted(lib_dir.glob("metadata-*"))
        if len(metadata_dirs) != 2:
            print(f"Expected 2 metadata dirs, found {len(metadata_dirs)}: {metadata_dirs}")
            print(f"Library dir contents: {list(lib_dir.iterdir())}")
        assert len(metadata_dirs) == 2
        config2 = json.load(open(metadata_dirs[1] / "config.json"))
        assert config2["sequences_preloaded"] == 2  # Loaded from first run
        assert config2["sequences_discovered"] == 3  # Total discovered (2 old + 1 new)
        assert config2["sequences_saved"] == 3

        # Verify sequences NOT in output (were preloaded)
        out2_content = out2.read_text()
        assert "Line 1\nLine 2\nLine 3\nLine 4" not in out2_content
        assert "Another 1\nAnother 2\nAnother 3" not in out2_content

        # Process third file (should recognize all sequences)
        out3 = tmpdir / "out3.log"
        exit_code, stdout, stderr = run_uniqseq(
            [str(app3), "--library-dir", str(lib_dir), "--window-size", "3"], output_file=out3
        )
        if exit_code != 0:
            print(f"Third run STDOUT: {stdout}")
            print(f"Third run STDERR: {stderr}")
        assert exit_code == 0

        # No new sequences added
        assert len(list(sequences_dir.glob("*.uniqseq"))) == 3

        # Check third metadata
        metadata_dirs = sorted(lib_dir.glob("metadata-*"))
        if len(metadata_dirs) != 3:
            print(
                f"Expected 3 metadata dirs after third run, found {len(metadata_dirs)}: {metadata_dirs}"
            )
            print(f"Third run exit code: {exit_code}")
            print(f"Third run stderr: {stderr}")
            print(f"Library contents: {list(lib_dir.iterdir())}")
        assert len(metadata_dirs) == 3
        config3 = json.load(open(metadata_dirs[2] / "config.json"))
        assert config3["sequences_preloaded"] == 3  # All from library
        # In third run, all sequences are preloaded and remain in unique_sequences
        assert config3["sequences_discovered"] == 3  # All preloaded sequences tracked
        # Note: Preloaded sequences that are observed get "saved" again (callback triggered)
        # even though the file already exists. This just rewrites the file.
        # TODO: Consider optimizing to skip saving if file already exists
        assert config3["sequences_saved"] == 2  # Two sequences observed in app3

        # Verify sequences NOT in output
        out3_content = out3.read_text()
        assert "Another 1" not in out3_content
        assert "Pattern X" not in out3_content


@pytest.mark.integration
def test_read_only_pattern_loading():
    """Test loading patterns in read-only mode with --read-sequences."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create custom pattern files
        patterns_dir = tmpdir / "patterns"
        patterns_dir.mkdir()

        # Pattern 1: Error sequence
        pattern1 = patterns_dir / "error-pattern.txt"
        pattern1.write_text("ERROR: Connection failed\nRetrying...\nERROR: Timeout")

        # Pattern 2: Warning sequence
        pattern2 = patterns_dir / "warning-pattern.txt"
        pattern2.write_text("WARNING: Slow\nTimeout exceeded\nAborted")

        # Create input with these patterns
        input_file = tmpdir / "input.log"
        input_file.write_text(
            "Start\n"
            "ERROR: Connection failed\n"
            "Retrying...\n"
            "ERROR: Timeout\n"
            "Middle\n"
            "WARNING: Slow\n"
            "Timeout exceeded\n"
            "Aborted\n"
            "ERROR: Connection failed\n"
            "Retrying...\n"
            "ERROR: Timeout\n"
            "End\n"
        )

        # Process with read-only patterns
        output = tmpdir / "output.log"
        exit_code, stdout, stderr = run_uniqseq(
            [
                str(input_file),
                "--read-sequences",
                str(patterns_dir),
                "--window-size",
                "3",
            ],
            output_file=output,
        )
        assert exit_code == 0

        # Check patterns directory NOT modified (read-only)
        assert len(list(patterns_dir.glob("*"))) == 2  # Still just 2 files

        # Verify sequences skipped on first observation
        output_content = output.read_text()
        lines = output_content.strip().split("\n")

        # Should have: Start, Middle, End (patterns skipped)
        assert "Start" in lines
        assert "Middle" in lines
        assert "End" in lines

        # ERROR sequence should NOT appear (skipped on first observation)
        # Only check that we don't have the full first occurrence
        error_count = output_content.count("ERROR: Connection failed")
        assert error_count == 0  # First occurrence skipped due to preload


@pytest.mark.integration
def test_combined_read_and_write_library():
    """Test combining --read-sequences (read-only) with --library-dir (read-write)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create read-only patterns
        readonly_dir = tmpdir / "readonly"
        readonly_dir.mkdir()
        pattern1 = readonly_dir / "pattern1.txt"
        pattern1.write_text("Known 1\nKnown 2\nKnown 3")

        # Create library directory
        lib_dir = tmpdir / "lib"

        # Create input with known and new patterns
        input_file = tmpdir / "input.log"
        input_file.write_text(
            "Known 1\n"
            "Known 2\n"
            "Known 3\n"
            "New A\n"
            "New B\n"
            "New C\n"
            "New A\n"
            "New B\n"
            "New C\n"
            "Known 1\n"
            "Known 2\n"
            "Known 3\n"
        )

        # Process with both read-only and library
        output = tmpdir / "output.log"
        exit_code, stdout, stderr = run_uniqseq(
            [
                str(input_file),
                "--read-sequences",
                str(readonly_dir),
                "--library-dir",
                str(lib_dir),
                "--window-size",
                "3",
            ],
            output_file=output,
        )
        assert exit_code == 0

        # Read-only directory unchanged
        assert len(list(readonly_dir.glob("*"))) == 1

        # Library directory has new sequences
        sequences_dir = lib_dir / "sequences"
        assert sequences_dir.exists()

        # Should have 2 sequences saved:
        # 1. Known 1/2/3 (preloaded from readonly, saved when first observed)
        # 2. New A/B/C (discovered and saved)
        saved_sequences = list(sequences_dir.glob("*.uniqseq"))
        assert len(saved_sequences) == 2

        # Check metadata
        metadata_dirs = list(lib_dir.glob("metadata-*"))
        assert len(metadata_dirs) == 1
        config = json.load(open(metadata_dirs[0] / "config.json"))
        assert config["sequences_preloaded"] == 1  # From readonly
        assert config["sequences_discovered"] == 2  # Total (1 preloaded + 1 new)
        assert config["sequences_saved"] == 2


@pytest.mark.integration
def test_pause_resume_workflow():
    """Test pausing and resuming processing with library."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        lib_dir = tmpdir / "lib"

        # Create large file
        large_file = tmpdir / "large.log"
        lines = []
        # Add repeated sequences
        for _ in range(5):
            lines.extend(["Block A", "Block B", "Block C"])
        for _ in range(5):
            lines.extend(["Block X", "Block Y", "Block Z"])
        large_file.write_text("\n".join(lines) + "\n")

        # Process first 10 lines
        part1 = tmpdir / "part1.log"
        with open(large_file) as f:
            first_10 = "".join([f.readline() for _ in range(10)])
        input1 = tmpdir / "input1.log"
        input1.write_text(first_10)

        exit_code, stdout, stderr = run_uniqseq(
            [str(input1), "--library-dir", str(lib_dir), "--window-size", "3"], output_file=part1
        )
        assert exit_code == 0

        # Library should have sequences
        sequences_dir = lib_dir / "sequences"
        assert sequences_dir.exists()
        seq_count_after_part1 = len(list(sequences_dir.glob("*.uniqseq")))
        assert seq_count_after_part1 > 0

        # Process remaining lines (resume)
        part2 = tmpdir / "part2.log"
        with open(large_file) as f:
            # Skip first 10 lines
            for _ in range(10):
                f.readline()
            remaining = f.read()
        input2 = tmpdir / "input2.log"
        input2.write_text(remaining)

        exit_code, stdout, stderr = run_uniqseq(
            [str(input2), "--library-dir", str(lib_dir), "--window-size", "3"], output_file=part2
        )
        assert exit_code == 0

        # Check library preloaded sequences
        metadata_dirs = sorted(lib_dir.glob("metadata-*"))
        assert len(metadata_dirs) == 2

        config2 = json.load(open(metadata_dirs[1] / "config.json"))
        assert config2["sequences_preloaded"] == seq_count_after_part1

        # Combine outputs and verify deduplication worked
        combined = part1.read_text() + part2.read_text()
        # Should have much less content than original (duplicates removed)
        assert len(combined.split("\n")) < len(lines)


@pytest.mark.integration
def test_multi_source_pattern_sharing():
    """Test sharing patterns across different systems/environments."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Simulate production system
        prod_lib = tmpdir / "prod_lib"
        prod_input = tmpdir / "prod.log"
        prod_input.write_text(
            "PROD: Start\n"
            "PROD: Error A\n"
            "PROD: Error B\n"
            "PROD: Error C\n"
            "PROD: Error A\n"
            "PROD: Error B\n"
            "PROD: Error C\n"
        )

        exit_code, stdout, stderr = run_uniqseq(
            [str(prod_input), "--library-dir", str(prod_lib), "--window-size", "3", "--quiet"]
        )
        assert exit_code == 0

        # Copy sequences to dev (simulate scp)
        dev_patterns = tmpdir / "dev_patterns"
        dev_patterns.mkdir()
        sequences_dir = prod_lib / "sequences"
        for seq_file in sequences_dir.glob("*.uniqseq"):
            (dev_patterns / seq_file.name).write_bytes(seq_file.read_bytes())

        # Dev system applies prod patterns
        dev_input = tmpdir / "dev.log"
        dev_input.write_text(
            "DEV: Start\n"
            "PROD: Error A\n"  # Known from prod
            "PROD: Error B\n"
            "PROD: Error C\n"
            "DEV: New Error X\n"
            "DEV: New Error Y\n"
            "DEV: New Error Z\n"
            "DEV: New Error X\n"
            "DEV: New Error Y\n"
            "DEV: New Error Z\n"
        )

        dev_output = tmpdir / "dev_out.log"
        dev_lib = tmpdir / "dev_lib"

        exit_code, stdout, stderr = run_uniqseq(
            [
                str(dev_input),
                "--read-sequences",
                str(dev_patterns),
                "--library-dir",
                str(dev_lib),
                "--window-size",
                "3",
            ],
            output_file=dev_output,
        )
        assert exit_code == 0

        # Prod patterns directory unchanged (read-only)
        assert len(list(dev_patterns.glob("*.uniqseq"))) == len(
            list(sequences_dir.glob("*.uniqseq"))
        )

        # Dev library has new patterns
        dev_sequences = dev_lib / "sequences"
        assert dev_sequences.exists()

        # Check metadata
        metadata_dirs = list(dev_lib.glob("metadata-*"))
        config = json.load(open(metadata_dirs[0] / "config.json"))
        assert config["sequences_preloaded"] > 0  # Loaded from prod
        assert config["sequences_discovered"] >= config["sequences_preloaded"]  # May have new

        # Verify prod patterns were recognized
        output_content = dev_output.read_text()
        assert "PROD: Error A" not in output_content  # Skipped (from prod library)


@pytest.mark.integration
def test_finding_new_patterns_with_inverse():
    """Test using --inverse with --read-sequences emits all duplicates (preloaded and new)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create known patterns library
        known_lib = tmpdir / "known_lib"
        known_lib.mkdir()

        # Build library from baseline
        baseline = tmpdir / "baseline.log"
        baseline.write_text("Known A\nKnown B\nKnown C\nKnown A\nKnown B\nKnown C\n")

        exit_code, stdout, stderr = run_uniqseq(
            [str(baseline), "--library-dir", str(known_lib), "--window-size", "3", "--quiet"]
        )
        assert exit_code == 0

        # New build with some known and some new patterns
        new_build = tmpdir / "new_build.log"
        new_build.write_text(
            "Known A\nKnown B\nKnown C\nNew X\nNew Y\nNew Z\nNew X\nNew Y\nNew Z\n"
        )

        # Find only new patterns using --inverse
        new_only = tmpdir / "new_only.log"
        sequences_dir = known_lib / "sequences"

        exit_code, stdout, stderr = run_uniqseq(
            [
                str(new_build),
                "--read-sequences",
                str(sequences_dir),
                "--inverse",
                "--window-size",
                "3",
            ],
            output_file=new_only,
        )
        assert exit_code == 0

        # Output should have ALL duplicates (both preloaded and new)
        output_content = new_only.read_text()
        # Known pattern matches preloaded sequence, so it's a duplicate -> emitted in inverse mode
        assert "Known A" in output_content
        assert "Known B" in output_content
        assert "Known C" in output_content
        # New pattern appears twice, second occurrence is duplicate -> emitted in inverse mode
        assert "New X" in output_content
        assert "New Y" in output_content
        assert "New Z" in output_content
        # Verify the pattern appears exactly once each (known once + new second occurrence)
        lines = output_content.strip().split("\n")
        assert len(lines) == 6  # 3 lines from known pattern + 3 lines from new pattern duplicate
