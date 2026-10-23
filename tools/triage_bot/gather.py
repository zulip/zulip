"""Gather what the triage bot reads about one zulip/zulip item.

Lookups are mechanical: the GitHub API through the `gh` CLI, the
chat.zulip.org spectator API, and the git log of a local checkout.
`gather()` returns a dict that assemble.py turns into the bot input.

All requests to GitHub are reads.  The GraphQL queries go through
`gh api graphql`, which sends them as POST requests, but they are
queries, not mutations.
"""

import json
import math
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict, TypeVar

from tools.triage_bot.assemble import (
    AUTHOR_ISSUES_SHOWN,
    AUTHOR_PRS_SHOWN,
    CZO_MESSAGES_SHOWN,
    JSONDict,
)
from tools.triage_bot.retry import RequestFailedError, backoff_delay, urlopen_with_retries

REPO = "zulip/zulip"
REPO_OWNER, REPO_NAME = REPO.split("/")
CI_WORKFLOW_FILE = "zulip-ci.yml"
CZO = "https://chat.zulip.org"
# The checkout whose git log at HEAD is used for reviewer candidates.
# In the workflow, HEAD is the default branch; locally, the current branch.
ZULIP_CHECKOUT = str(Path(__file__).resolve().parents[2])
BOT_LOGINS = {
    "zulipbot",
    "github-actions",
    "dependabot",
    "codecov",
    "github-actions[bot]",
    "dependabot[bot]",
}
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
RECENTLY_CLOSED_DAYS = 45
LINKED_ITEM_REF = re.compile(
    r"(?<![\w/#-])#(?P<number>\d{3,5})\b"
    r"|\b(?P<repo>[\w.-]+/[\w.-]+)#(?P<repo_number>\d+)\b"
    r"|github\.com/(?P<link_repo>[\w.-]+/[\w.-]+)/(?:issues|pull)/(?P<link_number>\d+)\b"
)
# Only a spam description would link more than this.
MAX_LINKED_ITEMS = 10
CZO_EXCLUDED_CHANNELS = {
    "commits",
    "deployments",
    "github",
    "test here",
    "automated testing",
    "errors",
    "devel",
}
# The bot input shows only the best chat.zulip.org thread.
CZO_THREADS_SHOWN = 1
STOP_WORDS = {
    "with",
    "from",
    "when",
    "that",
    "this",
    "into",
    "issue",
    "fixes",
    "fix",
    "should",
    "does",
    "doesn't",
    "dont",
    "don't",
    "have",
    "make",
    "made",
    "being",
    "about",
    "after",
    "before",
    "their",
    "there",
    "them",
    "they",
    "then",
    "than",
    "also",
    "only",
    "more",
    "most",
    "some",
    "such",
    "which",
    "while",
    "would",
    "could",
    "your",
    "what",
    "using",
    "used",
    "user",
    "users",
    "zulip",
    "support",
    "handle",
    "handles",
    "handling",
    "allow",
    "add",
    "adds",
    "added",
    "remove",
    "removes",
    "update",
    "updates",
    "change",
    "changes",
    "show",
    "shows",
}


def log(message: str) -> None:
    print(message, file=sys.stderr)


def parse_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def state_of(x: JSONDict) -> str:
    if x.get("merged_at"):
        return "merged"
    if x.get("closed_at"):
        return "closed"
    return "open"


# --- GitHub ---


GH_ATTEMPTS = 4


# How many lookups have failed so far, so gather() can tell which parts
# of the bot input are incomplete.
failed_lookups = 0

T = TypeVar("T")


def note_failed_lookup() -> None:
    global failed_lookups
    failed_lookups += 1


def complete_lookup(f: Callable[[], T]) -> tuple[T, bool]:
    """f's result, and whether none of its lookups failed."""
    before = failed_lookups
    result = f()
    return result, failed_lookups == before


