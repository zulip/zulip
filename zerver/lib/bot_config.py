from django.conf import settings
from django.db.models import Sum
from django.db.models.query import F
from django.db.models.functions import Length
from zerver.models import BotConfigData, UserProfile

from typing import Text, List, Dict, Optional

from collections import defaultdict

import os

import configparser
import importlib

class ConfigError(Exception):
    pass

def get_bot_config(bot_profile: UserProfile) -> Dict[Text, Text]:
    entries = BotConfigData.objects.filter(bot_profile=bot_profile)
    if not entries:
        raise ConfigError("No config data available.")
    return {entry.key: entry.value for entry in entries}

def get_bot_configs(bot_profiles: List[UserProfile]) -> Dict[int, Dict[Text, Text]]:
    if not bot_profiles:
        return {}
    entries = BotConfigData.objects.filter(bot_profile__in=bot_profiles).select_related()
    entries_by_uid = defaultdict(dict)  # type: Dict[int, Dict[Text, Text]]
    for entry in entries:
        entries_by_uid[entry.bot_profile.id].update({entry.key: entry.value})
    return entries_by_uid

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

def load_bot_config_template(bot: str) -> Dict[str, str]:
    bot_module_name = 'zulip_bots.bots.{}'.format(bot)
    bot_module = importlib.import_module(bot_module_name)
    bot_module_path = os.path.dirname(bot_module.__file__)
    config_path = os.path.join(bot_module_path, '{}.conf'.format(bot))
    if os.path.isfile(config_path):
        config = configparser.ConfigParser()
        with open(config_path) as conf:
            config.readfp(conf)  # type: ignore # readfp->read_file in python 3, so not in stubs
        return dict(config.items(bot))
    else:
        return dict()
