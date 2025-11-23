# Stage 4: Filtering and Inspection - Detailed Planning

**Status**: Planning
**Target Version**:
**Prerequisites**: Stage 3 (Sequence Libraries) complete

## Overview

Stage 4 adds filtering capabilities and output inspection features. This enables fine-grained control over what gets deduplicated and visibility into deduplication results.

## Features

### 1. Sequential Pattern Evaluation

**Design**: Patterns evaluated in order specified, first match wins.

**Flags**:
- `--track <pattern>` - Apply deduplication to lines matching pattern
- `--ignore <pattern>` - Don't deduplicate lines matching pattern (pass through unchanged)
- `--track-from <path>` - Load track patterns from file
- `--ignore-from <path>` - Load ignore patterns from file

**Evaluation Order**:
1. All patterns (inline + file) evaluated in command-line order
2. First matching pattern determines action
3. If no pattern matches → default behavior (process for deduplication)

**Pattern Actions**:
- `track`: Line participates in deduplication
- `ignore`: Line bypasses deduplication (always output)

### Sequential Evaluation Examples

**Example 1: Exclude debug, include everything else**
```bash
uniqseq --ignore 'DEBUG' app.log
```
- `"DEBUG: Starting process"` → **ignore** (pass through, no dedup)
- `"INFO: Process started"` → **no match** (deduplicate normally)
- `"ERROR: Failed"` → **no match** (deduplicate normally)

**Example 2: Only deduplicate errors**
```bash
uniqseq --track 'ERROR|CRITICAL' app.log
```
- `"ERROR: Connection failed"` → **track** (deduplicate)
- `"INFO: Retrying"` → **no match** (pass through, no dedup)
- `"DEBUG: Details"` → **no match** (pass through, no dedup)

**Example 3: Complex sequential rules**
```bash
uniqseq \
  --ignore 'DEBUG' \
  --track 'ERROR' \
  --ignore 'TEST' \
  app.log
```
Processing:
- `"DEBUG ERROR"` → **ignore** (rule 1 matches first, pass through)
- `"ERROR in production"` → **track** (rule 2 matches, deduplicate)
- `"ERROR TEST"` → **track** (rule 2 matches first, deduplicate)
- `"TEST data"` → **ignore** (rule 3 matches, pass through)
- `"INFO: Running"` → **no match** (default: deduplicate)

**Example 4: Order matters**
```bash
# Case A: Exclude first
uniqseq --ignore 'ERROR' --track 'ERROR CRITICAL' app.log
# "ERROR CRITICAL" → ignore (first rule wins)

# Case B: Include first
uniqseq --track 'ERROR CRITICAL' --ignore 'ERROR' app.log
# "ERROR CRITICAL" → track (first rule wins)
```

### 2. Pattern Files

**File Format**: One regex pattern per line, `#` for comments, blank lines ignored.

**Example - error-patterns.txt**:
```
# Common error signatures
ERROR
CRITICAL
FATAL
Exception
Traceback

# Include specific error codes
E[0-9]{4}
```

**Example - noise-patterns.txt**:
```
# Known noisy output to exclude
DEBUG
TRACE
Starting.*
Finished.*
^#.*   # Comment lines
```

**Example - security-events.txt**:
```
# Security-related patterns to always include
Authentication
Authorization
Permission denied
Access denied
Security violation
```

**Usage**:
```bash
# Single file
uniqseq --track-file error-patterns.txt app.log

# Multiple files
uniqseq \
  --track-file error-patterns.txt \
  --track-file security-events.txt \
  app.log

# Mix files and inline patterns
uniqseq \
  --track-file errors.txt \
  --track 'WARN' \
  --ignore-file noise.txt \
  --ignore 'TEST' \
  app.log
```

**File Pattern Order**: Patterns from files preserve command-line order.

**Example**:
```bash
uniqseq \
  --track 'FIRST' \
  --track-file rules.txt \
  --track 'LAST' \
  app.log
```