def gh(*args: str) -> object:
    """`gh` output as JSON, or None if the call failed."""
    for attempt in range(GH_ATTEMPTS):
        out = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
        if out.returncode == 0:
            return json.loads(out.stdout) if out.stdout.strip() else None
        if "not found" in out.stderr.lower() or "HTTP 404" in out.stderr:
            return None
        if attempt == GH_ATTEMPTS - 1:
            log(f"gh {' '.join(args)[:160]} failed: {out.stderr[:300]}")
            note_failed_lookup()
            return None
        # `gh` doesn't show the Retry-After header, so this is plain backoff.
        delay = backoff_delay(attempt, base_delay=10, max_delay=60)
        log(f"gh {' '.join(args)[:80]}: {out.stderr.strip()[:200]}; retrying in {delay:.0f}s")
        time.sleep(delay)
    return None


def api(path: str) -> object:
    # `gh api -f` would turn this into a POST, so query strings go in the path.
    return gh("api", "-X", "GET", path)


def api_pages(path: str, limit_pages: int = 20) -> list[JSONDict]:
    sep = "&" if "?" in path else "?"
    out: list[JSONDict] = []
    for page in range(1, limit_pages + 1):
        chunk = api(f"{path}{sep}per_page=100&page={page}")
        if not isinstance(chunk, list):
            break
        out += chunk
        if len(chunk) < 100:
            break
    return out


def graphql(query: str, **variables: object) -> JSONDict:
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        args += ["-F", f"{key}={value}"]
    result = gh(*args)
    return result.get("data") or {} if isinstance(result, dict) else {}


_last_search = 0.0


def search_issues(query: str, per_page: int = 50, newest_first: bool = True) -> list[JSONDict]:
    global _last_search
    # The search API allows 30 requests a minute.
    wait = 2.1 - (time.time() - _last_search)
    if wait > 0:
        time.sleep(wait)
    _last_search = time.time()
    q = urllib.parse.quote(query)
    sort = "&sort=created&order=desc" if newest_first else ""
    result = api(f"search/issues?q={q}&per_page={per_page}{sort}")
    return result.get("items", []) if isinstance(result, dict) else []


def user_login(u: JSONDict | None) -> str:
    return (u or {}).get("login") or "ghost"


def is_bot_user(u: JSONDict | None) -> bool:
    return user_login(u) in BOT_LOGINS or (u or {}).get("type") == "Bot"


def user_name(login: str) -> str:
    user = api(f"users/{login}")
    name = (user or {}).get("name") if isinstance(user, dict) else None
    return (name or login).strip()


def timeline(number: int, repo: str = REPO) -> list[JSONDict]:
    return api_pages(f"repos/{repo}/issues/{number}/timeline", limit_pages=15)


def comments_from_timeline(events: list[JSONDict]) -> list[JSONDict]:
    """Comments and reviews with bodies, oldest first."""
    out = []
    for ev in events:
        kind = ev.get("event")
        if kind == "commented":
            who = ev.get("user") or ev.get("actor")
            created = ev.get("created_at")
        elif kind == "reviewed" and (ev.get("body") or "").strip():
            who = ev.get("user")
            created = ev.get("submitted_at")
        else:
            continue
        if not created:
            continue
        out.append(
            {
                "who": user_login(who),
                "association": ev.get("author_association", "NONE"),
                "maintainer": user_login(who) in MAINTAINERS,
                "bot": is_bot_user(who),
                "kind": "review" if kind == "reviewed" else "comment",
                "review_state": ev.get("state") if kind == "reviewed" else None,
                "created": created,
                "body": ev.get("body") or "",
            }
        )
    return out


def cross_refs(events: list[JSONDict]) -> list[JSONDict]:
    """Issues and PRs in this repository that reference the item."""
    out = []
    for ev in events:
        if ev.get("event") != "cross-referenced":
            continue
        src = (ev.get("source") or {}).get("issue") or {}
        if not src.get("number") or (src.get("repository") or {}).get("full_name", REPO) != REPO:
            continue
        out.append({"number": src["number"], "kind": "pr" if "pull_request" in src else "issue"})
    return out


