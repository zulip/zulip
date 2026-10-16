"""Turn gathered data into the triage bot's input text.

The layout is the one the triage bot evals picked:
every human comment, the linked issue in full, earlier attempts with
the files they share, the single best chat.zulip.org thread (last 40
messages), the author's last 10 PRs with closing comments, and CI as
pass/fail.
"""

import re
from typing import Any

# Any, because these dicts hold JSON from the GitHub and chat.zulip.org
# APIs, plus the fields gather.py adds, and their shapes aren't declared.
JSONDict = dict[str, Any]

FAILED = {"failure", "timed_out", "action_required", "startup_failure"}
# The bot only posts a card while no Zulip CI run is queued or running,
# so a cancelled check on the head commit was never rerun.
CANCELLED = "cancelled"
PENDING = {"queued", "in_progress", "pending", "waiting", "requested"}
COMMENT_CHARS = 1500
LINKED_COMMENT_CHARS = 900
CZO_CHARS = 700
CZO_MESSAGES_SHOWN = 40
AUTHOR_PRS_SHOWN = 10
AUTHOR_ISSUES_SHOWN = 5


def clip(s: str, n: int) -> str:
    s = re.sub(r"<!--.*?-->", "", (s or "").replace("\r", ""), flags=re.DOTALL).strip()
    return s if len(s) <= n else s[:n].rstrip() + " [...]"


def one_line(s: str, n: int) -> str:
    return clip(re.sub(r"\s+", " ", s or ""), n)


def comment_line(c: JSONDict, n: int = COMMENT_CHARS) -> str:
    if c["bot"]:
        return f"- [{c['who']}, {c['created'][:10]}] {one_line(c['body'], 200)}"
    role = "maintainer" if c["maintainer"] else c["association"].lower()
    what = (
        f"review ({c['review_state'].lower()})"
        if c["kind"] == "review" and c.get("review_state")
        else c["kind"]
    )
    return f"- [{c['who']}, {role}, {c['created'][:10]}, {what}] {clip(c['body'], n)}"


def counted_checks(ci: JSONDict) -> list[JSONDict]:
    return [r for r in ci.get("runs", []) if r["conclusion"] not in ("skipped", "neutral")]


def ci_state(ci: JSONDict | None) -> str:
    """unknown, none, failed, pending, cancelled or passed."""
    if not ci or not ci.get("known"):
        return "unknown"
    runs = counted_checks(ci)
    if not runs:
        return "none"
    if any(r["conclusion"] in FAILED for r in runs):
        return "failed"
    if any(r["conclusion"] in PENDING for r in runs):
        return "pending"
    if any(r["conclusion"] == CANCELLED for r in runs):
        return "cancelled"
    return "passed"


def ci_status(ci: JSONDict | None) -> str:
    state = ci_state(ci)
    if state == "unknown":
        return f"unknown ({(ci or {}).get('reason', 'not available')})"
    return {
        "none": "no checks ran",
        "cancelled": "cancelled (not rerun)",
    }.get(state, state)


def author_lines(raw: JSONDict) -> list[str]:
    hist = raw["author_history"]
    prs, issues = hist["prs"], hist["issues"]
    merged = any(p["state"] == "merged" for p in prs)
    lines = [f"Has had PRs merged before: {'yes' if merged else 'no'}."]
    for p in prs[:AUTHOR_PRS_SHOWN]:
        lines.append(f"- PR #{p['number']} ({p['state']}, {p['created'][:10]}): {p['title']}")
        if p.get("closing_comment"):
            c = p["closing_comment"]
            lines.append(f"  closing comment by {c['who']}: {one_line(c['body'], 400)}")
    for i in issues[:AUTHOR_ISSUES_SHOWN]:
        lines.append(f"- issue #{i['number']} ({i['state']}, {i['created'][:10]}): {i['title']}")
        if i.get("closing_comment"):
            lines.append(
                f"  closing comment by {i['closing_comment']['who']}: {one_line(i['closing_comment']['body'], 400)}"
            )
    return lines


