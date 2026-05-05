#!/usr/bin/env python3
"""Build triage HTML from cached PR data."""

import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "cache")
TODAY = datetime.now(timezone.utc)

# Reviewer suggestions for cat-1 PRs come from the area-mapping snapshot.
sys.path.insert(0, os.path.join(BASE, "areas"))
from suggest import (  # type: ignore[import-not-found]  # sibling-script import
    Suggestion,
    load_alias_lookup,
    load_maintainers_per_area,
    suggest_reviewers,
)


def _default_range_key() -> str:
    """Last full UTC day, formatted as YYYY-MM-DD_YYYY-MM-DD."""
    day = (TODAY - timedelta(days=1)).date().isoformat()
    return f"{day}_{day}"


def _load_maintainers() -> set[str]:
    path = os.path.join(BASE, "maintainers.json")
    with open(path) as f:
        data = json.load(f)
    return {k.lower() for k in data if not k.startswith("_")}


MAINTAINERS = _load_maintainers()

# --- Manual flags / overrides ---
# AI policy violations require content judgment — populate this dict by
# hand for each triage run. Keys are PR numbers; values are short
# violation-type descriptions (not the policy text — reviewers know it).
AI_POLICY_VIOLATION: dict[int, str] = {}


COMMITS_CACHE = CACHE

FIXUP_PATTERNS = [
    r"^fix(es|ed)?(:|\b)\s*(ci|lint|tests?|formatting|typo|whitespace|indent|build|review|comments?)",
    r"^address(ed)?\s+(review|feedback|comments?)",
    r"^(small\s+fix|minor\s+fix|cleanup|small\s+changes?|misc)",
    r"^(rebased?|merge|update|wip)\b",
    r"^fix(es|ed)?\s+\w+\s+(error|issue)s?$",
]


def analyze_commits(
    num: str | int, head_sha: str | None = None, head_ci_failing: bool = False
) -> list[str]:
    """Return list of commit-discipline issue descriptions, or empty list if OK."""
    p = os.path.join(COMMITS_CACHE, f"commits_{num}.json")
    if not os.path.exists(p):
        return []
    with open(p) as f:
        commits = json.load(f)
    if not commits:
        return []
    issues: list[str] = []

    merge_count = sum(1 for c in commits if len(c.get("parents", [])) > 1)
    if merge_count > 0:
        issues.append(f"{merge_count} merge commit{'s' if merge_count > 1 else ''}")

    # Each commit must pass CI independently. Check non-HEAD commits' check
    # runs — but only if HEAD CI is passing, since otherwise the HEAD-CI
    # failure already covers the issue and listing intermediates is redundant.
    if not head_ci_failing:
        n_failing_intermediates = 0
        for c in commits:
            sha = c["sha"]
            if sha == head_sha:
                continue
            ck_path = os.path.join(COMMITS_CACHE, f"check_runs_sha_{sha}.json")
            if not os.path.exists(ck_path):
                continue
            with open(ck_path) as f:
                ck = json.load(f)
            if any(r.get("conclusion") == "failure" for r in ck.get("check_runs", [])):
                n_failing_intermediates += 1
        if n_failing_intermediates:
            if n_failing_intermediates > 1:
                issues.append("intermediate commits fail CI")
            else:
                issues.append("intermediate commit fails CI")

    n_ai_markers = sum(
        1
        for c in commits
        if c["commit"]["message"].split("\n")[0].strip().lower() == "initial plan"
        or re.match(
            r"^(copilot|claude|ai)[/:]",
            c["commit"]["message"].split("\n")[0].strip(),
            re.IGNORECASE,
        )
    )
    if n_ai_markers:
        issues.append("AI-workflow commits")

    n_fixup = 0
    n_no_prefix = 0
    for c in commits:
        subj = c["commit"]["message"].split("\n")[0].strip()
        if len(c.get("parents", [])) > 1:
            continue
        for pat in FIXUP_PATTERNS:
            if re.match(pat, subj, re.IGNORECASE):
                n_fixup += 1
                break
        else:
            # Check subsystem-prefix convention: lowercase[/segment]: Capitalized.
            # Skip the [ai]-prefixed variant.
            if not re.match(r"^[a-z][a-zA-Z0-9_/.,-]*(?:\([^)]+\))?: [A-Z]", subj) and not re.match(
                r"^\[(ai|wip)\]\s+[a-z]", subj
            ):
                n_no_prefix += 1

    if n_fixup >= 1 and len(commits) > 1:
        issues.append(f"{n_fixup} fix-up commit{'s' if n_fixup > 1 else ''}")

    if n_no_prefix >= 2:
        issues.append(f"{n_no_prefix} commits without `subsystem:` prefix")

    return issues


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def is_bot(u: str) -> bool:
    return u.endswith("[bot]") or u.lower() in {"zulipbot", "copilot", "github-actions"}


