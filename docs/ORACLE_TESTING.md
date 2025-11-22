# Oracle Testing Framework

## Overview

This document describes the enhanced oracle-based testing framework for the uniqseq deduplication algorithm. The oracle provides ground truth for validating the correctness of the optimized implementation.

## Oracle Implementation

### Location
`tests/oracle.py` - Reference implementation with comprehensive tracking

### Key Features

The oracle provides:

1. **Correctness validation**: Simple O(n²) brute-force algorithm that is obviously correct
2. **Complete sequence tracking**: All duplicate sequences with positions and occurrences
3. **Line-by-line analysis**: Detailed processing information for every input line
4. **Precomputed results**: All test cases analyzed in advance for fast test execution

### Data Structures

#### `SequenceInfo`
Tracks each unique sequence that had duplicates:
- `sequence`: The actual lines in the sequence
- `sequence_hash`: Blake2b hash for identification
- `first_occurrence_line`: Where first occurrence started (0-based)
- `occurrences`: List of all occurrences (first + duplicates)
- `total_occurrences`: Total times this sequence appeared
- `duplicate_count`: Number of duplicate occurrences (skipped)
- `lines_skipped`: Total lines skipped from this sequence's duplicates

#### `SequenceOccurrence`
Represents one occurrence of a sequence:
- `start_line`: 0-based line number where occurrence starts
- `length`: Number of lines in this occurrence
- `is_duplicate`: `false` for first occurrence, `true` for duplicates

#### `LineProcessingInfo`
Detailed information for each input line:
- `line_number`: 0-based input position
- `line_content`: The actual line text
- `was_output`: `true` if line was emitted to output
- `was_skipped`: `true` if line was part of duplicate sequence
- `output_position`: Position in output stream (0-based), `None` if skipped
- `part_of_sequence`: Hash of sequence this line belonged to (if duplicate)
- `reason`: Human-readable reason for decision
  - `"output_no_match"`: Line output, no duplicate detected
  - `"output_no_window"`: Line output, not enough lines for window
  - `"skipped_duplicate"`: Line skipped as part of duplicate sequence
- `buffer_depth_at_output`: Maximum buffer depth when this line was output
  - For output lines: How many lines were ahead in buffer (0 to window_size - 1)
  - For skipped lines: `None` (not output)
  - **Critical for validation**: Ensures lines aren't output too early or too late relative to potential matches
- `lines_in_buffer_when_output`: Total lines in buffer when output (buffer_depth + 1)
  - Includes the line being output
  - For skipped lines: `None`

#### `OracleResult`
Complete analysis of deduplication:
- `input_lines`: Original input
- `output_lines`: Expected deduplicated output
- `window_size`: Minimum sequence length
- `total_lines_input`: Total input line count
- `total_lines_output`: Total output line count
- `total_lines_skipped`: Total lines skipped
- `sequences`: List of all sequences with duplicates
- `unique_sequence_count`: Number of unique sequences detected
- `line_processing`: Per-line processing details

### Oracle Algorithm

The oracle uses a simple brute-force approach:

```python
for each position i in input:
    # Search all earlier positions for matching sequences
    for each earlier position start_pos:
        # Don't match if would overlap within window
        if start_pos + window_size > i:
            skip

        # Find longest match starting at i that matches start_pos
        match_len = count_matching_lines(i, start_pos)

        if match_len >= window_size:
            track_best_match

    if found_match of length >= window_size:
        skip entire matched sequence
    else:
        output this line
```

**Key properties**:
- O(n²) time complexity (acceptable for test oracle)
- Doesn't match sequences whose start lines overlap within window
- Tracks longest match when multiple matches found
- First occurrence always kept, duplicates skipped

## Test Fixtures

### Organization

Fixtures stored in `tests/fixtures/`:

- `handcrafted_cases.json` - 15 carefully designed test cases with known patterns
- `edge_cases.json` - 9 boundary condition tests
- `random_cases.json` - 15 randomly generated sequences with various properties
- `all_cases.json` - Combined fixture set (39 total cases)

### Generation

Run `tests/generate_fixtures.py` to regenerate all fixtures:

```bash
cd tests
python generate_fixtures.py
```

This:
1. Generates random sequences with various alphabet sizes and window sizes
2. Creates handcrafted test cases for known patterns
3. Runs oracle analysis on all cases
4. Saves comprehensive JSON fixtures with all analysis data

