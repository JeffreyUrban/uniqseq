# Stage 3: Pattern Libraries - Detailed Planning

**Status**: Planning
**Target Version**: v0.3.0
**Prerequisites**: Stage 2 (Core Enhancements) complete

## Overview

Stage 3 adds pattern library support, enabling reusable sequence patterns across runs and systems. This is foundational for workflows where known patterns are identified once and applied repeatedly.

## Features

### 1. Pattern Library Format

**File Format**: JSON with actual sequence content (not hashes)

**Text Mode Example** (`patterns.json`):
```json
{
  "version": "0.3.0",
  "metadata": {
    "window_size": 10,
    "mode": "text",
    "delimiter": "\n",
    "created": "2024-11-22T10:30:00Z"
  },
  "patterns": [
    {
      "sequence": [
        "Line 1 of pattern",
        "Line 2 of pattern",
        "Line 3 of pattern"
      ],
      "count": 5,
      "first_seen": "2024-11-22T10:30:15Z"
    },
    {
      "sequence": [
        "Another pattern line 1",
        "Another pattern line 2",
        "Another pattern line 3"
      ],
      "count": 3,
      "first_seen": "2024-11-22T10:31:42Z"
    }
  ]
}
```

**Binary Mode Example** (`patterns-binary.json`):
```json
{
  "version": "0.3.0",
  "metadata": {
    "window_size": 10,
    "mode": "binary",
    "delimiter_hex": "00",
    "created": "2024-11-22T11:00:00Z"
  },
  "patterns": [
    {
      "sequence_base64": [
        "YmluYXJ5IGRhdGEgbGluZSAx",
        "YmluYXJ5IGRhdGEgbGluZSAy",
        "YmluYXJ5IGRhdGEgbGluZSAz"
      ],
      "count": 2,
      "first_seen": "2024-11-22T11:00:30Z"
    }
  ]
}
```

**Design Decisions**:
1. **Store actual content, not hashes**
   - Rationale: Hashes aren't useful or intuitive. Compute hashes as needed from content.
   - Benefit: Human-readable, portable, debuggable

2. **Sequences on separate lines**
   - Rationale: Improved readability, easier to inspect patterns

3. **Metadata included**:
   - `count`: Number of times pattern was seen
   - `first_seen`: Timestamp when pattern first encountered
   - Rationale: Useful for analysis, debugging, and prioritizing patterns

4. **Validation on load**:
   - Verify loaded patterns match current window_size
   - Fail fast with clear error message if incompatible
   - Rationale: Prevent silent incorrect behavior

### 2. Save Patterns (`--save-patterns <path>`)

**Functionality**: Export discovered sequences to a pattern library file.

**Usage**:
```bash
# Save patterns discovered during deduplication
uniqseq input.log --save-patterns patterns.json

# Process and save patterns
cat large-log.txt | uniqseq --save-patterns known-patterns.json > unique-output.txt
```

**Behavior**:
- File created/overwritten atomically (write to temp, then rename)
- All unique sequences encountered are saved
- Metadata populated:
  - `count`: Number of times each sequence was seen
  - `first_seen`: Timestamp of first occurrence
  - `window_size`: Current window size
  - `mode`: Current mode (text/binary)
  - `delimiter`: Current delimiter setting

**Implementation Notes**:
- Buffer patterns in memory during processing
- Write JSON on flush/completion
- Use atomic file operations to prevent corruption

### 3. Load Patterns (`--load-patterns <path>`)

**Functionality**: Pre-load known patterns at startup.

**Usage**:
```bash
# Use pre-existing pattern library
uniqseq input.log --load-patterns known-patterns.json

# Combine with other options
uniqseq --load-patterns base-patterns.json --window-size 10 new-data.log
```

**Behavior**:
- Patterns loaded into history before processing starts
- Validation on load:
  - ✅ Check window_size matches current setting
  - ✅ Check mode compatibility (text vs binary)
  - ✅ Check delimiter compatibility
  - ❌ Fail fast with clear error if validation fails

