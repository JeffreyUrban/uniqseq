# Stage 3: Sequence Libraries - Detailed Planning

**Status**: Planning
**Prerequisites**: Stage 2 (Core Enhancements) complete

## Overview

Stage 3 adds sequence library support via directory-based sequence storage. This enables reusable sequences across runs and systems, with native format storage for easy inspection and monitoring.

**Key Design Principle**: Keep it simple. File I/O is **optional** and **disabled by default**. Sequences stored in native format (file content IS the sequence), no complex serialization.

## Features

### 1. Directory-Based Library Storage

**Design**: Single parent directory containing sequences and timestamped metadata.

**Directory Structure**:
```
mylib/
├── sequences/
│   ├── a1b2c3d4e5f6.uniqseq  # Sequence file (hash-based filename)
│   ├── f7e8d9c0b1a2.uniqseq  # Another sequence
│   └── ...
├── metadata-20241123-153045/
│   ├── config.json      # Configuration and stats from first run
│   └── progress.json    # Progress tracking (optional)
└── metadata-20241123-163012/
    ├── config.json      # Configuration and stats from second run
    └── progress.json
```

**Rationale**:
- **Single parent directory**: Simpler than separate paths for sequences/metadata
- **Sequences directory**: All files are sequences (when saving)
- **Metadata per run**: Timestamped subdirectories avoid overwrites, provide audit trail
- **Clean separation**: Easy to inspect sequences without parsing metadata

### 2. Sequence File Format

**Format**: Native - file content IS the sequence (exactly as processed).

**Critical Detail - Delimiter Handling**: Sequence files do NOT end with a trailing delimiter.

**Text Mode Example** (newline-delimited, window_size=3):
```
# File: sequences/a1b2c3d4e5f6.uniqseq (shown with visible newlines)
Line 1 of pattern\n
Line 2 of pattern\n
Line 3 of pattern
```
Note: File ends with "pattern" (no trailing newline after last line).

**Text Mode - Raw Bytes**:
```
4c696e652031206f66207061747465726e0a    # "Line 1 of pattern\n"
4c696e652032206f66207061747465726e0a    # "Line 2 of pattern\n"
4c696e652033206f66207061747465726e      # "Line 3 of pattern" (no \n)
```

**Binary Mode Example** (null-delimited, window_size=3):
```
# File: sequences/f7e8d9c0b1a2.uniqseq
<record 1>\x00<record 2>\x00<record 3>
```
Note: File ends with last record content (no trailing null byte).

**Key Properties**:
- **No special format**: Just the raw sequence content including delimiters
- **Filename (when saving)**: `<hash>.uniqseq` where hash is full sequence hash under current configuration
- **Filename (when loading)**: Ignored - filenames are opaque, any name/extension works
- **Rehashing on load**: Sequences re-hashed based on current window_size/mode/delimiter settings
- **Human-readable** (text mode): Can inspect with `cat`, `less`, etc.

**Design Rationale**:
- **Simplicity**: No JSON parsing, base64 encoding, or custom formats
- **Inspectability**: Direct file access shows exactly what was deduplicated
- **Portability**: Standard files, works with all Unix tools
- **User-friendly loading**: Any files work, not just hash-named ones

### 3. Metadata File Format

**Format**: Key-value JSON, output-only (never read by uniqseq).

**Example** (`metadata-20241123-153045/config.json`):
```json
{
  "timestamp": "2024-11-23T15:30:45Z",
  "window_size": 10,
  "mode": "text",
  "delimiter": "\n",
  "sequences_discovered": 47,
  "sequences_preloaded": 120,
  "sequences_saved": 95,
  "total_lines_processed": 125000,
  "lines_skipped": 98000
}
```

**Purpose**: Audit trail only - user can see what settings were used historically.

**Important**: uniqseq does NOT read or validate metadata. User is responsible for ensuring configuration compatibility across runs.

### 4. Pre-loaded Sequences (`--read-sequences <path>`)

**Functionality**: Load sequences from directory to treat as "already seen".

**Usage**:
```bash
# Load sequences from one directory
uniqseq --read-sequences ./user-patterns input.log

# Load from multiple directories
uniqseq \
  --read-sequences ./error-patterns \
  --read-sequences ./security-patterns \
  input.log
```