def classify_pr(num: int, blob: dict[str, Any]) -> tuple[int, str]:
    """Programmatic classification. Returns (category, reason)."""
    pr = blob["pr"]
    author = pr["user"]["login"]
    is_maint_author = author.lower() in MAINTAINERS
    labels = [label["name"] for label in pr["labels"]]
    # Routing labels — these PRs aren't being directly worked through the
    # maintainer review pipeline. Priority: `integration review` >
    # `chat.zulip.org review` > `completion candidate` if multiple are set.
    if "integration review" in labels:
        return 8, ""
    if "chat.zulip.org review" in labels:
        return 9, ""
    if "completion candidate" in labels:
        return 10, ""
    has_maint_review_label = "maintainer review" in labels
    has_conflicts = pr.get("mergeable_state") == "dirty" or "has conflicts" in labels
    ck = blob.get("check_runs", {}).get("check_runs", [])
    ci_failures = sum(1 for c in ck if c.get("conclusion") == "failure")
    ci_failing = ci_failures > 0

    # Collect maint vs author event timestamps (excluding bots).
    maint_ts: list[str] = []
    author_ts: list[str] = []
    last_maint_event: tuple[str, str, str, str] | None = None
    for r in blob["reviews"]:
        u = r["user"]["login"]
        if is_bot(u):
            continue
        ts = r["submitted_at"]
        if u.lower() in MAINTAINERS and u != author:
            maint_ts.append(ts)
            if not last_maint_event or ts > last_maint_event[0]:
                last_maint_event = (ts, u, "review", r.get("body") or "")
        elif u == author:
            author_ts.append(ts)
    for c in blob["issue_comments"]:
        u = c["user"]["login"]
        if is_bot(u):
            continue
        ts = c["created_at"]
        if u.lower() in MAINTAINERS and u != author:
            maint_ts.append(ts)
            if not last_maint_event or ts > last_maint_event[0]:
                last_maint_event = (ts, u, "comment", c["body"])
        elif u == author:
            author_ts.append(ts)
    for c in blob["review_comments"]:
        u = c["user"]["login"]
        if is_bot(u):
            continue
        ts = c["created_at"]
        if u.lower() in MAINTAINERS and u != author:
            maint_ts.append(ts)
            if not last_maint_event or ts > last_maint_event[0]:
                last_maint_event = (ts, u, "review_comment", c["body"])
        elif u == author:
            author_ts.append(ts)

    last_maint = max(maint_ts) if maint_ts else None
    last_author = max(author_ts) if author_ts else pr["created_at"]
    maint_acted = bool(maint_ts)

    # A maintainer's most recent comment that @-mentions another maintainer
    # (e.g., "@alya do you want to test this once?") is a delegation, not a
    # request to the author — the ball stays on the maintainer team even
    # though the maintainer commented after the author.
    maintainer_delegated = False
    if last_maint_event is not None:
        _, mu, _, mbody = last_maint_event
        unquoted = "\n".join(
            line for line in mbody.splitlines() if not line.lstrip().startswith(">")
        )
        for mention in MENTION_RE.findall(unquoted):
            ml = mention.lower()
            if ml in MAINTAINERS and ml != mu.lower() and ml != author.lower():
                maintainer_delegated = True
                break

    if num in AI_POLICY_VIOLATION:
        return 3, AI_POLICY_VIOLATION[num]

    # Cat 6: maintainer author, no 'maintainer review' label
    if is_maint_author and not has_maint_review_label:
        return 6, ""

    # Maintainer PR with the label → informational (recent activity bucket).
    if is_maint_author and has_maint_review_label:
        return 7, "In review pipeline."

    # Contributor PRs from here on.
    last_author_dt = parse_dt(last_author)
    days_idle = (TODAY - last_author_dt).days if last_author_dt else 0

    # Cat 4: clear guideline violations that need author work first.
    body = (pr["body"] or "").strip()
    body_no_comments = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL).strip()
    template_marker_count = body.count("<!--")

    cat4_reasons: list[str] = []
    if ci_failing:
        cat4_reasons.append(f"CI failing ({ci_failures})")
    if template_marker_count >= 5 and len(body_no_comments) < 400:
        cat4_reasons.append("template not filled in")
    # Self-review checklist check: the PR template asks for a checklist.
    # Authors may drop irrelevant items or add their own, but the checklist
    # should be present as a starting point. Accept either an explicit
    # "Self-review" reference (kept from the template) or a substantial
    # checklist (5+ items, suggesting genuine customization).
    checkbox_count = len(re.findall(r"^\s*-\s*\[[ xX]\]", body_no_comments, re.MULTILINE))
    has_self_review_label = bool(re.search(r"self[\s-]?review", body_no_comments, re.IGNORECASE))
    if not has_self_review_label and checkbox_count < 5:
        cat4_reasons.append("missing self-review checklist")
    # Screenshot check: if the PR touches CSS or HBS templates, expect at
    # least one image attachment in the body. Authors who change visual
    # output need to show the result.
    files = blob.get("files", [])
    visual_files = [
        f["filename"]
        for f in files
        if f["filename"].endswith((".css", ".scss", ".hbs"))
        or f["filename"].startswith("web/static/images/")
    ]
    has_screenshot = bool(
        re.search(
            r"<img\s|!\[[^\]]*\]\([^)]+\)|user-(?:images|attachments)\.githubusercontent\.com|github\.com/user-attachments/",
            pr["body"] or "",
        )
    )
    if visual_files and not has_screenshot:
        cat4_reasons.append("no screenshots for visual change")
    # Check for "Fixes:" line that's free-text rather than an issue reference.
    fixes_m = re.search(
        r"^\s*\*?\*?fixes:?\*?\*?\s*([^\n]*)", body_no_comments, re.IGNORECASE | re.MULTILINE
    )
    if fixes_m:
        rest = fixes_m.group(1).strip()
        if rest and not re.match(
            r"^(?:#\d+|https?://github\.com/zulip/zulip/(?:issues|pull)/\d+|part of\s|#?ISSUE)",
            rest,
            re.IGNORECASE,
        ):
            cat4_reasons.append("non-issue `Fixes:` line")
    cat4_reasons.extend(analyze_commits(num, pr["head"]["sha"], head_ci_failing=ci_failing))

    # Only put unreviewed PRs in cat 4. If a maintainer has reviewed, the PR is already
    # in the review process; CI failures/etc become cat 7 (ball on author).
    if cat4_reasons and not maint_acted:
        text = "; ".join(cat4_reasons)
        return 4, text[0].upper() + text[1:] + "."

    # Cat 1: no maintainer engagement yet, no clear violation.
    if not maint_acted:
        if has_conflicts:
            return 1, "Has merge conflicts."
        return 1, ""

    # From here, contributor PR with maintainer engagement.

    # Cat 2: ball on us + >3 days idle + no conflicts + CI not failing.
    # Ball is on us if author acted last OR if the maintainer's last comment
    # delegated to another maintainer (timestamp is recent but content shifts
    # the ball back to the maintainer team).
    ball_on_us = last_maint is None or last_author > last_maint or maintainer_delegated
    # When the maintainer delegated, "days idle" should reflect time since
    # the delegation, not time since the author's older response.
    if maintainer_delegated and last_maint and last_maint > last_author:
        delegated_at: str | None = last_maint
        last_maint_dt = parse_dt(last_maint)
        assert last_maint_dt is not None
        days_idle_for_cat2 = (TODAY - last_maint_dt).days
    else:
        delegated_at = None
        days_idle_for_cat2 = days_idle
    if ball_on_us and days_idle_for_cat2 > 3 and not has_conflicts and not ci_failing:
        if delegated_at and last_maint_event is not None:
            return 2, f"{last_maint_event[1]} delegated ({days_idle_for_cat2}d idle)."
        return 2, f"Author addressed feedback ({days_idle} days idle)."

    # Cat 5: ball on contributor and idle 10+ days since contributor's last action.
    if not ball_on_us and days_idle >= 10:
        return 5, f"Idle {days_idle} days."

    # Cat 7: maintainer engaged but ball on author (recently active), OR cat-2
    # conditions don't all hold (CI fail, conflicts, just-under-threshold idle).
    if not ball_on_us:
        return 7, f"Awaiting author response ({days_idle}d idle)."
    if has_conflicts:
        return 7, "Has merge conflicts."
    if ci_failing:
        return 7, f"CI failing ({ci_failures})."
    return 7, f"Ball on us ({days_idle}d idle)."


