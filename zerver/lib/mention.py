from __future__ import absolute_import

from typing import Optional, Set, Text

import re

# Match multi-word string between @** ** or match any one-word
# sequences after @
find_mentions = r'(?<![^\s\'\"\(,:<])@(\*\*[^\*]+\*\*|all|everyone)'

wildcards = ['all', 'everyone']

def user_mention_matches_wildcard(mention):
    # type: (Text) -> bool
    return mention in wildcards

def extract_name(s):
    # type: (Text) -> Optional[Text]
    if s.startswith("**") and s.endswith("**"):
        name = s[2:-2]
        if name in wildcards:
            return None
        return name

    # We don't care about @all or @everyone
    return None

def possible_mentions(content):
    # type: (Text) -> Set[Text]
    matches = re.findall(find_mentions, content)
    names_with_none = (extract_name(match) for match in matches)
    names = {name for name in names_with_none if name}
    return names
