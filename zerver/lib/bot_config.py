from django.conf import settings
from django.db.models import Sum
from django.db.models.query import F
from django.db.models.functions import Length
from zerver.models import BotConfigData, UserProfile

from typing import Text, Dict, Optional

class ConfigError(Exception):
    pass

def get_bot_config(bot_profile: UserProfile) -> Dict[Text, Text]:
    entries = BotConfigData.objects.filter(bot_profile=bot_profile)
    if not entries:
        raise ConfigError("No config data available.")
    return {entry.key: entry.value for entry in entries}

def get_bot_config_size(bot_profile: UserProfile, key: Optional[Text]=None) -> int:
    if key is None:
        return BotConfigData.objects.filter(bot_profile=bot_profile) \
                                    .annotate(key_size=Length('key'), value_size=Length('value')) \
                                    .aggregate(sum=Sum(F('key_size')+F('value_size')))['sum'] or 0
    else:
        try:
            return len(key) + len(BotConfigData.objects.get(bot_profile=bot_profile, key=key).value)
        except BotConfigData.DoesNotExist:
            return 0

def set_bot_config(bot_profile: UserProfile, key: Text, value: Text) -> None:
    config_size_limit = settings.BOT_CONFIG_SIZE_LIMIT
    old_entry_size = get_bot_config_size(bot_profile, key)
    new_entry_size = len(key) + len(value)
    old_config_size = get_bot_config_size(bot_profile)
    new_config_size = old_config_size + (new_entry_size - old_entry_size)
    if new_config_size > config_size_limit:
        raise ConfigError("Cannot store configuration. Request would require {} characters. "
                          "The current configuration size limit is {} characters.".format(new_config_size,
                                                                                          config_size_limit))
    obj, created = BotConfigData.objects.get_or_create(bot_profile=bot_profile, key=key,
                                                       defaults={'value': value})
    if not created:
        obj.value = value
        obj.save()
