import configparser
import importlib
import os
from collections import defaultdict
from typing import Dict, List, Optional

from django.conf import settings
from django.db.models import F, Sum
from django.db.models.functions import Length

from zerver.models import BotConfigData, UserProfile


class ConfigError(Exception):
    pass


def get_bot_config(bot_profile: UserProfile) -> Dict[str, str]:
    entries = BotConfigData.objects.filter(bot_profile=bot_profile)
    if not entries:
        raise ConfigError("No config data available.")
    return {entry.key: entry.value for entry in entries}


def get_bot_configs(bot_profile_ids: List[int]) -> Dict[int, Dict[str, str]]:
    if not bot_profile_ids:
        return {}
    entries = BotConfigData.objects.filter(bot_profile_id__in=bot_profile_ids)
    entries_by_uid: Dict[int, Dict[str, str]] = defaultdict(dict)
    for entry in entries:
        entries_by_uid[entry.bot_profile_id].update({entry.key: entry.value})
    return entries_by_uid


def get_bot_config_size(bot_profile: UserProfile, key: Optional[str] = None) -> int:
    if key is None:
        return (
            BotConfigData.objects.filter(bot_profile=bot_profile)
            .annotate(key_size=Length("key"), value_size=Length("value"))
            .aggregate(sum=Sum(F("key_size") + F("value_size")))["sum"]
            or 0
        )
    else:
        try:
            return len(key) + len(BotConfigData.objects.get(bot_profile=bot_profile, key=key).value)
        except BotConfigData.DoesNotExist:
            return 0


def set_bot_config(bot_profile: UserProfile, key: str, value: str) -> None:
    config_size_limit = settings.BOT_CONFIG_SIZE_LIMIT
    old_entry_size = get_bot_config_size(bot_profile, key)
    new_entry_size = len(key) + len(value)
    old_config_size = get_bot_config_size(bot_profile)
    new_config_size = old_config_size + (new_entry_size - old_entry_size)
    if new_config_size > config_size_limit:
        raise ConfigError(
            f"Cannot store configuration. Request would require {new_config_size} characters. "
            f"The current configuration size limit is {config_size_limit} characters."
        )
    obj, created = BotConfigData.objects.get_or_create(
        bot_profile=bot_profile, key=key, defaults={"value": value}
    )
    if not created:
        obj.value = value
        obj.save()


def load_bot_config_template(bot: str) -> Dict[str, str]:
    bot_module_name = f"zulip_bots.bots.{bot}"
    bot_module = importlib.import_module(bot_module_name)
    assert bot_module.__file__ is not None
    bot_module_path = os.path.dirname(bot_module.__file__)
    config_path = os.path.join(bot_module_path, f"{bot}.conf")
    if os.path.isfile(config_path):
        config = configparser.ConfigParser()
        with open(config_path) as conf:
            config.read_file(conf)
        return dict(config.items(bot))
    else:
        return {}
