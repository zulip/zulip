from django.conf import settings
from django.db.models import Sum
from django.db.models.query import F
from django.db.models.functions import Length
from zerver.models import BotUserStateData, UserProfile, Length

from typing import Text, Optional, List, Tuple

class StateError(Exception):
    pass

def get_bot_state(bot_profile, key):
    # type: (UserProfile, Text) -> Text
    try:
        return BotUserStateData.objects.get(bot_profile=bot_profile, key=key).value
    except BotUserStateData.DoesNotExist:
        raise StateError("Key does not exist.")

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

def set_bot_state(bot_profile, entries):
    # type: (UserProfile, List[Tuple[str, str]]) -> None
    state_size_limit = settings.USER_STATE_SIZE_LIMIT
    state_size_difference = 0
    for key, value in entries:
        if type(key) is not str:
            raise StateError("Key type is {}, but should be str.".format(type(key)))
        if type(value) is not str:
            raise StateError("Value type is {}, but should be str.".format(type(value)))
        state_size_difference += (len(key) + len(value)) - get_bot_state_size(bot_profile, key)
    new_state_size = get_bot_state_size(bot_profile) + state_size_difference
    if new_state_size > state_size_limit:
        raise StateError("Request exceeds storage limit by {} characters. The limit is {} characters."
                         .format(new_state_size - state_size_limit, state_size_limit))
    else:
        for key, value in entries:
            BotUserStateData.objects.update_or_create(bot_profile=bot_profile, key=key,
                                                      defaults={'value': value})

def remove_bot_state(bot_profile, keys):
    # type: (UserProfile, List[Text]) -> None
    queryset = BotUserStateData.objects.filter(bot_profile=bot_profile, key__in=keys)
    if len(queryset) < len(keys):
        raise StateError("Key does not exist.")
    queryset.delete()

def is_key_in_bot_state(bot_profile, key):
    # type: (UserProfile, Text) -> bool
    return BotUserStateData.objects.filter(bot_profile=bot_profile, key=key).exists()
