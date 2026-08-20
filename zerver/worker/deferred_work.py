# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
import time
from typing import Any

from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.actions.data_import import import_slack_data
from zerver.actions.message_flags import do_mark_stream_messages_as_read
from zerver.actions.realm_export import export_realm_from_event
from zerver.actions.realm_settings import scrub_deactivated_realm
from zerver.lib.push_notifications import clear_push_device_tokens
from zerver.lib.queue import retry_event
from zerver.lib.remote_server import (
    PushNotificationBouncerRetryLaterError,
    send_server_data_to_push_bouncer,
)
from zerver.lib.soft_deactivation import reactivate_user_if_soft_deactivated
from zerver.lib.upload import handle_reupload_emojis_event
from zerver.models import Realm
from zerver.models.users import get_user_profile_by_id
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("deferred_work")
class DeferredWorker(QueueProcessingWorker):
    """This queue processor is intended for cases where we want to trigger a
    potentially expensive, not urgent, job to be run on a separate
    thread from the Django worker that initiated it (E.g. so we that
    can provide a low-latency HTTP response or avoid risk of request
    timeouts for an operation that could in rare cases take minutes).

    Several of these event types can be routed to a dedicated queue
    instead, via a dedicated_*_queue setting in zulip.conf. Their handlers
    below must not be removed even then: they remain the default path, and
    they drain any events already queued here when a server opts in --
    stale deferred_work events can linger across upgrades for a long time.
    """

    # Because these operations have no SLO, and can take minutes,
    # remove any processing timeouts
    MAX_CONSUME_SECONDS = None

    @override
    def consume(self, event: dict[str, Any]) -> None:
        start = time.time()
        if event["type"] == "mark_stream_messages_as_read":
            user_profile = get_user_profile_by_id(event["user_profile_id"])
            logger.info(
                "Marking messages as read for user %s, stream_recipient_ids %s",
                user_profile.id,
                event["stream_recipient_ids"],
            )

            for recipient_id in event["stream_recipient_ids"]:
                count = do_mark_stream_messages_as_read(user_profile, recipient_id)
                logger.info(
                    "Marked %s messages as read for user %s, stream_recipient_id %s",
                    count,
                    user_profile.id,
                    recipient_id,
                )
        elif event["type"] == "clear_push_device_tokens":
            logger.info(
                "Clearing push device tokens for user_profile_id %s",
                event["user_profile_id"],
            )
            try:
                clear_push_device_tokens(event["user_profile_id"])
            except PushNotificationBouncerRetryLaterError:

                def failure_processor(event: dict[str, Any]) -> None:
                    logger.warning(
                        "Maximum retries exceeded for trigger:%s event:clear_push_device_tokens",
                        event["user_profile_id"],
                    )

                retry_event(self.queue_name, event, failure_processor)
        elif event["type"] == "realm_export":
            export_realm_from_event(event, threaded=self.threaded, logger=logger)
        elif event["type"] == "reupload_realm_emoji":
            # This is a special event queued by the migration for reuploading emojis.
            # We don't want to run the necessary code in the actual migration, so it simply
            # queues the necessary event, and the actual work is done here in the queue worker.
            realm = Realm.objects.get(id=event["realm_id"])
            logger.info("Processing reupload_realm_emoji event for realm %s", realm.id)
            handle_reupload_emojis_event(realm, logger)
        elif event["type"] == "soft_reactivate":
            logger.info(
                "Starting soft reactivation for user_profile_id %s",
                event["user_profile_id"],
            )
            user_profile = get_user_profile_by_id(event["user_profile_id"])
            reactivate_user_if_soft_deactivated(user_profile)
        elif event["type"] == "push_bouncer_update_for_realm":
            # In the future we may use the realm_id to send only that single realm's info.
            realm_id = event["realm_id"]
            logger.info("Updating push bouncer with metadata on behalf of realm %s", realm_id)
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        elif event["type"] == "scrub_deactivated_realm":
            realms_to_scrub = Realm.objects.filter(
                deactivated=True,
                scheduled_deletion_date__lte=timezone_now(),
            )
            for realm in realms_to_scrub:
                scrub_deactivated_realm(realm)
        elif event["type"] == "import_slack_data":
            import_slack_data(event)

        end = time.time()
        logger.info(
            "deferred_work processed %s event (%dms)",
            event["type"],
            (end - start) * 1000,
        )
