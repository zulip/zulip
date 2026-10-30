"""Suggest reviewers for a PR based on its canonical-area coverage.

Reads the committed snapshot CSVs (`area_maintainers.csv`,
`area_aliases.csv`) and a PR's cached commit list, and produces a top-3
ranked list with per-area scores for the maintainer triaging the report
to glance at.

Algorithm (hybrid D + E from the design discussion):

  1. Extract canonical areas the PR's commits touch (count per area).
  2. Identify the primary area (most commits).
  3. If the primary area covers >60% of the PR's prefix-bearing commits,
     surface its top 3 maintainers ("primary-area only" mode).
  4. Otherwise score each candidate as
       primary_pts + 0.3 * Σ secondary_pts
     and surface the top 3 ("weighted" mode).
  5. Drop the PR author. Don't drop existing commenters/reviewers — they
     might still get formally assigned later.
  6. Drop ≤1-pt entries if any maintainer in the suggestions has higher.
  7. Tag confidence: high if the primary area's leader has ≥10 pts,
     medium if 3–9, low if <3 or only meta-areas matched.
"""

import csv
import os
import re
from collections import Counter, defaultdict
from typing import Any, NamedTuple

DIR = os.path.dirname(os.path.abspath(__file__))


PREFIX_RE = re.compile(
    r"^([a-z][a-zA-Z0-9_/.,()\s-]*?(?::\s+[a-z][a-zA-Z0-9_/.,()\s-]*?)*?):\s+[A-Z]"
)


def _normalize(prefix: str) -> str:
    p = prefix.lower()
    p = re.sub(r"[-_]", " ", p)
    p = re.sub(r"\s+", " ", p)
    return p.strip()


def _extract_prefix(subject: str) -> str | None:
    m = PREFIX_RE.match(subject)
    if not m:
        return None
    return _normalize(m.group(1))


class Suggestion(NamedTuple):
    login: str
    score: float
    breakdown: dict[str, int]  # area → maintainer's points in that area
    is_maintainer: bool


# Per-area row in the CSV: (login, total_points, is_maintainer).
AreaRow = tuple[str, int, bool]


def load_alias_lookup() -> dict[str, str]:
    """raw_prefix → canonical_area, from area_aliases.csv."""
    lookup: dict[str, str] = {}
    with open(os.path.join(DIR, "area_aliases.csv")) as f:
        for row in csv.DictReader(f):
            lookup[row["raw_prefix"]] = row["area"]
    return lookup


def load_maintainers_per_area() -> dict[str, list[AreaRow]]:
    """canonical_area → [(login, total_points, is_maintainer), ...] sorted desc."""
    out: dict[str, list[AreaRow]] = defaultdict(list)
    with open(os.path.join(DIR, "area_maintainers.csv")) as f:
        for row in csv.DictReader(f):
            is_maint = row["in_maintainers_list"] == "yes"
            out[row["area"]].append((row["github_login"], int(row["total_points"]), is_maint))
    for rows in out.values():
        rows.sort(key=lambda x: -x[1])
    return dict(out)


def commit_areas(commits: list[dict[str, Any]], alias_lookup: dict[str, str]) -> Counter[str]:
    """Counter of canonical_area → number of PR commits with that prefix."""
    areas: Counter[str] = Counter()
    for c in commits:
        msg = c.get("commit", {}).get("message", "") or ""
        subj = msg.split("\n", 1)[0]
        raw = _extract_prefix(subj)
        if raw is None:
            continue
        canon = alias_lookup.get(raw)
        if canon is None:
            # Try the first colon-separated segment (e.g., `tests: foo.py` → `tests`).
            first = raw.split(":", 1)[0].strip()
            canon = alias_lookup.get(first)
        if canon:
            areas[canon] += 1
    return areas


def confidence_label(primary_area: str, maintainers_per_area: dict[str, list[AreaRow]]) -> str:
    rows = maintainers_per_area.get(primary_area, [])
    leader_score = rows[0][1] if rows else 0
    if leader_score >= 10:
        return "high"
    if leader_score >= 3:
        return "medium"
    return "low"


def _drop_outshadowed_low(suggestions: list[Suggestion]) -> list[Suggestion]:
    """Drop ≤1-pt entries if any maintainer in the list has a higher score."""
    max_maint = max((s.score for s in suggestions if s.is_maintainer), default=0.0)
    return [s for s in suggestions if not (s.score <= 1 and max_maint > s.score)]


def suggest_reviewers(
    commits: list[dict[str, Any]],
    author_login: str,
    alias_lookup: dict[str, str],
    maintainers_per_area: dict[str, list[AreaRow]],
    exclude: frozenset[str] = frozenset(),
) -> tuple[list[Suggestion], str]:
    """Return (top-3 suggestions, confidence label).

    `exclude` is a set of lowercased logins to omit from candidates
    (typically the PR's already-engaged reviewer(s)).

    Returns ([], "none") if the PR has no canonical-area coverage.
    """
    areas = commit_areas(commits, alias_lookup)
    if not areas:
        return [], "none"

    total = sum(areas.values())
    primary_area, primary_count = areas.most_common(1)[0]
    confidence = confidence_label(primary_area, maintainers_per_area)
    author_lower = author_login.lower()
    skip = {author_lower, *exclude}

    # Primary-area-only mode if the PR is dominated by one area.
    if primary_count / total > 0.6:
        suggestions: list[Suggestion] = []
        for login, pts, is_maint in maintainers_per_area.get(primary_area, []):
            if login in skip:
                continue
            suggestions.append(Suggestion(login, float(pts), {primary_area: pts}, is_maint))
            if len(suggestions) == 3:
                break
        return _drop_outshadowed_low(suggestions), confidence

    # Weighted mode: primary 1.0, secondaries 0.3.
    scores: dict[str, float] = defaultdict(float)
    breakdowns: dict[str, dict[str, int]] = defaultdict(dict)
    is_maintainer: dict[str, bool] = {}
    for area in areas:
        weight = 1.0 if area == primary_area else 0.3
        for login, pts, is_maint in maintainers_per_area.get(area, []):
            if login in skip:
                continue
            scores[login] += weight * pts
            breakdowns[login][area] = pts
            is_maintainer[login] = is_maint

    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))[:3]
    suggestions = [
        Suggestion(login, score, breakdowns[login], is_maintainer.get(login, False))
        for login, score in ranked
    ]
    return _drop_outshadowed_low(suggestions), confidence