def relative_days(dt: datetime | None) -> str:
    if not dt:
        return "—"
    delta = TODAY - dt
    days = delta.days
    if days == 0:
        return "today"
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


ISSUE_REF_KEYWORD = (
    r"(?:fixes(?:\s+part\s+of)?|closes|resolves|fix|close|resolve|makes\s+progress\s+towards?)"
)
ISSUE_NUM_RE = re.compile(
    rf"{ISSUE_REF_KEYWORD}\s*[:\s]\s*"
    r"(?:https?://github\.com/zulip/zulip/issues/)?#?(\d+)",
    re.IGNORECASE,
)
ALL_REF_RE = re.compile(r"(?:#|issues/)(\d+)")


def find_linked_issue(
    pr_body: str | None, issue_titles: dict[int, dict[str, Any]]
) -> tuple[int | None, str | None]:
    """Return (issue_num, issue_title) or (None, None)."""
    if not pr_body:
        return None, None
    body = re.sub(r"<!--.*?-->", "", pr_body, flags=re.DOTALL)
    # Priority pass: explicit Fixes/Closes/Resolves/etc.
    for m in ISSUE_NUM_RE.finditer(body):
        n = int(m.group(1))
        if n in issue_titles and not issue_titles[n].get("is_pr"):
            return n, issue_titles[n]["title"]
    # Fallback: first #N or issues/N reference that resolves to a real issue
    for m in ALL_REF_RE.finditer(body[:1500]):
        n = int(m.group(1))
        if n in issue_titles and not issue_titles[n].get("is_pr"):
            return n, issue_titles[n]["title"]
    return None, None


