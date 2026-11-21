#!/usr/bin/env python3
"""Build the issue triage HTML page.

Reads `issues_<range>.json` (produced by `fetch_issues.py`) and writes
`<start>_to_<end>_issues.html`. Splits issues into eight buckets, in
priority order (first match wins):

  Actionable, open by default:
    1. New issues filed by non-maintainers
    2. New issues from maintainers with possibly unclear next steps
    3. Issues with in-range comments from the issue author
    4. Issues with in-range comments from users (non-contributor)
    5. Issues with in-range contributor comments asking maintainers
       for help

  Non-actionable, collapsed by default:
    6. Other new issues filed by maintainers (for completeness)
    7. Updated issues (filed earlier, no maintainer comment, no
       actionable comment in range)
    8. Issues with maintainer replies and no actionable signal in range

Cat 3-5 routing requires comment-content judgment. Programmatic filters
drop zulipbot comments, all maintainer comments, and any body
containing `@zulipbot` (catches claim/abandon/unclaim variants and
informal bot-tagged claim requests). Beyond those, a triage pass
populates two `set[int]`s in a gitignored `local_overrides.py` next to
this file: `BORING_COMMENT_IDS` (suppress) and
`CONTRIBUTOR_HELP_REQUEST_IDS` (route into cat 5). The file is
optional; build_issues.py falls back to empty defaults.
"""

import html
import json
import os
import sys
from typing import Any

# When run as `python3 tools/triage/build_issues.py`, the script's directory
# is on sys.path[0], so plain `from build_html import ...` resolves correctly.
from build_html import (  # type: ignore[import-not-found]  # sibling-script import
    BASE,
    CACHE,
    MAINTAINERS,
    PAGE_CSS,
    parse_dt,
    relative_days,
)

# Labels that indicate the next step is intentionally somewhere else.
NEEDS_LABELS = {
    "needs discussion",
    "needs more work",
    "needs product spec",
    "needs reproducer",
    "needs tech spec",
}

# Comment IDs to fully suppress (informal claim requests, contributor
# technical chatter, contributor coordination, contributor clarification
# questions on issues not labeled `help wanted`, etc.). Populated by the
# triage pass.
BORING_COMMENT_IDS: set[int] = set()

# Comment IDs from contributors specifically asking maintainers for help
# (route into cat 5 rather than cat 4). Populated by the triage pass.
CONTRIBUTOR_HELP_REQUEST_IDS: set[int] = set()

# Each triage pass produces a list of comment IDs to suppress and a list
# of contributor-help-request IDs. To avoid checking date-specific data
# into the repo, these live in a gitignored `local_overrides.py` next to
# this file. The file should define `BORING_COMMENT_IDS` and
# `CONTRIBUTOR_HELP_REQUEST_IDS` as `set[int]`; an absent file is fine.
try:
    import local_overrides  # type: ignore[import-not-found] # optional gitignored sibling-script import

    BORING_COMMENT_IDS |= local_overrides.BORING_COMMENT_IDS
    CONTRIBUTOR_HELP_REQUEST_IDS |= local_overrides.CONTRIBUTOR_HELP_REQUEST_IDS
except ImportError:
    pass


CAT_TITLES = {
    1: "1. New issues filed by non-maintainers",
    2: "2. New issues from maintainers with possibly unclear next steps",
    3: "3. Issues with in-range comments from the issue author",
    4: "4. Issues with in-range comments from users",
    5: "5. Issues with in-range contributor questions for maintainers",
    6: "6. Other new issues filed by maintainers (for completeness)",
    7: "7. Updated issues (filed earlier, recent activity)",
    8: "8. Issues with maintainer replies (informational)",
}

OPEN_BY_DEFAULT = {1, 2, 3, 4, 5}


