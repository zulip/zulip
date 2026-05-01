# PR triage tool

Generates categorized HTML reports of open PRs in `zulip/zulip`, so a
maintainer can quickly see what needs review, what's stuck, and what's
already been handled. Two views:

- **Created-mode** (`fetch.py` + `build_html.py`): PRs created in a date
  range. Good for "what came in this week."
- **Active-mode** (`fetch_active.py` + `build_active.py`): PRs whose most
  recent meaningful comment falls in a date range, regardless of when the
  PR was created. Good for "what got attention this week, and is anything
  stuck."

You'll typically run both for the same range. The active view excludes
PRs created in the same range by default to avoid duplication with the
created view.

## Setup

You need a GitHub token with read access to public repos (a fine-grained PAT
with `public_repo` scope is enough). Either:

- Export it: `export GITHUB_TOKEN=ghp_…`, or
- Save it to `~/.github_token`.

## Usage

Each view is two steps: a fetch (hits the GitHub API, cached) and a build
(reads the cache, writes HTML).

```bash
# Created-mode: PRs created in the range.
python3 tools/triage/fetch.py 2026-04-01_2026-04-15
python3 tools/triage/build_html.py 2026-04-01_2026-04-15
# → tools/triage/2026-04-01_to_2026-04-15.html

# Active-mode: PRs commented in the range (and created earlier).
python3 tools/triage/fetch_active.py 2026-04-01_2026-04-15
python3 tools/triage/build_active.py 2026-04-01_2026-04-15
# → tools/triage/2026-04-01_to_2026-04-15_active.html
```

`fetch_active.py` accepts `--exclude-created START_END` to override the
default exclusion of same-range creations. Pass `--exclude-created none`
to keep all PRs.

The cache (shared across modes — per-PR data is identical) and generated
HTML are gitignored; nothing about a triage run is committed.

## Categories

Drafts and `[WIP]`-titled PRs are excluded entirely.

| Cat | Title                                           | What it means                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| --- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Awaiting first maintainer review                | No maintainer has commented or reviewed yet, no clear guideline issues. The "ready to look at" pile.                                                                                                                                                                                                                                                                                                                                                                           |
| 2   | Next step is on us (>3 days idle)               | Maintainer reviewed; author has since responded; CI clean; no merge conflicts; >3 days since author's last action. Delegations count: when a maintainer's last comment @-mentions another maintainer, the ball stays on us.                                                                                                                                                                                                                                                    |
| 3   | AI use policy violations                        | PRs that violate [the AI use policy](https://zulip.readthedocs.io/en/latest/contributing/contributing.html#ai-use-policy-and-guidelines) — unedited LLM scaffolding in the description, admissions that tests weren't run, Copilot work merged in without disclosure, etc. Detection requires content judgment, so entries are added by hand to `AI_POLICY_VIOLATION` in `build_html.py`.                                                                                      |
| 4   | Other guideline issues                          | Programmatic checks: CI failing, "Fixes:" line is descriptive text rather than an issue link, missing self-review checklist from the PR template, missing screenshots when visual files (CSS, HBS, image assets) were changed, merge commits in the PR, AI-workflow commit subjects (`Initial plan`, `copilot/...`), fix-up commits that should be squashed, commits without the `subsystem:` prefix, and intermediate commits that fail CI (when HEAD CI is otherwise clean). |
| 5   | Idle, awaiting contributor (≥10 days)           | Maintainer requested changes; contributor hasn't acted in ≥10 days. Candidates for a nudge or close.                                                                                                                                                                                                                                                                                                                                                                           |
| 6   | Core team PRs without `maintainer review` label | Maintainer-authored PRs that need another maintainer to review and apply the label.                                                                                                                                                                                                                                                                                                                                                                                            |
| 7   | Other (informational)                           | Recent activity, ball on contributor (<10 days), or maintainer PRs already in review. Collapsed by default.                                                                                                                                                                                                                                                                                                                                                                    |

A PR lands in only one category; cat 3 takes precedence over cat 4.

In active-mode, "meaningful comment" = any non-bot author's top-level
comment, formal review submission, or inline review comment. The
classifier is the same as created-mode; cat 1 ("awaiting first review")
will essentially always be empty in active-mode, since a PR can only
enter the active view via a comment in range.

## How it works

`fetch.py` searches `created:START..END`; `fetch_active.py` searches
`updated:>=START` (with pagination up to GitHub's 1000-result cap), then
filters client-side to PRs whose most-recent-meaningful-comment is in
[START, END] and whose `created_at` isn't in the exclusion range.

Per-PR fetching is identical between modes: the PR detail, issue comments,
reviews, review comments, check-runs (HEAD and each non-HEAD commit),
commits, files touched, and referenced-issue bodies. Everything is cached
at `cache/<key>.json`; running both modes for the same range only adds
the (small) active-specific bookkeeping.

`build_html.py` and `build_active.py` both read the cache, run
`classify_pr` on each PR, and call shared `render_html()` to produce the
output. The classifier is a single function with heuristics over
timestamps, labels, CI state, merge conflicts, commit discipline, file
paths, and PR body content.

## Tweaking it

- **Change the maintainer team** → edit `maintainers.json`. Lookups are
  case-insensitive on the GitHub login.
- **Mark a specific PR as an AI policy violation** → add an entry to
  `AI_POLICY_VIOLATION` in `build_html.py` with a short reason describing
  the violation type.
- **Adjust thresholds** → edit `classify_pr` in `build_html.py`. The 3-day
  cat-2 threshold and 10-day cat-5 threshold are simple constants there.
- **Add a new heuristic** → drop it into `classify_pr` (or `analyze_commits`
  for commit-level checks).
- **Add a column** → edit `build_pr_row` (data) and the table-rendering loop
  in `render_html`.

## Caveats

- The "next step on" column uses a small heuristic (most recent maintainer
  @-mention in a non-quoted line, falling back to the most recent maintainer
  reviewer, then to a maintainer assignee). It's right most of the time but
  occasionally picks up a tangential mention.
- Cat 3 detection is conservative: only PRs with explicit, literal evidence
  are flagged. Suspect-but-ambiguous cases land in cat 4.
- The classifier doesn't read the PR diff. It can't catch, for example, "the
  code doesn't actually do what the PR says it does" — that's still a
  human job.
- Active-mode caveat: GitHub's search API caps at 1000 results. For very old
  date ranges or extremely active periods, the candidate set could overflow
  and some PRs could be missed; `fetch_active.py` warns when this happens.
  Short ranges are fine.
