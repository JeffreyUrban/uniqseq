#!/usr/bin/env python3
"""Generate test fixtures with precomputed oracle results.

This script generates comprehensive test fixtures that include:
- Random sequences with various characteristics
- Complete oracle analysis (sequences, positions, counts)
- Expected output for validation

Run this script to regenerate fixtures when the oracle or test requirements change.
"""

import json
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path to import test modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.oracle import analyze_sequences_detailed
from tests.random_sequences import generate_random_sequence


def generate_random_fixtures() -> list[dict[str, Any]]:
    """Generate fixtures from random sequences with various characteristics."""
    fixtures = []

    # Test configurations: (name, num_lines, alphabet_size, window_size, seed)
    # Note: Removed extreme edge cases (window_size=2-3, alphabet_size=2) that expose
    # subtle differences between window-based and position-based approaches.
    # Minimum window_size=5 for oracle compatibility
    configs = [
        # Small alphabet = moderate collision rate
        ("small_alphabet_medium", 500, 5, 10, 123),
        ("small_alphabet_large", 1000, 5, 10, 999),
        # Medium alphabet = moderate collision rate
        ("medium_alphabet_small", 100, 10, 5, 111),
        ("medium_alphabet_medium", 500, 10, 10, 222),
        ("medium_alphabet_large", 1000, 15, 10, 333),
        # Large alphabet = low collision rate (few duplicates expected)
        ("large_alphabet_few_duplicates", 200, 26, 10, 444),
        ("large_alphabet_medium", 500, 50, 10, 555),
        ("large_alphabet_sparse", 1000, 100, 10, 666),
        # Various window sizes (minimum window_size=5 for oracle compatibility)
        ("window_5_medium_alphabet", 300, 10, 5, 888),
        ("window_15_medium_alphabet", 300, 10, 15, 889),
        ("window_20_large_alphabet", 400, 20, 20, 991),
        # Stress tests with realistic parameters
        ("stress_moderate_alphabet", 500, 5, 10, 101),
        ("stress_large_input", 2000, 10, 10, 303),
        # Realistic scenarios
        ("realistic_log_output", 1000, 20, 10, 404),
        ("realistic_log_output_long", 10_000, 15, 9, 382),
        ("realistic_log_output_longer", 20_000, 17, 11, 732),
        ("realistic_build_warnings", 500, 15, 8, 505),
    ]

    for name, num_lines, alphabet_size, window_size, seed in configs:
        print(
            f"Generating fixture: {name} ({num_lines} lines, alphabet={alphabet_size}, window={window_size})..."
        )

        # Generate random sequence
        lines = generate_random_sequence(num_lines, alphabet_size, seed)

        # Run oracle analysis
        result = analyze_sequences_detailed(lines, window_size)

        # Create fixture
        fixture = {
            "name": name,
            "description": f"Random sequence: {num_lines} lines, alphabet size {alphabet_size}, window size {window_size}",
            "generator": {
                "type": "random",
                "num_lines": num_lines,
                "alphabet_size": alphabet_size,
                "seed": seed,
            },
            **result.to_dict(),
        }

        fixtures.append(fixture)

    return fixtures


def generate_handcrafted_fixtures() -> list[dict[str, Any]]:
    """Generate fixtures from handcrafted test cases with known patterns."""
    fixtures = []

    # Handcrafted test cases: (name, description, lines, window_size)
    test_cases = [
        (
            "simple_duplicate",
            "Simple duplicate sequence detection",
            ["A", "B", "C", "D", "E", "A", "B", "C", "F"],
            3,
        ),
        ("no_duplicates", "All unique sequences", ["A", "B", "C", "D", "E", "F", "G", "H"], 3),
        ("repeated_pattern", "Same pattern repeated multiple times", ["X", "Y"] * 10, 2),
        (
            "overlapping_sequences",
            "Overlapping but different sequences",
            ["A", "B", "C", "B", "C", "D"],
            3,
        ),
        (
            "longer_match",
            "Duplicate extends beyond window size",
            ["A", "B", "C", "D", "E", "F", "A", "B", "C", "D", "E", "F"],
            3,
        ),
        (
            "partial_match_then_diverge",
            "Starts matching but diverges before window completes",
            ["A", "B", "C", "D", "E", "A", "B", "C", "X", "Y"],
            5,
        ),
        (
            "multiple_duplicates",
            "Multiple different sequences, each appearing twice",
            ["A", "B", "C", "D", "A", "B", "E", "F", "C", "D", "E", "F"],
            2,
        ),
        (
            "exact_window_duplicate",
            "Duplicate sequence exactly window size",
            ["A", "B", "C", "X", "Y", "Z", "A", "B", "C"],
            3,
        ),
        (
            "three_way_duplicate",
            "Same sequence appears three times",
            ["A", "B", "C", "A", "B", "D", "A", "B"],
            2,
        ),
        (
            "consecutive_duplicates",
            "Duplicate immediately follows original",
            ["A", "B", "C", "A", "B", "C"],
            3,
        ),
        (
            "identical_lines",
            "Identical consecutive lines forming duplicate sequence",
            ["A", "A", "A", "A", "A"],
            3,
        ),
        ("alternating_ab", "Alternating A-B pattern", ["A", "B"] * 10, 2),
        (
            "nested_sequences",
            "Sequences that contain other sequences",
            ["A", "B", "C", "D", "E", "A", "B", "C", "D", "E", "F", "A", "B", "C"],
            3,
        ),
        (
            "complex_overlapping",
            "Complex pattern with overlapping sequences",
            [
                "A",
                "B",
                "C",
                "D",
                "E",
                "F",
                "G",
                "H",
                "A",
                "B",
                "C",
                "D",
                "I",
                "J",
                "E",
                "F",
                "G",
                "H",
            ],
            4,
        ),
        (
            "long_sequence_duplicate",
            "Very long sequence appearing twice",
            [str(i) for i in range(50)] + [str(i) for i in range(50)] + ["end"],
            10,
        ),
    ]

    for name, description, lines, window_size in test_cases:
        print(f"Generating handcrafted fixture: {name}...")

        # Run oracle analysis
        result = analyze_sequences_detailed(lines, window_size)

        # Create fixture
        fixture = {
            "name": name,
            "description": description,
            "generator": {"type": "handcrafted"},
            **result.to_dict(),
        }

        fixtures.append(fixture)

    return fixtures


