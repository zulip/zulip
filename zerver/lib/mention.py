import re

from django.db.models import F, Q
import zerver.models

# Match multi-word string between @** ** or match any one-word
# sequences after @
find_mentions = r'(?<![^\s\'\"\(,:<])@(?:\*\*([^\*]+)\*\*|(\w+))'

wildcards = ['all', 'everyone']

def user_mention_matches_wildcard(mention):
    return mention in wildcards
