#!/usr/bin/env python3
"""Walk all cached commits and emit a normalized-prefix histogram.

Normalization:
  - Lowercase
  - Replace [-_/] with space (so `compose-box` == `compose box`,
    `tools/triage` stays as `tools/triage` since slash is preserved)
  - Collapse whitespace
  - Strip
For multi-colon prefixes like `tests: foo.test.cjs:`, we keep the full
multi-colon prefix as the raw unit but ALSO emit the leading part
("tests") as a separate "shallow" prefix so we can later decide whether
to roll up.
"""

import json
import os
import re
import sys
from collections import Counter

# Add tools/triage to sys.path so we can import its sibling fetch.py.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fetch import CACHE  # type: ignore[import-not-found]  # sibling-script import

SCRATCH = os.path.dirname(os.path.abspath(__file__))


def normalize(prefix: str) -> str:
    p = prefix.lower()
    p = re.sub(r"[-_]", " ", p)
    p = re.sub(r"\s+", " ", p)
    return p.strip()


PREFIX_RE = re.compile(
    r"^([a-z][a-zA-Z0-9_/.,()\s-]*?(?::\s+[a-z][a-zA-Z0-9_/.,()\s-]*?)*?):\s+[A-Z]"
)


def extract_prefix(subject: str) -> str | None:
    """Match `prefix: Subject` or `prefix1: prefix2: Subject` (capital first letter)."""
    m = PREFIX_RE.match(subject)
    if not m:
        return None
    return normalize(m.group(1))


def main() -> None:
    with open(os.path.join(SCRATCH, "year_prs.json")) as f:
        all_prs = json.load(f)
    keep = set()
    for pr in all_prs:
        merged = pr.get("pull_request", {}).get("merged_at") is not None
        if pr["state"] == "open" or merged:
            keep.add(pr["number"])

    raw_prefixes: Counter[str] = Counter()
    shallow_prefixes: Counter[str] = Counter()
    no_prefix = 0
    cached_count = 0
    missing_count = 0

    for num in keep:
        path = os.path.join(CACHE, f"commits_{num}.json")
        if not os.path.exists(path):
            missing_count += 1
            continue
        cached_count += 1
        with open(path) as f:
            commits = json.load(f)
        if not isinstance(commits, list):
            continue
        for c in commits:
            msg = c.get("commit", {}).get("message", "") or ""
            subject = msg.split("\n", 1)[0]
            prefix = extract_prefix(subject)
            if prefix is None:
                no_prefix += 1
                continue
            raw_prefixes[prefix] += 1
            # Also emit the shallow (first-colon) version
            shallow = prefix.split(":", 1)[0].strip()
            if shallow != prefix:
                shallow_prefixes[shallow] += 1

    print(f"PRs in scope: {len(keep)} (cached: {cached_count}, missing: {missing_count})")
    print(f"Commits with prefix: {sum(raw_prefixes.values())}, no prefix: {no_prefix}")
    print(f"Unique raw prefixes: {len(raw_prefixes)}")
    print()

    # Combine: total occurrences = raw direct + shallow rollup
    combined = Counter(raw_prefixes)
    for shallow, count in shallow_prefixes.items():
        combined[shallow] += count

    print("Top 100 (combining raw + shallow rollups):")
    for p, n in combined.most_common(100):
        direct = raw_prefixes.get(p, 0)
        shallow_n = shallow_prefixes.get(p, 0)
        marker = ""
        if shallow_n:
            marker = f" (direct {direct} + shallow {shallow_n})"
        print(f"  {n:5d}  {p}{marker}")

    out_path = os.path.join(SCRATCH, "raw_prefixes.json")
    with open(out_path, "w") as f:
        json.dump({"raw": raw_prefixes, "shallow": shallow_prefixes, "no_prefix": no_prefix}, f)
    print(f"\nWritten to {out_path}")


if __name__ == "__main__":
    main()
