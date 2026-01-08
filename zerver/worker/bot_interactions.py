# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
"""
Worker for processing bot interaction events.

When users interact with bot widgets (clicking buttons, selecting from menus,
submitting modals), those interactions are queued here and delivered to the
appropriate bot.
"""

import logging
from typing import Any

import requests
from django.conf import settings
from typing_extensions import override

from version import ZULIP_VERSION
from zerver.lib.outgoing_http import OutgoingSession
from zerver.models.bots import get_bot_services
from zerver.models.users import UserProfile, get_user_profile_by_id
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("bot_interactions")
class BotInteractionWorker(QueueProcessingWorker):
    """
    Process bot interaction events and deliver them to bots.

    For outgoing webhook bots, POSTs the interaction to the bot's URL.
    For embedded bots, calls the bot handler's handle_interaction method.
    """

    @override
    def consume(self, event: dict[str, Any]) -> None:
        bot_user_id = event["bot_user_id"]
        bot_profile = get_user_profile_by_id(bot_user_id)

        if bot_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
            self._handle_outgoing_webhook_interaction(event, bot_profile)
        elif bot_profile.bot_type == UserProfile.EMBEDDED_BOT:
            self._handle_embedded_bot_interaction(event, bot_profile)
        else:
            logger.warning(
                "Bot interaction event for unsupported bot type %s", bot_profile.bot_type
            )

    def _handle_outgoing_webhook_interaction(
        self, event: dict[str, Any], bot_profile: UserProfile
    ) -> None:
        """
        POST the interaction event to the bot's configured URL.

        Uses the same URL as the outgoing webhook service, but with a different
        payload format indicating this is an interaction event.
        """
        services = get_bot_services(bot_profile.id)
        if not services:
            logger.warning(
                "Bot %s has no services configured for interactions", bot_profile.id
            )
            return

        session = OutgoingSession(
            role="webhook",
            timeout=settings.OUTGOING_WEBHOOK_TIMEOUT_SECONDS,
            headers={"User-Agent": "ZulipBotInteraction/" + ZULIP_VERSION},
        )

        for service in services:
            # Build the interaction payload
            payload = {
                "type": "interaction",
                "token": service.token,
                "bot_email": bot_profile.email,
                "bot_full_name": bot_profile.full_name,
                # Interaction-specific fields
                "interaction_type": event["interaction_type"],
                "custom_id": event["custom_id"],
                "data": event["data"],
                # Context about the interaction
                "message": event["message"],
                "user": event["user"],
            }

            try:
                response = session.post(service.base_url, json=payload)
                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(
                        "Successfully delivered interaction to bot %s at %s",
                        bot_profile.email,
                        service.base_url,
                    )
                    # Process any response from the bot (e.g., message update)
                    self._process_interaction_response(event, bot_profile, response)
                else:
                    logger.warning(
                        "Bot %s returned status %s for interaction",
                        bot_profile.email,
                        response.status_code,
                    )
            except requests.exceptions.Timeout:
                logger.warning(
                    "Timeout delivering interaction to bot %s at %s",
                    bot_profile.email,
                    service.base_url,
                )
            except requests.exceptions.RequestException as e:
                logger.warning(
                    "Error delivering interaction to bot %s: %s",
                    bot_profile.email,
                    e,
                )

    def _handle_embedded_bot_interaction(
        self, event: dict[str, Any], bot_profile: UserProfile
    ) -> None:
        """
        Deliver the interaction to an embedded bot handler.

        Embedded bots can define a handle_interaction method to receive these events.
        """
        from zerver.lib.bot_lib import EmbeddedBotHandler, get_bot_handler
        from zerver.models.bots import get_bot_services

        services = get_bot_services(bot_profile.id)
        if not services:
            logger.warning(
                "Embedded bot %s has no services configured", bot_profile.id
            )
            return

        for service in services:
            try:
                bot_handler = get_bot_handler(str(service.name))
                if bot_handler is None:
                    continue

                embedded_bot_handler = EmbeddedBotHandler(bot_profile)

                # Check if the bot handler supports interactions
                if hasattr(bot_handler, "handle_interaction"):
                    bot_handler.handle_interaction(
                        interaction={
                            "type": event["interaction_type"],
                            "custom_id": event["custom_id"],
                            "data": event["data"],
                            "message": event["message"],
                            "user": event["user"],
                        },
                        bot_handler=embedded_bot_handler,
                    )
                    logger.info(
                        "Delivered interaction to embedded bot %s",
                        bot_profile.email,
                    )
                else:
                    logger.debug(
                        "Embedded bot %s does not support interactions",
                        bot_profile.email,
                    )

            except Exception as e:
                logger.exception(
                    "Error delivering interaction to embedded bot %s: %s",
                    bot_profile.email,
                    e,
                )

    def _process_interaction_response(
        self,
        event: dict[str, Any],
        bot_profile: UserProfile,
        response: requests.Response,
    ) -> None:
        """
        Process any response from the bot after receiving an interaction.

        Bots can respond to interactions with:
        - A message update (modify the widget that was interacted with)
        - A new message (reply to the interaction)
        - No response (just acknowledge)
        """
        import json

        from zerver.actions.message_send import check_send_message
        from zerver.models.clients import get_client

        try:
            if not response.text or response.text.strip() == "":
                return

            response_json = json.loads(response.text)
            if not isinstance(response_json, dict):
                return

            # Check if bot wants to send a reply message
            if "content" in response_json:
                message_info = event["message"]
                client = get_client("BotInteractionResponse")

                # Determine message type and recipient
                if message_info.get("stream_id"):
                    recipient_type_name = "stream"
                    # Need to get stream name from stream_id
                    from zerver.models import Stream

                    stream = Stream.objects.get(id=message_info["stream_id"])
                    message_to = [stream.name]
                    topic_name = message_info.get("topic")
                else:
                    recipient_type_name = "private"
                    message_to = [event["user"]["email"]]
                    topic_name = None

                check_send_message(
                    sender=bot_profile,
                    client=client,
                    recipient_type_name=recipient_type_name,
                    message_to=message_to,
                    topic_name=topic_name,
                    message_content=response_json["content"],
                    widget_content=response_json.get("widget_content"),
                    realm=bot_profile.realm,
                    skip_stream_access_check=True,
                )

        except json.JSONDecodeError:
            logger.debug("Bot response was not valid JSON, ignoring")
        except Exception as e:
            logger.warning(
                "Error processing bot interaction response: %s", e
            )
