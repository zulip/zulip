---
name: debug-node-coverage
description: "Debug node test coverage failures. Use when ./tools/test-js-with-node --coverage reports lines missing coverage."
---

# Debugging Node Test Coverage Failures

When `./tools/test-js-with-node --coverage` fails with lines missing
coverage, follow this process.

## Understanding the error

The error looks like:

```
ERROR: web/src/filter.ts no longer has complete node test coverage
  Lines missing coverage: 90, 225, 1780
```

This means the listed lines in the source file were never executed by
any test. Zulip enforces 100% line coverage for all files not listed
in `EXEMPT_FILES` in `tools/test-js-with-node`.

## Step 1: Read the uncovered lines

Read the source file at the reported line numbers. Classify each
uncovered line:

- **Testable code**: A branch or path that can be reached with the
  right test input. Fix by adding tests.
- **Defensive/unreachable assertion**: Code like `assert(false, ...)`
  that exists only as a safety net. These are automatically excluded
  by `COVERAGE_EXCLUDE_LINES` in `tools/test-js-with-node`.
- **Code that is unreachable or otherwise not worth testing**:
  Mark with `// istanbul ignore next` comments. Use sparingly.

## Step 2: Find the test file

Tests for `web/src/foo.ts` live in `web/tests/foo.test.cjs`. Read the
test file to understand existing patterns before adding new tests.

The common predicate test pattern:

```JavaScript
const predicate = get_predicate([["operator", operand]]);
assert.ok(predicate({...message that should match...}));
assert.ok(!predicate({...message that should not match...}));
```

## Step 3: Add tests for testable code

Add tests near related existing tests. Follow the existing style
exactly. Tests should exercise the behavior, not the implementation
detail — name and locate tests based on what they verify, not which
internal code path they hit.

## Step 4: Handle unreachable assertions

Use `// istanbul ignore next` where appropriate, being sure that
you think the codebase is better without test coverage for this case.

## Step 5: Verify

```bash
./tools/test-js-with-node --coverage
```

This runs all JS tests in serial mode with istanbul/nyc instrumentation
and checks that non-exempt files have 100% line coverage.

For faster iteration, you can run an individual test and analyze the
coverage output files to see whether it covered a target line.

## Key files

- `tools/test-js-with-node` — Test runner, coverage enforcement,
  `EXEMPT_FILES` list, `COVERAGE_EXCLUDE_LINES` patterns
- `tools/coveragerc` — Python equivalent (for reference on pattern
  style)
- `web/tests/*.test.cjs` — All JS test files
- `var/node-coverage/` — Generated coverage reports (HTML viewable
  at `http://zulipdev.com:9991/node-coverage/index.html`), but
  you can also access in var/node-coverage/.