**Validation Error Examples**:
```
Error: Pattern library window_size (15) does not match current setting (10)
Suggestion: Use --window-size 15 or regenerate pattern library with --window-size 10

Error: Pattern library is in binary mode but current mode is text
Suggestion: Add --byte-mode flag or use a text-mode pattern library

Error: Pattern library uses delimiter "\n" but current setting is "\0"
Suggestion: Use --delimiter "\n" or regenerate pattern library
```

**Implementation Notes**:
- Parse JSON and validate metadata
- Compute hashes from loaded sequences
- Populate window_hash_history before processing input
- Track loaded patterns separately for statistics

### 4. Incremental Mode (`--load-patterns X --save-patterns Y`)

**Functionality**: Update pattern library across runs.

**Usage**:
```bash
# Load existing patterns, discover new ones, save updated library
uniqseq \
  --load-patterns existing.json \
  --save-patterns updated.json \
  new-data.log
```

**Behavior**:
- Load existing patterns from `existing.json`
- Process input, discovering any new patterns
- Save all patterns (existing + new) to `updated.json`
- Update counts for patterns seen again
- Preserve `first_seen` for existing patterns

**Use Cases**:
- Continuous log processing with pattern accumulation
- Building comprehensive pattern libraries over time
- Distributed pattern collection (merge libraries from multiple sources)

**Implementation Notes**:
- Merge loaded and discovered patterns
- Update counts by summing occurrences
- Preserve earliest `first_seen` timestamp
- Support same file for load and save (read, process, atomic replace)

### 5. Multiple Input Files

**Functionality**: Process multiple files in a single run.

**Usage**:
```bash
# Process multiple files
uniqseq file1.log file2.log file3.log

# With pattern library
uniqseq --load-patterns known.json app*.log

# Save combined patterns
uniqseq log1.txt log2.txt log3.txt --save-patterns all-patterns.json
```

**Behavior**:
- Files processed sequentially in order specified
- Deduplication state maintained across all files
- Pattern library updated with sequences from all files

**Output**:
- Default: Concatenated deduplicated output from all files
- No file separators or markers (pure stream)
- Use `--annotate` if file boundaries are important

**Implementation Notes**:
- Accept multiple positional arguments
- Process files in order
- Maintain single deduplicator instance across all files

## CLI Design

### New Flags

| Flag | Type | Description |
|------|------|-------------|
| `--save-patterns <path>` | Path | Save discovered patterns to file |
| `--load-patterns <path>` | Path | Load patterns from file |
| `[FILES...]` | Positional args | Multiple input files (optional) |

### Flag Compatibility

**Compatible combinations**:
```bash
✅ --load-patterns lib.json --save-patterns updated.json
✅ --load-patterns lib.json file1 file2 file3
✅ --save-patterns lib.json --byte-mode --delimiter-hex 00
✅ --load-patterns lib.json --unlimited-history
```

**Incompatible combinations**:
```bash
❌ --load-patterns text.json --byte-mode  # If library is text-mode
❌ --load-patterns w10.json --window-size 15  # Mismatched window size
```

### Processing Order

1. **Parse arguments** → Validate compatibility
2. **Load patterns** (if `--load-patterns`) → Populate history
3. **Process input** → Files in order, or stdin
4. **Save patterns** (if `--save-patterns`) → Write library

## File Format Specification

### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["version", "metadata", "patterns"],
  "properties": {
    "version": {
      "type": "string",
      "pattern": "^\\d+\\.\\d+\\.\\d+$",
      "description": "Library format version"
    },
    "metadata": {
      "type": "object",
      "required": ["window_size", "mode", "created"],
      "properties": {
        "window_size": {"type": "integer", "minimum": 1},
        "mode": {"enum": ["text", "binary"]},
        "delimiter": {"type": "string"},
        "delimiter_hex": {"type": "string"},
        "created": {"type": "string", "format": "date-time"}
      }
    },
    "patterns": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["count", "first_seen"],
        "properties": {
          "sequence": {
            "type": "array",
            "items": {"type": "string"}
          },
          "sequence_base64": {
            "type": "array",
            "items": {"type": "string"}
          },
          "count": {"type": "integer", "minimum": 1},
          "first_seen": {"type": "string", "format": "date-time"}
        },
        "oneOf": [
          {"required": ["sequence"]},
          {"required": ["sequence_base64"]}
        ]
      }
    }
  }
}
```

### Validation Rules

On load, validate:
1. **Version compatibility**: Check version is supported (exact match for v0.3.0)
2. **Window size**: Must match current `--window-size` setting
3. **Mode**: Must match current mode (text/binary)
4. **Delimiter**: Must match current delimiter setting
5. **Sequence length**: All sequences must be exactly `window_size` lines
6. **Base64 encoding**: If binary mode, validate base64 encoding is valid

### File Format Evolution

**Version compatibility matrix**:

| Library Version | uniqseq Version | Compatibility |
|----------------|-----------------|---------------|
| 0.3.0 | 0.3.0 | ✅ Exact match required initially |
| 0.3.x | 0.3.y | 🔄 Future: Backward compatible |
| 0.4.x | 0.3.x | ❌ Reject with upgrade message |

**Future evolution**:
- v0.4.0 may add fields (backward compatible)
- v1.0.0 may change structure (migration tool provided)

## Use Cases

### Use Case 1: Building a Pattern Library

**Scenario**: Collect common patterns from production logs.

```bash
# Day 1: Process logs, save patterns
uniqseq prod-2024-11-22.log --save-patterns prod-patterns.json

# Day 2: Update library with new logs
uniqseq \
  --load-patterns prod-patterns.json \
  --save-patterns prod-patterns.json \
  prod-2024-11-23.log

# Day 3: Continue accumulating
uniqseq \
  --load-patterns prod-patterns.json \
  --save-patterns prod-patterns.json \
  prod-2024-11-24.log
