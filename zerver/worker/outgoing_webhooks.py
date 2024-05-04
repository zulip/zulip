# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
from typing import Any, Dict

from typing_extensions import override

from zerver.lib.outgoing_webhook import do_rest_call, get_outgoing_webhook_service_handler
from zerver.models.bots import get_bot_services
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("outgoing_webhooks")
class OutgoingWebhookWorker(QueueProcessingWorker):
    @override
    def consume(self, event: Dict[str, Any]) -> None:
        message = event["message"]
        event["command"] = message["content"]

        services = get_bot_services(event["user_profile_id"])
        for service in services:
            event["service_name"] = str(service.name)
            service_handler = get_outgoing_webhook_service_handler(service)
            do_rest_call(service.base_url, event, service_handler)
