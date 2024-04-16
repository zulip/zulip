# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
from typing import Any, Mapping

from typing_extensions import override

from zerver.actions.user_activity import do_update_user_activity_interval
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models.users import get_user_profile_by_id
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("user_activity_interval")
class UserActivityIntervalWorker(QueueProcessingWorker):
    @override
    def consume(self, event: Mapping[str, Any]) -> None:
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        log_time = timestamp_to_datetime(event["time"])
        do_update_user_activity_interval(user_profile, log_time)
