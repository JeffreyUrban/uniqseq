# Deployment and Distribution

**Status**: Planned
**Prerequisites**: Core features complete, documentation ready

This document outlines the deployment strategy for distributing uniqseq to users.

## Overview

uniqseq will be distributed through multiple channels to reach different user communities:

1. **PyPI** - Primary Python package distribution
2. **Homebrew** - macOS/Linux CLI tool distribution
3. **conda-forge** - Deferred - evaluate based on target audience

## PyPI Package

**Status**: Not yet published

### Package Configuration

Current `pyproject.toml` includes basic metadata. Additional fields needed for PyPI:

```toml
[project]
name = "uniqseq"
version = "0.1.0"  # Update based on actual release version
description = "Streaming multi-line sequence deduplicator"
readme = "README.md"
requires-python = ">=3.9"
license = {text = "MIT"}
authors = [
    {name = "Jeffrey Urban", email = "your.email@example.com"}  # Update with actual email
]
keywords = ["deduplication", "logs", "sequences", "streaming", "cli"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Intended Audience :: System Administrators",
    "License :: OSI Approved :: MIT License",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: System :: Logging",
    "Topic :: Text Processing :: Filters",
    "Topic :: Utilities",
]

[project.urls]
Homepage = "https://github.com/JeffreyUrban/uniqseq"
Documentation = "https://uniqseq.readthedocs.io"
Repository = "https://github.com/JeffreyUrban/uniqseq"
Issues = "https://github.com/JeffreyUrban/uniqseq/issues"
Changelog = "https://github.com/JeffreyUrban/uniqseq/blob/main/CHANGELOG.md"
```

### Release Process

**Modern Approach: Git Tags as Single Source of Truth**

This project uses **dynamic versioning** via `hatch-vcs`, where Git tags automatically determine the version number. No manual version updates needed!

**How it works**:
1. Git tag becomes the version (e.g., `v0.2.0` → version `0.2.0`)
2. Between tags, automatic `.dev` versions (e.g., `0.2.0.dev5+g1234567`)
3. Build process reads version from Git automatically
4. PyPI package gets correct version without manual edits

**Release Workflow**:

1. **Prepare Release**
   ```bash
   # Update CHANGELOG.md with release notes
   vim CHANGELOG.md

   # Commit changelog
   git add CHANGELOG.md
   git commit -m "docs: Prepare v0.2.0 release"
   git push
   ```

2. **Create GitHub Release** (Recommended: Use GitHub UI)
   - Go to: https://github.com/JeffreyUrban/uniqseq/releases/new
   - Tag: `v0.2.0` (create new tag)
   - Title: `v0.2.0`
   - Description: Copy from CHANGELOG.md
   - Click "Publish release"
   - GitHub Actions automatically triggers

3. **Alternative: Command Line**
   ```bash
   # Create and push tag
   git tag -a v0.2.0 -m "Release v0.2.0"
   git push origin v0.2.0

   # Manually create GitHub Release via gh CLI
   gh release create v0.2.0 --title "v0.2.0" --notes-file CHANGELOG.md
   ```

4. **Automated Steps** (via GitHub Actions)
   - Runs full test suite
   - Builds package with version from Git tag
   - Creates GitHub Release (if using tag push method)
   - Publishes to PyPI (when trusted publishing configured)

**First Release Checklist**:
- [ ] Verify all classifiers in `pyproject.toml` are accurate
- [ ] Update author email in `pyproject.toml`
- [ ] Complete CHANGELOG.md for v0.1.0
- [ ] Ensure all tests pass locally
- [ ] (Optional) Test with TestPyPI first
- [ ] Configure PyPI trusted publishing (for PyPI publication)
- [ ] Create GitHub Release v0.1.0
- [ ] Verify GitHub Actions workflow completes successfully
- [ ] (If PyPI) Verify package page renders correctly
- [ ] (If PyPI) Test installation: `pip install uniqseq`

### GitHub Actions Workflow

**Two-stage approach**: GitHub Release first, then PyPI

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  release:
    types: [published]

permissions:
  contents: read
  id-token: write  # Required for PyPI trusted publishing

