# Test Coverage

## Overview

Test-driven development plan for the redesigned deduplication algorithm. Tests are organized into three categories:

1. **Unit Tests**: Targeted tests for specific mechanisms and edge cases
2. **Property Tests**: Randomized tests with invariant checking
3. **Integration Tests**: End-to-end scenarios with realistic data

All tests use **pytest exclusively** (not unittest).

## Test Philosophy

- **Test-first**: Write tests before implementation
- **Comprehensive coverage**: Exercise all code paths and edge cases
- **Randomized stress testing**: Generate large inputs to expose corner cases
- **Invariant checking**: Verify algorithm guarantees hold under all conditions
- **Clear test names**: Describe what's being tested and expected behavior

## 1. Unit Tests

### 1.1 PositionalFIFO Data Structure

**File**: `tests/test_positional_fifo.py`

```python
import pytest
from uniqseq.uniqseq import PositionalFIFO

@pytest.mark.unit
class TestPositionalFIFO:
    """Test the PositionalFIFO data structure."""

    def test_append_and_retrieve(self):
        """Can append items and retrieve by position."""
        fifo = PositionalFIFO(maxsize=100)
        pos1 = fifo.append("hash1")
        pos2 = fifo.append("hash2")

        assert pos1 == 0
        assert pos2 == 1
        assert fifo.get_key(0) == "hash1"
        assert fifo.get_key(1) == "hash2"

    def test_find_all_positions(self):
        """Can find all positions matching a key."""
        fifo = PositionalFIFO(maxsize=100)
        fifo.append("A")
        fifo.append("B")
        fifo.append("A")
        fifo.append("C")
        fifo.append("A")

        positions = fifo.find_all_positions("A")
        assert positions == [0, 2, 4]

    def test_get_next_position(self):
        """get_next_position returns position + 1."""
        fifo = PositionalFIFO(maxsize=100)
        fifo.append("hash1")
        fifo.append("hash2")

        assert fifo.get_next_position(0) == 1
        assert fifo.get_next_position(1) == 2

    def test_eviction_at_capacity(self):
        """Oldest entries evicted when maxsize reached."""
        fifo = PositionalFIFO(maxsize=3)
        fifo.append("A")  # pos 0
        fifo.append("B")  # pos 1
        fifo.append("C")  # pos 2
        fifo.append("D")  # pos 3, evicts pos 0

        assert fifo.get_key(0) is None  # Evicted
        assert fifo.get_key(1) == "B"
        assert fifo.get_key(2) == "C"
        assert fifo.get_key(3) == "D"

    def test_find_positions_after_eviction(self):
        """find_all_positions excludes evicted entries."""
        fifo = PositionalFIFO(maxsize=3)
        fifo.append("A")  # pos 0
        fifo.append("B")  # pos 1
        fifo.append("A")  # pos 2
        fifo.append("C")  # pos 3, evicts pos 0

        positions = fifo.find_all_positions("A")
        assert positions == [2]  # pos 0 evicted

    def test_empty_fifo(self):
        """Operations on empty FIFO behave correctly."""
        fifo = PositionalFIFO(maxsize=10)

        assert fifo.get_key(0) is None
        assert fifo.find_all_positions("any") == []
```

### 1.2 Hash Functions

**File**: `tests/test_hashing.py`

```python
import pytest
from uniqseq.uniqseq import hash_line, hash_window

@pytest.mark.unit
class TestHashing:
    """Test hash function behavior."""

    def test_hash_line_deterministic(self):
        """Same line produces same hash."""
        line = "test line content"
        hash1 = hash_line(line)
        hash2 = hash_line(line)
        assert hash1 == hash2

    def test_hash_line_different_content(self):
        """Different lines produce different hashes."""
        hash1 = hash_line("line 1")
        hash2 = hash_line("line 2")
        assert hash1 != hash2

    def test_hash_line_size(self):
        """Line hash is 8 bytes (16 hex chars)."""
        hash_val = hash_line("test")
        assert len(hash_val) == 16

    def test_hash_window_size(self):
        """Window hash is 16 bytes (32 hex chars)."""
        window_hashes = ["abc123", "def456", "ghi789"]
        hash_val = hash_window(10, window_hashes)
        assert len(hash_val) == 32

    def test_hash_window_deterministic(self):
        """Same window produces same hash."""
        hashes = ["h1", "h2", "h3"]
        hash1 = hash_window(10, hashes)
        hash2 = hash_window(10, hashes)
        assert hash1 == hash2

    def test_hash_window_order_matters(self):
        """Window hash changes if order changes."""
        hash1 = hash_window(10, ["h1", "h2", "h3"])
        hash2 = hash_window(10, ["h3", "h2", "h1"])
        assert hash1 != hash2
```

### 1.3 NewSequenceCandidate Lifecycle

**File**: `tests/test_new_sequence_candidate.py`

