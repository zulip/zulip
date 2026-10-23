---
name: design-review
description: First-pass check of a Zulip web-app PR (or the current diff) against DESIGN.md, the per-component specs in .claude/rules/components/, and the repo's UI rules — tokens, component reuse, states in both themes, behaviour patterns, accessibility, likely regressions, help-center docs — producing CONFIRMED/PLAUSIBLE findings with file:symbol evidence. Not a full design review. Where a Zulip development environment is available, also runs the change in a browser and checks screenshots and measurements. Use when the user runs /design-review <PR#|branch> [full] [code], or asks to "design-check" or "vibe-check" a UI PR.
---

# Design review

Checks a change against Zulip's design system _as implemented_. Read-only:
never edit files, never post to GitHub, never commit.

## What this does and doesn't do

A first-pass check of a web app change against what `DESIGN.md` and the
component specs already say. It catches the issues a reviewer would
otherwise point out by hand: raw colours and px values, markup that
re-creates an existing partial, missing states or theme handling, icon-only
controls without a label, token swaps that change a colour, and side effects
on other places that use the same code.

It does not:

- Judge the design itself: layout, hierarchy, wording, or whether the
  feature should work this way. That stays with the design and product
  reviewers.
- See the UI, unless the Visual pass ran. Without it, it reads code only,
  so every PLAUSIBLE finding needs a check in the dev server, and
  CONFIRMED findings should be reproduced before anyone raises them.
- Settle open design questions. Where the docs have no rule, it says so
  instead of inventing one.
- Replace testing, the `/self-review` checklist or code review. Code
  quality and commit structure are out of scope.

Treat the output as a list of things to look at, not a verdict on the PR;
it gives no pass or fail.

## Errors and progress

Stop with one of these lines, exactly, when a precondition fails:

- `DESIGN-REVIEW ERROR: cannot fetch PR <N> (<reason>). Check the network and that the PR number exists.`
- `DESIGN-REVIEW ERROR: DESIGN.md not found at the repo root. Run this from a Zulip checkout that has it.`
- `DESIGN-REVIEW ERROR: no target. Pass a PR number, or run it on a branch with changes against zulip/zulip main.`

If a spec named in the table below is missing, print
`DESIGN-REVIEW WARNING: spec <file> not found; reviewing without it.` and
carry on.

While working, print one short line per step so the user can follow along:
`▸ source: …`, `▸ scope: …`, `▸ mode: …`, `▸ specs: …`, `▸ reading: …`,
`▸ checklist: …`.

After any stop (an error or `OUT OF SCOPE`), still print the log line, with
`ERROR` or `OUT OF SCOPE` after the mode and `raised=0 kept=0`, and the
`TRACE` block from Output, with the fields that were reached.

## Target

1. From `$ARGUMENTS`:
   - A PR number:
     - Fetch the head:
       `git fetch https://github.com/zulip/zulip +pull/<N>/head:refs/remotes/review/pr-<N>`.
     - Refresh the base: `git fetch https://github.com/zulip/zulip +main:refs/remotes/review/main`.
     - Diff with `git diff review/main...review/pr-<N>`.
     - Read the title and description:
       `gh pr view <N> --repo zulip/zulip --json title,body`, or without
       `gh`, `curl -sS https://api.github.com/repos/zulip/zulip/pulls/<N>`.
       Fetch an `#issue` the body cites only when the diff's intent is
       unclear. If neither works, say in one line that the title and
       description were not read, and carry on.
     - Design source: note every design link in the description (a
       chat.zulip.org thread, a Figma file, mock-up images). Read the ones
       you can reach (the `/fetch-zulip-messages` skill for chat.zulip.org
       threads) and use them as the intended design. If there are none, or
       you could not read them, the output says so.
     - Review history: read the review comments
       (`gh api repos/zulip/zulip/pulls/<N>/comments` and
       `gh api repos/zulip/zulip/issues/<N>/comments`, or the same paths
       under `https://api.github.com/` with `curl`). Don't raise a point
       that a reviewer and the author already settled.
   - A branch or nothing → refresh the base with the same
     `git fetch https://github.com/zulip/zulip +main:refs/remotes/review/main`
     and diff with `git diff review/main...HEAD` (a fork's `origin/main` may
     be far behind). If that fetch fails, use `upstream/main` and say so in
     one line; with no commits ahead of the base, fall back to `git diff` of
     the working tree.
