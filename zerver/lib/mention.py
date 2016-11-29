from __future__ import absolute_import

from typing import Text

# Match multi-word string between @** ** or match any one-word
# sequences after @
find_mentions = r'(?<![^\s\'\"\(,:<])@(?:\*\*([^\*]+)\*\*|(\w+))'

online = ['here', 'online']
wildcards = ['all', 'everyone'] + online


def user_mention_matches_wildcard(mention):
    # type: (Text) -> bool
    return mention in wildcards


def user_mention_matches_online(mention):
    # type: (Text) -> bool
    return mention in online
