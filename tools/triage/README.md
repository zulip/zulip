# PR and issue triage tool

Generates categorized HTML reports of open PRs and issues in
`zulip/zulip`, so a maintainer can quickly see what needs review,
what's stuck, and what's already been handled. Three views:

- **Created-mode PRs** (`fetch.py` + `build_html.py`): PRs created in a
  date range. Good for "what came in this week."
- **Active-mode PRs** (`fetch_active.py` + `build_active.py`): PRs whose
  most recent meaningful comment falls in a date range, regardless of
  when the PR was created. Good for "what got attention this week, and
  is anything stuck."
- **Issues** (`fetch_issues.py` + `build_issues.py`): open issues
  active in a date range, split into actionable and informational
  buckets based on creation date and in-range comment activity.
  Issue volume is low enough that one combined report is more useful
  than separate files.

You'll typically run all three for the same range. The active PR view
excludes PRs created in the same range by default to avoid duplication
with the created view.

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

# Issues: new-in-range plus earlier issues with activity in range.
python3 tools/triage/fetch_issues.py 2026-04-01_2026-04-15
python3 tools/triage/build_issues.py 2026-04-01_2026-04-15
# → tools/triage/2026-04-01_to_2026-04-15_issues.html
```

`fetch_active.py` accepts `--exclude-created START_END` to override the
default exclusion of same-range creations. Pass `--exclude-created none`
to keep all PRs.

The cache (shared across modes — per-PR data is identical) and generated
HTML are gitignored; nothing about a triage run is committed.

## PR categories

Drafts and `[WIP]`-titled PRs are excluded entirely. PRs labeled
`integration review`, `chat.zulip.org review`, or `completion candidate`
are routed to dedicated collapsed sections (cats 8, 9, 10).

| Cat | Title                                           | What it means                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| --- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1   | Awaiting first maintainer review                | No maintainer has commented or reviewed yet, no clear guideline issues. The "ready to look at" pile.                                                                                                                                                                                                                                                                                                                                                                           |
| 2   | Next step is on us (>3 days idle)               | Maintainer reviewed; author has since responded; CI clean; no merge conflicts; >3 days since author's last action. Delegations count: when a maintainer's last comment @-mentions another maintainer, the ball stays on us.                                                                                                                                                                                                                                                    |
| 3   | AI use policy violations                        | PRs that violate [the AI use policy](https://zulip.readthedocs.io/en/latest/contributing/contributing.html#ai-use-policy-and-guidelines) — unedited LLM scaffolding in the description, admissions that tests weren't run, Copilot work merged in without disclosure, etc. Detection requires content judgment, so entries are added by hand to `AI_POLICY_VIOLATION` in `build_html.py`.                                                                                      |
| 4   | Other guideline issues                          | Programmatic checks: CI failing, "Fixes:" line is descriptive text rather than an issue link, missing self-review checklist from the PR template, missing screenshots when visual files (CSS, HBS, image assets) were changed, merge commits in the PR, AI-workflow commit subjects (`Initial plan`, `copilot/...`), fix-up commits that should be squashed, commits without the `subsystem:` prefix, and intermediate commits that fail CI (when HEAD CI is otherwise clean). |
| 5   | Idle, awaiting contributor (≥10 days)           | Maintainer requested changes; contributor hasn't acted in ≥10 days. Candidates for a nudge or close.                                                                                                                                                                                                                                                                                                                                                                           |
| 6   | Core team PRs without `maintainer review` label | Maintainer-authored PRs that need another maintainer to review and apply the label.                                                                                                                                                                                                                                                                                                                                                                                            |
| 7   | Other (informational)                           | Recent activity, ball on contributor (<10 days), or maintainer PRs already in review. Collapsed by default.                                                                                                                                                                                                                                                                                                                                                                    |
| 8   | Integration review                              | PRs labeled `integration review`. Surfaced for awareness only. Collapsed by default.                                                                                                                                                                                                                                                                                                                                                                                           |
| 9   | chat.zulip.org review                           | PRs labeled `chat.zulip.org review`. Surfaced for awareness only. Collapsed by default.                                                                                                                                                                                                                                                                                                                                                                                        |
| 10  | Completion candidate                            | PRs labeled `completion candidate`. They aren't being actively worked on. Collapsed by default.                                                                                                                                                                                                                                                                                                                                                                                |

A PR lands in only one category. The label-based routing (cats 8, 9, 10)
is checked first and trumps the rest. If a PR has more than one routing
label, priority order is `integration review` > `chat.zulip.org review` >
`completion candidate`. Among cats 1–7, cat 3 takes precedence over cat 4.

In active-mode, "meaningful comment" = any non-bot author's top-level
comment, formal review submission, or inline review comment. The
classifier is the same as created-mode; cat 1 ("awaiting first review")
will essentially always be empty in active-mode, since a PR can only
enter the active view via a comment in range.

## Issue categories

The issue view splits into eight buckets, displayed in priority order
(first match wins, top to bottom):

| Cat | Title                                                        | What it means                                                                                                                                     |
| --- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | New issues filed by non-maintainers                          | Created in range by a non-maintainer, no maintainer comments yet. The "needs triage" pile.                                                        |
| 2   | New issues from maintainers with possibly unclear next steps | Maintainer-filed in range, no `help wanted` / `blocked` / `needs ...` label, no assignee, no other maintainer commented yet.                      |
| 3   | Issues with in-range comments from the issue author          | OP added a non-maintainer comment in range that may need a response.                                                                              |
| 4   | Issues with in-range comments from users                     | A non-OP, non-maintainer user added an in-range comment (default classification — most defaults land here).                                       |
| 5   | Issues with in-range contributor questions for maintainers   | A contributor's in-range comment specifically asks a maintainer for help; routed here via `CONTRIBUTOR_HELP_REQUEST_IDS` in `local_overrides.py`. |
| 6   | Other new issues filed by maintainers (for completeness)     | Maintainer-filed in range with the next step intentionally pinned somewhere else. Collapsed by default.                                           |
| 7   | Updated issues (filed earlier, recent activity)              | Older issues with activity in range, no maintainer comments and no actionable in-range comment. Collapsed by default.                             |
| 8   | Issues with maintainer replies (informational)               | Has at least one maintainer comment, and no other actionable signal in range. Collapsed by default.                                               |

`needs ...` covers `needs discussion`, `needs more work`, `needs
product spec`, `needs reproducer`, and `needs tech spec`.

Cats 3–5 require comment-content judgment. The triage pass populates
two sets in a gitignored `tools/triage/local_overrides.py` (date-
specific data doesn't belong in the repo), which `build_issues.py`
imports if present:

- **`BORING_COMMENT_IDS`**: comment IDs to fully suppress (informal
  claim requests, contributor technical chatter, contributor
  coordination, contributor clarification questions on issues not
  marked `help wanted`, etc.).
- **`CONTRIBUTOR_HELP_REQUEST_IDS`**: contributor comments that
  specifically ask a maintainer for help — routed to cat 5 instead
  of cat 4. (Without an entry here, contributor comments default to
  cat 4 unless suppressed.)

Without a `local_overrides.py`, every default-classified comment
lands in cats 3 or 4 and the report is much noisier.

Programmatic filters that always drop comments: zulipbot, comments
by maintainers (whether or not they're the OP), and any body
containing `@zulipbot` (catches claim/abandon/unclaim variants and
informal "@zulipbot please assign me" requests).

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

Each PR row also gets a "Suggested" column listing up to 3 likely
reviewers, derived from the area-maintainer snapshot in `areas/`.
The currently-engaged reviewer (`Last reviewer` / `Next on`) is
excluded from the suggestions, so the column shows _alternate_
reviewers a maintainer might tag in if needed. See `areas/README.md`
for the canonical-area definitions, the scoring rules, and how to
refresh the snapshot.

`fetch_issues.py` searches `is:issue is:open updated:START..END`, writes
`issues_<range>.json` (a separate cache file from the PR data — issues
and PRs are different GitHub objects), and fetches each issue's
comments into `issue_comments_<num>.json` (the same cache key used by
the PR tool, so reruns are free). `build_issues.py` reads both, runs
the comment classifier, and routes each issue into one of the eight
categories above. Routing is strict in-range: only comments with
`created_at` in `[START, END]` drive cats 3–5.

## Tweaking it

- **Change the maintainer team** → edit `maintainers.json`. Lookups are
  case-insensitive on the GitHub login.
- **Mark a specific PR as an AI policy violation** → add an entry to
  `AI_POLICY_VIOLATION` in `build_html.py` with a short reason describing
  the violation type.
- **Filter or reroute an issue comment** → add the comment ID to
  `BORING_COMMENT_IDS` (suppress) or `CONTRIBUTOR_HELP_REQUEST_IDS`
  (route to cat 5) in `tools/triage/local_overrides.py`. Create the
  file if it doesn't exist; it's gitignored.
- **Tune the area map / refresh reviewer-suggestion data** → edit
  `tools/triage/areas/areas.py` (canonical-area map) or rerun the
  scripts under `tools/triage/areas/`. Full instructions in
  `areas/README.md`.
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
