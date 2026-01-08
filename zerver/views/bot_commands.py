from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

from zerver.decorator import require_organization_member
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint, typed_endpoint_without_parameters
from zerver.models import BotCommand, UserProfile
from zerver.models.users import active_user_ids
from zerver.tornado.django_api import send_event_on_commit


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
