# Refined Feature Planning

**Status**: Planning (Refined)
**Current Version**:
**Target Versions**: through

This document describes the refined, streamlined feature roadmap for uniqseq. Features are ordered by foundational impact and focus on core competency: multi-line sequence deduplication.

## Design Philosophy

1. **Unix Composition**: Features achievable through composition with standard tools are documented with tested illustrative examples but not built-in
2. **Core Competency**: Focus on multi-line sequence deduplication, not general text processing
3. **Streaming First**: All features must work with unbounded streams
4. **Clear Value**: Each feature must provide value that's hard to replicate with composition

## Feature Roadmap

### Core Enhancements

**Focus**: Foundational flexibility for diverse input types and use cases.

| Feature | Flag | Rationale                                                                                                         |
|---------|------|-------------------------------------------------------------------------------------------------------------------|
| **Unlimited history** | `--unlimited-history` | Remove artificial memory limits for complete deduplication                                                        |
| **Binary mode** | `--byte-mode` | Support binary protocols, network captures, firmware analysis                                                     |
| **Custom delimiters** | `--delimiter <str>`, `--delimiter-hex <hex>` | Records beyond newline-delimited (null-terminated, custom separators)                                             |
| **Simple prefix skip** | `--skip-chars N` | Skip fixed-width timestamps/prefixes (80% use case, no subprocess)                                                |
| **Transform hashing** | `--hash-transform <cmd>` | Flexible prefix handling via Unix filter (20% complex cases)                                                      |
| **Auto-detect streaming** | (automatic) | Auto-detect pipe/stdin and apply bounded memory defaults (file mode: defaults to unlimited history and sequences) |
| **JSON statistics** | `--stats-format json` | Machine-readable stats for automation/monitoring                                                                  |

**Key Design Decisions**:
- `--skip-chars` for simple cases, `--hash-transform` for complex cases. No need for `--skip-until`, `--skip-regex` (achievable via transform).
- **Streaming auto-detection**: Detect pipe/stdin context automatically using `sys.stdin.isatty()`. Apply bounded memory defaults (100k history) for streaming, unlimited for file processing. No explicit `--streaming` flag needed - context is unambiguous.

---

### Sequence Libraries

**Focus**: Reusable sequences across runs and systems.

| Feature | Flag | Rationale |
|---------|------|-----------|
| **Pre-load sequences** | `--read-sequences <path>` (multiple) | Load sequences from any directory (read-only) |
| **Library mode** | `--library-dir <path>` | Load existing + save observed sequences |
| **Native format** | Automatic | File content IS the sequence (no JSON, base64) |
| **Hash-based filenames** | `<hash>.uniqseq` | Saved sequences use hash-based names |
| **Composable** | Both flags work together | Pre-load from multiple sources + save to library |

**Design**:
- **Directory-based storage**: Single parent directory with `sequences/` and `metadata-<timestamp>/` subdirectories
- **Native format**: Sequence files contain raw content (text or binary) with delimiters, no trailing delimiter
- **Pre-loaded sequences**: Unlimited retention (never evicted), treated as "already seen"
- **Metadata output-only**: Config files for audit trail, not read by uniqseq

---

### Track/Bypass and Inspection

**Focus**: Control what gets deduplicated and visibility into results.

| Feature | Flag | Rationale |
|---------|------|-----------|
| **Track** | `--track <regex>`, `--track-from <path>` | Only deduplicate lines matching regex pattern (sequential evaluation) |
| **Bypass** | `--bypass <regex>`, `--bypass-from <path>` | Exclude lines from deduplication (pass through unchanged) |
| **Inverse mode** | `--inverse` | Keep duplicates, remove unique sequences (algorithm-specific, hard to compose) |
| **Annotations** | `--annotate` | Inline markers showing where duplicates were skipped |
| **Annotation format** | `--annotation-format <template>` | Custom annotation templates |

**Key Design Decisions**:
- **Sequential regex evaluation**: Regex patterns (track/bypass, inline/file) evaluated in command-line order, first match wins
- **Regex pattern file format**: One regex per line, `#` comments, blank lines ignored
- **Common regex pattern files**: See EXAMPLES.md for error-patterns.txt, noise-patterns.txt, security-events.txt
- Keep track/bypass despite composition being possible, due to stream reassembly complexity

---

### Polish and Usability

**Focus**: Better user experience and integration.

