"""Gather what the triage bot reads about one zulip/zulip item.

Lookups are mechanical: the GitHub API through PyGithub, the
chat.zulip.org spectator API, and the git log of a local checkout.
`gather()` returns a GatheredItem that assemble.py turns into the bot input.
"""

import json
import os
import re
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import cache
from itertools import islice
from typing import Any, Literal

import requests
from github import Auth, Github, UnknownObjectException
from github.CheckRun import CheckRun
from github.Issue import Issue
from github.NamedUser import NamedUser
from github.Organization import Organization
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

REPO = "zulip/zulip"
CI_WORKFLOW_FILE = "zulip-ci.yml"
CZO = "https://chat.zulip.org"
# The checkout whose git log at HEAD is used for reviewer candidates.
# In the workflow, HEAD is the default branch; locally, the current branch.
ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BOT_LOGINS = {"zulipbot"}
# The org has many alumni, and GitHub hides private members, so
# maintainers are listed here.
MAINTAINERS = {
    "alexmv",
    "alya",
    "amanagr",
    "andersk",
    "apoorvapendse",
    "benprew",
    "chrisbobbe",
    "emilysutherlin",
    "evykassirer",
    "gnprice",
    "karlstolley",
    "laurynmm",
    "mateuszmandera",
    "Niloth-p",
    "PieterCK",
    "prakhar1144",
    "pratik-pc",
    "rajveermalviya",
    "sahil839",
    "shubham-padia",
    "timabbott",
}
LINKED_ITEM_REF = re.compile(
    r"(?<![\w/#-])#(?P<number>\d{3,5})\b"
    r"|\b(?P<repo>[\w.-]+/[\w.-]+)#(?P<repo_number>\d+)\b"
    r"|github\.com/(?P<link_repo>[\w.-]+/[\w.-]+)/(?:issues|pull)/(?P<link_number>\d+)\b"
)
# Only a spam description would link more than this.
MAX_LINKED_ITEMS = 10
# Each earlier attempt costs up to about 20 API requests.
MAX_ATTEMPTS = 12
# Each candidate thread is one chat.zulip.org request.
MAX_CZO_CANDIDATES = 10
CZO_SEARCH_MESSAGES = 60
MAX_TIMELINE_EVENTS = 1500
MAX_PR_FILES = 500
# Each pair of these words is one GitHub search.
TITLE_WORDS_SEARCHED = 5
SIMILAR_SHOWN = 6
CORE_CONTRIBUTOR_COUNT = 40
FILE_AUTHORS_SHOWN = 5
CZO_EXCLUDED_CHANNELS = {
    "commits",
    "deployments",
    "github",
    "test here",
    "automated testing",
    "errors",
    "devel",
}
CZO_MESSAGES_SHOWN = 40
AUTHOR_PRS_SHOWN = 10
AUTHOR_ISSUES_SHOWN = 5

# Any, because these dicts hold JSON from the GitHub and chat.zulip.org
# APIs, and their shapes aren't declared.
JSONDict = dict[str, Any]
ItemKind = Literal["pr", "issue"]
ItemState = Literal["open", "closed", "merged"]


@dataclass(frozen=True)
class Comment:
    author: str
    association: str
    is_maintainer: bool
    is_bot: bool
    kind: Literal["comment", "review"]
    review_state: str | None
    created_at: datetime
    body: str


@dataclass
class Item:
    number: int
    kind: ItemKind
    url: str
    title: str
    author: str
    author_association: str
    author_is_maintainer: bool
    created_at: datetime
    labels: list[str]
    assignees: list[str]
    body: str
    # Pull requests only.
    draft: bool = False
    head_sha: str | None = None
    review_requested: list[str] = field(default_factory=list)
    additions: int | None = None
    deletions: int | None = None
    changed_files: int | None = None
    files: list[str] = field(default_factory=list)
    commits: list[str] = field(default_factory=list)


