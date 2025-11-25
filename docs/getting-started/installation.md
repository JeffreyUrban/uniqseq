# Installation

`uniqseq` is a Python package that can be installed from source. PyPI and Homebrew distributions are planned for future releases.

## Requirements

- **Python 3.9 or higher**
- **pip** (usually included with Python)
- **Git** (for source installation)

`uniqseq` works on Linux, macOS, and Windows.

## Install from Source

The recommended way to install `uniqseq` is from source:

```bash
git clone https://github.com/JeffreyUrban/uniqseq.git
cd uniqseq
pip install .
```

This installs `uniqseq` and its dependencies:

- **typer** - CLI framework
- **rich** - Terminal formatting and progress display

## Install from PyPI

!!! info "Coming Soon"
    PyPI distribution is planned for a future release. For now, install from source.

```bash
# Future: Will be available via PyPI
pip install uniqseq
```

## Development Installation

For contributing or modifying `uniqseq`, install in editable mode with development dependencies:

```bash
git clone https://github.com/JeffreyUrban/uniqseq.git
cd uniqseq
pip install -e ".[dev]"
```

Development dependencies include:

- **pytest** - Test framework
- **pytest-cov** - Code coverage
- **ruff** - Linting and formatting
- **mypy** - Type checking
- **pre-commit** - Git hooks for code quality

## Platform-Specific Notes

### Linux

Install from source using `pip`:

```bash
git clone https://github.com/JeffreyUrban/uniqseq.git
cd uniqseq
pip install .
```

!!! tip "Virtual Environments"
    Consider using a virtual environment to avoid conflicts:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install .
    ```

### macOS

Install from source using `pip`:

```bash
git clone https://github.com/JeffreyUrban/uniqseq.git
cd uniqseq
pip install .
```

!!! info "Homebrew Support (Coming Soon)"
    Homebrew formula is planned for a future release:
    ```bash
    # Future: Will be available via Homebrew
    brew install uniqseq
    ```

### Windows

Install from source using `pip`:

```bash
git clone https://github.com/JeffreyUrban/uniqseq.git
cd uniqseq
pip install .
```

The `uniqseq` command will be available in your terminal after installation.

## Verify Installation

After installation, verify `uniqseq` is working:

```bash
uniqseq --version
uniqseq --help
```

Try a quick test:

```bash
echo -e "A\nB\nC\nA\nB\nC\nD" | uniqseq --window-size 3
```

Expected output:
```
A
B
C
D
```

## Upgrading

To upgrade to the latest version from source:

```bash
cd uniqseq
git pull
pip install --upgrade .
```

For development installations:

```bash
cd uniqseq
git pull
pip install --upgrade -e ".[dev]"
```

## Uninstalling

Remove `uniqseq` using pip:

```bash
pip uninstall uniqseq
```

## Troubleshooting

### Command Not Found

If `uniqseq` command is not found after installation:

1. **Check pip installed in the right location:**
   ```bash
   pip show uniqseq
   ```

2. **Verify Python scripts directory is in PATH:**
   ```bash
   python -m site --user-base
   ```
   Add `<user-base>/bin` to your PATH if needed.

3. **Use Python module syntax:**
   ```bash
   python -m uniqseq --help
   ```

### Import Errors

If you see import errors, ensure dependencies are installed:

```bash
pip install typer rich
```

Or reinstall with dependencies:

```bash
pip install --force-reinstall .
```

### Permission Errors

If you encounter permission errors, install for your user only:

```bash
pip install --user .
```

Or use a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install .
```

## Next Steps

- [Quick Start Guide](quick-start.md) - Learn basic usage
- [Basic Concepts](basic-concepts.md) - Understand how `uniqseq` works
- [CLI Reference](../reference/cli.md) - Complete command-line options
