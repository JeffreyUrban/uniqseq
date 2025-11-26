# Installation

`uniqseq` can be installed via Homebrew, pipx, pip, or from source.

## Requirements

- **Python 3.9 or higher** (for pip/pipx installations)
- **Homebrew** (for macOS/Linux Homebrew installation)

`uniqseq` works on Linux, macOS, and Windows.

## Via Homebrew (macOS/Linux)

```bash
brew tap jeffreyurban/uniqseq
brew install uniqseq
```

Homebrew manages the Python dependency and provides easy updates via `brew upgrade`.

## Via pipx (Cross-platform)

```bash
pipx install uniqseq
```

[pipx](https://pipx.pypa.io/) installs in an isolated environment with global CLI access. Works on macOS, Linux, and Windows. Update with `pipx upgrade uniqseq`.

## Via pip

```bash
pip install uniqseq
```

Use `pip` if you want to use uniqseq as a library in your Python projects.

## Via Source

For development or the latest unreleased features:

```bash
git clone https://github.com/JeffreyUrban/uniqseq.git
cd uniqseq
pip install .
```

This installs `uniqseq` and its dependencies:

- **typer** - CLI framework
- **rich** - Terminal formatting and progress display

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

Recommended installation methods:

- **Homebrew**: `brew tap jeffreyurban/uniqseq && brew install uniqseq`
- **pipx**: `pipx install uniqseq`
- **pip**: `pip install uniqseq`

!!! tip "Virtual Environments"
    If using pip directly, consider using a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install uniqseq
    ```

### macOS

Recommended installation methods:

- **Homebrew**: `brew tap jeffreyurban/uniqseq && brew install uniqseq` (recommended)
- **pipx**: `pipx install uniqseq`
- **pip**: `pip install uniqseq`

### Windows

Recommended installation methods:

- **pipx**: `pipx install uniqseq` (recommended)
- **pip**: `pip install uniqseq`

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

### Homebrew

```bash
brew upgrade uniqseq
```

### pipx

```bash
pipx upgrade uniqseq
```

### pip

```bash
pip install --upgrade uniqseq
```

### Source Installation

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

### Homebrew

```bash
brew uninstall uniqseq
```

### pipx

```bash
pipx uninstall uniqseq
```

### pip

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
