# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
from typing import Any

from typing_extensions import override

from zerver.lib.bot_lib import do_flag_service_bots_messages_as_processed
from zerver.lib.outgoing_webhook import do_rest_call, get_outgoing_webhook_service_handler
from zerver.models.bots import get_bot_services
from zerver.models.users import get_user_profile_by_id
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("outgoing_webhooks")
class OutgoingWebhookWorker(QueueProcessingWorker):
    @override
    def consume(self, event: dict[str, Any]) -> None:
        message = event["message"]
        event["command"] = message["content"]
        bot_profile = get_user_profile_by_id(event["user_profile_id"])

        services = get_bot_services(event["user_profile_id"])
        for service in services:
            event["service_name"] = str(service.name)
            service_handler = get_outgoing_webhook_service_handler(service)
            do_rest_call(service.base_url, event, service_handler)

        do_flag_service_bots_messages_as_processed(bot_profile, [message["id"]])