jobs:
  build-and-publish:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Required for hatch-vcs to read Git history

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install build dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build hatch-vcs

      - name: Build package
        run: python -m build

      - name: Verify version matches tag
        run: |
          TAG_VERSION=${GITHUB_REF#refs/tags/v}
          PACKAGE_VERSION=$(python -c "import tomli; print(tomli.load(open('pyproject.toml', 'rb'))['project']['name'])")
          echo "Tag version: $TAG_VERSION"
          pip install dist/*.whl
          BUILT_VERSION=$(python -c "import uniqseq; print(uniqseq.__version__)")
          echo "Built version: $BUILT_VERSION"
          if [ "$TAG_VERSION" != "$BUILT_VERSION" ]; then
            echo "Version mismatch: tag=$TAG_VERSION, built=$BUILT_VERSION"
            exit 1
          fi

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        # Only publish to PyPI after trusted publishing is configured
        # Comment out this step initially, uncomment when ready
        # if: startsWith(github.ref, 'refs/tags/v')
```

**Why release-triggered instead of tag-triggered?**
- ✅ GitHub Release created manually/via UI first (with release notes)
- ✅ Allows review before PyPI publication
- ✅ Release notes visible before automation runs
- ✅ Can test the release without publishing to PyPI
- ✅ PyPI publication is the final step, not the first

### Trusted Publishing Setup

PyPI trusted publishing eliminates the need for API tokens:

1. Go to PyPI → Account → Publishing
2. Add new trusted publisher:
   - Owner: `JeffreyUrban`
   - Repository: `uniqseq`
   - Workflow: `release.yml`
   - Environment: (leave blank)

### Testing with TestPyPI

Before first production release:

```bash
# Build package
python -m build

# Upload to TestPyPI (manual, one-time test)
python -m twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ --no-deps uniqseq

# Verify
uniqseq --version
uniqseq --help
```

---

## Homebrew Package

**Status**: Deferred until after PyPI is established

### Formula Location

Create separate tap repository: `homebrew-uniqseq`

**Repository**: `https://github.com/JeffreyUrban/homebrew-uniqseq`

### Formula Template

File: `Formula/uniqseq.rb`

```ruby
class Uniqseq < Formula
  include Language::Python::Virtualenv

  desc "Streaming multi-line sequence deduplicator"
  homepage "https://github.com/JeffreyUrban/uniqseq"
  url "https://files.pythonhosted.org/packages/.../uniqseq-0.1.0.tar.gz"
  sha256 "..."  # SHA256 hash of the PyPI tarball
  license "MIT"

  depends_on "python@3.11"

  # List all Python dependencies
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
    # Basic smoke test
    output = shell_output("#{bin}/uniqseq --version")
    assert_match "uniqseq version", output

    # Functional test
    (testpath/"test.txt").write("line1\nline2\nline3\nline1\nline2\nline3\n")
    output = shell_output("#{bin}/uniqseq --window-size 3 --quiet #{testpath}/test.txt")
    assert_equal "line1\nline2\nline3\n", output
  end
end
```

### Installation

Users will install via:

```bash
brew tap JeffreyUrban/uniqseq
brew install uniqseq
```

### Update Process

After each PyPI release:

1. Update formula with new version and SHA256
2. Test locally: `brew install --build-from-source ./Formula/uniqseq.rb`
3. Commit and push formula update
4. Users update: `brew upgrade uniqseq`

### Homebrew Core Submission

**Timing**: After tool has matured (6+ months, stable API)

**Requirements** for homebrew-core:
- Established user base
- Stable version (1.0+)
- Active maintenance
- Good documentation
- No dependencies on proprietary services

**Process**:
1. Submit PR to `homebrew/homebrew-core`
2. Address reviewer feedback
3. Maintain formula in homebrew-core (or delegate to Homebrew team)

---

## Release Versioning

### Semantic Versioning

Follow [SemVer 2.0](https://semver.org/):

- **MAJOR**: Incompatible API changes
- **MINOR**: New functionality (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Pre-1.0 Releases

- **0.1.x**: Initial releases, API may change
- **0.2.x**: Stable core features
- **0.3.x**: Advanced features (libraries, filtering)
- **1.0.0**: Stable API, production ready

### Version Bumping

Update version in:
- `pyproject.toml` - `[project] version = "x.y.z"`
- Create git tag: `vx.y.z`
- Update `CHANGELOG.md`

---

## Distribution Channels Summary

| Channel | Status | Priority | Target Audience |
|---------|--------|----------|----------------|
| **PyPI** | Planned | High | Python developers, general users |
| **Homebrew tap** | Planned | Medium | macOS/Linux CLI users |
| **Homebrew core** | Future | Low | Broader macOS/Linux adoption |
| **conda-forge** | Deferred | Low | Data science community |
| **GitHub Releases** | Planned | High | All users (download artifacts) |

---

## Maintenance Plan

### Release Cadence

- **Security patches**: Immediate (as needed)
- **Bug fixes**: As needed (patch releases)
- **Features**: Quarterly (minor releases)
- **Major versions**: Annually (or when breaking changes needed)

### Automation

- **PyPI publishing**: Fully automated via GitHub Actions on tag push
- **Homebrew updates**: Manual (update formula after PyPI release)
- **GitHub Releases**: Semi-automated (create release manually, upload artifacts automatically)

### Quality Gates

Before any release:
- ✅ All tests passing (100% pass rate)
- ✅ Code coverage ≥ 95%
- ✅ No known security vulnerabilities
- ✅ Documentation updated
- ✅ CHANGELOG.md updated
- ✅ Version number incremented correctly

---

## Next Steps

1. **PyPI Setup** (First Priority)
   - [ ] Update `pyproject.toml` metadata
   - [ ] Create `CHANGELOG.md`
   - [ ] Configure PyPI trusted publishing
   - [ ] Create release workflow (`.github/workflows/release.yml`)
   - [ ] Test with TestPyPI
   - [ ] First production release to PyPI

2. **Homebrew Tap** (After PyPI)
   - [ ] Create `homebrew-uniqseq` repository
   - [ ] Generate formula with accurate dependencies
   - [ ] Test formula locally
   - [ ] Document installation in README

3. **Long-term**
   - [ ] Consider homebrew-core submission (after 1.0)
   - [ ] Evaluate conda-forge based on user demand
   - [ ] Set up automated release notes generation