**When to regenerate**:
- When oracle algorithm changes
- When adding new test patterns
- When fixing oracle bugs
- Before major releases

### Fixture Contents

Each fixture contains:

```json
{
  "name": "test_case_name",
  "description": "Human-readable description",
  "generator": {"type": "random|handcrafted|edge_case", ...},
  "window_size": 10,
  "input_lines": ["A", "B", "C", ...],
  "output_lines": ["A", "B", ...],
  "total_lines_input": 100,
  "total_lines_output": 85,
  "total_lines_skipped": 15,
  "unique_sequence_count": 3,
  "sequences": [
    {
      "sequence": ["A", "B", "C"],
      "sequence_hash": "abc123...",
      "first_occurrence_line": 0,
      "total_occurrences": 2,
      "duplicate_count": 1,
      "lines_skipped": 3,
      "occurrences": [
        {"start_line": 0, "length": 3, "is_duplicate": false},
        {"start_line": 50, "length": 3, "is_duplicate": true}
      ]
    }
  ],
  "line_processing": [
    {
      "line_number": 0,
      "line_content": "A",
      "was_output": true,
      "was_skipped": false,
      "output_position": 0,
      "part_of_sequence": null,
      "reason": "output_no_match",
      "buffer_depth_at_output": 0,
      "lines_in_buffer_when_output": 1
    },
    ...
  ]
}
```

### Fixture Coverage

**Input sizes**: 0 to 2000 lines
**Window sizes**: 1 to 20 lines
**Alphabet sizes**: 2 to 100 characters (affects duplicate frequency)
**Patterns**:
- No duplicates (unique sequences only)
- High duplication (small alphabet)
- Exact window size matches
- Longer than window matches
- Multiple different sequences
- Overlapping patterns
- Consecutive duplicates
- Nested sequences

## Test Suite

### Location
`tests/test_comprehensive.py` - Main oracle-based test suite

### Test Classes

#### `TestHandcraftedCases`
- Tests known patterns with predictable behavior
- Verifies output and skip counts
- Validates sequence detection

#### `TestEdgeCases`
- Empty input, single line, boundary conditions
- Unicode, whitespace, very long lines
- Minimum/maximum window sizes

#### `TestRandomCases`
- Random sequences with precomputed oracle results
- Various alphabet sizes (collision rates)
- Various window sizes
- Statistics validation

#### `TestLineByLineProcessing`
- Validates line processing order matches oracle
- Verifies correct lines are skipped
- Tests buffering behavior

#### `TestSequenceDetection`
- Verifies duplicate sequences found
- Validates occurrence counts
- Tests first occurrence preservation

#### `TestInvariantsWithOracle`
- Conservation law: input = output + skipped
- Output never exceeds input
- Skip never exceeds input
- Exact match with oracle output

#### `TestFixtureQuality`
- Verifies all fixtures loaded correctly
- Validates fixture structure
- Checks coverage of edge cases

### Running Tests

```bash
# All comprehensive tests
pytest tests/test_comprehensive.py -v

# Specific test class
pytest tests/test_comprehensive.py::TestHandcraftedCases -v

# Specific fixture
pytest tests/test_comprehensive.py -k "simple_duplicate" -v

# With coverage
pytest tests/test_comprehensive.py --cov=uniqseq --cov-report=html
```

## Benefits of Oracle Approach

### 1. Correctness Guarantee
- Oracle implementation is simple enough to verify by inspection
- O(n²) brute force eliminates clever optimizations that could have bugs
- Ground truth for validating optimized implementation

### 2. Comprehensive Test Data
- 39 precomputed test cases cover wide range of scenarios
- Each case includes detailed expected results at multiple levels:
  - Final output (end-to-end validation)
  - Per-line processing (detailed behavior validation)
  - Sequence detection (algorithm internals validation)

### 3. Fast Test Execution
- Oracle runs once during fixture generation (slow O(n²) acceptable)
- Tests run against precomputed results (fast)
- No need to re-run oracle during development

### 4. Debugging Support
- Line-by-line processing info helps debug failures
- Sequence occurrence tracking shows where duplicates detected
- Clear reason codes explain each line's fate

### 5. Regression Prevention
- Fixtures capture current correct behavior
- Any change that breaks tests requires explanation
- Easy to add new fixtures for discovered edge cases

## Oracle vs Implementation

