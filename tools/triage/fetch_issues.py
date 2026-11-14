#!/usr/bin/env python3
"""Fetch open issues updated in a date range, into cache/.

Usage: python3 tools/triage/fetch_issues.py YYYY-MM-DD_YYYY-MM-DD

The search uses `updated:START..END`, which catches both newly-filed
issues in the range (their `updated_at` equals their `created_at`)
and older issues with their most recent activity in the range.
`build_issues.py` then splits them into "new in range" and "updated
in range" buckets.

Issue volume in `zulip/zulip` is low enough that one combined report
is more useful than separate files.
"""

import json
import os
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

# When run as `python3 tools/triage/fetch_issues.py`, the script's directory
# is on sys.path[0], so plain `from fetch import ...` resolves correctly.
from fetch import CACHE, REPO, cached  # type: ignore[import-not-found]  # sibling-script import


def search_issues(range_key: str) -> dict[str, Any]:
    """Search open issues whose most recent activity is in the range.

    Paginates up to GitHub's 1000-result cap; warns if exceeded.
    """
    start, end = range_key.split("_")
    q = f"repo:{REPO} is:issue is:open updated:{start}..{end}"
    items: list[dict[str, Any]] = []
    total_count = 0
    incomplete = False
    for page in range(1, 11):
        url = (
            f"https://api.github.com/search/issues"
            f"?q={urllib.parse.quote(q)}&per_page=100&page={page}"
        )
        data = cached(f"search_issues_{range_key}_p{page}", url)
        total_count = data.get("total_count", 0)
        incomplete = incomplete or data.get("incomplete_results", False)
        page_items = data.get("items", [])
        items.extend(page_items)
        if len(page_items) < 100:
            break
    return {"total_count": total_count, "incomplete_results": incomplete, "items": items}


def fetch_issue_comments(num: int) -> int:
    cached(
        f"issue_comments_{num}",
        f"https://api.github.com/repos/{REPO}/issues/{num}/comments?per_page=100",
    )
    return num


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: fetch_issues.py YYYY-MM-DD_YYYY-MM-DD")
    range_key = sys.argv[1]
    start, end = range_key.split("_")

    print(f"[1/2] Searching open issues updated in {start}..{end}")
    search = search_issues(range_key)
    items = search["items"]
    print(f"      found {len(items)} issues")
    if search.get("incomplete_results"):
        print(
            "      WARNING: GitHub search returned incomplete results "
            "(>1000 hits). Some issues may be missing.",
            file=sys.stderr,
        )

    print("[2/2] Fetching issue comments (in parallel)")
    numbers = [it["number"] for it in items]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for fut in as_completed([ex.submit(fetch_issue_comments, n) for n in numbers]):
            fut.result()

    out = {str(it["number"]): it for it in items}
    out_path = os.path.join(CACHE, f"issues_{range_key}.json")
    with open(out_path, "w") as f:
        json.dump(out, f)

    print(f"\nDone. Run: python3 tools/triage/build_issues.py {range_key}")


if __name__ == "__main__":
    main()
