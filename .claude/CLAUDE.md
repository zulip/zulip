# CLAUDE.md - Guidelines for AI Contributions to Zulip

This file provides guidance to Claude (and other AI coding assistants) for
contributing to the Zulip codebase. These guidelines are designed to produce
contributions that meet the same high standards we expect from human
contributors.

## Philosophy

Zulip is built to last for decades and holds a high bar for
readability, commit discipline, testing, and documentation. Its
engineering strategy is to "move quickly without breaking things":
every change should make the codebase easier to understand and
harder to make dangerous mistakes in. Maintainers expect to spend
review time on product and structure questions, not on catching
correctness issues, so the process below is designed to catch those
first.

### No detail is too small

There is no category of "minor issue" that is acceptable to ship —
if something is broken in any state, size, theme, or language where
a user would encounter it, it must be fixed before merging. If a fix
would require a design decision, raise it as a question rather than
shipping the broken state. The "Manual Testing for UI Changes"
checklist below enumerates what to check.

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

- Backend and API changes (with tests, and API documentation updated
  as described in "Documenting API Changes" below).
- Frontend UI changes (with tests and user-facing documentation
  updates). Remember to plan to use your visual test skill to check
  your work whenever you change web app code (HTML, CSS, JS).

Each commit should be self-contained, highly readable and reviewable
using `git show --color-moved`, and pass lint/tests independently. If
extracting new files or moving code, always do that in a separate
commit from other changes.

### 4. Verify Before Finalizing

Run the linter and the relevant tests before making each commit; see
"Testing Requirements" below for which ones.

## Documenting API Changes

API doc changes must be documented fully using our double-entry
changelog system. When starting an API change, reread
`docs/documentation/api.md` to review the process for documenting an
API change. Run `tools/create-api-changelog`; it generates an empty
`api_docs/unmerged.d/ZF-XXXXXX.md` file (where `XXXXXX` is a random
hex string the tool picks for you) and stages it for you. Document
the changes in that file as an unordered list (`*` bullets) of the
additions or changes, formatted to match `api_docs/changelog.md`.
Don't add a `**Feature level**` heading; the merge tooling emits that
itself.

In the OpenAPI yaml (`zerver/openapi/zulip.yaml`), reference the same
filename stem in **Changes** notes, e.g.,
`**Changes**: New in Zulip 13.0 (feature level ZF-XXXXXX).` The merge
process matches the `Zulip <version> (feature level ZF-XXXXXX)` shape
and overwrites both the version and the placeholder with the real
release version and final feature level. Use the upcoming release's
version — the next major release after the latest one shipped (e.g.,
13.0 while 12.0 is the current release), which you can read from the
first `## Changes in Zulip X.Y` heading in `api_docs/changelog.md`.
You must keep the literal `New in Zulip X.Y` format, or the merge
tooling won't recognize the note and CI (`check-feature-level-updated`)
will fail with the `ZF-` placeholder still in the file. Never update
`API_FEATURE_LEVEL` manually.

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
- If a value's correctness hinges on a qualifier — local, cached,
  approximate, lower bound — put that word in the name
  (`local_message_count`, not `message_count`). A reader who has to be
  told the caveat will eventually misuse the value.
- Keep everything well factored for maintainability. Avoid duplicating
  code, especially where access control or subtle correctness is involved.
- Before writing a helper, `git grep` the shared modules (e.g.,
  `web/src/util.ts`, `web/src/people.ts`, `web/src/message_util.ts`,
  `zerver/lib/`) for an existing equivalent. "It mirrors an existing
  pattern" justifies parallel structure, not duplicated code: if the
  new function equals an existing one modulo a parameter, extract a
  shared helper instead of copying.
- Run `./tools/lint` to catch style issues before committing, including mypy issues.
- JavaScript/TypeScript code must use `const` or `let`, never `var`.
- Avoid lodash in favor of modern ECMAScript primitives where available,
  keeping in mind our browserlist.
- Use `util.the($el)` instead of `$el[0]!` when a jQuery object should
  hold exactly one element; it asserts that at runtime.
- Use class or ID selectors in jQuery and CSS, not bare tag selectors
  (`$row.find("a")`) or attribute selectors (`[tabindex]`), which match
  unintended elements and can't be grepped for. If no suitable class
  exists, add one.
- Prefer writing code that is readable without explanation over heavily
  commented code using clever tricks. Comments should explain "why" when
  the reason isn't obvious, not narrate "what" the code does.
- A comment must make sense to a reader who never saw the old code.
  If it only makes sense as a contrast with how the code used to work
  ("show the modal before rendering so that if rendering throws..."),
  it describes the diff, and belongs in the commit message instead.
- Don't reference line numbers (`filter.ts:493`) in comments, commit
  messages, or PR descriptions; they are wrong after the next edit
  above them. Reference symbol names instead.
- Use the standard term for what the code does ("override the rule",
  "set the color"), not a metaphor ("defeat", "pin"). When the
  codebase already has a short idiom for a situation, such as
  `/* Override bootstrap defaults */`, reuse it verbatim rather than
  writing a longer explanation.
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

### Keep Unrelated Fixes Out of Feature PRs

