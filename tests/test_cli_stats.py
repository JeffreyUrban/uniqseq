"""Tests for CLI statistics printing."""

from io import StringIO

import pytest

from uniqseq.cli import print_stats
from uniqseq.uniqseq import UniqSeq


@pytest.mark.unit
def test_print_stats_normal():
    """Test print_stats with normal uniqseq."""
    uniqseq = UniqSeq(window_size=10, max_history=1000)

    # Process some lines
    output = StringIO()
    for i in range(30):
        uniqseq.process_line(f"line{i % 10}", output)
    uniqseq.flush(output)

    # print_stats writes to stderr via rich Console
    # Just verify it doesn't crash
    print_stats(uniqseq)


@pytest.mark.unit
def test_print_stats_empty():
    """Test print_stats with no lines processed."""
    uniqseq = UniqSeq(window_size=10, max_history=1000)

    # print_stats should handle empty stats
    print_stats(uniqseq)


@pytest.mark.unit
def test_print_stats_all_duplicates():
    """Test print_stats when everything is duplicated."""
    uniqseq = UniqSeq(window_size=5, max_history=1000)

    output = StringIO()
    # First occurrence
    for i in range(10):
        uniqseq.process_line(f"line{i}", output)

    # Duplicate
    for i in range(10):
        uniqseq.process_line(f"line{i}", output)

    uniqseq.flush(output)

    # Verify stats make sense
    stats = uniqseq.get_stats()
    assert stats["skipped"] > 0

    # print_stats should work
    print_stats(uniqseq)


@pytest.mark.unit
def test_print_stats_no_duplicates():
    """Test print_stats when there are no duplicates."""
    uniqseq = UniqSeq(window_size=10, max_history=1000)

    output = StringIO()
    for i in range(20):
        uniqseq.process_line(f"unique_line_{i}", output)
    uniqseq.flush(output)

    stats = uniqseq.get_stats()
    assert stats["skipped"] == 0

    print_stats(uniqseq)
