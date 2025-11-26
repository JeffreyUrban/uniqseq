# Developer Documentation

This directory contains technical documentation for uniqseq developers and contributors.

## Documentation Structure

### Design Documentation (`design/`)

Technical architecture and design decisions:

- **[IMPLEMENTATION.md](design/IMPLEMENTATION.md)** - Current implementation overview
  - Core algorithm architecture
  - Data structures and processing phases
  - Pattern libraries and filtering
  - Key implementation details

- **[ALGORITHM_DESIGN.md](design/ALGORITHM_DESIGN.md)** - Detailed algorithm design
  - Position-based duplicate detection
  - Multi-phase processing pipeline
  - Memory management and data structures
  - Performance characteristics

- **[DESIGN_RATIONALE.md](design/DESIGN_RATIONALE.md)** - Design decisions and trade-offs
  - Why certain approaches were chosen
  - Alternatives considered
  - Trade-offs and constraints
  - Feature scope decisions

### Testing Documentation (`testing/`)

Test strategy and coverage:

- **[TESTING_STRATEGY.md](testing/TESTING_STRATEGY.md)** - Test organization and approach
  - Test categories and structure
  - Unit, integration, and oracle testing
  - Testing best practices
  - CI/CD integration

- **[TEST_COVERAGE.md](testing/TEST_COVERAGE.md)** - Test coverage tracking
  - Coverage targets and status
  - Test scenarios for each feature
  - Gap analysis and priorities
  - Historical testing milestones

- **[ORACLE_TESTING.md](testing/ORACLE_TESTING.md)** - Oracle-based testing
  - Reference implementation testing
  - Correctness validation approach
  - Oracle compatibility guarantees

### User Documentation (`user/`)

Usage patterns and examples:

- **[EXAMPLES.md](user/EXAMPLES.md)** - Comprehensive usage examples
  - Common use cases
  - Composition patterns with Unix tools
  - Feature demonstrations
  - Best practices

### Planning Documentation (`planning/`)

Feature planning and future improvements:

- **[PLANNING.md](planning/PLANNING.md)** - Feature roadmap
  - Completed features (reference)
  - Future enhancement ideas
  - Design philosophy
  - Feature evaluation criteria

### Deployment Documentation (`deployment/`)

Distribution and release processes:

- **[DEPLOYMENT.md](deployment/DEPLOYMENT.md)** - Distribution strategy
  - PyPI package setup
  - Homebrew formula
  - Release process
  - Version management

## Quick Links

### For New Contributors

1. Start with [IMPLEMENTATION.md](design/IMPLEMENTATION.md) - understand the architecture
2. Read [ALGORITHM_DESIGN.md](design/ALGORITHM_DESIGN.md) - understand the core algorithm
3. Review [TESTING_STRATEGY.md](testing/TESTING_STRATEGY.md) - understand testing approach
4. Check [EXAMPLES.md](user/EXAMPLES.md) - see usage patterns

### For Feature Development

1. Review [DESIGN_RATIONALE.md](design/DESIGN_RATIONALE.md) - understand design philosophy
2. Check [PLANNING.md](planning/PLANNING.md) - evaluate against criteria
3. Update [TEST_COVERAGE.md](testing/TEST_COVERAGE.md) - document test plan
4. Update [IMPLEMENTATION.md](design/IMPLEMENTATION.md) - document changes

### For Release Management

1. Review [DEPLOYMENT.md](deployment/DEPLOYMENT.md) - understand release process
2. Update version and changelog
3. Run full test suite
4. Follow PyPI release workflow

## Documentation Standards

**Permanent Documentation** (design/, testing/, user/):
- Describes current reality, not plans or history
- Updated as features are implemented
- Technical and precise
- Includes code references where relevant

**Planning Documentation** (planning/, deployment/):
- Future-focused, not binding commitments
- Helps evaluate new feature requests
- Provides context for decisions
- May reference completed work for context

**All Documentation**:
- Written in Markdown
- Links to related docs
- Code examples tested where possible
- Updated alongside code changes

## Related Documentation

- **[README.md](../README.md)** - User-facing project overview
- **[CLAUDE.md](../CLAUDE.md)** - AI assistant guidance
- **[docs/](../docs/)** - User-facing documentation (Read the Docs)
