#!/usr/bin/env python3
"""Comprehensive benchmark for uniqseq performance."""

import io
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from uniqseq.uniqseq import UniqSeq


def generate_repeating_pattern(num_lines: int, pattern_length: int, num_repeats: int):
    """Generate test data with repeating patterns."""
    lines = []
    pattern_id = 0

    while len(lines) < num_lines:
        pattern = [f"Line {pattern_id}:{i} - Some content here" for i in range(pattern_length)]
        for _ in range(num_repeats):
            lines.extend(pattern)
            if len(lines) >= num_lines:
                break
        pattern_id += 1

    return lines[:num_lines]


def generate_unique_lines(num_lines: int):
    """Generate all unique lines (worst case for deduplication)."""
    return [f"Unique line {i} with content" for i in range(num_lines)]


def generate_mixed_pattern(num_lines: int):
    """Generate mixed patterns with varying repetition."""
    lines = []
    i = 0
    while len(lines) < num_lines:
        # Add some unique lines
        for _ in range(20):
            lines.append(f"Unique {i}")
            i += 1
            if len(lines) >= num_lines:
                break

        # Add a small repeating pattern (5x)
        pattern = [f"Small pattern {i}:{j}" for j in range(10)]
        for _ in range(5):
            lines.extend(pattern)
            if len(lines) >= num_lines:
                break

        # Add a large repeating pattern (3x)
        pattern = [f"Large pattern {i}:{j}" for j in range(50)]
        for _ in range(3):
            lines.extend(pattern)
            if len(lines) >= num_lines:
                break

        i += 1

    return lines[:num_lines]


def benchmark_workload(name: str, lines: list[str], window_size: int = 10):
    """Benchmark a specific workload."""
    output = io.StringIO()
    uniqseq = UniqSeq(window_size=window_size, max_history=100_000)

    start_time = time.time()

    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)

    elapsed = time.time() - start_time
    stats = uniqseq.get_stats()

    return {
        "name": name,
        "lines": len(lines),
        "elapsed": elapsed,
        "throughput": len(lines) / elapsed,
        "stats": stats,
    }


def main():
    """Run comprehensive benchmarks."""
    print("=" * 80)
    print("UNIQSEQ PERFORMANCE BENCHMARK")
    print("=" * 80)
    print()

    benchmarks = [
        # Different workload sizes
        ("Small (10k lines, heavy dup)", generate_repeating_pattern(10_000, 50, 5), 10),
        ("Medium (50k lines, heavy dup)", generate_repeating_pattern(50_000, 50, 5), 10),
        ("Large (100k lines, heavy dup)", generate_repeating_pattern(100_000, 50, 5), 10),
        # Different pattern characteristics
        ("100k lines, short patterns", generate_repeating_pattern(100_000, 10, 10), 10),
        ("100k lines, long patterns", generate_repeating_pattern(100_000, 100, 3), 10),
        ("100k lines, mixed patterns", generate_mixed_pattern(100_000), 10),
        ("100k lines, all unique (worst case)", generate_unique_lines(100_000), 10),
        # Different window sizes
        ("100k lines, window=5", generate_repeating_pattern(100_000, 50, 5), 5),
        ("100k lines, window=15", generate_repeating_pattern(100_000, 50, 5), 15),
        ("100k lines, window=20", generate_repeating_pattern(100_000, 50, 5), 20),
    ]

    results = []

    for name, lines, window_size in benchmarks:
        print(f"Running: {name}...")
        result = benchmark_workload(name, lines, window_size)
        results.append(result)

        print(f"  Time: {result['elapsed']:.3f}s")
        print(f"  Throughput: {result['throughput']:.0f} lines/sec")
        print(f"  Redundancy: {result['stats']['redundancy_pct']:.1f}%")
        print()

    # Print summary table
    print("=" * 80)
    print("SUMMARY TABLE")
    print("=" * 80)
    print()
    print(f"{'Workload':<40} {'Time (s)':<10} {'Lines/sec':<12} {'Redundancy':<12}")
    print("-" * 80)

    for result in results:
        print(
            f"{result['name']:<40} "
            f"{result['elapsed']:<10.3f} "
            f"{result['throughput']:<12.0f} "
            f"{result['stats']['redundancy_pct']:<12.1f}"
        )

    print()
    print("=" * 80)
    print("PERFORMANCE METRICS")
    print("=" * 80)
    print()

    # Find best and worst throughput
    best = max(results, key=lambda r: r["throughput"])
    worst = min(results, key=lambda r: r["throughput"])

    print(f"Best throughput:  {best['throughput']:.0f} lines/sec ({best['name']})")
    print(f"Worst throughput: {worst['throughput']:.0f} lines/sec ({worst['name']})")
    print(f"Range: {best['throughput'] / worst['throughput']:.2f}x variation")
    print()

    # Calculate average for 100k line benchmarks
    large_benchmarks = [r for r in results if r["lines"] >= 100_000]
    avg_throughput = sum(r["throughput"] for r in large_benchmarks) / len(large_benchmarks)
    print(f"Average throughput (100k lines): {avg_throughput:.0f} lines/sec")
    print()


if __name__ == "__main__":
    main()
