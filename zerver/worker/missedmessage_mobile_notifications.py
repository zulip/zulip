# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
from typing import Any

from django.conf import settings
from typing_extensions import override

from zerver.lib.push_notifications import (
    handle_push_notification,
    handle_remove_push_notification,
    initialize_push_notifications,
)
from zerver.lib.push_registration import (
    RegisterPushDeviceToBouncerQueueItem,
    handle_register_push_device_to_bouncer,
)
from zerver.lib.queue import retry_event
from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


from dataclasses import dataclass
from typing import cast


@dataclass
class MobileNotificationEvent:
    type: str | None = None
    user_profile_id: int | None = None
    message_ids: list[int] | None = None
    payload: dict[str, Any] | None = None
    # We maintain the raw event for passing downstream to functions that are not yet migrated
    _raw_event: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, raw_event: dict[str, Any]) -> "MobileNotificationEvent":
        return cls(
            type=raw_event.get("type"),
            user_profile_id=raw_event.get("user_profile_id"),
            message_ids=raw_event.get("message_ids"),
            payload=raw_event.get("payload"),
            _raw_event=raw_event,
        )


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
        worker_num: int | None = None,
    ) -> None:
        if settings.MOBILE_NOTIFICATIONS_SHARDS > 1 and worker_num is not None:  # nocoverage
            self.queue_name += f"_shard{worker_num}"
        super().__init__(threaded, disable_timeout, worker_num)

    @override
    def start(self) -> None:
        # initialize_push_notifications doesn't strictly do anything
        # beyond printing some logging warnings if push notifications
        # are not available in the current configuration.
        initialize_push_notifications()
        super().start()

    @override
    def consume(self, raw_event: dict[str, Any]) -> None:
        event = MobileNotificationEvent.from_dict(raw_event)
        try:
            if event.type == "register_push_device_to_bouncer":
                assert event.payload is not None
                handle_register_push_device_to_bouncer(
                    cast(RegisterPushDeviceToBouncerQueueItem, event.payload)
                )
            elif event.type == "remove":
                assert event.user_profile_id is not None
                assert event.message_ids is not None
                handle_remove_push_notification(event.user_profile_id, event.message_ids)
            else:
                assert event.user_profile_id is not None
                assert event._raw_event is not None
                handle_push_notification(event.user_profile_id, event._raw_event)
        except PushNotificationBouncerRetryLaterError:

            def failure_processor(raw_event: dict[str, Any]) -> None:
                if event.type == "register_push_device_to_bouncer":
                    logger.warning(
                        "Maximum retries exceeded for device_id:%s event:register_push_device_to_bouncer",
                        event.payload["device_id"] if event.payload else "unknown",
                    )
                else:
                    logger.warning(
                        "Maximum retries exceeded for trigger:%s event:push_notification",
                        event.user_profile_id,
                    )

            retry_event(self.queue_name, raw_event, failure_processor)
