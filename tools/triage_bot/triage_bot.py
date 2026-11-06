#!/usr/bin/env -S uv run --script --frozen --only-group release-tools
"""Post a triage card for a zulip/zulip issue or PR to chat.zulip.org.

The bot is read-only on GitHub.  For each item it posts one message
(a "card") to the current week's topic in a private channel.
Maintainers' items get a short status card; other items get a card
written by Claude from the input that assemble.py builds.

In GitHub Actions (see .github/workflows/triage-bot.yml):

  triage_bot.py --resolve-event   decide whether the event needs a card,
                                  and write the item number to GITHUB_OUTPUT
  triage_bot.py --item N

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
WORKFLOW_PATH = ".github/workflows/triage-bot.yml"


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
        # Checked first: this runs on every Zulip CI completion, and most
        # of those are for PRs that already have a card.
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


def launch_time() -> datetime:
    """This finds the oldest commit on main that touched the workflow file.
    That file didn't exist before the bot, so that commit is when the bot
    started.
    """
    commits = gather.repository().get_commits(sha="main", path=WORKFLOW_PATH)
    return commits.reversed[0].commit.committer.date


# Items opened before the bot started get no card, so that old open PRs
# don't each get one on their next push.
def opened_before_launch(number: int, created_at: datetime) -> bool:
    launched_at = launch_time()
    if created_at < launched_at:
        log(f"Skipping #{number}: opened before the bot started at {launched_at}.")
        return True
    return False


def skip_pr(zulip: Zulip, number: int, created_at: datetime, draft: bool) -> bool:
    """Whether the PR gets no card now."""
    if opened_before_launch(number, created_at):
        return True
    if draft:
        log(f"Skipping #{number}: draft PR.")
        return True
    if existing_card_topic(zulip, number) is not None:
        log(f"Skipping #{number}: it already has a card.")
        return True
    return False


def resolve_event() -> int | None:
    """The item to process, or None when there's nothing to post.

    PR cards wait for the PR's first Zulip CI run, so the CI result can
    be in the card.  The workflow_run event posts when that run finishes;
    a PR marked ready after CI finished posts right away.
    The workflow skips cancelled runs.
    """
    name = os.environ["GITHUB_EVENT_NAME"]
    payload = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    zulip = Zulip.from_env()
    if zulip is None:
        notice("Zulip bot credentials or channel aren't configured; skipping.")
        return None

    match name:
        case "issues":
            issue = payload["issue"]
            if opened_before_launch(issue["number"], gather.parse_github_time(issue["created_at"])):
                return None
            return issue["number"]

        case "workflow_dispatch":
            return int(payload["inputs"]["item"])

        case "pull_request_target":
            pr = payload["pull_request"]
            number = pr["number"]
            if skip_pr(zulip, number, gather.parse_github_time(pr["created_at"]), pr["draft"]):
                return None
            runs = gather.fetch_ci_workflow_runs(pr["head"]["sha"])
            if not runs or any(run.status != "completed" for run in runs):
                state = "none yet" if not runs else "queued or running"
                log(
                    f"Skipping #{number} for now: its Zulip CI run hasn't finished ({state}); "
                    "the workflow_run event will post the card."
                )
                return None
            return number

        case "workflow_run":
            workflow_run = payload["workflow_run"]
            if workflow_run["event"] != "pull_request":
                log(f"Skipping: Zulip CI run for a {workflow_run['event']} event.")
                return None
            if workflow_run["head_repository"] is None:
                log("Skipping: the PR's fork was deleted.")
                return None
            # workflow_run.pull_requests is empty for PRs from forks, so find
            # the PR from its head branch.
            fork_owner = workflow_run["head_repository"]["owner"]["login"]
            head = f"{fork_owner}:{workflow_run['head_branch']}"
            open_prs = gather.repository().get_pulls(state="open", head=head)
            prs = [open_pr for open_pr in open_prs if open_pr.head.sha == workflow_run["head_sha"]]
            if not prs:
                log(f"Skipping: no open PR has {workflow_run['head_sha']} as its head.")
                return None
            # Two open PRs with the same head commit share one CI run; only the first gets a card.
            pr = prs[0]
            if skip_pr(zulip, pr.number, pr.created_at, pr.draft):
                return None
            return pr.number

        case _:
            log(f"Skipping: unexpected event {name}.")
            return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--item", type=int, help="process this issue or PR")
    parser.add_argument(
        "--resolve-event", action="store_true", help="read the GitHub Actions event"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the card and its topic instead of posting"
    )
    args = parser.parse_args()

    if not args.resolve_event and args.item is None:
        parser.error("--item or --resolve-event is required")
    try:
        if args.resolve_event:
            number = resolve_event()
            if number is not None:
                log(f"Processing #{number}.")
                with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                    f.write(f"number={number}\n")
        else:
            process(args.item, args.dry_run)
    except (requests.RequestException, GithubException, anthropic.APIError, RuntimeError) as e:
        notice(f"No card posted: {e}. Run the bot again to retry.", level="error")
        sys.exit(1)


if __name__ == "__main__":
    main()
