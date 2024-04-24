# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
from typing import Any, Mapping

from typing_extensions import override

from zerver.lib.digest import bulk_handle_digest_email
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("digest_emails")
class DigestWorker(QueueProcessingWorker):  # nocoverage
    # Who gets a digest is entirely determined by the enqueue_digest_emails
    # management command, not here.
    @override
    def consume(self, event: Mapping[str, Any]) -> None:
        if "user_ids" in event:
            user_ids = event["user_ids"]
        else:
            # legacy code may have enqueued a single id
            user_ids = [event["user_profile_id"]]
        bulk_handle_digest_email(user_ids, event["cutoff"])
