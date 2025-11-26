# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No unreleased changes yet.

---

## [0.1.0] - 2025-11-26

**Initial Release** - Production-ready streaming multi-line sequence deduplicator.

uniqseq removes repeated sequences of lines from text streams and files while preserving all unique content. Unlike traditional line-based deduplication tools (`uniq`, `sort -u`), uniqseq detects and removes repeated **sequences** of lines, making it ideal for cleaning verbose logs, terminal sessions, and repetitive output.

### 🎯 Core Features

**Sequence Deduplication**
- Streaming multi-line sequence detection and removal
- Context-aware matching tracks WHERE sequences occur for accurate duplicate detection
- Configurable window size (default: 10 lines, range: 1+)
- Order preservation - first occurrence of each sequence is kept
- Oracle-compatible algorithm with 100% test compatibility

**Memory Management**
- Bounded memory for streaming with configurable limits
- Default: 100,000 line history, 10,000 unique sequences
- Unlimited modes for file processing (`--unlimited-history`, `--unlimited-unique-sequences`)
- Auto-detection: file inputs default to unlimited, stdin defaults to bounded
- LRU eviction for sequence tracking when limits reached

### 📥 Input Flexibility

**Text Processing**
- Standard input/output for Unix pipelines
- Custom delimiters beyond newlines (`--delimiter`)
- Skip fixed-width prefixes like timestamps (`--skip-chars N`)
- Transform lines via shell commands for flexible hashing (`--hash-transform`)

**Binary Mode**
- Process binary files and mixed encodings (`--byte-mode`)
- Hex delimiter support (`--delimiter-hex`)
- Null-terminated records, network captures, firmware analysis

### 🎨 Output Control

**Statistics**
- Table format (default) with Rich formatting
- JSON format for automation (`--stats-format json`)
- Shows: lines processed/emitted/skipped, redundancy %, unique sequences, config

**Inspection Tools**
- Inverse mode: show only duplicates (`--inverse`)
- Annotations: inline markers where duplicates were removed (`--annotate`)
- Custom annotation templates (`--annotation-format`)
- Explain mode: diagnostic messages for deduplication decisions (`--explain`)

### 🗂️ Pattern Libraries

**Reusable Sequences Across Runs**
- Pre-load known patterns (`--read-sequences <dir>` - can specify multiple)
- Library mode: load existing + save new patterns (`--library-dir <dir>`)
- Native format storage: file content IS the sequence (no JSON/base64)
- Hash-based filenames: `<blake2b-hash>.uniqseq`
- Preloaded sequences: never evicted, treated as "already seen"
- Metadata tracking: timestamped audit trail (output-only)

**Use Cases**
- Learn patterns from one log, apply to others
- Build organizational pattern libraries
- Incremental learning across multiple runs
- Pause/resume deduplication workflows

### 🔍 Pattern Filtering

**Selective Deduplication**
- Track patterns: only deduplicate matching lines (`--track <regex>`)
- Bypass patterns: exclude from deduplication (`--bypass <regex>`)
- Pattern files: load from files (`--track-file`, `--bypass-file`)
- Sequential evaluation: first match wins (like iptables rules)
- Pattern file format: one regex per line, `#` comments, blank lines ignored

**Common Use Cases**
- Focus on ERROR/FATAL lines only
- Exclude noisy INFO/DEBUG messages
- Process specific event types
- Filter by severity, component, or custom patterns

### 🛠️ Quality & Reliability

**Testing**
- 868 comprehensive tests across unit, integration, and oracle categories
- 85%+ code coverage with coverage requirements in CI
- Oracle testing validates correctness against reference implementation
- Property-based testing for edge cases
- Cross-platform testing (macOS, Linux, Windows)

**CI/CD**
- GitHub Actions workflows: quality, testing, docs, CodeQL
- Python 3.9-3.13 support matrix
- Automated dependency updates via Renovate
- Pre-commit hooks: ruff, mypy, trailing whitespace, etc.
- Read the Docs integration

