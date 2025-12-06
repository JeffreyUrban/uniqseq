#!/usr/bin/env python3
"""Analyze candidate tracking behavior to identify optimization opportunities."""

import io
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from uniqseq.uniqseq import UniqSeq


def generate_test_data(num_lines: int, pattern_length: int = 50, num_repeats: int = 5):
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


class InstrumentedUniqSeq(UniqSeq):
    """UniqSeq with instrumentation for tracking candidate behavior."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.candidate_counts = []
        self.match_counts = []
        self.max_candidates = 0
        self.max_matches = 0
        self.total_candidate_updates = 0
        self.total_history_positions_checked = 0

    def _update_new_sequence_records(self, current_window_hash: str) -> None:
        """Instrumented version that tracks metrics."""
        # Track candidate count
        num_candidates = len(self.new_sequence_records)
        self.candidate_counts.append(num_candidates)
        self.max_candidates = max(self.max_candidates, num_candidates)

        # Count history positions being checked
        total_positions = sum(
            len(c.matching_history_positions) for c in self.new_sequence_records.values()
        )
        self.total_history_positions_checked += total_positions
        self.total_candidate_updates += 1

        # Call parent implementation
        super()._update_new_sequence_records(current_window_hash)

    def _update_potential_uniq_matches(self, current_window_hash: str, output) -> None:
        """Instrumented version that tracks match counts."""
        num_matches = len(self.potential_uniq_matches)
        self.match_counts.append(num_matches)
        self.max_matches = max(self.max_matches, num_matches)

        # Call parent implementation
        super()._update_potential_uniq_matches(current_window_hash, output)


def analyze_candidates():
    """Analyze candidate tracking behavior."""
    print("=" * 80)
    print("CANDIDATE TRACKING ANALYSIS")
    print("=" * 80)
    print()

    # Generate test data
    print("Generating test data (100k lines)...")
    lines = generate_test_data(100_000, pattern_length=50, num_repeats=5)
    print(f"Generated {len(lines)} lines")
    print()

    # Run with instrumentation
    output = io.StringIO()
    uniqseq = InstrumentedUniqSeq(window_size=10, max_history=100_000)

    print("Processing lines...")
    for line in lines:
        uniqseq.process_line(line, output)

    uniqseq.flush(output)
    print("Processing complete.")
    print()

    # Analyze results
    print("=" * 80)
    print("CANDIDATE TRACKING STATISTICS")
    print("=" * 80)
    print()

    avg_candidates = sum(uniqseq.candidate_counts) / len(uniqseq.candidate_counts)
    avg_matches = sum(uniqseq.match_counts) / len(uniqseq.match_counts)

    avg_positions_per_update = (
        uniqseq.total_history_positions_checked / uniqseq.total_candidate_updates
        if uniqseq.total_candidate_updates > 0
        else 0
    )

    print(f"Total candidate updates: {uniqseq.total_candidate_updates:,}")
    print(f"Total history positions checked: {uniqseq.total_history_positions_checked:,}")
    print()
    print(f"Average candidates per update: {avg_candidates:.2f}")
    print(f"Max candidates at once: {uniqseq.max_candidates}")
    print()
    print(f"Average matches per update: {avg_matches:.2f}")
    print(f"Max matches at once: {uniqseq.max_matches}")
    print()
    print(f"Average positions checked per update: {avg_positions_per_update:.2f}")
    print()

    # Percentile analysis
    sorted_candidates = sorted(uniqseq.candidate_counts)
    p50 = sorted_candidates[len(sorted_candidates) // 2]
    p90 = sorted_candidates[int(len(sorted_candidates) * 0.9)]
    p95 = sorted_candidates[int(len(sorted_candidates) * 0.95)]
    p99 = sorted_candidates[int(len(sorted_candidates) * 0.99)]

    print("Candidate count percentiles:")
    print(f"  50th percentile (median): {p50}")
    print(f"  90th percentile: {p90}")
    print(f"  95th percentile: {p95}")
    print(f"  99th percentile: {p99}")
    print()

    # Distribution analysis
    zero_candidates = sum(1 for c in uniqseq.candidate_counts if c == 0)
    few_candidates = sum(1 for c in uniqseq.candidate_counts if 0 < c <= 10)
    many_candidates = sum(1 for c in uniqseq.candidate_counts if c > 10)

    total = len(uniqseq.candidate_counts)
    print("Candidate count distribution:")
    print(f"  Zero candidates: {zero_candidates:,} ({100 * zero_candidates / total:.1f}%)")
    print(f"  1-10 candidates: {few_candidates:,} ({100 * few_candidates / total:.1f}%)")
    print(f"  >10 candidates: {many_candidates:,} ({100 * many_candidates / total:.1f}%)")
    print()

    # Deduplication stats
    stats = uniqseq.get_stats()
    print("=" * 80)
    print("DEDUPLICATION STATISTICS")
    print("=" * 80)
    print(f"Total lines: {stats['total']:,}")
    print(f"Emitted: {stats['emitted']:,}")
    print(f"Skipped: {stats['skipped']:,}")
    print(f"Redundancy: {stats['redundancy_pct']:.1f}%")
    print(f"Unique sequences: {stats['unique_sequences']:,}")
    print()

    # Optimization recommendations
    print("=" * 80)
    print("OPTIMIZATION RECOMMENDATIONS")
    print("=" * 80)
    print()

    if uniqseq.max_candidates > 50:
        print(f"⚠️  High candidate count detected (max: {uniqseq.max_candidates})")
        print("   Recommendation: Implement candidate limiting")
        print()

    if avg_positions_per_update > 100:
        print(f"⚠️  Many positions checked per update (avg: {avg_positions_per_update:.0f})")
        print("   Recommendation: Consider position pruning or early termination")
        print()

    if p99 > 20:
        print(f"⚠️  99th percentile has {p99} candidates")
        print("   Recommendation: Cap candidates at 20-30 for consistent performance")
        print()


if __name__ == "__main__":
    analyze_candidates()
