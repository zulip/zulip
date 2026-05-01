---
name: pr-triage
description: "Run the PR triage tool against a date range and review the output. Use when the user asks for triage of recent PRs in zulip/zulip. The tool itself is at tools/triage/."
argument-hint: "[date-range like 2026-04-01_2026-04-15]"
---

# PR triage

The tool lives at `tools/triage/` — see its `README.md` for full docs. This
skill is a thin pointer for AI assistants helping with a triage pass.

## Two views, each a two-step run

```bash
# Created-mode: PRs created in the range.
python3 tools/triage/fetch.py YYYY-MM-DD_YYYY-MM-DD
python3 tools/triage/build_html.py YYYY-MM-DD_YYYY-MM-DD
# → tools/triage/<start>_to_<end>.html

# Active-mode: PRs commented in the range, created earlier.
python3 tools/triage/fetch_active.py YYYY-MM-DD_YYYY-MM-DD
python3 tools/triage/build_active.py YYYY-MM-DD_YYYY-MM-DD
# → tools/triage/<start>_to_<end>_active.html
```

Typically run both for the same range. The active view excludes
same-range creations by default (override with
`--exclude-created START_END` or `--exclude-created none`).

## Where AI judgment is load-bearing

Most of the classifier is mechanical, but two things benefit from human (or
AI-assisted) review:

1. **Cat 3 — AI use policy violations.** The classifier flags some patterns
   automatically (the `Fixes #ISSUE_NUMBER` placeholder, etc.), but
   judgment-call cases need to be added by hand. Read the
   [AI use policy](https://zulip.readthedocs.io/en/latest/contributing/contributing.html#ai-use-policy-and-guidelines)
   and add an entry to `AI_POLICY_VIOLATION` in `tools/triage/build_html.py`
   with a short reason (the violation type, not the policy text — reviewers
   know the policy).

2. **Spot-checks of cat 1 and cat 4.** A PR the classifier puts in cat 1
   ("ready to review") may have substantive problems the heuristics miss —
   commits with unrelated changes, hallucinated API references, etc. Inspect
   the commits with `gh api /repos/zulip/zulip/pulls/{N}/commits` (or read
   the cached `cache/commits_{N}.json`) and the diff before recommending
   review.

## Things to keep in mind

- Drafts and `[WIP]`-titled PRs are excluded entirely. PRs labeled
  `integration review`, `chat.zulip.org review`, or `completion candidate`
  go to dedicated collapsed sections (cats 8, 9, 10).
- Cache lives at `tools/triage/cache/` and is gitignored. `fetch.py` is
  idempotent on cached data; reruns won't re-download.
- The HTML output is also gitignored — share it by attaching the file or
  hosting it yourself, not by committing.
