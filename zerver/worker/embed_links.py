# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
import time
from types import FrameType
from typing import Any, Dict, List, Mapping, Optional

from django.db import transaction
from typing_extensions import override

from zerver.actions.message_edit import do_update_embedded_data
from zerver.actions.message_send import render_incoming_message
from zerver.lib.url_preview import preview as url_preview
from zerver.lib.url_preview.types import UrlEmbedData
from zerver.models import Message, Realm
from zerver.worker.base import InterruptConsumeError, QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("embed_links")
class FetchLinksEmbedData(QueueProcessingWorker):
    # This is a slow queue with network requests, so a disk write is negligible.
    # Update stats file after every consume call.
    CONSUME_ITERATIONS_BEFORE_UPDATE_STATS_NUM = 1

    @override
    def consume(self, event: Mapping[str, Any]) -> None:
        url_embed_data: Dict[str, Optional[UrlEmbedData]] = {}
        for url in event["urls"]:
            start_time = time.time()
            url_embed_data[url] = url_preview.get_link_embed_data(url)
            logging.info(
                "Time spent on get_link_embed_data for %s: %s", url, time.time() - start_time
            )

        with transaction.atomic():
            try:
                message = Message.objects.select_for_update().get(id=event["message_id"])
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
            rendering_result = render_incoming_message(
                message,
                message.content,
                realm,
                url_embed_data=url_embed_data,
            )
            do_update_embedded_data(message.sender, message, message.content, rendering_result)

    @override
    def timer_expired(
        self, limit: int, events: List[Dict[str, Any]], signal: int, frame: Optional[FrameType]
    ) -> None:
        assert len(events) == 1
        event = events[0]

        logging.warning(
            "Timed out in %s after %s seconds while fetching URLs for message %s: %s",
            self.queue_name,
            limit,
            event["message_id"],
            event["urls"],
        )
        raise InterruptConsumeError
