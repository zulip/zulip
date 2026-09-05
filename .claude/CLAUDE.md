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

There is no category of "minor issue" that is acceptable to ship —
if something is broken in any state, size, theme, or language where
a user would encounter it, it must be fixed before merging. If a fix
would require a design decision, raise it as a question rather than
shipping the broken state. See `.claude/rules/ui-testing.md` for
what to test for UI changes (the file loads automatically when you
work on frontend files).

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

Run the linter and the relevant tests before making each commit; see
"Testing Requirements" below for instructions.

Run through the `/self-review` skill's checklist before suggesting opening
a PR (`.claude/skills/self-review/SKILL.md`).

## Before You Start

### Read the Relevant Documentation

Zulip has over 185,000 words of developer documentation. Before working on any area:

- Read documentation from docs/, starlight_help/src/content/docs/, and api_docs/.
  `docs/subsystems/directory-structure.md` explains where code lives.
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

See: https://zulip.readthedocs.io/en/latest/contributing/code-style.html

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

Manage your time by running specific backend test collections, not
the entire suite; the node suite is fast enough to run in full.

```bash
# Includes mypy and typescript checkers
./tools/lint path/to/changed/files.py
./tools/test-backend zerver.tests.test_relevant_module
./tools/test-js-with-node
```

### Manual Testing for UI Changes

If a PR makes frontend changes, manually verify the affected UI
using the checklist in `.claude/rules/ui-testing.md` (loaded
automatically when you work on frontend files).

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

1. Show the relevant code and explain what's happening
2. Brainstorm theories for how the bug might be possible
3. Analyze and propose a fix with a clear explanation
4. Write tests that would have caught this bug if possible
5. Format as a single commit following commit guidelines
6. Audit for whether the bug may exist elsewhere or might be
   re-introduced and propose appropriate changes to address if so.

### For New Features

1. Read the relevant documentation in docs/
2. Show similar existing features in the codebase
3. Propose an implementation approach before coding
4. Implement in minimal, coherent commits
5. Each commit must pass tests independently

### For Refactoring

1. Show the current implementation
2. Explain what makes it problematic
3. Propose the refactoring approach
4. Implement in commits that each leave the codebase working
5. No behavior changes unless explicitly discussed
6. Verify completeness: use `git grep` to find all occurrences and
   confirm nothing was missed

## Key Documentation Links

- Contributing guide: https://zulip.readthedocs.io/en/latest/contributing/contributing.html
- Code style: https://zulip.readthedocs.io/en/latest/contributing/code-style.html
- Commit discipline: https://zulip.readthedocs.io/en/latest/contributing/commit-discipline.html
- Testing overview: https://zulip.readthedocs.io/en/latest/testing/testing.html
- Backend tests: https://zulip.readthedocs.io/en/latest/testing/testing-with-django.html
- Code review: https://zulip.readthedocs.io/en/latest/contributing/code-reviewing.html
- mypy guide: https://zulip.readthedocs.io/en/latest/testing/mypy.html

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
