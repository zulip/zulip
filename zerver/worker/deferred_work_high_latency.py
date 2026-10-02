# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
import time
from typing import Any

from typing_extensions import override

from zerver.actions.data_import import import_slack_data
from zerver.actions.realm_export import export_realm_from_event
from zerver.actions.realm_settings import clean_deactivated_realm_data
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("deferred_work_high_latency")
class DeferredWorkHighLatencyWorker(QueueProcessingWorker):
    """Runs deferred work with no latency expectations at all, currently
    realm data exports, Slack imports and scrubbing deactivated realms,
    each of which can take many minutes.

    Such jobs normally share the deferred_work queue, where they hold up
    its latency-sensitive jobs. A server can opt into this dedicated queue
    via the DEDICATED_DEFERRED_WORK_HIGH_LATENCY_QUEUE setting to isolate
    them.
    """

    MAX_CONSUME_SECONDS = None

    @override
    def consume(self, event: dict[str, Any]) -> None:
        start = time.time()
        if event["type"] == "realm_export":
            export_realm_from_event(event, threaded=self.threaded, logger=logger)
        elif event["type"] == "import_slack_data":
            import_slack_data(event)
        elif event["type"] == "scrub_deactivated_realm":
            clean_deactivated_realm_data()
        else:
            raise AssertionError(f"Unexpected event type {event['type']}")

        end = time.time()
        logger.info(
            "deferred_work_high_latency processed %s event (%dms)",
            event["type"],
            (end - start) * 1000,
        )
