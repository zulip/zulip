"""The data for a status update on a "not ready" PR."""

from dataclasses import dataclass
from datetime import datetime
from itertools import islice

from tools.triage_bot.assemble import COMMITS_SHOWN, FILES_SHOWN, clip, day
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
FEEDBACK_CHARS = 4000
AUTHOR_COMMENT_CHARS = 4000
MAX_CI_RUNS = 200


@dataclass
class StatusUpdateRequest:
    # When the "not ready" label was last added, and by whom.
    labeled_at: datetime
    labeled_by: str
    # The last maintainer comment before the author's comment.
    feedback: Comment | None
    author_comment: Comment

    @property
    def feedback_time(self) -> datetime:
        return self.feedback.created_at if self.feedback else self.labeled_at


@dataclass
class PrShape:
    files: list[str]
    additions: int
    deletions: int
    commits: list[str]


def find_status_update_request(
    item: Item, events: list[JSONDict], comments: list[Comment]
) -> StatusUpdateRequest | None:
    """The author's latest comment, if it came after the "not ready"
    label and no maintainer has commented since."""
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
    author_comments = [comment for comment in human_comments if comment.author == item.author]
    if not author_comments or author_comments[-1].created_at < labeled_at:
        return None
    author_comment = author_comments[-1]
    maintainer_comments = [
        comment
        for comment in human_comments
        if comment.is_maintainer and comment.author != item.author
    ]
    if maintainer_comments and maintainer_comments[-1].created_at > author_comment.created_at:
        return None
    return StatusUpdateRequest(
        labeled_at=labeled_at,
        labeled_by=json_user_login(label_events[-1].get("actor")),
        feedback=maintainer_comments[-1] if maintainer_comments else None,
        author_comment=author_comment,
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
        return ["None: no new push since the feedback."]
    lines = [f"New pushes since the feedback: {pushes}."]
    if then is None:
        lines.append("The commits and files at the time of the feedback couldn't be found.")
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
    heads_before = [sha for when, sha in pushes if when <= request.feedback_time]
    pushes_after = {sha for when, sha in pushes if when > request.feedback_time}
    then = fetch_shape(heads_before[-1]) if heads_before else None
    now = PrShape(
        files=item.files,
        additions=item.additions,
        deletions=item.deletions,
        commits=item.commits,
    )
    return changes_lines(then, now, len(pushes_after))


def status_update_lines(request: StatusUpdateRequest, changes: list[str]) -> list[str]:
    lines = [
        "## Status update",
        "",
        f'"{NOT_READY_LABEL}" label added by {request.labeled_by} on {day(request.labeled_at)}.',
        "",
        "### The maintainer feedback the author is answering",
    ]
    feedback = request.feedback
    if feedback is not None:
        lines.append(
            f"[{feedback.author}, maintainer, {day(feedback.created_at)}, {feedback.kind}]\n"
            + clip(feedback.body, FEEDBACK_CHARS)
        )
    else:
        lines.append("(No maintainer comment before the author's comment; only the label.)")
    comment = request.author_comment
    lines.extend(
        [
            "",
            "### Code changes since that feedback",
            *changes,
            "",
            "### The author's new comment (this is what the status update is about)",
            f"[{comment.author}, PR author, {comment.created_at:%Y-%m-%d %H:%M} UTC]\n"
            + clip(comment.body, AUTHOR_COMMENT_CHARS),
        ]
    )
    return lines


def ready_check_input(item: Item, request: StatusUpdateRequest) -> str:
    """The input for the check of whether the comment asks for another look."""
    parts = [f"PR #{item.number}"]
    if request.feedback is not None:
        parts.append(
            f"Maintainer comment before the author's (by {request.feedback.author}):\n"
            f"<maintainer_comment>\n{clip(request.feedback.body, FEEDBACK_CHARS)}\n"
            "</maintainer_comment>"
        )
    else:
        parts.append("There is no maintainer comment before the author's.")
    parts.append(
        f"The author's comment (by {item.author}):\n"
        f"<author_comment>\n{clip(request.author_comment.body, AUTHOR_COMMENT_CHARS)}\n"
        "</author_comment>"
    )
    return "\n\n".join(parts)
