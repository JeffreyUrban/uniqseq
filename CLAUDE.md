# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working with this repository.

## Critical Rules

**NEVER mention version numbers** (v0.x, v1.x, etc.) unless they have been explicitly agreed upon and documented in planning. Use:
- **"Stage X"** for implementation phases (e.g., "Stage 3: Pattern Libraries")
- **"Current implementation"** for what exists now
- **"Planned features"** or **"Future features"** for what's coming
- **"Milestone"** for completed work

**DO NOT** add version numbers to:
- Documentation
- Code comments
- Commit messages
- Planning documents
- Unless the user has explicitly specified and approved a versioning scheme and specific versions

## Quick Links

**User Documentation:**
- **[README.md](./README.md)** - Project overview and installation
- **[dev-docs/user/EXAMPLES.md](./dev-docs/user/EXAMPLES.md)** - Usage examples and patterns

**Design Documentation:**
- **[dev-docs/design/IMPLEMENTATION.md](./dev-docs/design/IMPLEMENTATION.md)** - Implementation overview and design decisions
- **[dev-docs/design/ALGORITHM_DESIGN.md](./dev-docs/design/ALGORITHM_DESIGN.md)** - Detailed algorithm design
- **[dev-docs/design/DESIGN_RATIONALE.md](./dev-docs/design/DESIGN_RATIONALE.md)** - Design rationale and trade-offs

**Planning Documentation:**
- **[dev-docs/planning/PLANNING.md](./dev-docs/planning/PLANNING.md)** - Roadmap and feature planning

**Testing Documentation:**
- **[dev-docs/testing/TESTING_STRATEGY.md](./dev-docs/testing/TESTING_STRATEGY.md)** - Test strategy and organization
- **[dev-docs/testing/TEST_COVERAGE.md](./dev-docs/testing/TEST_COVERAGE.md)** - Test coverage plan
- **[dev-docs/testing/ORACLE_TESTING.md](./dev-docs/testing/ORACLE_TESTING.md)** - Oracle-based testing approach

**Code Quality:**

- **Type hints required** for function signatures
- **Docstrings required** for public functions/classes
- **Avoid magic numbers** - use named constants

## Modern Tools & Techniques Philosophy

**Approach:** Favor modern, mature tools over legacy approaches. Not bleeding edge, but proven improvements.

**When relevant, consider these modern alternatives:**

**Python libraries** (consider when use case arises):

- **CLI tools:** `typer` (type-based, modern) over `argparse`/`click` ✓ Project standard
- **Terminal output:** `rich` for beautiful CLI output, progress bars, tables

## Code Standards

**Python:**

- Type hints required for function signatures
- Docstrings for public functions/classes
- **Avoid magic numbers** - use named constants
    - Example: `MY_CONSTANT = 0.5` instead of hardcoded `0.5`

## Documentation Standards

**Three Types of Documentation:**

1. **Planning Documentation** (temporary) - Design explorations, implementation plans, "Next Steps", "TODO"
2. **Progress Documentation** (temporary) - "What We've Built", implementation status
3. **Work Product Documentation** (permanent) - Current implementation, usage, architecture decisions

**Key Principles:**

- Work is not complete until documentation is production-ready
- Planning/progress docs are valuable during development - archive after completion
- Work product docs describe current reality, not plans or history
- Put function details in docstrings, not external docs
- Reference code locations, don't duplicate values or implementation
- Preserve design rationales when converting planning → work product docs

**Before creating directory structures:** Discuss scope and organization with user

### Documentation-Driven Engineering

**CRITICAL: Before implementing, understand and document requirements first!**

This project follows a documentation-driven approach. When working on features or fixing issues:

1. **Clarify requirements** through discussion with the user
2. **Document the design** in the appropriate work product documentation
3. **Reference the documentation** during implementation
4. **Update documentation** as design evolves

**Documentation Organization:**

Documentation is organized by audience and purpose:

1. **User Documentation** (`dev-docs/user/`):
   - Usage guides, examples, and user-facing features
   - **Update when**: Adding features, changing CLI, updating examples
   - **Audience**: End users of uniqseq

2. **Design Documentation** (`dev-docs/design/`):
   - Technical architecture, algorithms, implementation details
   - **Update when**: Changing algorithms, adding design decisions, modifying architecture
   - **Audience**: Developers, contributors, technical reviewers

3. **Planning Documentation** (`dev-docs/planning/`):
   - Roadmaps, feature plans, implementation stages
   - **Update when**: Completing milestones, planning new stages, updating roadmap
   - **Audience**: Project maintainers, contributors

4. **Testing Documentation** (`dev-docs/testing/`):
   - Test strategy, coverage plans, testing approaches
   - **Update when**: Adding test categories, changing coverage targets, new testing approaches
   - **Audience**: Developers, QA, contributors

**Documentation Maintenance Rules:**

When working on different scopes of work, maintain corresponding documentation:

