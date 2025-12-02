# Investigation Findings: Non-Tracked Lines Affecting Deduplication

## Summary

**CRITICAL BUG IDENTIFIED**: Non-tracked (filtered/bypassed) lines are causing tracked lines to be deduplicated differently, violating the core requirement that non-tracked lines must have ZERO effect on how tracked lines are deduplicated.

## Evidence

Testing with the same 13,835 tracked input lines:
- **With non-tracked lines mixed in**: 5,855 tracked output lines
- **Without non-tracked lines**: 6,222 tracked output lines
- **Difference**: Not just different line counts (367-line difference), but 5,640 lines of actual content differences

After removing non-tracked lines from both outputs, the tracked line outputs should be IDENTICAL. They are not.

**Note**: We make no judgment about which output is "correct" - the violation is that they differ at all.

## Root Cause: History Position Misalignment

The code maintains two numbering systems that become misaligned when non-tracked lines are present:

### 1. Input Line Numbers (`line_num_input`)
- Location: `src/uniqseq/uniqseq.py:448`
- Incremented for **ALL lines** (tracked + non-tracked)
- Stored in `BufferedLine.input_line_num`

### 2. History Positions (`window_hash_history`)
- Location: `src/uniqseq/uniqseq.py:510`
- Appended only for **TRACKED lines**
- Sequential with no gaps: 0, 1, 2, 3, ...
- Non-tracked lines don't add entries (they return early at line 465)

### The Bug

At `src/uniqseq/uniqseq.py:571-574`, when emitting a tracked line:

```python
hist_pos = buffered_line.input_line_num - 1
entry = self.window_hash_history.get_entry(hist_pos)
if entry and entry.first_output_line is None:
    entry.first_output_line = self.line_num_output
```

**The formula `hist_pos = input_line_num - 1` is INCORRECT when non-tracked lines exist!**

It assumes `input_line_num` only counts tracked lines, but it actually counts ALL lines.

### Concrete Example

```
Input stream:
  Line 1: +: A (tracked)      → input_line_num=1, creates history[0]
  Line 2: -: SEP (non-tracked) → input_line_num=2, NO history entry
  Line 3: +: B (tracked)      → input_line_num=3, creates history[1]

When line 3 (tracked) is emitted:
  Calculated: hist_pos = 3 - 1 = 2
  Tries to access history[2]
  But history only has [0, 1]!

  Correct hist_pos should be 1, not 2!
```

### Consequences

- Wrong history entries get updated with `first_output_line` values
- Corrupts the duplicate detection logic
- Causes false negatives (duplicates not detected)
- Window alignment fails
- Completely different deduplication results depending on non-tracked line presence

## Tests Created

### 1. `tests/test_output_consistency.py`
Comprehensive test that verifies:
1. Non-tracked output lines are identical ✓ (passes)
2. Tracked output lines are identical ✗ (fails - the bug)

Provides detailed quantitative metrics showing the divergence.

### 2. `tests/test_nontracked_interference.py`
Minimal test case (currently needs refinement to reproduce the bug at small scale).

## Branch

`investigate-output-discrepancy`

## Recommended Fix

Add a separate counter for tracked lines only, and use that for history position calculations:

```python
# In __init__:
self.line_num_input_tracked = 0  # Count tracked lines only

# When processing tracked line (after line 485):
self.line_num_input_tracked += 1
buffered_line.tracked_line_num = self.line_num_input_tracked

# When emitting (line 571):
hist_pos = buffered_line.tracked_line_num - 1  # Use tracked count
```

Alternatively, track the mapping between `input_line_num` and history positions to handle the gaps from non-tracked lines.

## Files Modified

- `tests/test_output_consistency.py` - Main test demonstrating the bug
- `tests/test_nontracked_interference.py` - Minimal test case
- `INVESTIGATION_FINDINGS.md` - This document
