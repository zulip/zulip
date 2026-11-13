"""The data for a status update on a "not ready" PR."""

from dataclasses import dataclass
from datetime import datetime
from itertools import islice

from tools.triage_bot.assemble import COMMITS_SHOWN, FILES_SHOWN, clip, comment_kind, day
from tools.triage_bot.gather import (
    CI_WORKFLOW_FILE,
    MAX_PR_FILES,
    Comment,
    Item,
    JSONDict,
    json_user_login,
    parse_github_time,
    repository,
)

NOT_READY_LABEL = "not ready"
CONVERSATION_COMMENT_CHARS = 4000
MAX_CI_RUNS = 200


@dataclass
class StatusUpdateRequest:
    # When the "not ready" label was last added, and by whom.
    labeled_at: datetime
    labeled_by: str
    # The last maintainer comment up to the label, then every comment
    # since the label, oldest first.
    conversation: list[Comment]
    latest_author_comment: Comment


@dataclass
class PrShape:
    files: list[str]
    additions: int
    deletions: int
    commits: list[str]


def find_status_update_request(
    item: Item, events: list[JSONDict], comments: list[Comment]
) -> StatusUpdateRequest | None:
    """The conversation since the "not ready" label, if the author has
    commented since then."""
    label_events = [
        event
        for event in events
        if event.get("event") == "labeled"
        and (event.get("label") or {}).get("name") == NOT_READY_LABEL
    ]
    if not label_events:
        return None
    labeled_at = parse_github_time(label_events[-1]["created_at"])
    human_comments = [comment for comment in comments if not comment.is_bot]
    since_label = [comment for comment in human_comments if comment.created_at >= labeled_at]
    author_comments = [comment for comment in since_label if comment.author == item.author]
    if not author_comments:
        return None
    maintainer_comments_before_label = [
        comment
        for comment in human_comments
        if comment.created_at < labeled_at
        and comment.is_maintainer
        and comment.author != item.author
    ]
    return StatusUpdateRequest(
        labeled_at=labeled_at,
        labeled_by=json_user_login(label_events[-1].get("actor")),
        conversation=maintainer_comments_before_label[-1:] + since_label,
        latest_author_comment=author_comments[-1],
    )


def fetch_pushes(number: int) -> list[tuple[datetime, str]]:
    """The time and head commit of each push to the PR, oldest first.

    Each push starts a Zulip CI run, so the runs show the pushes.
    """
    pr = repository().get_pull(number)
    # PyGithub's types miss that a deleted fork has no repository.
    head_repo = (pr.head.raw_data.get("repo") or {}).get("full_name")
    if head_repo is None:
        return []
    runs = (
        repository()
        .get_workflow(CI_WORKFLOW_FILE)
        .get_runs(
            branch=pr.head.ref,
            event="pull_request",
            created=f">={pr.created_at:%Y-%m-%dT%H:%M:%SZ}",
        )
    )
    return sorted(
        (run.created_at, run.head_sha)
        for run in islice(runs, MAX_CI_RUNS)
        if run.head_repository.full_name == head_repo
    )


def fetch_shape(head_sha: str) -> PrShape:
    """The files, size and commits of the PR when its head was head_sha."""
    comparison = repository().compare("main", head_sha)
    files = list(islice(comparison.files, MAX_PR_FILES))
    return PrShape(
        files=[file.filename for file in files],
        additions=sum(file.additions for file in files),
        deletions=sum(file.deletions for file in files),
        commits=[commit.commit.message.partition("\n")[0] for commit in comparison.commits],
    )


def changes_lines(then: PrShape | None, now: PrShape, pushes: int) -> list[str]:
    if pushes == 0:
        return ["None: no new push since the label."]
    lines = [f"New pushes since the label: {pushes}."]
    if then is None:
        lines.append("The commits and files at the time of the label couldn't be found.")
        return lines
    lines.append(
        f"Size then: +{then.additions}/-{then.deletions} in {len(then.files)} files. "
        f"Size now: +{now.additions}/-{now.deletions} in {len(now.files)} files."
    )
    if then.commits != now.commits:
        lines.append("Commits then:")
        lines.extend(f"- {commit}" for commit in then.commits[:COMMITS_SHOWN])
        lines.append("Commits now:")
        lines.extend(f"- {commit}" for commit in now.commits[:COMMITS_SHOWN])
    else:
        lines.append("Commit messages: unchanged.")
    added = sorted(set(now.files) - set(then.files))
    removed = sorted(set(then.files) - set(now.files))
    if added:
        lines.append("Files added to the PR: " + ", ".join(added[:FILES_SHOWN]))
    if removed:
        lines.append("Files no longer in the PR: " + ", ".join(removed[:FILES_SHOWN]))
    if not added and not removed:
        lines.append("Same files as before.")
    return lines


def fetch_changes_lines(item: Item, request: StatusUpdateRequest) -> list[str]:
    pushes = fetch_pushes(item.number)
    if not pushes:
        return ["Unknown: the PR's pushes couldn't be found."]
    heads_before = [sha for when, sha in pushes if when <= request.labeled_at]
    pushes_after = {sha for when, sha in pushes if when > request.labeled_at}
    then = fetch_shape(heads_before[-1]) if heads_before else None
    now = PrShape(
        files=item.files,
        additions=item.additions,
        deletions=item.deletions,
        commits=item.commits,
    )
    return changes_lines(then, now, len(pushes_after))


def conversation_lines(item: Item, request: StatusUpdateRequest) -> list[str]:
    lines = []
    for comment in request.conversation:
        if comment.author == item.author:
            role = "PR author"
        elif comment.is_maintainer:
            role = "maintainer"
        else:
            role = comment.association.lower()
        lines.append(
            f"[{comment.author}, {role}, {comment.created_at:%Y-%m-%d %H:%M} UTC,"
            f" {comment_kind(comment)}]\n" + clip(comment.body, CONVERSATION_COMMENT_CHARS)
        )
    return lines


def label_line(request: StatusUpdateRequest) -> str:
    return f'"{NOT_READY_LABEL}" label added by {request.labeled_by} on {day(request.labeled_at)}.'


def status_update_lines(item: Item, request: StatusUpdateRequest, changes: list[str]) -> list[str]:
    return [
        "## Status update",
        "",
        label_line(request),
        "",
        "### The conversation since the label (this is what the status update is about)",
        *conversation_lines(item, request),
        "",
        "### Code changes since the label",
        *changes,
    ]


def ready_check_input(item: Item, request: StatusUpdateRequest) -> str:
    """The input for the check of whether the author asks for another look."""
    conversation = "\n\n".join(conversation_lines(item, request))
    return (
        f"PR #{item.number} by {item.author}. {label_line(request)}\n\n"
        f"<conversation>\n{conversation}\n</conversation>"
    )
