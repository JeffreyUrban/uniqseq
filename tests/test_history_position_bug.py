"""Test for history position misalignment bug.

ROOT CAUSE: When non-tracked lines are present, input_line_num (which counts ALL lines)
becomes misaligned with window_hash_history positions (which only has entries for
tracked lines).

This causes the wrong history entries to be updated with first_output_line values,
corrupting duplicate detection.
"""

import subprocess

import pytest


@pytest.mark.integration
class TestHistoryPositionMisalignment:
    """Test that history positions are correctly aligned regardless of non-tracked lines."""

    def test_history_position_misalignment_breaks_deduplication(self, tmp_path):
        """Demonstrate history position misalignment with concrete example.

        Input pattern:
          Line 1: +: A (tracked)      → input_line_num=1, should map to history[0]
          Line 2: -: SEP (non-tracked) → input_line_num=2, no history entry
          Line 3: +: B (tracked)      → input_line_num=3, should map to history[1]
          ...
          (duplicate of lines 1-10)

        BUG: When line 3 is emitted, code does: hist_pos = 3 - 1 = 2
             But history only has [0, 1]! Should use hist_pos = 1.

        This corruption causes duplicates to not be detected properly.
        """
        # Create input with tracked lines and one non-tracked separator
        # Pattern: 10 tracked lines, separator, then duplicate of those 10 lines
        with_separator = tmp_path / "with_sep.txt"
        lines = []
        for i in range(1, 11):
            lines.append(f"+: Line {i}")
        lines.append("-: SEPARATOR")  # Non-tracked line
        for i in range(1, 11):
            lines.append(f"+: Line {i}")  # Duplicate

        with_separator.write_text("\n".join(lines) + "\n")

        # Create input WITHOUT separator (same tracked lines)
        without_separator = tmp_path / "without_sep.txt"
        tracked_lines = []
        for i in range(1, 11):
            tracked_lines.append(f"+: Line {i}")
        for i in range(1, 11):
            tracked_lines.append(f"+: Line {i}")  # Duplicate

        without_separator.write_text("\n".join(tracked_lines) + "\n")

        # Run uniqseq on both
        result_with = tmp_path / "result_with.txt"
        result_without = tmp_path / "result_without.txt"

        cmd = ["uniqseq", "--track", r"^\+: ", "--quiet"]

        with open(with_separator) as stdin, open(result_with, "w") as stdout:
            subprocess.run(cmd, stdin=stdin, stdout=stdout, check=True)

        with open(without_separator) as stdin, open(result_without, "w") as stdout:
            subprocess.run(cmd, stdin=stdin, stdout=stdout, check=True)

        # Extract tracked lines from outputs
        with open(result_with) as f:
            tracked_with = [line for line in f if line.startswith("+: ")]

        with open(result_without) as f:
            tracked_without = [line for line in f if line.startswith("+: ")]

        # Print diagnostics
        print("\n" + "=" * 70)
        print("HISTORY POSITION MISALIGNMENT TEST")
        print("=" * 70)
        print("\nInput: 20 tracked lines (10 unique + 10 duplicate)")
        print("Expected: Both outputs should have 10 tracked lines (duplicate detected)")
        print("\nWith separator (has history misalignment bug):")
        print(f"  Tracked output lines: {len(tracked_with)}")
        print("\nWithout separator (correct behavior):")
        print(f"  Tracked output lines: {len(tracked_without)}")

        # The critical assertion: tracked outputs must be identical
        if tracked_with != tracked_without:
            print("\n✗ BUG CONFIRMED: Outputs differ!")
            print(f"  Difference: {abs(len(tracked_with) - len(tracked_without))} lines")
            print("\nRoot cause:")
            print("  When line 3 (+: Line 3) is emitted:")
            print("    input_line_num = 3 (includes the separator)")
            print("    hist_pos = 3 - 1 = 2")
            print("    But history only has [0, 1]!")
            print("    Should be hist_pos = 1 (tracked line index)")
        else:
            print("\n✓ PASS: Outputs identical")

        print("=" * 70 + "\n")

        # REQUIREMENT: Tracked outputs must be identical
        assert tracked_with == tracked_without, (
            f"\nHISTORY POSITION MISALIGNMENT BUG!\n\n"
            f"Same tracked input lines produced different outputs:\n"
            f"  With separator: {len(tracked_with)} tracked lines\n"
            f"  Without separator: {len(tracked_without)} tracked lines\n\n"
            f"ROOT CAUSE (src/uniqseq/uniqseq.py:571):\n"
            f"  hist_pos = buffered_line.input_line_num - 1\n\n"
            f"This formula assumes input_line_num only counts tracked lines,\n"
            f"but it actually counts ALL lines (tracked + non-tracked).\n\n"
            f"When non-tracked lines are present:\n"
            f"  - input_line_num has gaps (skips non-tracked)\n"
            f"  - history positions are sequential (no gaps)\n"
            f"  - The mapping becomes misaligned\n\n"
            f"This corrupts first_output_line tracking, breaking duplicate detection.\n"
        )

    def test_tracked_outputs_must_be_identical_regardless_of_nontracked(self, tmp_path):
        """Core requirement: Same tracked lines → same tracked output, always.

        This is the fundamental requirement that the history position bug violates.
        """
        # Create a sequence that will have duplicates
        tracked_lines = []
        for i in range(15):  # Need > 10 for window matching
            tracked_lines.append(f"+: Sequence Line {i % 5}")

        # Test 1: Tracked only
        tracked_only = tmp_path / "tracked_only.txt"
        tracked_only.write_text("\n".join(tracked_lines) + "\n")

        # Test 2: Same tracked lines with non-tracked interspersed
        mixed = tmp_path / "mixed.txt"
        mixed_lines = []
        for i, line in enumerate(tracked_lines):
            mixed_lines.append(line)
            if i % 3 == 0:  # Add non-tracked every 3 lines
                mixed_lines.append(f"-: Non-tracked {i}")
        mixed.write_text("\n".join(mixed_lines) + "\n")

        # Run uniqseq
        result_tracked = tmp_path / "result_tracked.txt"
        result_mixed = tmp_path / "result_mixed.txt"

        cmd = ["uniqseq", "--track", r"^\+: ", "--quiet"]

        with open(tracked_only) as stdin, open(result_tracked, "w") as stdout:
            subprocess.run(cmd, stdin=stdin, stdout=stdout, check=True)

        with open(mixed) as stdin, open(result_mixed, "w") as stdout:
            subprocess.run(cmd, stdin=stdin, stdout=stdout, check=True)

        # Extract tracked outputs
        with open(result_tracked) as f:
            out_tracked = [line for line in f if line.startswith("+: ")]

        with open(result_mixed) as f:
            out_mixed = [line for line in f if line.startswith("+: ")]

        print("\n" + "=" * 70)
        print("REQUIREMENT TEST: Tracked outputs must be identical")
        print("=" * 70)
        print(f"\nTracked-only input → {len(out_tracked)} tracked output")
        print(f"Mixed input → {len(out_mixed)} tracked output")
        print("=" * 70 + "\n")

        # CORE REQUIREMENT
        assert out_tracked == out_mixed, (
            f"\nCORE REQUIREMENT VIOLATED!\n\n"
            f"Same tracked lines, different presence of non-tracked lines:\n"
            f"  Result: Different tracked outputs\n\n"
            f"Tracked-only: {len(out_tracked)} lines\n"
            f"Mixed: {len(out_mixed)} lines\n\n"
            f"Non-tracked lines must have ZERO effect on tracked line deduplication.\n"
        )
