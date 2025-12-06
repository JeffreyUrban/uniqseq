#!/usr/bin/env python3
"""Detailed analysis of _update_new_sequence_records hotspot."""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uniqseq import UniqSeq


class InstrumentedUniqSeq(UniqSeq):
    """UniqSeq with instrumentation for hotspot analysis."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_calls = 0
        self.candidate_iterations = 0
        self.position_checks = 0
        self.dict_hits = 0
        self.dict_misses = 0
        self.set_operations = 0
        self.total_update_time = 0.0

    def _update_new_sequence_records(self, current_window_hash: str) -> None:
        """Instrumented version to track operations."""
        start = time.perf_counter()
        self.update_calls += 1

        position_to_entry = self.window_hash_history.position_to_entry

        for _candidate_id, candidate in self.new_sequence_records.items():
            self.candidate_iterations += 1

            if not candidate.matching_history_positions:
                continue

            # Count operations in set comprehension
            still_matching = set()
            for hist_pos in candidate.matching_history_positions:
                self.position_checks += 1
                entry = position_to_entry.get(hist_pos + 1)
                if entry is not None:
                    self.dict_hits += 1
                    if entry.window_hash == current_window_hash:
                        still_matching.add(hist_pos + 1)
                        self.set_operations += 1
                else:
                    self.dict_misses += 1

            # Update candidate
            if still_matching:
                candidate.matching_history_positions = still_matching
                candidate.length += 1
                candidate.buffer_depth += 1
                candidate.window_hashes.append(current_window_hash)
            else:
                candidate.matching_history_positions.clear()

        elapsed = time.perf_counter() - start
        self.total_update_time += elapsed

    def print_stats(self):
        """Print detailed statistics."""
        print("\n" + "=" * 80)
        print("HOTSPOT ANALYSIS - _update_new_sequence_records")
        print("=" * 80)
        print(f"\nFunction calls: {self.update_calls:,}")
        print(f"Total time spent: {self.total_update_time:.3f}s")
        print(
            f"Avg time per call: {self.total_update_time / max(1, self.update_calls) * 1000:.3f}ms"
        )
        print(f"\nCandidate iterations: {self.candidate_iterations:,}")
        print(
            f"Avg candidates per call: {self.candidate_iterations / max(1, self.update_calls):.1f}"
        )
        print(f"\nPosition checks: {self.position_checks:,}")
        hit_pct = self.dict_hits / max(1, self.position_checks) * 100
        miss_pct = self.dict_misses / max(1, self.position_checks) * 100
        print(f"Dict lookups (hits): {self.dict_hits:,} ({hit_pct:.1f}%)")
        print(f"Dict lookups (misses): {self.dict_misses:,} ({miss_pct:.1f}%)")
        print(f"Set additions: {self.set_operations:,}")
        ops_per_call = self.position_checks / max(1, self.update_calls)
        print(f"\nOperations per function call: {ops_per_call:.1f}")


def main():
    """Run instrumented analysis."""
    print("Generating test data...")

    # Generate realistic test data with long patterns that repeat
    lines = []

    # Create a 15-line pattern that repeats
    base_pattern = [f"Pattern line {i}" for i in range(15)]

    # Heavy duplication scenario - repeat the pattern many times
    for i in range(200):
        lines.extend(base_pattern)  # 15-line pattern
        # Add some unique lines between patterns
        if i % 10 == 0:
            lines.extend([f"Separator {i}-{j}" for j in range(5)])

    # Add more varied patterns
    for i in range(50):
        # Another 15-line pattern
        varied_pattern = [f"Variant {i} line {j}" for j in range(15)]
        lines.extend(varied_pattern)
        lines.extend(varied_pattern)  # Repeat it once

    print(f"Generated {len(lines):,} lines")
    print("\nProcessing with instrumentation...")

    # Create instrumented uniqseq
    uniqseq = InstrumentedUniqSeq(window_size=10, max_candidates=100)

    # Process lines (suppress output)
    import io

    output = io.StringIO()
    start = time.perf_counter()
    for line in lines:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)
    total_time = time.perf_counter() - start

    # Print results
    stats = uniqseq.get_stats()
    print(f"\nProcessing complete in {total_time:.3f}s")
    print(f"Total lines: {stats['total']:,}")
    print(f"Emitted: {stats['emitted']:,}")
    print(f"Skipped: {stats['skipped']:,}")
    print(f"Redundancy: {stats['redundancy_pct']:.1f}%")

    # Print instrumentation stats
    uniqseq.print_stats()

    # Calculate efficiency metrics
    print("\n" + "=" * 80)
    print("EFFICIENCY METRICS")
    print("=" * 80)

    hotspot_pct = (uniqseq.total_update_time / total_time) * 100
    print(f"\nHotspot percentage of total time: {hotspot_pct:.1f}%")

    if uniqseq.position_checks > 0:
        ops_per_second = uniqseq.position_checks / uniqseq.total_update_time
        print(f"Position checks per second: {ops_per_second:,.0f}")

        hit_rate = uniqseq.dict_hits / uniqseq.position_checks * 100
        print(f"Dict hit rate: {hit_rate:.1f}%")

        if uniqseq.dict_hits > 0:
            match_rate = uniqseq.set_operations / uniqseq.dict_hits * 100
            print(f"Hash match rate (when entry exists): {match_rate:.1f}%")


if __name__ == "__main__":
    main()