**Behavior**:
- Can be specified **multiple times** for multiple directories
- Read all files from each directory (any filenames, any extensions)
- Skip known noise files: `.DS_Store`, `.gitignore`, `README.md`, `README.txt`, `.keep`
- Compute full sequence hashes based on current configuration
- Store in **pre-loaded sequence set** (unlimited retention, never evicted)
- **Validation**: Text mode requires UTF-8 decodable content, binary mode accepts anything
- **Deduplication**: Pre-loaded sequences treated as "already seen" → **skip on first observation**
- **No saving**: Pre-loaded sequences not written anywhere (unless `--library-dir` also specified)

**Error Handling**:
```
Error: Cannot read sequence file ./user-patterns/pattern1.txt in text mode (not UTF-8)
Suggestion: Use --byte-mode or remove incompatible sequence files
```

**Rationale**:
- **Flexible**: User can provide sequences in any format/naming
- **Non-invasive**: Doesn't modify user's directories
- **Composable**: Multiple directories can be combined
- **Use case**: Filter logs with known sequences from various sources

### 5. Library Mode (`--library-dir <path>`)

**Functionality**: Load pre-existing sequences AND save observed sequences to library.

**Usage**:
```bash
# Create new library
uniqseq input.log --library-dir ./mylib

# Load and extend existing library
uniqseq input2.log --library-dir ./mylib

# Combine with pre-loaded sequences from other sources
uniqseq \
  --read-sequences ./error-patterns \
  --read-sequences ./security-patterns \
  --library-dir ./mylib \
  input.log
```

**Behavior**:
- **Create directory if doesn't exist** (including `sequences/` subdirectory)
- **Load**: Read all files from `<path>/sequences/` into pre-loaded sequence set (same as `--read-sequences`)
  - For `.uniqseq` files: If computed hash doesn't match filename, rename file to `<new-hash>.uniqseq`
  - This keeps library consistent when configuration changes (window_size, mode, delimiter)
- **Save**: Write sequences to `<path>/sequences/` when observed in input:
  - All newly discovered sequences (first time seen anywhere)
  - All pre-loaded sequences (from `--read-sequences` or library itself) when observed in input
  - Only write if file doesn't already exist in `sequences/` directory
- **Metadata**: Create `<path>/metadata-<timestamp>/config.json` with settings and stats
- **Write timing**: Immediate write on observation (no queue, no batching)
- **Progress tracking**: Optional `progress.json` updated periodically for monitoring

**Saving Logic**:
```python
# When sequence is observed in input:
if sequence_hash in preloaded_sequences or sequence_hash in fifo_history:
    # It's a repeat - skip output
    if library_dir and sequence_hash not in saved_sequences:
        # Save to library (first observation of this pre-loaded/discovered sequence)
        save_sequence_to_library(sequence)
        saved_sequences.add(sequence_hash)
else:
    # It's new - output it
    output(sequence)
    add_to_fifo_history(sequence_hash)
    if library_dir:
        save_sequence_to_library(sequence)
        saved_sequences.add(sequence_hash)
```

**Pause/Resume Workflow**:
```bash
# First run
uniqseq input1.log --library-dir ./mylib
# Creates: mylib/sequences/a1b2c3d4.uniqseq (observed sequences)
#          mylib/metadata-20241123-153045/config.json

# Continue (pause/resume) - same library directory
uniqseq input2.log --library-dir ./mylib
# Loads: mylib/sequences/*.uniqseq (pre-loaded sequences)
# Creates: mylib/sequences/f7e8d9c0.uniqseq (new sequences observed in input2.log)
#          mylib/metadata-20241123-163012/config.json
```

**Rationale**:
- **Accumulation**: Library grows with all observed sequences over time
- **Persistence**: Pre-loaded sequences saved to library when observed
- **Audit trail**: Each run's metadata preserved separately
- **Simplicity**: Single directory, no manual file management

### 6. Pre-loaded Sequence Set

**Implementation**: Separate set from FIFO history, unlimited retention.

**Properties**:
- Contains all sequences from `--read-sequences` directories
- Contains all sequences from `--library-dir` sequences/
- **Never evicted** (not subject to `--max-history` limits)
- **Checked during deduplication** (same priority as FIFO history)
- If sequence in pre-loaded set → treated as repeat, skip on first observation

