#!/usr/bin/env -S uv run --script --frozen --only-group release-tools
"""Post a triage card for a zulip/zulip issue or PR to chat.zulip.org.

The bot is read-only on GitHub.  For each item it posts one message
(a "card") to the current week's topic in a private channel.
Maintainers' items get a one-line card.  Other items get a card
written by Claude from the input that assemble.py builds.

When the author of a PR labeled "not ready" comments after the
feedback, asking for another look, the bot posts a status update:
what the author did since the feedback, and what is still missing.
See status_update.py.

In GitHub Actions (see .github/workflows/triage-bot.yml):

  triage_bot.py --scan     post cards for recently updated items that
                           don't have one yet, status updates and
                           reviewer suggestions
  triage_bot.py --item N

Locally:

  triage_bot.py --item N --dry-run   print the card and its topic

Configuration comes from the environment: ZULIP_TRIAGE_BOT_EMAIL,
ZULIP_TRIAGE_BOT_API_KEY, ZULIP_TRIAGE_CHANNEL and ANTHROPIC_API_KEY.
GITHUB_TOKEN must be set to a GitHub token.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import anthropic
import requests
from github import GithubException

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ZULIP_PATH)

from tools.triage_bot import gather
from tools.triage_bot.assemble import HAS_CONFLICTS_LABEL, assemble, kind_name
from tools.triage_bot.gather import MAINTAINERS, GatheredItem, Item, JSONDict, log
from tools.triage_bot.status_update import (
    NOT_READY_LABEL,
    StatusUpdateRequest,
    fetch_changes_lines,
    find_status_update_request,
    ready_check_input,
    status_update_lines,
)

MODEL = "claude-opus-5-5"
BOT_DIR = Path(__file__).resolve().parent
PROMPT_FILE = BOT_DIR / "prompt.md"
READY_CHECK_PROMPT_FILE = BOT_DIR / "ready_check.md"
STATUS_UPDATE_PROMPT_FILE = BOT_DIR / "status_update.md"
REVIEWER_PROMPT_FILE = BOT_DIR / "reviewer.md"
NOTHING_MISSING = "| ✅"
# Buddy and mentor reviews don't need an assignee.
HANDOFF_LABELS = {"maintainer review", "integration review", "priority integration review"}
REVIEWER_LINE = re.compile(r"@(?P<login>[\w-]+) — (?P<reason>.+)")
# Zulip allows up to 5000, but cards are long, so pages stay smaller.
MESSAGES_PER_FETCH = 1000
WORKFLOW_PATH = ".github/workflows/triage-bot.yml"
# Twice the time between scheduled runs, so the next run covers the
# items of a run that failed, and PRs whose CI was still running.
SCAN_WINDOW = timedelta(days=2)
# The most results GitHub's search returns.
MAX_SEARCH_RESULTS = 1000
POST_ERRORS = (requests.RequestException, GithubException, anthropic.APIError, RuntimeError)


def notice(message: str, level: str = "notice") -> None:
    # Shown as an annotation on the workflow run.
    print(
        f"::{level}::{message}" if os.environ.get("GITHUB_ACTIONS") else message,
        file=sys.stderr,
        flush=True,
    )


class Zulip:
    def __init__(self, email: str, api_key: str, channel: str) -> None:
        self.email = email
        self.channel = channel
        self.session = gather.retrying_session()
        self.session.auth = (email, api_key)
        self.posted = PostedMessages()

    @classmethod
    def from_env(cls) -> "Zulip | None":
        email = os.environ.get("ZULIP_TRIAGE_BOT_EMAIL")
        api_key = os.environ.get("ZULIP_TRIAGE_BOT_API_KEY")
        channel = os.environ.get("ZULIP_TRIAGE_CHANNEL")
        if not (email and api_key and channel):
            return None
        return cls(email, api_key, channel)

    def get(self, path: str, params: dict[str, str]) -> JSONDict:
        response = self.session.get(f"{gather.CZO}/api/v1/{path}", params=params, timeout=60)
        response.raise_for_status()
        return response.json()

    def load_posted(self) -> None:
        narrow = [
            {"operator": "channel", "operand": self.channel},
            {"operator": "sender", "operand": self.email},
        ]
        anchor = "newest"
        while True:
            result = self.get(
                "messages",
                {
                    "anchor": anchor,
                    "include_anchor": "false",
                    "num_before": str(MESSAGES_PER_FETCH),
                    "num_after": "0",
                    "apply_markdown": "false",
                    "narrow": json.dumps(narrow),
                },
            )
            messages = result["messages"]
            for message in reversed(messages):
                self.posted.add(message["content"], message["subject"])
            if result["found_oldest"] or not messages:
                return
            anchor = str(messages[0]["id"])

    def post(self, topic: str, content: str) -> None:
        # The session doesn't retry this: a POST that timed out may have
        # posted, and retrying it would post twice.
        response = self.session.post(
            f"{gather.CZO}/api/v1/messages",
            data={"type": "stream", "to": self.channel, "topic": topic, "content": content},
            timeout=60,
        )
        response.raise_for_status()


def topic_name(day: date) -> str:
    """The topic for the week, Monday to Sunday, that contains the day."""
    monday = day - timedelta(days=day.weekday())
    sunday = monday + timedelta(days=6)
    if monday.year != sunday.year:
        return f"{monday:%B} {monday.day}, {monday.year}–{sunday:%B} {sunday.day}, {sunday.year}"
    if monday.month != sunday.month:
        return f"{monday:%B} {monday.day}–{sunday:%B} {sunday.day}, {sunday.year}"
    return f"{monday:%B} {monday.day}–{sunday.day}, {sunday.year}"


def card_heading(item: Item) -> str:
    lines = [f"**[#{item.number} {item.title}]({item.url})**"]
    if item.labels:
        lines.append(" · ".join(f"`{label}`" for label in item.labels))
    return "\n".join(lines)


def status_update_heading(item: Item, comment_url: str) -> str:
    return f"**Status update: [#{item.number} {item.title}]({comment_url})**"


def reviewer_heading(item: Item) -> str:
    return f"**Reviewer: [#{item.number} {item.title}]({item.url})**"


# The first lines of card_heading(), status_update_heading() and
# reviewer_heading().  An item's URL ends with its number.
CARD_HEADING = re.compile(r"\*\*\[#(?P<number>\d+) .*/(?P=number)\)\*\*")
STATUS_UPDATE_HEADING = re.compile(r"\*\*Status update: \[#\d+ .*\]\((?P<comment_url>[^()]+)\)\*\*")
REVIEWER_HEADING = re.compile(r"\*\*Reviewer: \[#(?P<number>\d+) .*/(?P=number)\)\*\*")


@dataclass
class PostedMessages:
    """What the bot posted in the cards channel, read from each message's first line."""

    card_topics: dict[int, str] = field(default_factory=dict)
    status_update_comment_urls: set[str] = field(default_factory=set)
    reviewer_suggestions: set[int] = field(default_factory=set)

    def add(self, content: str, topic: str) -> None:
        """Call this newest first, so an item keeps its newest card's topic."""
        line = content.partition("\n")[0]
        if match := CARD_HEADING.fullmatch(line):
            self.card_topics.setdefault(int(match["number"]), topic)
        elif match := STATUS_UPDATE_HEADING.fullmatch(line):
            self.status_update_comment_urls.add(match["comment_url"])
        elif match := REVIEWER_HEADING.fullmatch(line):
            self.reviewer_suggestions.add(int(match["number"]))


