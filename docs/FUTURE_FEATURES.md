# Future Features - Planning Document

**Status**: Planning
**Current Version**: v0.1.0
**Target Versions**: v0.2.0, v0.3.0, v1.0.0

This document describes planned enhancement features for future releases of uniqseq. All features listed here are **not yet implemented** but are designed to build on the stable v0.1.0 core algorithm.

---

## Feature Roadmap

### v0.2.0 - Inline Annotations (Planned)
**Priority**: Medium
**Estimated Effort**: Medium
**Dependencies**: Core algorithm (✅ implemented in v0.1.0)

Add optional inline markers showing where duplicate sequences were skipped.

### v0.3.0 - Content Archiving (Planned)
**Priority**: Low
**Estimated Effort**: Medium
**Dependencies**: Core algorithm (✅ implemented in v0.1.0)

Optionally persist skipped sequences to disk for audit/debugging.

### v1.0.0 - Portable Sequence Libraries (Future)
**Priority**: Low
**Estimated Effort**: High
**Dependencies**: Core algorithm (✅ implemented), stable UniqSeq format

Save/load discovered patterns for reuse across runs.

---

## v0.2.0: Inline Annotations

### Overview

When enabled via `--annotate` flag, insert formatted annotation lines in the output stream when duplicate sequences are skipped.

### Use Cases

1. **Transparency**: Users can see where deduplication occurred without having to diff files
2. **Debugging**: Quick reference to what was removed (line ranges)
3. **Auditability**: Track what content was removed inline with output

### Default Annotation Format

```
[... skipped duplicate lines 1234-1243 ...]
```

### Line Numbering Modes

**File mode** (input is a file path): Absolute line numbers (1-indexed from file start)
```
[... skipped duplicate lines 1234-1243 ...]
```

**Streaming mode** (input is stdin): Relative line numbers (backward from current output position, counting only emitted lines)
```
[... skipped duplicate lines back 50-41 ...]
```

**Mode detection**: Automatically determined by input source
- File path argument → file mode (absolute numbers)
- Stdin/pipe → streaming mode (relative numbers)

**Override**: User can explicitly set line number format via CLI flag:
```bash
uniqseq --annotate --line-numbers absolute file.log   # Force absolute
uniqseq --annotate --line-numbers relative file.log   # Force relative
```

### CLI Options

```bash
--annotate                    # Enable annotations (default: disabled)
--line-numbers <mode>         # absolute|relative (auto-detect if not specified)
--annotation-format <string>  # Custom format string (see format specifiers below)
```

### Format Specifiers

Annotation text supports format specifiers:

| Specifier   | Description                           | Example    |
|-------------|---------------------------------------|------------|
| `{start}`   | First line number of skipped sequence | `1234`     |
| `{end}`     | Last line number of skipped sequence  | `1243`     |
| `{count}`   | Number of lines in sequence           | `10`       |
| `{hash}`    | Sequence hash (8-char hex)            | `a3f5c8d9` |

**Format string examples**:

```bash
# Default
uniqseq --annotate file.log
# Output: [... skipped duplicate lines 1234-1243 ...]

# Verbose
uniqseq --annotate --annotation-format "[DUPLICATE: {count} lines ({start}-{end}), hash={hash}]" file.log
# Output: [DUPLICATE: 10 lines (1234-1243), hash=a3f5c8d9]

# Minimal
uniqseq --annotate --annotation-format "[skip {start}-{end}]" file.log
# Output: [skip 1234-1243]
```

### Design Considerations

**Annotations go to stdout** (part of data stream, not UI):
- Rationale: Annotations are part of the processed output, not status messages
- UI messages (statistics, progress) go to stderr
- Allows piping annotated output to another tool

**Distinguishable from actual content**:
- Bracketed format: `[... ... ...]`
- Descriptive text: "skipped duplicate lines"
- Unlikely to match actual log content

### Implementation Notes

**StreamingDeduplicator changes**:
- Add `annotation_enabled` parameter (default: False)
- Add `annotation_format` parameter (default: template string)
- Add `line_number_mode` parameter ('auto', 'absolute', 'relative')
- Emit annotation line to output when skipping sequence