def assemble(raw: JSONDict) -> str:
    out: list[str] = []

    def section(title: str, lines: list[str], key: str | None = None) -> None:
        out.append(f"## {title}")
        if key in raw["incomplete"]:
            lines = (
                [*lines, "(some of this couldn't be loaded)"] if lines else ["(couldn't be loaded)"]
            )
        out.extend(lines or ["(none)"])
        out.append("")

    kind = "Pull request" if raw["kind"] == "pr" else "Issue"
    # The heading the program posts above the bot's message.
    out += [
        f"# {kind} #{raw['number']}: {raw['title']}",
        raw["url"],
        "Labels: " + (", ".join(raw["labels"]) or "none"),
        "",
    ]

    facts = [
        f"Author: {raw['author_name']} (GitHub {raw['author']}, {raw['author_association']})",
        f"Opened: {raw['opened'][:16].replace('T', ' ')} UTC",
        "Assignees: " + (", ".join(raw["assignees"]) or "none"),
    ]
    if raw["kind"] == "pr":
        facts.append("Review requested from: " + (", ".join(raw["review_requested"]) or "none"))
        facts.append("Draft: yes" if raw["draft"] else "Draft: no (ready for review)")
        facts.append(
            "Merge conflicts: "
            + (
                "yes (has conflicts label)"
                if "has conflicts" in raw["labels"]
                else 'none known (no "has conflicts" label)'
            )
        )
        facts.append(
            f"Changes: +{raw['additions']}/-{raw['deletions']} in {len(raw['files'])} files"
        )
    section("About the item", facts)
    section("Description", [clip(raw["body"], 6000) or "(empty)"])
    if raw["kind"] == "pr":
        section(
            "Files", [", ".join(raw["files"][:60]) + (" ..." if len(raw["files"]) > 60 else "")]
        )
        section("Commits", [f"- {c}" for c in raw["commits"][:30]])
        section("CI", [ci_status(raw["ci"])])

    section("Comments so far", [comment_line(c) for c in raw["comments"]])

    linked = []
    for x in raw["linked"]:
        linked.append(
            f"### {x['ref']} ({'PR' if x['kind'] == 'pr' else 'issue'}, {x['state']}): {x['title']}"
        )
        linked.append(
            f"Opened by {x['author']} ({x['author_association']}). Labels: {', '.join(x['labels']) or 'none'}. "
            f"Assignees: {', '.join(x['assignees']) or 'none'}."
        )
        linked.append("Description: " + clip(x["body"], 2500))
        if x["comments"]:
            linked.append("Comments:")
            linked += [comment_line(c, LINKED_COMMENT_CHARS) for c in x["comments"]]
        linked.append("")
    section("Linked issues and PRs", linked, key="linked")

    if raw["kind"] == "pr" or raw["attempts"]:
        att = []
        for a in raw["attempts"]:
            line = f"- #{a['number']} by {a['author']} ({a['state']}, opened {a['created'][:10]}): {a['title']}"
            if a["same_author"]:
                line += " [same author]"
            line += f" — mentioned in this item: {'yes' if a['mentioned_in_item'] else 'no'}"
            att.append(line)
            if a.get("last_maintainer_comment"):
                c = a["last_maintainer_comment"]
                att.append(
                    f"  last maintainer comment ({c['who']}, {c['created'][:10]}): {one_line(c['body'], 500)}"
                )
            if raw["kind"] == "pr":
                att.append(
                    f"  files shared with this PR: {len(a['files_shared'])}"
                    + (" (" + ", ".join(a["files_shared"][:6]) + ")" if a["files_shared"] else "")
                )
        section(
            "Earlier attempts at the linked issue (other PRs that reference it)",
            att,
            key="attempts",
        )

    dup = [
        f"- {'PR' if s['kind'] == 'pr' else 'issue'} #{s['number']} ({s['state']}, {s['created'][:10]}): {s['title']}"
        for s in raw["similar"][:6]
    ]
    section("Possible duplicates (items with similar titles)", dup, key="similar")

    czo = []
    for t in raw["czo_threads"]:
        shown = "" if t["whole"] else f" (last {CZO_MESSAGES_SHOWN} messages)"
        czo.append(f"### #{t['channel']} > {t['topic']}{shown}")
        czo += [
            f"- [{m['sender']}, {m['time'][:10]}] {one_line(m['content'], CZO_CHARS)}"
            for m in t["messages"]
        ]
        czo.append("")
    if raw["czo_unread_links"]:
        if not czo:
            czo += ["(none)", ""]
        czo.append(
            "Linked conversations that couldn't be read (the topic may have been renamed, "
            "or the channel isn't public):"
        )
        czo += [f"- {link}" for link in raw["czo_unread_links"]]
    section("chat.zulip.org threads", czo, key="czo_threads")

    section("Author history", author_lines(raw), key="author_history")
    if raw["kind"] == "pr":
        section(
            "Core contributors who changed these files in the last year",
            [f"- {a['name']} ({a['commits']} commits)" for a in raw["file_authors"][:5]],
        )
    return "\n".join(out).rstrip() + "\n"