def silence_mentions(content: str) -> str:
    """Turn every user, group and wildcard mention into a silent mention.

    The title and the model's text come from what the item's author
    wrote, so they could mention anyone, even @**all**.
    """
    return content.replace("@*", "@_*")


def maintainer_card(item: Item) -> str:
    """A card with no LLM call: maintainers triage their own items."""
    return f"**Maintainer {kind_name(item.kind)} from {item.author}. Nothing to triage.**"


def call_claude(system_prompt: str, user_message: str) -> str:
    # Five attempts in all. The SDK waits between them with backoff.
    client = anthropic.Anthropic(max_retries=4, timeout=600)
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"The model declined to answer: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        log("The model hit max_tokens; the answer may be cut off.")
    text = "".join(
        block.text for block in response.content if isinstance(block, anthropic.types.TextBlock)
    ).strip()
    if not text:
        raise RuntimeError("The model returned no text.")
    return text


def process(
    zulip: Zulip | None,
    number: int,
    dry_run: bool,
    wait_for_ci: bool = False,
    judged_before: datetime | None = None,
) -> None:
    if zulip is None:
        log("No Zulip credentials; skipping the check for an existing card.")
    else:
        # Checked first: most items a scan finds already have a card.
        topic = zulip.posted.card_topics.get(number)
        if topic is not None:
            log(f"#{number} already has a card in {topic!r}.")
            item = gather.fetch_item(number)
            if item is None or item.kind != "pr" or item.draft or item.author_is_maintainer:
                return
            post_status_update(zulip, item, dry_run, judged_before)
            suggest_reviewer_for_handoff(zulip, item, dry_run)
            return

    item = gather.fetch_item(number)
    if item is None:
        raise RuntimeError(f"#{number} not found")
    if item.draft:
        log(f"Skipping #{number}: draft PR.")
        return
    # PR cards wait for the PR's Zulip CI run, so the card can say
    # whether CI passed.
    if wait_for_ci and item.head_sha is not None:
        runs = gather.fetch_ci_workflow_runs(item.head_sha)
        if not runs or any(run.status != "completed" for run in runs):
            state = "none yet" if not runs else "queued or running"
            log(f"Skipping #{number} for now: its Zulip CI run hasn't finished ({state}).")
            return

    if item.author_is_maintainer:
        log(f"#{number} is by a maintainer; using the maintainer card.")
        body = maintainer_card(item)
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            notice("ANTHROPIC_API_KEY isn't configured; not posting.")
            return
        bot_input = assemble(gather.gather(item))
        body = call_claude(PROMPT_FILE.read_text(), bot_input)

    post(zulip, card_heading(item), body, dry_run)
    log(f"Posted the card for #{number}.")