| Feature | Flag | Rationale |
|---------|------|-----------|
| **Pattern library tools** | `uniqseq-lib` command | Merge, filter, inspect pattern libraries |

---

### Ecosystem Maturity

**Focus**: Production-ready ecosystem and tooling.

| Feature | Flag | Rationale |
|---------|------|-----------|
| **Pattern metadata** | Library includes repeat counts, timestamps | Enable pattern analysis |
| **Library directory format** | `--format directory` | Alternative to JSON for large libraries |

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
| **Track/bypass** | All text features | Byte mode | Regex requires text mode |
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

3. **Track/Bypass Combination**: Can combine
   - `--track` and `--bypass` work together
   - bypass applied after track
   - Both require text mode

4. **Library Compatibility**:
   - Libraries include mode metadata (window_size, delimiter, mode)
   - Must load with compatible settings
   - Binary libraries for binary mode, text for text mode

---

## CLI Design Principles

**Pipeline Order**: Features are applied in this order:
1. **Input** → Read lines/records
2. **Track/Bypass** → Apply track/bypass (bypassed lines pass through)
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

Error: --track requires text mode (incompatible with --byte-mode)
Suggestion: Remove --byte-mode or preprocess with grep before uniqseq

Error: --bypass requires text mode (incompatible with --byte-mode)
Suggestion: Remove --byte-mode or preprocess with grep before uniqseq

Warning: --unlimited-history may cause high memory usage
Current memory: 1.2 GB (estimated)
Suggestion: Monitor memory with --progress
```

---

## Implementation Priorities

**Must Have**:
- Core flexibility (byte mode, delimiters, transforms)
- Streaming support
- JSON stats

**Should Have**:
- Pattern libraries (save/load)
- Incremental mode

**Nice to Have**:
- Track/Bypass (despite composition alternative, user value high)
- Annotations
- Inverse mode

**Polish**:
- Context lines
- Library management tools

---

## Success Criteria

- Can process text logs, binary data, and custom formats in real-time
- Can build and reuse pattern libraries across systems
- Clear visibility into what was deduplicated and why
- Production-ready with ecosystem tooling
- Feature-complete for all common use cases

---

## Quality, Tooling, and Maintenance

### Argument Validation

**Requirement**: Fail fast with clear error messages on invalid argument combinations.

**Invalid Combinations**:
```python
# Hex delimiter without byte mode
--delimiter-hex 0x00               # Error: --delimiter-hex requires --byte-mode

# Incompatible delimiter specifications
--delimiter '\n' --delimiter-hex 0x0a  # Error: specify one delimiter type only
```

**Implementation**:
- Validate in CLI layer before creating deduplicator
- Use typer callbacks for validation
- Provide actionable error messages with suggestions

**Tests**:
- `tests/test_cli_validation.py` - Test all invalid combinations
- Ensure clear error messages are tested

---

### Test Coverage Requirements

**Target**: 95%+ code coverage for core logic, 100% for argument validation

**Coverage by Module**:

| Module | Target Coverage | Focus Areas |
|--------|----------------|-------------|
| `deduplicator.py` | 95%+ | All algorithm paths, edge cases |
| `cli.py` | 90%+ | Argument validation, error handling |
| Hash functions | 100% | Critical correctness |
| Data structures | 95%+ | PositionalFIFO, UniqSeq operations |

**Coverage Tools**:
```bash
# Generate coverage report
pytest --cov=src/uniqseq --cov-report=html --cov-report=term

