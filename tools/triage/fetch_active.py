#!/usr/bin/env python3
"""Fetch data for the recently-active triage view.

Selects PRs whose most recent meaningful comment falls within a date range,
regardless of when the PR was created. By default excludes PRs created in
that same range (they're covered by the created-mode tool); pass
`--exclude-created START_END` to override or `--exclude-created none` to
keep them in.

Usage:
  python3 tools/triage/fetch_active.py YYYY-MM-DD_YYYY-MM-DD
  python3 tools/triage/fetch_active.py YYYY-MM-DD_YYYY-MM-DD --exclude-created none
  python3 tools/triage/fetch_active.py YYYY-MM-DD_YYYY-MM-DD --exclude-created 2026-04-01_2026-04-30

The same per-PR cache is shared with `fetch.py`, so reruns are essentially
free.
"""

import argparse
import json
import os
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

# When run as `python3 tools/triage/fetch_active.py`, the script's directory
# is on sys.path[0], so plain `from fetch import ...` resolves correctly.
from build_html import is_bot  # type: ignore[import-not-found]  # sibling-script import
from fetch import (  # type: ignore[import-not-found]  # sibling-script import
    CACHE,
    REPO,
    _read_json,
    cached,
    fetch_issue,
    fetch_pr_bundle,
    referenced_issue_numbers,
)


def search_active_prs(range_key: str) -> dict[str, Any]:
    """Search for PRs updated since the start of the range.

    GitHub's `updated:` qualifier filters on the PR's *current* `updated_at`,
    not "had any update in window," so a tight range like `START..END` only
    matches PRs that have been dormant since `END` — the exact opposite of
    what we want. We use `>=START` to catch every PR that's been touched
    since `start`, and filter client-side by most-recent-meaningful-comment.

    Paginates up to GitHub's 1000-result cap; warns if exceeded.
    """
    start, _end = range_key.split("_")
    q = f"repo:{REPO} is:pr is:open updated:>={start}"
    items: list[dict[str, Any]] = []
    total_count = 0
    incomplete = False
    for page in range(1, 11):  # GitHub search caps at 1000 results = 10 pages of 100
        url = (
            f"https://api.github.com/search/issues"
            f"?q={urllib.parse.quote(q)}&per_page=100&page={page}"
        )
        data = cached(f"search_active_{range_key}_p{page}", url)
        total_count = data.get("total_count", 0)
        incomplete = incomplete or data.get("incomplete_results", False)
        page_items = data.get("items", [])
        items.extend(page_items)
        if len(page_items) < 100:
            break
    return {"total_count": total_count, "incomplete_results": incomplete, "items": items}


def most_recent_meaningful_comment(blob: dict[str, Any]) -> str | None:
    """Return the timestamp of the most recent non-bot comment/review/review-comment.

    "Meaningful" = author isn't a bot (per `is_bot`). Includes top-level
    issue comments, formal review submissions, and inline review comments.
    """
    timestamps: list[str] = [
        r["submitted_at"]
        for r in blob["reviews"]
        if not is_bot(r["user"]["login"]) and r.get("submitted_at")
    ]
    timestamps.extend(
        c["created_at"] for c in blob["issue_comments"] if not is_bot(c["user"]["login"])
    )
    timestamps.extend(
        c["created_at"] for c in blob["review_comments"] if not is_bot(c["user"]["login"])
    )
    return max(timestamps) if timestamps else None


def in_range(ts: str | None, start: str, end: str) -> bool:
    """Inclusive on both ends; `end` covers the whole day via < end + "T24"."""
    if ts is None:
        return False
    return start <= ts[:10] <= end


def assemble_combined_active(range_key: str, numbers: list[int]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for n in numbers:
        out[str(n)] = {
            "pr": _read_json(f"{CACHE}/pr_{n}.json"),
            "issue_comments": _read_json(f"{CACHE}/issue_comments_{n}.json"),
            "reviews": _read_json(f"{CACHE}/reviews_{n}.json"),
            "review_comments": _read_json(f"{CACHE}/review_comments_{n}.json"),
            "check_runs": _read_json(f"{CACHE}/check_runs_{n}.json"),
            "files": _read_json(f"{CACHE}/files_{n}.json"),
        }
    with open(f"{CACHE}/combined_active_{range_key}.json", "w") as f:
        json.dump(out, f)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("range", help="YYYY-MM-DD_YYYY-MM-DD")
    p.add_argument(
        "--exclude-created",
        default="SAME",
        help="Skip PRs created in this range. Default: same as `range`. "
        "Pass 'none' to keep all PRs.",
    )
    args = p.parse_args()
    range_key = args.range
    start, end = range_key.split("_")

    if args.exclude_created.lower() == "none":
        exclude_start: str | None = None
        exclude_end: str | None = None
    elif args.exclude_created == "SAME":
        exclude_start, exclude_end = start, end
    else:
        exclude_start, exclude_end = args.exclude_created.split("_")

    print(f"[1/4] Searching open PRs updated since {start}")
    search = search_active_prs(range_key)
    candidates = [it["number"] for it in search["items"]]
    print(f"      found {len(candidates)} candidate PRs")
    if search.get("incomplete_results"):
        print(
            "      WARNING: GitHub search returned incomplete results "
            "(>1000 hits). Some PRs may be missing.",
            file=sys.stderr,
        )

    print("[2/4] Fetching PR details (in parallel)")
    with ThreadPoolExecutor(max_workers=8) as ex:
        for f in as_completed([ex.submit(fetch_pr_bundle, n) for n in candidates]):
            f.result()

    print("[3/4] Filtering: created-date and most-recent-comment-in-range")
    final: list[int] = []
    excluded_by_created = 0
    excluded_by_no_comment_in_range = 0
    for n in candidates:
        pr = _read_json(f"{CACHE}/pr_{n}.json")
        created = pr["created_at"][:10]
        if exclude_start and exclude_end and exclude_start <= created <= exclude_end:
            excluded_by_created += 1
            continue
        blob = {
            "pr": pr,
            "issue_comments": _read_json(f"{CACHE}/issue_comments_{n}.json"),
            "reviews": _read_json(f"{CACHE}/reviews_{n}.json"),
            "review_comments": _read_json(f"{CACHE}/review_comments_{n}.json"),
        }
        ts = most_recent_meaningful_comment(blob)
        if not in_range(ts, start, end):
            excluded_by_no_comment_in_range += 1
            continue
        final.append(n)
    print(
        f"      kept {len(final)}, dropped {excluded_by_created} (created in exclusion range), "
        f"{excluded_by_no_comment_in_range} (most-recent comment outside [{start}, {end}])"
    )

    print(f"      assembling combined_active_{range_key}.json")
    combined = assemble_combined_active(range_key, final)

    print("[4/4] Fetching referenced issues")
    issues = referenced_issue_numbers(combined)
    new_issues = [n for n in sorted(issues) if not os.path.exists(f"{CACHE}/issue_{n}.json")]
    print(
        f"      fetching {len(new_issues)} new issues (already cached: {len(issues) - len(new_issues)})"
    )
    with ThreadPoolExecutor(max_workers=8) as ex:
        for f in as_completed([ex.submit(fetch_issue, n) for n in new_issues]):
            f.result()

    print(f"\nDone. Run: python3 tools/triage/build_active.py {range_key}")


if __name__ == "__main__":
    main()
