# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working with this repository.

## Quick Links

- **[README.md](./README.md)** - High-level documentation

**Development Operations:**
→ **Reference [IMPLEMENTATION.md](./DEVELOPMENT.md)** for requirements and design documentation

- Don't duplicate requirements and design documentation in other docs

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

**Work Product Documentation:**

**@docs/IMPLEMENTATION.md** - Requirements and design documentation
- Pipeline architecture and data flow
- Component responsibilities and interfaces
- Design decisions and rationale
- Key algorithms and their requirements
- **UPDATE THIS** when requirements are clarified or design changes
- **REFERENCE THIS** before and during implementation

**Implementation Workflow:**

When implementing or fixing features:

1. For **requirements and design guidance**, read @docs/IMPLEMENTATION.md
2. **Ask for clarification** if requirements are unclear or incomplete
3. When design changes are agreed upon, **Update documentation** before implementation
4. **Implement** according to documented design
5. **Verify** implementation matches documentation

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
2. Reference @tests/TEST_COVERAGE.md to understand test coverage and ensure comprehensive testing
3. When tests fail, determine if the change is a fix (regenerate tests) or a regression (fix the code)

## Common Task Checklists

### Creating New Features

1. Check **docs/IMPLEMENTATION** for design alignment
2. **Write tests** (TDD or alongside implementation):
    - Create fixtures
    - Unit tests for pure functions
    - Mark with `@pytest.mark.unit`, `@pytest.mark.integration`, etc.
3. **Verify tests pass**: `pytest`
4. Update documentation if adding new patterns

**Testing is not optional** - All features require tests.

## Project Context for Claude Code

**Development Philosophy:**

- **Testing Required** - All code needs pytest tests

**Project-Specific Critical Rules:**

- **CRITICAL: Implement requirements correctly, don't document violations as limitations!**
  - When given a requirement (e.g., "keep the most recent value"), implement it correctly
  - Do NOT implement the opposite behavior and add a TODO noting it should be fixed later
  - If the requirement needs clarification or would require significant changes, ASK first

**Maintenance:**

- Upon confirming new code works correctly, remove outdated code and documentation
- Add and maintain test cases in @tests corresponding to issues found and fixes applied
