# Refined Feature Planning

**Status**: Planning (Refined)
**Current Version**: v0.1.0
**Target Versions**: v0.2.0 through v1.0.0

This document describes the refined, streamlined feature roadmap for uniqseq. Features are ordered by foundational impact and focus on core competency: multi-line sequence deduplication.

## Design Philosophy

1. **Unix Composition**: Features achievable through composition with standard tools are documented with tested illustrative examples but not built-in
2. **Core Competency**: Focus on multi-line sequence deduplication, not general text processing
3. **Streaming First**: All features must work with unbounded streams
4. **Clear Value**: Each feature must provide value that's hard to replicate with composition

## Feature Roadmap

### v0.2.0 - Core Enhancements

**Focus**: Foundational flexibility for diverse input types and use cases.

| Feature | Flag | Rationale |
|---------|------|-----------|
| **Unlimited history** | `--unlimited-history` | Remove artificial memory limits for complete deduplication |
| **Binary mode** | `--byte-mode` | Support binary protocols, network captures, firmware analysis |
| **Custom delimiters** | `--delimiter <str>`, `--delimiter-hex <hex>` | Records beyond newline-delimited (null-terminated, custom separators) |
| **Simple prefix skip** | `--skip-chars N` | Skip fixed-width timestamps/prefixes (80% use case, no subprocess) |
| **Transform hashing** | `--hash-transform <cmd>` | Flexible prefix handling via Unix filter (20% complex cases) |
| **Streaming output** | `--streaming` | Real-time deduplication for `tail -f` monitoring |
| **JSON statistics** | `--stats-format json` | Machine-readable stats for automation/monitoring |
| **Minimum repeats** | `--min-repeats N` | Only deduplicate sequences seen N+ times (noise reduction) |

**Key Design Decision**: `--skip-chars` for simple cases, `--hash-transform` for complex cases. No need for `--skip-until`, `--skip-regex` (achievable via transform).

---

### v0.3.0 - Pattern Libraries

**Focus**: Reusable sequence patterns across runs and systems.

| Feature | Flag | Rationale |
|---------|------|-----------|
| **Save patterns** | `--save-patterns <path>` | Export discovered sequences for reuse |
| **Load patterns** | `--load-patterns <path>` | Pre-load known patterns at startup |
| **Directory format** | `--format directory` | Hash-based filenames for fast lookup and live inspection |
| **Incremental mode** | `--load-patterns X --save-patterns Y` | Update pattern library across runs |
| **Multiple inputs** | `uniqseq file1 file2 file3` | Process multiple files (positional args) |

**File Formats**:
- **Single file** (default): `patterns.lib` - atomic, versionable, single artifact
- **Directory** (opt-in): `patterns/` - hash-based filenames for live inspection and fast lookup

---

### v0.4.0 - Filtering and Inspection

**Focus**: Control what gets deduplicated and visibility into results.

| Feature | Flag | Rationale |
|---------|------|-----------|
| **Filter-in** | `--filter-in <pattern>` | Only deduplicate lines matching pattern (cannot compose - stream reassembly problem) |
| **Filter-out** | `--filter-out <pattern>` | Exclude lines from deduplication (pass through unchanged) |
| **Filter files** | `--filter-in-file <path>` | Patterns from file |
| **Inverse mode** | `--inverse` | Keep duplicates, remove unique sequences (algorithm-specific, hard to compose) |
| **Annotations** | `--annotate` | Inline markers showing where duplicates were skipped |
| **Annotation format** | `--annotation-format <template>` | Custom annotation templates |

**Key Design Decision**: Keep filtering despite composition being possible, due to stream reassembly complexity (cannot efficiently merge filtered/non-filtered streams while preserving order and streaming).

---

### v0.5.0 - Polish and Usability

**Focus**: Better user experience and integration.

| Feature | Flag | Rationale |
|---------|------|-----------|
| **Context lines** | `-A N`, `-B N`, `-C N` | Show context around duplicates (borrowed from grep) |
| **Quiet mode** | `--quiet` | Suppress output, only show statistics |
| **Pattern library tools** | `uniqseq-lib` command | Merge, filter, inspect pattern libraries |

---

### v1.0.0 - Advanced Use Cases

**Focus**: Specialized applications and ecosystem maturity.

| Feature | Flag | Rationale |
|---------|------|-----------|
| **Multi-file diff** | `--diff <file1> <file2>` | Show unique sequences per file |
| **Pattern metadata** | Library includes repeat counts, positions | Enable pattern analysis |

---

### v2.0.0 - Future Considerations

**Focus**: Advanced matching beyond exact duplicates.

| Feature | Flag | Rationale |
|---------|------|-----------|
| **Fuzzy matching** | `--similarity N` | Catch "almost duplicates" (Hamming/Levenshtein distance) |

---

## Features Removed (Achievable via Composition)

| Feature | Composition Approach | Documentation |
|---------|---------------------|---------------|
| **Directory scanning** | `cat logs/*.log \| uniqseq` | See EXAMPLES.md |
| **File lists** | `xargs cat < files.txt \| uniqseq` | See EXAMPLES.md |
| **Complex skip patterns** | `--hash-transform 'sed ...'` | See EXAMPLES.md |
| **Character-by-character** | Python preprocessing | See EXAMPLES.md |