def all_referenced_issue_numbers(pr_body: str | None) -> list[int]:
    if not pr_body:
        return []
    body = re.sub(r"<!--.*?-->", "", pr_body, flags=re.DOTALL)
    seen: set[int] = set()
    out: list[int] = []
    for m in ALL_REF_RE.finditer(body):
        n = int(m.group(1))
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


CZO_RE = re.compile(r'(https?://chat\.zulip\.org/[^\s\)\]<>"\']+)')


def find_czo_link(
    pr_body: str | None, referenced_issues: list[int], issue_titles: dict[int, dict[str, Any]]
) -> str | None:
    """Extract a chat.zulip.org narrow link.

    Order:
    1. PR body itself.
    2. Body of the primary linked issue (first one that's a real issue).
    3. Body of any other issue referenced from the PR body (in reference order).
    """
    sources = [(pr_body or "", "pr")]
    for n in referenced_issues:
        info = issue_titles.get(n)
        if info and not info.get("is_pr"):
            sources.append((info.get("body") or "", f"issue#{n}"))
    for src, _origin in sources:
        src = re.sub(r"<!--.*?-->", "", src, flags=re.DOTALL)
        m = CZO_RE.search(src)
        if m:
            return m.group(1).rstrip(".,;")
    return None


MENTION_RE = re.compile(r"@([A-Za-z][A-Za-z0-9-]*)")


