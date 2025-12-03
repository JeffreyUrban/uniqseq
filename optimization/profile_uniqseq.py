#!/usr/bin/env python3
"""Profile uniqseq to identify performance bottlenecks."""

import cProfile
import io
import pstats
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from uniqseq.uniqseq import UniqSeq


def generate_test_data(num_lines: int, pattern_length: int = 100, num_repeats: int = 10):
    """Generate test data with repeating patterns.

    Args:
        num_lines: Total number of lines to generate
        pattern_length: Length of each repeating pattern
        num_repeats: How many times each pattern repeats
    """
    lines = []
    pattern_id = 0

    while len(lines) < num_lines:
        # Generate a pattern
        pattern = []
        for i in range(pattern_length):
            pattern.append(f"Line {pattern_id}:{i} - Some content here with data")

        # Repeat the pattern
        for _ in range(num_repeats):
            lines.extend(pattern)
            if len(lines) >= num_lines:
                break

        pattern_id += 1

    return lines[:num_lines]


def profile_uniqseq():
    """Profile uniqseq with various workloads."""

    print("Generating test data...")
    # Generate 100k lines with repeating patterns
    lines = generate_test_data(100_000, pattern_length=50, num_repeats=5)

    print(f"Generated {len(lines)} lines")
    print("Starting profiling...")

    # Profile with cProfile
    profiler = cProfile.Profile()
    profiler.enable()

    # Run uniqseq
    output = io.StringIO()
    uniqseq = UniqSeq(window_size=10, max_history=100_000)

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    profiler.disable()

    # Print stats
    stats = pstats.Stats(profiler, stream=sys.stdout)

    print("\n" + "=" * 80)
    print("PROFILING RESULTS - Top 30 functions by cumulative time")
    print("=" * 80)
    stats.sort_stats("cumulative")
    stats.print_stats(30)

    print("\n" + "=" * 80)
    print("PROFILING RESULTS - Top 30 functions by total time (tottime)")
    print("=" * 80)
    stats.sort_stats("tottime")
    stats.print_stats(30)

    print("\n" + "=" * 80)
    print("PROFILING RESULTS - Calls sorted by tottime")
    print("=" * 80)
    stats.sort_stats("tottime")
    stats.print_stats("uniqseq", 50)

    # Print summary stats
    stats_obj = uniqseq.get_stats()
    print("\n" + "=" * 80)
    print("DEDUPLICATION STATISTICS")
    print("=" * 80)
    print(f"Total lines: {stats_obj['total']}")
    print(f"Emitted: {stats_obj['emitted']}")
    print(f"Skipped: {stats_obj['skipped']}")
    print(f"Redundancy: {stats_obj['redundancy_pct']:.2f}%")
    print(f"Unique sequences: {stats_obj['unique_sequences']}")


if __name__ == "__main__":
    profile_uniqseq()
