from __future__ import absolute_import

from six import text_type
# Match multi-word string between @** ** or match any one-word
# sequences after @
find_mentions = r'(?<![^\s\'\"\(,:<])@(?:\*\*([^\*]+)\*\*|(\w+))'

wildcards = ['all', 'everyone']

def user_mention_matches_wildcard(mention):
    # type: (text_type) -> bool
    return mention in wildcards