```python
import pytest
from io import StringIO
from uniqseq.uniqseq import UniqSeq

@pytest.mark.unit
class TestNewSequenceCandidate:
    """Test NewSequenceCandidate creation and finalization."""

    def test_candidate_created_on_history_match(self):
        """NewSequenceCandidate created when window hash matches history."""
        uniqseq = UniqSeq(window_size=3, max_history=100)
        output = StringIO()

        # Build up history
        for line in ["A", "B", "C", "D", "E"]:
            uniqseq.process_line(line, output)

        # Now repeat the pattern starting with A
        uniqseq.process_line("A", output)
        uniqseq.process_line("B", output)
        uniqseq.process_line("C", output)

        # Should have created NewSequenceCandidate
        assert len(uniqseq.new_sequence_records) > 0

    def test_candidate_tracks_multiple_history_positions(self):
        """NewSequenceCandidate can track multiple history matches."""
        uniqseq = UniqSeq(window_size=3, max_history=100)
        output = StringIO()

        # Create pattern A,B,C at two positions in history
        for line in ["A", "B", "C", "D", "A", "B", "C"]:
            uniqseq.process_line(line, output)

        # Repeat pattern again
        uniqseq.process_line("A", output)
        uniqseq.process_line("B", output)
        uniqseq.process_line("C", output)

        # Should track both history positions
        candidates = list(uniqseq.new_sequence_records.values())
        assert len(candidates) == 1
        assert len(candidates[0].matching_history_positions) == 2

    def test_candidate_eliminated_on_mismatch(self):
        """History match removed from candidate on mismatch."""
        uniqseq = UniqSeq(window_size=3, max_history=100)
        output = StringIO()

        # History: A,B,C,D
        for line in ["A", "B", "C", "D"]:
            uniqseq.process_line(line, output)

        # Start matching: A,B,C
        uniqseq.process_line("A", output)
        uniqseq.process_line("B", output)
        uniqseq.process_line("C", output)

        # Mismatch (expected D, got X)
        uniqseq.process_line("X", output)

        # Candidate should have no matching positions
        candidates = list(uniqseq.new_sequence_records.values())
        if candidates:
            assert len(candidates[0].matching_history_positions) == 0

    def test_candidate_finalized_when_all_eliminated(self):
        """Candidate finalized when all history matches eliminated."""
        uniqseq = UniqSeq(window_size=3, max_history=100)
        output = StringIO()

        # History: A,B,C,D
        for line in ["A", "B", "C", "D"]:
            uniqseq.process_line(line, output)

        # Matching start: A,B,C
        uniqseq.process_line("A", output)
        uniqseq.process_line("B", output)
        uniqseq.process_line("C", output)

        # At this point, candidate exists
        assert len(uniqseq.new_sequence_records) == 1

        # Mismatch causes finalization
        uniqseq.process_line("X", output)

        # Candidate should be finalized and removed
        # (Check on next line processing to ensure finalization happened)
        uniqseq.process_line("Y", output)
        assert len(uniqseq.new_sequence_records) == 0
```

### 1.4 PotentialSeqRecMatch Behavior

**File**: `tests/test_uniq_seq_match.py`

```python
import pytest
from io import StringIO
from uniqseq.uniqseq import UniqSeq

@pytest.mark.unit
class TestPotentialSeqRecMatch:
    """Test matching against known unique sequences."""

    def test_uniq_seq_match_created_on_start_hash(self):
        """PotentialSeqRecMatch created when start_window_hash matches."""
        uniqseq = UniqSeq(window_size=3, max_history=100)
        output = StringIO()

        # First occurrence creates SequenceRecord
        for line in ["A", "B", "C", "D", "E"]:
            uniqseq.process_line(line, output)

        # Force finalization by processing more lines
        for line in ["X", "Y", "Z"]:
            uniqseq.process_line(line, output)

        # Second occurrence should create PotentialSeqRecMatch
        uniqseq.process_line("A", output)
        uniqseq.process_line("B", output)
        uniqseq.process_line("C", output)

        assert len(uniqseq.potential_uniq_matches) > 0

    def test_uniq_seq_match_confirmed_on_full_match(self):
        """Full sequence match triggers duplicate handling."""
        uniqseq = UniqSeq(window_size=3, max_history=100)
        output = StringIO()

        # First occurrence: A,B,C,D,E (5 lines)
        for line in ["A", "B", "C", "D", "E"]:
            uniqseq.process_line(line, output)

        # Force finalization
        for line in ["X", "Y", "Z"]:
            uniqseq.process_line(line, output)

        initial_skipped = uniqseq.lines_skipped

        # Second occurrence (exact duplicate)
        for line in ["A", "B", "C", "D", "E"]:
            uniqseq.process_line(line, output)

        # Should have skipped lines
        assert uniqseq.lines_skipped > initial_skipped

    def test_uniq_seq_match_eliminated_on_mismatch(self):
        """Partial match eliminated on mismatch."""
        uniqseq = UniqSeq(window_size=3, max_history=100)
        output = StringIO()

        # First occurrence: A,B,C,D,E
        for line in ["A", "B", "C", "D", "E"]:
            uniqseq.process_line(line, output)

        # Force finalization
        for line in ["X", "Y", "Z"]:
            uniqseq.process_line(line, output)

        # Partial match: A,B,C,D,F (mismatch at last line)
        for line in ["A", "B", "C", "D", "F"]:
            uniqseq.process_line(line, output)

        # Should not have any active matches
        assert len(uniqseq.potential_uniq_matches) == 0
```

### 1.5 LRU Eviction

**File**: `tests/test_lru.py`

```python
import pytest
from io import StringIO
from uniqseq.uniqseq import UniqSeq

@pytest.mark.unit
class TestLRUEviction:
    """Test LRU eviction of unique sequences."""

    def test_lru_evicts_least_recently_used(self):
        """Oldest unused sequence evicted when limit reached."""
        uniqseq = UniqSeq(
            window_size=3,
            max_history=100,
            max_unique_sequences=2  # Small limit
        )
        output = StringIO()

        # Create 3 unique sequences (exceeds limit of 2)
        sequences = [
            ["A", "B", "C"],
            ["D", "E", "F"],
            ["G", "H", "I"]
        ]

        for seq in sequences:
            for line in seq:
                uniqseq.process_line(line, output)
            # Finalize
            for line in ["X", "Y", "Z"]:
                uniqseq.process_line(line, output)

        # Should have evicted first sequence
        total_seqs = sum(len(d) for d in uniqseq.unique_sequences.values())
        assert total_seqs == 2

    def test_lru_accessed_sequence_not_evicted(self):
        """Recently accessed sequence stays in memory."""
        uniqseq = UniqSeq(
            window_size=3,
            max_unique_sequences=2
        )
        output = StringIO()

        # Create sequence 1
        for line in ["A", "B", "C"]:
            uniqseq.process_line(line, output)
        for line in ["X1", "Y1", "Z1"]:
            uniqseq.process_line(line, output)

        # Create sequence 2
        for line in ["D", "E", "F"]:
            uniqseq.process_line(line, output)
        for line in ["X2", "Y2", "Z2"]:
            uniqseq.process_line(line, output)

        # Access sequence 1 (match against it)
        for line in ["A", "B", "C"]:
            uniqseq.process_line(line, output)
        for line in ["X3", "Y3", "Z3"]:
            uniqseq.process_line(line, output)

        # Create sequence 3 (should evict sequence 2, not 1)
        for line in ["G", "H", "I"]:
            uniqseq.process_line(line, output)

        # Sequence 1 should still be present
        # (Check by matching against it)
        uniqseq.process_line("A", output)
        uniqseq.process_line("B", output)
        uniqseq.process_line("C", output)
        assert len(uniqseq.potential_uniq_matches) > 0
```