2. List the changed files with `--name-only` on the same diff, and apply
   Scope before reading any diff content. Then diff only the in-scope paths
   (`git diff <base>...<head> -- <paths>`).

## Scope

`DESIGN.md` and the specs describe the **web app** only. Keep only these:

- `web/templates/**`
- `web/styles/**`, except `web/styles/portico/**` and `pygments.css`
- `web/src/**`, except `web/src/portico/**` and `web/src/billing/**`
- `web/icons/**` (quick check only: naming and that the icon is used)
- `templates/zerver/app/**` (the app's page shell)

Everything else is out of scope: the website, billing and other portico
pages (`templates/**` apart from `templates/zerver/app/`,
`web/styles/portico/`, `web/src/portico/`, `web/src/billing/`), emails
(`templates/zerver/emails/`), the help center and docs (`starlight_help/`,
`api_docs/`, `docs/`), translations (`locale/`), tests only (`web/tests/`,
`web/e2e-tests/`), vendored or generated files (`web/third/`,
`web/generated/`), and backend or tooling.

- No in-scope files → reply `OUT OF SCOPE: <one line on what the PR
touches>` and stop.
- Some in-scope files → review only those, and name the skipped files in
  one line of the output.
- Some app stylesheets are also loaded on portico pages, which do not load
  `app_variables.css`: `modal.css`, `alerts.css`, `blueslip.css` and
  `progress_bar.css` (`web/src/bundles/common.ts`), and `components.css`
  (`help_bundle.ts`, `integrations_bundle.ts`). Flag a change in them that
  would also affect portico, e.g. a token from `app_variables.css`.

## Mode

- **Quick** (default): every checklist item, kept short. Item 3 only for
  states the diff visibly changes; item 5 at most two scenarios, one
  `git grep` each, and none if none is likely; item 6 only if user-visible
  strings, flows or keyboard behaviour changed; item 7 only when it applies.
- **Full**: every checklist item in depth. Use it when `$ARGUMENTS`
  contains `full`, or when the in-scope diff changes more than 400 lines
  and `$ARGUMENTS` does not contain `quick`.

State the mode in the summary line.

Both modes also run the Visual pass below, whenever a provisioned Zulip
development environment is available. `code` in `$ARGUMENTS` skips it.
Where it cannot run, the review is code-only and the summary line says so.

## Rulebook, specs and rules

1. Rulebook: `DESIGN.md` at the repo root. Read it fully.
2. Component specs: for every component the diff **edits or uses**, read
   the matching file in `.claude/rules/components/`. Decide by grepping the
   changed file names and the diff's added and removed lines (not context
   lines) for the entry points
   (the `DESIGN.md` → Components table is the index):

   | Spec                   | Grep the diff for                                                                                                               |
   | ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
   | `action-button.md`     | `action_button`, `action-button`                                                                                                |
   | `icon-button.md`       | `icon_button`, `icon-button`                                                                                                    |
   | `banner.md`            | `components/banner`, `.banner-`, `banners.` (the `banners.ts` module, not `compose_banner` or `popup_banners`)                  |
   | `text-input.md`        | `input_wrapper`, `input-element`, `filter-input`, `settings_text_input`                                                         |
   | `input-pill.md`        | `input_pill`, `pill-container`, `.pill`                                                                                         |
   | `popover-menu.md`      | `popover-menu`, `popover_menus`, `data-theme="popover-menu"`                                                                    |
   | `dropdown-widget.md`   | `dropdown_widget`, `dropdown-widget`, `dropdown-list`, `dropdown_list`                                                          |
   | `modal.md`             | `dialog_widget`, `confirm_dialog`, `modal__`, `micromodal`                                                                      |
   | `settings-controls.md` | `settings_checkbox`, `rendered-checkbox`, `tab-switcher`, `ind-tab`, `components.toggle`, `input-group`, `save-button-controls` |
   | `indicators.md`        | `unread_count`, `user-circle`, `tippy`, `data-tippy`, `loading_indicator`, `make_indicator`, `loader.hbs`                       |
   | `sidebar-rows.md`      | `top_left_row`, `bottom_left_row`, `left_sidebar`, `stream_sidebar_row`, `topic_list_item`, `narrow-filter`                     |

   Do not load specs for components the diff does not touch. If no spec
   matches, say so in the "rulebook could not judge" line and compare the
   change with the nearest existing use in the codebase.