# Enforce minimum coverage in CI
pytest --cov=src/uniqseq --cov-fail-under=95
```

**Gap Analysis**:
- Identify untested code paths
- Add tests for edge cases discovered in production
- Maintain TEST_COVERAGE.md with known gaps and rationale

**Implementation Plan** :
1. Add pytest-cov to dev dependencies
2. Configure coverage in pyproject.toml
3. Add coverage badge to README
4. Enforce coverage thresholds in CI

---

### Realistic Test Fixtures and Executable Examples

**Goal**: Create comprehensive, realistic test scenarios that also serve as user-facing documentation examples.

**Two-Track Approach**:

#### 1. Realistic Test Fixtures (`tests/fixtures/scenarios/`)

**Purpose**: Synthetic but realistic data representing common use cases

**Organization**:
```
tests/fixtures/scenarios/
├── server_logs/
│   ├── apache_access.log          # Web server access logs
│   ├── nginx_error.log             # Error log patterns
│   ├── syslog_messages.log         # System logs
│   └── json_structured.log         # Structured logging
├── development/
│   ├── pytest_output.txt           # Test framework output
│   ├── npm_install.txt             # Package manager output
│   ├── git_log.txt                 # Version control logs
│   └── compiler_warnings.txt       # Build output
├── monitoring/
│   ├── kubernetes_events.log       # Container orchestration
│   ├── prometheus_metrics.txt      # Metrics output
│   ├── application_traces.log      # Distributed tracing
│   └── health_checks.log           # Service health
├── security/
│   ├── auth_attempts.log           # Authentication logs
│   ├── firewall_rules.log          # Network security
│   └── audit_trail.log             # Compliance logs
└── binary/
    ├── null_delimited.dat          # Binary protocols
    ├── network_capture.pcap        # Packet captures (simplified)
    └── custom_protocol.bin         # Binary format examples
```

**Characteristics**:
- **Synthetic but realistic**: Generated patterns matching real-world formats
- **Well-documented**: Each fixture includes header comments explaining the scenario
- **Deterministic**: Reproducible generation scripts
- **Variety**: Cover timing patterns, error bursts, interleaved streams
- **Size ranges**: Small (10-100 lines), medium (1K-10K lines), large (100K+ lines)

**Generation**:
- Extend `tests/generate_fixtures.py` for scenario generation
- Include realistic timestamps, IPs, UUIDs, error codes
- Preserve privacy - no real log data

#### 2. Executable Examples (`docs/examples/`)

**Purpose**: User-facing documentation that is automatically tested in CI

**Documentation Format**: MyST Markdown (`.md` files)
- **MyST** (Markedly Structured Text) - CommonMark + Sphinx directives
- GitHub-friendly (renders as regular Markdown)
- Powerful features (admonitions, tabs, cross-references)
- Sphinx-ready for future documentation site
- Sybil fully supports MyST

**Organization**:
```
docs/examples/
├── 01_basic_usage.md               # Getting started
├── 02_server_logs.md               # Web/app server log deduplication
├── 03_development_tools.md         # Dev workflow examples
├── 04_monitoring.md                # Observability use cases
├── 05_binary_data.md               # Binary protocols
├── 06_advanced_patterns.md         # Complex scenarios
└── 07_composition.md               # Unix pipeline patterns
```

**Example Format** (MyST Markdown):
````markdown
# Server Log Deduplication

Remove repeated log sequences while preserving unique entries.

## Apache Access Logs

Remove repeated access patterns while preserving unique requests:

```{code-block} console
$ uniqseq --window-size 100 tests/fixtures/scenarios/server_logs/apache_access.log | head -5
192.168.1.1 - - [22/Nov/2024:10:15:32 +0000] "GET /index.html HTTP/1.1" 200 1234
192.168.1.2 - - [22/Nov/2024:10:15:33 +0000] "GET /api/users HTTP/1.1" 200 5678
192.168.1.1 - - [22/Nov/2024:10:15:35 +0000] "GET /about.html HTTP/1.1" 200 2345
192.168.1.3 - - [22/Nov/2024:10:15:36 +0000] "POST /api/login HTTP/1.1" 200 432
192.168.1.2 - - [22/Nov/2024:10:15:40 +0000] "GET /api/posts HTTP/1.1" 200 9876
```

:::{tip}
Use `--skip-chars 30` to skip timestamps and deduplicate by content only.
:::

## Ignore Timestamps for Content-Based Deduplication

```{code-block} console
$ uniqseq --skip-chars 30 tests/fixtures/scenarios/server_logs/apache_access.log | wc -l
42
```

The `--skip-chars 30` skips the timestamp field, deduplicating based on IP + request.

:::{seealso}
See [Binary Mode](./05_binary_data.md) for null-delimited logs.
:::
````

**Testing Tool**: Sybil (pytest plugin)
- **Actively maintained** (2024-2025)
- **Multi-format support** - Markdown, MyST, reStructuredText
- **Extensible parsers** - Custom bash/console parser
- **Pytest integration** - Works with existing test suite
- **Documentation**: https://sybil.readthedocs.io/

**Execution via Sybil**:
```python
# conftest.py or tests/test_examples.py
from sybil import Sybil
from sybil.parsers.myst import CodeBlockParser
from typer.testing import CliRunner
from uniqseq.cli import app

