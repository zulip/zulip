import re
from typing import Optional, Set, Tuple

# Match multi-word string between @** ** or match any one-word
# sequences after @
FIND_MENTIONS_RE = (
    r"(?<![^\s\'\"\(,:<])@(?P<silent>_?)(?P<match>\*\*[^\*]+\*\*|all|everyone|stream|online|here)"
)
USER_GROUP_MENTIONS_RE = r"(?<![^\s\'\"\(,:<])@(\*[^\*]+\*)"

WILDCARDS = ["all", "everyone", "stream"]
ONLINE = ["online", "here"]


def user_mention_matches_wildcard(mention: str) -> bool:
    return mention in WILDCARDS


def user_mention_matches_online(mention: str) -> bool:
    return mention in ONLINE


def extract_mention_text(m: Tuple[str, str]) -> Tuple[Optional[str], bool, bool]:
    # re.findall provides tuples of match elements; we want the second
    # to get the main mention content.
    text = None
    s = m[1]
    if s.startswith("**") and s.endswith("**"):
        text = s[2:-2]
        if text in WILDCARDS:
            return None, True, False
        if text in ONLINE:
            return None, False, True
    return text, False, False


def possible_mentions(content: str) -> Tuple[Set[str], bool, bool]:
    matches = re.findall(FIND_MENTIONS_RE, content)
    # mention texts can either be names, or an extended name|id syntax.
    texts = set()
    message_has_wildcards = False
    message_has_online_mentions = False
    for match in matches:
        text, is_wildcard, has_online_mentions = extract_mention_text(match)
        if text:
            texts.add(text)
        if is_wildcard:
            message_has_wildcards = True
        elif has_online_mentions:
            message_has_online_mentions = True
    return texts, message_has_wildcards, message_has_online_mentions


def extract_user_group(matched_text: str) -> str:
    return matched_text[1:-1]


def possible_user_group_mentions(content: str) -> Set[str]:
    matches = re.findall(USER_GROUP_MENTIONS_RE, content)
    return {extract_user_group(match) for match in matches}
