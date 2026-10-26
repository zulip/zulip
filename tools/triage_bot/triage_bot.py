#!/usr/bin/env -S uv run --script --frozen --only-group release-tools
"""Post a triage card for a zulip/zulip issue or PR to chat.zulip.org.

The bot is read-only on GitHub.  For each item it posts one message
(a "card") to the current week's topic in a private channel.
Maintainers' items get a short status card; other items get a card
written by Claude from the input that assemble.py builds.

Locally:

  triage_bot.py --item N --dry-run   print the card and its topic

Configuration comes from the environment: ZULIP_TRIAGE_BOT_EMAIL,
ZULIP_TRIAGE_BOT_API_KEY, ZULIP_TRIAGE_CHANNEL and ANTHROPIC_API_KEY.
GH_TOKEN must be set to a GitHub token.
"""

import argparse
import json
import os
import sys
import time
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


def existing_card_topic(zulip: Zulip, number: int) -> str | None:
    """The topic of the item's card, found by the card's first line, so a
    renamed topic still counts."""
    # Zulip's search doesn't index link URLs, so this searches for the
    # number in the heading's link text, then checks each heading.
    narrow = [
        {"operator": "channel", "operand": zulip.channel},
        {"operator": "sender", "operand": zulip.email},
        {"operator": "search", "operand": f"#{number}"},
    ]
    messages = zulip.get(
        "messages",
        {
            "anchor": "newest",
            "num_before": "100",
            "num_after": "0",
            "apply_markdown": "false",
            "narrow": json.dumps(narrow),
        },
    )["messages"]
    for message in messages:
        if is_card_heading(message["content"].partition("\n")[0], number):
            return message["subject"]
    return None


def is_card_heading(line: str, number: int) -> bool:
    """Whether the line is the heading() of the item's card."""
    return line.startswith(f"**[#{number} ") and line.endswith(f"/{number})**")


def heading(item: Item) -> str:
    lines = [f"**[#{item.number} {item.title}]({item.url})**"]
    if item.labels:
        lines.append(" · ".join(f"`{label}`" for label in item.labels))
    return "\n".join(lines)


def silence_mentions(content: str) -> str:
    """Turn every user, group and wildcard mention into a silent mention.

    The title and the model's text come from what the item's author
    wrote, so they could mention anyone, even @**all**.
    """
    return content.replace("@*", "@_*")


def maintainer_card(item: Item) -> str:
    """A card with no LLM call: maintainers triage their own items."""
    return f"**Maintainer {kind_name(item.kind)} from {item.author}. Nothing to triage.**"


def call_claude(bot_input: str) -> str:
    # Five attempts in all; the SDK waits between them with backoff.
    client = anthropic.Anthropic(max_retries=4, timeout=600)
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=PROMPT_FILE.read_text(),
        messages=[{"role": "user", "content": bot_input}],
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


def process(number: int, dry_run: bool) -> None:
    zulip = Zulip.from_env()
    if zulip is None:
        if not dry_run:
            notice("Zulip bot credentials or channel aren't configured; not posting.")
            return
        log("No Zulip credentials; skipping the check for an existing card.")
    else:
        topic = existing_card_topic(zulip, number)
        if topic is not None:
            log(f"Skipping #{number}: it already has a card in {topic!r}.")
            return

    item = gather.fetch_item(number)
    if item is None:
        raise RuntimeError(f"#{number} not found")
    if item.kind == "pr" and item.draft:
        log(f"Skipping #{number}: draft PR.")
        return

    if item.author_is_maintainer:
        log(f"#{number} is by a maintainer; using the maintainer card.")
        body = maintainer_card(item)
    else:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            notice("ANTHROPIC_API_KEY isn't configured; not posting.")
            return
        start = time.time()
        bot_input = assemble(gather.gather(item))
        log(
            f"Gathered #{number} in {time.time() - start:.0f}s ({len(bot_input)} characters of input)."
        )
        body = call_claude(bot_input)

    topic = topic_name(datetime.now(timezone.utc).date())
    # The rule separates consecutive cards in the week's topic.
    content = silence_mentions(heading(item) + "\n\n" + body + "\n\n---")
    if dry_run:
        print(f"Topic: {topic}\n\n{content}")
        return
    assert zulip is not None
    zulip.post(topic, content)
    log(f"Posted the card for #{number} to {topic!r}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--item", type=int, required=True, help="process this issue or PR")
    parser.add_argument(
        "--dry-run", action="store_true", help="print the card and its topic instead of posting"
    )
    args = parser.parse_args()

    try:
        process(args.item, args.dry_run)
    except (requests.RequestException, GithubException, anthropic.APIError, RuntimeError) as e:
        notice(f"No card posted: {e}. Run the bot again to retry.", level="error")
        sys.exit(1)


if __name__ == "__main__":
    main()