@dataclass
class LinkedItem:
    number: int
    repo: str
    ref: str
    kind: ItemKind
    title: str
    author: str
    author_association: str | None
    created_at: datetime
    state: ItemState
    labels: list[str]
    assignees: list[str]
    body: str
    comments: list[Comment]
    referencing_prs: list[int]
    files: list[str] = field(default_factory=list)


@dataclass
class Attempt:
    pr: LinkedItem
    last_maintainer_comment: Comment | None
    mentioned_in_item: bool
    same_author: bool
    files_shared: list[str]


@dataclass
class SimilarItem:
    number: int
    kind: ItemKind
    title: str
    created_at: datetime
    state: ItemState


@dataclass(frozen=True)
class CzoMessage:
    sender: str
    is_bot: bool
    timestamp: datetime
    content: str


@dataclass(frozen=True)
class ConversationLink:
    message_id: int | None
    channel_id: int | None
    topic: str | None


@dataclass
class CzoThread:
    channel_id: int
    channel: str
    topic: str
    messages: list[CzoMessage]
    found_oldest: bool

    @property
    def url(self) -> str:
        return topic_narrow_url(self.channel_id, self.channel, self.topic)


@dataclass(frozen=True)
class ClosingComment:
    author: str
    body: str


@dataclass
class AuthorHistoryEntry:
    number: int
    title: str
    created_at: datetime
    state: ItemState
    closing_comment: ClosingComment | None


@dataclass
class AuthorHistory:
    has_merged_pr: bool
    prs: list[AuthorHistoryEntry]
    issues: list[AuthorHistoryEntry]


@dataclass(frozen=True)
class FileAuthor:
    name: str
    commits: int


@dataclass
class GatheredItem:
    item: Item
    author_name: str
    comments: list[Comment]
    linked: list[LinkedItem]
    attempts: list[Attempt]
    similar: list[SimilarItem]
    czo_thread: CzoThread | None
    czo_unread_links: list[str]
    author_history: AuthorHistory
    # None for issues, and when the check runs couldn't be read.
    ci_conclusions: list[str] | None
    file_authors: list[FileAuthor]


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def parse_github_time(value: str) -> datetime:
    # Python 3.10's datetime.fromisoformat doesn't accept a trailing "Z".
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def item_kind(issue: Issue) -> ItemKind:
    # Reading a field that the API response left out, like pull_request on
    # an issue, makes PyGithub fetch the whole item again.
    return "pr" if "/pull/" in issue.html_url else "issue"


def item_state(issue: Issue) -> ItemState:
    if item_kind(issue) == "pr" and issue.pull_request is not None:
        # PyGithub types merged_at as always set, but it's None for an
        # unmerged PR.
        merged_at: datetime | None = issue.pull_request.merged_at
        if merged_at is not None:
            return "merged"
    return "closed" if issue.state == "closed" else "open"


RETRY_STATUSES = {429, 500, 502, 503, 504}