3. Repo rules: `.claude/rules/css.md`, `.claude/rules/frontend.md`,
   `.claude/rules/ui-testing.md`, and `docs/subsystems/accessibility.md`
   when the diff adds interactive elements.

## Reading budget

Most of a review's cost is reading code, so read narrowly. The rulebook,
specs and repo rules above don't count towards the budget.

- Read code from the refs Target set up, never from the working tree, which
  may be older than the base: `git show <ref>:<path> | sed -n '<from>,<to>p'`
  and `git grep -n <term> <ref>` (with the ref in a shell variable, write
  `"${ref}:<path>"`; zsh reads `$ref:w…` as a modifier). Use the head ref (`review/pr-<N>` or
  `HEAD`) for the changed code and the base ref (`review/main`) for the rest
  of the codebase.
- Read changed code as hunks plus about 40 lines around them, not whole
  files.
- Beyond the diff, open at most 5 other files in quick mode and 10 in full
  mode. `git grep -n` searches don't count; prefer them to opening a file.
- The nearest existing element of the same kind (the sibling the change
  copies or sits next to) doesn't count either: always read its CSS and
  template, since most questions about a new element are answered by what
  its sibling does.
- Stop exploring a checklist item once it has an answer backed by code.

## Checklist (answer in order, each with file and symbol, never line numbers)

1. **Tokens** — any raw `hsl()`/`#hex`, px sizing that should be `em`,
   new radius / shadow / z-index / `!important` / inline `style=`? Cite the
   token or scale from the rulebook that should have been used. A new
   custom property must follow `--color-<property>-<intent>-<attention>-<component>[-<state>]`
   and live in the first `:root` block of `app_variables.css` (or the
   `modal.css` `:root` block for modal surfaces) — not inside its
   `%dark-theme` block, which only applies in the dark theme; flag names
   that copy the legacy `--background-color-*` or property-less
   `--color-<thing>` forms, and new `:root` blocks elsewhere.
2. **Components** — hand-rolled markup that a partial in
   `web/templates/components/` provides? Legacy classes (`.button`,
   `.alert`)? Direct `addClass`/`removeClass` of
   variant/intent classes instead of the `buttons.ts` helpers? Check the
   spec's _API_ and _Don't_ lists.
3. **States & themes** — for every new or changed element: hover, active,
   focus-visible, disabled, loading, selected, empty, overflow; light and
   dark; 480–1920px; 1.5× string length and RTL; base font 12–20px. Say
   which are covered by the diff, inherited from a partial, or missing.
   Without the Visual pass, report only what the code proves (a state with
   no rule, a fixed width that cannot fit a longer string); how a state
   looks is for the Visual pass.
   Where a claim depends on box model or specificity, verify by reading the
   cascade, never by assumption (buttons and legacy inputs are
   `content-box`: a `width` or `height` excludes padding and border, and
   auto height always adds the border).
4. **Behaviour & accessibility** — does the change follow the rulebook's
   Floating layers, Focus & keyboard, Accessibility, Feedback and Motion
   sections and the spec's _Behaviour_ / _Accessibility_ blocks? Name the
   sanctioned symbol and whether the diff uses it. Labels on icon-only
   controls, `alt`, focus ring, Escape.
5. **Regressions** — concrete scenarios (shared selectors elsewhere via
   `git grep`, other callers of a changed function, scroll containers,
   keyboard flows, other views rendering the same component): up to two
   in quick mode and six in full mode, and only ones the diff makes
   likely; none is a valid answer. Verify each in code; mark CONFIRMED
   (code proves it) or PLAUSIBLE (only a browser can settle it — say
   which check).
6. **Docs & tests** — if a user-visible string, flow or keyboard behaviour
   changed, grep `starlight_help/src/content/docs/` for the old wording. Is
   there a node test (`web/tests/`) or puppeteer test where this belongs?
   Name it; don't ask for a test for a CSS-only change.