**Evaluation order**:
1. `FIRST` (inline)
2. All patterns from `rules.txt` (in file order)
3. `LAST` (inline)

**File Loading**:
- Read patterns from file line-by-line
- Strip leading/trailing whitespace
- Skip empty lines
- Skip lines starting with `#` (comments)
- Compile each pattern as regex
- Preserve order from file

### 3. Inverse Mode (`--inverse`)

**Functionality**: Keep duplicates, remove unique sequences.

**Usage**:
```bash
# Show only duplicated sequences
uniqseq --inverse app.log
```

**Behavior**:
- Output only sequences that appear 2+ times
- First occurrence is skipped
- Subsequent occurrences are emitted

**Example**:
```
Input:
A
B
C
A
B
C
D
```

```bash
# Normal mode
uniqseq --window-size 3 input.txt
# Output: A, B, C, D (unique sequences only)

# Inverse mode
uniqseq --window-size 3 --inverse input.txt
# Output: A, B, C (duplicate sequence lines)
```

**Use Cases**:
- Find repeated error patterns
- Identify cyclic behavior in logs
- Analyze repetition frequency

**Rationale for inclusion**: Algorithm-specific behavior, hard to compose efficiently.

### 4. Annotations (`--annotate`)

**Functionality**: Add inline markers showing where duplicates were skipped.

**Usage**:
```bash
uniqseq --annotate app.log
```

**Output Format**:
```
Line 1: A
Line 2: B
Line 3: C
Line 4: D
[DUPLICATE: Lines 5-7 matched lines 1-3 (sequence seen 2 times)]
Line 8: E
[DUPLICATE: Lines 9-11 matched lines 1-3 (sequence seen 3 times)]
Line 12: F
```

**Annotation Content**:
- Which lines were skipped
- Which earlier lines they matched
- How many times sequence has been seen

**Customization**: See Annotation Format below.

### 5. Annotation Format (`--annotation-format <template>`)

**Functionality**: Custom annotation templates.

**Default Template**:
```
[DUPLICATE: Lines {start}-{end} matched lines {match_start}-{match_end} (sequence seen {count} times)]
```

**Available Variables**:
- `{start}` - First line number of skipped sequence
- `{end}` - Last line number of skipped sequence
- `{match_start}` - First line number of matched sequence
- `{match_end}` - Last line number of matched sequence
- `{count}` - Total times sequence has been seen
- `{window_size}` - Current window size

**Examples**:

**Minimal format**:
```bash
uniqseq --annotate --annotation-format "... skipped {count}x ..." app.log
```
Output:
```
Line A
Line B
Line C
... skipped 2x ...
Line D
... skipped 3x ...
```

**Verbose format**:
```bash
uniqseq --annotate \
  --annotation-format "SKIP: {window_size} lines ({start}-{end}) duplicate of ({match_start}-{match_end})" \
  app.log
```
Output:
```
Line A
Line B
Line C
SKIP: 3 lines (4-6) duplicate of (1-3)
Line D
```

**Machine-readable format**:
```bash
uniqseq --annotate \
  --annotation-format "SKIP|{start}|{end}|{match_start}|{match_end}|{count}" \
  app.log
```
Output:
```
Line A
Line B
Line C
SKIP|4|6|1|3|2
Line D
SKIP|7|9|1|3|3
```

**Integration with `--stats-format json`**:
```bash
uniqseq --annotate --annotation-format "SKIP|{start}|{end}|{count}" \
  --stats-format json app.log
```
- Annotations in stdout (data stream)
- Statistics in stderr (JSON format)
- Clean separation for pipeline processing

## CLI Design

### New Flags

| Flag | Type | Description |
|------|------|-------------|
| `--track <pattern>` | Regex | Include lines matching pattern |
| `--ignore <pattern>` | Regex | Exclude lines from dedup |
| `--track-file <path>` | Path | Load track patterns from file |
| `--ignore-file <path>` | Path | Load ignore patterns from file |
| `--inverse` | Boolean | Keep duplicates, remove unique |
| `--annotate` | Boolean | Add markers for skipped duplicates |
| `--annotation-format <template>` | String | Custom annotation template |