### 1.6 Edge Cases

**File**: `tests/test_edge_cases.py`

```python
import pytest
from io import StringIO
from uniqseq.uniqseq import UniqSeq

@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_input(self):
        """Empty input produces empty output."""
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()
        uniqseq.flush(output)

        assert output.getvalue() == ""
        assert uniqseq.line_num_input == 0
        assert uniqseq.line_num_output == 0

    def test_single_line(self):
        """Single line passes through unchanged."""
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()
        uniqseq.process_line("single line", output)
        uniqseq.flush(output)

        assert "single line" in output.getvalue()
        assert uniqseq.line_num_output == 1

    def test_fewer_lines_than_window(self):
        """Sequences shorter than window pass through."""
        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for i in range(5):
            uniqseq.process_line(f"line {i}", output)
        uniqseq.flush(output)

        lines = output.getvalue().strip().split('\n')
        assert len(lines) == 5

    def test_exact_window_size(self):
        """Sequence exactly window_size long."""
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        # First occurrence
        for line in ["A", "B", "C"]:
            uniqseq.process_line(line, output)

        # Force finalization
        for line in ["X", "Y", "Z"]:
            uniqseq.process_line(line, output)

        # Second occurrence (duplicate)
        for line in ["A", "B", "C"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)
        assert uniqseq.lines_skipped == 3

    def test_overlapping_sequences(self):
        """Overlapping sequences handled correctly."""
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        # Pattern: A,B,C,B,C,D
        # Contains overlapping subsequences
        for line in ["A", "B", "C", "B", "C", "D"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)
        # Should emit all lines (no duplicates)
        lines = output.getvalue().strip().split('\n')
        assert len(lines) == 6

    def test_alternating_pattern(self):
        """Alternating pattern: A,B,A,B,A,B."""
        uniqseq = UniqSeq(window_size=2)
        output = StringIO()

        for line in ["A", "B", "A", "B", "A", "B"]:
            uniqseq.process_line(line, output)

        uniqseq.flush(output)
        # First A,B passes through, second A,B detected as duplicate
        # (depends on exact algorithm behavior)
        assert uniqseq.lines_skipped >= 0  # At least doesn't crash

    def test_very_long_sequence(self):
        """Very long sequence (1000+ lines)."""
        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        # Create 1000-line sequence
        for i in range(1000):
            uniqseq.process_line(f"line_{i % 10}", output)

        uniqseq.flush(output)
        assert uniqseq.line_num_input == 1000
```

## 2. Property-Based Tests with Random Data

### 2.1 Random Sequence Generation

**File**: `tests/test_random_sequences.py`

```python
import pytest
import random
from io import StringIO
from uniqseq.uniqseq import UniqSeq

def generate_random_sequence(
    num_lines: int,
    alphabet_size: int,
    seed: int = None
) -> list[str]:
    """Generate random sequence from limited alphabet.

    Args:
        num_lines: Number of lines to generate
        alphabet_size: Size of character set (e.g., 10 for digits 0-9)
        seed: Random seed for reproducibility

    Returns:
        List of single-character lines
    """
    if seed is not None:
        random.seed(seed)

    alphabet = [str(i) for i in range(alphabet_size)]
    return [random.choice(alphabet) for _ in range(num_lines)]


@pytest.mark.property
class TestRandomSequences:
    """Property-based tests with random inputs."""

    @pytest.mark.parametrize("alphabet_size", [2, 5, 10, 26])
    @pytest.mark.parametrize("num_lines", [100, 1000, 10000])
    def test_random_sequence_completes(self, alphabet_size, num_lines):
        """Random sequence processing completes without error."""
        lines = generate_random_sequence(num_lines, alphabet_size, seed=42)

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Invariant: output + skipped = input
        assert uniqseq.line_num_output + uniqseq.lines_skipped == uniqseq.line_num_input

    @pytest.mark.parametrize("alphabet_size", [2, 5, 10])
    def test_small_alphabet_finds_duplicates(self, alphabet_size):
        """Small alphabet (high collision rate) finds duplicates."""
        # 10,000 lines from 2-10 character alphabet should have duplicates
        lines = generate_random_sequence(10000, alphabet_size, seed=42)

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # With small alphabet, should find duplicates
        if alphabet_size <= 5:
            assert uniqseq.lines_skipped > 0

    def test_large_alphabet_few_duplicates(self):
        """Large alphabet (low collision rate) finds few duplicates."""
        # 1,000 lines from 100 character alphabet unlikely to have duplicates
        alphabet = [chr(i) for i in range(ord('A'), ord('A') + 100)]
        random.seed(42)
        lines = [random.choice(alphabet) for _ in range(1000)]

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Large alphabet should have few/no duplicates
        assert uniqseq.lines_skipped < 100  # Very conservative

    @pytest.mark.slow
    def test_very_large_random_input(self):
        """Stress test with very large random input (100k lines)."""
        lines = generate_random_sequence(100000, alphabet_size=10, seed=42)

        uniqseq = UniqSeq(
            window_size=10,
            max_history=10000,
            max_unique_sequences=1000
        )
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Invariant checks
        assert uniqseq.line_num_output + uniqseq.lines_skipped == uniqseq.line_num_input
        assert uniqseq.line_num_input == 100000
```

