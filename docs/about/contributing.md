# Contributing to uniqseq

Thank you for your interest in contributing to uniqseq! This guide will help you get started.

## Ways to Contribute

### 1. Report Issues

Found a bug or have a feature request?

**Before creating an issue**:
- Search existing issues to avoid duplicates
- Check if it's already fixed in the main branch
- Gather relevant information (see below)

**What to include**:
```markdown
**Description**: Brief description of the issue

**Command used**:
```bash
uniqseq --window-size 3 --skip-chars 20 input.log
```

**Sample input** (first 20 lines):
```
[paste sample here]
```

**Expected behavior**: What you expected to happen

**Actual behavior**: What actually happened

**Environment**:
- uniqseq version: `uniqseq --version`
- Python version: `python --version`
- OS: macOS/Linux/Windows
```

### 2. Improve Documentation

Documentation improvements are always welcome!

**Types of documentation contributions**:
- Fix typos or unclear explanations
- Add examples for common use cases
- Improve existing guides
- Add new use case examples
- Clarify error messages

**Where documentation lives**:
- `docs/` - User-facing documentation (MkDocs)
- `README.md` - Project overview
- Code docstrings - API documentation

**Testing documentation changes**:
```bash
# Install dependencies
pip install -e ".[docs]"

# Serve documentation locally
mkdocs serve

# View at http://127.0.0.1:8000
```

### 3. Submit Code Changes

#### Getting Started

**Fork and clone**:
```bash
# Fork on GitHub, then:
git clone https://github.com/YOUR_USERNAME/uniqseq.git
cd uniqseq
```

**Set up development environment**:
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

**Run tests**:
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_deduplicator.py

# Run with coverage
pytest --cov=src --cov-report=html
```

#### Code Standards

**Python code requirements**:

1. **Type hints** for all function signatures:
   ```python
   def process_line(self, line: str, output: TextIO) -> None:
       """Process a single line."""
       pass
   ```

2. **Docstrings** for public functions/classes:
   ```python
   def deduplicate(input_file: str, window_size: int) -> int:
       """
       Deduplicate a file with given window size.

       Args:
           input_file: Path to input file
           window_size: Minimum sequence length to detect

       Returns:
           Number of duplicate lines removed
       """
       pass
   ```

3. **Named constants** instead of magic numbers:
   ```python
   # Good
   DEFAULT_WINDOW_SIZE = 10
   window_size = DEFAULT_WINDOW_SIZE

   # Bad
   window_size = 10  # What does 10 mean?
   ```

4. **Code formatting**:
   ```bash
   # Format code (runs automatically via pre-commit)
   ruff format .

   # Check for issues
   ruff check .
   ```

5. **Type checking**:
   ```bash
   # Run type checker
   mypy src/
   ```

#### Testing Requirements

**All code changes must include tests.**

**Test categories**:
- **Unit tests**: Test individual functions/classes
- **Integration tests**: Test component interactions
- **Feature tests**: Test complete features with fixtures

**Writing tests**:
```python
import pytest
from uniqseq import UniqSeq

def test_basic_deduplication():
    """Test that repeated lines are deduplicated."""
    dedup = UniqSeq(window_size=1)

    # Test input
    lines = ["A", "B", "A", "C"]

    # Process and collect output
    output = []
    for line in lines:
        result = dedup.process_line(line)
        if result:
            output.append(result)

    # Verify
    assert output == ["A", "B", "C"]
```

**Running specific tests**:
```bash
# Run by name pattern
pytest -k "test_window_size"

# Run specific file
pytest tests/test_deduplicator.py

# Run with verbose output
pytest -v

# Run and stop at first failure
pytest -x
```

#### Submitting Pull Requests

**Before submitting**:

1. **Create a branch**:
   ```bash
   git checkout -b feature/my-improvement
   ```

2. **Make your changes**:
   - Write code
   - Add tests
   - Update documentation
   - Ensure all tests pass

3. **Commit your changes**:
   ```bash
   git add .
   git commit -m "Add feature: brief description"
   ```

   **Good commit messages**:
   - Start with verb (Add, Fix, Update, Remove)
   - Keep first line under 50 characters
   - Add detailed description if needed

   **Examples**:
   ```
   Add support for custom delimiters

   - Add --delimiter option to CLI
   - Support escape sequences (\n, \t, \0)
   - Add tests for delimiter handling
   - Update documentation with examples
   ```

4. **Push and create PR**:
   ```bash
   git push origin feature/my-improvement
   ```

   Then create a Pull Request on GitHub.

**PR description should include**:
- What problem does this solve?
- How does it solve it?
- Any breaking changes?
- Related issues (closes #123)

**PR checklist**:
- [ ] Tests added and passing
- [ ] Documentation updated
- [ ] Type hints added
- [ ] Docstrings added
- [ ] Pre-commit hooks pass
- [ ] No merge conflicts

## Development Workflow

### Project Structure

```
uniqseq/
├── src/uniqseq/          # Source code
│   ├── __init__.py
│   ├── cli.py            # CLI interface (Typer)
│   ├── deduplicator.py   # Core deduplication logic
│   ├── normalization.py  # Line normalization
│   └── ...
├── tests/                # Test files
│   ├── test_deduplicator.py
│   ├── test_cli.py
│   └── fixtures/         # Test data files
├── docs/                 # Documentation (MkDocs)
│   ├── guides/
│   ├── features/
│   └── use-cases/
├── pyproject.toml        # Project configuration
└── README.md
```

### Running Quality Checks

**Before committing** (automatic via pre-commit):
```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type check
mypy src/

