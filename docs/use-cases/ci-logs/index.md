# Use Case: CI Build Logs

## Scenario

Your CI/CD pipeline generates verbose logs with repeated error messages during retries. You want to clean them up to focus on unique issues and understand what actually failed.

## Input Data

```
fixtures/
└── [ci-build.log](../../examples/fixtures/ci-build.log)
```

??? note "View file contents"
    ```text title="examples/fixtures/ci-build.log"
    --8<-- "examples/fixtures/ci-build.log"
    ```

This log shows a typical CI build where:
- A test fails with a 3-line stack trace
- The test is retried (same error appears again)
- Different timestamps for each occurrence

## Exercise

**[Remove Multi-Line Error Sequences](multi-line-sequences.md)** - Clean up repeated 3-line error traces in CI logs

## Key Concepts

This use case demonstrates:
- Using `--window-size` to detect multi-line patterns
- Using `--skip-chars` to ignore timestamp prefixes
- Combining features to solve real-world problems