ITEM_QUERY = """query($owner:String!,$name:String!,$n:Int!){repository(owner:$owner,name:$name){issueOrPullRequest(number:$n){
  __typename
  ... on Issue { title body url createdAt closedAt state author{login} authorAssociation
    labels(first:50){nodes{name}} assignees(first:10){nodes{login}} }
  ... on PullRequest { title body url createdAt closedAt mergedAt state isDraft author{login} authorAssociation
    headRefOid additions deletions
    labels(first:50){nodes{name}} assignees(first:10){nodes{login}}
    reviewRequests(first:10){nodes{requestedReviewer{... on User{login}}}}
    files(first:100){nodes{path}}
    commits(first:100){nodes{commit{messageHeadline}}} }
}}}"""


def fetch_item(number: int) -> JSONDict | None:
    """The item's current state: cheap, and enough for a maintainer card."""
    node, complete = complete_lookup(
        lambda: (
            graphql(ITEM_QUERY, owner=REPO_OWNER, name=REPO_NAME, n=number).get("repository") or {}
        ).get("issueOrPullRequest")
    )
    if not complete:
        raise RequestFailedError(f"Couldn't load #{number} from GitHub")
    if not node:
        return None
    is_pr = node["__typename"] == "PullRequest"
    author = user_login(node.get("author"))
    item = {
        "number": number,
        "kind": "pr" if is_pr else "issue",
        "url": node["url"],
        "title": node["title"].strip(),
        "author": author,
        "author_association": node["authorAssociation"],
        "maintainer_author": author in MAINTAINERS,
        "opened": node["createdAt"],
        "state": "merged" if node.get("mergedAt") else node["state"].lower(),
        "labels": [x["name"] for x in node["labels"]["nodes"]],
        "assignees": [x["login"] for x in node["assignees"]["nodes"]],
        "body": node.get("body") or "",
    }
    if is_pr:
        item["draft"] = node["isDraft"]
        item["head_sha"] = node["headRefOid"]
        item["review_requested"] = [
            r["requestedReviewer"]["login"]
            for r in node["reviewRequests"]["nodes"]
            if r.get("requestedReviewer") and r["requestedReviewer"].get("login")
        ]
        item["additions"], item["deletions"] = node["additions"], node["deletions"]
        item["files"] = [f["path"] for f in node["files"]["nodes"]]
        item["commits"] = [c["commit"]["messageHeadline"] for c in node["commits"]["nodes"]]
    return item


def linked_item_refs(text: str) -> list[tuple[str, int]]:
    """The (repository, number) of each issue or PR the text refers to, in order."""
    refs = []
    for m in LINKED_ITEM_REF.finditer(text):
        if m["number"]:
            refs.append((REPO, int(m["number"])))
        elif m["repo"]:
            refs.append((m["repo"], int(m["repo_number"])))
        else:
            refs.append((m["link_repo"], int(m["link_number"])))
    return refs


def small_item(number: int, repo: str = REPO, *, with_files: bool = False) -> JSONDict | None:
    """A linked issue or PR, or an earlier attempt.

    None if it doesn't exist or isn't public.
    """
    it = api(f"repos/{repo}/issues/{number}")
    if not isinstance(it, dict):
        return None
    events = timeline(number, repo)
    out = {
        "number": number,
        "repo": repo,
        "ref": f"#{number}" if repo == REPO else f"{repo}#{number}",
        "kind": "pr" if "pull_request" in it else "issue",
        "title": it["title"],
        "author": user_login(it.get("user")),
        "author_association": it.get("author_association"),
        "created": it["created_at"],
        "closed_at": it.get("closed_at"),
        "merged_at": (it.get("pull_request") or {}).get("merged_at"),
        "labels": [x["name"] for x in it.get("labels", [])],
        "assignees": [user_login(x) for x in it.get("assignees", [])],
        "body": it.get("body") or "",
        "comments": comments_from_timeline(events),
        "cross_refs": cross_refs(events),
    }
    out["state"] = state_of(out)
    if out["kind"] == "pr" and with_files:
        out["files"] = [f["filename"] for f in api_pages(f"repos/{repo}/pulls/{number}/files", 5)]
    return out


