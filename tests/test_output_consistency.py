r"""Test for consistent deduplication output when tracked lines are added.

This test verifies that adding a small number of tracked lines to an input should
not cause massive divergence in the deduplication output. The algorithm should be
robust to small perturbations in the input.

Related issue: When running `uniqseq --track '^\+: ' --quiet` on two nearly identical
files (output1.txt with 7 additional window-title lines, output2.txt without them),
the outputs should differ by approximately those 7 lines plus minor boundary effects,
not by thousands of lines.

The window-title lines DO match the --track pattern (they start with '+: '), so they
are tracked lines. The issue is that inserting these 7 tracked lines causes the
deduplication state to diverge massively, producing completely different output.
"""

import difflib
import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
class TestOutputConsistency:
    """Test that uniqseq output is consistent when non-tracked lines differ."""

    def test_output_consistency_with_additional_tracked_lines(self, tmp_path):
        """Measure divergence when a few tracked lines are added to input.

        When two input files differ by a small number of tracked lines (7 lines out
        of ~19k), the deduplication output should differ by approximately those same
        lines plus minor boundary effects. This test provides quantitative metrics
        to track the degree of divergence.

        Expected behavior:
        - Input files differ by 7 tracked lines (window-title lines in output1.txt)
        - Output should differ by ~7-17 lines (the added lines + window boundary effects)
        - Divergence ratio should be ~1x (minimal amplification)

        Current behavior (bug):
        - Outputs diverge by ~2000+ lines (divergence ratio: ~295x)
        - Adding 7 tracked lines causes completely different deduplication decisions
          throughout the rest of the file
        """
        # Read the fixture files
        fixtures_dir = Path(__file__).parent / "fixtures"
        output1_path = fixtures_dir / "output1.txt"
        output2_path = fixtures_dir / "output2.txt"

        # Verify fixtures exist
        assert output1_path.exists(), f"Fixture not found: {output1_path}"
        assert output2_path.exists(), f"Fixture not found: {output2_path}"

        # Analyze input differences
        with open(output1_path) as f1, open(output2_path) as f2:
            input1_lines = f1.readlines()
            input2_lines = f2.readlines()

        input_line_diff = len(input1_lines) - len(input2_lines)
        window_title_count = sum(1 for line in input1_lines if "window-title" in line)

        # Run uniqseq on both files
        result1_path = tmp_path / "result1.txt"
        result2_path = tmp_path / "result2.txt"

        cmd = ["uniqseq", "--track", r"^\+: ", "--quiet"]

        with open(output1_path) as stdin, open(result1_path, "w") as stdout:
            subprocess.run(cmd, stdin=stdin, stdout=stdout, check=True)

        with open(output2_path) as stdin, open(result2_path, "w") as stdout:
            subprocess.run(cmd, stdin=stdin, stdout=stdout, check=True)

        # Read and analyze the results
        with open(result1_path) as f1, open(result2_path) as f2:
            result1_lines = f1.readlines()
            result2_lines = f2.readlines()

        # Calculate metrics
        output_line_diff = len(result1_lines) - len(result2_lines)
        output_line_diff_abs = abs(output_line_diff)

        # Use difflib to get a more precise measure of differences
        diff = list(difflib.unified_diff(result1_lines, result2_lines, lineterm=""))
        # Filter out diff metadata lines (those starting with +++, ---, @@)
        actual_diff_lines = [line for line in diff if not line.startswith(("+++", "---", "@@"))]
        diff_line_count = len(actual_diff_lines)

        # Count window-title lines in outputs
        window_title_in_result1 = sum(1 for line in result1_lines if "window-title" in line)
        window_title_in_result2 = sum(1 for line in result2_lines if "window-title" in line)

        # Calculate divergence ratio (how much more the outputs differ vs inputs)
        expected_diff = window_title_count
        excess_divergence = output_line_diff_abs - expected_diff
        divergence_ratio = (
            output_line_diff_abs / expected_diff if expected_diff > 0 else float("inf")
        )

        # Analyze tracked vs non-tracked lines separately
        tracked1 = [line for line in result1_lines if line.startswith("+: ")]
        tracked2 = [line for line in result2_lines if line.startswith("+: ")]
        nontracked1 = [line for line in result1_lines if not line.startswith("+: ")]
        nontracked2 = [line for line in result2_lines if not line.startswith("+: ")]

        # Print detailed metrics
        print("\n" + "=" * 70)
        print("OUTPUT CONSISTENCY ANALYSIS")
        print("=" * 70)
        print("\nINPUT FILES:")
        print(f"  output1.txt lines: {len(input1_lines):,}")
        print(f"  output2.txt lines: {len(input2_lines):,}")
        print(f"  Difference: {input_line_diff} lines")
        print(f"  Window-title lines in output1.txt: {window_title_count}")
        print("\nOUTPUT FILES:")
        print(f"  result1.txt lines: {len(result1_lines):,}")
        print(f"  result2.txt lines: {len(result2_lines):,}")
        print(f"  Difference: {output_line_diff} lines ({output_line_diff_abs} absolute)")
        print(f"  Window-title lines in result1: {window_title_in_result1}")
        print(f"  Window-title lines in result2: {window_title_in_result2}")
        print("\nTRACKED VS NON-TRACKED BREAKDOWN:")
        print(f"  Tracked lines in result1 (start with '+: '): {len(tracked1):,}")
        print(f"  Tracked lines in result2 (start with '+: '): {len(tracked2):,}")
        print(f"  Tracked line difference: {abs(len(tracked1) - len(tracked2)):,}")
        print(f"  Non-tracked lines in result1: {len(nontracked1):,}")
        print(f"  Non-tracked lines in result2: {len(nontracked2):,}")
        print(f"  Non-tracked lines identical: {nontracked1 == nontracked2}")
        print("\nDIVERGENCE METRICS:")
        print(f"  Expected output difference: ~{expected_diff} lines")
        print(f"  Actual output difference: {output_line_diff_abs} lines")
        print(f"  Excess divergence: {excess_divergence} lines")
        print(f"  Divergence ratio: {divergence_ratio:.1f}x expected")
        print(f"  Unified diff changes: {diff_line_count} lines")
        print("\nVERDICT:")
        if output_line_diff_abs <= expected_diff + 10:
            print(f"  ✓ PASS - Minimal divergence ({output_line_diff_abs} ≤ {expected_diff + 10})")
        else:
            print(
                f"  ✗ FAIL - Excessive divergence ({output_line_diff_abs} > {expected_diff + 10})"
            )
            print("  The deduplication state is being affected by non-tracked lines.")
        print("=" * 70 + "\n")

        # Verify requirement 1: non-tracked lines must be identical
        assert nontracked1 == nontracked2, (
            f"\nREQUIREMENT VIOLATION: Non-tracked lines are NOT identical!\n"
            f"Non-tracked lines must pass through unchanged.\n"
            f"Non-tracked1 lines: {len(nontracked1):,}\n"
            f"Non-tracked2 lines: {len(nontracked2):,}\n"
        )

        # Verify requirement 2: tracked outputs must be identical
        # (non-tracked lines in input must have ZERO effect on tracked line deduplication)
        assert tracked1 == tracked2, (
            f"\nCRITICAL REQUIREMENT VIOLATION!\n"
            f"Tracked line outputs are NOT identical!\n\n"
            f"The same tracked input lines produced different tracked outputs\n"
            f"depending on whether non-tracked lines were present in the input.\n\n"
            f"Tracked lines in result1: {len(tracked1):,}\n"
            f"Tracked lines in result2: {len(tracked2):,}\n"
            f"Difference: {abs(len(tracked1) - len(tracked2)):,} lines\n\n"
            f"REQUIREMENT: Non-tracked lines must have ZERO effect on how\n"
            f"tracked lines are deduplicated. After removing non-tracked lines\n"
            f"from outputs, the tracked lines must be IDENTICAL.\n"
        )

        # Assert with detailed message
        assert output_line_diff_abs <= expected_diff + 10, (
            f"\nExcessive output divergence detected!\n"
            f"Expected: outputs differ by ~{expected_diff} lines (the added tracked lines)\n"
            f"Actual: outputs differ by {output_line_diff_abs} lines\n"
            f"Excess divergence: {excess_divergence} lines\n"
            f"Divergence ratio: {divergence_ratio:.1f}x\n\n"
            f"This indicates that adding a small number of tracked lines causes massive\n"
            f"divergence in deduplication decisions. The algorithm is not robust to small\n"
            f"perturbations in the input.\n"
            f"See detailed metrics above."
        )
