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
**Goal**: Create simple, focused examples demonstrating individual features

**Rationale**: While Phase 3 created the infrastructure and Phase 6 will show complex real-world scenarios, Phase 5 focuses on teaching individual features clearly with minimal examples.

**Content Strategy**:
- One feature per document
- Minimal, focused examples
- Clear before/after demonstrations
- Executable via Sybil (where practical)
- Build understanding incrementally

**Planned Documents**:

1. **Window Size** (`features/window-size.md`)
   - Show how window size affects what gets detected
   - Examples: 1-line (unique), 3-line, 10-line sequences
   - Visual demonstration of sliding window

2. **History Management** (`features/history.md`)
   - Max history vs unlimited history
   - Memory implications
   - When to use limited vs unlimited
   - Auto-detection for files vs streams

3. **Ignoring Prefixes** (`features/skip-chars.md`)
   - Common use case: timestamp prefixes
   - Before/after examples
   - When to use skip-chars vs hash-transform

4. **Hash Transformations** (`features/hash-transform.md`)
   - Pipe lines through shell commands
   - Extract specific fields for comparison
   - Advanced text manipulation
   - Difference from skip-chars

5. **Pattern Filtering** (`features/pattern-filtering.md`)
   - Track patterns (whitelist)
   - Bypass patterns (blacklist)
   - Combining patterns
   - Pattern file format (--track-file, --bypass-file)

6. **Custom Delimiters** (`features/delimiters.md`)
   - Text delimiters (null, tab, custom)
   - Binary mode and hex delimiters
   - When to use each mode

7. **Library Mode** (`features/library-mode.md`)
   - Loading known patterns (--read-sequences)
   - Saving discovered patterns (--library-dir)
   - Pattern reuse across runs
   - Library directory structure

8. **Inverse Mode** (`features/inverse-mode.md`)
   - Extract duplicates for analysis
   - Pattern discovery workflow
   - Analyzing repetitive content

9. **Annotations** (`features/annotations.md`)
   - Default annotation format
   - Custom annotation templates (--annotation-format)
   - Use cases for annotations

10. **Progress and Output** (`features/progress-output.md`)
    - Progress indicator (--progress)
    - Statistics formats (--stats-format: table vs json)
    - Quiet mode (--quiet)
    - Output control options

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
