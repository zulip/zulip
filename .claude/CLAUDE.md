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
  It must work in both light and dark themes.
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
- Use `em` units instead of `px` for computed CSS values that need to
  scale with font size. Pixel approximations break at different zoom
  levels and font-size settings.
- Comments should have a line to themself except for CSS px math.
- **Review CSS for redundant rules.** After writing CSS, review the
  full set of rules affecting the same elements. Look for rules that
  are immediately overridden by a more specific selector, duplicated
  selector lists, or cases where scoping (e.g., `:not()`) would
  eliminate the need for an override.
- **Check CSS change scope.** When modifying CSS, always check what
  other pages or components use the same selectors, files, and
  classes. Use `git grep` on class names and check webpack bundle
  entries to understand which pages load the file. Prefer scoped
  overrides (e.g., `.parent .target`) over modifying shared rules,
  to avoid unintended changes to other parts of the app.

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
- In a multi-commit PR, use `Fixes part of #123.` in earlier commits
  and `Fixes #123.` in the final commit.
- Never: `Partially fixes #123.` (GitHub ignores "partially")

### Rebasing Commits (Non-Interactive)

Since `git rebase -i` requires an interactive editor, use
`GIT_SEQUENCE_EDITOR` to supply the todo list via a script:

1. **Updating the HEAD commit:** If the commit you need to modify is
   already at HEAD, just use `git commit --amend` directly. The
   fixup+rebase workflow below is only needed for non-HEAD commits.

2. **Squashing fixups into existing commits:** Create fixup commits with
   `git commit --fixup=<target-hash>`, then write a shell script that
   outputs the desired todo (with `pick` and `fixup` lines in order)
   and run:

   ```bash
   GIT_SEQUENCE_EDITOR=/path/to/todo-script.sh git rebase -i <base>
   ```

   Note: `--autosquash` alone without `-i` does **not** reorder or
   squash anything.

3. **Rewording commit messages:** Use `git format-patch` to export
   commits as patch files, edit the message headers in the patch
   files, then reapply:

   ```bash
   git format-patch <base> -o /tmp/patches/
   # Edit the commit message in each /tmp/patches/000N-*.patch file
   # (the message is between the Subject: line and the --- line)
   git reset --hard <base>
   git am /tmp/patches/*.patch
   ```

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
catches issues that automated tests miss. **Treat this checklist as
blocking, not advisory** — every applicable item must be verified
before the change is ready.

**Visual appearance:**

- Is the new UI consistent with similar elements (fonts, colors, sizes)?
  Find the closest existing analogues and compare carefully.
- Is alignment correct, both vertically and horizontally? Measure
  programmatically with `getBoundingClientRect()` when in doubt —
  don't eyeball it.
- Do clickable elements have hover behavior consistent with similar UI?
- If elements can be disabled, does the disabled state look right?
- Did the change accidentally affect other parts of the UI? Use
  `git grep` to check if modified CSS is used elsewhere. CSS changes
  are notorious for unintended consequences — check every page and
  component that shares the selectors you modified.
- Check all of the above in both light and dark themes.

**Responsiveness and internationalization:**

- Does the UI look good at different window sizes? Check wide desktop
  (1920px), typical laptop (1280px), tablet, and narrow phone (480px).
- Would the UI break if translated strings were 1.5x longer than
  English? What if they were half as long? Both directions matter.

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
- Think about edge cases in data: empty lists, very long names, single
  items vs. hundreds, special characters in strings.

### Puppeteer Visual Tests: Verifying Alignment

When using Puppeteer to verify visual alignment, do not rely on
eyeballing screenshots — especially small full-page ones. Instead:

- Use `page.evaluate()` with `getBoundingClientRect()` to measure
  actual pixel positions of the elements you need aligned, and print
  them to the console. Compare the numbers.
- Always take **both** a full-page screenshot and a zoomed clip of
  the area of interest.
- For zoomed clips, calculate the clip region from non-fixed elements;
  fixed/sticky elements may report bounding-box positions that don't
  match their visual location on the page.
- Be aware that CSS nesting can scope styles to a specific parent
  (e.g., `.parent .my-class`) — reusing the same class name in a
  different context may not pick up the expected styles.
- To verify keyboard-focus styles, use real keyboard navigation
  (`page.keyboard.press`); programmatic `.focus()` doesn't reliably
  trigger `:focus-visible` and may be overridden by view-level focus
  management.
- Focus rings drawn as `::before` / `::after` pseudo-elements aren't
  visible in `getComputedStyle` of the focused element — verify them
  in a screenshot, not via computed styles.
- For visual changes, produce before/after screenshot pairs by writing
  one test and running it twice with a `SCREENSHOT_SUFFIX` env var
  (`-old` on `main`, `-updated` on your branch).

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

### Code Quality:

- Don't use `Any` type annotations without comments justifying it.
- Don't use `cursor.execute()` with string formatting (SQL injection risk)
- Don't use `.extra()` in Django without careful review and commenting
- Don't use `onclick` attributes in HTML; use event delegation
- Don't access DOM APIs (`document.documentElement.style`, `$()`
  selectors for specific elements) without guarding for node test
  environments, where the DOM is mocked minimally. Check that the
  element exists before using it.
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

### PR Description Should:

When opening a pull request, prefix the PR title with `[ai]` (e.g.,
`[ai] compose: Fix cursor position after emoji insertion.`). Use
`upstream/main` as the base branch.

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

When removing a CSS dependency (e.g., Bootstrap), audit the full
property list of every rule, not just visually obvious properties like
colors and backgrounds. Subtle properties like `line-height`, `margin`,
`padding`, `text-decoration`, `font-weight`, and `border` are easy to
miss but cause visible regressions. Check inherited properties too —
e.g., a `body` rule's `line-height` or `margin` affects all descendants.

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
- Do not specify default values or list out options — the user can see
  them in the UI. For dropdowns, refer to the setting by its label name
  rather than enumerating the choices.
- Do not use "we" to refer to Zulip; use "you" for the reader.
- Fewer words is better; many users have English as a second language.
- Use `<kbd>Enter</kbd>` for keyboard keys (non-Mac; auto-translated for Mac).
- Use `FlattenedList` to merge adjacent bullet lists (inline markdown
  and/or include components) into a single visual list. Use
  `FlattenedSteps` for the same purpose with ordered (numbered) lists.
- Common components and their imports:
  ```
  import {Steps, TabItem, Tabs} from "@astrojs/starlight/components";
  import FlattenedList from "../../components/FlattenedList.astro";
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
