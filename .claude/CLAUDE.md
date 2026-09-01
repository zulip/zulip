# CLAUDE.md - Guidelines for AI Contributions to Zulip

This file provides guidance to Claude (and other AI coding assistants) for
contributing to the Zulip codebase. These guidelines are designed to produce
contributions that meet the same high standards we expect from human
contributors.

## Philosophy

Zulip is a team chat application used by thousands of organizations,
built to last for many years. It is developed by a vibrant open-source
community, with maintainers who have consistently emphasized **high
standards for codebase readability, code review, commit discipline,
debuggability, automated testing, tooling, documentation, and all the
other subtle details that together determine whether software is easy
to understand, operate, and modify**.

Zulip's engineering strategy is to **"move quickly without breaking
things"**. This is possible because the project has invested years in
testing, tooling, code structure, documentation, and development
practices that catch bugs systematically rather than relying on
individual vigilance. Maintainers spend most of their review time on
product decisions and code structure/readability, not on chasing
correctness issues — because the process is designed to prevent them.

This means Zulip's coding philosophy is to **focus relentlessly on
making the codebase easy to understand and difficult to make dangerous
mistakes**. This applies equally to AI-generated contributions. Every
change should make the codebase more maintainable and easier to read.

### No detail is too small

Zulip holds itself to a high bar for polish because users depend on
this software daily, and because the project is built to last for
decades. There is no category of "minor issue" that is acceptable
to ship — if something is broken in any context where a user would
encounter it, it must be fixed before merging. The project's
extensive investment in testing, tooling, and review processes exists
precisely so that these issues get caught and fixed, not so that they
can be classified as low-priority and deferred.

This philosophy extends to every aspect of the product:

- **Visual precision matters.** Alignment, spacing, colors, and font
  sizes must be consistent with similar existing UI. When making CSS
  changes, you must demonstrate with pixel-precise before/after
  comparisons that there are no unintended side effects.
- **Every state matters.** UI must look correct in all its states:
  hover, active, disabled, focused, selected, empty, overflowing.
  Changes that could plausibly affect colors, contrast, or
  theme-dependent imagery must work in both light and dark themes;
  changes whose effect can't reasonably vary with theme (pure
  geometry/typography — `font-size`, `line-height`, `margin`,
  `padding`, `display`, `font-weight`, etc.) only need a single
  theme verified.
- **Every window size matters.** UI must look good from wide desktop
  (1920px) down to narrow phone screens (480px).
- **Every language matters.** Translated strings can be 1.5x longer
  than English or half as short. UI must handle both extremes without
  breaking layout. Think about right-to-left languages too.
- **Every interaction path matters.** Keyboard navigation, screen
  readers, permission levels, feature interactions (banners
  overlapping, resolved topics, muted messages), and edge cases in
  data (empty lists, very long names, single items vs. many) must all
  be considered.

The right attitude is: "What could go wrong, and how do I verify that
it doesn't?" not "It looks fine to me." **What isn't tested probably
doesn't work** — this applies to visual changes just as much as to
backend logic.

### Understand before coding

Before writing any code, you must understand:

1. What the existing code does and why, including the relevant help center or
   developer-facing documentation.
2. What problem you're solving, in its full scope.
3. Why your approach is the right solution, and available alternatives.
4. How you will verify that your work is correct, and avoid regressions
   that are plausible for the type of work you're doing.

The answer to "Why is X an improvement?" should never be "I'm not sure."

## Workflow

Follow this workflow for every task: **understand → propose → implement → verify**.

### 1. Understand Before Coding

Before making any changes:

```bash
# Read relevant documentation
cat docs/*/<relevant-area>.md
cat starlight_help/src/content/docs/<topic>.md
cat api_docs/<topic>.md and read the relevant part of zerver/openapi/zulip.yaml

# Look at existing code patterns
git grep "similar_function_name"
git log --oneline -20 -- path/to/file.py

# Check for related issues on GitHub
```

Always show existing similar code and explain how it works before proposing
changes.

### 2. Propose an Approach

Before writing code, explain the plan:

- Explain your understanding of the problem and all relevant design decisions
- What changes are needed and why
- How the changes fit with existing patterns
- What could break and how to prevent regressions

### 3. Implement in Minimal, Coherent Commits

Structure changes as clean commits:

- Backend and API changes, with tests and API doc changes documented
  fully using our double-entry changelog system. Instructions for
  documentation can be found in `.claude/rules/api-changelog.md`
  (loaded automatically when you edit `zerver/openapi/zulip.yaml`).
- Frontend UI changes (with tests and user-facing documentation
  updates). Remember to plan to use your visual test skill to check
  your work whenever you change web app code (HTML, CSS, JS).

Each commit should be self-contained, highly readable and reviewable
using `git show --color-moved`, and pass lint/tests independently. If
extracting new files or moving code, always do that in a separate
commit from other changes.