# --- chat.zulip.org ---

_last_czo = 0.0


def czo_get(
    narrow: list[dict[str, object]],
    anchor: str = "newest",
    before: int = 100,
    after: int = 0,
    note_failure: bool = True,
) -> JSONDict:
    global _last_czo
    wait = 0.7 - (time.time() - _last_czo)
    if wait > 0:
        time.sleep(wait)
    _last_czo = time.time()
    narrow = [{"operator": "channels", "operand": "web-public"}, *narrow]
    params = urllib.parse.urlencode(
        {
            "narrow": json.dumps(narrow),
            "anchor": anchor,
            "num_before": before,
            "num_after": after,
            "apply_markdown": "false",
        }
    )
    request = urllib.request.Request(f"{CZO}/json/messages?{params}")
    try:
        body = urlopen_with_retries(
            request,
            what="chat.zulip.org messages request",
            attempts=3,
            base_delay=5,
            max_delay=30,
            timeout=40,
        )
    except RequestFailedError as e:
        log(f"{e}; continuing without these messages")
        if note_failure:
            note_failed_lookup()
        return {}
    return json.loads(body)


def czo_message(m: JSONDict) -> JSONDict:
    return {
        "sender": m["sender_full_name"],
        "bot": "-bot@" in m.get("sender_email", "")
        or m.get("sender_email", "").startswith("notification-bot"),
        "time": iso(datetime.fromtimestamp(m["timestamp"], timezone.utc)),
        "content": m["content"][:3000],
    }


def czo_thread(channel_id: int, topic: str) -> JSONDict:
    narrow: list[dict[str, object]] = [
        {"operator": "channel", "operand": channel_id},
        {"operator": "topic", "operand": topic},
    ]
    result = czo_get(narrow, before=CZO_MESSAGES_SHOWN)
    msgs = result.get("messages", [])
    return {
        "channel_id": channel_id,
        "channel": msgs[0]["display_recipient"] if msgs else "",
        "topic": topic,
        "messages": [czo_message(m) for m in msgs],
        "whole": result.get("found_oldest", True),
    }


CZO_LINK = re.compile(rf"{re.escape(CZO)}/#narrow/\S+")
TRAILING_PUNCTUATION = ")]}>,;:!?'\"*."

# Copied from parse_narrow_url in zerver/lib/url_decoding.py, which
# needs Django.  Keep the two in sync.
OPERATOR_SYNONYMS = {
    "stream": "channel",
    "streams": "channels",
    "pm-with": "dm",
    "group-pm-with": "dm-including",
    "from": "sender",
    "subject": "topic",
}


class NarrowTerm(TypedDict):
    operator: str
    operand: str | int | list[int]
    negated: bool


def canonicalize_operator_synonyms(text: str) -> str:
    text = text.lower()
    if text in OPERATOR_SYNONYMS.values():
        return text
    if text in OPERATOR_SYNONYMS:
        return OPERATOR_SYNONYMS[text]
    return text


def parse_recipient_slug(slug: str) -> tuple[int | list[int], str] | None:
    try:
        ids_string, suffix = slug.split("-", maxsplit=1)
        ids = [int(id) for id in ids_string.split(",")]
        return (ids if len(ids) > 1 else ids[0], suffix)
    except ValueError:
        return None


def decode_hash_component(string: str) -> str:
    return urllib.parse.unquote(string.replace(".", "%"))