runner = CliRunner()

def evaluate_console_block(example):
    """Execute uniqseq commands using CliRunner"""
    lines = example.parsed.strip().split('\n')

    # Parse command (starts with $) and expected output
    command_line = lines[0]
    assert command_line.startswith('$ '), "Console block must start with $ prompt"

    cmd = command_line[2:]  # Remove '$ ' prefix
    expected_output = '\n'.join(lines[1:])

    # Run via CliRunner (faster than subprocess, better errors)
    if cmd.startswith('uniqseq '):
        args = cmd[8:].split()  # Remove 'uniqseq ' prefix
        result = runner.invoke(app, args)
        assert result.exit_code == 0, f"Command failed: {result.stderr}"
        assert result.stdout.strip() == expected_output.strip()
    else:
        # Fall back to subprocess for shell commands (pipes, etc.)
        import subprocess
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert result.stdout.strip() == expected_output.strip()

# Configure Sybil
pytest_collect_file = Sybil(
    parsers=[
        CodeBlockParser(['console', 'shell'], evaluate_console_block),
    ],
    pattern='docs/examples/*.md',
    fixtures=['tmp_path'],  # Provide pytest fixtures to examples
).pytest()
```

**Dependencies**:
```toml
# pyproject.toml
[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "sybil>=6.0.0",      # Executable documentation testing
    "myst-parser>=2.0.0", # MyST Markdown support
    # ... other dev dependencies
]
```

#### 3. Integration

**Cross-references**:
- Examples reference fixtures: `tests/fixtures/scenarios/server_logs/apache_access.log`
- Test cases reference examples: "See docs/examples/02_server_logs.md for usage"
- README links to examples for each feature

**CI Integration**:
```yaml
# .github/workflows/test.yml
- name: Install dependencies
  run: pip install -e ".[dev]"  # Includes sybil, myst-parser

- name: Test code
  run: pytest tests/

- name: Test documentation examples
  run: pytest docs/examples/ --sybil  # Sybil auto-discovers via conftest.py
```

**Benefits**:
1. **Always accurate**: Examples fail if they break
2. **Realistic**: Users see real-world scenarios
3. **Comprehensive**: Examples double as integration tests
4. **Discoverable**: Organized by use case, not implementation detail
5. **Maintainable**: Single source of truth for examples
6. **Fast**: CliRunner executes in-process (no subprocess overhead)
7. **Debuggable**: Python stack traces, not shell errors

**Quality Standards**:
- All examples must pass in CI
- Examples must reference real fixture files (no inline heredocs)
- Each example must have explanatory text
- Examples must cover all major features
- Examples must show both input and output

**Tool Selection Rationale**:

| Decision | Alternatives Considered | Rationale |
|----------|------------------------|-----------|
| **Sybil** | cram, pytest-markdown-docs, mktestdocs, bats-core | Actively maintained (2024-2025), multi-format, extensible, pytest integration |
| **MyST Markdown** | Plain Markdown, reStructuredText | CommonMark compatible + Sphinx directives, GitHub-friendly, future-proof |
| **CliRunner** | subprocess, bats-core | In-process execution, better errors, code coverage, natural fit for Python CLI |
| **Skip bats-core** | Use bats for shell testing | Avoid duplication, examples ARE tests, simpler maintenance |

**Implementation Stages**:
1. **Stage 3-4**: Generate realistic test fixtures for common scenarios
2. **Stage 4-5**: Create initial executable examples (basic usage, server logs)
3. **Stage 5**: Expand examples to cover all features
4. **Stage 5**: Add Sybil to CI pipeline
5. **Future**: Optional Sphinx docs site using same MyST markdown files

---

### Quality Tooling

**Code Quality Stack**:

| Tool | Purpose | Configuration |
|------|---------|---------------|
| **ruff** | Linting + formatting (replaces black, isort, flake8) | `pyproject.toml` |
| **mypy** | Static type checking | `pyproject.toml` |
| **pre-commit** | Git hooks for quality checks | `.pre-commit-config.yaml` |
| **pytest** | Testing framework | `pyproject.toml` |
| **pytest-cov** | Coverage reporting | `pyproject.toml` |

**Ruff Configuration**:
```toml
[tool.ruff]
target-version = "py39"
line-length = 100

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "UP",  # pyupgrade
]

