# Testing Strategy

## Test Coverage

** Status**: 462 tests passing, 94.55% code coverage

Test categories:
- **Unit tests**: Core algorithm components, CLI edge cases, validation
- **Integration tests**: End-to-end workflows, file processing
- **Comprehensive tests**: Oracle-compatible fixtures with invariant checking
- **Property tests**: Randomized inputs with statistical validation
- **Coverage gap tests**: LRU eviction, exception handling paths

**Coverage breakdown**:
- `__init__.py`: 100% (3/3 statements)
- `deduplicator.py`: 99% (254/256 statements) - 2 uncovered LRU edge cases
- `cli.py`: 79% (55/70 statements) - progress bar TTY simulation challenging
- `__main__.py`: 0% (1/1 statement) - entry point tested via subprocess

**Overall**: 94.55% coverage (312/330 statements), exceeds 90% requirement

## Test Data Philosophy

**All tests use synthetic data** - no real session logs in test fixtures

**Rationale**:
- **Reproducibility**: Synthetic patterns are deterministic
- **Clarity**: Test intent is obvious from data generation
- **Compactness**: Minimal test data for specific scenarios
- **Privacy**: No risk of exposing sensitive terminal content

**Example pattern** (from `test_interleaved_patterns`):
```python
pattern_a = [f"A-{i}" for i in range(10)]
pattern_b = [f"B-{i}" for i in range(10)]
lines = pattern_a + pattern_b + pattern_a + pattern_b
# Tests: A, B, A (dup), B (dup) � output = A, B
```

### tests/test_deduplicator.py

**Purpose**: Comprehensive test suite

**Test organization**:
- Basic functionality tests
- Edge case tests
- Configuration tests
- Advanced pattern tests
- Performance tests

**All tests use StringIO for output** - no file I/O in tests