def find_next_on(blob: dict[str, Any], author: str) -> str | None:
    """Determine who the next step is on for a PR with maintainer engagement.

    Heuristic:
    1. Walk recent events (newest first). If a comment body @-mentions a maintainer
       (author asking a reviewer, or a reviewer delegating to another reviewer),
       that mention is the target.
    2. Otherwise, fall back to the most recent maintainer reviewer.
    3. Otherwise, fall back to a maintainer assignee.
    """
    events: list[tuple[str, str, str]] = []
    for r in blob["reviews"]:
        u = r["user"]["login"]
        if is_bot(u):
            continue
        events.append((r["submitted_at"], u, r.get("body") or ""))
    for c in blob["issue_comments"]:
        u = c["user"]["login"]
        if is_bot(u):
            continue
        events.append((c["created_at"], u, c["body"]))
    for c in blob["review_comments"]:
        u = c["user"]["login"]
        if is_bot(u):
            continue
        events.append((c["created_at"], u, c["body"]))
    events = [e for e in events if e[2] and e[0]]
    events.sort(reverse=True)

    for ts, user, body in events[:8]:
        # Skip quoted lines (lines starting with `>`) so a @-mention inside a quote
        # of someone else's earlier comment isn't treated as a fresh delegation.
        unquoted = "\n".join(
            line for line in body.splitlines() if not line.lstrip().startswith(">")
        )
        for mention in MENTION_RE.findall(unquoted):
            ml = mention.lower()
            if ml in MAINTAINERS and ml != user.lower() and ml != author.lower():
                return mention

    for ts, user, body in events:
        if user.lower() in MAINTAINERS and user != author:
            return user

    for assignee in [a["login"] for a in blob["pr"]["assignees"]]:
        if assignee.lower() in MAINTAINERS:
            return assignee

    return None


def find_last_reviewer(events: list[tuple[str, str, str]], exclude_author: str) -> str | None:
    """events: list of (ts, user, kind). Returns most recent maintainer reviewer's name."""
    for ts, u, kind in sorted(events, reverse=True):
        if u.lower() in MAINTAINERS and not is_bot(u):
            return u
    for ts, u, kind in sorted(events, reverse=True):
        if u != exclude_author and not is_bot(u):
            return u
    return None


