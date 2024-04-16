# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
from typing import Any, Dict, Mapping

from typing_extensions import override
from zulip_bots.lib import extract_query_without_mention

from zerver.lib.bot_lib import EmbeddedBotHandler, EmbeddedBotQuitError, get_bot_handler
from zerver.models import UserProfile
from zerver.models.bots import get_bot_services
from zerver.models.users import get_user_profile_by_id
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("embedded_bots")
class EmbeddedBotWorker(QueueProcessingWorker):
    def get_bot_api_client(self, user_profile: UserProfile) -> EmbeddedBotHandler:
        return EmbeddedBotHandler(user_profile)

    @override
    def consume(self, event: Mapping[str, Any]) -> None:
        user_profile_id = event["user_profile_id"]
        user_profile = get_user_profile_by_id(user_profile_id)

        message: Dict[str, Any] = event["message"]

        # TODO: Do we actually want to allow multiple Services per bot user?
        services = get_bot_services(user_profile_id)
        for service in services:
            bot_handler = get_bot_handler(str(service.name))
            if bot_handler is None:
                logging.error(
                    "Error: User %s has bot with invalid embedded bot service %s",
                    user_profile_id,
                    service.name,
                )
                continue
            try:
                if hasattr(bot_handler, "initialize"):
                    bot_handler.initialize(self.get_bot_api_client(user_profile))
                if event["trigger"] == "mention":
                    message["content"] = extract_query_without_mention(
                        message=message,
                        client=self.get_bot_api_client(user_profile),
                    )
                    assert message["content"] is not None
                bot_handler.handle_message(
                    message=message,
                    bot_handler=self.get_bot_api_client(user_profile),
                )
            except EmbeddedBotQuitError as e:
                logging.warning("%s", e)