### 4. Verify Before Finalizing

Run tests before making a commit. Always manage your time by running
specific test collections, not the entire test suite:

```bash
# Includes mypy and typescript checkers
./tools/lint path/to/changed/files.py
./tools/test-backend zerver.tests.test_relevant_module
```

Run through the `/self-review` skill's checklist before suggesting opening
a PR (`.claude/skills/self-review/SKILL.md`).

## Before You Start

### Read the Relevant Documentation

Zulip has over 185,000 words of developer documentation. Before working on any area:

- Read documentation from docs/, starlight_help/src/content/docs/, and api_docs/.
- Read existing code in the area you're modifying.
- Use `git grep` to find similar patterns in the codebase and read those.

### Understand the Code Style

- **Be consistent with existing code.** Look at surrounding code and follow
  the same patterns, as this is a thoughtfully crafted codebase.
- **Use clear, greppable names** for functions, arguments, variables, and
  tests. Future developers will `git grep` for relevant terms when
  researching a problem, so names should communicate purpose clearly.
- Keep everything well factored for maintainability. Avoid duplicating
  code, especially where access control or subtle correctness is involved.
- Run `./tools/lint` to catch style issues before committing, including mypy issues.
- Prefer writing code that is readable without explanation over heavily
  commented code using clever tricks. Comments should explain "why" when
  the reason isn't obvious, not narrate "what" the code does.
- Comments should have a line to themself except for CSS px math.

Frontend rules can be found in `.claude/rules/frontend.md` (loaded
automatically when you work on frontend JS/TS and template files).

CSS rules can be found in `.claude/rules/css.md` (loaded
automatically when you work on CSS files).

Python rules can be found in `.claude/rules/python.md` (loaded
automatically when you work on .py files).

See: `docs/contributing/code-style.md`

## Commit Discipline

Zulip follows the Git project's practice of **"Each commit is a minimal
coherent idea."** This is non-negotiable.

### Each Commit Must:

1. **Be coherent**: Implement one logical change completely and atomically.
2. **Pass tests**: Include test updates in the same commit as code changes.
3. **Not make Zulip worse**: Work is ordered so no commit has regressions.
4. **Be safe to deploy individually**: Or explain in detail why not.
5. **Be minimal** and **reviewable**: Don't combine moving code with changing
   it in the same commit; make liberal use of small prep commits for
   no-op refactoring that are easy to verify.

### Never:

- Mix multiple separable changes in a single commit.
- Create a commit that "fixes" a mistake from an earlier commit in the same PR;
  always edit Git to fix the original commit.
- Add content in one commit only to remove or move it in the next;
  plan upfront what belongs where and do it right the first time.
- Include debugging code, commented-out code, or temporary TODOs.
- Leave commits that break if a later commit in the PR is dropped.
  When a commit is flagged as potentially droppable, verify all
  earlier commits work correctly without it.

### Commit Message Format

Use the `/commit-message` skill whenever you write or reword a
commit message (`.claude/skills/commit-message/SKILL.md`).

## Testing Requirements

Zulip server takes pride in its ~98% test coverage. All server changes
must include nice tests that follow our testing philosophy.

When writing tests, follow our testing philosophy in
`.claude/rules/testing.md` (loaded automatically when you work on
test files).

### Before Submitting:

```bash
./tools/test-js-with-node       # JavaScript tests; full suite fast enough
./tools/lint                    # Run all linters
./tools/test-backend            # Python tests
```

### Manual Testing for UI Changes

If a PR makes frontend changes, manually verify the affected UI
using the checklist in `.claude/rules/ui-testing.md` (loaded
automatically when you work on frontend files).

## Common Pitfalls

### Treating Known Issues as Acceptable

A common failure mode is discovering a problem during verification
and then noting it as a known limitation rather than fixing it. At
Zulip, there is no category of "known minor issue" that is acceptable
to ship. If it's broken in any state, size, theme, or language, it
needs to be fixed.

**Mitigation:** When you find any issue during verification, fix it
before presenting the work. If a fix would require a design decision,
raise it as a question rather than shipping the broken state.

### Overconfident Code Generation

You may generate code that looks correct but doesn't match Zulip patterns.

**Mitigation:** Always show existing similar code first before implementing.

### Incomplete Type Annotations

Python code must be fully typed for mypy.

**Mitigation:** Ensure all functions have complete type annotations. Run mypy
(perhaps via the linter) to verify.

### Missing Test Updates

Tests must be in the same commit as the code they test.

**Mitigation:** Include test updates in each commit. Show what tests need to
change.

### Verbose Commit Messages

Zulip commits are concise -- say everything that's important for a
reviewer to understand about the motivation for the work and changes,
and nothing more. Avoid wordiness and details obvious to someone who
is looking at the commit and its metadata (lists of filenames, etc).

**Mitigation:** Keep summary under 72 characters. Body should explain why,
not what.

