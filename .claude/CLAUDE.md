# CLAUDE.md - Guidelines for AI Contributions to Zulip

This file provides guidance to Claude (and other AI coding assistants) for
contributing to the Zulip codebase. These guidelines are designed to produce
contributions that meet the same high standards we expect from human
contributors.

## Philosophy

Zulip's coding philosophy is to **focus relentlessly on making the codebase
easy to understand and difficult to make dangerous mistakes**. This applies
equally to AI-generated contributions. Every change should make the codebase
more maintainable and easier to read.

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

- Backend and API changes (with tests and API doc changes documented
  fully using our double-entry changelog system). When starting an API
  change, reread `docs/documentation/api.md` to review the process for
  documenting an API change. You'll run `tools/create-api-changelog`
  to create an `api_docs/unmerged.d/ZF-RANDOM.md` file. Never update
  `API_FEATURE_LEVEL` manually. **Changes** entries should use the
  "New in Zulip 12.0 (Feature level RANDOM)" pattern, which will be
  replaced with the final feature level when the changes are merged.
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
- JavaScript/TypeScript code must use `const` or `let`, never `var`.
- Avoid lodash in favor of modern ECMAScript primitives where available,
  keeping in mind our browserlist.
- Prefer writing code that is readable without explanation over heavily
  commented code using clever tricks. Comments should explain "why" when
  the reason isn't obvious, not narrate "what" the code does.
- Comments should have a line to themself except for CSS px math.
- **Review CSS for redundant rules.** After writing CSS, review the
  full set of rules affecting the same elements. Look for rules that
  are immediately overridden by a more specific selector, duplicated
  selector lists, or cases where scoping (e.g., `:not()`) would
  eliminate the need for an override.

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
- Include debugging code, commented-out code, or temporary TODOs.

### Commit Message Format

```
subsystem: Summary in 72 characters or less.

The body explains why and how. Include context that helps reviewers
and future developers understand your reasoning, analysis, and
verification of the work above and beyond CI, without repeating
details already well presented in the commit metadata (filenames,
etc.). Explain what the change accomplishes and why it won't break
things one might worry about.

Line-wrap at 68-70 characters, except URLs and verbatim content
(error messages, etc.).

Fixes #123.
```

**Commit summary format:**

- Before the colon is a lower-case brief gesture at subsystem (ex: "nginx" config) or
  feature (ex: "compose" for the compose box) being modified.
- Use a period at the end of the summary
- Example: `compose: Fix cursor position after emoji insertion.`
- Example: `nginx: Refactor immutable cache headers.`
- Bad examples: `Fix bug`, `Update code`, `gather_subscriptions was broken`

**Linking issues:**

- `Fixes #123.` - Automatically closes the issue
- `Fixes part of #123.` - Does not close (for partial fixes)
- Never: `Partially fixes #123.` (GitHub ignores "partially")

### Rebasing Commits (Non-Interactive)

Since `git rebase -i` requires an interactive editor, use
`GIT_SEQUENCE_EDITOR` to supply the todo list via a script:

1. **Squashing fixups into existing commits:** Create fixup commits with
   `git commit --fixup=<target-hash>`, then write a shell script that
   outputs the desired todo (with `pick` and `fixup` lines in order)
   and run:

   ```bash
   GIT_SEQUENCE_EDITOR=/path/to/todo-script.sh git rebase -i <base>
   ```

   Note: `--autosquash` alone without `-i` does **not** reorder or
   squash anything.

2. **Rewording commit messages:** In the todo script, use `exec` lines:
   ```
   pick <hash> Original message
   exec GIT_EDITOR=/path/to/new-msg-script.sh git commit --amend
   ```
   where the message script writes the new commit message to `$1`.

## Testing Requirements

Zulip server takes pride in its ~98% test coverage. All server changes
must include nice tests that follow our testing philosophy.

### Before Submitting:

```bash
./tools/test-js-with-node       # JavaScript tests; full suite fast enough
./tools/lint                    # Run all linters
./tools/test-backend            # Python tests
```

A common failure mode is failing to have test coverage for error
conditions that require coverage (note `tools/coveragerc` excludes
asserts). Run `test-backend --coverage FooTest` and check the coverage
data to confirm that the new lines you added are in fact run by the
tests.

### Testing Philosophy:

- Write end-to-end tests when possible verifying what's important, not
  internal APIs.
- Tests must work offline. Use fixtures (in `zerver/tests/fixtures`) for
  external service testing and `responses` for simpler things.
- Use time_machine and similar libraries to mock time.
- Read `zerver/tests/test_example.py` for patterns.
- A good failing test before implementing is good practice so your
  test and code can jointly verify each other.
- Remember to always assert state is correctly updated, not just "success".

### For Webhooks:

```bash
./tools/test-backend zerver/webhooks/<integration>
```

### Manual Testing for UI Changes

If a PR makes frontend changes, manually verify the affected UI. This
catches issues that automated tests miss:

**Visual appearance:**

- Is the new UI consistent with similar elements (fonts, colors, sizes)?
- Is alignment correct, both vertically and horizontally?
- Do clickable elements have hover behavior consistent with similar UI?
- If elements can be disabled, does the disabled state look right?
- Did the change accidentally affect other parts of the UI? Use
  `git grep` to check if modified CSS is used elsewhere.
