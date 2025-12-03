#!/usr/bin/env python3
"""Test different optimization approaches for the hotspot."""

import time


# Simulate the data structures
class Entry:
    __slots__ = ("window_hash",)

    def __init__(self, window_hash: str):
        self.window_hash = window_hash


def approach_1_original(
    position_to_entry: dict[int, Entry], matching_positions: set[int], target_hash: str
) -> set[int]:
    """Original approach with walrus operator."""
    still_matching = {
        hist_pos + 1
        for hist_pos in matching_positions
        if (entry := position_to_entry.get(hist_pos + 1)) is not None
        and entry.window_hash == target_hash
    }
    return still_matching


def approach_2_separate_lookup(
    position_to_entry: dict[int, Entry], matching_positions: set[int], target_hash: str
) -> set[int]:
    """Separate dict lookup from hash comparison."""
    still_matching = set()
    for hist_pos in matching_positions:
        next_pos = hist_pos + 1
        entry = position_to_entry.get(next_pos)
        if entry is not None and entry.window_hash == target_hash:
            still_matching.add(next_pos)
    return still_matching


def approach_3_try_except(
    position_to_entry: dict[int, Entry], matching_positions: set[int], target_hash: str
) -> set[int]:
    """Use try/except for dict access (EAFP style)."""
    still_matching = set()
    for hist_pos in matching_positions:
        next_pos = hist_pos + 1
        try:
            if position_to_entry[next_pos].window_hash == target_hash:
                still_matching.add(next_pos)
        except KeyError:
            pass
    return still_matching


def approach_4_precompute_positions(
    position_to_entry: dict[int, Entry], matching_positions: set[int], target_hash: str
) -> set[int]:
    """Precompute next positions."""
    next_positions = {pos + 1 for pos in matching_positions}
    still_matching = {
        pos
        for pos in next_positions
        if (entry := position_to_entry.get(pos)) is not None and entry.window_hash == target_hash
    }
    return still_matching


def approach_5_list_comprehension(
    position_to_entry: dict[int, Entry], matching_positions: set[int], target_hash: str
) -> set[int]:
    """Use list comprehension then convert to set."""
    next_positions = [pos + 1 for pos in matching_positions]
    still_matching = {
        pos
        for pos in next_positions
        if (entry := position_to_entry.get(pos)) is not None and entry.window_hash == target_hash
    }
    return still_matching


def benchmark_approaches():
    """Benchmark different approaches."""
    # Setup test data
    print("Setting up test data...")

    # Create 10,000 entries
    position_to_entry = {i: Entry(f"hash_{i % 100}") for i in range(10000)}

    # Create test scenarios
    scenarios = [
        ("Small set (10 items)", {100, 200, 300, 400, 500, 600, 700, 800, 900, 1000}),
        ("Medium set (50 items)", set(range(1000, 1050))),
        ("Large set (100 items)", set(range(2000, 2100))),
    ]

    approaches = [
        ("Original (walrus)", approach_1_original),
        ("Separate lookup", approach_2_separate_lookup),
        ("Try/except", approach_3_try_except),
        ("Precompute positions", approach_4_precompute_positions),
        ("List comprehension", approach_5_list_comprehension),
    ]

    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)

    for scenario_name, matching_positions in scenarios:
        print(f"\n{scenario_name}:")
        print("-" * 80)

        target_hash = "hash_5"  # This will match about 1% of entries
        results = {}

        for approach_name, approach_func in approaches:
            # Warmup
            for _ in range(100):
                approach_func(position_to_entry, matching_positions, target_hash)

            # Benchmark
            iterations = 10000
            start = time.perf_counter()
            for _ in range(iterations):
                result = approach_func(position_to_entry, matching_positions, target_hash)
            elapsed = time.perf_counter() - start

            results[approach_name] = (elapsed, result)

            per_iteration = (elapsed / iterations) * 1_000_000  # microseconds
            print(f"  {approach_name:25s}: {per_iteration:7.2f} μs/iter ({elapsed:.4f}s total)")

        # Verify all approaches give same result
        first_result = None
        for approach_name, (_, result) in results.items():
            if first_result is None:
                first_result = result
            elif result != first_result:
                print(f"  WARNING: {approach_name} gave different result!")

        # Find fastest
        fastest_name = min(results.keys(), key=lambda k: results[k][0])
        baseline = results["Original (walrus)"][0]
        fastest_time = results[fastest_name][0]
        speedup = baseline / fastest_time
        print(f"\n  Fastest: {fastest_name} ({speedup:.2f}x vs original)")


if __name__ == "__main__":
    benchmark_approaches()