def build_pr_row(
    num: str, blob: dict[str, Any], issue_titles: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    pr = blob["pr"]
    author = pr["user"]["login"]
    title = pr["title"]
    pr_url = pr["html_url"]
    created = parse_dt(pr["created_at"])
    age = relative_days(created)

    events: list[tuple[str, str, str]] = [
        (r["submitted_at"], r["user"]["login"], "review") for r in blob["reviews"]
    ]
    events.extend((c["created_at"], c["user"]["login"], "ic") for c in blob["issue_comments"])
    events.extend((c["created_at"], c["user"]["login"], "rc") for c in blob["review_comments"])
    events = [e for e in events if e[0]]

    last_reviewer = find_last_reviewer(events, author)
    next_on = find_next_on(blob, author)
    last_activity_ts = max([e[0] for e in events] + [pr["updated_at"]])
    last_activity = relative_days(parse_dt(last_activity_ts))

    issue_num, issue_title = find_linked_issue(pr["body"], issue_titles)
    referenced = all_referenced_issue_numbers(pr["body"])
    czo = find_czo_link(pr["body"], referenced, issue_titles)

    return {
        "num": num,
        "title": title,
        "pr_url": pr_url,
        "author": author,
        "last_reviewer": last_reviewer,
        "next_on": next_on,
        "issue_num": issue_num,
        "issue_title": issue_title,
        "czo": czo,
        "age": age,
        "last_activity": last_activity,
    }


def issue_link_html(num: int | None, title: str | None) -> str:
    if not num:
        return '<span class="muted">—</span>'
    title_safe = html.escape(title or "?")
    return f'<a href="https://github.com/zulip/zulip/issues/{num}" target="_blank">#{num} {title_safe}</a>'


def czo_link_html(url: str | None) -> str:
    if not url:
        return '<span class="muted">—</span>'
    return f'<a href="{html.escape(url)}" target="_blank">CZO thread</a>'


def _skip_links(nums: list[int]) -> str:
    if not nums:
        return ""
    links = ", ".join(
        f'<a href="https://github.com/zulip/zulip/pull/{n}" target="_blank">#{n}</a>'
        for n in sorted(nums, reverse=True)
    )
    return f": {links}"


def _suggested_reviewers_html(suggestions: list[Suggestion], confidence: str) -> str:
    if not suggestions:
        return ""
    parts = []
    for s in suggestions:
        breakdown = ", ".join(
            f"{a} {p}" for a, p in sorted(s.breakdown.items(), key=lambda x: -x[1])
        )
        login_html = (
            f'<a href="https://github.com/{html.escape(s.login)}" target="_blank">'
            f"{html.escape(s.login)}</a>"
        )
        parts.append(f'<span class="suggested-name">{login_html}</span> ({html.escape(breakdown)})')
    return (
        '<div class="suggested-reviewers">Suggested: '
        + " · ".join(parts)
        + f' <span class="suggested-confidence suggested-{html.escape(confidence)}">{html.escape(confidence)}</span></div>'
    )


def reviewer_html(name: str | None) -> str:
    if not name:
        return '<span class="muted">—</span>'
    is_maint = name.lower() in MAINTAINERS
    cls = "maint" if is_maint else "nonmaint"
    suffix = "" if is_maint else " (non-maintainer)"
    return f'<span class="{cls}">{html.escape(name)}{suffix}</span>'


CAT_TITLES = {
    1: "1. Contributor PRs awaiting first maintainer review",
    2: "2. Contributor PRs where the next step is on us (>3 days idle)",
    3: "3. Contributor PRs that violate the AI use policy",
    4: "4. Contributor PRs with other guideline issues",
    5: "5. Idle PRs awaiting contributor (10+ days since contributor's last action)",
    6: "6. Core team PRs without 'maintainer review' label",
    7: "7. Other open PRs (informational — recent activity, not actionable)",
    8: "8. PRs labeled 'integration review'",
    9: "9. PRs labeled 'chat.zulip.org review'",
    10: "10. PRs labeled 'completion candidate'",
}

PAGE_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 1400px; margin: 1.5em auto; padding: 0 1em; color: #222; }
.table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
h1 { font-size: 1.4em; }
.summary { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 0.5em 1em; margin-bottom: 1.5em; }
.summary ul { margin: 0.3em 0; }
details { border: 1px solid #d0d7de; border-radius: 6px; margin-bottom: 0.8em; padding: 0; }
details > summary { padding: 0.7em 1em; cursor: pointer; font-weight: 600; background: #f6f8fa; border-radius: 6px; }
details[open] > summary { border-bottom: 1px solid #d0d7de; border-radius: 6px 6px 0 0; }
.count { color: #57606a; font-weight: normal; margin-left: 0.5em; }
table { border-collapse: collapse; width: 100%; font-size: 0.92em; min-width: 700px; }
th, td { border-top: 1px solid #d0d7de; padding: 0.55em 0.75em; vertical-align: top; text-align: left; }
th { background: #fff; font-weight: 600; color: #57606a; }
tr:hover td { background: #fafbfc; }
.pr-num { font-weight: 600; white-space: nowrap; }
.muted { color: #8c959f; }
.maint { font-weight: 500; color: #1f883d; }
.nonmaint { color: #57606a; font-style: italic; }
.reason { color: #444; font-size: 0.92em; }
.title { color: #57606a; font-size: 0.9em; display: block; margin-top: 0.2em; }
.empty { padding: 0.8em; color: #8c959f; }
.author { white-space: nowrap; }
.age { white-space: nowrap; color: #57606a; font-size: 0.9em; }
.suggested-reviewers { color: #57606a; font-size: 0.88em; margin-top: 0.3em; }
.suggested-name { font-weight: 500; }
.suggested-confidence { font-style: italic; margin-left: 0.4em; }
.suggested-high { color: #1f883d; }
.suggested-medium { color: #9a6700; }
.suggested-low { color: #8c959f; }
"""


def load_issue_titles() -> dict[int, dict[str, Any]]:
    issue_titles: dict[int, dict[str, Any]] = {}
    for fn in os.listdir(CACHE):
        m = re.fullmatch(r"issue_(\d+)\.json", fn)
        if not m:
            continue
        with open(f"{CACHE}/{fn}") as f:
            data = json.load(f)
        if "error" in data:
            continue
        issue_titles[int(m.group(1))] = {
            "title": data.get("title"),
            "body": data.get("body") or "",
            "is_pr": "pull_request" in data,
        }
    return issue_titles


def render_html(
    rows_by_cat: dict[int, list[dict[str, Any]]],
    page_title: str,
    h1_text: str,
    summary_html: str,
    output_path: str,
) -> None:
    """Build and write the HTML report. Shared between created-mode and active-mode."""
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{html.escape(page_title)}</title>",
        "<style>",
        PAGE_CSS,
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
        is_open = cat not in (7, 8, 9, 10)
        show_next_on = cat in (2, 5, 6, 7)
        parts.append(f"<details{' open' if is_open else ''}>")
        parts.append(
            f'<summary>{html.escape(cat_title)}<span class="count">({len(rows)})</span></summary>'
        )
        if not rows:
            parts.append('<div class="empty">None.</div>')
        else:
            parts.append('<div class="table-wrap"><table>')
            header_cells = ["<th>PR</th>", "<th>Author</th>", "<th>Last reviewer</th>"]
            if show_next_on:
                header_cells.append("<th>Next on</th>")
            header_cells += [
                "<th>Issue</th>",
                "<th>CZO</th>",
                "<th>Age</th>",
                "<th>Last activity</th>",
                "<th>Reason</th>",
            ]
            parts.append("<thead><tr>" + "".join(header_cells) + "</tr></thead><tbody>")
            for r in rows:
                pr_link = f'<a href="{html.escape(r["pr_url"])}" target="_blank">#{r["num"]}</a>'
                title_html = f'<span class="title">{html.escape(r["title"])}</span>'
                suggested_html = _suggested_reviewers_html(
                    r.get("suggestions", []), r.get("suggestion_confidence", "none")
                )
                parts.append("<tr>")
                parts.append(
                    f'<td><span class="pr-num">{pr_link}</span>{title_html}{suggested_html}</td>'
                )
                parts.append(f'<td class="author">{html.escape(r["author"])}</td>')
                parts.append(f"<td>{reviewer_html(r['last_reviewer'])}</td>")
                if show_next_on:
                    parts.append(f"<td>{reviewer_html(r['next_on'])}</td>")
                parts.append(f"<td>{issue_link_html(r['issue_num'], r['issue_title'])}</td>")
                parts.append(f"<td>{czo_link_html(r['czo'])}</td>")
                parts.append(f'<td class="age">{html.escape(r["age"])}</td>')
                parts.append(f'<td class="age">{html.escape(r["last_activity"])}</td>')
                parts.append(f'<td class="reason">{html.escape(r["reason"])}</td>')
                parts.append("</tr>")
            parts.append("</tbody></table></div>")
        parts.append("</details>")

    parts += ["</body>", "</html>"]
    with open(output_path, "w") as f:
        f.write("\n".join(parts))
    print("wrote", output_path)


def _suggest_for_pr(
    num: int,
    author: str,
    alias_lookup: dict[str, str],
    maintainers_per_area: dict[str, list[tuple[str, int, bool]]],
) -> tuple[list[Suggestion], str]:
    """Compute reviewer suggestions for a PR. Empty if no commits cached."""
    p = os.path.join(CACHE, f"commits_{num}.json")
    if not os.path.exists(p):
        return [], "none"
    with open(p) as f:
        commits = json.load(f)
    if not commits:
        return [], "none"
    return suggest_reviewers(commits, author, alias_lookup, maintainers_per_area)


def main() -> None:
    range_key = sys.argv[1] if len(sys.argv) > 1 else _default_range_key()
    range_start, range_end = range_key.split("_")
    range_label = f"{range_start}_to_{range_end}"

    with open(f"{CACHE}/combined_{range_key}.json") as f:
        combined = json.load(f)
    issue_titles = load_issue_titles()
    alias_lookup = load_alias_lookup()
    maintainers_per_area = load_maintainers_per_area()

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
        row["suggestions"], row["suggestion_confidence"] = (
            _suggest_for_pr(n, row["author"], alias_lookup, maintainers_per_area)
            if cat in (1, 6)
            else ([], "none")
        )
        rows_by_cat[cat].append(row)

    for rows in rows_by_cat.values():
        rows.sort(key=lambda r: -int(r["num"]))

    summary_html = (
        f"<p>Date range: <strong>{range_start} .. {range_end}</strong> (created window). "
        f"Filter: open, non-draft, not WIP. "
        f"Total PRs shown: <strong>{sum(len(v) for v in rows_by_cat.values())}</strong>"
        f" (skipped {len(drafts_skipped)} draft"
        f"{_skip_links(drafts_skipped)}, {len(wip_skipped)} WIP"
        f"{_skip_links(wip_skipped)}).</p>"
    )

    render_html(
        rows_by_cat=rows_by_cat,
        page_title=f"Zulip PR Triage: {range_start} to {range_end}",
        h1_text=f"Zulip PR Triage — open PRs created {range_start} to {range_end}",
        summary_html=summary_html,
        output_path=os.path.join(BASE, f"{range_label}.html"),
    )


if __name__ == "__main__":
    main()
