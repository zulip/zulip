import importlib
import json
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.utils.translation import gettext as _
from zulip_bots.lib import BotIdentity, RateLimit

from zerver.actions.message_flags import do_update_message_flags
from zerver.actions.message_send import (
    internal_send_group_direct_message,
    internal_send_private_message,
    internal_send_stream_message_by_name,
)
from zerver.lib.bot_config import ConfigError, get_bot_config
from zerver.lib.bot_storage import (
    get_bot_storage,
    is_key_in_bot_storage,
    remove_bot_storage,
    set_bot_storage,
)
from zerver.lib.integrations import EMBEDDED_BOTS
from zerver.lib.topic import get_topic_from_message_info
from zerver.models import UserProfile
from zerver.models.users import get_active_user


def get_bot_handler(service_name: str) -> Any:
    # Check that this service is present in EMBEDDED_BOTS, add exception handling.
    configured_service = ""
    for embedded_bot_service in EMBEDDED_BOTS:
        if service_name == embedded_bot_service.name:
            configured_service = embedded_bot_service.name
    if not configured_service:
        return None
    bot_module_name = f"zulip_bots.bots.{configured_service}.{configured_service}"
    bot_module: Any = importlib.import_module(bot_module_name)
    return bot_module.handler_class()


class StateHandler:
    storage_size_limit: int = settings.USER_STATE_SIZE_LIMIT

    def __init__(self, user_profile: UserProfile) -> None:
        self.user_profile = user_profile
        self.marshal: Callable[[object], str] = json.dumps
        self.demarshal: Callable[[str], object] = json.loads

    def get(self, key: str) -> object:
        return self.demarshal(get_bot_storage(self.user_profile, key))

    def put(self, key: str, value: object) -> None:
        set_bot_storage(self.user_profile, [(key, self.marshal(value))])

    def remove(self, key: str) -> None:
        remove_bot_storage(self.user_profile, [key])

    def contains(self, key: str) -> bool:
        return is_key_in_bot_storage(self.user_profile, key)


class EmbeddedBotQuitError(Exception):
    pass


class EmbeddedBotEmptyRecipientsListError(Exception):
    pass


class EmbeddedBotHandler:
    def __init__(self, user_profile: UserProfile) -> None:
        # Only expose a subset of our UserProfile's functionality
        self.user_profile = user_profile
        self._rate_limit = RateLimit(20, 5)
        self.full_name = user_profile.full_name
        self.email = user_profile.email
        self.storage = StateHandler(user_profile)
        self.user_id = user_profile.id

    def identity(self) -> BotIdentity:
        return BotIdentity(self.full_name, self.email)

    def react(self, message: dict[str, Any], emoji_name: str) -> dict[str, Any]:
        return {}  # Not implemented

    def send_message(self, message: dict[str, Any]) -> dict[str, Any]:
        if not self._rate_limit.is_legal():
            self._rate_limit.show_error_and_exit()

        if message["type"] == "stream":
            message_id = internal_send_stream_message_by_name(
                self.user_profile.realm,
                self.user_profile,
                message["to"],
                message["topic"],
                message["content"],
            )
            return {"id": message_id}

        assert message["type"] == "private"
        # Ensure that it's a comma-separated list, even though the
        # usual 'to' field could be either a List[str] or a str.
        recipients = ",".join(message["to"]).split(",")

        if len(message["to"]) == 0:
            raise EmbeddedBotEmptyRecipientsListError(_("Message must have recipients!"))
        elif len(message["to"]) == 1:
            recipient_user = get_active_user(recipients[0], self.user_profile.realm)
            message_id = internal_send_private_message(
                self.user_profile, recipient_user, message["content"]
            )
        else:
            message_id = internal_send_group_direct_message(
                self.user_profile.realm, self.user_profile, message["content"], emails=recipients
            )
        return {"id": message_id}

    def send_reply(
        self, message: dict[str, Any], response: str, widget_content: str | None = None
    ) -> dict[str, Any]:
        if message["type"] == "private":
            result = self.send_message(
                dict(
                    type="private",
                    to=[x["email"] for x in message["display_recipient"]],
                    content=response,
                    sender_email=message["sender_email"],
                )
            )
        else:
            result = self.send_message(
                dict(
                    type="stream",
                    to=message["display_recipient"],
                    topic=get_topic_from_message_info(message),
                    content=response,
                    sender_email=message["sender_email"],
                )
            )
        return {"id": result["id"]}

    def update_message(self, message: dict[str, Any]) -> None:
        pass  # Not implemented

    # The bot_name argument exists only to comply with ExternalBotHandler.get_config_info().
    def get_config_info(self, bot_name: str, optional: bool = False) -> dict[str, str]:
        try:
            return get_bot_config(self.user_profile)
        except ConfigError:
            if optional:
                return {}
            raise

    def quit(self, message: str = "") -> None:
        raise EmbeddedBotQuitError(message)


def do_flag_service_bots_messages_as_processed(
    bot_profile: UserProfile, message_ids: list[int]
) -> None:
    assert bot_profile.is_bot is True and bot_profile.bot_type in UserProfile.SERVICE_BOT_TYPES
    do_update_message_flags(bot_profile, "add", "read", message_ids)
