
from typing import Optional, Set, Text

import re

# Match multi-word string between @** ** or match any one-word
# sequences after @
find_mentions = r'(?<![^\s\'\"\(,:<])@(\*\*[^\*]+\*\*|all|everyone)'
user_group_mentions = r'(?<![^\s\'\"\(,:<])@(\*[^\*]+\*)'
topic_mentions = r'(?<![^\s\'\"\(,:<])@(\*\*\*[^\*]+\*\*\*)'

wildcards = ['all', 'everyone']

def user_mention_matches_wildcard(mention: Text) -> bool:
    return mention in wildcards

def extract_name(s: Text) -> Optional[Text]:
    if s.startswith("**") and s.endswith("**"):
        name = s[2:-2]
        if name in wildcards:
            return None
        return name

    # We don't care about @all or @everyone
    return None

def possible_mentions(content: Text) -> Set[Text]:
    matches = re.findall(find_mentions, content)
    names_with_none = (extract_name(match) for match in matches)
    names = {name for name in names_with_none if name}
    return names

def extract_user_group(matched_text: Text) -> Text:
    return matched_text[1:-1]

def possible_user_group_mentions(content: Text) -> Set[Text]:
    matches = re.findall(user_group_mentions, content)
    return {extract_user_group(match) for match in matches}

def extract_topic(matched_text: str) -> str:
    return matched_text[3:-3]

def possible_topic_mentions(content: str) -> Set[str]:
    matches = re.findall(topic_mentions, content)
    return {extract_topic(match) for match in matches}