### Flag Compatibility

**Compatible combinations**:
```bash
✅ --track 'ERROR' --ignore 'DEBUG'
✅ --track-file errors.txt --track 'EXTRA'
✅ --annotate --annotation-format "..."
✅ --inverse --annotate
✅ --track 'ERROR' --annotate
```

**Incompatible combinations**:
```bash
❌ --track 'pattern' --byte-mode  # Filters require text mode
❌ --annotation-format "..." (without --annotate)  # Format requires annotate
```

**Warning combinations** (allowed but potentially confusing):
```bash
⚠️  --inverse --track 'ERROR'  # Inverse + filtering (document behavior)
⚠️  --quiet --annotate  # Quiet suppresses all output including annotations
```

### Processing Pipeline Order

1. **Input** → Read lines/records
2. **Filter Evaluation** → Apply filters in sequence
   - If `ignore` matches → Output line immediately, skip dedup
   - If `track` matches → Continue to dedup
   - If no match → Default behavior (continue to dedup)
3. **Skip/Transform** → Apply skip-chars, hash-transform (if enabled)
4. **Hash** → Compute line hash
5. **Deduplication** → Check for sequence matches
   - Normal mode: Emit unique, skip duplicates
   - Inverse mode: Skip unique, emit duplicates
6. **Annotation** → Add markers (if `--annotate` enabled)
7. **Output** → Write to stdout

## Implementation Plan

### Phase 1: Basic Pattern Matching

**Tasks**:
1. Add `--track` and `--ignore` flags
2. Implement sequential pattern evaluation
3. Add pattern action handling in processing loop
4. Tests for track/ignore behavior

**Acceptance Criteria**:
- Track includes lines for deduplication
- Ignore bypasses deduplication
- Sequential evaluation works correctly
- Tests achieve 95%+ coverage

### Phase 2: Pattern Files

**Tasks**:
1. Add `--track-file` and `--ignore-file` flags
2. Implement file parsing (comments, blank lines)
3. Integrate file patterns with inline patterns
4. Preserve command-line order

**Acceptance Criteria**:
- Can load patterns from files
- Comments and blank lines handled
- Order preserved across files and inline
- Invalid regex patterns produce clear errors

### Phase 3: Inverse Mode

**Tasks**:
1. Add `--inverse` flag
2. Implement inverse deduplication logic
3. Update statistics for inverse mode
4. Tests for inverse behavior

**Acceptance Criteria**:
- Inverse mode outputs only duplicates
- Statistics reflect inverse behavior
- Works with filtering

### Phase 4: Annotations

**Tasks**:
1. Add `--annotate` flag
2. Track line numbers during processing
3. Track match positions
4. Generate default annotations
5. Tests for annotation output

**Acceptance Criteria**:
- Annotations show skip positions
- Line numbers accurate
- Works with all modes (normal, inverse, binary)

### Phase 5: Annotation Formatting

**Tasks**:
1. Add `--annotation-format` flag
2. Implement template variable substitution
3. Validation for format string
4. Tests for custom formats

**Acceptance Criteria**:
- Template variables substituted correctly
- Format validation prevents errors
- Works with all annotation use cases

## Testing Strategy

### Unit Tests

**Filter Evaluation**:
- `test_filter_in_includes_lines()` - Lines included for dedup
- `test_filter_out_bypasses_dedup()` - Lines bypass dedup
- `test_no_filter_default_behavior()` - Default when no match
- `test_filter_sequential_evaluation()` - First match wins
- `test_filter_order_matters()` - Order changes outcome

**Filter Files**:
- `test_load_filter_file()` - Load patterns from file
- `test_filter_file_comments()` - Skip comment lines
- `test_filter_file_blank_lines()` - Skip blank lines
- `test_filter_file_order()` - Preserve pattern order
- `test_filter_file_invalid_regex()` - Error on bad regex
- `test_mixed_file_inline_order()` - Combine file + inline

