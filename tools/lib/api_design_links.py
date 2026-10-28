"""Recognize links to conversations in the #api design channel.

Our API-design policy asks that every API change be discussed and
approved there; see docs/processes/api-design.md.
"""

import re
from urllib.parse import urlsplit

# The Zulip development community, where the #api design channel lives.
CZO_URL = "https://chat.zulip.org"
API_DESIGN_CHANNEL_ID = "378"

# A candidate to examine: CZO_URL and everything up to the next
# whitespace. Deliberately loose, since prose leaves punctuation stuck
# to a link; is_api_design_link makes the real decision.
CANDIDATE_LINK = re.compile(rf"{re.escape(CZO_URL)}/\S+")

# Punctuation to strip from the end of a candidate link. A narrow link
# never ends in one of these, because encodeHashComponent turns each into
# a dot-escape like ".29" or ".3F", which ends in a hex digit. See
# web/src/internal_url.ts.
TRAILING_PUNCTUATION = ")]}>,;:!?'\"*."


def is_api_design_link(candidate_url: str) -> bool:
    """Whether this string is a link to a conversation in the #api design channel.

    Returns False for anything else, including a string that isn't a URL.
    """
    try:
        parts = urlsplit(candidate_url)
    except ValueError:
        # Some malformed URLs, like "https://[", can't be parsed at all.
        return False
    if f"{parts.scheme}://{parts.netloc}" != CZO_URL:
        return False
    if parts.path not in ("", "/"):
        return False

    # A narrow link's fragment is "narrow" followed by operator/operand
    # pairs, like "narrow/channel/378-api-design/topic/some.20topic".
    # See search_terms_to_hash in web/src/hash_util.ts.
    segments = parts.fragment.split("/")
    if segments[0] != "narrow":
        return False
    operands = {segments[i]: segments[i + 1] for i in range(1, len(segments) - 1, 2)}

    # The operand is the channel's ID, optionally followed by its name.
    # Zulip called channels streams until 2024 (see commit d3987f611).
    channel = operands.get("channel", operands.get("stream"))
    if channel is None or channel.split("-")[0] != API_DESIGN_CHANNEL_ID:
        return False

    # Require a topic.
    return "topic" in operands


def find_api_design_links(text: str) -> list[str]:
    """Return the #api design conversations linked in this text, in order."""
    links: list[str] = []
    for candidate in CANDIDATE_LINK.findall(text):
        link = candidate.rstrip(TRAILING_PUNCTUATION)
        if is_api_design_link(link) and link not in links:
            links.append(link)
    return links
