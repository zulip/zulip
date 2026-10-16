#!/usr/bin/env -S uv run --script --frozen --only-group release-tools
"""Post a triage card for a zulip/zulip issue or PR to chat.zulip.org.

The bot is read-only on GitHub.  For each item it posts one message
(a "card") to the current week's topic in a private channel.
Maintainers' items get a one-line card.  Other items get a card
written by Claude from the input that assemble.py builds.

In GitHub Actions (see .github/workflows/triage-bot.yml):

  triage_bot.py --scan     post cards for recently updated items that
                           don't have one yet
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
from tools.triage_bot.assemble import assemble, kind_name
from tools.triage_bot.gather import Item, JSONDict, log

MODEL = "claude-opus-5-5"
PROMPT_FILE = Path(__file__).resolve().parent / "prompt.md"
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


# The first line of card_heading().  An item's URL ends with its number.
CARD_HEADING = re.compile(r"\*\*\[#(?P<number>\d+) .*/(?P=number)\)\*\*")


@dataclass
class PostedMessages:
    """What the bot posted in the cards channel, read from each message's first line."""

    card_topics: dict[int, str] = field(default_factory=dict)

    def add(self, content: str, topic: str) -> None:
        """Call this newest first, so an item keeps its newest card's topic."""
        line = content.partition("\n")[0]
        if match := CARD_HEADING.fullmatch(line):
            self.card_topics.setdefault(int(match["number"]), topic)


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
        raise RuntimeError(f"The model declined to write a card: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        log("The model hit max_tokens; the card may be cut off.")
    text = "".join(
        block.text for block in response.content if isinstance(block, anthropic.types.TextBlock)
    ).strip()
    if not text:
        raise RuntimeError("The model returned no text.")
    return text


def process(zulip: Zulip | None, number: int, dry_run: bool, wait_for_ci: bool = False) -> None:
    if zulip is None:
        log("No Zulip credentials; skipping the check for an existing card.")
    else:
        # Checked first: most items a scan finds already have a card.
        topic = zulip.posted.card_topics.get(number)
        if topic is not None:
            log(f"Skipping #{number}: it already has a card in {topic!r}.")
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


def launch_time() -> datetime:
    """When the bot started: the date of the oldest commit on main that
    touched the workflow file.  That file didn't exist before the bot."""
    commits = gather.repository().get_commits(sha="main", path=WORKFLOW_PATH)
    return commits.reversed[0].commit.committer.date


def scan(zulip: Zulip, dry_run: bool) -> list[int]:
    """Post cards for the open items updated in the last SCAN_WINDOW that
    don't have one yet.  Returns the items whose card failed."""
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
    failed = []
    for number in numbers:
        try:
            process(zulip, number, dry_run, wait_for_ci=True)
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
