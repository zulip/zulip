#!/usr/bin/env python3
"""Post a triage card for a zulip/zulip issue or PR to chat.zulip.org.

The bot is read-only on GitHub.  For each item it posts one message
(a "card") to a topic named after the item in a private channel.
Maintainers' items get a short status card; other items get a card
written by Claude from the input that assemble.py builds.

Locally:

  triage_bot.py --item N --dry-run   print the card and its topic

Configuration comes from the environment: ZULIP_TRIAGE_BOT_EMAIL,
ZULIP_TRIAGE_BOT_API_KEY, ZULIP_TRIAGE_CHANNEL and ANTHROPIC_API_KEY.
`gh` must be logged in, or have GH_TOKEN set.
"""

import argparse
import base64
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(TOOLS_DIR))

from tools.triage_bot import gather
from tools.triage_bot.assemble import JSONDict, assemble
from tools.triage_bot.retry import RETRY_STATUSES, RequestFailedError, urlopen_with_retries

MODEL = "claude-opus-5-5"
PROMPT_FILE = Path(__file__).resolve().parent / "prompt.md"
MAX_TOPIC_NAME_LENGTH = 60
MAX_MESSAGE_LENGTH = 10000


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def notice(message: str, level: str = "notice") -> None:
    # Shown as an annotation on the workflow run.
    print(
        f"::{level}::{message}" if os.environ.get("GITHUB_ACTIONS") else message,
        file=sys.stderr,
        flush=True,
    )


# --- Zulip ---


class Zulip:
    def __init__(self, email: str, api_key: str, channel: str) -> None:
        self.email = email
        self.channel = channel
        token = base64.b64encode(f"{email}:{api_key}".encode()).decode()
        self.auth = f"Basic {token}"

    @classmethod
    def from_env(cls) -> "Zulip | None":
        email = os.environ.get("ZULIP_TRIAGE_BOT_EMAIL")
        api_key = os.environ.get("ZULIP_TRIAGE_BOT_API_KEY")
        channel = os.environ.get("ZULIP_TRIAGE_CHANNEL")
        if not (email and api_key and channel):
            return None
        return cls(email, api_key, channel)

    def request(self, method: str, path: str, params: dict[str, str]) -> JSONDict:
        data = urllib.parse.urlencode(params)
        url = f"{gather.CZO}/api/v1/{path}"
        body = None
        if method == "GET":
            url += "?" + data
        else:
            body = data.encode()
        req = urllib.request.Request(
            url, data=body, method=method, headers={"Authorization": self.auth}
        )
        # A POST that timed out may have posted, and retrying it would
        # post twice, so only GETs retry after a server or network error.
        retry_statuses = RETRY_STATUSES if method == "GET" else {429}
        return json.loads(
            urlopen_with_retries(
                req,
                what=f"Zulip {method} {path}",
                attempts=3,
                base_delay=5,
                max_delay=30,
                timeout=60,
                retry_statuses=retry_statuses,
                retry_network_errors=method == "GET",
            )
        )

    def post(self, topic: str, content: str) -> None:
        self.request(
            "POST",
            "messages",
            {"type": "stream", "to": self.channel, "topic": topic, "content": content},
        )


def topic_name(number: int, title: str) -> str:
    # Zulip rejects topic names with tabs, newlines or other control
    # characters; see is_character_printable in zerver/lib/string_validation.py.
    title = "".join(" " if unicodedata.category(c) in ("Cc", "Cs") else c for c in title)
    title = re.sub(r"\s+", " ", title).strip()
    topic = f"#{number} {title}"
    if len(topic) > MAX_TOPIC_NAME_LENGTH:
        topic = topic[: MAX_TOPIC_NAME_LENGTH - 1].rstrip() + "…"
    return topic


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
    messages = zulip.request(
        "GET",
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
        first_line = message["content"].split("\n", 1)[0]
        if first_line.startswith(f"**[#{number} ") and first_line.endswith(f"/{number})**"):
            return message["subject"]
    return None


# --- the card ---


def heading(item: JSONDict) -> str:
    lines = [f"**[#{item['number']} {item['title']}]({item['url']})**"]
    if item["labels"]:
        lines.append(" · ".join(f"`{label}`" for label in item["labels"]))
    return "\n".join(lines)


def maintainer_card(item: JSONDict) -> str:
    """A card with no LLM call: maintainers triage their own items."""
    kind = "PR" if item["kind"] == "pr" else "issue"
    return f"**Maintainer {kind} from {item['author']}. Nothing to triage.**"


def call_claude(api_key: str, model: str, bot_input: str) -> str:
    payload = json.dumps(
        {
            "model": model,
            "max_tokens": 16000,
            "system": PROMPT_FILE.read_text(),
            "messages": [{"role": "user", "content": bot_input}],
        }
    ).encode()
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=payload, headers=headers, method="POST"
    )
    # Five attempts, with random waits of 5-10s, 10-20s, 20-40s and 40-80s between them.
    response = json.loads(
        urlopen_with_retries(
            req,
            what="Anthropic API call",
            attempts=5,
            base_delay=10,
            max_delay=120,
            timeout=600,
        )
    )
    if response.get("stop_reason") == "refusal":
        raise RuntimeError(f"The model declined to write a card: {response.get('stop_details')}")
    if response.get("stop_reason") == "max_tokens":
        log("The model hit max_tokens; the card may be cut off.")
    text = "".join(
        b["text"] for b in response.get("content", []) if b.get("type") == "text"
    ).strip()
    if not text:
        raise RuntimeError("The model returned no text.")
    return text


def fit_message(content: str) -> str:
    if len(content) <= MAX_MESSAGE_LENGTH:
        return content
    suffix = "\n\n*(trimmed to fit Zulip's message limit)*"
    content = content[: MAX_MESSAGE_LENGTH - len(suffix) - 5].rstrip()
    if content.count("```") % 2:
        content += "\n```"
    return content + suffix


# --- processing one item ---


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
    if item["kind"] == "pr" and item["draft"]:
        log(f"Skipping #{number}: draft PR.")
        return

    if item["maintainer_author"]:
        log(f"#{number} is by a maintainer; using the maintainer card.")
        body = maintainer_card(item)
    else:
        start = time.time()
        bot_input = assemble(gather.gather(item))
        log(
            f"Gathered #{number} in {time.time() - start:.0f}s ({len(bot_input)} characters of input)."
        )
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            notice("ANTHROPIC_API_KEY isn't configured; not posting.")
            return
        body = call_claude(api_key, MODEL, bot_input)

    topic = topic_name(number, item["title"])
    content = fit_message(heading(item) + "\n\n" + body)
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
    except (RequestFailedError, RuntimeError) as e:
        notice(f"No card posted: {e}. Re-run the workflow to try again.", level="error")
        sys.exit(1)


if __name__ == "__main__":
    main()
