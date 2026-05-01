#!/usr/bin/env python3
"""Build the recently-active triage HTML page.

Reads `combined_active_<range>.json` (produced by `fetch_active.py`) and
writes `<start>_to_<end>_active.html`. Uses the same classifier and
rendering as the created-mode tool.
"""

import os
import sys
from typing import Any

# Same trick as fetch_active.py — tools/triage is on sys.path[0].
from build_html import (  # type: ignore[import-not-found]  # sibling-script import
    BASE,
    CACHE,
    CAT_TITLES,
    _skip_links,
    build_pr_row,
    classify_pr,
    load_issue_titles,
    render_html,
)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: build_active.py YYYY-MM-DD_YYYY-MM-DD")
    range_key = sys.argv[1]
    range_start, range_end = range_key.split("_")
    range_label = f"{range_start}_to_{range_end}"

    import json

    with open(f"{CACHE}/combined_active_{range_key}.json") as f:
        combined = json.load(f)
    issue_titles = load_issue_titles()

    rows_by_cat: dict[int, list[dict[str, Any]]] = {c: [] for c in CAT_TITLES}
    drafts_skipped: list[int] = []
    wip_skipped: list[int] = []
    for num_str, blob in combined.items():
        n = int(num_str)
        if blob["pr"].get("draft"):
            drafts_skipped.append(n)
            continue
        title_lower = blob["pr"]["title"].lower()
        if "[wip]" in title_lower or "wip:" in title_lower:
            wip_skipped.append(n)
            continue
        cat, reason = classify_pr(n, blob)
        row = build_pr_row(num_str, blob, issue_titles)
        row["reason"] = reason
        rows_by_cat[cat].append(row)

    for rows in rows_by_cat.values():
        rows.sort(key=lambda r: -int(r["num"]))

    summary_html = (
        f"<p>Activity range: <strong>{range_start} .. {range_end}</strong> "
        f"(PRs whose most recent meaningful comment falls in this window). "
        f"Filter: open, non-draft, not WIP. "
        f"Total PRs shown: <strong>{sum(len(v) for v in rows_by_cat.values())}</strong>"
        f" (skipped {len(drafts_skipped)} draft"
        f"{_skip_links(drafts_skipped)}, {len(wip_skipped)} WIP"
        f"{_skip_links(wip_skipped)}).</p>"
    )

    render_html(
        rows_by_cat=rows_by_cat,
        page_title=f"Zulip PR Triage (active): {range_start} to {range_end}",
        h1_text=f"Zulip PR Triage — recently-active PRs, {range_start} to {range_end}",
        summary_html=summary_html,
        output_path=os.path.join(BASE, f"{range_label}_active.html"),
    )


if __name__ == "__main__":
    main()