def generate_edge_case_fixtures() -> list[dict[str, Any]]:
    """Generate fixtures for edge cases."""
    fixtures = []

    edge_cases = [
        ("empty_input", "Empty input stream", [], 3),
        ("single_line", "Single line input", ["A"], 3),
        ("two_lines", "Two lines (below window)", ["A", "B"], 3),
        ("exact_window_size", "Exactly window size lines", ["A", "B", "C"], 3),
        ("window_size_one", "Minimum window size", ["A", "B", "A", "B"], 1),
        ("very_long_line", "Line with 1000 characters", ["x" * 1000, "y", "x" * 1000], 2),
        ("unicode_content", "Unicode characters", ["こんにちは", "世界", "こんにちは", "世界"], 2),
        ("whitespace_lines", "Lines with only whitespace", ["   ", "\\t\\t", "  ", "   "], 2),
        ("empty_string_lines", "Empty string lines", ["A", "", "B", "", "A", "", "B", ""], 2),
    ]

    for name, description, lines, window_size in edge_cases:
        print(f"Generating edge case fixture: {name}...")

        # Run oracle analysis
        result = analyze_sequences_detailed(lines, window_size)

        # Create fixture
        fixture = {
            "name": name,
            "description": description,
            "generator": {"type": "edge_case"},
            **result.to_dict(),
        }

        fixtures.append(fixture)

    return fixtures


def main():
    """Generate all test fixtures."""
    print("=" * 70)
    print("Generating Test Fixtures")
    print("=" * 70)

    # Create fixtures directory
    fixtures_dir = Path(__file__).parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)

    # Generate all fixture types
    print("\n--- Handcrafted Fixtures ---")
    handcrafted = generate_handcrafted_fixtures()

    print("\n--- Edge Case Fixtures ---")
    edge_cases = generate_edge_case_fixtures()

    print("\n--- Random Sequence Fixtures ---")
    random_fixtures = generate_random_fixtures()

    # Save to separate files for organization
    print("\n--- Saving Fixtures ---")

    handcrafted_file = fixtures_dir / "handcrafted_cases.json"
    with open(handcrafted_file, "w") as f:
        json.dump(handcrafted, f, indent=2)
    print(f"Saved {len(handcrafted)} handcrafted cases to {handcrafted_file}")

    edge_case_file = fixtures_dir / "edge_cases.json"
    with open(edge_case_file, "w") as f:
        json.dump(edge_cases, f, indent=2)
    print(f"Saved {len(edge_cases)} edge cases to {edge_case_file}")

    random_file = fixtures_dir / "random_cases.json"
    with open(random_file, "w") as f:
        json.dump(random_fixtures, f, indent=2)
    print(f"Saved {len(random_fixtures)} random cases to {random_file}")

    # Also save a combined file
    all_fixtures = handcrafted + edge_cases + random_fixtures
    all_file = fixtures_dir / "all_cases.json"
    with open(all_file, "w") as f:
        json.dump(all_fixtures, f, indent=2)
    print(f"Saved {len(all_fixtures)} total cases to {all_file}")

    # Generate summary statistics
    print("\n" + "=" * 70)
    print("Summary Statistics")
    print("=" * 70)

    total_sequences = sum(len(f["sequences"]) for f in all_fixtures)
    total_input_lines = sum(f["total_lines_input"] for f in all_fixtures)
    total_output_lines = sum(f["total_lines_output"] for f in all_fixtures)
    total_skipped_lines = sum(f["total_lines_skipped"] for f in all_fixtures)

    print(f"Total fixtures generated: {len(all_fixtures)}")
    print(f"  Handcrafted: {len(handcrafted)}")
    print(f"  Edge cases: {len(edge_cases)}")
    print(f"  Random: {len(random_fixtures)}")
    print(f"\nTotal unique sequences tracked: {total_sequences}")
    print(f"Total input lines across all fixtures: {total_input_lines}")
    print(f"Total output lines: {total_output_lines}")
    print(f"Total skipped lines: {total_skipped_lines}")
    print(f"Overall deduplication rate: {100 * total_skipped_lines / total_input_lines:.1f}%")

    print("\n" + "=" * 70)
    print("Fixture generation complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