**Inverse Mode**:
- `test_inverse_keeps_duplicates()` - Only duplicates output
- `test_inverse_removes_unique()` - Unique sequences skipped
- `test_inverse_with_filters()` - Inverse + filtering
- `test_inverse_statistics()` - Stats reflect inverse mode

**Annotations**:
- `test_annotate_marks_skips()` - Annotations inserted
- `test_annotate_line_numbers()` - Accurate line tracking
- `test_annotate_match_positions()` - Match references correct
- `test_annotate_sequence_counts()` - Count increments
- `test_annotate_custom_format()` - Template substitution

### Integration Tests

**End-to-End Filtering**:
- `test_error_only_dedup()` - Real-world error filtering
- `test_exclude_debug_noise()` - Exclude noisy patterns
- `test_security_events_workflow()` - Include security events

**Annotation Workflows**:
- `test_annotated_output_parsing()` - Parse annotations
- `test_annotation_with_json_stats()` - Annotations + JSON stats
- `test_machine_readable_annotations()` - Custom format parsing

### Edge Cases

- Empty filter file
- Filter file with only comments
- Invalid regex in filter
- Annotation with no duplicates (no annotations)
- Inverse mode with no duplicates (empty output)
- Very long annotation format string
- Filter matching every line
- Filter matching no lines

## Documentation Requirements

### Update IMPLEMENTATION.md

Add sections:
- Pattern evaluation algorithm
- Sequential matching logic
- Inverse mode implementation
- Annotation generation

### Update EXAMPLES.md

Add examples:
- Common pattern files (error-patterns.txt, noise-patterns.txt, security-events.txt)
- Sequential pattern workflows
- Inverse mode use cases
- Annotation parsing examples
- Machine-readable annotation formats

**Example pattern libraries to include**:

**error-patterns.txt**:
```
# Common error signatures for applications
ERROR
CRITICAL
FATAL
Exception
Traceback
SEVERE
^E[0-9]{4}   # Error codes like E0001
```

**noise-patterns.txt**:
```
# Known noisy output to exclude from deduplication
DEBUG
TRACE
VERBOSE
Starting\s+\w+
Finished\s+\w+
^#.*          # Comment lines
^\s*$         # Blank lines
```

**security-events.txt**:
```
# Security-related patterns to always include
Authentication\s+(failed|successful)
Authorization\s+denied
Permission\s+denied
Access\s+denied
Security\s+violation
Login\s+attempt
Unauthorized\s+access
sudo:
su:
```

**Workflow examples**:

```bash
# Example 1: Deduplicate only errors, pass through everything else
uniqseq --track-file error-patterns.txt application.log

# Example 2: Exclude debug noise from deduplication
uniqseq --ignore-file noise-patterns.txt verbose-app.log

# Example 3: Complex filtering with multiple sources
uniqseq \
  --track-file error-patterns.txt \
  --track-file security-events.txt \
  --ignore-file noise-patterns.txt \
  --track 'CUSTOM.*PATTERN' \
  production.log

# Example 4: Find repeated security events
uniqseq \
  --track-file security-events.txt \
  --inverse \
  --annotate \
  audit.log

# Example 5: Machine-readable duplicate tracking
uniqseq \
  --annotate \
  --annotation-format 'SKIP|{start}|{end}|{count}' \
  app.log | grep '^SKIP'
```

### Update TEST_COVERAGE.md

Document test coverage for:
- Pattern evaluation
- Pattern file parsing
- Inverse mode
- Annotation generation

## Success Criteria

**Stage 4 is successful if**:
1. Sequential pattern evaluation works intuitively
2. Pattern files support common workflows (error/noise/security patterns)
3. Inverse mode enables duplicate analysis
4. Annotations provide visibility into deduplication
5. Custom annotation formats support machine parsing
6. Documentation includes real-world pattern libraries
7. Tests achieve 95%+ coverage