[tool.ruff.format]
quote-style = "double"
```

**Mypy Configuration**:
```toml
[tool.mypy]
python_version = "3.9"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

**Pre-commit Hooks**:
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev:
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev:
    hooks:
      - id: mypy
        additional_dependencies: [types-all]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev:
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

**Implementation Plan** :
1. Add quality tools to pyproject.toml
2. Configure all tools in pyproject.toml
3. Set up pre-commit hooks
4. Run on entire codebase, fix issues
5. Enforce in CI

---

### Python Version Compatibility

**Support Policy**: Support Python 3.9+ (current stable versions)

**Version Matrix**:
| Python Version | Status | Support Until |
|----------------|--------|---------------|
| 3.9 | ✅ Minimum | Oct 2025 |
| 3.10 | ✅ Supported | Oct 2026 |
| 3.11 | ✅ Supported | Oct 2027 |
| 3.12 | ✅ Supported | Oct 2028 |
| 3.13 | ✅ Supported | Oct 2029 |

**Testing Strategy**:
- Test matrix in CI (all supported versions)
- Use `pyproject.toml` to specify minimum version
- Use pyupgrade to enforce minimum syntax

**Configuration**:
```toml
[project]
requires-python = ">=3.9"
```

**CI Matrix**:
```yaml
strategy:
  matrix:
    python-version: ["3.9", "3.10", "3.11", "3.12", "3.13"]
```

**Version Migration Plan**:
- Drop 3.9 support in (Oct 2025)
- Add 3.14+ support as released
- Announce version drops 6 months in advance

---

### Dependency Management

**Approach**: Minimal dependencies, lock file for reproducibility

**Core Dependencies**:
```toml
[project]
dependencies = [
    "typer>=0.9.0",      # CLI framework
    "rich>=13.0.0",      # Terminal formatting
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.1.9",
    "mypy>=1.8.0",
    "pre-commit>=3.6.0",
]
```

**Dependency Updates**:
- **Dependabot**: Auto-create PRs for security updates
- **Renovate**: Alternative for more control over update frequency
- **Mend.io**: Vulnerability scanning and auto-remediation

**Update Policy**:
- Security updates: Immediate (automated)
- Minor updates: Monthly review
- Major updates: Quarterly review with breaking change assessment

**Lock File**:
```bash
# Generate lock file for reproducible installs
pip-compile pyproject.toml -o requirements.txt
pip-compile pyproject.toml --extra dev -o requirements-dev.txt
```

**Implementation Plan** :
1. Configure Dependabot in `.github/dependabot.yml`
2. Set up Mend.io for vulnerability scanning
3. Add dependency update workflow
4. Document update policy

---

### CI/CD Pipeline (GitHub Actions)

**Workflows**:

#### 1. Test Workflow (`.github/workflows/test.yml`)
```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run tests with coverage
        run: |
          pytest --cov=src/uniqseq --cov-report=xml --cov-fail-under=95

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
```

#### 2. Quality Workflow (`.github/workflows/quality.yml`)
```yaml
name: Quality

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run ruff (lint + format check)
        run: |
          ruff check .
          ruff format --check .

      - name: Run mypy
        run: mypy src/uniqseq
```

#### 3. Release Workflow (`.github/workflows/release.yml`)
```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  release:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Build package
        run: |
          pip install build
          python -m build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_TOKEN }}
```

**Implementation Plan** :
1. Create workflow files
2. Configure secrets (PYPI_TOKEN)
3. Add status badges to README
4. Test workflows on feature branch

---

### PyPI Package

**Package Structure**:
```
uniqseq/
├── pyproject.toml          # Modern Python packaging
├── README.md               # PyPI description
├── LICENSE                 # MIT or Apache 2.0
├── src/
│   └── uniqseq/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       └── deduplicator.py
└── tests/
```

**pyproject.toml Configuration**:
```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "uniqseq"
version = "0.1.0"
description = "Streaming multi-line sequence deduplicator"
readme = "README.md"
requires-python = ">=3.9"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
keywords = ["deduplication", "logs", "sequences", "streaming"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
]

[project.scripts]
uniqseq = "uniqseq.cli:main"

[project.urls]
Homepage = "https://github.com/yourusername/uniqseq"
Documentation = "https://github.com/yourusername/uniqseq/blob/main/README.md"
Repository = "https://github.com/yourusername/uniqseq"
Issues = "https://github.com/yourusername/uniqseq/issues"
```

