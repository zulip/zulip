# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
from typing import Any

from typing_extensions import override

from zerver.lib.soft_deactivation import reactivate_user_if_soft_deactivated
from zerver.models.users import get_user_profile_by_id
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("soft_reactivation")
class SoftReactivationWorker(QueueProcessingWorker):
    """Backfills the UserMessage rows skipped while a long-term-idle user was
    soft-deactivated, in response to a signal that the user is likely about to
    return (a notification or password-reset email).

    It's undesirable for these jobs to share the deferred_work queue with jobs
    such as realm exports, which can take many minutes: a prolonged delay in
    processing a soft reactivation gives the returning user a bad experience,
    and can race with the synchronous reactivation that runs when the user
    loads the app. A server can opt into this dedicated queue via the
    DEDICATED_SOFT_REACTIVATION_QUEUE setting.
    """

    # Soft reactivation has always run without a per-event timeout, as part of
    # the deferred_work queue, and the backfill for a very idle user can
    # legitimately take a while; preserve that rather than risk killing a job
    # partway through.
    MAX_CONSUME_SECONDS = None

    @override
    def consume(self, event: dict[str, Any]) -> None:
        logger.info(
            "Starting soft reactivation for user_profile_id %s",
            event["user_profile_id"],
        )
        user_profile = get_user_profile_by_id(event["user_profile_id"])
        reactivate_user_if_soft_deactivated(user_profile)