**Rationale**:
- **Persistent sequences**: Known sequences always recognized, regardless of history limits
- **Composable**: Multiple sources of pre-loaded sequences can be combined
- **Predictable**: Pre-loaded sequences never "forgotten" due to FIFO eviction

### 7. File Write Strategy

**When saving sequences (library mode only)**:
- **Timing**: Write immediately when sequence observed in input
- **Filename**: `<hash>.uniqseq` where hash is full sequence hash
- **Atomic writes**: Write to temp file, then rename (prevents partial writes)
- **No queue**: Simple immediate writes, no batching complexity
- **Idempotent**: Check if file exists before writing (avoid overwriting)

**Write Format** (critical for correctness):
```python
# Pseudocode for writing sequence file
def write_sequence_file(sequence_lines, delimiter, filepath):
    with open(filepath, 'wb') as f:
        for i, line in enumerate(sequence_lines):
            f.write(line)  # Write line content (bytes)
            if i < len(sequence_lines) - 1:  # NOT the last line
                f.write(delimiter)  # Write delimiter between lines
        # DO NOT write delimiter after last line
```

**Example - Text Mode (window_size=3, delimiter=\n)**:
```python
sequence = [b"Line 1", b"Line 2", b"Line 3"]
# Writes: b"Line 1\nLine 2\nLine 3"
# File ends WITHOUT trailing newline
```

**Example - Binary Mode (window_size=2, delimiter=\x00)**:
```python
sequence = [b"\x01\x02\x03", b"\x04\x05\x06"]
# Writes: b"\x01\x02\x03\x00\x04\x05\x06"
# File ends WITHOUT trailing null byte
```

**Rationale**:
- **Correctness**: Matches internal representation (lines stored without delimiters)
- **Prevents extra records**: Trailing delimiter would create empty final record on read
- **Simplicity**: Easier to implement and debug
- **Sufficient**: No evidence of performance issues until proven otherwise
- **Monitoring**: Files appear as observed (real-time visibility)

**Future optimization**: If I/O spikes become a problem, can add batching later.

**Read Format** (critical for correctness):
```python
# Pseudocode for reading sequence file
def read_sequence_file(filepath, delimiter):
    with open(filepath, 'rb') as f:
        content = f.read()  # Read entire file as bytes

    # Split by delimiter
    lines = content.split(delimiter)

    # Result: lines WITHOUT trailing delimiter
    # Example: b"A\nB\nC" splits to [b"A", b"B", b"C"]
    # Example: b"A\nB\nC\n" splits to [b"A", b"B", b"C", b""] (WRONG - extra empty line!)

    return lines
```

**Important**: Because files do NOT end with delimiter, `split(delimiter)` produces correct result.