**CLI changes**:
- Add `--annotate` flag
- Add `--line-numbers` option
- Add `--annotation-format` option
- Pass parameters to StreamingDeduplicator

---

## v0.3.0: Content Archiving

### Overview

Optionally write each unique skipped sequence to a file in a specified directory for audit/debugging purposes.

### Use Cases

1. **Archival**: Preserve skipped content for later review without duplicating identical sequences
2. **Auditability**: Track exactly what was removed
3. **Debugging**: Examine skipped sequences offline

### Enabling Archiving

```bash
uniqseq --archive-dir <path> file.log
```

**No default directory**: Archiving is opt-in via the `--archive-dir` parameter
- Directory is created if it doesn't exist (including parent directories)
- If directory exists, continue without error

### Key Properties

**Hash-based naming**: Use sequence hash in filename to avoid duplicating identical content
- Same sequence seen multiple times → written once
- Different sequences → separate files

**Idempotent**: If file exists, don't write again
- Check file existence before writing
- Same hash = same content, no need to rewrite

**Self-documenting**: Files contain the actual skipped lines for reference
- Plain text files
- Original line content preserved

### Default Filename Format

```
uniqseq-{hash}.txt
```

Where `{hash}` is the 8-character hex sequence hash (filesystem-safe).

### CLI Options

```bash
--archive-dir <path>              # Enable archiving to directory
--archive-filename-format <string>  # Custom filename format (see format specifiers below)
```

### Format Specifiers

Archive filenames support format specifiers:

| Specifier        | Description                           | Example               |
|------------------|---------------------------------------|-----------------------|
| `{hash}`         | Sequence hash (8-char hex, filesystem-safe) | `a3f5c8d9`            |
| `{hash_full}`    | Full sequence hash (32-char hex)      | `a3f5c8d9e1b2c4f6...` |
| `{start}`        | First line number of skipped sequence | `00001234`            |
| `{end}`          | Last line number of skipped sequence  | `00001243`            |
| `{count}`        | Number of lines in sequence           | `0010`                |
| `{timestamp}`    | ISO timestamp (sanitized for filenames) | `2025-11-20T14_32_15` |
| `{seq_num}`      | Nth unique sequence skipped           | `0042`                |

**Format string examples**:

```bash
# Default
uniqseq --archive-dir ./archive file.log
# Files: archive/uniqseq-a3f5c8d9.txt

# Descriptive
uniqseq --archive-dir ./archive --archive-filename-format "skipped-{start:08d}-{end:08d}-{hash}.txt" file.log
# Files: archive/skipped-00001234-00001243-a3f5c8d9.txt

# Timestamped
uniqseq --archive-dir ./archive --archive-filename-format "{timestamp}-{hash}.txt" file.log
# Files: archive/2025-11-20T14_32_15-a3f5c8d9.txt

# Numbered
uniqseq --archive-dir ./archive --archive-filename-format "skip-{seq_num:04d}-{hash}.txt" file.log
# Files: archive/skip-0001-a3f5c8d9.txt, archive/skip-0002-e1f2a3b4.txt
```

### File Content Format

```
Lines 1234-1243 (10 lines, hash: a3f5c8d9)
Skipped from: /path/to/file.log
Timestamp: 2025-11-20T14:32:15

--- BEGIN SEQUENCE ---
line content 1
line content 2
...
line content 10
--- END SEQUENCE ---
```

### Implementation Notes

**StreamingDeduplicator changes**:
- Add `archive_dir` parameter (default: None)
- Add `archive_filename_format` parameter (default: template string)
- Track written archive files by hash to avoid duplicates
- Write to archive file when skipping sequence (if enabled)

**CLI changes**:
- Add `--archive-dir` option
- Add `--archive-filename-format` option
- Create directory if it doesn't exist
- Pass parameters to StreamingDeduplicator

**Error handling**:
- Warn if archive directory not writable
- Continue processing even if archive write fails
- Log errors to stderr

---

## v1.0.0: Portable Sequence Libraries

### Overview

Save discovered unique sequence patterns to a library file and load them at startup for immediate matching across runs.

### Use Cases

1. **Pre-load common patterns**: Faster deduplication by reusing discovered patterns
2. **Share patterns**: Distribute pattern libraries across team/deployments
3. **Domain-specific libraries**: Build specialized libraries for build output, test logs, etc.