| Work Scope | Documentation to Update |
|------------|------------------------|
| **Adding/changing features** | `dev-docs/design/IMPLEMENTATION.md`, `dev-docs/user/EXAMPLES.md` |
| **Modifying algorithm** | `dev-docs/design/ALGORITHM_DESIGN.md`, `dev-docs/design/IMPLEMENTATION.md` |
| **Adding tests** | `dev-docs/testing/TESTING_STRATEGY.md` |
| **CLI changes** | `README.md`, `dev-docs/user/EXAMPLES.md` |
| **Completing milestones** | `dev-docs/planning/PLANNING.md` |
| **Design decisions** | `dev-docs/design/DESIGN_RATIONALE.md` |

**Implementation Workflow:**

When implementing or fixing features:

1. **Identify scope**: Determine which documentation category applies
2. **Read relevant docs**: Reference appropriate design/planning docs
3. **Ask for clarification** if requirements are unclear or incomplete
4. **Update documentation FIRST**: Document design changes before implementing
5. **Implement** according to documented design
6. **Update related docs**: Ensure all affected documentation is updated
7. **Verify** implementation matches documentation

**DO NOT:**
- Implement based on assumptions without documented requirements
- Add implementation details to @CLAUDE.md (they belong in @docs/IMPLEMENTATION.md)
- Skip documentation updates when design changes
- Document violations of requirements as "limitations" or "TODO" items
- **Make unsubstantiated causal claims** - only state what is observed, not assumed causes

**Example violations:**

*Requirement violation:*
```
Requirement: "Keep the most recent value"
Wrong: Implement to keep old value, add TODO to fix later
Right: Ask for clarification if unclear, implement correctly
```

*Unsubstantiated causal claim:*
```
Wrong: "Substring matching causes performance degradation"
  (we observed slow performance AND learned of a requirement - no causal link established)
Right: "Full-line matching required per user specification. Performance issue under investigation."
```

**Evidence-Based Documentation:**
- Distinguish between **observed facts** and **inferred causes**
- Use precise language: "observed", "measured", "specified by user" vs "causes", "due to", "because"
- When debugging, document what was tried and what was observed, not assumed root causes
- If stating a cause, cite the evidence or mark as hypothesis

**When Asked to Justify Decisions:**
- If the user asks why you made a decision or assumption, search documentation and code comments for supporting evidence
- Present the evidence with specific references (file paths and line numbers where applicable)
- If no supporting evidence is found, acknowledge the assumption and ask for clarification
- Example: "I assumed X based on the comment at normalization_engine.py:117 which states '...'"

## Testing

This project uses **pytest exclusively** (not unittest).

**Core Principles:**

1. **Use pytest markers** - `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`
2. Reference `dev-docs/testing/TESTING_STRATEGY.md` and `dev-docs/testing/TEST_COVERAGE.md` to understand test organization and coverage
3. When tests fail, determine if the change is a fix (regenerate tests) or a regression (fix the code)

## Common Task Checklists

### Creating New Features

1. Check `dev-docs/design/IMPLEMENTATION.md` for design alignment
2. **Write tests** (TDD or alongside implementation):
    - Create fixtures
    - Unit tests for pure functions
    - Mark with `@pytest.mark.unit`, `@pytest.mark.integration`, etc.
3. **Verify tests pass**: `pytest`
4. **Update documentation**:
    - `dev-docs/design/IMPLEMENTATION.md` - if changing architecture
    - `dev-docs/user/EXAMPLES.md` - if adding user-facing features
    - `dev-docs/testing/TESTING_STRATEGY.md` - if adding new test categories

**Testing is not optional** - All features require tests.

## Project Context for Claude Code

**Development Philosophy:**

- **Testing Required** - All code needs pytest tests

**Project-Specific Critical Rules:**

- **CRITICAL: Implement requirements correctly, don't document violations as limitations!**
  - When given a requirement (e.g., "keep the most recent value"), implement it correctly
  - Do NOT implement the opposite behavior and add a TODO noting it should be fixed later
  - If the requirement needs clarification or would require significant changes, ASK first

- **CRITICAL: Use proper solutions, not workarounds!**
  - When encountering issues (especially in CI/testing), investigate the root cause
  - Find the standard/best-practice solution for the problem
  - Examples of workarounds to AVOID:
    - Weakening test assertions to pass (e.g., changing "window-size" to "window")
    - Adding `# type: ignore` comments instead of fixing type issues
    - Disabling linters/checkers instead of fixing the underlying issue
  - Examples of proper solutions:
    - Setting environment variables for consistent behavior (e.g., `COLUMNS` for terminal width)
    - Using appropriate imports for Python version compatibility (e.g., `Optional` vs `|`)
    - Configuring tools correctly in config files
  - If unsure whether a solution is a workaround or proper fix, ASK the user

**Maintenance:**

- Upon confirming new code works correctly, remove outdated code and documentation
- Add and maintain test cases in @tests corresponding to issues found and fixes applied
