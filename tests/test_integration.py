"""Integration tests for end-to-end scenarios."""

from io import StringIO

import pytest

from uniqseq.uniqseq import UniqSeq


@pytest.mark.integration
class TestIntegration:
    """End-to-end integration tests with realistic scenarios."""

    def test_typical_log_output(self):
        """Simulated log file with repeated status updates."""
        # Simulate a log with repeated progress messages
        lines = [
            "Starting process...",
            "Loading module A",
            "Loading module B",
            "Loading module C",
            "Processing item 1",
            "Processing item 2",
            "Loading module A",  # Duplicate sequence starts
            "Loading module B",
            "Loading module C",
            "Status: 50% complete",
            "Processing item 3",
            "Processing item 4",
            "Loading module A",  # Another duplicate
            "Loading module B",
            "Loading module C",
            "Done!",
        ]

        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Should detect and skip the two duplicate "Loading module" sequences
        assert uniqseq.lines_skipped == 6
        assert "Loading module A" in output_lines
        assert "Loading module B" in output_lines
        assert "Loading module C" in output_lines
        assert "Done!" in output_lines

    def test_build_output_with_warnings(self):
        """Simulated build output with repeated warnings."""
        lines = [
            "Compiling file1.c",
            "Warning: unused variable 'x'",
            "Warning: deprecated function",
            "Compiling file2.c",
            "Warning: unused variable 'x'",  # Duplicate sequence
            "Warning: deprecated function",
            "Compiling file3.c",
            "Build complete",
        ]

        uniqseq = UniqSeq(window_size=2)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Should skip duplicate warning sequence
        assert uniqseq.lines_skipped == 2
        assert "Build complete" in output_lines

    def test_interactive_cli_session(self):
        """Simulated interactive CLI with repeated prompts."""
        lines = [
            "$ help",
            "Available commands:",
            "  start - Start the service",
            "  stop - Stop the service",
            "$ status",
            "Service is running",
            "$ help",  # User types help again
            "Available commands:",
            "  start - Start the service",
            "  stop - Stop the service",
            "$ exit",
        ]

        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Should detect duplicate help output (4 lines: 3 command lines + $ help)
        assert uniqseq.lines_skipped == 4
        assert "$ exit" in output_lines

    def test_test_suite_output(self):
        """Simulated test suite with repeated test patterns."""
        lines = [
            "Running tests...",
            "test_feature_a ... ok",
            "test_feature_b ... ok",
            "test_feature_c ... FAILED",
            "Traceback:",
            "  File test.py, line 10",
            "    assert x == 1",
            "AssertionError",
            "Rerunning failed tests...",
            "test_feature_c ... FAILED",
            "Traceback:",  # Duplicate traceback
            "  File test.py, line 10",
            "    assert x == 1",
            "AssertionError",
            "2 passed, 1 failed",
        ]

        uniqseq = UniqSeq(window_size=4)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Should detect duplicate traceback (5 lines including "Traceback:" + 3 lines + "AssertionError")
        assert uniqseq.lines_skipped == 5
        assert "2 passed, 1 failed" in output_lines

    def test_database_query_results(self):
        """Simulated database query with repeated result sets."""
        lines = [
            "Query: SELECT * FROM users",
            "id | name  | email",
            "1  | Alice | alice@example.com",
            "2  | Bob   | bob@example.com",
            "Query: SELECT * FROM users WHERE active=1",
            "id | name  | email",  # Duplicate header sequence
            "1  | Alice | alice@example.com",
            "2  | Bob   | bob@example.com",
            "Query complete",
        ]

        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Should detect duplicate result rows
        assert uniqseq.lines_skipped == 3
        assert "Query complete" in output_lines

    def test_nested_duplicates(self):
        """Nested duplicate patterns."""
        # Pattern A-B-C appears, then A-B-C-D-E, then A-B-C again
        lines = [
            "A",
            "B",
            "C",
            "D",
            "E",
            "A",
            "B",
            "C",
            "D",
            "E",  # Should match longer sequence
            "F",
            "A",
            "B",
            "C",  # Should match original
        ]

        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Both duplicates should be detected
        assert uniqseq.lines_skipped >= 3
        assert "F" in output_lines

    def test_progress_bar_updates(self):
        """Simulated progress bar with repeated update patterns."""
        lines = [
            "Download starting...",
            "[          ] 0%",
            "Downloading chunk 1",
            "[==        ] 20%",
            "Downloading chunk 2",
            "[====      ] 40%",
            "Downloading chunk 3",
            "[======    ] 60%",
            "Downloading chunk 4",
            "[========  ] 80%",
            "Downloading chunk 5",
            "[==========] 100%",
            "Download complete!",
        ]

        uniqseq = UniqSeq(window_size=2)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Progress bars are all unique, should not be deduplicated
        assert uniqseq.lines_skipped == 0

    def test_multiline_error_messages(self):
        """Repeated multi-line error messages."""
        error_block = [
            "ERROR: Connection failed",
            "Reason: Timeout after 30s",
            "Retrying in 5 seconds...",
        ]

        lines = []
        lines.extend(["Starting service..."])
        lines.extend(error_block)
        lines.extend(["Attempt 1 failed"])
        lines.extend(error_block)  # Duplicate error
        lines.extend(["Attempt 2 failed"])
        lines.extend(error_block)  # Another duplicate
        lines.extend(["Service failed to start"])

        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Should skip 2 duplicate error blocks (6 lines total)
        assert uniqseq.lines_skipped == 6
        assert "Service failed to start" in output_lines

    def test_configuration_dump_repeated(self):
        """Configuration dump that appears multiple times."""
        config_block = ["Configuration:", "  host: localhost", "  port: 8080", "  debug: true"]

        lines = []
        lines.extend(["Initializing..."])
        lines.extend(config_block)
        lines.extend(["Server started"])
        lines.extend(["Reloading configuration..."])
        lines.extend(config_block)  # Duplicate config dump
        lines.extend(["Configuration reloaded"])

        uniqseq = UniqSeq(window_size=4)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Should skip duplicate config block
        assert uniqseq.lines_skipped == 4
        assert "Configuration reloaded" in output_lines

    def test_mixed_duplicate_and_unique(self):
        """Mix of duplicate and unique sequences."""
        lines = [
            "Unique line 1",
            "Pattern A",
            "Pattern B",
            "Pattern C",
            "Unique line 2",
            "Different pattern X",
            "Different pattern Y",
            "Different pattern Z",
            "Unique line 3",
            "Pattern A",  # Duplicate of first pattern
            "Pattern B",
            "Pattern C",
            "Unique line 4",
            "Different pattern X",  # Duplicate of second pattern
            "Different pattern Y",
            "Different pattern Z",
            "Unique line 5",
        ]

        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Should skip both duplicate patterns (6 lines total)
        assert uniqseq.lines_skipped == 6
        # All unique lines should be present
        for i in range(1, 6):
            assert f"Unique line {i}" in output_lines

    def test_streaming_with_flush(self):
        """Test streaming behavior with explicit flush."""
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        # Process first batch
        for line in ["A", "B", "C", "D"]:
            uniqseq.process_line(line, output)

        # Don't flush yet - lines still in buffer

        # Process duplicate sequence
        for line in ["A", "B", "C"]:
            uniqseq.process_line(line, output)

        # Now flush
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Should detect duplicate
        assert uniqseq.lines_skipped == 3
        assert "D" in output_lines

    def test_very_long_duplicate_sequence(self):
        """Very long duplicate sequence (50+ lines)."""
        # Create a long repeated block
        long_block = [f"Line {i}" for i in range(50)]

        lines = []
        lines.extend(["Start"])
        lines.extend(long_block)
        lines.extend(["Middle"])
        lines.extend(long_block)  # Duplicate
        lines.extend(["End"])

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = [l for l in output.getvalue().split("\n") if l]

        # Should skip entire duplicate block
        assert uniqseq.lines_skipped == 50
        assert "Start" in output_lines
        assert "Middle" in output_lines
        assert "End" in output_lines
        assert "Line 0" in output_lines

    def test_statistics_accuracy(self):
        """Verify statistics are accurate for complex scenario."""
        lines = ["A"] * 5 + ["B"] * 5 + ["A"] * 5  # A×5, B×5, A×5

        uniqseq = UniqSeq(window_size=5)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Verify statistics
        stats = uniqseq.get_stats()
        assert stats["total"] == 15
        assert stats["emitted"] + stats["skipped"] == 15
        assert stats["total"] == stats["emitted"] + stats["skipped"]
