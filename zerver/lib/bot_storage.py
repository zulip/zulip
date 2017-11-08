from django.db.models import Sum
from django.db.models.query import F
from django.db.models.functions import Length
from zerver.models import BotUserStateData, UserProfile, Length

from typing import Text, Optional

def get_bot_state(bot_profile, key):
    # type: (UserProfile, Text) -> Text
    return BotUserStateData.objects.get(bot_profile=bot_profile, key=key).value

def set_bot_state(bot_profile, key, value):
    # type: (UserProfile, Text, Text) -> None
    obj, created = BotUserStateData.objects.get_or_create(bot_profile=bot_profile, key=key,
                                                          defaults={'value': value})
    if not created:
        obj.value = value
        obj.save()

def remove_bot_state(bot_profile, key):
    # type: (UserProfile, Text) -> None
    removed_ctr, removed_entries = BotUserStateData.objects.get(bot_profile=bot_profile, key=key).delete()

def is_key_in_bot_state(bot_profile, key):
    # type: (UserProfile, Text) -> bool
    return BotUserStateData.objects.filter(bot_profile=bot_profile, key=key).exists()

def get_bot_state_size(bot_profile, key=None):
    # type: (UserProfile, Optional[Text]) -> int
    if key is None:
        return BotUserStateData.objects.filter(bot_profile=bot_profile) \
                                       .annotate(key_size=Length('key'), value_size=Length('value')) \
                                       .aggregate(sum=Sum(F('key_size')+F('value_size')))['sum'] or 0
    else:
        try:
            return len(key) + len(BotUserStateData.objects.get(bot_profile=bot_profile, key=key).value)
        except BotUserStateData.DoesNotExist:
            return 0
