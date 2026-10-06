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
    do_send_url_embed_data_event,
    is_latest_preview_draft,
    render_incoming_message,
    render_unsaved_message,
)
from zerver.lib.cache import (
    cache_delete,
    pending_preview_draft_cache_key,
    preview_draft_content_hash,
)
from zerver.lib.mention import MentionBackend, MentionData
from zerver.lib.url_preview import preview as url_preview
from zerver.lib.url_preview.types import UrlEmbedData
from zerver.models import Message, Realm, UserProfile
from zerver.models.users import get_user_profile_by_id
from zerver.worker.base import InterruptConsumeError, QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


def fetch_link_embed_data(url: str) -> UrlEmbedData | None:
    start_time = time.time()
    link_embed_data = url_preview.get_link_embed_data(url)
    logging.info("Time spent on get_link_embed_data for %s: %s", url, time.time() - start_time)
    return link_embed_data


@assign_queue("embed_links")
class FetchLinksEmbedData(QueueProcessingWorker):
    # This is a slow queue with network requests, so a disk write is negligible.
    # Update stats file after every consume call.
    CONSUME_ITERATIONS_BEFORE_UPDATE_STATS_NUM = 1

    @override
    def consume(self, event: Mapping[str, Any]) -> None:
        if event.get("type") == "url_embed_data":
            self.handle_url_embed_data_request(
                user_profile_id=event["user_id"],
                content=event["content"],
                cached_urls=event["cached_urls"],
                urls=event["urls"],
            )
            return

        url_embed_data = {url: fetch_link_embed_data(url) for url in event["urls"]}

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

    def handle_url_embed_data_request(
        self, *, user_profile_id: int, content: str, cached_urls: list[str], urls: list[str]
    ) -> None:
        try:
            sender = get_user_profile_by_id(user_profile_id)
        except UserProfile.DoesNotExist:
            # The user may have been deleted.
            return

        content_hash = preview_draft_content_hash(content)
        try:
            fetched_url_embed_data: dict[str, UrlEmbedData | None] = {}
            unavailable_urls = url_preview.get_unavailable_preview_urls(urls)
            for url in urls:
                if url in unavailable_urls:
                    continue
                if not is_latest_preview_draft(sender.id, content_hash):
                    return
                try:
                    fetched_url_embed_data[url] = fetch_link_embed_data(url)
                finally:
                    if fetched_url_embed_data.get(url) is None:
                        url_preview.mark_preview_url_unavailable(url)

            if not is_latest_preview_draft(sender.id, content_hash):
                return
            previewed_url_embed_data = {url: fetch_link_embed_data(url) for url in cached_urls}
            rendered_content = render_unsaved_message(
                sender,
                content,
                url_embed_data={**previewed_url_embed_data, **fetched_url_embed_data},
            ).rendered_content
            previewed_rendered_content = render_unsaved_message(
                sender, content, url_embed_data=previewed_url_embed_data
            ).rendered_content
            if rendered_content != previewed_rendered_content:
                do_send_url_embed_data_event(sender, content, rendered_content)
        finally:
            # Lets a later render queue a job for any links this one didn't fetch.
            cache_delete(pending_preview_draft_cache_key(sender.id, content_hash))

    @override
    def timer_expired(
        self, limit: int, events: list[dict[str, Any]], signal: int, frame: FrameType | None
    ) -> None:
        assert len(events) == 1
        event = events[0]

        if event.get("type") == "url_embed_data":
            fetching_for = f"a preview by user {event['user_id']}"
        else:
            fetching_for = f"message {event['message_id']}"
        logging.warning(
            "Timed out in %s after %s seconds while fetching URLs for %s: %s",
            self.queue_name,
            limit,
            fetching_for,
            event["urls"],
        )
        raise InterruptConsumeError
