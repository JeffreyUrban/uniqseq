# Stage 5: Executable Documentation and Examples

**Status**: In Progress
**Branch**: stage-5-executable-docs
**Started**: 2025-01-24
**Last Updated**: 2025-01-24

## Overview

Implement professional documentation with executable examples that are tested in CI, ensuring documentation stays accurate and up-to-date. Use ReadTheDocs for hosting with built-in analytics to track feature interest.

## Goals

1. **Executable Documentation**: Examples in docs are automatically tested via Sybil
2. **Professional Presentation**: Modern, searchable documentation on ReadTheDocs
3. **Analytics**: Track which features get attention to inform development priorities
4. **Single Source of Truth**: Code examples serve as both docs and integration tests

## Technology Stack

### Documentation Framework
- **MkDocs Material** ✅: Modern, responsive documentation theme
  - Production-ready and stable
  - Maintained through 2026
  - Easy migration path to Zensical when it matures
- **PyMdown Extensions** ✅: Rich Markdown features (using instead of MyST)
  - Better MkDocs integration than MyST
  - Mature and well-supported
  - Code highlighting, tabs, admonitions, snippets
- **Termynal Plugin** ✅: Terminal session animations
  - Renders console examples with typing effect
  - Perfect for CLI documentation

### Executable Examples
- **Sybil** ✅: Tests code examples embedded in documentation
  - Standard Markdown parsers (CodeBlockParser)
  - Integrates with pytest
  - Validates examples during CI
- **Custom console evaluator** ✅: For shell command examples
  - Runs actual commands in fixture directories
  - Verifies file output against expected results
  - More powerful than CliRunner for real workflows

### Hosting
- **ReadTheDocs**: Free documentation hosting
  - Built-in analytics (page views, search terms)
  - Automatic builds on commit
  - Version management from git tags
  - Professional, trusted platform

## Documentation Structure

```
docs/
├── index.md                           # Landing page
├── getting-started/
│   ├── installation.md               # Install instructions
│   ├── quick-start.md                # 5-minute intro
│   └── basic-concepts.md             # Core concepts
├── examples/                          # Executable examples (Sybil-tested)
│   ├── basic-deduplication.md        # Simple use cases
│   ├── pattern-filtering.md          # --track and --bypass
│   ├── annotations.md                # --annotate and formats
│   ├── inverse-mode.md               # --inverse for analysis
│   ├── advanced-scenarios.md         # Complex real-world examples
│   ├── log-processing.md             # Server logs, app logs
│   └── terminal-sessions.md          # Cleaning script output
├── guides/                            # How-to guides
│   ├── choosing-window-size.md       # Tuning for your data
│   ├── performance.md                # Optimization tips
│   ├── common-patterns.md            # Recipes and patterns
│   └── troubleshooting.md            # Common issues
├── reference/                         # API documentation
│   ├── cli.md                        # CLI reference (mkdocstrings)
│   ├── deduplicator.md               # Deduplicator class API
│   └── library.md                    # Library usage
└── about/
    ├── algorithm.md                  # How it works
    ├── design-decisions.md           # Why we made these choices
    └── contributing.md               # Contribution guide
```

## Implementation Phases

### Phase 1: Setup and Configuration ✅ **COMPLETED**
**Goal**: Get MkDocs Material working with basic structure

**Completed Tasks**:
- [x] Install dependencies: `mkdocs-material` (9.7.0), `sybil` (9.2.0), `mkdocstrings`
- [x] Create `mkdocs.yml` configuration
- [x] Set up documentation structure (all directories created)
- [x] Configure PyMdown Extensions (using instead of MyST - better MkDocs integration)
- [x] Test local preview: `mkdocs serve` and `mkdocs build --strict` working
- [x] **BONUS**: Reorganized internal docs to `dev-docs/`
- [x] **BONUS**: Added Termynal plugin for terminal animations

**Status**: Complete - infrastructure exceeds initial goals

