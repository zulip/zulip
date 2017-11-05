from django.conf import settings
from django.db.models import Sum
from django.db.models.query import F
from django.db.models.functions import Length
from zerver.models import BotStorageData, UserProfile, Length

from typing import Text, Optional, List, Tuple

class StateError(Exception):
    pass

def get_bot_storage(bot_profile: UserProfile, key: Text) -> Text:
    try:
        return BotStorageData.objects.get(bot_profile=bot_profile, key=key).value
    except BotStorageData.DoesNotExist:
        raise StateError("Key does not exist.")

def get_bot_storage_size(bot_profile: UserProfile, key: Optional[Text]=None) -> int:
    if key is None:
        return BotStorageData.objects.filter(bot_profile=bot_profile) \
                                     .annotate(key_size=Length('key'), value_size=Length('value')) \
                                     .aggregate(sum=Sum(F('key_size')+F('value_size')))['sum'] or 0
    else:
        try:
            return len(key) + len(BotStorageData.objects.get(bot_profile=bot_profile, key=key).value)
        except BotStorageData.DoesNotExist:
            return 0

def set_bot_storage(bot_profile: UserProfile, entries: List[Tuple[str, str]]) -> None:
    storage_size_limit = settings.USER_STATE_SIZE_LIMIT
    storage_size_difference = 0
    for key, value in entries:
        if type(key) is not str:
            raise StateError("Key type is {}, but should be str.".format(type(key)))
        if type(value) is not str:
            raise StateError("Value type is {}, but should be str.".format(type(value)))
        storage_size_difference += (len(key) + len(value)) - get_bot_storage_size(bot_profile, key)
    new_storage_size = get_bot_storage_size(bot_profile) + storage_size_difference
    if new_storage_size > storage_size_limit:
        raise StateError("Request exceeds storage limit by {} characters. The limit is {} characters."
                         .format(new_storage_size - storage_size_limit, storage_size_limit))
    else:
        for key, value in entries:
            BotStorageData.objects.update_or_create(bot_profile=bot_profile, key=key,
                                                    defaults={'value': value})

def remove_bot_storage(bot_profile: UserProfile, keys: List[Text]) -> None:
    queryset = BotStorageData.objects.filter(bot_profile=bot_profile, key__in=keys)
    if len(queryset) < len(keys):
        raise StateError("Key does not exist.")
    queryset.delete()

def is_key_in_bot_storage(bot_profile: UserProfile, key: Text) -> bool:
    return BotStorageData.objects.filter(bot_profile=bot_profile, key=key).exists()

def get_keys_in_bot_storage(bot_profile: UserProfile) -> List[Text]:
    return list(BotStorageData.objects.filter(bot_profile=bot_profile).values_list('key', flat=True))