If, while building a feature, you find and fix a pre-existing bug or
make a refactor that would be worth merging even if the feature never
lands, submit it as its own PR. A small isolated PR gets real
scrutiny; the same change as commit 1 of 6 in a large PR tends to be
waved through. Prep commits that only make sense for the feature
stay in the feature PR.

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

**Only claim what you verified:**

- `Fixes #123.` on a bug report asserts the bug was reproduced and
  the change resolves it. If you couldn't reproduce it, tell the user
  rather than writing `Fixes`; they may be able to confirm it. Issues
  that describe a feature rather than a bug need no reproduction.
- The same applies to any claim in a commit message or PR description
  about what the code does; state only what you checked by reading
  the code, running it, or running tests.

### Rebasing Commits

To change a commit that is not at HEAD (squash a fixup into it,
reorder, or reword it), use the `/git-rebase` skill; `git rebase -i`
needs an interactive editor and won't work directly.

## Testing Requirements

Zulip server takes pride in its ~98% test coverage. All server changes
must include nice tests that follow our testing philosophy.

### Before Submitting:

Manage your time by running specific backend test collections, not
the entire suite; the node suite is fast enough to run in full.

```bash
# Includes mypy and typescript checkers
./tools/lint path/to/changed/files.py
./tools/test-backend zerver.tests.test_relevant_module
./tools/test-js-with-node
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
- Name and comment tests by what they guarantee ("must not throw when
  the list is empty"), not by the past failure they were written
  after ("regression test for the empty-list crash"). The same goes
  for commit messages.

### For Webhooks:

```bash
./tools/test-backend zerver/webhooks/<integration>
```

### Manual Testing for UI Changes

If a PR makes frontend changes, manually verify the affected UI. This
catches issues that automated tests miss. **Treat this checklist as
blocking, not advisory** — every applicable item must be verified
before the change is ready.

Most of these items don't need a human: the `/visual-test` skill can
screenshot the UI at several window widths and in both themes, measure
positions with `getBoundingClientRect()`, and drive keyboard
navigation. Verify what you can that way before asking the user to
test anything.

When the skill can't run in your environment, much of the list can
still be checked from code: `git grep` every selector you touched to
see where else it applies, look for fixed widths or `white-space:
nowrap` that a longer translated string would overflow, and read the
keyboard-handling and permission code paths you changed. Then tell
the user exactly which items you could not verify (rendered alignment,
hover appearance) rather than a general "please test".

**Visual appearance:**

- Is the new UI consistent with similar elements (fonts, colors, sizes)?
  Find the closest existing analogues and compare carefully.
- Is alignment correct, both vertically and horizontally? Measure
  programmatically with `getBoundingClientRect()` when in doubt —
  don't eyeball it.
- Do clickable elements have hover behavior consistent with similar UI?
- If elements can be disabled, does the disabled state look right?
- Does every state look right: hover, active, disabled, focused,
  selected, empty, overflowing?
- Did the change accidentally affect other parts of the UI? Use
  `git grep` to check if modified CSS is used elsewhere. CSS changes
  are notorious for unintended consequences — check every page and
  component that shares the selectors you modified, and demonstrate
  with pixel-precise before/after comparisons that there are none.
- Check all of the above in both light and dark themes when the
  change could plausibly affect colors, contrast, or theme-dependent
  imagery. Pure geometry/typography changes (`font-size`,
  `line-height`, `margin`, `padding`, `display`, `font-weight`,
  etc.) don't need a separate dark-theme pass —
  `web/styles/dark_theme.css` only overrides colors, so a single
  theme suffices for theme-invariant changes.

**Responsiveness and internationalization:**

- Does the UI look good at different window sizes? Check wide desktop
  (1920px), typical laptop (1280px), tablet, and narrow phone (480px).
- Would the UI break if translated strings were 1.5x longer than
  English? What if they were half as long? Both directions matter.
  Think about right-to-left languages too.

**Functionality:**

- Are live updates working as expected?
- Is keyboard navigation, including tabbing to interactive elements, working?
- Do screen readers get sensible labels and roles for new elements?
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
- [ ] If a helper's return value or a shared data structure gained a
      field, every consumer that destructures or rebuilds it was
      audited, including sibling blocks in the same file that build
      the same shape. TypeScript does not flag callers that silently
      drop the new field.
- [ ] Security audit of changes. Always check for XSS in UI changes
      and for incorrect access control in server changes.

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

- In tests, don't assert on `assertLogs` output with
  `any(phrase in line for line in mock_log.output)`; pin the full line
  against `mock_log.output`, or a substring to a specific `mock_log.output[i]`.

### Process:

- When starting or resuming work, `git fetch` and check whether the
  branch is behind `upstream/main`; tell the user if so. Rebasing
  their branch is their decision; don't run `git rebase` unless asked.
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
- Database migrations are needed (See `docs/subsystems/schema-migrations.md`).
- The change alters behavior in several subsystems at once (a
  mechanical rename or type annotation sweep touching many files
  does not count)
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

When removing a CSS dependency (e.g., Bootstrap), audit the full
property list of every rule, not just visually obvious properties like
colors and backgrounds. Subtle properties like `line-height`, `margin`,
`padding`, `text-decoration`, `font-weight`, and `border` are easy to
miss but cause visible regressions. Check inherited properties too —
e.g., a `body` rule's `line-height` or `margin` affects all descendants.

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
