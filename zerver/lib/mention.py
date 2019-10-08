
from typing import Optional, Set

import re

# Match multi-word string between @** ** or match any one-word
# sequences after @
find_mentions = r'(?<![^\s\'\"\(,:<])@(\*\*[^\*]+\*\*|all|everyone|stream)'
user_group_mentions = r'(?<![^\s\'\"\(,:<])@(\*[^\*]+\*)'

wildcards = ['all', 'everyone', 'stream']

def user_mention_matches_wildcard(mention: str) -> bool:
    return mention in wildcards

def extract_mention_text(s: str) -> Optional[str]:
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
