from __future__ import absolute_import

from typing import Text

# Match multi-word string between @** ** or match any one-word
# sequences after @
FIND_MENTIONS = r'(?<![^\s\'\"\(,:<])@(?:\*\*([^\*]+)\*\*|(\w+))'

ONLINE = ['here', 'online']
WILDCARDS = ['all', 'everyone'] + ONLINE

def user_mention_matches_wildcard(mention):
    # type: (Text) -> bool
    return mention in WILDCARDS

def user_mention_matches_online(mention):
    # type: (Text) -> bool
    return mention in ONLINE
