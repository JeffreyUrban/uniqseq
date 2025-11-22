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

## Quality, Tooling, and Maintenance

### Argument Validation

**Requirement**: Fail fast with clear error messages on invalid argument combinations.

**Invalid Combinations**:
```python
# Text-only features with byte mode
--byte-mode --hash-transform      # Error: hash-transform requires text mode
--byte-mode --filter-in           # Error: filtering requires text mode
--byte-mode --skip-chars          # Error: skip-chars requires text mode

# Hex delimiter without byte mode
--delimiter-hex 0x00               # Error: --delimiter-hex requires --byte-mode

# Incompatible delimiter specifications
--delimiter '\n' --delimiter-hex 0x0a  # Error: specify one delimiter type only

# Format without save
--format directory                 # Error: --format requires --save-patterns
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

**Implementation Plan** (v0.2.0):
1. Add pytest-cov to dev dependencies
2. Configure coverage in pyproject.toml
3. Add coverage badge to README
4. Enforce coverage thresholds in CI

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
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

**Implementation Plan** (v0.2.0):
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
- Drop 3.9 support in v2.0.0 (Oct 2025)
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

**Implementation Plan** (v0.2.0):
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

**Implementation Plan** (v0.2.0):
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
3. Create git tag: `git tag v0.1.0`
4. Push tag: `git push origin v0.1.0`
5. GitHub Actions auto-publishes to PyPI

**Implementation Plan** (v0.1.0 - current):
1. ✅ Basic pyproject.toml exists
2. Add full metadata and classifiers
3. Set up PyPI account and tokens
4. Test release to TestPyPI first
5. Release v0.1.0 to PyPI

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

**Implementation Plan** (v0.2.0):
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

**Implementation Plan** (v0.2.0):
1. Set up all CI workflows
2. Configure Dependabot and Mend.io
3. Add stale-bot for issue management
4. Create MAINTENANCE.md with runbook
5. Document on-call procedures

---

## Implementation Roadmap (Revised)

### v0.1.0 (Current - Production Foundation)
- ✅ Core algorithm implemented
- ✅ Basic tests passing (418/418)
- 🔄 **Add quality tooling** (ruff, mypy, pre-commit)
- 🔄 **Improve test coverage** to 95%+
- 🔄 **Add argument validation**
- 🔄 **Set up CI/CD pipeline**
- 🔄 **Publish to PyPI**

### v0.2.0 (Core Enhancements)
- Core features (byte mode, transforms, streaming, etc.)
- ✅ Quality tooling in place
- ✅ 95%+ test coverage
- ✅ CI/CD operational
- ✅ Homebrew formula
- ✅ Automated maintenance

### v0.3.0 (Pattern Libraries)
- Pattern save/load features
- Continue quality standards from v0.2.0

### v0.4.0+ (Future)
- Feature development continues
- Maintain quality standards
- Regular dependency updates
- Python version updates as needed

---

## See Also

- **EXAMPLES.md** - Comprehensive usage examples and composition patterns
- **DESIGN_RATIONALE.md** - Detailed justifications for feature decisions
- **IMPLEMENTATION.md** - Current implementation overview
- **ALGORITHM_DESIGN.md** - Core algorithm documentation
- **TEST_COVERAGE.md** - Test coverage documentation