def decode_narrow_operand(operator: str, operand: str) -> str | int | list[int]:
    if operator in ["dm-including", "dm", "mentions", "sender", "channel"]:
        result = parse_recipient_slug(operand)
        return result[0] if isinstance(result, tuple) else ""

    if operator == "near":
        return int(operand) if operand.isdigit() else ""

    operand = decode_hash_component(operand).strip()

    return operand


def parse_narrow_url(narrow_url: str) -> list[NarrowTerm] | None:
    fragment = urllib.parse.urlsplit(narrow_url).fragment
    fragment_parts = fragment.split("/")

    terms: list[NarrowTerm] = []

    for i in range(1, len(fragment_parts), 2):
        raw_operator = decode_hash_component(fragment_parts[i]).strip()

        if not raw_operator:
            return None

        negated = False
        if raw_operator.startswith("-"):
            negated = True
            raw_operator = raw_operator[1:]
        operator = canonicalize_operator_synonyms(raw_operator)

        try:
            raw_operand = fragment_parts[i + 1]
        except IndexError:
            raw_operand = ""
        operand = decode_narrow_operand(operator, raw_operand)

        if operand == "" and operator != "topic":
            return None

        terms.append({"operator": operator, "operand": operand, "negated": negated})
    return terms


def czo_links(text: str) -> list[str]:
    return [link.rstrip(TRAILING_PUNCTUATION) for link in CZO_LINK.findall(text)]


def conversation_operands(link: str) -> dict[str, str | int | list[int]] | None:
    """The operands of a link to a conversation, or None for other links."""
    terms = parse_narrow_url(link)
    if terms is None:
        return None
    operands = {t["operator"]: t["operand"] for t in terms if not t["negated"]}
    if "with" in operands or "near" in operands or ("channel" in operands and "topic" in operands):
        return operands
    return None


def find_conversation(operands: dict[str, str | int | list[int]]) -> tuple[int, str] | None:
    """The channel ID and topic of the conversation now, or None if it can't be read."""
    # A link to a private channel or a deleted message fails, and is
    # listed as unread rather than marking the CZO section incomplete.
    message_id = operands.get("with") or operands.get("near")
    if message_id:
        # The "with" operator finds the message's conversation even after
        # the topic was renamed, resolved or moved.
        msgs = czo_get(
            [{"operator": "with", "operand": message_id}],
            anchor=str(message_id),
            before=0,
            after=0,
            note_failure=False,
        ).get("messages", [])
        if msgs:
            return msgs[0]["stream_id"], msgs[0]["subject"]
    channel = operands.get("channel")
    topic = operands.get("topic")
    if isinstance(channel, int) and isinstance(topic, str):
        narrow: list[dict[str, object]] = [
            {"operator": "channel", "operand": channel},
            {"operator": "topic", "operand": topic},
        ]
        if czo_get(narrow, before=1, note_failure=False).get("messages"):
            return channel, topic
    return None


def czo_search(operand: str) -> list[JSONDict]:
    return czo_get([{"operator": "search", "operand": operand}], before=60).get("messages", [])


def title_words(title: str, n: int = 4) -> list[str]:
    # Short all-caps words like UI, DM and API are kept.
    words = re.findall(r"[A-Za-z][A-Za-z'-]{3,}|\b[A-Z]{2,3}s?\b", re.sub(r"`[^`]*`", " ", title))
    return [w for w in dict.fromkeys(w.lower() for w in words) if w not in STOP_WORDS][:n]


def title_terms(title: str, vocab: set[str]) -> set[str]:
    """Content words of a title, for comparing titles.

    Adjacent words whose concatenation is a word in `vocab` are joined
    ("side bar" -> "sidebar"), and a plural "s" is dropped.
    """
    tokens = re.findall(r"[a-z]+", title.lower())
    joined = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and tokens[i] + tokens[i + 1] in vocab:
            joined.append(tokens[i] + tokens[i + 1])
            i += 2
        else:
            joined.append(tokens[i])
            i += 1
    stems = {
        w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w for w in joined
    }
    return {w for w in stems if len(w) >= 3 and w not in STOP_WORDS}


