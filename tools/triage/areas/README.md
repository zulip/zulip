# Area-maintainer mapping

A pipeline that derives "who maintains what" in `zulip/zulip` from a
year of PR history, for downstream use by the triage tool to suggest
reviewer assignments.

## Output (committed snapshot)

- **`area_maintainers.csv`** — one row per (area, person), top 3 per
  area (with ties; 3rd dropped if it's just 1 pt; areas with no leader
  at ≥2 pts dropped entirely).
- **`area_aliases.csv`** — canonical_area → raw_prefix mapping with
  occurrence counts. Lets a consumer match a raw PR's commit prefixes
  back to canonical areas when tagging.

The committed CSVs are a snapshot from `2025-05-05..2026-05-05`.
Regenerate by running the pipeline below.

`area_maintainers.csv` columns:

| column                | meaning                                                                |
| --------------------- | ---------------------------------------------------------------------- |
| `area`                | canonical area name                                                    |
| `github_login`        | maintainer's GitHub login (lowercase)                                  |
| `total_points`        | unique PRs contributing to (area, person)                              |
| `direct_points`       | PRs whose canonical area was this one directly                         |
| `meta_only_points`    | PRs that only rolled up here from sub-areas                            |
| `meta_breakdown`      | which sub-areas contributed (e.g., `compose typeahead:5,compose ui:2`) |
| `in_maintainers_list` | `yes` if listed in `tools/triage/maintainers.json`, else `no`          |

A row with `in_maintainers_list=no` means a contributor (not on the
maintainer team) who showed enough activity to be a candidate area
expert. Non-maintainers need ≥2 PRs in the area to appear.

## Pipeline

Four scripts, run in order. The first two are slow (~1-2 hours total
on a fresh cache) and rate-limited; the last is instant.

```bash
# 1. Search for PRs in the date window (chunked monthly, throttled)
python3 tools/triage/areas/fetch_year.py

# 2. Pull commits + issue comments + reviews for each PR
#    (~9000 API calls; idempotent, restart any time)
python3 tools/triage/areas/fetch_per_pr.py

# 3. (Optional diagnostic) emit a raw-prefix histogram for tuning
python3 tools/triage/areas/extract_prefixes.py

# 4. Apply the canonical-area map and emit the CSVs
python3 tools/triage/areas/score.py
```

A GitHub token in `~/.github_token` (or `$GITHUB_TOKEN`) is required —
same token the rest of the triage tool uses.

## Tuning the area map

`areas.py` defines canonical areas + their aliases + meta-area rollups.
Edit, then rerun **only** `score.py` (no re-fetch needed).

`extract_prefixes.py` emits a frequency histogram of raw normalized
prefixes seen in the cache, useful for spotting prefixes that should
be aliased into an existing canonical area or split out as their own.

`EXCLUDED` (top of `areas.py`) drops entire canonical areas from
output. Currently: `tests`, `settings`, `realm` — too generic to give
useful maintainership signal.

## Scoring rules (in `score.py`)

For each PR, determine the set of canonical areas its commits touch.
For each area:

- The PR author gets +1 in that area.
- Each non-bot, non-author commenter (issue-comment author or review
  submitter) gets +1.
- **Comment exemption**: `timabbott` and `alya` only score on PRs
  they authored.
- For each meta-area in the canonical area's `meta` list, score the
  same set of people there too. (Intentional double-counting; tracked
  separately so it can be undone later.)

Filtering for the output:

- Maintainers (in `tools/triage/maintainers.json`) appear with any
  number of points. Non-maintainers need ≥2.
- Areas with no leader at ≥2 points are dropped entirely.
- Top 3 per area, extended for ties at the cutoff. 3rd entry dropped
  if it's only 1 point.
- **Dominant-primary rule**: if some non-broad-reviewer (not `alya`,
  `timabbott`, `alexmv`, or `gnprice`) holds ≥10 points in an area,
  every entry at ≤3 points is dropped from that area's rows.
- **Cameo-drop rule**: entries from `alya`, `timabbott`, or `gnprice`
  with ≤2 points are dropped. (`alexmv` exempt — he contributes
  broadly enough that small entries are typically real signal.)

## Notable consolidations baked into `areas.py`

- **`channels`** is the canonical name (renamed from `streams`); all
  `stream*` raw prefixes alias into the channel hierarchy.
- **Help vs. Starlight**: `help:` (Help Center articles, content) and
  `starlight_help:` / `help-beta:` (Starlight framework, build, components)
  are different skill sets — separate canonical areas.
- **X-and-X-importer merged** for each platform: `slack`, `mattermost`,
  `rocketchat`, `microsoft teams` each one canonical area covering both
  the integration code and the importer. All roll up to `import`.
- **`user groups`** is one canonical area; settings (`user group
settings`) and UI (`groups ui`) are kept distinct as sub-areas
  rolling up to it.
- **`production`** meta-area covers `nginx`, `puppet`, `kandra`,
  `letsencrypt`, `setup certbot`, `setup docs`,
  `setup upgrade postgresql`, `restart server`, `provision`,
  `restore backup`, `backup`, `tornado`, `sharding`.
- **`events`** meta-area covers `event queue`, `event types`,
  `server events`, plus per-domain `*_events` (channel/user/message).
- **`sidebar ui`** consolidates bare `sidebar:` / `sidebars:` (separate
  from `left sidebar` / `right sidebar`).
- **`pm list`** renamed to **`dm list`**; `pm`/`private messages`
  variants alias into `direct messages`.

## Caveats

- Date window is hardcoded at the top of `fetch_year.py`; change there
  before rerunning.
- ~5% of PRs may hit GitHub's hourly rate limit during the per-PR
  fetch; `fetch_per_pr.py` is idempotent — rerun after the reset.
- The shared cache lives at `tools/triage/cache/` (gitignored) and is
  reused across the triage tool, so a fresh checkout's first run is
  the slow one.
- Bot accounts (any login ending `[bot]`, plus `zulipbot`) are excluded.

## Files

| File                                                                  | Committed?     |
| --------------------------------------------------------------------- | -------------- |
| `areas.py`                                                            | yes            |
| `fetch_year.py`, `fetch_per_pr.py`, `extract_prefixes.py`, `score.py` | yes            |
| `area_maintainers.csv`, `area_aliases.csv`                            | yes (snapshot) |
| `year_prs.json`, `raw_prefixes.json`                                  | gitignored     |
| `__pycache__/`                                                        | gitignored     |