7. **Token changes** — only when the diff adds, renames or changes a
   custom property, or swaps raw colours for `var()`. Say which kind the PR
   is: a _swap_ (claims no visible change), a _value change_, or a _new
   token_. Token values are in `web/styles/app_variables.css` (and the
   `modal.css` `:root` block).
   - Swap: for every replaced raw colour, resolve the token (`var()` chains,
     `light-dark()`) and compare it with the raw value in each theme where
     the rule applies — both themes for a plain rule, dark only for
     `dark_theme.css`; also check `dark_theme.css` for an override of the
     same selector that the swap bypasses. Any difference is a visible
     change (CONFIRMED, name the theme and element).
   - Meaning: `git grep` every use of the token, old and new. Each must
     pass the role test — "if this token's value changed, should every one
     of these change with it?" Flag uses on a different surface (text on a
     solid fill vs on a dark scrim, a component that has its own token
     family). Flag a new token that duplicates an existing one with the
     same meaning.
   - Value change: list every element that uses the token, in both themes,
     and check the changed pairs for contrast (4.5:1 text, 3:1 icons and
     focus indicators).
   - New token: name follows the pattern above; both themes defined; no
     existing token already carries the same meaning (grep
     `app_variables.css` for the same resolved values and similar names);
     every use passes the role test; contrast as for a value change.
   - Evidence: a swap PR needs a before/after comparison of computed
     colours on the affected elements in both themes; a value change needs
     before/after screenshots in both themes; a new token needs
     screenshots of its uses in both themes. Missing evidence is a
     PLAUSIBLE finding.

## Visual pass

Runs by default, after the checklist's code reading, unless `$ARGUMENTS`
contains `code`. It runs the change in Zulip's Puppeteer test server and
checks screenshots and measurements, which is where most real design
issues show. It needs a checkout with a provisioned Zulip development
environment; run every `./tools/` command inside it (see `AGENTS.md`).
Without one (no checkout, or step 1 fails), skip the pass and report it
as not run, with the reason.
Follow `.claude/skills/visual-test/SKILL.md` for how to write the script
and `.claude/rules/ui-testing.md` for what to cover.

1. **Worktree.** Run the `visual-worktree` script that sits next to this
   file, as `visual-worktree prepare <head ref>`, from the checkout. It
   checks the head ref out in one reused worktree
   (`.claude/worktrees/design-review-visual` in the main checkout), which
   shares the main checkout's dependencies, and prints its path. The main
   checkout and its development server are not touched. If it stops with
   an error, report the visual pass as not run, with the reason.
2. **Plan.** From the diff, list each new or changed element a user can
   see, the screen it is on, the data it needs to appear (for example
   enough topics to scroll) and its nearest existing sibling. Read the
   code that shows and hides it; don't guess selectors.
3. **Script.** Write `web/e2e-tests/_claude_visual_<target>.test.ts` in the
   worktree. Create data through the API (`fetch` with the CSRF token),
   not by clicking. For each element capture:
   - light and dark theme (`color_scheme=3`, then `2`, via
     `PATCH /json/settings`, then reload);
   - rest, hover and keyboard focus (press Tab before focusing, so
     `:focus-visible` applies), plus disabled, selected, empty and loading
     where the element has them;
   - a label 1.5× longer than the English one, set in the DOM;
   - a 1400×1024 window and a 480×800 one. Call `page.setViewport` for
     the wide size at the start too, since there is no way back to the
     default. At 480px the left sidebar is a closed overlay: open it with
     the visible `.left-sidebar-toggle-button`.
   - what happens after each action: where focus goes (read
     `document.activeElement` two animation frames later, not at once),
     what feedback appears, the cancel path, and removing the last item.

   Take whole-viewport screenshots with `common.screenshot`. Don't pass
   `clip` to `page.screenshot`: it lays the page out again and the
   sidebars come out blank. Instead record each element's
   `getBoundingClientRect()` and crop the PNG afterwards.

   Measure, don't judge by eye: for each element and for its sibling,
   write `getBoundingClientRect()` and the computed colour, background,
   border, radius, font, outline, opacity and cursor to
   `var/puppeteer/<target>-measurements.json`. Wait for transitions to
   finish before capturing (`waitForFunction` on the computed value); a
   fade can be on an ancestor, such as a modal's overlay, so check
   `opacity` up the ancestors too. Give every screenshot its own name, so
   a re-run never leaves an older one behind.

4. **Run.** In the worktree:
   `./tools/test-js-with-puppeteer --skip-provision-check _claude_visual_<target>`.
   The provision check is skipped because the worktree uses the main
   checkout's provisioned dependencies, which step 1 verified match.
   Screenshots land in `var/puppeteer/`. Fix the script and re-run if it
   fails; a script failure is not a finding.