---

## Features Cut (Out of Scope)

| Feature | Reason | Alternative |
|---------|--------|-------------|
| **Filter expressions** | Scope creep (building expression language) | Use `grep \| awk` chains |
| **Template extraction** | Different problem domain (log parsing) | Use Drain, Spell, angle |
| **Char mode** | Less common, achievable via preprocessing | See EXAMPLES.md |
| **Bio tool features** | Domain-specific, existing specialized tools | Use seqkit, CD-HIT, VSEARCH |

---

## Documentation Requirements

Each feature must include:

1. **Implementation documentation** (IMPLEMENTATION.md)
2. **Usage examples** (EXAMPLES.md)
3. **Test coverage** (TEST_COVERAGE.md)
4. **Design rationale** (DESIGN_RATIONALE.md)

For features removed via composition:
1. **Composition pattern documented** (EXAMPLES.md)
2. **Tested example provided** (tests/examples/)
3. **Comparison with alternatives** (DESIGN_RATIONALE.md)

---

## Feature Compatibility Matrix

This matrix shows which features work together and constraints.

| Feature | Compatible With | Incompatible With | Notes |
|---------|----------------|-------------------|-------|
| **Unlimited history** | All features | (memory limits only) | Monitor memory usage |
| **Byte mode** | Delimiter-hex, archiving | Hash-transform (text-based), filters (regex) | Binary mode disables text features |
| **Delimiter** | All text/byte features | None | Specify text or hex based on mode |
| **Skip-chars** | All text features, hash-transform | Byte mode | Requires text parsing |
| **Hash-transform** | All text features | Byte mode | Transform operates on text |
| **Filter-in/out** | All text features | Byte mode | Regex requires text mode |
| **Annotations** | All modes | None | Adapts format to mode |
| **Pattern libraries** | All modes | None | Library includes mode metadata |

**Key Compatibility Rules**:

1. **Text vs Binary Modes**: Mutually exclusive
   - Byte mode (`--byte-mode`) → disables text features (hash-transform, filters)
   - Text mode (default) → all text features available

2. **Skip + Transform**: Can combine
   - `--skip-chars` and `--hash-transform` work together
   - skip-chars applied first, then transform
   - Both affect hashing only, not output

3. **Filter Combination**: Can combine
   - `--filter-in` and `--filter-out` work together
   - filter-out applied after filter-in
   - Both require text mode

4. **Library Compatibility**:
   - Libraries include mode metadata (window_size, delimiter, mode)
   - Must load with compatible settings
   - Binary libraries for binary mode, text for text mode

---

## CLI Design Principles

**Pipeline Order**: Features are applied in this order:
1. **Input** → Read lines/records
2. **Filter** → Apply filter-in/filter-out (filtered lines pass through)
3. **Skip** → Apply skip-chars (affects hashing only)
4. **Transform** → Apply hash-transform (affects hashing only)
5. **Hash** → Compute line hash
6. **Match** → Check for sequence matches
7. **Output** → Emit unique lines, skip duplicates

**Mode Selection**: Exactly one input mode (text or byte)

**Additive Features**: Annotations and libraries don't affect deduplication logic

**Format Consistency**: Library files include all settings needed to reproduce

**Error Handling**: Incompatible options detected early with clear error messages

### Example Error Messages

```
Error: --hash-transform requires text mode (incompatible with --byte-mode)
Suggestion: Remove --byte-mode for text processing, or use --delimiter-hex for binary

Error: --filter-in requires text mode (incompatible with --byte-mode)
Suggestion: Remove --byte-mode or preprocess with grep before uniqseq

Warning: --unlimited-history may cause high memory usage
Current memory: 1.2 GB (estimated)
Suggestion: Monitor memory with --progress or set --max-memory <limit>
```

---

## Implementation Priorities

**Must Have (v0.2.0)**:
- Core flexibility (byte mode, delimiters, transforms)
- Streaming support
- JSON stats

**Should Have (v0.3.0)**:
- Pattern libraries (save/load)
- Incremental mode

**Nice to Have (v0.4.0)**:
- Filtering (despite composition alternative, user value high)
- Annotations
- Inverse mode

**Polish (v0.5.0)**:
- Context lines
- Library management tools

---

## Success Criteria

**v0.2.0**: Can process text logs, binary data, and custom formats in real-time
**v0.3.0**: Can build and reuse pattern libraries across systems
**v0.4.0**: Clear visibility into what was deduplicated and why
**v0.5.0**: Production-ready with ecosystem tooling
**v1.0.0**: Feature-complete for all common use cases

---

## See Also

- **EXAMPLES.md** - Comprehensive usage examples and composition patterns
- **DESIGN_RATIONALE.md** - Detailed justifications for feature decisions
- **IMPLEMENTATION.md** - Current implementation overview
- **ALGORITHM_DESIGN.md** - Core algorithm documentation