### Phase 2: Core Documentation Content ✅ **COMPLETED**
**Goal**: Create non-executable documentation content

**Completed Tasks**:
- [x] Write `docs/index.md` (landing page) - existed, reviewed
- [x] Write `docs/getting-started/installation.md` - existed, reviewed
- [x] Write `docs/getting-started/quick-start.md`
- [x] Write `docs/getting-started/basic-concepts.md`
- [x] Write `docs/about/algorithm.md` (adapted from design docs)
- [x] Write `docs/about/design-decisions.md` (adapted from DESIGN_RATIONALE.md)

**Success Criteria**: ✅ Documentation builds and renders correctly with `mkdocs build --strict`

### Phase 3: Executable Examples with Sybil ✅ **COMPLETED**
**Goal**: Create tested examples in documentation

**Completed Tasks**:
- [x] Set up Sybil pytest integration (docs/conftest.py)
- [x] Configure Sybil with standard Markdown parsers (CodeBlockParser)
- [x] Create custom console evaluator for shell command testing
- [x] Implement file verification system for CLI examples
- [x] Add Sybil tests to pytest configuration (testpaths)
- [x] Verify examples run in CI (test_mkdocs_build.py)
- [x] **Working Example**: use-cases/ci-logs/multi-line-sequences.md

**Success Criteria**:
- ✅ Infrastructure: All examples execute successfully via pytest
- ✅ CI Integration: CI fails if examples break

**Status**: Complete - executable documentation infrastructure working

### Phase 4: API Documentation ✅ **COMPLETED**
**Goal**: Auto-generate API docs from code

**Completed Tasks**:
- [x] Install `mkdocstrings` with Python handler
- [x] Configure mkdocstrings in `mkdocs.yml`
- [x] Create reference structure (cli.md, deduplicator.md, library.md exist)
- [x] Populate `docs/reference/cli.md` with complete CLI reference
- [x] Populate `docs/reference/deduplicator.md` with API reference and examples
- [x] Populate `docs/reference/library.md` with library usage guide and integration examples

**Status**: Complete - comprehensive API documentation with examples

### Phase 5: Feature Examples
**Goal**: Document all features accurately based on actual behavior

**Critical Requirement**: All examples MUST be verified against actual code behavior. No invented examples.

**Evidence-Based Strategy**:

1. **Study Existing Tests First**
   - Read relevant test files in `tests/` to understand actual behavior
   - Extract test cases that demonstrate each feature
   - Note edge cases and limitations from tests

2. **Review Design Documentation**
   - Read `dev-docs/design/IMPLEMENTATION.md` for feature descriptions
   - Read `dev-docs/design/ALGORITHM_DESIGN.md` for algorithm behavior
   - Understand design decisions from `dev-docs/design/DESIGN_RATIONALE.md`

3. **Create Fixtures from Real Test Cases**
   - Base fixture data on existing test inputs
   - Generate expected outputs by running actual commands
   - Verify outputs match before documenting

4. **Document What Actually Happens**
   - Describe observed behavior, not assumptions
   - Include exact command-line invocations
   - Show actual output, not idealized output
   - Note any surprising or counterintuitive behavior

5. **Test Every Example**
   - Run CLI commands to generate fixtures
   - Verify Sybil tests pass
   - Confirm Python examples produce same output as CLI