def post(zulip: Zulip | None, message_heading: str, body: str, dry_run: bool) -> None:
    topic = topic_name(datetime.now(timezone.utc).date())
    # A horizontal rule separates consecutive messages in the week's topic.
    content = silence_mentions(message_heading + "\n\n" + body + "\n\n---")
    if dry_run:
        print(f"Topic: {topic}\n\n{content}")
    else:
        assert zulip is not None
        zulip.post(topic, content)
    if zulip is not None:
        zulip.posted.add(content, topic)


def asks_for_another_look(item: Item, request: StatusUpdateRequest) -> bool:
    answer = call_claude(READY_CHECK_PROMPT_FILE.read_text(), ready_check_input(item, request))
    return answer.partition("\n")[0].strip().lower() == "yes"


def suggest_reviewer(gathered: GatheredItem) -> str | None:
    """The "Possible reviewer" line, or None if the model's answer doesn't
    start with a maintainer."""
    maintainers = "\n".join(f"- @{login}" for login in sorted(MAINTAINERS, key=str.lower))
    prompt = REVIEWER_PROMPT_FILE.read_text().replace("{maintainers}", maintainers)
    answer = call_claude(prompt, assemble(gathered))
    match = REVIEWER_LINE.match(answer.partition("\n")[0].strip())
    if match is None or match["login"] not in MAINTAINERS:
        log(f"No usable reviewer suggestion in: {answer!r}")
        return None
    return f"Possible reviewer: {match['login']} ({match['reason']})"


def post_status_update(
    zulip: Zulip, item: Item, dry_run: bool, judged_before: datetime | None
) -> None:
    """Post a status update if the author of a "not ready" PR asked for
    another look since the feedback, and it isn't posted yet."""
    number = item.number
    if NOT_READY_LABEL not in item.labels:
        return
    if HAS_CONFLICTS_LABEL in item.labels:
        log(f"No status update for #{number}: it has conflicts.")
        return
    events = gather.fetch_timeline(gather.repository().get_issue(number))
    request = find_status_update_request(item, events, gather.comments_from_timeline(events))
    if request is None:
        return
    if judged_before is not None and request.author_comment.created_at < judged_before:
        log(f"No status update for #{number}: an earlier scan already judged the author's comment.")
        return
    comment_url = request.author_comment.url
    if comment_url in zulip.posted.status_update_comment_urls:
        log(f"Skipping the status update for #{number}: it is already posted.")
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        notice("ANTHROPIC_API_KEY isn't configured; no status update.")
        return
    if not asks_for_another_look(item, request):
        log(f"No status update for #{number}: the author's comment doesn't ask for one.")
        return

    gathered = gather.gather(item)
    bot_input = (
        assemble(gathered)
        + "\n"
        + "\n".join(status_update_lines(request, fetch_changes_lines(item, request)))
        + "\n"
    )
    answer = call_claude(STATUS_UPDATE_PROMPT_FILE.read_text(), bot_input)
    choice, _, rest = answer.partition("\n")
    choice = choice.strip()
    if choice == "NOTHING":
        log(f"No status update for #{number}: {rest.strip()}")
        return
    if choice == "CARD":
        # The status update's heading marks the comment as looked at.
        body = "The PR changed a lot since its card, so here is a new one.\n\n" + call_claude(
            PROMPT_FILE.read_text(), assemble(gathered)
        )
    elif choice == "NOTE":
        body = rest.strip()
        if NOTHING_MISSING in body and not item.assignees:
            reviewer = suggest_reviewer(gathered)
            if reviewer is not None:
                body += f"\n| 👤 | {reviewer} |"
    else:
        raise RuntimeError(f"The status update started with {choice!r}, not NOTHING, CARD or NOTE.")
    post(zulip, status_update_heading(item, comment_url), body, dry_run)
    log(f"Posted the status update for #{number}.")