# Run tests
pytest
```

**All checks together**:
```bash
# Run pre-commit on all files
pre-commit run --all-files
```

### Building Documentation

**Local preview**:
```bash
# Install docs dependencies
pip install -e ".[docs]"

# Serve documentation
mkdocs serve

# Open http://127.0.0.1:8000
```

**Build static site**:
```bash
mkdocs build
# Output in site/
```

### Debugging

**Enable debug logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Use pytest debugger**:
```bash
# Drop into debugger on failure
pytest --pdb

# Start debugger at specific test
pytest tests/test_file.py::test_function --pdb
```

**Profile performance**:
```bash
# Time a command
time uniqseq large-file.log > /dev/null

# Profile with cProfile
python -m cProfile -s cumulative -m uniqseq large-file.log
```

## Feature Development Guidelines

### Adding a New Feature

**Process**:

1. **Discuss first**: Open an issue to discuss the feature
2. **Design**: Write design doc if complex
3. **Implement**: Write code + tests
4. **Document**: Add to user documentation
5. **Submit**: Create PR

**Example: Adding a new CLI option**

1. **Add to CLI** (`src/uniqseq/cli.py`):
   ```python
   @app.command()
   def main(
       # ... existing options ...
       my_option: int = typer.Option(
           42,
           "--my-option",
           help="Description of what this does"
       ),
   ):
       # Implementation
   ```

2. **Add to core** (`src/uniqseq/deduplicator.py`):
   ```python
   def __init__(self, my_option: int = 42):
       self.my_option = my_option
   ```

3. **Add tests**:
   ```python
   def test_my_option():
       dedup = UniqSeq(my_option=50)
       # Test behavior
   ```

4. **Add documentation**:
   - Feature page in `docs/features/my-feature/`
   - Example in `docs/use-cases/`
   - Update `docs/reference/cli.md`

### Code Review Process

**What reviewers look for**:

- Does code work correctly?
- Are tests comprehensive?
- Is code readable and maintainable?
- Is documentation clear?
- Are edge cases handled?

**Responding to feedback**:
- Be open to suggestions
- Ask questions if unclear
- Make requested changes
- Push updates to same branch

## Common Development Tasks

### Adding a Test

```bash
# Create test file
touch tests/test_new_feature.py

# Write test
cat > tests/test_new_feature.py << 'EOF'
import pytest
from uniqseq import UniqSeq

def test_new_feature():
    """Test the new feature."""
    dedup = UniqSeq(new_option=True)
    # Test code
EOF

# Run the new test
pytest tests/test_new_feature.py -v
```

### Adding Documentation

```bash
# Create new doc page
mkdir -p docs/features/my-feature
touch docs/features/my-feature/my-feature.md

# Add to navigation (mkdocs.yml)
# Edit nav: section

# Preview
mkdocs serve
```

### Updating Dependencies

```bash
# Update specific package
pip install --upgrade package-name

# Update all dev dependencies
pip install --upgrade -e ".[dev]"

# Regenerate lockfile (if using)
pip freeze > requirements.txt
```

## Getting Help

### Resources

- **Documentation**: https://github.com/JeffreyUrban/uniqseq/docs
- **Issue Tracker**: https://github.com/JeffreyUrban/uniqseq/issues
- **Discussions**: https://github.com/JeffreyUrban/uniqseq/discussions

### Ask Questions

**Where to ask**:
- GitHub Discussions for general questions
- GitHub Issues for bugs/features
- PR comments for code-specific questions

**How to ask**:
- Be specific about what you're trying to do
- Include code snippets or examples
- Show what you've already tried

## Code of Conduct

**Be respectful and inclusive**:
- Welcome newcomers
- Be patient with questions
- Provide constructive feedback
- Focus on the code, not the person

**Unacceptable behavior**:
- Harassment or discrimination
- Trolling or insulting comments
- Publishing private information
- Other unprofessional conduct

## License

By contributing to uniqseq, you agree that your contributions will be licensed under the MIT License.

## Recognition

Contributors are recognized in:
- GitHub contributors page
- Release notes for significant contributions
- Documentation credits for major doc improvements

Thank you for contributing to uniqseq! 🎉
