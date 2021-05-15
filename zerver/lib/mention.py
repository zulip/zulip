import re
from typing import Optional, Set, Tuple

# Match multi-word string between @** ** or match any one-word
# sequences after @
MENTIONS_RE = r"(?<![^\s\'\"\(,:<])@(?P<silent>_?)(?P<match>\*\*[^\*]+\*\*|all|everyone|stream)"
USER_GROUP_MENTIONS_RE = r"(?<![^\s\'\"\(,:<])@(\*[^\*]+\*)"

wildcards = ["all", "everyone", "stream"]


def user_mention_matches_wildcard(mention: str) -> bool:
    return mention in wildcards


def extract_mention_text(m: Tuple[str, str]) -> Tuple[Optional[str], bool]:
    # re.findall provides tuples of match elements; we want the second
    # to get the main mention content.
    s = m[1]
    if s.startswith("**") and s.endswith("**"):
        text = s[2:-2]
        if text in wildcards:
            return None, True
        return text, False
    return None, False


def possible_mentions(content: str) -> Tuple[Set[str], bool]:
    matches = re.findall(MENTIONS_RE, content)
    # mention texts can either be names, or an extended name|id syntax.
    texts = set()
    message_has_wildcards = False
    for match in matches:
        text, is_wildcard = extract_mention_text(match)
        if text:
            texts.add(text)
        if is_wildcard:
            message_has_wildcards = True
    return texts, message_has_wildcards


def extract_user_group(matched_text: str) -> str:
    return matched_text[1:-1]


def possible_user_group_mentions(content: str) -> Set[str]:
    matches = re.findall(USER_GROUP_MENTIONS_RE, content)
    return {extract_user_group(match) for match in matches}
