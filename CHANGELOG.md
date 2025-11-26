# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Dynamic versioning using Git tags via hatch-vcs
- Comprehensive deployment documentation

### Changed
- Version is now automatically derived from Git tags
- No manual version updates needed

## [0.1.0] - TBD

Initial release with full feature set.

### Added
- **Core Functionality**
  - Streaming multi-line sequence deduplication
  - Configurable window size and history limits
  - Unlimited history and sequence tracking modes
  - Auto-detection of streaming vs file input

- **Input/Output Flexibility**
  - Binary mode (`--byte-mode`)
  - Custom delimiters (text with `--delimiter`, hex with `--delimiter-hex`)
  - Skip characters (`--skip-chars`)
  - Hash transform (`--hash-transform`)
  - JSON statistics (`--stats-format json`)
  - Progress indicator (`--progress`)

- **Pattern Libraries**
  - Pre-load sequences (`--read-sequences`)
  - Library mode (`--library-dir`)
  - Native format storage with hash-based filenames
  - Metadata tracking for audit trails

- **Filtering and Inspection**
  - Track patterns (`--track`, `--track-file`)
  - Bypass patterns (`--bypass`, `--bypass-file`)
  - Inverse mode (`--inverse`)
  - Annotations (`--annotate`, `--annotation-format`)
  - Explain mode (`--explain`)

- **Quality and Testing**
  - Comprehensive test suite (868 tests)
  - High code coverage (>85%)
  - Oracle compatibility testing
  - CI/CD pipeline with Python 3.9-3.13 support
  - Quality tooling (ruff, mypy, pre-commit)

### Documentation
- Complete CLI reference in Read the Docs
- Algorithm documentation
- Design rationale
- Testing strategy
- Usage examples and patterns

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