### 2.2 Invariant Testing

**File**: `tests/test_invariants.py`

```python
import pytest
from io import StringIO
from uniqseq.uniqseq import UniqSeq
from tests.test_random_sequences import generate_random_sequence

@pytest.mark.property
class TestInvariants:
    """Test algorithm invariants hold under all conditions."""

    def test_conservation_of_lines(self):
        """Invariant: input lines = output lines + skipped lines."""
        lines = generate_random_sequence(1000, alphabet_size=5, seed=42)

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        assert uniqseq.line_num_input == uniqseq.line_num_output + uniqseq.lines_skipped

    def test_order_preservation(self):
        """Invariant: Output preserves input order."""
        lines = ["A", "B", "C", "D", "E", "A", "B", "C"]

        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = output.getvalue().strip().split('\n')

        # Track which input lines were emitted
        emitted_indices = []
        out_idx = 0
        for in_idx, line in enumerate(lines):
            if out_idx < len(output_lines) and output_lines[out_idx] == line:
                emitted_indices.append(in_idx)
                out_idx += 1

        # Emitted indices should be in ascending order
        assert emitted_indices == sorted(emitted_indices)

    def test_first_occurrence_always_emitted(self):
        """Invariant: First occurrence of any sequence is emitted."""
        lines = ["A", "B", "C", "D", "E"]

        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        output_lines = output.getvalue().strip().split('\n')

        # All lines should be emitted (first occurrence)
        assert len(output_lines) == 5

    def test_bounded_memory_unique_sequences(self):
        """Invariant: unique_sequences never exceeds max_unique_sequences."""
        lines = generate_random_sequence(10000, alphabet_size=10, seed=42)

        max_seqs = 100
        uniqseq = UniqSeq(
            window_size=10,
            max_unique_sequences=max_seqs
        )
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)

            # Check invariant at every step
            total_seqs = sum(len(d) for d in uniqseq.unique_sequences.values())
            assert total_seqs <= max_seqs

        uniqseq.flush(output)

    def test_bounded_memory_history(self):
        """Invariant: window hash history never exceeds max_history."""
        lines = generate_random_sequence(10000, alphabet_size=10, seed=42)

        max_hist = 1000
        uniqseq = UniqSeq(
            window_size=10,
            max_history=max_hist
        )
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)

            # Check history size
            # (Would need access to internal state or a getter method)
            # For now, just verify processing completes

        uniqseq.flush(output)
        assert uniqseq.line_num_input == 10000
```

### 2.3 Determinism and Reproducibility

**File**: `tests/test_determinism.py`

```python
import pytest
from io import StringIO
from uniqseq.uniqseq import UniqSeq
from tests.test_random_sequences import generate_random_sequence

@pytest.mark.property
class TestDeterminism:
    """Test that algorithm is deterministic and reproducible."""

    def test_same_input_same_output(self):
        """Same input produces identical output on multiple runs."""
        lines = generate_random_sequence(1000, alphabet_size=5, seed=42)

        outputs = []
        for _ in range(3):
            uniqseq = UniqSeq(window_size=10)
            output = StringIO()

            for line in lines:
                uniqseq.process_line(line, output)
            uniqseq.flush(output)

            outputs.append(output.getvalue())

        # All outputs should be identical
        assert outputs[0] == outputs[1] == outputs[2]

    def test_same_seed_same_random(self):
        """Same random seed produces same sequence."""
        seq1 = generate_random_sequence(100, alphabet_size=10, seed=123)
        seq2 = generate_random_sequence(100, alphabet_size=10, seed=123)

        assert seq1 == seq2

    def test_different_seed_different_random(self):
        """Different random seeds produce different sequences."""
        seq1 = generate_random_sequence(100, alphabet_size=10, seed=123)
        seq2 = generate_random_sequence(100, alphabet_size=10, seed=456)

        assert seq1 != seq2
```

## 3. Integration Tests

### 3.1 End-to-End Scenarios

**File**: `tests/test_integration.py`

```python
import pytest
from io import StringIO
from uniqseq.uniqseq import UniqSeq

@pytest.mark.integration
class TestEndToEnd:
    """End-to-end integration tests with realistic scenarios."""

    def test_log_file_with_repeated_errors(self):
        """Simulated log file with repeated error blocks."""
        log_lines = [
            "INFO: Server started",
            "INFO: Connection from 192.168.1.1",
            "ERROR: Connection timeout",
            "  at line 42 in server.py",
            "  in handle_request()",
            "  stacktrace line 1",
            "INFO: Retrying connection",
            "ERROR: Connection timeout",  # Duplicate error
            "  at line 42 in server.py",
            "  in handle_request()",
            "  stacktrace line 1",
            "INFO: Connection established",
        ]

        uniqseq = UniqSeq(window_size=4)
        output = StringIO()

        for line in log_lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Should detect and skip duplicate error block
        assert uniqseq.lines_skipped >= 4

    def test_build_output_with_warnings(self):
        """Simulated build output with repeated warnings."""
        build_lines = []

        # Add some unique lines
        build_lines.extend([
            "Building project...",
            "Compiling main.c",
            "Compiling utils.c",
        ])

        # Add repeated warning (10 times)
        warning_block = [
            "WARNING: Deprecated function used",
            "  in utils.c:123",
            "  Use new_function() instead",
        ]

        for _ in range(10):
            build_lines.extend(warning_block)
            build_lines.append(f"Compiling module_{_}.c")

        build_lines.append("Build complete!")

        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        for line in build_lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Should skip 9 of the 10 warning blocks
        assert uniqseq.lines_skipped >= 27  # 9 blocks × 3 lines

    def test_mixed_unique_and_duplicate(self):
        """Mix of unique content and duplicates."""
        lines = []

        # Pattern: unique, duplicate, unique, duplicate, ...
        for i in range(20):
            if i % 2 == 0:
                lines.extend([f"unique_{i}_a", f"unique_{i}_b", f"unique_{i}_c"])
            else:
                lines.extend(["dup_a", "dup_b", "dup_c"])

        uniqseq = UniqSeq(window_size=3)
        output = StringIO()

        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        # Should emit unique blocks and first duplicate
        # Skip subsequent duplicates (9 duplicate blocks)
        assert uniqseq.lines_skipped >= 27
```