**Release Process**:
1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create git tag: `git tag`
4. Push tag: `git push origin`
5. GitHub Actions auto-publishes to PyPI

**Implementation Plan** ( - current):
1. ✅ Basic pyproject.toml exists
2. Add full metadata and classifiers
3. Set up PyPI account and tokens
4. Test release to TestPyPI first
5. Release to PyPI

---

### Homebrew Package

**Formula Location**: `homebrew-uniqseq` tap (separate repo)

**Formula Template** (`uniqseq.rb`):
```ruby
class Uniqseq < Formula
  include Language::Python::Virtualenv

  desc "Streaming multi-line sequence deduplicator"
  homepage "https://github.com/yourusername/uniqseq"
  url "https://files.pythonhosted.org/packages/.../uniqseq-0.1.0.tar.gz"
  sha256 "..."
  license "MIT"

  depends_on "python@3.11"

  resource "typer" do
    url "https://files.pythonhosted.org/packages/.../typer-0.9.0.tar.gz"
    sha256 "..."
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/.../rich-13.0.0.tar.gz"
    sha256 "..."
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    output = shell_output("#{bin}/uniqseq --help")
    assert_match "Streaming multi-line sequence deduplicator", output
  end
end
```

**Installation**:
```bash
brew tap yourusername/uniqseq
brew install uniqseq
```

**Update Process**:
1. Release new version to PyPI
2. Update formula with new URL and sha256
3. Test: `brew install --build-from-source uniqseq`
4. Push formula update

**Implementation Plan** :
1. Create `homebrew-uniqseq` repository
2. Generate initial formula
3. Test installation
4. Document in README
5. Submit to homebrew-core (optional, after maturity)

---

### Maintenance Plan

**Automated Maintenance Tasks**:

| Task | Tool | Frequency | Automation |
|------|------|-----------|------------|
| **Dependency updates** | Dependabot | Weekly | Auto-create PRs |
| **Security scanning** | Mend.io | Daily | Auto-alerts + fixes |
| **CI tests** | GitHub Actions | Every push | Automatic |
| **Coverage tracking** | Codecov | Every push | Automatic |
| **Python version tests** | GitHub Actions | Every push | Automatic |
| **Release to PyPI** | GitHub Actions | On tag | Automatic |
| **Homebrew formula update** | Manual | After release | Semi-automated |

**Manual Maintenance Tasks**:

| Task | Frequency | Owner |
|------|-----------|-------|
| Review Dependabot PRs | Weekly | Maintainer |
| Triage issues | Daily | Maintainer |
| Review PRs | As needed | Maintainer |
| Release planning | Quarterly | Maintainer |
| Documentation updates | As needed | Maintainer |
| Python version policy review | Annually | Maintainer |

**Health Metrics** (tracked automatically):

- Test pass rate (target: 100%)
- Code coverage (target: 95%+)
- Known vulnerabilities (target: 0)
- Open issues (target: < 10)
- PR response time (target: < 48 hours)
- Release cadence (target: quarterly for features, immediate for security)

**Automation Opportunities**:
- Auto-close stale issues (30 days inactive)
- Auto-label issues based on content
- Auto-assign reviewers based on files changed
- Auto-merge Dependabot PRs after tests pass
- Auto-generate release notes from commits

**Implementation Plan** :
1. Set up all CI workflows
2. Configure Dependabot and Mend.io
3. Add stale-bot for issue management
4. Create MAINTENANCE.md with runbook
5. Document on-call procedures

---

## Implementation Roadmap

### Stage 1: Production Foundation - ✅ COMPLETED
- ✅ Core algorithm implemented
- ✅ Tests passing (462 passed, 1 skipped)
- ✅ Quality tooling (ruff, mypy, pre-commit)
- ✅ Test coverage improved to 94.55% (exceeds 90% threshold, 0.45% from 95% target)
- ✅ CI/CD pipeline (GitHub Actions: quality + test matrix Python 3.9-3.13)
- ✅ Comprehensive argument validation framework with clear error messages
  - Validates semantic constraints (window_size ≤ max_history)
  - Fail-fast validation before processing
  - Extensible design for future features
- ✅ Coverage improvement tests added (6 new tests for edge cases)
  - LRU eviction scenarios
  - CLI exception handling paths
  - KeyboardInterrupt handling
- ⏳ **PyPI publishing** (deferred to Stage 5 per user request)

