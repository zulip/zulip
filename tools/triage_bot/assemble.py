"""Turn gathered data into the triage bot's input text.

The input has every human comment, the linked issue in full, earlier
attempts with the files they share, the single best chat.zulip.org
thread, the author's recent PRs with closing comments, and CI as
pass/fail.
"""

import re
from datetime import datetime

from tools.triage_bot.gather import CZO_MESSAGES_SHOWN, Comment, GatheredItem, ItemKind

FAILED = {"failure", "timed_out", "action_required", "startup_failure"}
# Only the latest check run of each name is fetched, so a cancelled
# check wasn't rerun.
CANCELLED = "cancelled"
PENDING = {"queued", "in_progress", "pending", "waiting", "requested"}
DESCRIPTION_CHARS = 6000
LINKED_DESCRIPTION_CHARS = 2500
COMMENT_CHARS = 1500
LINKED_COMMENT_CHARS = 900
CZO_CHARS = 700
MAINTAINER_COMMENT_CHARS = 500
CLOSING_COMMENT_CHARS = 400
BOT_COMMENT_CHARS = 200
FILES_SHOWN = 60
COMMITS_SHOWN = 30
SHARED_FILES_SHOWN = 6


def kind_name(kind: ItemKind) -> str:
    return "PR" if kind == "pr" else "issue"


def names_or_none(names: list[str]) -> str:
    return ", ".join(names) or "none"


def clip(text: str, limit: int) -> str:
    text = re.sub(r"<!--.*?-->", "", (text or "").replace("\r", ""), flags=re.DOTALL).strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " [...]"


def one_line(text: str, limit: int) -> str:
    return clip(re.sub(r"\s+", " ", text or ""), limit)


def day(when: datetime) -> str:
    return when.strftime("%Y-%m-%d")


def comment_line(comment: Comment, limit: int = COMMENT_CHARS) -> str:
    author, created = comment.author, day(comment.created_at)
    if comment.is_bot:
        return f"- [{author}, {created}] {one_line(comment.body, BOT_COMMENT_CHARS)}"
    role = "maintainer" if comment.is_maintainer else comment.association.lower()
    kind = (
        f"review ({comment.review_state.lower()})"
        if comment.kind == "review" and comment.review_state
        else comment.kind
    )
    return f"- [{author}, {role}, {created}, {kind}] {clip(comment.body, limit)}"


def ci_status(conclusions: list[str] | None) -> str:
    if conclusions is None:
        return "unknown (check runs aren't available)"
    counted = set(conclusions) - {"skipped", "neutral"}
    if not counted:
        return "no checks ran"
    if counted & FAILED:
        return "failed"
    if counted & PENDING:
        return "pending"
    if CANCELLED in counted:
        return "cancelled (not rerun)"
    return "passed"


def fact_lines(gathered: GatheredItem) -> list[str]:
    item = gathered.item
    lines = [
        f"Author: {gathered.author_name} (GitHub {item.author}, {item.author_association})",
        f"Opened: {item.created_at:%Y-%m-%d %H:%M UTC}",
        f"Assignees: {names_or_none(item.assignees)}",
    ]
    if item.kind == "pr":
        if "has conflicts" in item.labels:
            conflicts = "yes (has conflicts label)"
        else:
            conflicts = 'none known (no "has conflicts" label)'
        lines.append(f"Review requested from: {names_or_none(item.review_requested)}")
        lines.append("Draft: yes" if item.draft else "Draft: no (ready for review)")
        lines.append(f"Merge conflicts: {conflicts}")
        lines.append(f"Changes: +{item.additions}/-{item.deletions} in {item.changed_files} files")
    return lines


def linked_lines(gathered: GatheredItem) -> list[str]:
    lines = []
    for linked_item in gathered.linked:
        lines.extend(
            [
                (
                    f"### {linked_item.ref} ({kind_name(linked_item.kind)}, {linked_item.state}): "
                    f"{linked_item.title}"
                ),
                (
                    f"Opened by {linked_item.author} ({linked_item.author_association}). "
                    f"Labels: {names_or_none(linked_item.labels)}. "
                    f"Assignees: {names_or_none(linked_item.assignees)}."
                ),
                "Description: " + clip(linked_item.body, LINKED_DESCRIPTION_CHARS),
            ]
        )
        if linked_item.comments:
            lines.append("Comments:")
            lines.extend(
                comment_line(comment, LINKED_COMMENT_CHARS) for comment in linked_item.comments
            )
        lines.append("")
    return lines


