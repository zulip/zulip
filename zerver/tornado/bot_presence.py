"""Bot presence integration with event queue lifecycle.

This module provides hooks to automatically update bot presence based on
whether they have an active event queue connection.
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from zerver.lib.queue import queue_json_publish_rollback_unsafe

if TYPE_CHECKING:
    from zerver.tornado.event_queue import ClientDescriptor

logger = logging.getLogger(__name__)


def bot_presence_gc_hook(
    user_profile_id: int, client: "ClientDescriptor", last_for_user: bool
) -> None:
    """Called when an event queue is garbage collected.

    If this was the bot's last event queue, mark them as disconnected.
    We queue this to the deferred_work queue to avoid blocking the Tornado event loop.
    """
    if not last_for_user:
        # Bot still has other event queues, don't mark as disconnected
        return

    if not client.is_bot:
        # Not a bot, no presence update needed
        return

    # Queue the presence update to be processed asynchronously
    # We can't safely do DB operations directly in the Tornado event loop
    event = {
        "type": "bot_presence_update",
        "user_profile_id": user_profile_id,
        "is_connected": False,
    }
    queue_json_publish_rollback_unsafe("deferred_work", event)
    logger.debug("Queued bot presence disconnect for user %d", user_profile_id)


def bot_presence_connect_hook(user_profile_id: int, is_bot: bool) -> None:
    """Called when an event queue is allocated for a user.

    If this is a bot, mark them as connected.
    """
    if not is_bot:
        return

    event = {
        "type": "bot_presence_update",
        "user_profile_id": user_profile_id,
        "is_connected": True,
    }
    queue_json_publish_rollback_unsafe("deferred_work", event)
    logger.debug("Queued bot presence connect for user %d", user_profile_id)


def get_gc_hook() -> Callable[[int, "ClientDescriptor", bool], None]:
    """Returns the GC hook function for bot presence."""
    return bot_presence_gc_hook
