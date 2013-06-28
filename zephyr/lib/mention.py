import re

from django.db.models import F, Q
import zephyr.models

# Match multi-word string between @** ** or match any one-word
# sequences after @
find_mentions = r'(?:\B@(?:\*\*([^\*]+)\*\*)|@(\w+))'
find_mentions_re = re.compile(find_mentions)

wildcards = ['all', 'everyone']

def find_user_for_mention(mention, realm):
    if mention in wildcards:
        return (True, None)

    try:
        user = zephyr.models.UserProfile.objects.filter(
                Q(full_name__iexact=mention) | Q(short_name__iexact=mention),
                realm=realm
            )[0]
    except IndexError:
        user = None

    return (False, user)