5. **Check.** Read the screenshots and the measurements, and compare:
   - with the sibling: size, spacing, alignment, radius, colours, focus
     ring. A difference needs a reason in the design source.
   - with the design source, where there is one.
   - with `DESIGN.md`: contrast from the computed colours (4.5:1 text, 3:1
     icons, focus indicators and control boundaries), overflow of the long
     label, nothing clipped or overlapping at 480px, both themes.
   - with the code findings: a PLAUSIBLE finding the browser settles
     becomes CONFIRMED or is dropped.
6. **Clean up.** Delete the script from the worktree. Leave the worktree
   in place for the next review; `visual-worktree remove` deletes it.

To let the user look for themselves, end the script with a loop that
waits until `var/puppeteer/done` exists (or an hour passes) and run it in
the background: the test server stays up with the script's data at
`http://zulip.zulipdev.com:9981`, where they sign in with the user in
`var/puppeteer/test_credentials.json`. Create the `done` file to stop it.

A visual finding is CONFIRMED and names its screenshot and the measured
values. Say which elements and states were captured, and which were not
and why.

## Output

- One summary line: `<n> to look at` or `Nothing to look at`, the mode,
  and whether the visual pass ran. No pass or fail.
- One line naming out-of-scope files that were skipped, if any.
- Findings only, starting with what a user would notice, at most 5 in
  quick mode and 8 in full: what → evidence → why it matters → suggested
  fix → CONFIRMED | PLAUSIBLE. Before writing the list, re-read each
  finding and drop the ones you would retract on reflection; don't print
  them.
- `Checked, fine:` one line naming what was checked and raised nothing.
  Never a numbered item.
- `Codebase differs from the docs:` at most one line, only when the
  Guardrails send something here.
- `Design source:` what was read (thread, mock-ups), or "not read".
- One line: what the rulebook could not judge and which section or spec
  would have.
- Under 400 words in quick mode, 500 in full, not counting the log line
  and `TRACE`. No praise, no restating the diff.

Then print one line the user can paste into a shared log:
`<YYYY-MM-DD> <target> <mode>[+visual] raised=<n> kept=<n>` (`+visual`
when the Visual pass ran), where `raised` counts the
findings before the re-read and `kept` the ones printed.

Finally print a `TRACE` block (a fenced code block) so the user can check
the run did what this skill says:

```
source:   git fetch | branch | working tree (title/description read: yes|no)
design:   <design links read, or none>; review comments read: yes|no
mode:     quick | full (default | `full` argument | <n> in-scope lines)
scope:    <n> in scope: <files>; <n> skipped: <files>
rulebook: DESIGN.md read
specs:    <spec> ← <matched term>, … (or: none matched)
rules:    <repo rules read>
reading:  <n> of <budget> extra files: <files>; <n> searches: <terms>
items:    in depth <numbers>; short <numbers>; not applicable <numbers>
visual:   skipped (`code`) | not run (<reason>) | <n> screenshots: <elements and states>
warnings: <any DESIGN-REVIEW WARNING lines, or none>
```

## Guardrails

- Findings must cite code you actually read. "Looks inconsistent" without
  a symbol is not a finding.
- Settle in code whatever code can settle before reporting: read the
  sibling element, count uses with `git grep`, follow the cascade. Report
  only what survives. PLAUSIBLE is for claims only a browser can settle.
- Before citing a rule, check what the surrounding code does. If the
  sibling the change copies doesn't follow the rule either, and most of
  the codebase doesn't, it is not a finding on this PR: put it in the
  `Codebase differs from the docs` line.
- A choice the design source shows (a shape, a size, a label) is not a
  finding, even where it differs from `DESIGN.md`; name it in the
  "rulebook could not judge" line so the docs can catch up.
- Legacy listed under a spec's _Known debt_ is not a finding unless the
  diff adds more of it.
- Where `DESIGN.md` or a spec says "for new code", apply it to added lines
  only, not to existing code the diff moves or touches.
- Don't raise open design questions (those the docs leave open) as
  findings; mention them in the "rulebook could not judge" line.
- Commit structure and commit messages are out of scope; maintainers
  review those.
- Do not post the result anywhere. The user reproduces CONFIRMED items in
  the dev server and writes any PR comment in their own words (Zulip's
  AI-use policy).
