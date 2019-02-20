
from typing import Optional, Set, Tuple

import re

# Match multi-word string between @** ** or match any one-word
# sequences after @
find_mentions = r'(?<![^\s\'\"\(,:<])@(?P<silent>_?)(?P<match>\*\*[^\*]+\*\*|all|everyone|stream)'
user_group_mentions = r'(?<![^\s\'\"\(,:<])@(\*[^\*]+\*)'

wildcards = ['all', 'everyone', 'stream']

def user_mention_matches_wildcard(mention: str) -> bool:
    return mention in wildcards

def extract_mention_text(m: Tuple[str, str]) -> Optional[str]:
    # re.findall provides tuples of match elements; we want the second
    # to get the main mention content.
    s = m[1]
    if s.startswith("**") and s.endswith("**"):
        text = s[2:-2]
        if text in wildcards:
            return None
        return text

    # We don't care about @all, @everyone or @stream
    return None

def possible_mentions(content: str) -> Set[str]:
    matches = re.findall(find_mentions, content)
    # mention texts can either be names, or an extended name|id syntax.
    texts_with_none = (extract_mention_text(match) for match in matches)
    texts = {text for text in texts_with_none if text}
    return texts

def extract_user_group(matched_text: str) -> str:
    return matched_text[1:-1]

def possible_user_group_mentions(content: str) -> Set[str]:
    matches = re.findall(user_group_mentions, content)
    return {extract_user_group(match) for match in matches}
