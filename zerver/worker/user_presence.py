# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
from typing import Any, Mapping

from typing_extensions import override

from zerver.actions.presence import do_update_user_presence
from zerver.lib.timestamp import timestamp_to_datetime
from zerver.models.clients import get_client
from zerver.models.users import get_user_profile_by_id
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("user_presence")
class UserPresenceWorker(QueueProcessingWorker):
    @override
    def consume(self, event: Mapping[str, Any]) -> None:
        logging.debug("Received presence event: %s", event)
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        client = get_client(event["client"])
        log_time = timestamp_to_datetime(event["time"])
        status = event["status"]
        do_update_user_presence(user_profile, client, log_time, status)