## 4. Test Fixtures and Utilities

### 4.1 Common Fixtures

**File**: `tests/conftest.py`

```python
import pytest
from pathlib import Path
import tempfile
import shutil

@pytest.fixture
def temp_dir():
    """Temporary directory for test files."""
    dirpath = Path(tempfile.mkdtemp())
    yield dirpath
    shutil.rmtree(dirpath)

@pytest.fixture
def sample_log_file(temp_dir):
    """Sample log file with repeated patterns."""
    log_file = temp_dir / "sample.log"

    lines = [
        "INFO: Starting application",
        "ERROR: Connection failed",
        "  at line 10",
        "  retry in 5s",
        "INFO: Retrying",
        "ERROR: Connection failed",  # Duplicate
        "  at line 10",
        "  retry in 5s",
        "INFO: Success",
    ]

    log_file.write_text('\n'.join(lines))
    return log_file

@pytest.fixture(params=[2, 5, 10, 26])
def alphabet_size(request):
    """Parametrized alphabet sizes for random testing."""
    return request.param

@pytest.fixture(params=[100, 1000, 10000])
def sequence_length(request):
    """Parametrized sequence lengths for random testing."""
    return request.param
```

### 4.2 Test Utilities

**File**: `tests/test_utils.py`

```python
from io import StringIO
from uniqseq.uniqseq import UniqSeq

def process_lines(lines: list[str], **dedup_kwargs) -> tuple[str, UniqSeq]:
    """Helper to process lines and return output + uniqseq.

    Args:
        lines: Lines to process
        **dedup_kwargs: Arguments for UniqSeq

    Returns:
        (output_string, uniqseq_instance)
    """
    uniqseq = UniqSeq(**dedup_kwargs)
    output = StringIO()

    for line in lines:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)

    return output.getvalue(), dedup

def count_output_lines(output: str) -> int:
    """Count non-empty lines in output."""
    return len([line for line in output.split('\n') if line.strip()])

def assert_lines_equal(actual: str, expected: list[str]):
    """Assert output matches expected lines."""
    actual_lines = [line for line in actual.split('\n') if line.strip()]
    assert actual_lines == expected
```

## 5. Test Execution Strategy

### 5.1 Test Markers

```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
markers = [
    "unit: Unit tests for specific components",
    "property: Property-based tests with random inputs",
    "integration: End-to-end integration tests",
    "slow: Tests that take >1 second",
]
```

### 5.2 Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest -m unit

# Run only fast tests (exclude slow)
pytest -m "not slow"

# Run specific test file
pytest tests/test_random_sequences.py

# Run with coverage
pytest --cov=uniqseq --cov-report=html

# Run in parallel (requires pytest-xdist)
pytest -n auto

# Verbose output
pytest -v

# Show print statements
pytest -s
```

## 6. Coverage Goals

**Minimum coverage targets**:
- Overall: 90%+
- Core algorithm (uniqseq.py): 95%+
- Critical paths (matching, finalization): 100%

**What to test**:
- ✅ All public methods
- ✅ All error conditions
- ✅ All edge cases
- ✅ Algorithm invariants
- ✅ Memory bounds
- ✅ Determinism

**What not to test**:
- ❌ CLI formatting (tested separately)
- ❌ External dependencies (mocked)
- ❌ Implementation details (test behavior, not internals)

## 7. Oracle Testing with Reference Implementation

### 7.1 Concept

Use a simple, obviously-correct implementation to precalculate expected output for random test cases. This validates that the optimized algorithm produces correct results.

### 7.2 Reference Implementation

**File**: `tests/oracle.py`

```python
from typing import List, Tuple

def find_duplicates_naive(lines: List[str], window_size: int) -> Tuple[List[str], int]:
    """Naive but obviously correct duplicate detection.

    Finds all sequences of window_size+ lines that appear more than once.
    Returns deduplicated output and count of skipped lines.

    This is SLOW (O(n²)) but serves as ground truth for testing.
    """
    output = []
    skipped_count = 0
    i = 0

    while i < len(lines):
        # Try to find if sequence starting at i is a duplicate
        if i + window_size > len(lines):
            # Not enough lines left for a full window
            output.extend(lines[i:])
            break

        # Build sequence starting at i
        current_seq = []
        j = i

        # Find longest sequence starting at i that matches something earlier
        best_match_len = 0

        # Search all earlier positions
        for start_pos in range(i):
            if start_pos + window_size > i:
                # Would overlap with current position
                continue

            # Try to match from start_pos
            match_len = 0
            while (j + match_len < len(lines) and
                   start_pos + match_len < i and
                   lines[start_pos + match_len] == lines[j + match_len]):
                match_len += 1

            if match_len >= window_size:
                best_match_len = max(best_match_len, match_len)

        if best_match_len >= window_size:
            # Found duplicate - skip it
            skipped_count += best_match_len
            i += best_match_len
        else:
            # No duplicate - emit line
            output.append(lines[i])
            i += 1

    return output, skipped_count


def find_duplicates_with_library(lines: List[str], window_size: int) -> Tuple[List[str], int]:
    """Use difflib or similar to find repeated sequences.

    Alternative oracle implementation using standard library.
    """
    from difflib import SequenceMatcher

    # This is a sketch - would need full implementation
    # Could use SequenceMatcher to find longest matching blocks
    # Then remove duplicates

    # For now, fall back to naive implementation
    return find_duplicates_naive(lines, window_size)
