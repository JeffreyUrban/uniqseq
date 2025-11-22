"""Tests using precomputed expected outputs."""

import json
import pytest
from pathlib import Path
from io import StringIO
from uniqseq.deduplicator import StreamingDeduplicator


def load_test_cases():
    """Load precomputed test cases from JSON file."""
    fixtures_path = Path(__file__).parent / "fixtures" / "precomputed_cases.json"
    with open(fixtures_path, 'r') as f:
        return json.load(f)


TEST_CASES = load_test_cases()


@pytest.mark.unit
class TestPrecomputedCases:
    """Test against precomputed expected outputs."""

    @pytest.mark.parametrize("test_case", TEST_CASES, ids=[tc["name"] for tc in TEST_CASES])
    def test_precomputed_case(self, test_case):
        """Run precomputed test case."""
        name = test_case["name"]
        window_size = test_case["window_size"]
        input_lines = test_case["input"]
        expected_output = test_case["expected_output"]
        expected_skipped = test_case["expected_skipped"]

        # Run deduplicator
        dedup = StreamingDeduplicator(window_size=window_size)
        output = StringIO()

        for line in input_lines:
            dedup.process_line(line, output)
        dedup.flush(output)

        # Parse output
        output_lines = [l for l in output.getvalue().split('\n') if l]

        # Verify output matches expected
        assert output_lines == expected_output, \
            f"Test case '{name}': output mismatch"

        # Verify skip count matches expected
        assert dedup.lines_skipped == expected_skipped, \
            f"Test case '{name}': expected {expected_skipped} skipped, got {dedup.lines_skipped}"

        # Verify line conservation invariant
        assert dedup.line_num_input == dedup.line_num_output + dedup.lines_skipped, \
            f"Test case '{name}': line conservation violated"

    def test_all_cases_loaded(self):
        """Verify test cases loaded successfully."""
        assert len(TEST_CASES) > 0, "No test cases loaded from JSON"
        assert len(TEST_CASES) >= 10, f"Expected at least 10 test cases, got {len(TEST_CASES)}"

    def test_case_structure(self):
        """Verify all test cases have required fields."""
        required_fields = {"name", "description", "window_size", "input", "expected_output", "expected_skipped"}

        for test_case in TEST_CASES:
            missing = required_fields - set(test_case.keys())
            assert not missing, \
                f"Test case '{test_case.get('name', 'unknown')}' missing fields: {missing}"

    def test_case_validity(self):
        """Verify test cases have valid data."""
        for test_case in TEST_CASES:
            name = test_case["name"]

            # Window size must be positive
            assert test_case["window_size"] > 0, \
                f"Test case '{name}': window_size must be positive"

            # Skipped count must be non-negative
            assert test_case["expected_skipped"] >= 0, \
                f"Test case '{name}': expected_skipped must be non-negative"

            # Input and output must be lists
            assert isinstance(test_case["input"], list), \
                f"Test case '{name}': input must be a list"
            assert isinstance(test_case["expected_output"], list), \
                f"Test case '{name}': expected_output must be a list"

            # Output cannot exceed input
            assert len(test_case["expected_output"]) <= len(test_case["input"]), \
                f"Test case '{name}': output cannot have more lines than input"

            # Conservation law
            input_count = len(test_case["input"])
            output_count = len(test_case["expected_output"])
            skipped_count = test_case["expected_skipped"]

            assert input_count == output_count + skipped_count, \
                f"Test case '{name}': conservation law violated: " \
                f"{input_count} input != {output_count} output + {skipped_count} skipped"
