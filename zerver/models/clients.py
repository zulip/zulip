import hashlib

from django.conf import settings
from django.db import models
from typing_extensions import override

from zerver.lib import cache
from zerver.lib.cache import cache_with_key


class Client(models.Model):
    MAX_NAME_LENGTH = 30
    id = models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")
    name = models.CharField(max_length=MAX_NAME_LENGTH, db_index=True, unique=True)

    @override
    def __str__(self) -> str:
        return self.name

    def default_read_by_sender(self) -> bool:
        """Used to determine whether a message was sent by a full Zulip UI
        style client (and thus whether the message should be treated
        as sent by a human and automatically marked as read for the
        sender).  The purpose of this distinction is to ensure that
        message sent to the user by e.g. a Google Calendar integration
        using the user's own API key don't get marked as read
        automatically.
        """
        sending_client = self.name.lower()

        return (
            sending_client
            in (
                "zulipandroid",
                "zulipios",
                "zulipdesktop",
                "zulipmobile",
                "zulipelectron",
                "zulipterminal",
                "snipe",
                "website",
                "ios",
                "android",
            )
            # Since the vast majority of messages are sent by humans
            # in Zulip, treat test suite messages as such.
            or (sending_client == "test suite" and settings.TEST_SUITE)
        )


get_client_cache: dict[str, Client] = {}


def clear_client_cache() -> None:  # nocoverage
    global get_client_cache
    get_client_cache = {}


def get_client(name: str) -> Client:
    # Accessing KEY_PREFIX through the module is necessary
    # because we need the updated value of the variable.
    cache_name = cache.KEY_PREFIX + name[0 : Client.MAX_NAME_LENGTH]
    if cache_name not in get_client_cache:
        result = get_client_remote_cache(name)
        get_client_cache[cache_name] = result
    return get_client_cache[cache_name]


def get_client_cache_key(name: str) -> str:
    return f"get_client:{hashlib.sha1(name.encode()).hexdigest()}"


@cache_with_key(get_client_cache_key, timeout=3600 * 24 * 7)
def get_client_remote_cache(name: str) -> Client:
    (client, _) = Client.objects.get_or_create(name=name[0 : Client.MAX_NAME_LENGTH])
    return client