def attempt_lines(gathered: GatheredItem) -> list[str]:
    lines = []
    for attempt in gathered.attempts:
        same_author = " [same author]" if attempt.same_author else ""
        mentioned = "yes" if attempt.mentioned_in_item else "no"
        lines.append(
            f"- #{attempt.pr.number} by {attempt.pr.author} "
            f"({attempt.pr.state}, opened {day(attempt.pr.created_at)}): "
            f"{attempt.pr.title}{same_author}"
            f" — mentioned in this item: {mentioned}"
        )
        if attempt.last_maintainer_comment:
            comment = attempt.last_maintainer_comment
            lines.append(
                f"  last maintainer comment ({comment.author}, {day(comment.created_at)}): "
                f"{one_line(comment.body, MAINTAINER_COMMENT_CHARS)}"
            )
        if gathered.item.kind == "pr":
            files_shared = attempt.files_shared
            shown = f" ({', '.join(files_shared[:SHARED_FILES_SHOWN])})" if files_shared else ""
            lines.append(f"  files shared with this PR: {len(files_shared)}{shown}")
    return lines


def czo_lines(gathered: GatheredItem) -> list[str]:
    lines = []
    if gathered.czo_thread is not None:
        thread = gathered.czo_thread
        shown = "" if thread.found_oldest else f" (last {CZO_MESSAGES_SHOWN} messages)"
        lines.extend([f"### #{thread.channel} > {thread.topic}{shown}", thread.url])
        lines.extend(
            f"- [{message.sender}, {day(message.timestamp)}] {one_line(message.content, CZO_CHARS)}"
            for message in thread.messages
        )
        lines.append("")
    if gathered.czo_unread_links:
        if not lines:
            lines.extend(["(none)", ""])
        lines.append(
            "Linked conversations that couldn't be read (the topic may have been renamed, "
            "or the channel isn't public):"
        )
        lines.extend(f"- {link}" for link in gathered.czo_unread_links)
    return lines


def author_lines(gathered: GatheredItem) -> list[str]:
    history = gathered.author_history
    lines = [f"Has had PRs merged before: {'yes' if history.has_merged_pr else 'no'}."]
    for kind, entries in (("PR", history.prs), ("issue", history.issues)):
        for entry in entries:
            lines.append(
                f"- {kind} #{entry.number} ({entry.state}, {day(entry.created_at)}): {entry.title}"
            )
            if entry.closing_comment:
                comment = entry.closing_comment
                body = one_line(comment.body, CLOSING_COMMENT_CHARS)
                lines.append(f"  closing comment by {comment.author}: {body}")
    return lines


def assemble(gathered: GatheredItem) -> str:
    item = gathered.item
    kind = "Pull request" if item.kind == "pr" else "Issue"
    # The heading the program posts above the bot's message.
    lines = [
        f"# {kind} #{item.number}: {item.title}",
        item.url,
        f"Labels: {names_or_none(item.labels)}",
        "",
    ]

    def section(title: str, section_lines: list[str]) -> None:
        lines.extend([f"## {title}", *(section_lines or ["(none)"]), ""])

    section("About the item", fact_lines(gathered))
    section("Description", [clip(item.body, DESCRIPTION_CHARS) or "(empty)"])
    if item.kind == "pr":
        more_files = " ..." if len(item.files) > FILES_SHOWN else ""
        section("Files", [", ".join(item.files[:FILES_SHOWN]) + more_files])
        section("Commits", [f"- {commit}" for commit in item.commits[:COMMITS_SHOWN]])
        section("CI", [ci_status(gathered.ci_conclusions)])
    section("Comments so far", [comment_line(comment) for comment in gathered.comments])
    section("Linked issues and PRs", linked_lines(gathered))
    if item.kind == "pr" or gathered.attempts:
        section(
            "Earlier attempts at the linked issue (other PRs that reference it)",
            attempt_lines(gathered),
        )
    similar_lines = [
        f"- {kind_name(similar.kind)} #{similar.number} "
        f"({similar.state}, {day(similar.created_at)}): {similar.title}"
        for similar in gathered.similar
    ]
    section("Possible duplicates (items with similar titles)", similar_lines)
    section("chat.zulip.org threads", czo_lines(gathered))
    section("Author history", author_lines(gathered))
    if item.kind == "pr":
        file_author_lines = [
            f"- {file_author.name} ({file_author.commits} commits)"
            for file_author in gathered.file_authors
        ]
        section("Core contributors who changed these files in the last year", file_author_lines)
    return "\n".join(lines).rstrip() + "\n"
