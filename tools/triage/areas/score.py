#!/usr/bin/env python3
"""Score (canonical_area, person) pairs from the year's PRs.

Per-PR scoring:
  - Determine the set of canonical areas the PR's commits touch.
  - For each canonical area in the set:
    - PR author gets +1 in that area.
    - Each non-bot commenter (issue comments + reviews) who isn't the
      author gets +1, EXCEPT timabbott and alya — they only score on
      PRs they authored.
  - Then for each meta-area in the area's meta list, score the same
    set of people (this is intentional double-counting; tracked via a
    `direct_pr_count` vs `meta_pr_count` split per (area, person)).

Output:
  area_maintainers.csv  - top 3 per area (more in case of ties), with
                          maintainer-list flag and meta-derived note.
  area_aliases.csv      - canonical_area, raw_prefix, count.
"""

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from typing import Any

# Add tools/triage to sys.path so we can import its sibling fetch.py.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from areas import (  # type: ignore[import-not-found]  # same-dir import
    AREAS,
    EXCLUDED,
    build_alias_lookup,
)
from fetch import CACHE  # type: ignore[import-not-found]  # sibling-script import

SCRATCH = os.path.dirname(os.path.abspath(__file__))

# Tim and Alya only score on their own PRs.
COMMENT_EXEMPT = {"timabbott", "alya"}

# When determining "dominant non-executive ownership," ignore these four —
# they comment broadly so a 10+ score from them isn't a clean ownership
# signal. Used by the "drop ≤3 if dominant ≥10" filter below.
BROAD_REVIEWERS = {"alya", "timabbott", "alexmv", "gnprice"}

# Bot accounts to exclude from output entirely. Anything with a `[bot]`
# suffix is also dropped via the suffix check.
BOT_LOGINS = {"zulipbot"}


def is_bot(login: str) -> bool:
    return login.endswith("[bot]") or login in BOT_LOGINS


def load_maintainers() -> set[str]:
    with open(os.path.join(os.path.dirname(__file__), "..", "maintainers.json")) as f:
        data = json.load(f)
    return {k.lower() for k in data if not k.startswith("_")}


def normalize(prefix: str) -> str:
    p = prefix.lower()
    p = re.sub(r"[-_]", " ", p)
    p = re.sub(r"\s+", " ", p)
    return p.strip()


PREFIX_RE = re.compile(
    r"^([a-z][a-zA-Z0-9_/.,()\s-]*?(?::\s+[a-z][a-zA-Z0-9_/.,()\s-]*?)*?):\s+[A-Z]"
)


def extract_prefix(subject: str) -> str | None:
    m = PREFIX_RE.match(subject)
    if not m:
        return None
    return normalize(m.group(1))


def canonical_for(raw_prefix: str, alias_lookup: dict[str, str]) -> str | None:
    """Map a raw normalized prefix to a canonical area, or None if excluded.

    Multi-colon prefixes collapse to first segment when no full match exists,
    so `tests: foo.test.cjs` → "tests" (then excluded).
    """
    if raw_prefix in alias_lookup:
        canonical = alias_lookup[raw_prefix]
    else:
        # Try the first colon-separated segment.
        first = raw_prefix.split(":", 1)[0].strip()
        if first in alias_lookup:
            canonical = alias_lookup[first]
        else:
            # Default: canonical is the raw prefix itself.
            canonical = first if ":" in raw_prefix else raw_prefix
    if canonical in EXCLUDED:
        return None
    return canonical


