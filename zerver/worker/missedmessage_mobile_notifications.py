# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from typing_extensions import override

from zerver.lib.push_notifications import (
    handle_push_notification,
    handle_remove_push_notification,
    initialize_push_notifications,
)
from zerver.lib.queue import retry_event
from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("missedmessage_mobile_notifications")
class PushNotificationsWorker(QueueProcessingWorker):
    # The use of aioapns in the backend means that we cannot use
    # SIGALRM to limit how long a consume takes, as SIGALRM does not
    # play well with asyncio.
    MAX_CONSUME_SECONDS = None

    @override
    def __init__(
        self,
        threaded: bool = False,
        disable_timeout: bool = False,
        worker_num: Optional[int] = None,
    ) -> None:
        if settings.MOBILE_NOTIFICATIONS_SHARDS > 1 and worker_num is not None:  # nocoverage
            self.queue_name = self.queue_name + f"_shard{worker_num}"
        super().__init__(threaded, disable_timeout, worker_num)

    @override
    def start(self) -> None:
        # initialize_push_notifications doesn't strictly do anything
        # beyond printing some logging warnings if push notifications
        # are not available in the current configuration.
        initialize_push_notifications()
        super().start()

    @override
    def consume(self, event: Dict[str, Any]) -> None:
        try:
            if event.get("type", "add") == "remove":
                message_ids = event["message_ids"]
                handle_remove_push_notification(event["user_profile_id"], message_ids)
            else:
                handle_push_notification(event["user_profile_id"], event)
        except PushNotificationBouncerRetryLaterError:

            def failure_processor(event: Dict[str, Any]) -> None:
                logger.warning(
                    "Maximum retries exceeded for trigger:%s event:push_notification",
                    event["user_profile_id"],
                )

            retry_event(self.queue_name, event, failure_processor)