**Documentation Guidelines** (adapt structure to each feature's needs):

### Required Elements

1. **Title & Overview**
   - Clear feature name
   - Brief explanation of what it does and why

2. **Illustrative Examples**
   - Show actual behavior with real fixtures
   - Use `???+ example` or `???+ note`/`???+ success` as appropriate
   - Include both CLI and Python versions
   - Add Sybil verification: `<!-- verify-file: output.txt expected: expected.txt -->`

3. **How It Works**
   - Explain the mechanism
   - Visual diagrams where helpful
   - Reference algorithm or design docs if relevant

4. **See Also**
   - Links to reference docs
   - Related features

### Flexible Structure (adapt per feature)

**Different features need different structures:**

- **Comparison features** (window-size, skip-chars):
  - Same input, multiple outputs showing variations
  - Side-by-side comparisons with highlighting

- **Filter features** (pattern filtering):
  - Show what gets included/excluded
  - May need separate outputs for tracked vs bypassed

- **Mode features** (inverse, annotate):
  - Show normal vs mode-enabled output
  - Highlight what changes

- **Configuration features** (delimiters, history):
  - Show behavior differences
  - May need binary files or special formats

- **Workflow features** (library mode):
  - Show directory structures
  - Multiple files and steps
  - Metadata examples

- **Output features** (progress, stats):
  - Show stderr output, not just stdout
  - Table/JSON format examples

### Style Conventions

- Use `--8<--` for fixture includes
- Use `hl_lines` to highlight relevant parts
- Use `<!-- termynal -->` for CLI examples
- Use numbered annotations `# (1)!` in Python code
- Provide fixture files that can be verified by Sybil
- Ensure CLI and Python produce identical output

**File-Based Testing via Sybil**:

Each example MUST include:
- Input fixture file in `docs/features/{feature-name}/fixtures/input.txt`
- Expected output file in `docs/features/{feature-name}/fixtures/expected-output.txt`
- Sybil verification comments: `<!-- verify-file: output.txt expected: expected-output.txt -->`
- Both CLI and Python examples that produce identical output
- Working directory context: examples run in `docs/features/{feature-name}/fixtures/`
- File references use simple filenames like `input.txt`, not `{feature-name}/input.txt`

**Process for Each Feature**:
1. Find existing tests for the feature in `tests/`
2. Read design docs explaining the feature
3. Create feature directory: `docs/features/{feature-name}/`
4. Create markdown file: `docs/features/{feature-name}/{feature-name}.md`
5. Create fixture directory: `docs/features/{feature-name}/fixtures/`
6. Create minimal input fixture that demonstrates the feature
7. Run `uniqseq` command to generate expected output (from fixtures directory)
8. Verify output is correct and demonstrates the feature clearly
9. Write documentation following the style template above
10. Use simple filenames in code examples: `input.txt`, not `{feature-name}/input.txt`
11. Ensure both CLI and Python examples produce identical output
12. Add Sybil verification comments to both examples: `<!-- verify-file: output.txt expected: expected-output.txt -->`
13. Update `mkdocs.yml` navigation: `- Feature Name: features/{feature-name}/{feature-name}.md`
14. Verify mkdocs builds and Sybil tests pass: `cd docs && python -m pytest features/{feature-name}/{feature-name}.md -v`
15. **Illustrate, don't just explain**: Show before/after, highlight changed lines, use visual diagrams

**Feature-to-Test Mapping** (find examples in these tests):

| Feature | Test Files | Design Docs |
|---------|-----------|-------------|
| Window Size | `test_deduplicator.py`, `test_oracle.py` | ALGORITHM_DESIGN.md §2 |
| History Limits | `test_positional_fifo.py`, `test_deduplicator.py` | ALGORITHM_DESIGN.md §2.1 |
| Skip Chars | `test_cli.py`, `test_deduplicator.py` | IMPLEMENTATION.md CLI section |
| Hash Transform | `test_cli.py` (transform tests) | DESIGN_RATIONALE.md |
| Pattern Filters | `test_cli.py` (track/bypass) | IMPLEMENTATION.md Pattern section |
| Delimiters | `test_cli.py` (delimiter tests) | IMPLEMENTATION.md |
| Library Mode | `test_library.py`, `test_cli_library.py` | IMPLEMENTATION.md §Pattern Libraries |
| Inverse Mode | `test_cli.py`, `test_deduplicator.py` | IMPLEMENTATION.md |
| Annotations | `test_deduplicator.py`, `test_cli.py` | ALGORITHM_DESIGN.md |
| Progress/Stats | `test_cli_stats.py` | IMPLEMENTATION.md §Unix Principles |

**Planned Documents**:

1. ✅ **Window Size** (`features/window-size/window-size.md`) - COMPLETED
   - Tests: `test_deduplicator.py::test_basic_deduplication`, `test_oracle.py`
   - Shows test retry output with 4-line error that repeats
   - Demonstrates behavior with window sizes 3, 5, and 10
   - Explains why window size 5 detects 4-line error (5-line windows including empty lines)
   - Improved diagram showing sliding window concept
   - Fixtures: `docs/features/window-size/fixtures/`
   - Structure follows multi-line-sequences.md pattern: feature directory with md file + fixtures subdirectory

2. ✅ **History Management** (`features/history/history.md`) - COMPLETED
   - Tests: `test_deduplicator.py::test_history_limit`, `test_deduplicator.py::test_unlimited_history`
   - Shows log entries where early error reappears after many intermediate entries
   - Demonstrates limited history (max-history=5) misses duplicate - history full, early entries evicted
   - Demonstrates unlimited history detects duplicate - all entries retained
   - **Code change**: Updated --max-history validation from min=100 to min=0
   - Fixtures: `docs/features/history/fixtures/`

3. **Ignoring Prefixes** (`features/skip-chars.md`)
   - Tests: `test_cli.py` skip_chars tests, `test_deduplicator.py`
   - Timestamp prefix handling
   - Character offset behavior

4. **Hash Transformations** (`features/hash-transform.md`)
   - Tests: `test_cli.py` hash_transform tests
   - Shell command piping behavior
   - Use cases and examples

5. **Pattern Filtering** (`features/pattern-filtering.md`)
   - Tests: `test_cli.py` track/bypass tests
   - Whitelist/blacklist behavior
   - Pattern precedence rules

6. **Custom Delimiters** (`features/delimiters.md`)
   - Tests: `test_cli.py` delimiter tests
   - Text vs binary mode
   - Escape sequences

7. **Library Mode** (`features/library-mode.md`)
   - Tests: `test_library.py`, `test_library_workflows.py`
   - File format and structure
   - Load/save workflows

8. **Inverse Mode** (`features/inverse-mode.md`)
   - Tests: `test_cli.py` inverse tests, `test_deduplicator.py`
   - Actual inverse behavior
   - Pattern analysis workflow

9. **Annotations** (`features/annotations.md`)
   - Tests: `test_deduplicator.py` annotation tests
   - Format strings and variables
   - Output examples

10. **Progress and Output** (`features/progress-output.md`)
    - Tests: `test_cli_stats.py`
    - Table vs JSON format
    - Progress indicator behavior

**Tasks**:
- [ ] Create `docs/features/window-size.md`
- [ ] Create `docs/features/history.md`
- [ ] Create `docs/features/skip-chars.md`
- [ ] Create `docs/features/hash-transform.md`
- [ ] Create `docs/features/pattern-filtering.md`
- [ ] Create `docs/features/delimiters.md`
- [ ] Create `docs/features/library-mode.md`
- [ ] Create `docs/features/inverse-mode.md`
- [ ] Create `docs/features/annotations.md`
- [ ] Create `docs/features/progress-output.md`
- [ ] Create fixture files for examples where needed
- [ ] Remove placeholder.md from features directory
- [ ] Update mkdocs.yml navigation with new feature pages

**Success Criteria**:
- Each major feature has clear, focused documentation
- Examples are executable and tested via Sybil (where practical)
- Features build on each other logically
- Documentation complements (doesn't duplicate) reference docs

### Phase 6: Realistic Scenario Examples
**Goal**: Create compelling real-world examples

**Tasks**:
- [ ] Generate realistic test fixtures (if not already done in Stage 4)
- [ ] Write `docs/use-cases/log-processing.md` with server log examples
- [ ] Write `docs/use-cases/terminal-sessions.md` with script output examples
- [ ] Write `docs/use-cases/advanced-scenarios.md` with complex patterns
- [ ] Add fixtures to `tests/fixtures/scenarios/`

**Success Criteria**: Examples demonstrate real-world value

### Phase 7: Guides and Polish
**Goal**: Complete documentation with guides

**Tasks**:
- [ ] Write `docs/guides/choosing-window-size.md`
- [ ] Write `docs/guides/performance.md`
- [ ] Write `docs/guides/common-patterns.md`
- [ ] Write `docs/guides/troubleshooting.md`
- [ ] Write `docs/about/contributing.md`
- [ ] Add search customization if needed
- [ ] Review all documentation for consistency
- [ ] Add navigation and cross-references

**Success Criteria**: Documentation feels complete and professional

### Phase 8: ReadTheDocs Deployment
**Goal**: Host documentation on ReadTheDocs with analytics

**Tasks**:
- [ ] Create ReadTheDocs account and link repository
- [ ] Create `.readthedocs.yml` configuration
- [ ] Configure build settings (Python version, dependencies)
- [ ] Test documentation builds on ReadTheDocs
- [ ] Enable analytics in ReadTheDocs dashboard
- [ ] Verify versioning works from git tags
- [ ] Add documentation badge to README.md

**Success Criteria**:
- Documentation builds automatically on commit
- Analytics tracking enabled
- Versions correspond to git tags

## Configuration Files

### mkdocs.yml
```yaml
site_name: uniqseq
site_url: https://uniqseq.readthedocs.io/
site_description: Deduplicate repeated sequences of lines in text streams
repo_url: https://github.com/JeffreyUrban/uniqseq
repo_name: JeffreyUrban/uniqseq

theme:
  name: material
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: Switch to dark mode
    - scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: Switch to light mode
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy

markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.superfences
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - admonition
  - pymdownx.details
  - attr_list
  - md_in_html
  - myst_parser  # Enable MyST Markdown

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            show_source: true
            show_root_heading: true

nav:
  - Home: index.md
  - Getting Started:
      - Installation: getting-started/installation.md
      - Quick Start: getting-started/quick-start.md
      - Basic Concepts: getting-started/basic-concepts.md
  - Examples:
      - Basic Deduplication: examples/basic-deduplication.md
      - Pattern Filtering: examples/pattern-filtering.md
      - Annotations: examples/annotations.md
      - Inverse Mode: examples/inverse-mode.md
      - Log Processing: examples/log-processing.md
      - Terminal Sessions: examples/terminal-sessions.md
      - Advanced Scenarios: examples/advanced-scenarios.md
  - Guides:
      - Choosing Window Size: guides/choosing-window-size.md
      - Performance: guides/performance.md
      - Common Patterns: guides/common-patterns.md
      - Troubleshooting: guides/troubleshooting.md
  - Reference:
      - CLI: reference/cli.md
      - Deduplicator: reference/deduplicator.md
      - Library Usage: reference/library.md
  - About:
      - Algorithm: about/algorithm.md
      - Design Decisions: about/design-decisions.md
      - Contributing: about/contributing.md
```

### .readthedocs.yml
```yaml
version: 2

build:
  os: ubuntu-22.04
  tools:
    python: "3.12"
  jobs:
    post_install:
      - pip install -e ".[docs]"

mkdocs:
  configuration: mkdocs.yml

python:
  install:
    - requirements: docs/requirements.txt
```

### docs/requirements.txt
```
mkdocs-material>=9.5.0
mkdocs-myst-parser>=1.0.0
mkdocstrings[python]>=0.25.0
```

### conftest.py (Sybil integration)
```python
from sybil import Sybil
from sybil.parsers.myst import PythonCodeBlockParser, SkipParser

pytest_collect_file = Sybil(
    parsers=[
        PythonCodeBlockParser(),
        SkipParser(),
    ],
    patterns=['*.md'],
    fixtures=['tmp_path'],
).pytest()
```

## Sybil Example Format

### Basic Example
````markdown
# Basic Deduplication

Remove duplicate sequences from a file:

```python
from uniqseq import Deduplicator

dedup = Deduplicator(window_size=3)
lines = ["A", "B", "C", "A", "B", "C", "D"]
result = list(dedup.process(lines))
assert result == ["A", "B", "C", "D"]
```
````

### CLI Example with CliRunner
````markdown
# Pattern Filtering

Track only error messages:

```python
from typer.testing import CliRunner
from uniqseq.cli import app
from pathlib import Path

runner = CliRunner()
with runner.isolated_filesystem():
    Path("input.txt").write_text("ERROR: A\nINFO: B\nERROR: A\n")
    result = runner.invoke(app, ["input.txt", "--track", "^ERROR"])
    assert result.exit_code == 0
    assert result.stdout.count("ERROR: A") == 1
```
````

## Success Criteria

### Phase 1-7 Completion
- [ ] All phases implemented
- [ ] Documentation builds without errors
- [ ] All Sybil tests pass in CI

### Content Quality
- [ ] Examples demonstrate all major features
- [ ] Examples are realistic and compelling
- [ ] API documentation is complete
- [ ] Guides cover common questions

### Technical Quality
- [ ] All code examples execute successfully
- [ ] Examples fail CI if they break
- [ ] Documentation renders correctly on ReadTheDocs
- [ ] Search works effectively

### Analytics Setup
- [ ] ReadTheDocs analytics enabled
- [ ] Can view page view statistics
- [ ] Can view search term analytics

### User Experience
- [ ] Navigation is intuitive
- [ ] Examples are easy to copy/paste
- [ ] Mobile-friendly rendering
- [ ] Fast search results

## Dependencies

### Python Packages (add to pyproject.toml)
```toml
[project.optional-dependencies]
docs = [
    "mkdocs-material>=9.5.0",
    "mkdocs-myst-parser>=1.0.0",
    "mkdocstrings[python]>=0.25.0",
    "sybil>=6.0.0",
]
```

### External Services
- ReadTheDocs account (free for open source)
- GitHub repository (already exists)

## Migration Path to Zensical

When Zensical becomes production-ready with MyST and ReadTheDocs support:

1. **Prerequisites to check**:
   - [ ] Zensical out of alpha (stable release)
   - [ ] MyST Markdown support added
   - [ ] ReadTheDocs officially supports Zensical
   - [ ] Sybil works with Zensical's MyST implementation

2. **Migration steps**:
   - [ ] Install Zensical
   - [ ] Test build: `zensical build` (reads mkdocs.yml natively)
   - [ ] Verify examples still work with Sybil
   - [ ] Update `.readthedocs.yml` to use Zensical
   - [ ] Test on ReadTheDocs staging
   - [ ] Deploy to production

3. **Benefits of waiting**:
   - Rust-based performance (multi-core builds)
   - Modern architecture
   - Active development by same team
   - New features as they're added

## Notes

### Why Not Zensical Now?
- **Alpha software**: Not production-ready (as of Jan 2025)
- **No MyST support**: Only Python Markdown (Sybil needs MyST)
- **No ReadTheDocs support**: Would need alternative hosting without analytics
- **Missing features**: Still working toward feature parity with MkDocs Material

### Why MkDocs Material Works
- **Production-ready**: Stable, well-documented
- **MyST support**: Via mkdocs-myst-parser plugin
- **ReadTheDocs**: Full support with analytics
- **Easy migration**: Same team built both tools, compatible config

### Key Decision Points
- **Now**: Get documentation and analytics working today
- **2026+**: Migrate when Zensical is production-ready
- **Low risk**: Easy migration path, maintained through 2026

## References

- [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)
- [MyST Markdown](https://mystmd.org/)
- [Sybil Documentation](https://sybil.readthedocs.io/)
- [ReadTheDocs Documentation](https://docs.readthedocs.io/)
- [mkdocstrings](https://mkdocstrings.github.io/)
- [Zensical](https://zensical.org/) (future migration target)
