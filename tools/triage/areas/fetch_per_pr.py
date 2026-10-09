#!/usr/bin/env python3
"""For each merged or open PR in year_prs.json, fetch commits + issue
comments + reviews into the cache. Skips closed-unmerged PRs.

Rate-limit aware: pauses when GitHub's hourly budget is nearly exhausted.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

# Add tools/triage to sys.path so we can import its sibling fetch.py.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fetch import CACHE, HDR, REPO  # type: ignore[import-not-found]  # sibling-script import

SCRATCH = os.path.dirname(os.path.abspath(__file__))


def get_with_rate_limit(url: str) -> tuple[Any, dict[str, str]]:
    """Like fetch.get but also returns response headers (for rate-limit info)."""
    req = urllib.request.Request(url, headers=HDR)
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r), dict(r.headers)
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and attempt < 4:
                time.sleep(2**attempt)
                continue
            if e.code == 403 and attempt < 4:
                # Rate limit hit; honour Retry-After or sleep 60s.
                retry_after = int(e.headers.get("Retry-After", 60))
                print(f"  403 — sleeping {retry_after}s")
                time.sleep(retry_after)
                continue
            raise
    raise RuntimeError("unreachable")


def cached_with_throttle(key: str, url: str) -> Any:
    """cached() but checks remaining rate budget after each uncached fetch."""
    p = os.path.join(CACHE, f"{key}.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    data, headers = get_with_rate_limit(url)
    with open(p, "w") as f:
        json.dump(data, f)
    remaining = int(headers.get("x-ratelimit-remaining", "9999"))
    if remaining < 100:
        reset = int(headers.get("x-ratelimit-reset", "0"))
        wait = max(0, reset - int(time.time()) + 5)
        print(f"  rate limit low ({remaining}); sleeping {wait}s until reset")
        time.sleep(wait)
    return data


def fetch_one(num: int) -> tuple[int, bool]:
    """Returns (num, success). Fetches commits, issue_comments, reviews."""
    try:
        cached_with_throttle(
            f"commits_{num}",
            f"https://api.github.com/repos/{REPO}/pulls/{num}/commits?per_page=100",
        )
        cached_with_throttle(
            f"issue_comments_{num}",
            f"https://api.github.com/repos/{REPO}/issues/{num}/comments?per_page=100",
        )
        cached_with_throttle(
            f"reviews_{num}",
            f"https://api.github.com/repos/{REPO}/pulls/{num}/reviews?per_page=100",
        )
        return num, True
    except Exception as e:
        print(f"  PR #{num}: {e}")
        return num, False


def main() -> None:
    with open(os.path.join(SCRATCH, "year_prs.json")) as f:
        prs = json.load(f)

    # Filter: keep open + merged, skip closed-unmerged.
    keep = []
    for pr in prs:
        merged = pr.get("pull_request", {}).get("merged_at") is not None
        if pr["state"] == "open" or merged:
            keep.append(pr["number"])
    print(f"Filtered: {len(keep)} merged-or-open of {len(prs)} total")

    # Sort newest first so we process recent PRs early.
    keep.sort(reverse=True)

    # Skip ones already fully cached.
    needed = []
    for num in keep:
        all_cached = all(
            os.path.exists(os.path.join(CACHE, f"{kind}_{num}.json"))
            for kind in ("commits", "issue_comments", "reviews")
        )
        if not all_cached:
            needed.append(num)
    print(f"To fetch: {len(needed)} PRs ({len(keep) - len(needed)} fully cached)")

    if not needed:
        print("All cached.")
        return

    successes = 0
    failures = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(fetch_one, n) for n in needed]
        for i, fut in enumerate(as_completed(futures), 1):
            num, ok = fut.result()
            if ok:
                successes += 1
            else:
                failures += 1
            if i % 100 == 0:
                print(f"  progress: {i}/{len(needed)} (success={successes} fail={failures})")
    print(f"\nDone: {successes} succeeded, {failures} failed")


if __name__ == "__main__":
    main()