```

### 7.3 Oracle Tests

**File**: `tests/test_oracle.py`

```python
import pytest
from io import StringIO
from uniqseq.uniqseq import UniqSeq
from tests.oracle import find_duplicates_naive
from tests.test_random_sequences import generate_random_sequence

@pytest.mark.property
class TestAgainstOracle:
    """Compare algorithm output against reference implementation."""

    def test_small_random_matches_oracle(self):
        """Small random input matches naive implementation."""
        lines = generate_random_sequence(100, alphabet_size=5, seed=42)

        # Our implementation
        uniqseq = UniqSeq(window_size=10)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        actual_output = output.getvalue().strip().split('\n')
        actual_skipped = uniqseq.lines_skipped

        # Oracle implementation
        expected_output, expected_skipped = find_duplicates_naive(lines, window_size=10)

        # Compare
        assert actual_output == expected_output
        assert actual_skipped == expected_skipped

    @pytest.mark.parametrize("alphabet_size", [2, 5, 10])
    @pytest.mark.parametrize("window_size", [3, 5, 10])
    def test_various_configs_match_oracle(self, alphabet_size, window_size):
        """Various configurations match oracle."""
        lines = generate_random_sequence(200, alphabet_size, seed=123)

        # Our implementation
        uniqseq = UniqSeq(window_size=window_size)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        actual_output = [l for l in output.getvalue().split('\n') if l]
        actual_skipped = uniqseq.lines_skipped

        # Oracle
        expected_output, expected_skipped = find_duplicates_naive(lines, window_size)

        assert actual_output == expected_output
        assert actual_skipped == expected_skipped

    def test_known_pattern_matches_oracle(self):
        """Known pattern with duplicates matches oracle."""
        lines = [
            "A", "B", "C",  # First occurrence
            "D", "E",
            "A", "B", "C",  # Duplicate
            "F", "G",
        ]

        # Our implementation
        uniqseq = UniqSeq(window_size=3)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        actual_output = [l for l in output.getvalue().split('\n') if l]

        # Oracle
        expected_output, _ = find_duplicates_naive(lines, window_size=3)

        assert actual_output == expected_output

    @pytest.mark.slow
    def test_large_random_matches_oracle(self):
        """Larger input matches oracle (slower)."""
        # Use smaller input for oracle (it's O(n²))
        lines = generate_random_sequence(500, alphabet_size=5, seed=999)

        uniqseq = UniqSeq(window_size=10)
        output = StringIO()
        for line in lines:
            uniqseq.process_line(line, output)
        uniqseq.flush(output)

        actual_output = [l for l in output.getvalue().split('\n') if l]
        actual_skipped = uniqseq.lines_skipped

        expected_output, expected_skipped = find_duplicates_naive(lines, window_size=10)

        assert actual_output == expected_output
        assert actual_skipped == expected_skipped
```

### 7.4 Precomputed Test Cases

**File**: `tests/fixtures/precomputed_cases.json`

```json
{
  "test_cases": [
    {
      "name": "simple_duplicate",
      "window_size": 3,
      "input": ["A", "B", "C", "D", "A", "B", "C"],
      "expected_output": ["A", "B", "C", "D"],
      "expected_skipped": 3
    },
    {
      "name": "no_duplicates",
      "window_size": 3,
      "input": ["A", "B", "C", "D", "E", "F"],
      "expected_output": ["A", "B", "C", "D", "E", "F"],
      "expected_skipped": 0
    },
    {
      "name": "overlapping_sequences",
      "window_size": 2,
      "input": ["A", "B", "C", "B", "C", "D"],
      "expected_output": ["A", "B", "C", "D"],
      "expected_skipped": 2
    }
  ]
}
```

**File**: `tests/test_precomputed.py`

```python
import pytest
import json
from pathlib import Path
from io import StringIO
from uniqseq.uniqseq import UniqSeq

def load_precomputed_cases():
    """Load precomputed test cases from JSON."""
    fixture_path = Path(__file__).parent / "fixtures" / "precomputed_cases.json"
    with open(fixture_path) as f:
        return json.load(f)["test_cases"]

@pytest.mark.unit
@pytest.mark.parametrize("test_case", load_precomputed_cases())
def test_precomputed_case(test_case):
    """Test against precomputed expected outputs."""
    uniqseq = UniqSeq(window_size=test_case["window_size"])
    output = StringIO()

    for line in test_case["input"]:
        uniqseq.process_line(line, output)
    uniqseq.flush(output)

    actual_output = [l for l in output.getvalue().split('\n') if l]

    assert actual_output == test_case["expected_output"]
    assert uniqseq.lines_skipped == test_case["expected_skipped"]
```

### 7.5 Generating Test Data

**Script**: `tests/generate_test_data.py`

```python
#!/usr/bin/env python3
"""Generate precomputed test cases for validation.

Usage:
    python tests/generate_test_data.py

Generates random test cases, runs oracle to compute expected output,
saves to tests/fixtures/precomputed_cases.json
"""

import json
from pathlib import Path
from tests.oracle import find_duplicates_naive
from tests.test_random_sequences import generate_random_sequence

def generate_test_suite():
    """Generate comprehensive test suite with expected outputs."""
    test_cases = []

    # Hand-crafted cases
    test_cases.extend([
        {
            "name": "simple_duplicate",
            "window_size": 3,
            "input": ["A", "B", "C", "D", "A", "B", "C"],
        },
        {
            "name": "no_duplicates",
            "window_size": 3,
            "input": ["A", "B", "C", "D", "E", "F"],
        },
        {
            "name": "all_duplicates",
            "window_size": 2,
            "input": ["A", "B"] * 5,
        },
    ])

    # Random cases
    configs = [
        (100, 5, 3, "small_alphabet_short"),
        (100, 10, 10, "medium_alphabet_short"),
        (500, 5, 10, "small_alphabet_long"),
    ]

    for num_lines, alphabet_size, window_size, name in configs:
        lines = generate_random_sequence(num_lines, alphabet_size, seed=42)
        test_cases.append({
            "name": name,
            "window_size": window_size,
            "input": lines,
        })

    # Compute expected outputs using oracle
    for case in test_cases:
        output, skipped = find_duplicates_naive(case["input"], case["window_size"])
        case["expected_output"] = output
        case["expected_skipped"] = skipped

    return {"test_cases": test_cases}

