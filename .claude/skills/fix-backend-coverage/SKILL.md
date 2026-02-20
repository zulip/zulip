---
name: fix-backend-coverage
description: Fix backend test coverage gaps. Use when CI output or test-backend --coverage reports missing lines, like "ERROR: path/to/file.py no longer has complete backend test coverage".
argument-hint: "[test_module_or_file]"
---

# Fix Backend Coverage

Fix backend test coverage gaps for Zulip's enforced 100% coverage files.

Use this skill when:

- CI output contains "no longer has complete backend test coverage"
- You need to verify coverage after modifying code in an enforced file
- A file in `not_yet_fully_covered` has reached 100% and should be
  promoted to enforced, or coverage should be added to reach 100%

## Workflow

### 1. Run coverage on the specific test module

IMPORTANT: Never run the full test suite with `--coverage` — it takes
a very long time. Always target the specific test module that covers
the file with missing coverage.

```bash
./tools/test-backend --skip-provision-check --coverage --no-cov-cleanup \
    --no-html-report zerver.tests.test_specific_module
```

If invoked with an argument, use it: `$ARGUMENTS`

If the CI output names the source file but not the test module, use
`git grep` to find which test file imports or tests the relevant code.

### 2. Analyze missing lines

```bash
./.claude/skills/fix-backend-coverage/analyze-coverage <source_file_with_missing_coverage>
```

With no arguments, checks all enforced files for missing coverage
(useful after a targeted test run to see what's still missing).

The script loads `var/.coverage` and reports:

- Classification: ENFORCED (must be 100%) vs EXEMPT
- Statement/excluded/missing counts and coverage percentage
- Each missing line with 1 line of source context above and below

### 3. Fix each uncovered line using the right technique

Read the source at each missing line and classify it:

| Line type                           | Fix                                                         |
| ----------------------------------- | ----------------------------------------------------------- |
| Dead code (unreachable branch)      | Simplify/remove the dead branch                             |
| Error-only test path (assert, fail) | Add `# nocoverage` comment                                  |
| Missing test coverage               | Write a test that exercises the line                        |
| Newly 100% covered file             | Remove from `not_yet_fully_covered` in `tools/test-backend` |

`# nocoverage` should only be used for lines that execute only when a
test fails or for truly unreachable defensive code. Never use it to
skip writing tests for reachable production code.

### 4. Verify

Re-run coverage on the same targeted test module and re-analyze:

```bash
./tools/test-backend --skip-provision-check --coverage --no-cov-cleanup \
    --no-html-report zerver.tests.test_specific_module
./.claude/skills/fix-backend-coverage/analyze-coverage <source_file>
```

Confirm 0 missing lines, then lint:

```bash
./tools/lint --skip-provision-check --fix --only=ruff,ruff-format <changed_files>
```

## Coverage system reference

### Config

- Coverage config: `tools/coveragerc`
- Coverage data: `var/.coverage`
- Exclusion patterns in `coveragerc`: `# nocoverage`, `if False:`,
  `raise NotImplementedError`, `raise AssertionError`, `if TYPE_CHECKING:`,
  `@abstractmethod`, `@skip`, and `...` (ellipsis)

### Enforcement model

- `tools/test-backend` defines two lists:
  - `enforce_fully_covered`: all `.py` files matching `source_files` globs
    minus those in `not_yet_fully_covered`
  - `not_yet_fully_covered`: files exempt from the 100% requirement
- When a file in `not_yet_fully_covered` reaches 100%, it should be
  removed from the list to promote it to enforced status
- Enforcement only runs in CI with full suite + `--coverage`; locally
  you check with targeted runs + `analyze-coverage`