**Edge Case Handling**:
- If file has trailing delimiter → `split()` produces extra empty element at end
  - **Could be valid**: User's sequence legitimately ends with empty record (e.g., blank line)
  - **Could be formatting issue**: File saved incorrectly with trailing delimiter
  - **Recommendation**: Log warning when loading file with trailing delimiter (inform user, don't error)
  - Example warning: `"Warning: Sequence file xyz.uniqseq ends with delimiter (empty final record)"`
  - **Suppression**: Use `--no-warn-trailing-delimiters` to suppress this warning
- If file is empty → `split()` produces `[b""]` → single empty line (valid sequence of 1 empty line)

### 8. Progress Monitoring (Library Mode)

**Optional progress tracking** via `progress.json` in metadata directory.

**Format** (`metadata-<timestamp>/progress.json`):
```json
{
  "last_update": "2024-11-23T15:30:45Z",
  "total_sequences": 1247,
  "sequences_preloaded": 800,
  "sequences_discovered": 447,
  "sequences_saved": 1100,
  "total_lines_processed": 125000,
  "lines_skipped": 98000
}
```

**Update frequency**: Every 1000 lines processed (same as progress bar).

**Monitoring workflow**:
```bash
# Start long-running job
uniqseq large-file.log --library-dir ./mylib &

# Monitor progress (separate terminal)
watch -n 1 'jq . mylib/metadata-*/progress.json'

# Or count sequence files
watch -n 1 'ls mylib/sequences/ | wc -l'
```

**Rationale**: Enables monitoring without affecting performance (infrequent updates).

### 9. Noise File Handling

**When loading sequences**: Skip known noise files to avoid errors.

**Skip list**:
```python
SKIP_FILES = {'.DS_Store', '.gitignore', 'README.md', 'README.txt', '.keep'}
```

**Behavior**: If file matches skip list, silently ignore it (don't load, don't error).

**Extensibility**: Skip list is hardcoded initially, could be made configurable later if needed.

### 10. No Metadata Validation

**Design decision**: Don't read or validate metadata files.

**Implications**:
- User responsible for ensuring compatible settings across runs
- No validation of window_size, mode, delimiter when loading
- Simpler implementation, fewer edge cases

**User guidance**: Add warning message to help output:
```
Warning: When using --library-dir or --read-sequences, ensure settings match:
  --window-size, --delimiter, --byte-mode
Incompatible settings will cause incorrect deduplication.
```

**Future enhancement**: Could add optional `--validate-metadata` flag if users report confusion.

## CLI Design

### New Flags

| Flag | Type | Description |
|------|------|-------------|
| `--library-dir <path>` | Path | Directory for library (load sequences, save observed sequences + metadata) |
| `--read-sequences <path>` | Path | Directory to load sequences from (can be specified multiple times) |
| `--no-warn-trailing-delimiters` | Boolean | Suppress warnings about sequence files ending with delimiter |

### Flag Compatibility

**Compatible combinations**:
```bash
✅ --library-dir ./mylib
✅ --read-sequences ./user-patterns
✅ --read-sequences ./errors --read-sequences ./security
✅ --library-dir ./mylib --byte-mode
✅ --read-sequences ./patterns --window-size 15
✅ --read-sequences ./errors --library-dir ./mylib  # Load + save
✅ --read-sequences ./patterns --no-warn-trailing-delimiters
```

**All combinations are valid** - flags are fully composable.

**Important notes**:
- `--read-sequences` can be specified multiple times
- `--library-dir` loads from `sequences/` + saves observed sequences
- Both can be used together: pre-load from external sources + save to library

### Processing Order

1. **Parse arguments** → Validate compatibility
2. **Load pre-loaded sequences**:
   - From each `--read-sequences` directory (if specified)
   - From `--library-dir` sequences/ (if specified)
   - All loaded into pre-loaded sequence set
3. **Process input** → Stream processing
   - Check pre-loaded set first (treat as "already seen")
   - Then check FIFO history
   - Save to library when observed (if `--library-dir`)
4. **Save metadata** (if `--library-dir`) → Write config.json at completion

## Use Cases

### Use Case 1: Building a Sequence Library

**Scenario**: Collect common sequences from production logs over time.

```bash
# Day 1: Process logs, save sequences and metadata
uniqseq prod-2024-11-22.log --library-dir ./prod-lib

# Day 2: Load existing sequences, save newly observed ones
uniqseq prod-2024-11-23.log --library-dir ./prod-lib

# Day 3: Continue accumulating
uniqseq prod-2024-11-24.log --library-dir ./prod-lib

# Result:
# - prod-lib/sequences/ contains all observed sequences across 3 days
# - prod-lib/metadata-*/ subdirectories contain per-run configs (audit trail)
```

### Use Case 2: Filtering with Known Sequences

**Scenario**: User has manually crafted sequences, wants to filter logs.

```bash
# User creates sequence files
mkdir my-sequences
echo -e "ERROR: Connection failed\nRetrying...\nFailed again" > my-sequences/error1.txt
echo -e "WARNING: Slow response\nTimeout exceeded\nRequest aborted" > my-sequences/warning1.txt

# Use sequences for deduplication
uniqseq --read-sequences ./my-sequences app.log > filtered.log
```

**Note**: User's directory unchanged, original filenames preserved.

### Use Case 3: Combining Multiple Sequence Sources

**Scenario**: Load sequences from multiple sources, save observations to library.

```bash
# Load sequences from two directories + save all observed sequences to library
uniqseq \
  --read-sequences ./error-sequences \
  --read-sequences ./security-sequences \
  --library-dir ./mylib \
  input.log
```

**Behavior**:
- Pre-loads sequences from `./error-sequences/`
- Pre-loads sequences from `./security-sequences/`
- Pre-loads sequences from `./mylib/sequences/` (existing library)
- Saves all observed sequences (pre-loaded + newly discovered) to `./mylib/sequences/`

### Use Case 4: Multi-System Sequence Sharing

**Scenario**: Share sequences between development, staging, and production.

```bash
# Production: Build library
uniqseq /var/log/app.log --library-dir /tmp/prod-lib

# Copy library to development
scp -r prod:/tmp/prod-lib/sequences ./prod-sequences

# Development: Apply production sequences (read-only)
uniqseq --read-sequences ./prod-sequences dev-logs.log

# Or: Apply production sequences + save new observations
uniqseq --read-sequences ./prod-sequences --library-dir ./dev-lib dev-logs.log
```

### Use Case 5: Monitoring Long-Running Jobs

**Scenario**: Monitor sequence discovery in real-time.

```bash
# Start long-running job
uniqseq large-file.log --library-dir ./mylib &

# Monitor progress (separate terminal)
watch -n 1 'jq . mylib/metadata-*/progress.json'
# Shows: total_sequences, lines_processed, lines_skipped

# Or count sequence files
watch -n 1 'ls mylib/sequences/ | wc -l'
```

### Use Case 6: Processing Multiple Files

**Scenario**: Process multiple files as a single stream.

```bash
# Use cat to concatenate files
cat file1.log file2.log file3.log | \
  uniqseq --library-dir ./mylib

# Or with process substitution
uniqseq <(cat app1.log app2.log app3.log) --library-dir ./mylib
```

**Rationale**: Multi-file support removed - same as `cat`, no added value.

## Implementation Plan

### Phase 1: Basic Library Mode

**Tasks**:
1. Add `--library-dir` flag
2. Implement directory creation (parent, sequences/, metadata-<timestamp>/)
3. Implement sequence file reading (load all files from sequences/)
4. Implement hash verification and renaming for `.uniqseq` files on load
5. Implement pre-loaded sequence set (unlimited retention)
6. Implement sequence file writing (immediate write with hash-based filename)
7. Write config.json to metadata directory at completion
8. UTF-8 validation for text mode sequences
9. Tests for load/save roundtrip

**Acceptance Criteria**:
- Can create new library from scratch
- Can load sequences from existing library into pre-loaded set
- `.uniqseq` files renamed if hash doesn't match filename (config changed)
- Can save observed sequences to library with hash-based filenames
- Pre-loaded sequences treated as "already seen" (skip on first observation)
- UTF-8 validation prevents incompatible files
- Tests achieve 95%+ coverage

### Phase 2: Read-Only Sequence Loading

**Tasks**:
1. Add `--read-sequences` flag (can be specified multiple times)
2. Implement arbitrary directory reading (any filenames/extensions)
3. Implement noise file skipping (`.DS_Store`, etc.)
4. Load into same pre-loaded sequence set as library
5. Tests for read-only loading

**Acceptance Criteria**:
- Can load sequences from multiple directories
- Noise files skipped silently
- All pre-loaded sequences (from `--read-sequences` + `--library-dir`) in same set
- Tests cover various filename/extension patterns

### Phase 3: Library Saving of Pre-loaded Sequences

**Tasks**:
1. Implement saving of pre-loaded sequences when observed
2. Check for existing files before writing (avoid overwriting)
3. Track saved sequences to avoid duplicate writes
4. Update statistics (sequences_preloaded, sequences_saved)
5. Tests for pre-loaded sequence saving

**Acceptance Criteria**:
- Pre-loaded sequences saved to library when observed in input
- No duplicate writes (idempotent)
- Statistics accurate
- Tests cover all saving scenarios

### Phase 4: Progress Monitoring

**Tasks**:
1. Implement progress.json file updates
2. Atomic file writes (temp + rename)
3. Update progress file every 1000 lines
4. Tests for progress tracking

**Acceptance Criteria**:
- Progress file updated periodically
- Atomic writes prevent partial reads
- Monitoring workflow documented

### Phase 5: Documentation and Examples

**Tasks**:
1. Update IMPLEMENTATION.md with library design
2. Update EXAMPLES.md with use cases
3. Update TEST_COVERAGE.md with test plans
4. Add user warnings about configuration compatibility

**Acceptance Criteria**:
- All documentation updated
- Real-world examples included
- Configuration compatibility warnings documented

## Testing Strategy

### Unit Tests

**Directory Operations**:
- `test_create_library_structure()` - Create parent/sequences/metadata dirs
- `test_load_sequences_from_library()` - Load from sequences/
- `test_load_sequences_multiple_read_dirs()` - Load from multiple `--read-sequences`
- `test_save_sequences_to_library()` - Write with hash-based names
- `test_sequence_filename_ignored_on_load()` - Any filename works
- `test_noise_files_skipped()` - Skip .DS_Store, .gitignore, etc.

**Pre-loaded Sequence Set**:
- `test_preloaded_set_unlimited_retention()` - Never evicted
- `test_preloaded_treated_as_seen()` - Skip on first observation
- `test_preloaded_and_discovered_separate()` - Different handling

**Library Saving**:
- `test_save_newly_discovered_sequences()` - New sequences saved
- `test_save_preloaded_when_observed()` - Pre-loaded sequences saved when seen
- `test_idempotent_saving()` - Don't overwrite existing files
- `test_saved_sequences_tracking()` - Track what's been saved

**File Format (Delimiter Handling)**:
- `test_sequence_file_no_trailing_delimiter_text()` - Text files don't end with newline
- `test_sequence_file_no_trailing_delimiter_binary()` - Binary files don't end with null byte
- `test_read_sequence_file_text_mode()` - Read splits correctly (no extra empty line)
- `test_read_sequence_file_binary_mode()` - Binary read splits correctly
- `test_write_read_roundtrip_text()` - Write then read produces identical sequence
- `test_write_read_roundtrip_binary()` - Binary write then read roundtrip
- `test_trailing_delimiter_warning()` - Warn (not error) if file has trailing delimiter
- `test_sequence_ending_with_empty_record()` - Valid sequence with empty final record

**Validation Tests**:
- `test_utf8_validation_text_mode()` - Reject non-UTF-8 in text mode
- `test_binary_accepts_anything()` - Binary mode accepts all data

**Metadata Tests**:
- `test_config_file_timestamped()` - Unique metadata dir per run
- `test_config_file_content()` - Correct settings recorded
- `test_progress_file_updates()` - Progress tracking works
- `test_atomic_file_writes()` - No partial writes

### Integration Tests

**Library Workflows**:
- `test_build_library_incremental()` - Sequences accumulate over runs
- `test_pause_resume_workflow()` - Load existing, add new sequences
- `test_metadata_per_run_isolated()` - Each run creates separate metadata

**Combined Workflows**:
- `test_read_sequences_with_library()` - Both flags together
- `test_multiple_read_sequences_dirs()` - Multiple pre-load sources
- `test_preloaded_sequences_saved_to_library()` - Pre-loaded → library when observed

**End-to-End Tests**:
- `test_build_library_workflow()` - Complete workflow from scratch
- `test_filter_with_patterns_workflow()` - Read-only usage
- `test_monitoring_workflow()` - Progress file updates during processing

### Edge Cases

- Empty sequences directory
- Sequences directory with single file
- Very large library (10k+ sequences)
- Corrupted sequence file (partial write)
- Non-UTF-8 file in text mode
- Directory with only noise files (.DS_Store, etc.)
- Concurrent access to same library
- Disk full during write
- File permissions errors
- Pre-loaded sequence observed multiple times (save once)

## Documentation Requirements

### Update IMPLEMENTATION.md

Add sections:
- Directory-based pattern library design
- Pre-loaded sequence set (unlimited retention)
- Library mode: load + save observed sequences
- `--read-sequences` for flexible pattern loading
- Sequence file format (native format)
- Metadata file format (timestamped, output-only)
- No metadata validation (user responsibility)
- Noise file handling

### Update EXAMPLES.md

Add examples:
- Building pattern libraries over time
- Filtering with known patterns
- Combining multiple pattern sources
- Multi-system pattern sharing
- Monitoring long-running jobs
- Processing multiple files with cat

### Update TEST_COVERAGE.md

Document test coverage for:
- Directory operations
- Pre-loaded sequence set
- Library saving of observed sequences
- UTF-8 validation
- Noise file skipping
- Progress tracking

## Success Criteria

Stage 3 is successful if:
1. Library mode enables pattern accumulation across runs
2. Pre-loaded sequences from multiple sources can be combined
3. Pre-loaded sequences saved to library when observed
4. Native format enables easy inspection with standard tools
5. Immediate writes provide real-time monitoring without performance issues
6. UTF-8 validation prevents incompatible files in text mode
7. Noise file handling works transparently (no user intervention)
8. Documentation includes real-world examples
9. Tests achieve 95%+ coverage