def retrying_session() -> requests.Session:
    """A session that retries GETs after temporary failures, with backoff.

    urllib3's Retry doesn't retry POSTs: one that timed out may have gone
    through.
    """
    retry = Retry(
        total=2, backoff_factor=5, backoff_max=30, backoff_jitter=5, status_forcelist=RETRY_STATUSES
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


czo_session = retrying_session()


@cache
def github() -> Github:
    # PyGithub's default retry policy retries server errors and waits out
    # rate limits.
    return Github(auth=Auth.Token(os.environ["GH_TOKEN"]), per_page=100)


def repository(name: str = REPO) -> Repository:
    return github().get_repo(name, lazy=True)


def search_issues(query: str, limit: int, newest_first: bool = True) -> list[Issue]:
    if newest_first:
        results = github().search_issues(query, sort="created", order="desc")
    else:
        results = github().search_issues(query)
    return list(islice(results, limit))


def named_user_login(user: NamedUser | Organization | None) -> str:
    return user.login if user else "ghost"


def user_login(user: JSONDict | None) -> str:
    return (user or {}).get("login") or "ghost"


def is_bot_user(user: JSONDict | None) -> bool:
    return user_login(user) in BOT_LOGINS or (user or {}).get("type") == "Bot"


def fetch_user_name(login: str) -> str:
    try:
        name = github().get_user(login).name
    except UnknownObjectException:
        name = None
    return (name or login).strip()


def fetch_timeline(issue: Issue) -> list[JSONDict]:
    return [event.raw_data for event in islice(issue.get_timeline(), MAX_TIMELINE_EVENTS)]


def comments_from_timeline(events: list[JSONDict]) -> list[Comment]:
    """Comments and reviews with bodies, oldest first."""
    comments = []
    for event in events:
        kind: Literal["comment", "review"]
        if event.get("event") == "commented":
            kind = "comment"
            user = event.get("user") or event.get("actor")
            created = event.get("created_at")
            review_state = None
        elif event.get("event") == "reviewed" and (event.get("body") or "").strip():
            kind = "review"
            user = event.get("user")
            created = event.get("submitted_at")
            review_state = event.get("state")
        else:
            continue
        if not created:
            continue
        login = user_login(user)
        comments.append(
            Comment(
                author=login,
                association=event.get("author_association", "NONE"),
                is_maintainer=login in MAINTAINERS,
                is_bot=is_bot_user(user),
                kind=kind,
                review_state=review_state,
                created_at=parse_github_time(created),
                body=event.get("body") or "",
            )
        )
    return comments


def referencing_prs_from_timeline(events: list[JSONDict]) -> list[int]:
    """PRs in this repository that reference the item."""
    numbers = []
    for event in events:
        if event.get("event") != "cross-referenced":
            continue
        source = (event.get("source") or {}).get("issue") or {}
        source_repo = (source.get("repository") or {}).get("full_name", REPO)
        if not source.get("number") or source_repo != REPO or "pull_request" not in source:
            continue
        numbers.append(source["number"])
    return numbers


def fetch_item(number: int) -> Item | None:
    """The item's current state: enough for a maintainer card."""
    try:
        issue = repository().get_issue(number).complete()
    except UnknownObjectException:
        return None
    author = named_user_login(issue.user)
    item = Item(
        number=number,
        kind=item_kind(issue),
        url=issue.html_url,
        title=issue.title.strip(),
        author=author,
        author_association=issue.author_association,
        author_is_maintainer=author in MAINTAINERS,
        created_at=issue.created_at,
        labels=[label.name for label in issue.labels],
        assignees=[assignee.login for assignee in issue.assignees],
        body=issue.body or "",
    )
    if item.kind == "pr":
        pr = repository().get_pull(number).complete()
        item.draft = pr.draft
        item.head_sha = pr.head.sha
        item.review_requested = [reviewer.login for reviewer in pr.requested_reviewers]
        item.additions, item.deletions = pr.additions, pr.deletions
        item.changed_files = pr.changed_files
        item.files = [file.filename for file in islice(pr.get_files(), MAX_PR_FILES)]
        item.commits = [commit.commit.message.partition("\n")[0] for commit in pr.get_commits()]
    return item


def linked_item_refs(text: str) -> list[tuple[str, int]]:
    """The (repository, number) of each issue or PR the text refers to, in order."""
    refs = []
    for match in LINKED_ITEM_REF.finditer(text):
        if match["number"]:
            refs.append((REPO, int(match["number"])))
        elif match["repo"]:
            refs.append((match["repo"], int(match["repo_number"])))
        else:
            refs.append((match["link_repo"], int(match["link_number"])))
    return refs


def fetch_linked_item(
    number: int, repo: str = REPO, *, with_files: bool = False
) -> LinkedItem | None:
    """An issue or PR that the item links to, or an earlier attempt at a
    linked issue.

    None if it doesn't exist or isn't public.
    """
    try:
        # The repository is lazy, so the issue is too until complete()
        # fetches it.
        issue = repository(repo).get_issue(number).complete()
    except UnknownObjectException:
        return None
    events = fetch_timeline(issue)
    item = LinkedItem(
        number=number,
        repo=repo,
        ref=f"#{number}" if repo == REPO else f"{repo}#{number}",
        kind=item_kind(issue),
        title=issue.title,
        author=named_user_login(issue.user),
        author_association=issue.author_association,
        created_at=issue.created_at,
        state=item_state(issue),
        labels=[label.name for label in issue.labels],
        assignees=[assignee.login for assignee in issue.assignees],
        body=issue.body or "",
        comments=comments_from_timeline(events),
        referencing_prs=referencing_prs_from_timeline(events),
    )
    if item.kind == "pr" and with_files:
        pr_files = repository(repo).get_pull(number).get_files()
        item.files = [file.filename for file in islice(pr_files, MAX_PR_FILES)]
    return item


def czo_get(
    narrow: list[dict[str, object]],
    before: int,
    anchor: str = "newest",
    after: int = 0,
) -> JSONDict:
    narrow = [{"operator": "channels", "operand": "web-public"}, *narrow]
    params: dict[str, str | int] = {
        "narrow": json.dumps(narrow),
        "anchor": anchor,
        "num_before": before,
        "num_after": after,
        "apply_markdown": "false",
    }
    response = czo_session.get(f"{CZO}/json/messages", params=params, timeout=40)
    response.raise_for_status()
    return response.json()


def czo_message(message: JSONDict) -> CzoMessage:
    sender_email = message.get("sender_email", "")
    return CzoMessage(
        sender=message["sender_full_name"],
        is_bot="-bot@" in sender_email or sender_email.startswith("notification-bot"),
        timestamp=datetime.fromtimestamp(message["timestamp"], timezone.utc),
        content=message["content"],
    )


def topic_narrow(channel_id: int, topic: str) -> list[dict[str, object]]:
    return [
        {"operator": "channel", "operand": channel_id},
        {"operator": "topic", "operand": topic},
    ]


def fetch_czo_thread(channel_id: int, topic: str) -> CzoThread:
    result = czo_get(topic_narrow(channel_id, topic), before=CZO_MESSAGES_SHOWN)
    messages = result.get("messages", [])
    return CzoThread(
        channel_id=channel_id,
        channel=messages[0]["display_recipient"] if messages else "",
        topic=topic,
        messages=[czo_message(message) for message in messages],
        found_oldest=result.get("found_oldest", True),
    )


# Narrow URLs follow https://zulip.com/api/zulip-urls.
OPERATOR_SYNONYMS = {"stream": "channel", "subject": "topic"}
HASH_REPLACEMENTS = {"%": ".", "(": ".28", ")": ".29", ".": ".2E"}


def encode_hash_component(string: str) -> str:
    encoded = urllib.parse.quote(string, safe="")
    return "".join(HASH_REPLACEMENTS.get(char, char) for char in encoded)


def decode_hash_component(string: str) -> str:
    return urllib.parse.unquote(string.replace(".", "%"))


def encode_channel(channel_id: int, channel_name: str) -> str:
    return f"{channel_id}-{encode_hash_component(channel_name.replace(' ', '-'))}"


def topic_narrow_url(channel_id: int, channel_name: str, topic_name: str) -> str:
    channel = encode_channel(channel_id, channel_name)
    return f"{CZO}/#narrow/channel/{channel}/topic/{encode_hash_component(topic_name)}"


CZO_LINK = re.compile(rf"{re.escape(CZO)}/#narrow/\S+")
TRAILING_PUNCTUATION = ")]}>,;:!?'\"*."


def czo_links(text: str) -> list[str]:
    return [link.rstrip(TRAILING_PUNCTUATION) for link in CZO_LINK.findall(text)]


def parse_conversation_link(link: str) -> ConversationLink | None:
    """The conversation a link points to, or None for other links."""
    parts = urllib.parse.urlsplit(link).fragment.split("/")
    operands = {
        OPERATOR_SYNONYMS.get(operator, operator): operand
        for operator, operand in zip(parts[1::2], parts[2::2], strict=False)
    }
    message_id = operands.get("with") or operands.get("near") or ""
    # A channel operand is the channel ID, optionally followed by "-"
    # and the channel name.
    channel_id = operands.get("channel", "").split("-")[0]
    topic = operands.get("topic")
    conversation = ConversationLink(
        message_id=int(message_id) if message_id.isdigit() else None,
        channel_id=int(channel_id) if channel_id.isdigit() else None,
        topic=decode_hash_component(topic) if topic is not None else None,
    )
    if conversation.message_id is None and (
        conversation.channel_id is None or conversation.topic is None
    ):
        return None
    return conversation


def find_conversation(conversation: ConversationLink) -> tuple[int, str] | None:
    """The channel ID and topic of the conversation now, or None if it can't be read."""
    # A link to a private channel or a deleted message fails, and is
    # listed as unread rather than stopping the run.
    message_id = conversation.message_id
    try:
        if message_id is not None:
            # The "with" operator finds the message's conversation even after
            # the topic was renamed, resolved or moved.
            messages = czo_get(
                [{"operator": "with", "operand": message_id}],
                anchor=str(message_id),
                before=0,
                after=0,
            ).get("messages", [])
            if messages:
                return messages[0]["stream_id"], messages[0]["subject"]
        channel_id, topic = conversation.channel_id, conversation.topic
        if (
            channel_id is not None
            and topic is not None
            and czo_get(topic_narrow(channel_id, topic), before=1).get("messages")
        ):
            return channel_id, topic
    except requests.RequestException as e:
        log(f"{e}; listing the link as unread")
    return None


def title_words(title: str, limit: int) -> list[str]:
    # Short all-caps words like UI, DM and API are kept.
    title_without_code = re.sub(r"`[^`]*`", " ", title)
    words = re.findall(r"[A-Za-z][A-Za-z'-]{3,}|\b[A-Z]{2,3}s?\b", title_without_code)
    return list(dict.fromkeys(word.lower() for word in words))[:limit]


def singular(word: str) -> str:
    return word[:-1] if len(word) > 4 and word.endswith("s") and not word.endswith("ss") else word


def find_similar(number: int, title: str) -> list[SimilarItem]:
    """Earlier items whose titles share the most words with this title.

    GitHub's title search needs every query word to match, so one query
    with all title words misses a duplicate worded differently.  Instead,
    run one query per pair of title words, then rank the pooled results by
    how many title words they share.  Ties keep the order GitHub found
    them in.
    """
    words = title_words(title, TITLE_WORDS_SEARCHED)
    queries = [" ".join(words[:4])] if len(words) > 2 else []
    queries += [f"{first} {second}" for i, first in enumerate(words) for second in words[i + 1 :]]
    pool: dict[int, Issue] = {}
    for query in queries:
        for result in search_issues(f"repo:{REPO} {query} in:title", 30, newest_first=False):
            if result.number != number:
                pool[result.number] = result
    title_stems = {singular(word) for word in words}

    def shared_words(candidate: Issue) -> int:
        candidate_words = re.findall(r"[a-z']+", candidate.title.lower())
        return len({singular(word) for word in candidate_words} & title_stems)

    ranked = sorted(pool.values(), key=shared_words, reverse=True)
    return [
        SimilarItem(
            number=candidate.number,
            kind=item_kind(candidate),
            title=candidate.title,
            created_at=candidate.created_at,
            state=item_state(candidate),
        )
        for candidate in ranked[:SIMILAR_SHOWN]
    ]


@dataclass
class CzoCandidate:
    channel_id: int
    topic: str
    from_link: bool = False
    hits: int = 0


def find_czo_thread(
    number: int,
    texts: list[str],
    linked: list[LinkedItem],
    attempt_numbers: list[int],
) -> tuple[CzoThread | None, list[str]]:
    """The best chat.zulip.org thread, from links and item numbers.

    Also returns the linked conversations that couldn't be read.
    """
    candidates: dict[tuple[int, str], CzoCandidate] = {}
    unread_links: list[str] = []

    def add_candidate(channel_id: int, topic: str, from_link: bool) -> None:
        candidate = candidates.setdefault((channel_id, topic), CzoCandidate(channel_id, topic))
        candidate.from_link = candidate.from_link or from_link
        candidate.hits += 1

    for link in dict.fromkeys(czo_links("\n".join(texts))):
        conversation_link = parse_conversation_link(link)
        if conversation_link is None:
            continue
        conversation = find_conversation(conversation_link)
        if conversation is None:
            unread_links.append(link)
        else:
            channel_id, topic = conversation
            add_candidate(channel_id, topic, from_link=True)
    linked_numbers = [linked_item.number for linked_item in linked if linked_item.repo == REPO]
    for searched_number in [number, *linked_numbers, *attempt_numbers]:
        narrow: list[dict[str, object]] = [{"operator": "search", "operand": str(searched_number)}]
        for message in czo_get(narrow, before=CZO_SEARCH_MESSAGES).get("messages", []):
            if re.search(rf"\b{searched_number}\b", message["content"] + " " + message["subject"]):
                add_candidate(message["stream_id"], message["subject"], from_link=False)
    # Linked threads first, then the most mentions.
    ranked = sorted(
        candidates.values(), key=lambda candidate: (not candidate.from_link, -candidate.hits)
    )
    for candidate in ranked[:MAX_CZO_CANDIDATES]:
        thread = fetch_czo_thread(candidate.channel_id, candidate.topic)
        if thread.channel.lower() in CZO_EXCLUDED_CHANNELS:
            continue
        thread.messages = [message for message in thread.messages if not message.is_bot]
        if not thread.messages:
            continue
        return thread, unread_links
    return None, unread_links


def fetch_closing_comment(issue: Issue) -> ClosingComment | None:
    """The last maintainer comment from when the item was closed."""
    # "Close with comment" saves the comment just after the close.
    maintainer_comments = [
        comment
        for comment in issue.get_comments()
        if named_user_login(comment.user) in MAINTAINERS
        and comment.created_at <= issue.closed_at + timedelta(minutes=10)
    ]
    if not maintainer_comments:
        return None
    comment = maintainer_comments[-1]
    return ClosingComment(author=named_user_login(comment.user), body=comment.body)


def fetch_author_entries(
    author: str, number: int, query: str, limit: int
) -> list[AuthorHistoryEntry]:
    # One more than the limit, since the results can include the item itself.
    results = search_issues(f"repo:{REPO} {query} author:{author}", limit + 1)
    entries: list[AuthorHistoryEntry] = []
    for result in [result for result in results if result.number != number][:limit]:
        state = item_state(result)
        closing_comment = fetch_closing_comment(result) if state == "closed" else None
        entries.append(
            AuthorHistoryEntry(
                number=result.number,
                title=result.title,
                created_at=result.created_at,
                state=state,
                closing_comment=closing_comment,
            )
        )
    return entries


def fetch_author_history(author: str, number: int) -> AuthorHistory:
    merged_prs = search_issues(f"repo:{REPO} type:pr is:merged author:{author}", 1)
    return AuthorHistory(
        has_merged_pr=bool(merged_prs),
        prs=fetch_author_entries(author, number, "type:pr", AUTHOR_PRS_SHOWN),
        issues=fetch_author_entries(author, number, "type:issue", AUTHOR_ISSUES_SHOWN),
    )


def fetch_ci_workflow_runs(head_sha: str) -> list[WorkflowRun]:
    runs = (
        repository()
        .get_workflow(CI_WORKFLOW_FILE)
        .get_runs(head_sha=head_sha, event="pull_request")
    )
    return list(islice(runs, 20))


def zulip_ci_checks(check_runs: list[CheckRun], workflow_runs: list[WorkflowRun]) -> list[CheckRun]:
    """The check runs that belong to the given Zulip CI workflow runs.

    Other workflows, like Copilot code review, add check runs to the same
    commit, and their results say nothing about the PR's tests.
    """
    suite_ids = {run.check_suite_id for run in workflow_runs}
    return [check for check in check_runs if check.check_suite.id in suite_ids]


def fetch_ci_conclusions(head_sha: str) -> list[str] | None:
    """The result of the latest check run of each name in Zulip CI on the
    PR's head commit."""
    try:
        check_runs = list(repository().get_commit(head_sha).get_check_runs())
        workflow_runs = fetch_ci_workflow_runs(head_sha)
    except UnknownObjectException:
        return None
    checks = zulip_ci_checks(check_runs, workflow_runs)
    return [check.conclusion or check.status for check in checks]


def shortlog(since: str, *paths: str) -> list[str]:
    return subprocess.check_output(
        ["git", "shortlog", "-sn", f"--since={since}", "HEAD", "--", *paths],
        cwd=ZULIP_PATH,
        text=True,
    ).splitlines()


def core_contributors() -> set[str]:
    return {line.split("\t")[1] for line in shortlog("2 years ago")[:CORE_CONTRIBUTOR_COUNT]}


def find_file_authors(files: list[str]) -> list[FileAuthor]:
    if not files:
        return []
    core = core_contributors()
    authors = []
    for line in shortlog("12 months ago", *files):
        count, name = line.split("\t")
        if name in core:
            authors.append(FileAuthor(name=name, commits=int(count)))
    return authors[:FILE_AUTHORS_SHOWN]


def find_attempts(item: Item, linked: list[LinkedItem], comments: list[Comment]) -> list[Attempt]:
    """Earlier attempts: PRs cross-referencing a linked issue."""
    attempt_numbers = {
        number
        for linked_item in linked
        if linked_item.kind == "issue"
        for number in linked_item.referencing_prs
        if number != item.number
    }
    author_comments = " ".join(
        comment.body for comment in comments if comment.author == item.author
    )
    mention_text = item.body + " " + author_comments
    attempts = []
    for attempt_number in sorted(attempt_numbers)[-MAX_ATTEMPTS:]:
        pr = fetch_linked_item(attempt_number, with_files=True)
        if not pr:
            continue
        maintainer_comments = [comment for comment in pr.comments if comment.is_maintainer]
        mention = rf"#{attempt_number}\b|/pull/{attempt_number}\b"
        attempts.append(
            Attempt(
                pr=pr,
                last_maintainer_comment=maintainer_comments[-1] if maintainer_comments else None,
                mentioned_in_item=bool(re.search(mention, mention_text)),
                same_author=pr.author == item.author,
                files_shared=sorted(set(pr.files) & set(item.files)),
            )
        )
    return attempts


def gather(item: Item) -> GatheredItem:
    """Everything the bot input needs, added to the item from fetch_item()."""
    number = item.number
    comments = comments_from_timeline(fetch_timeline(repository().get_issue(number)))

    text = item.title + "\n" + item.body
    linked_refs = [ref for ref in dict.fromkeys(linked_item_refs(text)) if ref != (REPO, number)]
    linked = []
    for repo, ref_number in linked_refs[:MAX_LINKED_ITEMS]:
        linked_item = fetch_linked_item(ref_number, repo)
        if linked_item is not None:
            linked.append(linked_item)
    attempts = find_attempts(item, linked, comments)

    similar = find_similar(number, item.title)

    texts = [item.body] + [comment.body for comment in comments]
    for related in [*linked, *(attempt.pr for attempt in attempts)]:
        texts += [related.body] + [comment.body for comment in related.comments]
    thread, unread_links = find_czo_thread(
        number, texts, linked, [attempt.pr.number for attempt in attempts]
    )

    return GatheredItem(
        item=item,
        author_name=fetch_user_name(item.author),
        comments=comments,
        linked=linked,
        attempts=attempts,
        similar=similar,
        czo_thread=thread,
        czo_unread_links=unread_links,
        author_history=fetch_author_history(item.author, number),
        ci_conclusions=fetch_ci_conclusions(item.head_sha) if item.head_sha is not None else None,
        file_authors=find_file_authors(item.files) if item.kind == "pr" else [],
    )
