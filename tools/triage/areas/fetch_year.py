#!/usr/bin/env python3
"""Fetch all PRs in a date range, chunked monthly, into the existing cache.

We reuse tools/triage/fetch.py's cached() helper so per-PR data shares
the same cache directory as the triage tool.
"""

import json
import os
import sys
import time
import urllib.parse
from typing import Any

# Add tools/triage to sys.path so we can import its sibling fetch.py.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fetch import CACHE, REPO, cached  # type: ignore[import-not-found]  # sibling-script import

START = "2025-05-05"
END = "2026-05-05"
SCRATCH = os.path.dirname(os.path.abspath(__file__))


def month_chunks(start: str, end: str) -> list[tuple[str, str]]:
    from datetime import date, timedelta

    s = date.fromisoformat(start)
    e = date.fromisoformat(end)
    chunks = []
    cur = s
    while cur <= e:
        # First day of next month
        if cur.month == 12:
            nxt = date(cur.year + 1, 1, 1)
        else:
            nxt = date(cur.year, cur.month + 1, 1)
        chunk_end = min(nxt - timedelta(days=1), e)
        chunks.append((cur.isoformat(), chunk_end.isoformat()))
        cur = nxt
    return chunks


def search_prs_chunk(start: str, end: str) -> list[dict[str, Any]]:
    q = f"repo:{REPO} is:pr created:{start}..{end}"
    items: list[dict[str, Any]] = []
    for page in range(1, 11):
        url = (
            f"https://api.github.com/search/issues"
            f"?q={urllib.parse.quote(q)}&per_page=100&page={page}"
        )
        cache_key = f"year_search_{start}_{end}_p{page}"
        # Search API caps at 30 requests/min — throttle uncached calls.
        if not os.path.exists(os.path.join(CACHE, f"{cache_key}.json")):
            time.sleep(2.5)
        data = cached(cache_key, url)
        page_items = data.get("items", [])
        items.extend(page_items)
        if data.get("incomplete_results"):
            print(f"  WARNING: incomplete results for {start}..{end} p{page}")
        if len(page_items) < 100:
            break
    return items


def main() -> None:
    chunks = month_chunks(START, END)
    print(f"Searching {len(chunks)} monthly chunks: {chunks[0]} .. {chunks[-1]}")
    all_prs: list[dict[str, Any]] = []
    seen_numbers: set[int] = set()
    for s, e in chunks:
        items = search_prs_chunk(s, e)
        new = [it for it in items if it["number"] not in seen_numbers]
        seen_numbers.update(it["number"] for it in items)
        all_prs.extend(new)
        print(f"  {s}..{e}: {len(items)} PRs ({len(new)} new)")
    out_path = os.path.join(SCRATCH, "year_prs.json")
    with open(out_path, "w") as f:
        json.dump(all_prs, f)
    print(f"\nTotal: {len(all_prs)} unique PRs written to {out_path}")


if __name__ == "__main__":
    main()
