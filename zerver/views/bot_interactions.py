"""
Bot interaction endpoints.

These endpoints allow bot widgets to receive interaction events (button clicks,
select menu selections, modal submissions) from users interacting with bot-created
widgets.
"""

import orjson
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

from zerver.actions.bot_interactions import do_handle_bot_interaction
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import access_message
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


@transaction.atomic(durable=True)
@typed_endpoint
def handle_bot_interaction(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: Json[int],
    interaction_type: str,
    custom_id: str,
    data: str = "{}",
) -> HttpResponse:
    """
    Handle an interaction event from a bot widget.

    This endpoint is called when a user interacts with a bot widget (clicks a button,
    selects from a menu, submits a modal form, etc.).

    Parameters:
    - message_id: The ID of the message containing the widget
    - interaction_type: The type of interaction (button_click, select_menu, modal_submit)
    - custom_id: The custom identifier set by the bot for this interactive element
    - data: JSON-encoded additional data about the interaction
    """
    # Access the message and verify the user can interact with it
    message = access_message(user_profile, message_id, lock_message=True, is_modifying_message=True)

    # Validate interaction_type
    valid_interaction_types = ["button_click", "select_menu", "modal_submit", "freeform"]
    if interaction_type not in valid_interaction_types:
        raise JsonableError(_("Invalid interaction type"))

    # Parse the additional data
    try:
        interaction_data = orjson.loads(data)
    except orjson.JSONDecodeError:
        raise JsonableError(_("Invalid JSON in interaction data"))

    # Validate that the message was sent by a bot
    if not message.sender.is_bot:
        raise JsonableError(_("Can only interact with bot messages"))

    # Process the interaction
    do_handle_bot_interaction(
        realm=user_profile.realm,
        user=user_profile,
        message=message,
        interaction_type=interaction_type,
        custom_id=custom_id,
        interaction_data=interaction_data,
    )

    return json_success(request)