### Planned Features

**Export unique_sequences to file**:
```bash
uniqseq --export-library patterns.json file.log
```

**Load patterns at startup**:
```bash
uniqseq --import-library patterns.json new_file.log
```

**Merge libraries from multiple runs**:
```bash
uniqseq-merge-lib lib1.json lib2.json -o merged.json
```

**Pattern library management**:
```bash
uniqseq-lib list patterns.json           # List patterns
uniqseq-lib filter patterns.json --min-count 5   # Filter by repeat count
uniqseq-lib combine lib1.json lib2.json  # Combine libraries
```

### Library File Format (Proposed)

JSON format with version information:

```json
{
  "version": "1.0",
  "created": "2025-11-20T14:32:15Z",
  "source": "/path/to/file.log",
  "window_size": 10,
  "patterns": [
    {
      "start_window_hash": "a3f5c8d9",
      "full_sequence_hash": "a3f5c8d9e1b2c4f6a1b2c3d4e5f6a7b8",
      "sequence_length": 10,
      "repeat_count": 3,
      "window_hashes": ["abc123...", "def456...", ...]
    }
  ]
}
```

### CLI Options (Proposed)

```bash
--export-library <path>     # Export patterns to file after processing
--import-library <path>     # Load patterns from file before processing
--library-mode <mode>       # merge|replace (default: merge)
```

### Implementation Notes

**File format stability**:
- Use semantic versioning for library format
- Backward compatibility for minor version bumps
- Migration tools for major version changes

**Performance considerations**:
- Large libraries may increase startup time
- Consider lazy loading or indexing for very large libraries
- Memory usage scales with library size

**Security considerations**:
- Validate library file format
- Hash verification to prevent tampering
- Consider signing libraries for production use

---

## Combined Features Example

Once all features are implemented, a complete workflow might look like:

```bash
# First run: Build pattern library
uniqseq --export-library build-patterns.json build.log > clean-build.log

# Subsequent runs: Use library with annotations and archiving
uniqseq --import-library build-patterns.json \
        --annotate \
        --archive-dir ./duplicates \
        new-build.log > clean-new-build.log
```

**Result**:
- Faster processing (pre-loaded patterns)
- Annotated output showing where duplicates were removed
- Archive of skipped sequences for audit
- Clean deduplicated output

---

## Implementation Priority Rationale

### Why v0.2.0: Annotations First?
- **User value**: Immediate visibility into what was deduplicated
- **Low complexity**: Minimal changes to core algorithm
- **Foundation**: Format specifiers used by archiving too

### Why v0.3.0: Archiving Second?
- **Lower priority**: Less commonly needed than annotations
- **Builds on v0.2.0**: Reuses format specifier infrastructure
- **Standalone value**: Can be used without annotations

### Why v1.0.0: Libraries Last?
- **High complexity**: Requires stable format and versioning
- **Architectural impact**: Loading patterns affects startup
- **Optional optimization**: Core algorithm works well without it

---

## Design Principles for All Features

1. **Opt-in by default**: New features disabled unless explicitly requested
2. **Backward compatible**: Old workflows continue to work unchanged
3. **Composable**: Features work independently or together
4. **Unix philosophy**: Each feature does one thing well
5. **Performance**: No impact when features are disabled
6. **Error resilience**: Continue processing even if optional features fail

---

## Contributing

Feature implementations should follow these guidelines:

**Before implementation**:
1. Review this planning document
2. Discuss approach with maintainers
3. Update planning doc with implementation details

**During implementation**:
1. Write tests first (TDD)
2. Maintain backward compatibility
3. Document CLI options and format specifiers
4. Update IMPLEMENTATION.md with usage examples

**After implementation**:
1. Update version number
2. Move feature from this doc to IMPLEMENTATION.md
3. Add changelog entry
4. Update README with new capabilities

---

## Questions and Discussion

For questions about planned features or to suggest new ones, please:
1. Check existing GitHub issues
2. Open new issue with `enhancement` label
3. Reference this planning document
4. Describe use case and proposed approach

**Note**: This document describes planned work and may change based on user feedback, technical constraints, or changing priorities.
