
from typing import Optional, Set, Text

import re

# Match multi-word string between @** ** or match any one-word
# sequences after @
find_mentions = r'(?<![^\s\'\"\(,:<])@(\*\*[^\*]+\*\*|all|everyone|stream)'
user_group_mentions = r'(?<![^\s\'\"\(,:<])@(\*[^\*]+\*)'

wildcards = ['all', 'everyone', 'stream']

def user_mention_matches_wildcard(mention: Text) -> bool:
    return mention in wildcards

def extract_name(s: Text) -> Optional[Text]:
    if s.startswith("**") and s.endswith("**"):
        name = s[2:-2]
        if name in wildcards:
            return None
        return name

    # We don't care about @all, @everyone or @stream
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
