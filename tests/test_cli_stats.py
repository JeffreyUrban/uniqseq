"""Tests for CLI statistics printing."""

from io import StringIO

import pytest
from uniqseq.cli import print_stats
from uniqseq.deduplicator import StreamingDeduplicator


@pytest.mark.unit
def test_print_stats_normal():
    """Test print_stats with normal deduplicator."""
    dedup = StreamingDeduplicator(window_size=10, max_history=1000)

    # Process some lines
    output = StringIO()
    for i in range(30):
        dedup.process_line(f"line{i % 10}", output)
    dedup.flush(output)

    # print_stats writes to stderr via rich Console
    # Just verify it doesn't crash
    print_stats(dedup)


@pytest.mark.unit
def test_print_stats_empty():
    """Test print_stats with no lines processed."""
    dedup = StreamingDeduplicator(window_size=10, max_history=1000)

    # print_stats should handle empty stats
    print_stats(dedup)


@pytest.mark.unit
def test_print_stats_all_duplicates():
    """Test print_stats when everything is duplicated."""
    dedup = StreamingDeduplicator(window_size=5, max_history=1000)

    output = StringIO()
    # First occurrence
    for i in range(10):
        dedup.process_line(f"line{i}", output)

    # Duplicate
    for i in range(10):
        dedup.process_line(f"line{i}", output)

    dedup.flush(output)

    # Verify stats make sense
    stats = dedup.get_stats()
    assert stats["skipped"] > 0

    # print_stats should work
    print_stats(dedup)


@pytest.mark.unit
def test_print_stats_no_duplicates():
    """Test print_stats when there are no duplicates."""
    dedup = StreamingDeduplicator(window_size=10, max_history=1000)

    output = StringIO()
    for i in range(20):
        dedup.process_line(f"unique_line_{i}", output)
    dedup.flush(output)

    stats = dedup.get_stats()
    assert stats["skipped"] == 0

    print_stats(dedup)