### What Oracle Tracks (but implementation doesn't need to)

The oracle tracks comprehensive metadata for testing purposes:
- All sequence occurrences with positions
- Per-line processing reasons
- Sequence hashes for identification

The actual implementation only needs:
- Which lines to skip
- Final output
- Basic statistics

### Overlap Rule

Both oracle and implementation enforce the same rule:

**Don't match sequences whose start lines overlap within the window**

Example with window_size=5:
```
Position 0-4: Sequence "ABCDE"
Position 3-7: Can't match against position 0 (3 + 5 = 8 > 0, but 3 < 5)
Position 5-9: CAN match against position 0 (5 + 5 = 10 >= 5)
```

This prevents false positives from overlapping patterns within the window.

### Buffer Depth Tracking

The oracle tracks **buffer depth at output time** for each line, which is critical for validating correct buffering behavior.

#### Why Buffer Depth Matters

The implementation must buffer lines while checking for potential matches. Lines should:
- **Not be output too early**: Must wait until enough lines have been seen to confirm no match
- **Not be output too late**: Should be output as soon as it's confirmed no longer part of a potential match

Buffer depth validation ensures the implementation follows correct buffering protocol.

#### Buffer Depth Behavior

For a given `window_size`:

1. **Initial fill phase** (lines 0 to window_size - 1):
   - Line 0: buffer_depth = 0 (first line, nothing buffered before it)
   - Line 1: buffer_depth = 1 (line 0 was buffered)
   - Line 2: buffer_depth = 2 (lines 0-1 buffered)
   - ...
   - Line N: buffer_depth = min(N, window_size - 1)

2. **Steady state** (line window_size onward):
   - buffer_depth = window_size - 1 (buffer is full)
   - Each output releases oldest line from buffer

3. **Final flush** (when input ends):
   - Remaining buffered lines output
   - buffer_depth decreases as buffer empties

#### Example (window_size = 3)

```
Input:  A B C D E
Line 0 (A): buffer_depth = 0, lines_in_buffer = 1  [buffer: A]
Line 1 (B): buffer_depth = 1, lines_in_buffer = 2  [buffer: A B]
Line 2 (C): buffer_depth = 2, lines_in_buffer = 3  [buffer: A B C] (full)
Line 3 (D): buffer_depth = 2, lines_in_buffer = 3  [buffer: B C D] (A output, D added)
Line 4 (E): buffer_depth = 2, lines_in_buffer = 3  [buffer: C D E] (B output, E added)
Flush:      buffer_depth varies as remaining lines output
```

#### Validation Tests

The test suite validates:
- Buffer depth never exceeds `window_size - 1`
- Buffer fills gradually during initial phase
- Buffer maintains steady state after filling
- `lines_in_buffer = buffer_depth + 1` (consistency check)
- Skipped lines have no buffer depth (they're never output)

## Maintenance

### Adding New Test Cases

1. Add pattern to `tests/generate_fixtures.py`:
   - Handcrafted: Add to `generate_handcrafted_fixtures()`
   - Random: Add configuration to `generate_random_fixtures()`
   - Edge case: Add to `generate_edge_case_fixtures()`

2. Regenerate fixtures:
   ```bash
   python tests/generate_fixtures.py
   ```

3. Run tests to verify:
   ```bash
   pytest tests/test_comprehensive.py -v
   ```

### Updating Oracle Algorithm

If oracle algorithm changes:

1. Update `analyze_sequences_detailed()` in `tests/oracle.py`
2. Regenerate all fixtures: `python tests/generate_fixtures.py`
3. Review changes to fixture outputs (git diff)
4. Verify changes are correct
5. Commit updated fixtures

### Verifying Oracle Correctness

The oracle itself should be simple enough to verify by inspection. Key invariants:

- ✓ Never match overlapping positions
- ✓ Always keep first occurrence
- ✓ Skip entire duplicate sequences
- ✓ Conservation: input = output + skipped
- ✓ Greedy longest match

## Statistics

Current test coverage (from fixture generation):

```
Total fixtures: 39
  Handcrafted: 15
  Edge cases: 9
  Random: 15

Total unique sequences tracked: 200
Total input lines: 8,987
Total output lines: 7,876
Total skipped lines: 1,111
Overall deduplication rate: 12.4%
```

This comprehensive test suite provides high confidence in algorithm correctness across a wide variety of inputs and conditions.
