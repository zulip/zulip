import logging
from typing import Annotated, Any

import requests
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

from version import ZULIP_VERSION
from zerver.decorator import require_organization_member
from zerver.lib.exceptions import JsonableError
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint, typed_endpoint_without_parameters
from zerver.models import BotCommand, UserProfile
from zerver.models.bots import get_bot_services
from zerver.models.users import active_user_ids, get_user_profile_by_id
from zerver.tornado.django_api import send_event_on_commit

logger = logging.getLogger(__name__)


@require_organization_member
@typed_endpoint_without_parameters
def list_bot_commands(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    """List all bot commands registered in the user's realm."""
    commands = BotCommand.objects.filter(realm=user_profile.realm).select_related("bot_profile")
    result = [
        {
            "id": cmd.id,
            "name": cmd.name,
            "description": cmd.description,
            "options": cmd.options_schema,
            "bot_id": cmd.bot_profile_id,
            "bot_name": cmd.bot_profile.full_name,
        }
        for cmd in commands
    ]
    return json_success(request, data={"commands": result})


@typed_endpoint
def register_bot_command(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    name: Annotated[str, "Name of the command (e.g., 'weather')"],
    description: Annotated[str, "Description shown in typeahead"],
    options: Annotated[Json[list[dict[str, object]]], "Command options schema"] = [],
) -> HttpResponse:
    """Register a new bot command. Only callable by bots."""
    if not user_profile.is_bot:
        raise JsonableError(_("Only bots can register commands"))

    # Create or update the command
    command, created = BotCommand.objects.update_or_create(
        realm=user_profile.realm,
        name=name,
        defaults={
            "bot_profile": user_profile,
            "description": description,
            "options_schema": options,
        },
    )

    # Send event to notify clients about new/updated command
    event = {
        "type": "bot_command",
        "op": "add",
        "command": {
            "id": command.id,
            "name": command.name,
            "description": command.description,
            "options": command.options_schema,
            "bot_id": command.bot_profile_id,
            "bot_name": command.bot_profile.full_name,
        },
    }
    send_event_on_commit(user_profile.realm, event, active_user_ids(user_profile.realm_id))

    return json_success(
        request,
        data={
            "id": command.id,
            "name": command.name,
            "created": created,
        },
    )


@typed_endpoint_without_parameters
def delete_bot_command(
    request: HttpRequest,
    user_profile: UserProfile,
    command_id: int,
) -> HttpResponse:
    """Delete a bot command. Only the owning bot or realm admins can delete."""
    try:
        command = BotCommand.objects.get(id=command_id, realm=user_profile.realm)
    except BotCommand.DoesNotExist:
        raise JsonableError(_("Command not found"))

    # Check permissions: must be the owning bot or a realm admin
    if not (user_profile.is_bot and command.bot_profile_id == user_profile.id):
        if not user_profile.is_realm_admin:
            raise JsonableError(_("Permission denied"))

    command_id_to_delete = command.id
    command.delete()

    # Send event to notify clients about deleted command
    event = {
        "type": "bot_command",
        "op": "remove",
        "command_id": command_id_to_delete,
    }
    send_event_on_commit(user_profile.realm, event, active_user_ids(user_profile.realm_id))

    return json_success(request)


@require_organization_member
@typed_endpoint
def get_command_autocomplete(
    request: HttpRequest,
    user_profile: UserProfile,
    bot_id: int,
    *,
    command_name: str,
    option_name: str,
    partial_value: str = "",
    context: str = "{}",
) -> HttpResponse:
    """
    Fetch autocomplete suggestions for a bot command option.

    This endpoint queries the bot for dynamic suggestions based on the current
    input. The bot can return choices that are context-aware (e.g., items in
    the user's inventory for a game bot).

    Parameters:
    - bot_id: The ID of the bot that owns the command
    - command_name: The name of the command being typed
    - option_name: The name of the option needing suggestions
    - partial_value: The partial value the user has typed
    - context: JSON-encoded context (channel_id, topic, other options already entered)

    Returns:
    - choices: List of {value, label} objects for the typeahead
    """
    import json

    # Validate bot exists and is in the same realm
    try:
        bot_profile = get_user_profile_by_id(bot_id)
    except UserProfile.DoesNotExist:
        raise JsonableError(_("Bot not found"))

    if bot_profile.realm_id != user_profile.realm_id:
        raise JsonableError(_("Bot not found"))

    if not bot_profile.is_bot:
        raise JsonableError(_("Specified user is not a bot"))

    # Parse context
    try:
        context_data = json.loads(context) if context else {}
    except json.JSONDecodeError:
        context_data = {}

    # For outgoing webhook bots, query the bot's service
    if bot_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
        choices = _fetch_autocomplete_from_webhook(
            bot_profile=bot_profile,
            command_name=command_name,
            option_name=option_name,
            partial_value=partial_value,
            context_data=context_data,
            user_profile=user_profile,
        )
    elif bot_profile.bot_type == UserProfile.EMBEDDED_BOT:
        choices = _fetch_autocomplete_from_embedded_bot(
            bot_profile=bot_profile,
            command_name=command_name,
            option_name=option_name,
            partial_value=partial_value,
            context_data=context_data,
            user_profile=user_profile,
        )
    else:
        # For other bot types, return empty choices
        choices = []

    return json_success(request, data={"choices": choices})


def _fetch_autocomplete_from_webhook(
    bot_profile: UserProfile,
    command_name: str,
    option_name: str,
    partial_value: str,
    context_data: dict[str, Any],
    user_profile: UserProfile,
) -> list[dict[str, str]]:
    """Fetch autocomplete suggestions from an outgoing webhook bot."""
    services = get_bot_services(bot_profile.id)
    if not services:
        return []

    session = OutgoingSession(
        role="webhook",
        timeout=5,  # Short timeout for autocomplete
        headers={"User-Agent": "ZulipBotAutocomplete/" + ZULIP_VERSION},
    )

    for service in services:
        payload = {
            "type": "autocomplete",
            "token": service.token,
            "command": command_name,
            "option": option_name,
            "partial": partial_value,
            "context": context_data,
            "user": {
                "id": user_profile.id,
                "email": user_profile.delivery_email,
                "full_name": user_profile.full_name,
            },
        }

        try:
            response = session.post(service.base_url, json=payload)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and "choices" in data:
                    return _normalize_choices(data["choices"])
        except (requests.exceptions.RequestException, ValueError):
            logger.debug("Autocomplete request to bot %s failed", bot_profile.email)

    return []


def _fetch_autocomplete_from_embedded_bot(
    bot_profile: UserProfile,
    command_name: str,
    option_name: str,
    partial_value: str,
    context_data: dict[str, Any],
    user_profile: UserProfile,
) -> list[dict[str, str]]:
    """Fetch autocomplete suggestions from an embedded bot."""
    from zerver.lib.bot_lib import EmbeddedBotHandler, get_bot_handler

    services = get_bot_services(bot_profile.id)
    if not services:
        return []

    for service in services:
        try:
            bot_handler = get_bot_handler(str(service.name))
            if bot_handler is None:
                continue

            # Check if the bot handler supports autocomplete
            if hasattr(bot_handler, "get_autocomplete"):
                embedded_bot_handler = EmbeddedBotHandler(bot_profile)
                result = bot_handler.get_autocomplete(
                    command=command_name,
                    option=option_name,
                    partial=partial_value,
                    context=context_data,
                    user={
                        "id": user_profile.id,
                        "email": user_profile.delivery_email,
                        "full_name": user_profile.full_name,
                    },
                    bot_handler=embedded_bot_handler,
                )
                if isinstance(result, list):
                    return _normalize_choices(result)

        except Exception as e:
            logger.debug("Autocomplete from embedded bot %s failed: %s", bot_profile.email, e)

    return []


def _normalize_choices(choices: list[Any]) -> list[dict[str, str]]:
    """Normalize choices to the expected format: [{value, label}]."""
    result = []
    for choice in choices:
        if isinstance(choice, dict):
            value = str(choice.get("value", ""))
            label = str(choice.get("label", value))
            result.append({"value": value, "label": label})
        elif isinstance(choice, str):
            result.append({"value": choice, "label": choice})
    return result