**Code Quality**
- Type hints throughout (strict mypy)
- Formatted with ruff
- Linted with ruff (replaces black, isort, flake8)
- Pre-commit hooks prevent quality regressions

### 📚 Documentation

**User Documentation** (Read the Docs)
- Quick start guide
- Complete CLI reference
- Feature guides: window size, history, libraries, filtering, etc.
- Use case examples: production monitoring, incident response, operations, etc.
- Algorithm explanation
- Troubleshooting guide

**Developer Documentation**
- Implementation overview with architecture details
- Algorithm design document (data structures, phases, correctness)
- Design rationale for key decisions
- Testing strategy and coverage tracking
- Contribution guidelines

### 🚀 Performance

**Characteristics**
- Streaming: processes line-by-line with minimal memory
- Fast hashing: BLAKE2b with 8-byte digests
- Efficient data structures: PositionalFIFO, LRU caches
- Time complexity: O(n) amortized for n lines
- Space complexity: O(max_history + max_unique_sequences × avg_seq_length)

**Practical Performance**
- Handles GB-sized files with bounded memory
- Real-time processing for live logs and terminal sessions
- Minimal overhead for typical use cases

### 🔧 Technical Details

**Algorithm**
- Position-based duplicate detection (tracks WHERE sequences occur)
- Multi-phase processing pipeline (5 phases per line)
- Multi-candidate evaluation for complex matching scenarios
- Overlap prevention via position arithmetic
- Oracle-compatible EOF flush logic

**Dependencies**
- Python 3.9+ (tested through 3.13)
- `typer` - CLI framework with type hints
- `rich` - Terminal formatting and progress bars
- No other runtime dependencies

**Platform Support**
- Linux, macOS, Windows
- Any platform with Python 3.9+
- Works in: terminals, CI/CD, Docker, cloud environments

### 📋 Release Assets

- **Source Distribution** (`uniqseq-0.1.0.tar.gz`)
- **Wheel Distribution** (`uniqseq-0.1.0-py3-none-any.whl`)
- **Documentation** (https://uniqseq.readthedocs.io)

### 🎉 Getting Started

**Installation** (when released to PyPI):
```bash
pip install uniqseq
```

**Basic Usage**:
```bash
# Remove duplicate sequences from a file
uniqseq session.log > clean.log

# Process from stdin
tail -f app.log | uniqseq

# Smaller sequences (3+ lines instead of 10+)
uniqseq --window-size 3 verbose.log

# Ignore timestamps when comparing
uniqseq --skip-chars 21 "[2024-01-15 10:30:01] app.log"

# Save patterns for reuse
uniqseq --library-dir ~/patterns app.log
```

**Learn More**:
- Quick Start: https://uniqseq.readthedocs.io/en/latest/getting-started/quick-start/
- Examples: https://uniqseq.readthedocs.io/en/latest/examples/
- CLI Reference: https://uniqseq.readthedocs.io/en/latest/reference/cli/

### 🙏 Acknowledgments

This is the initial release of uniqseq, developed with:
- Comprehensive testing and oracle validation
- Modern Python packaging (hatch, hatch-vcs)
- Industry-standard tooling (ruff, mypy, pytest)
- Extensive documentation and examples
- CI/CD automation

Special thanks to the Python community and the developers of the excellent tools that made this project possible.

---

## Release Process

Releases are automated via GitHub Actions when a version tag is pushed:

1. Update CHANGELOG.md with release notes
2. Create and push Git tag: `git tag v0.1.0 && git push origin v0.1.0`
3. GitHub Actions automatically:
   - Creates GitHub Release
   - Publishes to PyPI (when configured)
4. Version number is automatically derived from Git tag

[Unreleased]: https://github.com/JeffreyUrban/uniqseq/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/JeffreyUrban/uniqseq/releases/tag/v0.1.0