def find_similar(number: int, title: str, keep: int = 6) -> list[JSONDict]:
    """Earlier items whose titles share rare words with this title.

    GitHub's title search needs every query word to match, so one query
    with all title words misses a duplicate worded differently.  Instead,
    run one query per pair of title words, then rank the pooled results by
    how many title words they share, preferring items open or recently
    closed, then rarer words.
    """
    words = title_words(title, 5)
    queries = [" ".join(words[:4])] if len(words) > 2 else []
    queries += [f"{a} {b}" for i, a in enumerate(words) for b in words[i + 1 :]]
    cutoff = datetime.now(timezone.utc)
    pool: dict[int, JSONDict] = {}
    for q in queries:
        for s in search_issues(f"repo:{REPO} {q} in:title", 30, newest_first=False):
            if s["number"] != number:
                pool[s["number"]] = s
    vocab = {w for s in pool.values() for w in re.findall(r"[a-z]+", s["title"].lower())}
    mine = title_terms(title, vocab)
    terms = {n: title_terms(s["title"], vocab) & mine for n, s in pool.items()}
    df = Counter(w for t in terms.values() for w in t)
    score = {n: sum(math.log((1 + len(pool)) / df[w]) for w in t) for n, t in terms.items()}

    def current(n: int) -> bool:
        closed = pool[n].get("closed_at")
        return closed is None or parse_time(closed) > cutoff - timedelta(days=RECENTLY_CLOSED_DAYS)

    # Most shared words first; among equals, items open or recently closed
    # (what a new duplicate report usually repeats), then rarer words.
    ranked = sorted(
        (n for n in pool if len(terms[n]) >= 2),
        key=lambda n: (-len(terms[n]), not current(n), -score[n], -n),
    )[:keep]
    return [
        {
            "number": n,
            "kind": "pr" if "pull_request" in pool[n] else "issue",
            "title": pool[n]["title"],
            "created": pool[n]["created_at"],
            "closed_at": pool[n].get("closed_at"),
            "merged_at": (pool[n].get("pull_request") or {}).get("merged_at"),
            "author": user_login(pool[n].get("user")),
        }
        for n in ranked
    ]


def czo_threads(
    number: int,
    texts: list[str],
    linked: list[JSONDict],
    attempts: list[int],
) -> tuple[list[JSONDict], list[str]]:
    """The best chat.zulip.org threads, from links and item numbers, best first.

    Also returns the linked conversations that couldn't be read.
    """
    candidates: dict[str, JSONDict] = {}
    unread_links: list[str] = []

    def add_candidate(channel_id: int, topic: str, source: str) -> None:
        c = candidates.setdefault(
            f"{channel_id}\t{topic}",
            {"channel_id": channel_id, "topic": topic, "sources": [], "hits": 0},
        )
        if source not in c["sources"]:
            c["sources"].append(source)
        c["hits"] += 1

    for link in dict.fromkeys(czo_links("\n".join(texts))):
        operands = conversation_operands(link)
        if operands is None:
            continue
        conversation = find_conversation(operands)
        if conversation is None:
            unread_links.append(link)
        else:
            add_candidate(*conversation, "link")
    for n in [number, *(x["number"] for x in linked if x["repo"] == REPO), *attempts]:
        for msg in czo_search(str(n)):
            if re.search(rf"\b{n}\b", msg["content"] + " " + msg["subject"]):
                add_candidate(msg["stream_id"], msg["subject"], "number")
    tier = {"link": 0, "number": 1}
    ranked = sorted(
        candidates.values(), key=lambda c: (min(tier[s] for s in c["sources"]), -c["hits"])
    )
    threads = []
    for c in ranked[:10]:
        t = czo_thread(c["channel_id"], c["topic"])
        if t["channel"].lower() in CZO_EXCLUDED_CHANNELS:
            continue
        t["messages"] = [m for m in t["messages"] if not m["bot"]]
        if not t["messages"]:
            continue
        threads.append(t)
        if len(threads) >= CZO_THREADS_SHOWN:
            break
    return threads, unread_links