def get_pr_areas(
    num: int, alias_lookup: dict[str, str]
) -> tuple[set[str], dict[str, set[str]], Counter[str]]:
    """Returns:
    - direct: set of canonical areas the PR's commits touch
    - meta_provenance: {meta_area: {sub_area1, sub_area2, ...}} showing which
      direct sub-areas contributed to each meta-area
    - raw_counts: Counter of normalized raw prefixes seen on this PR (for aliases CSV)
    """
    path = os.path.join(CACHE, f"commits_{num}.json")
    if not os.path.exists(path):
        return set(), {}, Counter()
    with open(path) as f:
        commits = json.load(f)
    if not isinstance(commits, list):
        return set(), {}, Counter()

    direct: set[str] = set()
    raw_counts: Counter[str] = Counter()
    for c in commits:
        msg = c.get("commit", {}).get("message", "") or ""
        subj = msg.split("\n", 1)[0]
        raw = extract_prefix(subj)
        if raw is None:
            continue
        raw_counts[raw] += 1
        canon = canonical_for(raw, alias_lookup)
        if canon is None:
            continue
        direct.add(canon)

    meta_provenance: dict[str, set[str]] = defaultdict(set)
    for sub in direct:
        for meta in AREAS.get(sub, {}).get("meta", []):
            if meta in EXCLUDED:
                continue
            meta_provenance[meta].add(sub)

    return direct, dict(meta_provenance), raw_counts


def collect_commenters(num: int) -> set[str]:
    """Union of issue commenters and review submitters (excluding bots)."""
    commenters: set[str] = set()
    for kind in ("issue_comments", "reviews"):
        path = os.path.join(CACHE, f"{kind}_{num}.json")
        if not os.path.exists(path):
            continue
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, list):
            continue
        for entry in data:
            login = entry.get("user", {}).get("login", "").lower()
            if not login or is_bot(login):
                continue
            commenters.add(login)
    return commenters