def load_comments(num: int) -> list[dict[str, Any]]:
    path = os.path.join(CACHE, f"issue_comments_{num}.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def comment_kind(c: dict[str, Any], issue: dict[str, Any]) -> str | None:
    """Classify a single comment for routing.

    Returns one of: "op", "user", "contributor_help", or None (filtered).
    Maintainer comments are always filtered, even when the OP is a
    maintainer commenting on their own issue.
    """
    author = c.get("user", {}).get("login", "").lower()
    if author == "zulipbot":
        return None
    if author in MAINTAINERS:
        return None
    # Anyone addressing the bot is doing bot-coordination, not user
    # feedback — this catches @zulipbot claim/abandon/unclaim variants
    # as well as informal "@zulipbot please assign me" comments.
    if "@zulipbot" in c.get("body", "").lower():
        return None
    if c["id"] in BORING_COMMENT_IDS:
        return None
    if c["id"] in CONTRIBUTOR_HELP_REQUEST_IDS:
        return "contributor_help"
    if author == issue["user"]["login"].lower():
        return "op"
    return "user"


def has_any_maintainer_comment(comments: list[dict[str, Any]]) -> bool:
    return any(c.get("user", {}).get("login", "").lower() in MAINTAINERS for c in comments)


def classify_new_issue(issue: dict[str, Any]) -> int:
    """Return cat 1, 2, or 6 for an issue created in the range, before
    accounting for in-range comments."""
    if issue["user"]["login"].lower() not in MAINTAINERS:
        return 1
    label_names = {label["name"] for label in issue["labels"]}
    if (
        "help wanted" in label_names
        or "blocked" in label_names
        or label_names & NEEDS_LABELS
        or issue.get("assignees")
    ):
        return 6
    return 2


def route_issue(
    issue: dict[str, Any], range_start: str, range_end: str
) -> tuple[int, list[dict[str, Any]]]:
    """Pick the highest-priority category for an issue, plus the list of
    in-range non-filtered comments to surface on the row."""
    comments = load_comments(issue["number"])
    in_range_kinds: dict[str, list[dict[str, Any]]] = {"op": [], "user": [], "contributor_help": []}
    for c in comments:
        when = c["created_at"][:10]
        if not (range_start <= when <= range_end):
            continue
        kind = comment_kind(c, issue)
        if kind is None:
            continue
        in_range_kinds[kind].append(c)

    created = issue["created_at"][:10]
    is_new = range_start <= created <= range_end
    has_maint = has_any_maintainer_comment(comments)
    op_is_maint = issue["user"]["login"].lower() in MAINTAINERS

    # Cat 1: new, by non-maintainer, no maintainer comment yet.
    if is_new and not op_is_maint and not has_maint:
        return 1, in_range_kinds["op"]
    # Cat 2: new, by maintainer, no clear next-step label, no other
    # maintainer comments.
    if (
        is_new
        and classify_new_issue(issue) == 2
        and not _has_other_maintainer_comment(comments, issue)
    ):
        return 2, in_range_kinds["op"]
    # Cats 3, 4, 5: actionable comments in range, in priority order.
    if in_range_kinds["op"]:
        return 3, in_range_kinds["op"]
    if in_range_kinds["user"]:
        return 4, in_range_kinds["user"]
    if in_range_kinds["contributor_help"]:
        return 5, in_range_kinds["contributor_help"]
    # Cat 6: new, by maintainer, with clear next-step label (no actionable
    # comments).
    if is_new and classify_new_issue(issue) == 6:
        return 6, []
    # Cat 7: older, no maintainer comment, no actionable comment.
    if not has_maint:
        return 7, []
    # Cat 8: has maintainer comment, no other actionable signal.
    return 8, []


def _has_other_maintainer_comment(comments: list[dict[str, Any]], issue: dict[str, Any]) -> bool:
    """True if any maintainer other than the OP commented on the issue."""
    op = issue["user"]["login"].lower()
    return any(
        c.get("user", {}).get("login", "").lower() in MAINTAINERS
        and c.get("user", {}).get("login", "").lower() != op
        for c in comments
    )


def labels_html(issue: dict[str, Any]) -> str:
    if not issue["labels"]:
        return '<span class="muted">—</span>'
    parts = []
    for label in issue["labels"]:
        name = html.escape(label["name"])
        color = label.get("color", "ccc")
        parts.append(f'<span class="label" style="background:#{color}">{name}</span>')
    return " ".join(parts)


def assignees_html(issue: dict[str, Any]) -> str:
    if not issue.get("assignees"):
        return '<span class="muted">—</span>'
    return ", ".join(html.escape(a["login"]) for a in issue["assignees"])


def comment_link(c: dict[str, Any]) -> str:
    author = html.escape(c["user"]["login"])
    when = html.escape(relative_days(parse_dt(c["created_at"])))
    url = html.escape(c["html_url"])
    return f'<a class="comment-link" href="{url}" target="_blank">{author} · {when}</a>'


def issue_row(issue: dict[str, Any], surfaced_comments: list[dict[str, Any]]) -> str:
    num = issue["number"]
    title = html.escape(issue["title"])
    url = html.escape(issue["html_url"])
    author = html.escape(issue["user"]["login"])
    is_maint = issue["user"]["login"].lower() in MAINTAINERS
    author_cls = "maint" if is_maint else "nonmaint"
    age = html.escape(relative_days(parse_dt(issue["created_at"])))
    last_activity = html.escape(relative_days(parse_dt(issue["updated_at"])))
    comment_links = ""
    if surfaced_comments:
        surfaced_comments = sorted(surfaced_comments, key=lambda c: c["created_at"])
        links = ", ".join(comment_link(c) for c in surfaced_comments)
        comment_links = f'<div class="comment-links">{links}</div>'
    return (
        f"<tr>"
        f'<td><span class="pr-num"><a href="{url}" target="_blank">#{num}</a></span>'
        f'<span class="title">{title}</span>{comment_links}</td>'
        f'<td class="author"><span class="{author_cls}">{author}</span></td>'
        f"<td>{labels_html(issue)}</td>"
        f"<td>{assignees_html(issue)}</td>"
        f'<td class="age">{age}</td>'
        f'<td class="age">{last_activity}</td>'
        f"</tr>"
    )


def render_html(
    rows_by_cat: dict[int, list[tuple[dict[str, Any], list[dict[str, Any]]]]],
    page_title: str,
    h1_text: str,
    summary_html: str,
    output_path: str,
) -> None:
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{html.escape(page_title)}</title>",
        "<style>",
        PAGE_CSS,
        # Issue rows have a labels column; give label badges a compact style.
        ".label { display: inline-block; padding: 1px 6px; border-radius: 3px; "
        "font-size: 0.85em; color: #222; margin: 1px 2px; }",
        ".comment-links { margin-top: 3px; font-size: 0.9em; color: #57606a; }",
        ".comment-link { font-weight: 500; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(h1_text)}</h1>",
        '<div class="summary">',
        summary_html,
        "<ul>",
    ]
    parts += [
        f"<li>{html.escape(title)} — <strong>{len(rows_by_cat[c])}</strong></li>"
        for c, title in CAT_TITLES.items()
    ]
    parts += ["</ul>", "</div>"]

    for cat, cat_title in CAT_TITLES.items():
        rows = rows_by_cat[cat]
        is_open = cat in OPEN_BY_DEFAULT
        parts.append(f"<details{' open' if is_open else ''}>")
        parts.append(
            f'<summary>{html.escape(cat_title)}<span class="count">({len(rows)})</span></summary>'
        )
        if not rows:
            parts.append('<div class="empty">None.</div>')
        else:
            parts.append('<div class="table-wrap"><table><thead><tr>')
            parts.append("<th>Issue</th><th>Author</th><th>Labels</th>")
            parts.append("<th>Assignees</th><th>Age</th><th>Last activity</th>")
            parts.append("</tr></thead><tbody>")
            for issue, surfaced in rows:
                parts.append(issue_row(issue, surfaced))
            parts.append("</tbody></table></div>")
        parts.append("</details>")

    parts += ["</body>", "</html>"]
    with open(output_path, "w") as f:
        f.write("\n".join(parts))
    print("wrote", output_path)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: build_issues.py YYYY-MM-DD_YYYY-MM-DD")
    range_key = sys.argv[1]
    range_start, range_end = range_key.split("_")
    range_label = f"{range_start}_to_{range_end}"

    with open(f"{CACHE}/issues_{range_key}.json") as f:
        issues: dict[str, dict[str, Any]] = json.load(f)

    rows_by_cat: dict[int, list[tuple[dict[str, Any], list[dict[str, Any]]]]] = {
        c: [] for c in CAT_TITLES
    }
    for issue in issues.values():
        cat, surfaced = route_issue(issue, range_start, range_end)
        rows_by_cat[cat].append((issue, surfaced))

    for rows in rows_by_cat.values():
        rows.sort(key=lambda pair: -pair[0]["number"])

    actionable = sum(len(rows_by_cat[c]) for c in (1, 2, 3, 4, 5))
    non_actionable = sum(len(rows_by_cat[c]) for c in (6, 7, 8))
    summary_html = (
        f"<p>Date range: <strong>{range_start} .. {range_end}</strong>. "
        f"Filter: open issues with most recent activity in range. "
        f"Total issues shown: <strong>{actionable + non_actionable}</strong> "
        f"(actionable: {actionable}, informational: {non_actionable}).</p>"
    )

    render_html(
        rows_by_cat=rows_by_cat,
        page_title=f"Zulip issue triage: {range_start} to {range_end}",
        h1_text=f"Zulip issue triage — {range_start} to {range_end}",
        summary_html=summary_html,
        output_path=os.path.join(BASE, f"{range_label}_issues.html"),
    )


if __name__ == "__main__":
    main()