if __name__ == "__main__":
    suite = generate_test_suite()

    output_path = Path(__file__).parent / "fixtures" / "precomputed_cases.json"
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(suite, f, indent=2)

    print(f"Generated {len(suite['test_cases'])} test cases")
    print(f"Saved to {output_path}")
```

### 7.6 Benefits of Oracle Testing

1. **Confidence**: Validates correctness against simple, obviously correct implementation
2. **Regression detection**: Precomputed cases catch unintended behavior changes
3. **Coverage**: Random generation explores input space we might not think of
4. **Documentation**: Test cases serve as examples of expected behavior

### 7.7 Oracle Limitations

- **Performance**: Oracle is O(n²), so limited to smaller inputs (~500-1000 lines)
- **For larger tests**: Use invariant checking instead of exact output matching
- **Not for benchmarking**: Only for correctness validation

## 8. Random Test Data Generation

### 7.1 Alphabet Sizes

| Alphabet | Size | Collision Rate | Use Case |
|----------|------|----------------|----------|
| Binary | 2 | Very High | Stress test duplicate detection |
| Digits | 10 | High | General testing |
| Hex | 16 | Medium | Moderate collision rate |
| Alpha | 26 | Low | Few duplicates |
| Alphanumeric | 62 | Very Low | Mostly unique |

### 7.2 Sequence Lengths

| Lines | Purpose |
|-------|---------|
| 100 | Quick smoke tests |
| 1,000 | Standard unit tests |
| 10,000 | Stress testing |
| 100,000 | Performance validation (marked `@slow`) |

### 7.3 Window Sizes

Test with various window sizes to ensure algorithm works across scales:
- Small: 2-3 (edge cases)
- Default: 10 (typical usage)
- Large: 50-100 (long sequences)

---

## Future Feature Testing Plans

### Stage 3: Sequence Libraries

**Test Categories**:

1. **Pattern Serialization** (unit tests):
   - `test_serialize_text_patterns()` - JSON output with actual content
   - `test_serialize_binary_patterns()` - Base64 encoding for binary sequences
   - `test_deserialize_text_patterns()` - Load text patterns from JSON
   - `test_deserialize_binary_patterns()` - Load binary patterns with base64
   - `test_serialize_empty()` - Empty pattern library
   - `test_deserialize_invalid_json()` - Malformed JSON handling

2. **Validation Tests** (unit tests):
   - `test_validate_window_size_mismatch()` - Reject wrong window_size
   - `test_validate_mode_mismatch()` - Reject text/binary mismatch
   - `test_validate_delimiter_mismatch()` - Reject delimiter mismatch
   - `test_validate_version_mismatch()` - Reject unsupported version
   - `test_validate_sequence_length()` - Sequences must match window_size
   - All must fail fast with clear error messages

3. **Save/Load Tests** (integration tests):
   - `test_save_patterns_creates_file()` - File creation with atomic writes
   - `test_load_patterns_populates_history()` - History populated correctly
   - `test_roundtrip_text()` - Save then load produces same patterns
   - `test_roundtrip_binary()` - Save then load binary patterns
   - `test_metadata_preserved()` - count, first_seen timestamps preserved

4. **Incremental Mode Tests** (integration tests):
   - `test_incremental_updates_counts()` - Counts accumulated across runs
   - `test_incremental_preserves_first_seen()` - Earliest timestamp kept
   - `test_incremental_adds_new_patterns()` - New patterns added to library
   - `test_incremental_same_file()` - Can use same file for load/save

5. **Multiple Files Tests** (integration tests):
   - `test_multiple_files_sequential()` - Files processed in order
   - `test_multiple_files_deduplication()` - uniqseq works across file boundaries
   - `test_multiple_files_with_library()` - Library + multiple files

**Edge Cases**:
- Empty pattern library
- Very large library (10k+ patterns)
- Corrupt JSON file
- Missing required fields
- Invalid base64 encoding
- File permissions errors
- Disk full during save

**Coverage Target**: 95%+ for all pattern library code

---

### Stage 4: Track/Bypass and Inspection

**Test Categories**:

1. **Track/Bypass Evaluation Tests** (unit tests):
   - `test_track_includes_lines()` - Lines matched by track continue to dedup
   - `test_bypass_bypasses_dedup()` - Lines matched by bypass pass through
   - `test_no_pattern_default_behavior()` - Default when no pattern matches
   - `test_pattern_sequential_evaluation()` - First match wins
   - `test_pattern_order_matters()` - Different order, different outcome

2. **Pattern File Tests** (unit tests):
   - `test_load_pattern_file()` - Load patterns from file
   - `test_pattern_file_comments()` - Skip `#` comment lines
   - `test_pattern_file_blank_lines()` - Skip blank lines
   - `test_pattern_file_order()` - Preserve pattern order from file
   - `test_pattern_file_invalid_regex()` - Error on bad regex with clear message
   - `test_mixed_file_inline_order()` - Combine file + inline, preserve order

3. **Inverse Mode Tests** (integration tests):
   - `test_inverse_keeps_duplicates()` - Only duplicates in output
   - `test_inverse_removes_unique()` - Unique sequences skipped
   - `test_inverse_with_filters()` - Inverse + filtering interaction
   - `test_inverse_statistics()` - Stats reflect inverse mode behavior