### Stage 2: Core Enhancements - ✅ COMPLETED
**Focus**: Foundational flexibility for diverse input types and use cases

**Summary**: All Stage 2 features have been successfully implemented and tested.
- 518 tests passing (94% code coverage)
- All Phase 1-4 features complete
- Comprehensive documentation updated
- Quality requirements met (except 95% coverage target - currently at 94%)

**Implementation Order** (prioritized by user value and complexity):

**Phase 1: Output and Filtering** (High value, low complexity)

1. ✅ **JSON statistics** (`--stats-format json`) - Enables machine-readable output
   - **Status**: Complete
   - **Implementation**: Added `--stats-format {table|json}` flag with validation
   - **JSON output**: Structured statistics to stderr
   - **Testing**: 3 new tests (465 total passing, 94.53% coverage)
   - **Use cases**: Pipeline integration, monitoring, automated analysis

**Phase 2: History Management** (Foundation for scaling)
2. ✅ **Unlimited history mode** (`--unlimited-history`) - Complete
3. ✅ **Auto-detect streaming** - Complete

**Phase 3: Input Flexibility** (Enables new use cases)
4. ✅ **Simple prefix skip** (`--skip-chars N`) - Complete
5. ✅ **Custom delimiters** (`--delimiter <str>`) - Complete

**Phase 4: Advanced Features** (Complex, enables power users)
6. ✅ **Transform hashing** (`--hash-transform <cmd>`) - Complete
   - **Status**: Complete
   - **Implementation**: Added `--hash-transform` parameter, subprocess-based line transformation
   - **Features**:
     - Pipes each line through Unix filter for hashing (preserves original output)
     - Validates single-line output (rejects multi-line transforms)
     - 5-second timeout per line with clear error messages
     - Validation: incompatible with `--byte-mode` (text-only feature)
   - **Testing**: 7 new tests (518 total passing, 94% coverage)
   - **Use cases**: Case-insensitive matching, variable-width timestamp removal, field extraction, whitespace normalization
7. ✅ **Binary mode** (`--byte-mode`, `--delimiter-hex`) - Complete
   - **Status**: Complete
   - **Implementation**: Added `--byte-mode` flag, binary record readers, polymorphic type handling, hex delimiter parsing
   - **Features**:
     - Supports bytes input/output with `--byte-mode`
     - Text delimiters with `--delimiter` (escape sequences: \n, \t, \0)
     - Hex delimiters with `--delimiter-hex` (e.g., "00", "0x0a0d")
     - Skip-chars compatible with binary data
     - Validation: `--delimiter-hex` requires `--byte-mode`, mutually exclusive with `--delimiter`
   - **Testing**: 20 new tests (502 total passing, 93% coverage)
   - **Use cases**: Binary protocols, mixed encodings, null-delimited data, CRLF-delimited files

Quality requirements:
- ✅ Comprehensive tests for all features (518 tests passing)
- ⏳ Test coverage maintained at 95%+ (currently 94%, up from 93%)
- ✅ Compatibility validation (text vs binary modes)
- ✅ Extend argument validation for new feature combinations
- ✅ Update IMPLEMENTATION.md with new features
- ✅ Add usage examples to EXAMPLES.md

### Stage 3: Sequence Libraries
**Focus**: Reusable sequence patterns across runs and systems

**Key Features**:
- **Pre-load sequences**: `--read-sequences <path>` (can specify multiple times)
- **Library mode**: `--library-dir <path>` (load existing + save observed)
- **Native format**: File content IS the sequence (no JSON, no base64)
- **Hash-based filenames**: `<hash>.uniqseq` for saved sequences
- **Composable**: Combine `--read-sequences` with `--library-dir`

**Key Design Decisions**:
- **Directory-based**: Single parent directory with `sequences/` and `metadata-<timestamp>/` subdirectories
- **Native format**: Raw sequence content with delimiters, no trailing delimiter
- **Pre-loaded sequences**: Unlimited retention, never evicted, treated as "already seen"
- **Metadata output-only**: Timestamped config files for audit trail, not read by uniqseq
- **No validation**: User responsible for compatible settings across runs
- **File extension**: `.uniqseq` for sequence files saved to library
- **Hash renaming**: Files with mismatched hashes renamed on load to maintain consistency

**See**: [STAGE_3_DETAILED.md](STAGE_3_DETAILED.md) for complete specification

