#!/usr/bin/env python3
"""Fetch all GitHub data needed for a triage range, into cache/.

Usage: python3 tools/triage/fetch.py YYYY-MM-DD_YYYY-MM-DD

Steps:
  1. GitHub search for open PRs created in the range.
  2. For each PR, fetch detail + comments + reviews + check-runs.
  3. For each PR, fetch its commit list.
  4. For each issue referenced in a PR body, fetch the issue.

All responses are cached on disk; reruns only fetch what's missing.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "cache")
REPO = "zulip/zulip"
os.makedirs(CACHE, exist_ok=True)


def _load_token() -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return token.strip()
    path = os.path.expanduser("~/.github_token")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    sys.exit("error: set GITHUB_TOKEN or write a token to ~/.github_token")


HDR = {
    "Authorization": f"Bearer {_load_token()}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "zulip-triage",
}


def get(url: str) -> Any:
    """Some endpoints return lists, others dicts; let the caller decide."""
    req = urllib.request.Request(url, headers=HDR)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and attempt < 2:
                time.sleep(2**attempt)
                continue
            raise
    raise RuntimeError("unreachable")


def cached(key: str, url: str) -> Any:
    p = os.path.join(CACHE, f"{key}.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    data = get(url)
    with open(p, "w") as f:
        json.dump(data, f)
    return data


def search_prs(range_key: str) -> dict[str, Any]:
    start, end = range_key.split("_")
    q = f"repo:{REPO} is:pr is:open created:{start}..{end}"
    url = f"https://api.github.com/search/issues?q={urllib.parse.quote(q)}&per_page=100"
    return cached(f"search_{range_key}", url)


def fetch_pr_bundle(num: int) -> int:
    pr = cached(f"pr_{num}", f"https://api.github.com/repos/{REPO}/pulls/{num}")
    cached(
        f"issue_comments_{num}",
        f"https://api.github.com/repos/{REPO}/issues/{num}/comments?per_page=100",
    )
    cached(
        f"reviews_{num}", f"https://api.github.com/repos/{REPO}/pulls/{num}/reviews?per_page=100"
    )
    cached(
        f"review_comments_{num}",
        f"https://api.github.com/repos/{REPO}/pulls/{num}/comments?per_page=100",
    )
    cached(
        f"check_runs_{num}",
        f"https://api.github.com/repos/{REPO}/commits/{pr['head']['sha']}/check-runs?per_page=100",
    )
    cached(
        f"commits_{num}", f"https://api.github.com/repos/{REPO}/pulls/{num}/commits?per_page=100"
    )
    return num


def _read_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)


def assemble_combined(range_key: str, numbers: list[int]) -> dict[str, Any]:
    """build_html.py reads combined_<range>.json — assemble it from per-PR pieces."""
    out: dict[str, Any] = {}
    for n in numbers:
        out[str(n)] = {
            "pr": _read_json(f"{CACHE}/pr_{n}.json"),
            "issue_comments": _read_json(f"{CACHE}/issue_comments_{n}.json"),
            "reviews": _read_json(f"{CACHE}/reviews_{n}.json"),
            "review_comments": _read_json(f"{CACHE}/review_comments_{n}.json"),
            "check_runs": _read_json(f"{CACHE}/check_runs_{n}.json"),
        }
    with open(f"{CACHE}/combined_{range_key}.json", "w") as f:
        json.dump(out, f)
    return out


def referenced_issue_numbers(combined: dict[str, Any]) -> set[int]:
    refs: set[int] = set()
    for blob in combined.values():
        body = blob["pr"]["body"] or ""
        body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
        for m in re.finditer(r"(?:#|issues/)(\d+)", body):
            refs.add(int(m.group(1)))
    return refs


def fetch_issue(n: int) -> int:
    p = f"{CACHE}/issue_{n}.json"
    if os.path.exists(p):
        return n
    try:
        data: dict[str, Any] = get(f"https://api.github.com/repos/{REPO}/issues/{n}")
    except urllib.error.HTTPError as e:
        data = {"error": e.code, "number": n}
    with open(p, "w") as f:
        json.dump(data, f)
    return n


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: fetch.py YYYY-MM-DD_YYYY-MM-DD")
    range_key = sys.argv[1]

    print(f"[1/4] Searching open PRs in {range_key}")
    search = search_prs(range_key)
    numbers = [it["number"] for it in search["items"]]
    print(f"      found {len(numbers)} PRs")

    print("[2/4] Fetching PR details (in parallel)")
    with ThreadPoolExecutor(max_workers=8) as ex:
        for f in as_completed([ex.submit(fetch_pr_bundle, n) for n in numbers]):
            f.result()

    print(f"[3/4] Assembling combined_{range_key}.json")
    combined = assemble_combined(range_key, numbers)

    print("[4/4] Fetching referenced issues")
    issues = referenced_issue_numbers(combined)
    new_issues = [n for n in sorted(issues) if not os.path.exists(f"{CACHE}/issue_{n}.json")]
    print(
        f"      fetching {len(new_issues)} new issues (already cached: {len(issues) - len(new_issues)})"
    )
    with ThreadPoolExecutor(max_workers=8) as ex:
        for f in as_completed([ex.submit(fetch_issue, n) for n in new_issues]):
            f.result()

    print(f"\nDone. Run: python3 tools/triage/build_html.py {range_key}")


if __name__ == "__main__":
    main()