def main() -> None:
    alias_lookup = build_alias_lookup()
    maintainers = load_maintainers()

    with open(os.path.join(SCRATCH, "year_prs.json")) as f:
        all_prs = json.load(f)

    keep = []
    for pr in all_prs:
        merged = pr.get("pull_request", {}).get("merged_at") is not None
        if pr["state"] == "open" or merged:
            keep.append(pr)

    print(f"Scoring across {len(keep)} merged-or-open PRs")

    # (canonical_area, person) → set of PR numbers (direct evidence)
    direct_points: dict[tuple[str, str], set[int]] = defaultdict(set)
    # (meta_area, person) → {sub_area: set of PR numbers}
    meta_points: dict[tuple[str, str], dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    # canonical_area → Counter of raw prefixes
    aliases_seen: dict[str, Counter[str]] = defaultdict(Counter)

    skipped_no_commits = 0
    for pr in keep:
        num = pr["number"]
        author = pr["user"]["login"].lower()
        if is_bot(author):
            continue
        direct, meta_provenance, raw_counts = get_pr_areas(num, alias_lookup)
        if not direct and not raw_counts:
            skipped_no_commits += 1
            continue
        for raw, n in raw_counts.items():
            canon = canonical_for(raw, alias_lookup)
            if canon is not None:
                aliases_seen[canon][raw] += n
        commenters = collect_commenters(num)

        for area in direct:
            direct_points[(area, author)].add(num)
            for c in commenters:
                if c == author:
                    continue
                if c in COMMENT_EXEMPT:
                    continue
                direct_points[(area, c)].add(num)

        for meta_area, sub_set in meta_provenance.items():
            for sub in sub_set:
                meta_points[(meta_area, author)][sub].add(num)
                for c in commenters:
                    if c == author:
                        continue
                    if c in COMMENT_EXEMPT:
                        continue
                    meta_points[(meta_area, c)][sub].add(num)

    print(f"Skipped {skipped_no_commits} PRs with no commits cached or no parseable prefixes")

    # Build per-area output. An area is anything that appears as a key in
    # direct_points OR meta_points.
    all_areas: set[str] = set()
    for area, _ in direct_points:
        all_areas.add(area)
    for area, _ in meta_points:
        all_areas.add(area)

    rows = []
    for area in sorted(all_areas):
        # Build per-person totals: total_pts = direct_pts ∪ meta_pts (set union to avoid double-counting same PR)
        person_totals: dict[str, dict[str, Any]] = {}
        # Collect everyone with any points in this area.
        people_here: set[str] = {p for (a, p) in direct_points if a == area}
        people_here |= {p for (a, p) in meta_points if a == area}

        for p in people_here:
            direct_prs: set[int] = direct_points.get((area, p), set())
            meta_breakdown: dict[str, set[int]] = meta_points.get((area, p), {})
            meta_prs: set[int] = set()
            for sub, prs in meta_breakdown.items():
                meta_prs |= prs
            total_prs = direct_prs | meta_prs
            if not total_prs:
                continue
            person_totals[p] = {
                "total": len(total_prs),
                "direct": len(direct_prs),
                "meta_only": len(meta_prs - direct_prs),
                "breakdown": {sub: len(prs) for sub, prs in meta_breakdown.items()},
            }

        # Inclusion rule:
        #   - Any maintainer with ≥1 point: include.
        #   - Non-maintainer: include iff total ≥ 2.
        included = []
        for p, info in person_totals.items():
            if p in maintainers:
                included.append((p, info))
            elif info["total"] >= 2:
                included.append((p, info))

        if not included:
            continue

        # Sort by total desc, then alpha for stability.
        included.sort(key=lambda pi: (-pi[1]["total"], pi[0]))

        # Skip areas with no real signal (leader at 1 pt).
        if included[0][1]["total"] < 2:
            continue

        # If a non-broad-reviewer has ≥10 points, they're a clear primary
        # maintainer for the area. In that case, drop low-signal entries
        # (≤3 points) from the output — they'd just be noise next to a
        # dominant owner.
        dominant_non_broad = any(
            p not in BROAD_REVIEWERS and info["total"] >= 10 for p, info in included
        )
        if dominant_non_broad:
            included = [(p, info) for p, info in included if info["total"] > 3]

        # Drop ≤2 pt entries from alya, timabbott, gnprice.
        included = [
            (p, info)
            for p, info in included
            if not (p in ("alya", "timabbott", "gnprice") and info["total"] <= 2)
        ]

        # Top 3, with ties; drop 3rd if it's just 1 point.
        keep_n = 3
        if len(included) >= 3 and included[2][1]["total"] == 1:
            keep_n = 2
        kept = included[:keep_n]
        # Extend with ties only if the last-included score is >= 2.
        if kept and kept[-1][1]["total"] >= 2 and len(included) > keep_n:
            last_score = kept[-1][1]["total"]
            for pi in included[keep_n:]:
                if pi[1]["total"] == last_score:
                    kept.append(pi)
                else:
                    break

        for p, info in kept:
            breakdown_str = ",".join(
                f"{sub}:{n}" for sub, n in sorted(info["breakdown"].items(), key=lambda x: -x[1])
            )
            rows.append(
                {
                    "area": area,
                    "github_login": p,
                    "total_points": info["total"],
                    "direct_points": info["direct"],
                    "meta_only_points": info["meta_only"],
                    "meta_breakdown": breakdown_str,
                    "in_maintainers_list": "yes" if p in maintainers else "no",
                }
            )

    # Write area_maintainers.csv
    out1 = os.path.join(SCRATCH, "area_maintainers.csv")
    with open(out1, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "area",
                "github_login",
                "total_points",
                "direct_points",
                "meta_only_points",
                "meta_breakdown",
                "in_maintainers_list",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {out1}")

    # Write area_aliases.csv
    alias_rows = []
    for area, raw_counter in aliases_seen.items():
        for raw, n in sorted(raw_counter.items(), key=lambda x: -x[1]):
            alias_rows.append({"area": area, "raw_prefix": raw, "prefix_count": n})
    out2 = os.path.join(SCRATCH, "area_aliases.csv")
    with open(out2, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["area", "raw_prefix", "prefix_count"])
        w.writeheader()
        w.writerows(alias_rows)
    print(f"Wrote {len(alias_rows)} rows to {out2}")

    print(f"\nUnique areas in output: {len({r['area'] for r in rows})}")


if __name__ == "__main__":
    main()