```

### Use Case 2: Reusable Deduplication

**Scenario**: Apply known patterns to new data without discovery overhead.

```bash
# Build library from historical data
uniqseq historical-logs/*.log --save-patterns baseline.json

# Apply to new logs
uniqseq --load-patterns baseline.json live-stream.log > deduplicated.log
```

### Use Case 3: Multi-System Pattern Sharing

**Scenario**: Share patterns between development, staging, and production.

```bash
# Production: Save patterns
ssh prod "uniqseq /var/log/app.log --save-patterns /tmp/prod-patterns.json"
scp prod:/tmp/prod-patterns.json .

# Development: Apply production patterns
uniqseq --load-patterns prod-patterns.json dev-logs.log
```

### Use Case 4: Distributed Log Processing

**Scenario**: Process logs from multiple servers, combine patterns.

```bash
# Server 1
uniqseq server1.log --save-patterns server1-patterns.json

# Server 2
uniqseq server2.log --save-patterns server2-patterns.json

# Merge (using future v0.5.0 tool: uniqseq-lib merge)
uniqseq-lib merge server1-patterns.json server2-patterns.json > combined.json

# Apply combined patterns to new logs
uniqseq --load-patterns combined.json new-logs.log
```

## Implementation Plan

### Phase 1: Basic Save/Load

**Tasks**:
1. Define JSON schema
2. Implement pattern serialization (text mode)
3. Implement pattern deserialization with validation
4. Add `--save-patterns` flag
5. Add `--load-patterns` flag
6. Tests for save/load roundtrip

**Acceptance Criteria**:
- Can save patterns to JSON file
- Can load patterns from JSON file
- Validation rejects incompatible libraries
- Tests achieve 95%+ coverage

### Phase 2: Binary Mode Support

**Tasks**:
1. Implement base64 encoding for binary sequences
2. Update serialization for binary mode
3. Update deserialization for binary mode
4. Tests for binary pattern libraries

**Acceptance Criteria**:
- Binary patterns saved with base64 encoding
- Binary patterns loaded correctly
- Mode validation prevents mixing text/binary

### Phase 3: Incremental Mode

**Tasks**:
1. Support `--load-patterns` + `--save-patterns` together
2. Merge loaded and discovered patterns
3. Update counts correctly
4. Preserve `first_seen` timestamps
5. Support same file for load and save

**Acceptance Criteria**:
- Can update library incrementally
- Counts accumulated correctly across runs
- Atomic file operations prevent corruption

### Phase 4: Multiple Files

**Tasks**:
1. Accept multiple positional arguments
2. Process files sequentially
3. Maintain deduplication state across files
4. Update documentation and examples

**Acceptance Criteria**:
- Can process multiple files in one run
- Deduplication works across file boundaries
- Pattern library includes sequences from all files

## Testing Strategy

### Unit Tests

**Pattern Serialization**:
- `test_serialize_text_patterns()` - Text mode JSON output
- `test_serialize_binary_patterns()` - Binary mode with base64
- `test_deserialize_text_patterns()` - Load text patterns
- `test_deserialize_binary_patterns()` - Load binary patterns
- `test_serialize_empty()` - Empty pattern library
- `test_deserialize_invalid_json()` - Malformed JSON handling

**Validation Tests**:
- `test_validate_window_size_mismatch()` - Reject wrong window size
- `test_validate_mode_mismatch()` - Reject text/binary mismatch
- `test_validate_delimiter_mismatch()` - Reject delimiter mismatch
- `test_validate_version_mismatch()` - Reject unsupported version
- `test_validate_sequence_length()` - Sequences must match window_size

**Save/Load Tests**:
- `test_save_patterns_creates_file()` - File creation
- `test_save_patterns_atomic()` - Atomic write operation
- `test_load_patterns_populates_history()` - History populated
- `test_roundtrip_text()` - Save then load produces same patterns
- `test_roundtrip_binary()` - Save then load binary patterns

**Incremental Tests**:
- `test_incremental_updates_counts()` - Counts accumulated
- `test_incremental_preserves_first_seen()` - Timestamps preserved
- `test_incremental_adds_new_patterns()` - New patterns added
- `test_incremental_same_file()` - Can use same file for load/save

### Integration Tests

**Multiple Files**:
- `test_multiple_files_sequential()` - Files processed in order
- `test_multiple_files_deduplication()` - Dedup across files
- `test_multiple_files_with_library()` - Library + multiple files

**End-to-End Tests**:
- `test_build_library_workflow()` - Complete workflow
- `test_apply_library_workflow()` - Load and apply
- `test_incremental_workflow()` - Multi-day accumulation

### Edge Cases

- Empty pattern library
- Single pattern
- Very large library (10k+ patterns)
- Corrupt JSON file
- Missing required fields
- Invalid base64 encoding
- File permissions errors
- Disk full during save
- Concurrent access to same file

## Documentation Requirements

### Update IMPLEMENTATION.md

Add sections:
- Pattern library format specification
- Serialization/deserialization logic
- Validation rules
- File format versioning

### Update EXAMPLES.md

Add examples:
- Building pattern libraries
- Incremental library updates
- Multi-file processing
- Distributed pattern sharing
- Common pattern libraries (error-patterns.txt, etc.)

### Update TEST_COVERAGE.md

Document test coverage for:
- Pattern serialization
- Validation logic
- Incremental mode
- Multiple file handling

## Future Enhancements (v0.5.0+)

### Pattern Library Tools (`uniqseq-lib`)

**Planned commands**:
```bash
# Merge multiple libraries
uniqseq-lib merge lib1.json lib2.json > combined.json

# Filter library by count threshold
uniqseq-lib filter --min-count 5 lib.json > filtered.json

# Show library statistics
uniqseq-lib stats lib.json

# Inspect patterns
uniqseq-lib show lib.json

# Validate library
uniqseq-lib validate lib.json
```

### Directory Format (Alternative to JSON)

**Concept**: Hash-based filenames for fast lookup and live inspection.

```
patterns/
├── metadata.json          # Library metadata
├── abc123def456.txt       # Pattern 1 (hash of sequence)
├── 789ghi012jkl.txt       # Pattern 2
└── ...
```

**Benefits**:
- Live inspection (can view patterns while processing)
- Fast lookup (no JSON parsing)
- Incremental updates (add files without rewriting everything)

**Tradeoffs**:
- More complex to manage
- Not single-file portable
- Requires filesystem support

**Decision**: Defer to v0.5.0+ based on user demand.

## Success Criteria

**v0.3.0 is successful if**:
1. Pattern libraries can be saved and loaded reliably
2. Validation prevents silent errors from incompatible libraries
3. Incremental mode enables pattern accumulation over time
4. Multiple file processing works seamlessly
5. Binary mode patterns work correctly
6. Documentation includes real-world examples
7. Tests achieve 95%+ coverage