---

### Stage 4: Track/Bypass and Inspection - Planned
**Focus**: Fine-grained control over deduplication and visibility into results

**Key Features**:
- **Sequential Track/Bypass**: `--track <pattern>`, `--bypass <pattern>`, `--track-file <path>`, `--bypass-file <path>`
- **Filter evaluation**: First match wins (command-line order preserved)
- **Inverse mode**: `--inverse` (keep duplicates, remove unique)
- **Annotations**: `--annotate` with `--annotation-format <template>`
- **Common pattern libraries**: error-patterns.txt, noise-patterns.txt, security-events.txt

**Key Design Decisions**:
- Sequential evaluation (like iptables), not OR logic
- Filter file format: one regex per line, `#` comments, blank lines ignored
- Template variables for annotations: `{start}`, `{end}`, `{match_start}`, `{match_end}`, `{count}`

**See**: [STAGE_4_DETAILED.md](STAGE_4_DETAILED.md) for complete specification

---

### Stage 5: Distribution and Automation
**Focus**: Production ecosystem, distribution channels, and automated maintenance

**Key Features**:

#### Executable Documentation and Examples
- **Realistic test fixtures**: Synthetic but realistic scenarios in `tests/fixtures/scenarios/`
  - Server logs, development tools, monitoring, security, binary protocols
  - Generated via extended `tests/generate_fixtures.py`
- **Executable examples**: MyST Markdown in `docs/examples/`
  - User-facing documentation tested in CI via Sybil
  - Examples double as integration tests
  - Single source of truth for documentation
- **Tooling**: Sybil + MyST Markdown + Typer CliRunner
  - See "Realistic Test Fixtures and Executable Examples" section above for details

#### Distribution Channels
- **PyPI**: Primary Python package distribution
  - GitHub Actions workflow for automated publishing on release
  - Use trusted publishing (no API tokens needed)
  - Test releases on TestPyPI first
- **GitHub Releases**: Version tags with changelogs
- **Homebrew**: macOS/Linux CLI tool distribution (evaluate after PyPI is established)
- **conda-forge**: Deferred - evaluate based on target audience

#### Automated Dependency Management
- **Renovate**: Automated dependency updates
  - Weekly schedule for dependency PRs
  - Auto-merge patch updates after CI passes
  - Auto-merge minor updates for dev dependencies
  - Group non-major updates together
  - 3-day minimum release age before updates
  - Concurrent PR limits (5 max, 2/hour) to avoid overwhelming CI
- **Security**: Vulnerability alerts enabled (free tier)
  - No paid security scanning tools
  - GitHub's built-in security alerts

#### Python Version Support
- **Minimum version**: Python 3.9
- **CI matrix testing**: 3.9, 3.10, 3.11, 3.12, 3.13
- **New version handling**: Manual matrix updates when new Python versions release
  - Renovate can help by creating PRs for Python version updates in GitHub Actions
  - Update `python-version` matrix in `.github/workflows/test.yml`
  - Update classifiers in `pyproject.toml`

#### Release Automation
- **PyPI Publishing Workflow**:
  1. Create version tag (e.g., `v0.2.0`)
  2. GitHub Actions automatically:
     - Builds package
     - Runs full test suite
     - Publishes to PyPI using trusted publishing
  3. Manual step: Create GitHub Release with changelog

#### Auto-merge Strategy
- **Patch updates**: Auto-merge after CI passes (minimal risk)
- **Minor dev dependency updates**: Auto-merge after CI passes
- **Other updates**: Require manual review
- **Security updates**: Immediate review and merge

#### CI/CD Requirements
- All workflows must pass before merge
- Test matrix across all supported Python versions
- Quality checks (ruff, mypy) must pass
- Coverage threshold maintained (95%+ target)

---

## See Also

- **[EXAMPLES.md](../user/EXAMPLES.md)** - Comprehensive usage examples and composition patterns
- **[DESIGN_RATIONALE.md](../design/DESIGN_RATIONALE.md)** - Detailed justifications for feature decisions
- **[IMPLEMENTATION.md](../design/IMPLEMENTATION.md)** - Current implementation overview
- **[ALGORITHM_DESIGN.md](../design/ALGORITHM_DESIGN.md)** - Core algorithm documentation
- **[TEST_COVERAGE.md](../testing/TEST_COVERAGE.md)** - Test coverage documentation
