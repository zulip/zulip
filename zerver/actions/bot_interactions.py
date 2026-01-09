"""
Actions for handling bot interactions.

When a user interacts with a bot widget (button click, select menu, modal submit),
these actions route the interaction event to the originating bot.
"""

import json
from typing import Any

from zerver.lib.queue import queue_event_on_commit
from zerver.models import Message, Realm, SubMessage, UserProfile
from zerver.tornado.django_api import send_event_on_commit as send_event


def do_handle_bot_interaction(
    realm: Realm,
    user: UserProfile,
    message: Message,
    interaction_type: str,
    custom_id: str,
    interaction_data: dict[str, Any],
    *,
    interaction_id: str,
) -> None:
    """
    Process a user interaction with a bot widget and route it to the bot.

    This creates a submessage record for tracking and then queues an event
    for the bot to process.

    The interaction_id is a unique identifier for this interaction that can
    be used for acknowledgement tracking on the frontend.
    """
    bot = message.sender

    # Build the interaction content
    content = {
        "type": "interaction",
        "interaction_id": interaction_id,
        "interaction_type": interaction_type,
        "custom_id": custom_id,
        "data": interaction_data,
    }

    # Create a submessage to record this interaction
    submessage = SubMessage(
        sender_id=user.id,
        message_id=message.id,
        msg_type="bot_interaction",
        content=json.dumps(content),
    )
    submessage.save()

    # Broadcast the submessage event to all clients viewing this message
    # (so other users can see interaction state updates if the widget supports it)
    from zerver.lib.message import event_recipient_ids_for_action_on_messages

    event = dict(
        type="submessage",
        msg_type="bot_interaction",
        message_id=message.id,
        submessage_id=submessage.id,
        sender_id=user.id,
        content=json.dumps(content),
    )
    target_user_ids = event_recipient_ids_for_action_on_messages(
        [message.id], message.is_channel_message
    )
    send_event(realm, event, target_user_ids)

    # Queue the interaction for the bot to process
    queue_bot_interaction_event(
        bot=bot,
        user=user,
        message=message,
        interaction_type=interaction_type,
        custom_id=custom_id,
        interaction_data=interaction_data,
        interaction_id=interaction_id,
    )


def queue_bot_interaction_event(
    bot: UserProfile,
    user: UserProfile,
    message: Message,
    interaction_type: str,
    custom_id: str,
    interaction_data: dict[str, Any],
    *,
    interaction_id: str,
) -> None:
    """
    Queue an interaction event for a bot to process.

    All bot types receive interaction events via the event queue if they subscribe
    to 'bot_interaction' events. Additionally, outgoing webhook bots get events
    POSTed to their URL, and embedded bots get events routed to their handler.
    """
    event = {
        "type": "bot_interaction",
        "bot_user_id": bot.id,
        "user_profile_id": user.id,
        "message_id": message.id,
        "interaction_id": interaction_id,
        "interaction_type": interaction_type,
        "custom_id": custom_id,
        "data": interaction_data,
        # Include message context for the bot
        "message": {
            "id": message.id,
            "sender_id": message.sender_id,
            "content": message.content,
            "topic": message.topic_name() if message.is_channel_message else None,
            "stream_id": message.recipient.type_id if message.is_channel_message else None,
        },
        "user": {
            "id": user.id,
            "email": user.delivery_email,
            "full_name": user.full_name,
        },
    }

    # Send event to bot via event queue (any bot type can subscribe to bot_interaction events)
    send_event(bot.realm, event, [bot.id])

    # Also queue for webhook/embedded bot delivery
    if bot.bot_type in [UserProfile.OUTGOING_WEBHOOK_BOT, UserProfile.EMBEDDED_BOT]:
        queue_event_on_commit("bot_interactions", event)