def suggest_reviewer_for_handoff(zulip: Zulip, item: Item, dry_run: bool) -> None:
    """Post a reviewer suggestion if the PR has a review label and nobody
    is assigned, and the suggestion isn't posted yet."""
    number = item.number
    if HANDOFF_LABELS.isdisjoint(item.labels) or item.assignees:
        return
    if number in zulip.posted.reviewer_suggestions:
        log(f"Skipping the reviewer suggestion for #{number}: it is already posted.")
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        notice("ANTHROPIC_API_KEY isn't configured; no reviewer suggestion.")
        return
    reviewer = suggest_reviewer(gather.gather(item))
    if reviewer is None:
        return
    post(zulip, reviewer_heading(item), reviewer, dry_run)
    log(f"Posted the reviewer suggestion for #{number}.")


def launch_time() -> datetime:
    """When the bot started: the date of the oldest commit on main that
    touched the workflow file.  That file didn't exist before the bot."""
    commits = gather.repository().get_commits(sha="main", path=WORKFLOW_PATH)
    return commits.reversed[0].commit.committer.date


def last_scan_time() -> datetime | None:
    """When the last successful scheduled scan started.  Manual runs
    don't count, since one may have processed only one item."""
    workflow = gather.repository().get_workflow(Path(WORKFLOW_PATH).name)
    for run in workflow.get_runs(event="schedule", status="success"):
        return run.run_started_at
    return None


def scan(zulip: Zulip, dry_run: bool) -> list[int]:
    """Post cards, status updates and reviewer suggestions for the open
    items updated in the last SCAN_WINDOW.  Returns the items that
    failed."""
    since = datetime.now(timezone.utc) - SCAN_WINDOW
    # Items opened before the bot started get no card, so that old open
    # PRs don't each get one on their next update.
    query = (
        f"repo:{gather.REPO} is:open updated:>={since:%Y-%m-%dT%H:%M:%SZ}"
        f" created:>={launch_time():%Y-%m-%dT%H:%M:%SZ}"
    )
    # Oldest first, so the cards are in the order the items were opened.
    numbers = sorted(issue.number for issue in gather.search_issues(query, MAX_SEARCH_RESULTS))
    log(f"Found {len(numbers)} items updated since {since:%Y-%m-%d %H:%M} UTC.")
    judged_before = last_scan_time()
    failed = []
    for number in numbers:
        try:
            process(zulip, number, dry_run, wait_for_ci=True, judged_before=judged_before)
        except POST_ERRORS as e:
            notice(f"No card posted for #{number}: {e}.", level="error")
            failed.append(number)
    return failed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--item", type=int, help="process this issue or PR")
    target.add_argument(
        "--scan", action="store_true", help="process the recently updated issues and PRs"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the card and its topic instead of posting"
    )
    args = parser.parse_args()

    zulip = Zulip.from_env()
    if zulip is None and (args.scan or not args.dry_run):
        notice("Zulip bot credentials or channel aren't configured; not posting.")
        return
    try:
        if zulip is not None:
            zulip.load_posted()
        if args.scan:
            assert zulip is not None
            failed = scan(zulip, args.dry_run)
            if failed:
                numbers = ", ".join(f"#{number}" for number in failed)
                notice(f"No card posted for {numbers}. Run the bot again to retry.", level="error")
                sys.exit(1)
        else:
            process(zulip, args.item, args.dry_run)
    except POST_ERRORS as e:
        notice(f"No card posted: {e}. Run the bot again to retry.", level="error")
        sys.exit(1)


if __name__ == "__main__":
    main()