# --- author history ---


def author_history(author: str, number: int) -> JSONDict:
    out: dict[str, list[JSONDict]] = {"prs": [], "issues": []}
    for kind, query, per_page, shown in (
        ("prs", "type:pr", 100, AUTHOR_PRS_SHOWN),
        ("issues", "type:issue", 50, AUTHOR_ISSUES_SHOWN),
    ):
        for it in search_issues(f"repo:{REPO} {query} author:{author}", per_page):
            if it["number"] == number:
                continue
            entry = {
                "number": it["number"],
                "title": it["title"],
                "created": it["created_at"],
                "closed_at": it.get("closed_at"),
                "merged_at": (it.get("pull_request") or {}).get("merged_at"),
                "closing_comment": None,
            }
            entry["state"] = state_of(entry)
            if entry["state"] == "closed" and len(out[kind]) < shown:
                comments = api(f"repos/{REPO}/issues/{it['number']}/comments?per_page=100")
                if not isinstance(comments, list):
                    comments = []
                maint = [
                    c
                    for c in comments
                    if user_login(c.get("user")) in MAINTAINERS
                    and parse_time(c["created_at"])
                    <= parse_time(entry["closed_at"]) + timedelta(minutes=10)
                ]
                if maint:
                    c = maint[-1]
                    entry["closing_comment"] = {
                        "who": user_login(c["user"]),
                        "created": c["created_at"],
                        "body": c["body"][:1500],
                    }
            out[kind].append(entry)
    return out


# --- CI ---


def ci_workflow_runs(head_sha: str) -> list[JSONDict] | None:
    """The Zulip CI runs for a PR head commit, or None if they can't be read."""
    runs = api(
        f"repos/{REPO}/actions/workflows/{CI_WORKFLOW_FILE}/runs"
        f"?head_sha={head_sha}&event=pull_request&per_page=20"
    )
    return runs.get("workflow_runs", []) if isinstance(runs, dict) else None


def zulip_ci_checks(check_runs: list[JSONDict], workflow_runs: list[JSONDict]) -> list[JSONDict]:
    """The check runs that belong to the given Zulip CI workflow runs.

    Other workflows, like Copilot code review, add check runs to the same
    commit, and their results say nothing about the PR's tests.
    """
    suite_ids = {r["check_suite_id"] for r in workflow_runs}
    return [c for c in check_runs if c["check_suite"]["id"] in suite_ids]


def check_runs(head_sha: str) -> JSONDict:
    """The latest check run of each name in Zulip CI on the PR's head commit."""
    runs = api(f"repos/{REPO}/commits/{head_sha}/check-runs?per_page=100")
    workflow_runs = ci_workflow_runs(head_sha)
    if not isinstance(runs, dict) or workflow_runs is None:
        return {"head": head_sha, "known": False, "reason": "check runs aren't available"}
    checks = zulip_ci_checks(runs.get("check_runs", []), workflow_runs)
    return {
        "head": head_sha,
        "known": True,
        "runs": [
            {"name": r["name"], "conclusion": r.get("conclusion") or r.get("status")}
            for r in checks
        ],
    }


# --- reviewer candidates ---


def git(*args: str) -> str:
    out = subprocess.run(
        ["git", "-C", ZULIP_CHECKOUT, *args], capture_output=True, text=True, check=False
    )
    if out.returncode != 0:
        log(f"git {' '.join(args)[:160]} failed: {out.stderr[:300]}")
    return out.stdout


def core_contributors() -> list[str]:
    lines = git("shortlog", "-sn", "--since=2 years ago", "HEAD").splitlines()
    return [line.split("\t", 1)[1] for line in lines[:40] if "\t" in line]


