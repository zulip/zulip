from django.conf import settings
from django.db.models import Sum
from django.db.models.query import F
from django.db.models.functions import Length
from zerver.models import BotUserStateData, UserProfile, Length

from typing import Text, Optional

class StateError(Exception):
    pass

def get_bot_state(bot_profile, key):
    # type: (UserProfile, Text) -> Text
    try:
        return BotUserStateData.objects.get(bot_profile=bot_profile, key=key).value
    except BotUserStateData.DoesNotExist:
        raise StateError("Cannot get state. {} doesn't have "
                         "an entry with the key '{}'.".format(bot_profile, key))

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

def set_bot_state(bot_profile, key, value):
    # type: (UserProfile, Text, Text) -> None
    state_size_limit = settings.USER_STATE_SIZE_LIMIT
    old_entry_size = get_bot_state_size(bot_profile, key)
    new_entry_size = len(key) + len(value)
    old_state_size = get_bot_state_size(bot_profile)
    new_state_size = old_state_size + (new_entry_size - old_entry_size)
    if new_state_size > state_size_limit:
        raise StateError("Cannot set state. Request would require {} bytes storage. "
                         "The current storage limit is {}.".format(new_state_size,
                                                                   state_size_limit))
    elif type(key) is not str:
        raise StateError("Cannot set state. The key type is {}, but it should be str.".format(type(key)))
    elif type(value) is not str:
        raise StateError("Cannot set state. The value type is {}, but it should be str.".format(type(value)))
    else:
        obj, created = BotUserStateData.objects.get_or_create(bot_profile=bot_profile, key=key,
                                                              defaults={'value': value})
        if not created:
            obj.value = value
            obj.save()

def remove_bot_state(bot_profile, key):
    # type: (UserProfile, Text) -> None
    try:
        BotUserStateData.objects.get(bot_profile=bot_profile, key=key).delete()
    except BotUserStateData.DoesNotExist:
        raise StateError("Cannot remove state. The key {} does not exist.".format(key))

def is_key_in_bot_state(bot_profile, key):
    # type: (UserProfile, Text) -> bool
    return BotUserStateData.objects.filter(bot_profile=bot_profile, key=key).exists()
