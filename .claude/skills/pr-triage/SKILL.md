---
name: pr-triage
description: "Run the PR and issue triage tool against a date range and review the output. Use when the user asks for triage of recent PRs or issues in zulip/zulip. The tool itself is at tools/triage/."
argument-hint: "[date-range like 2026-04-01_2026-04-15]"
---

# PR and issue triage

The tool lives at `tools/triage/` — see its `README.md` for full docs. This
skill is a thin pointer for AI assistants helping with a triage pass.

## Three views, each a two-step run

```bash
# Created-mode: PRs created in the range.
python3 tools/triage/fetch.py YYYY-MM-DD_YYYY-MM-DD
python3 tools/triage/build_html.py YYYY-MM-DD_YYYY-MM-DD
# → tools/triage/<start>_to_<end>.html

# Active-mode: PRs commented in the range, created earlier.
python3 tools/triage/fetch_active.py YYYY-MM-DD_YYYY-MM-DD
python3 tools/triage/build_active.py YYYY-MM-DD_YYYY-MM-DD
# → tools/triage/<start>_to_<end>_active.html

# Issues: new-in-range plus earlier issues with activity in range.
python3 tools/triage/fetch_issues.py YYYY-MM-DD_YYYY-MM-DD
python3 tools/triage/build_issues.py YYYY-MM-DD_YYYY-MM-DD
# → tools/triage/<start>_to_<end>_issues.html
```

Typically run all three for the same range. The active PR view excludes
same-range creations by default (override with
`--exclude-created START_END` or `--exclude-created none`).

## Where AI judgment is load-bearing

Most of the classifier is mechanical, but a few things benefit from human
(or AI-assisted) review:

1. **PR cat 3 — AI use policy violations.** The classifier flags some
   patterns automatically (the `Fixes #ISSUE_NUMBER` placeholder, etc.),
   but judgment-call cases need to be added by hand. Read the
   [AI use policy](https://zulip.readthedocs.io/en/latest/contributing/contributing.html#ai-use-policy-and-guidelines)
   and add an entry to `AI_POLICY_VIOLATION` in `tools/triage/build_html.py`
   with a short reason (the violation type, not the policy text — reviewers
   know the policy).

2. **PR spot-checks of cat 1 and cat 4.** A PR the classifier puts in cat 1
   ("ready to review") may have substantive problems the heuristics miss —
   commits with unrelated changes, hallucinated API references, etc. Inspect
   the commits with `gh api /repos/zulip/zulip/pulls/{N}/commits` (or read
   the cached `cache/commits_{N}.json`) and the diff before recommending
   review.

3. **Issue cats 3-5 — comment classification.** Default routing puts every
   non-bot, non-maintainer, non-`@zulipbot` comment into cat 3 (OP) or cat 4
   (user), so cat 4 fills with informal claims, contributor coordination,
   and contributor technical chatter unless filtered. Read the in-range
   comments and add to `BORING_COMMENT_IDS` (suppress) or
   `CONTRIBUTOR_HELP_REQUEST_IDS` (route to cat 5) in
   `tools/triage/local_overrides.py` (gitignored — create the file if it
   doesn't exist). Without this pass, cats 3 and 4 are noisy and the report
   loses most of its value.

## Reviewer suggestions

Each PR row in the created-mode and active-mode reports has a
"Suggested" column with up to 3 alternate reviewers, derived from
the area-maintainer snapshot in `tools/triage/areas/`. The
already-engaged reviewer (last reviewer / next on) is excluded, so
the column shows fresh names a maintainer might tag in. Numbers in
parentheses are the candidate's per-area scores; the confidence tag
(high / medium / low) reflects how strong the primary-area signal
is.

If suggestions look stale or wrong, the snapshot needs refreshing —
see `tools/triage/areas/README.md` for the (slow) regeneration
pipeline.

## Things to keep in mind

- Drafts and `[WIP]`-titled PRs are excluded entirely. PRs labeled
  `integration review`, `chat.zulip.org review`, or `completion candidate`
  go to dedicated collapsed sections (cats 8, 9, 10).
- Cache lives at `tools/triage/cache/` and is gitignored. `fetch.py` is
  idempotent on cached data; reruns won't re-download.
- The HTML output is also gitignored — share it by attaching the file or
  hosting it yourself, not by committing.