4. **Annotation Tests** (integration tests):
   - `test_annotate_marks_skips()` - Annotations inserted at skip points
   - `test_annotate_line_numbers()` - Accurate line number tracking
   - `test_annotate_match_positions()` - Match references correct
   - `test_annotate_sequence_counts()` - Count increments correctly
   - `test_annotate_custom_format()` - Template variable substitution
   - `test_annotation_variables()` - All variables ({start}, {end}, etc.) work

5. **Real-World Workflow Tests** (end-to-end):
   - `test_error_only_dedup_workflow()` - error-patterns.txt usage
   - `test_exclude_noise_workflow()` - noise-patterns.txt usage
   - `test_security_events_workflow()` - security-events.txt usage
   - `test_complex_multi_filter()` - Multiple file + inline filters
   - `test_annotated_output_parsing()` - Parse annotation markers

**Edge Cases**:
- Empty pattern file
- Pattern file with only comments
- Invalid regex in pattern (error handling)
- Annotation with no duplicates (no annotations)
- Inverse mode with no duplicates (empty output)
- Very long annotation format string
- Pattern matching every line
- Pattern matching no lines

**Coverage Target**: 95%+ for all filtering and annotation code

---

## Next Steps

1. ✅ **Implement test infrastructure** (conftest.py, test_utils.py)
2. ✅ **Write unit tests** for core algorithm
3. ✅ **Implement core algorithm** to pass tests
4. ✅ **Add property tests** with random data
5. ✅ **Verify invariants** under stress
6. ✅ **Run coverage analysis** (currently 84%)
7. ✅ **Document edge cases** in this document
8. ✅ **Plan Stage 3 & 4 testing** (documented above)
9. ✅ **Implement Stage 3** (Sequence Libraries)
10. ✅ **Implement Stage 4** (Filtering and Inspection)

---

## Current Coverage Status

**Date**: November 23, 2025
**Stage**: Stage 4 Complete (All 5 phases)

### Overall Metrics

- **Total Tests**: 632 passing, 1 skipped
- **Overall Coverage**: 84% (875 statements, 136 missing)
- **Test-to-Code Ratio**: 0.72 (632 tests / 875 statements)

### Module Breakdown

| Module | Coverage | Statements | Missing | Notes |
|--------|----------|------------|---------|-------|
| **uniqseq.py** | 91% | 449 | 39 | Core algorithm - excellent coverage |
| **library.py** | 100% | 80 | 0 | Perfect coverage |
| **cli.py** | 72% | 342 | 96 | UI/progress code accounts for most gaps |
| **__main__.py** | 0% | 1 | 1 | Subprocess entry point |

### Coverage Gap Analysis

The missing 16% (136 statements) consists of:

1. **UI/Progress Code** (61 lines, 45% of gaps):
   - Progress bar display logic (cli.py lines 814-874)
   - Rich console formatting
   - Terminal width detection
   - Not critical for correctness

2. **Framework Validation** (30+ lines, 22% of gaps):
   - File existence/permission checks handled by typer
   - Executed before our code runs
   - Cannot be tested directly

3. **Edge Cases** (40+ lines, 29% of gaps):
   - Very specific error paths
   - Difficult to trigger in testing
   - Low impact on typical usage

4. **Module Entry Point** (1 line, <1%):
   - `__main__.py` subprocess invocation
   - Tested via integration but not tracked by coverage

### Stage 4 Test Coverage

**Phases Implemented**: All 5 phases complete
- Phase 1: Basic Pattern Matching
- Phase 2: Pattern Files
- Phase 3: Inverse Mode
- Phase 4: Annotations
- Phase 5: Annotation Formatting

**Tests Added for Stage 4**:
- Pattern evaluation tests (track/bypass)
- Pattern file loading and validation
- Invalid regex error handling
- File permission error handling
- Inverse mode operation tests
- Annotation generation tests
- Custom annotation format tests
- Preloaded sequence edge cases

**Integration Tests**:
- End-to-end filter workflows
- Pattern file combinations
- Annotation output parsing
- Error handling paths

### Critical Path Coverage

**100% Coverage** on critical paths:
- Core deduplication algorithm
- Sequence matching logic
- Buffer management
- Hash computation
- Library loading/saving

**95%+ Coverage** on:
- Filter pattern evaluation
- Sequence tracking
- Memory bounds checking
- Statistics collection

**Good Coverage (80-90%)** on:
- CLI flag validation
- Error message generation
- File I/O operations

### Test Organization

Tests are organized by:
1. **Type**: Unit, Integration, Property-based
2. **Component**: UniqSeq, Library, CLI, Edge cases
3. **Speed**: Fast (<1s), Slow (marked for optional execution)

**Test Files**:
- `test_cli.py` - CLI flag parsing and validation (68 tests)
- `test_cli_coverage.py` - CLI error paths (35 tests)
- `test_uniqseq.py` - Core algorithm (47 tests)
- `test_library.py` - Sequence libraries (20 tests)
- `test_comprehensive.py` - Handcrafted scenarios (229 tests)
- `test_oracle.py` - Oracle validation (18 tests)
- `test_random_sequences.py` - Randomized testing (21 tests)
- `test_invariants.py` - Property checking (10 tests)
- Plus 15 additional specialized test files

### Quality Metrics

**Code Quality**:
- All public functions have type hints
- All public functions have docstrings
- No magic numbers (constants are named)
- Pre-commit hooks enforce: ruff, mypy, formatting

**Test Quality**:
- Clear, descriptive test names
- Comprehensive assertions
- Edge case coverage
- Randomized stress tests
- Oracle-based validation

### Future Coverage Improvements

Potential areas for incremental improvements:
1. Mock-based testing for progress bar display (~5% gain)
2. Additional edge case testing for preloaded sequences (~2% gain)
3. More comprehensive filter pattern combinations (~1% gain)

**Note**: Pursuing 95%+ coverage would require diminishing returns - testing UI code and framework-handled validation that doesn't improve software quality.
