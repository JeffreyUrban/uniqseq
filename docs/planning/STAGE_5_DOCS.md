# Stage 5: Executable Documentation and Examples

**Status**: Planning
**Branch**: stage-5-executable-docs
**Started**: 2025-01-24

## Overview

Implement professional documentation with executable examples that are tested in CI, ensuring documentation stays accurate and up-to-date. Use ReadTheDocs for hosting with built-in analytics to track feature interest.

## Goals

1. **Executable Documentation**: Examples in docs are automatically tested via Sybil
2. **Professional Presentation**: Modern, searchable documentation on ReadTheDocs
3. **Analytics**: Track which features get attention to inform development priorities
4. **Single Source of Truth**: Code examples serve as both docs and integration tests

## Technology Stack

### Documentation Framework
- **MkDocs Material**: Modern, responsive documentation theme
  - Production-ready today
  - Maintained through 2026
  - Easy migration path to Zensical when it matures
- **MyST Markdown**: Extended Markdown with semantic markup
  - Enables rich documentation features
  - Required for Sybil's advanced parsers
- **mkdocs-material plugin**: For MyST support in MkDocs

### Executable Examples
- **Sybil**: Tests code examples embedded in documentation
  - MyST parsers for Python code blocks
  - Integrates with pytest
  - Validates examples during CI
- **Typer CliRunner**: For CLI examples in docs
  - Same tool used in unit tests
  - Ensures CLI examples are accurate

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

### Phase 1: Setup and Configuration
**Goal**: Get MkDocs Material + MyST working with basic structure

**Tasks**:
- [ ] Install dependencies: `mkdocs-material`, `mkdocs-myst-parser`, `sybil`
- [ ] Create `mkdocs.yml` configuration
- [ ] Set up basic documentation structure (empty files)
- [ ] Configure MyST Markdown support
- [ ] Test local preview: `mkdocs serve`

**Dependencies**: `mkdocs-material`, `mkdocs-myst-parser`

### Phase 2: Core Documentation Content
**Goal**: Create non-executable documentation content

**Tasks**:
- [ ] Write `docs/index.md` (landing page)
- [ ] Write `docs/getting-started/installation.md`
- [ ] Write `docs/getting-started/quick-start.md`
- [ ] Write `docs/getting-started/basic-concepts.md`
- [ ] Write `docs/about/algorithm.md` (adapt from design docs)
- [ ] Write `docs/about/design-decisions.md` (adapt from DESIGN_RATIONALE.md)

**Success Criteria**: Documentation builds and renders correctly locally

### Phase 3: Executable Examples with Sybil
**Goal**: Create tested examples in documentation

**Tasks**:
- [ ] Set up Sybil pytest integration
- [ ] Configure Sybil with MyST parsers
- [ ] Write `docs/examples/basic-deduplication.md` with executable examples
- [ ] Write `docs/examples/pattern-filtering.md` with CLI examples
- [ ] Write `docs/examples/annotations.md` with format examples
- [ ] Write `docs/examples/inverse-mode.md`
- [ ] Add Sybil tests to pytest configuration
- [ ] Verify examples run in CI

**Success Criteria**:
- All examples execute successfully via pytest
- Examples cover major features
- CI fails if examples break

### Phase 4: API Documentation
**Goal**: Auto-generate API docs from code

**Tasks**:
- [ ] Install `mkdocstrings` with Python handler
- [ ] Configure mkdocstrings in `mkdocs.yml`
- [ ] Create `docs/reference/cli.md` (document CLI module)
- [ ] Create `docs/reference/deduplicator.md` (document Deduplicator class)
- [ ] Create `docs/reference/library.md` (usage as library)
- [ ] Ensure docstrings are complete and accurate

**Dependencies**: `mkdocstrings[python]`

### Phase 5: Realistic Scenario Examples
**Goal**: Create compelling real-world examples

**Tasks**:
- [ ] Generate realistic test fixtures (if not already done in Stage 4)
- [ ] Write `docs/examples/log-processing.md` with server log examples
- [ ] Write `docs/examples/terminal-sessions.md` with script output examples
- [ ] Write `docs/examples/advanced-scenarios.md` with complex patterns
- [ ] Add fixtures to `tests/fixtures/scenarios/`

**Success Criteria**: Examples demonstrate real-world value

### Phase 6: ReadTheDocs Deployment
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
