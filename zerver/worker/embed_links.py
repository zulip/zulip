# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
import time
from collections.abc import Mapping
from types import FrameType
from typing import Any

from django.db import transaction
from typing_extensions import override

from zerver.actions.message_edit import do_update_embedded_data
from zerver.actions.message_send import (
    do_send_compose_link_preview,
    render_incoming_message,
    render_message_for_compose_preview,
)
from zerver.lib.mention import MentionBackend, MentionData
from zerver.lib.url_preview import preview as url_preview
from zerver.lib.url_preview.types import UrlEmbedData
from zerver.models import Message, Realm
from zerver.models.users import get_user_profile_by_id
from zerver.worker.base import InterruptConsumeError, QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("embed_links")
class FetchLinksEmbedData(QueueProcessingWorker):
    # This is a slow queue with network requests, so a disk write is negligible.
    # Update stats file after every consume call.
    CONSUME_ITERATIONS_BEFORE_UPDATE_STATS_NUM = 1

    @override
    def consume(self, event: Mapping[str, Any]) -> None:
        if event.get("compose_preview"):
            self.handle_compose_link_preview(event)
            return

        url_embed_data = self.fetch_url_embed_data(event["urls"])

        # Ideally, we should use `durable=True` here. However, in the
        # `test_message_update_race_condition` test, this function is not called
        # as the outermost transaction. As a result, it's acceptable to make an
        # exception and not use `durable=True` in this case.
        #
        # For more details on why the `consume` method is called directly in tests, see:
        # https://zulip.readthedocs.io/en/latest/subsystems/queuing.html#publishing-events-into-a-queue
        with transaction.atomic(savepoint=False):
            try:
                message = Message.objects.select_for_update(no_key=True).get(id=event["message_id"])
            except Message.DoesNotExist:
                # Message may have been deleted
                return

            # If the message changed, we will run this task after updating the message
            # in zerver.actions.message_edit.check_update_message
            if message.content != event["message_content"]:
                return

            # Fetch the realm whose settings we're using for rendering
            realm = Realm.objects.get(id=event["message_realm_id"])

            # If rendering fails, the called code will raise a JsonableError.
            mention_data = MentionData(
                mention_backend=MentionBackend(message.realm_id),
                content=message.content,
                message_sender=message.sender,
            )
            rendering_result = render_incoming_message(
                message,
                message.content,
                realm,
                url_embed_data=url_embed_data,
                mention_data=mention_data,
            )
            do_update_embedded_data(message.sender, message, rendering_result, mention_data)

    def fetch_url_embed_data(self, urls: list[str]) -> dict[str, UrlEmbedData | None]:
        url_embed_data: dict[str, UrlEmbedData | None] = {}
        for url in urls:
            start_time = time.time()
            url_embed_data[url] = url_preview.get_link_embed_data(url)
            logging.info(
                "Time spent on get_link_embed_data for %s: %s", url, time.time() - start_time
            )
        return url_embed_data

    def handle_compose_link_preview(self, event: Mapping[str, Any]) -> None:
        # A compose preview has no saved message to look up, so render an
        # unsaved stub and push the result to just the composing user.
        url_embed_data = self.fetch_url_embed_data(event["urls"])
        sender = get_user_profile_by_id(event["user_id"])
        rendering_result = render_message_for_compose_preview(
            sender, event["content"], url_embed_data=url_embed_data
        )
        do_send_compose_link_preview(sender, event["content"], rendering_result.rendered_content)

    @override
    def timer_expired(
        self, limit: int, events: list[dict[str, Any]], signal: int, frame: FrameType | None
    ) -> None:
        assert len(events) == 1
        event = events[0]

        # Compose-preview jobs have no saved message, so message_id is
        # absent; use .get() to log None rather than raising KeyError
        # here, which would mask the timeout we are trying to report.
        logging.warning(
            "Timed out in %s after %s seconds while fetching URLs for message %s: %s",
            self.queue_name,
            limit,
            event.get("message_id"),
            event["urls"],
        )
        raise InterruptConsumeError
