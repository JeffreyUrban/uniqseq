"""Test that non-tracked lines do not interfere with deduplication of tracked lines.

CRITICAL BUG: Non-tracked lines must pass through unchanged AND have zero effect
on how tracked lines are deduplicated. Currently, non-tracked lines are passed
through correctly but their presence affects duplicate detection.
"""

import subprocess

import pytest


@pytest.mark.integration
class TestNonTrackedInterference:
    """Test that non-tracked lines don't affect deduplication of tracked lines."""

    def test_nontracked_separator_prevents_duplicate_detection(self, tmp_path):
        """Minimal reproduction: non-tracked separator prevents duplicate detection.

        Two identical 10-line sequences should be deduplicated identically regardless of whether there's a non-tracked
        line between them.

        Expected: Both cases produce identical tracked output (10 tracked lines)
        Actual: With separator produces 10 tracked lines (duplicate NOT detected)
                Without separator produces 10 tracked lines (duplicate detected)

        The bug: Non-tracked lines are interfering with window-based duplicate detection.
        """
        # Create test with non-tracked separator
        with_sep = tmp_path / "with_sep.txt"
        with_sep.write_text(
            "+: Line 1\n"
            "+: Line 2\n"
            "+: Line 3\n"
            "+: Line 4\n"
            "+: Line 5\n"
            "+: Line 6\n"
            "+: Line 7\n"
            "+: Line 8\n"
            "+: Line 9\n"
            "+: Line 10\n"
            "-: NON_TRACKED_SEPARATOR\n"
            "+: Line 1\n"
            "+: Line 2\n"
            "+: Line 3\n"
            "+: Line 4\n"
            "+: Line 5\n"
            "+: Line 6\n"
            "+: Line 7\n"
            "+: Line 8\n"
            "+: Line 9\n"
            "+: Line 10\n"
        )

        # Create test without separator (tracked only)
        without_sep = tmp_path / "without_sep.txt"
        without_sep.write_text(
            "+: Line 1\n"
            "+: Line 2\n"
            "+: Line 3\n"
            "+: Line 4\n"
            "+: Line 5\n"
            "+: Line 6\n"
            "+: Line 7\n"
            "+: Line 8\n"
            "+: Line 9\n"
            "+: Line 10\n"
            "+: Line 1\n"
            "+: Line 2\n"
            "+: Line 3\n"
            "+: Line 4\n"
            "+: Line 5\n"
            "+: Line 6\n"
            "+: Line 7\n"
            "+: Line 8\n"
            "+: Line 9\n"
            "+: Line 10\n"
        )

        # Run uniqseq on both
        result_with_sep = tmp_path / "result_with_sep.txt"
        result_without_sep = tmp_path / "result_without_sep.txt"

        cmd = ["uniqseq", "--track", r"^\+: ", "--quiet"]

        with open(with_sep) as stdin, open(result_with_sep, "w") as stdout:
            subprocess.run(cmd, stdin=stdin, stdout=stdout, check=True)

        with open(without_sep) as stdin, open(result_without_sep, "w") as stdout:
            subprocess.run(cmd, stdin=stdin, stdout=stdout, check=True)

        # Read results
        with open(result_with_sep) as f:
            lines_with_sep = f.readlines()

        with open(result_without_sep) as f:
            lines_without_sep = f.readlines()

        # Extract tracked lines only
        tracked_with_sep = [line for line in lines_with_sep if line.startswith("+: ")]
        tracked_without_sep = [line for line in lines_without_sep if line.startswith("+: ")]

        # Print diagnostics
        print("\n" + "=" * 70)
        print("NON-TRACKED INTERFERENCE TEST")
        print("=" * 70)
        print("\nWith separator:")
        print(f"  Total lines: {len(lines_with_sep)}")
        print(f"  Tracked lines: {len(tracked_with_sep)}")
        print("\nWithout separator:")
        print(f"  Total lines: {len(lines_without_sep)}")
        print(f"  Tracked lines: {len(tracked_without_sep)}")
        print("\nExpected: Both should have 10 tracked lines (duplicate detected)")
        print(
            f"Actual: With sep has {len(tracked_with_sep)}, without has {len(tracked_without_sep)}"
        )
        print("=" * 70 + "\n")

        # The CRITICAL requirement: tracked output must be identical
        assert tracked_with_sep == tracked_without_sep, (
            f"\nCRITICAL BUG: Non-tracked lines are affecting duplicate detection!\n"
            f"With separator: {len(tracked_with_sep)} tracked lines\n"
            f"Without separator: {len(tracked_without_sep)} tracked lines\n\n"
            f"Non-tracked lines must pass through unchanged AND have ZERO effect\n"
            f"on how tracked lines are deduplicated.\n\n"
            f"The presence of a non-tracked separator line is preventing\n"
            f"the duplicate 10-line sequence from being detected."
        )