def file_authors(files: list[str], core: list[str]) -> list[JSONDict]:
    if not files:
        return []
    # %aN applies .mailmap, as shortlog does, so the names match.
    log_names = git(
        "log", "--since=12 months ago", "--format=%aN", "HEAD", "--", *files[:40]
    ).split("\n")
    counts = Counter(a for a in log_names if a in set(core))
    return [{"name": a, "commits": c} for a, c in counts.most_common(8)]


# --- gather ---


def gather(item: JSONDict) -> JSONDict:
    """Everything the bot input needs, added to the item from fetch_item()."""
    number = item["number"]
    is_pr = item["kind"] == "pr"
    events, complete = complete_lookup(lambda: timeline(number))
    if not complete:
        raise RequestFailedError(f"Couldn't load the comments on #{number} from GitHub")
    comments = comments_from_timeline(events)
    author = item["author"]
    incomplete = set()

    text = item["title"] + "\n" + item["body"]
    linked_refs = [ref for ref in dict.fromkeys(linked_item_refs(text)) if ref != (REPO, number)]
    linked, complete = complete_lookup(
        lambda: [
            x for x in (small_item(n, repo) for repo, n in linked_refs[:MAX_LINKED_ITEMS]) if x
        ]
    )
    if not complete:
        incomplete.add("linked")
    files = item.get("files", [])

    # Earlier attempts: PRs cross-referencing a linked issue.
    via: dict[int, int] = {}
    for li in linked:
        if li["kind"] != "issue":
            continue
        for ref in li["cross_refs"]:
            if ref["kind"] == "pr" and ref["number"] != number and ref["number"] not in via:
                via[ref["number"]] = li["number"]
    mention_text = item["body"] + " " + " ".join(c["body"] for c in comments if c["who"] == author)
    before = failed_lookups
    attempts = []
    for a in sorted(via)[-12:]:
        full = small_item(a, with_files=True)
        if not full:
            continue
        maint = [c for c in full["comments"] if c["maintainer"]]
        attempts.append(
            {
                "number": a,
                "title": full["title"],
                "author": full["author"],
                "author_association": full["author_association"],
                "created": full["created"],
                "state": full["state"],
                "last_maintainer_comment": maint[-1] if maint else None,
                "mentioned_in_item": bool(re.search(rf"#{a}\b|/pull/{a}\b", mention_text)),
                "same_author": full["author"] == author,
                "files_shared": sorted(set(full.get("files", [])) & set(files)),
                "body": full["body"],
                "comments": full["comments"],
            }
        )

    if failed_lookups > before:
        incomplete.add("attempts")

    # Similar items by title words (duplicates, related issues).
    similar, complete = complete_lookup(lambda: find_similar(number, item["title"]))
    if not complete:
        incomplete.add("similar")
    for entry in similar:
        entry["state"] = state_of(entry)

    texts = [item["body"]] + [c["body"] for c in comments]
    for x in [*linked, *attempts]:
        texts += [x["body"]] + [c["body"] for c in x["comments"]]
    (threads, unread_links), complete = complete_lookup(
        lambda: czo_threads(number, texts, linked, [a["number"] for a in attempts])
    )
    if not complete:
        incomplete.add("czo_threads")
    history, complete = complete_lookup(lambda: author_history(author, number))
    if not complete:
        incomplete.add("author_history")

    core = core_contributors()
    return {
        **item,
        "author_name": user_name(author),
        "comments": comments,
        "linked": linked,
        "attempts": attempts,
        "similar": similar,
        "czo_threads": threads,
        "czo_unread_links": unread_links,
        "author_history": history,
        "ci": check_runs(item["head_sha"]) if is_pr else None,
        "file_authors": file_authors(files, core) if is_pr else [],
        "incomplete": sorted(incomplete),
    }
