# Testing Strategy

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

### tests/test_uniqseq.py

**Purpose**: Comprehensive test suite

**Test organization**:
- Basic functionality tests
- Edge case tests
- Configuration tests
- Advanced pattern tests
- Performance tests

**All tests use StringIO for output** - no file I/O in tests