- Check all of the above in both light and dark themes.

**Responsiveness and internationalization:**

- Does the UI look good at different window sizes, including mobile?
- Would the UI break if translated strings were 1.5x longer than English?

**Functionality:**

- Are live updates working as expected?
- Is keyboard navigation, including tabbing to interactive elements, working?
- If the feature affects the message view, try different narrows: topic,
  channel, Combined feed, direct messages.
- If the feature affects the compose box, test both channel messages and
  direct messages, and both ways of resizing.
- If the feature requires elevated permissions, test as both a user who
  has permissions and one who does not.
- Think about feature interactions: could banners overlap? What about
  resolved/unresolved topics? Collapsed or muted messages?

## Self-Review Checklist

Before finalizing, verify:

- [ ] The PR addresses all points described in the issue
- [ ] All relevant tests pass locally
- [ ] Code follows existing patterns in the codebase
- [ ] Names (functions, variables, tests) are clear and greppable
- [ ] Commit messages, comments, and PR description are well done.
- [ ] Each commit is a minimal coherent idea
- [ ] No debugging code or unnecessary comments remain
- [ ] Type annotations are complete and correct
- [ ] User-facing strings are tagged for translation
- [ ] User-facing error messages are clear and actionable
- [ ] No secrets or credentials are hardcoded
- [ ] Documentation is updated if behavior changes
- [ ] Refactoring is complete (`git grep` for remaining occurrences)
- [ ] Security audit of changes. Always check for XSS in UI changes
      and for incorrect access control in server changes.

Always output a recommend pull request summary+description that
follow's Zulip's guidelines once you finish preparing a series of
commits.

## Common Pitfalls

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

### Code Quality:

- Don't use `Any` type annotations without comments justifying it.
- Don't use `cursor.execute()` with string formatting (SQL injection risk)
- Don't use `.extra()` in Django without careful review and commenting
- Don't use `onclick` attributes in HTML; use event delegation
- Don't create N+1 query patterns:

  ```python
  # BAD
  for bar in bars:
      foo = Foo.objects.get(id=bar.foo_id)

  # GOOD
  foos = {f.id: f for f in Foo.objects.filter(id__in=[b.foo_id for b in bars])}
  ```

### Process:

- Always check if you're working on top of the latest upstream/main, and
  fetch + rebase when starting a project so you're not using a stale branch.
  If you're continuing a project, start by rebasing, resolving merge
  conflicts carefully.
- Don't submit code you haven't tested
- Don't skip becoming familiar with the code you're modifying
- Don't make claims about code behavior without verification, and
  cite your sources.
- Don't generate PR descriptions that just describe what files changed
- Always do a pre-mortem: Think about how to avoid a bug recurring,
  how it might break something that already works, or imagine under
  what circumstances your changes might need to be reverted.

## Pull Request Guidelines

### PR Description Should:

Output the PR description in a markdown code block so that formatting
(bold, headers, checkboxes, etc.) copy-pastes correctly into GitHub.

1. Start with a `Fixes: #...` line linking the issue being addressed.
2. Explain **why** the change is needed, not just what changed.
3. Describe how you tested the change, using checkbox format for the
   test plan (e.g., `- [x] ./tools/test-backend ...`).
4. Include screenshots for UI changes.
5. Link to relevant issues or discussions.
6. Call out any open questions, concerns, or decisions you are uncertain
   about, so they can be resolved during review.
7. Include the self-review checklist from
   `.github/pull_request_template.md` using checkbox format (`- [x]` /
   `- [ ]`), checking off all applicable items.

### PR Description Should Not:

- Regurgitate information visible from the diff
- Make claims you haven't double-checked
- Express more certainty than is justified given the evidence

## When to Pause and Discuss

Recommend pausing for discussion when:

- The approach involves security-sensitive code
- Database migrations are needed
- The change affects many files (>10)
- Performance implications are unclear
- The feature design isn't fully specified
- The API or data model design isn't fully specified
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

Help center articles are MDX files in `starlight_help/src/content/docs/`.
Images go in `starlight_help/src/images`. Include files go in the `include/`
subdirectory with an `_` prefix (e.g., `_AdminOnly.mdx`). New articles need
a sidebar entry in `starlight_help/astro.config.mjs`.

See `docs/documentation/helpcenter.md` for the full writing guide. Key points:

- **Bold** UI element names (e.g., **Settings** page, **Save changes** button).
- Do not specify default values or list out options in instructions — the user
  can see them in the UI.
- Do not use "we" to refer to Zulip; use "you" for the reader.
- Fewer words is better; many users have English as a second language.
- Use `<kbd>Enter</kbd>` for keyboard keys (non-Mac; auto-translated for Mac).
- Common components and their imports:
  ```
  import {Steps, TabItem, Tabs} from "@astrojs/starlight/components";
  import FlattenedSteps from "../../components/FlattenedSteps.astro";
  import NavigationSteps from "../../components/NavigationSteps.astro";
  import ZulipTip from "../../components/ZulipTip.astro";
  import ZulipNote from "../../components/ZulipNote.astro";
  import AdminOnly from "../include/_AdminOnly.mdx";
  import SaveChanges from "../include/_SaveChanges.mdx";
  ```

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