### Mixing Concerns

Multiple changes in one commit makes review difficult.

**Mitigation:** Each commit should do exactly one thing. Plan
necessary refactoring and preparatory commits in advance of functional
changes. You can split into good commits after the fact, but it's much
faster and easier to just plan and write them well the first time.

## What Not To Do

- Always check if you're working on top of the latest upstream/main, and
  fetch + rebase when starting a project so you're not using a stale branch.
  If you're continuing a project, start by rebasing, resolving merge
  conflicts carefully.
- Don't make design or UX decisions silently. When a technical
  constraint forces a tradeoff, present the constraint and options
  to the user rather than picking one. Never remove features, hide
  UI elements, or change interaction patterns without asking.
- Don't submit code you haven't tested
- Don't skip becoming familiar with the code you're modifying
- Don't make claims about code behavior without verification, and
  cite your sources.
- Don't generate PR descriptions that just describe what files changed
- Always do a pre-mortem: Think about how to avoid a bug recurring,
  how it might break something that already works, or imagine under
  what circumstances your changes might need to be reverted.

## Pull Request Guidelines

When opening a pull request, prefix the PR title with `[ai]` (e.g.,
`[ai] compose: Fix cursor position after emoji insertion.`). Use
`upstream/main` as the base branch. Use the `/pr-description` skill
to write the PR description
(`.claude/skills/pr-description/SKILL.md`).

## When to Pause and Discuss

Recommend pausing for discussion when:

- The approach involves security-sensitive code
- Database migrations are needed (See `docs/subsystems/schema-migrations.md`).
- The change affects many files (>10)
- Performance implications are unclear
- The feature design isn't fully specified
- The API or data model design isn't fully specified
- An API change may not be compatible (See `docs/processes/api-design.md`).
- Existing tests are failing for unclear reasons

## Task-Specific Approaches

### For Bug Fixes

1. Look at the relevant code and brainstorm theories for
   how the bug might be possible
2. Provide a clear explanation for the bug, and ideally
   provide steps for reproducing the bug on `main` in the
   dev environment. Verify the cause of the bug before
   suggesting a fix, unless a bug is very difficult to verify,
   in which case say so and explain a hypothesis instead.
3. Analyze and propose a fix with a clear explanation
4. Write tests that would have caught this bug if possible
5. Audit for whether the bug may exist elsewhere or might be
   re-introduced and propose appropriate changes to address if so.

### For New Features

1. Read the relevant documentation in docs/
2. Show similar existing features in the codebase
3. Propose an implementation approach before coding
4. Implement, following "Commit Discipline" above

### For Refactoring

1. Show the current implementation
2. Explain what makes it problematic
3. Propose the refactoring approach
4. Implement in commits that each leave the codebase working
5. No behavior changes unless explicitly discussed
6. Verify completeness: use `git grep` to find all occurrences and
   confirm nothing was missed

## Key Documentation Links

- Contributing guide: `docs/contributing/contributing.md`
- Code style: `docs/contributing/code-style.md`
- Commit discipline: `docs/contributing/commit-discipline.md`
- Testing overview: `docs/testing/testing.md`
- Backend tests: `docs/testing/testing-with-django.md`
- Code review: `docs/contributing/code-reviewing.md`
- mypy guide: `docs/testing/mypy.md`

## Repository Structure Quick Reference

```
zerver/           # Main Django app
  models/         # Database models
  views/          # API endpoints
  lib/            # Shared utilities
  tests/          # Backend tests
  webhooks/       # Integration webhooks
web/              # Frontend TypeScript/JavaScript
  src/            # Main frontend code
  styles/         # CSS
  templates/      # Frontend HTML
  tests/          # Frontend tests
templates/        # Jinja2/Handlebars templates
tools/            # Development and testing scripts
docs/             # ReadTheDocs documentation source
```

## Help Center Documentation

When making any user-facing change, **read
`docs/documentation/helpcenter.md`** in full and review the relevant
help center articles under `starlight_help/src/content/docs/` for any
updates that should be made. The writing guide there is the source
of truth for help center conventions, components, and structure.

## Zulip Chat Links

When you encounter a Zulip narrow URL (e.g., from `chat.zulip.org` in a
GitHub issue, PR, or user message), use the `/fetch-zulip-messages` skill
to read the conversation. Do not use `WebFetch` — it cannot access Zulip
message content.

## Common Commands

```bash
./tools/provision           # Set up development environment
./tools/run-dev             # Start development server
./tools/lint                # Run all linters
./tools/test-backend        # Run Python tests
./tools/test-js-with-node   # Run JavaScript tests
./tools/run-mypy            # Run type checker
git grep "pattern"          # Search codebase (use extensively!)
```

If a tool complains that provision is outdated, run `./tools/provision`
to fix it. Do not use `--skip-provision-check` to work around the
error; the check exists because tests and linters depend on provisioned
dependencies being current.
