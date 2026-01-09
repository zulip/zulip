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

        # Route based on event type
        event_type = event.get("type")
        if event_type == "command_invocation":
            self._handle_command_invocation(event, bot_profile)
            return

        # Widget interaction events
        if bot_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
            self._handle_outgoing_webhook_interaction(event, bot_profile)
        elif bot_profile.bot_type == UserProfile.EMBEDDED_BOT:
            self._handle_embedded_bot_interaction(event, bot_profile)
        else:
            logger.warning(
                "Bot interaction event for unsupported bot type %s", bot_profile.bot_type
            )

    def _handle_command_invocation(
        self, event: dict[str, Any], bot_profile: UserProfile
    ) -> None:
        """
        Handle a slash command invocation.

        Routes to the appropriate handler based on bot type.
        """
        if bot_profile.bot_type == UserProfile.OUTGOING_WEBHOOK_BOT:
            self._handle_outgoing_webhook_command(event, bot_profile)
        elif bot_profile.bot_type == UserProfile.EMBEDDED_BOT:
            self._handle_embedded_bot_command(event, bot_profile)
        else:
            logger.warning(
                "Command invocation for unsupported bot type %s", bot_profile.bot_type
            )

    def _send_command_error_status(
        self,
        event: dict[str, Any],
        bot_profile: UserProfile,
        error_message: str,
    ) -> None:
        """
        Send an error status update to the command invocation widget.

        This updates the widget to show the user that the bot failed to respond.
        """
        import json

        from zerver.actions.submessage import do_add_submessage

        message_id = event.get("message_id")
        if not message_id:
            return

        try:
            submessage_content = json.dumps({
                "type": "command_status",
                "status": "error",
                "error": error_message,
            })

            do_add_submessage(
                realm=bot_profile.realm,
                sender_id=bot_profile.id,
                message_id=message_id,
                msg_type="widget",
                content=submessage_content,
            )
        except Exception as e:
            logger.warning("Failed to send error status for command: %s", e)

    def _handle_outgoing_webhook_command(
        self, event: dict[str, Any], bot_profile: UserProfile
    ) -> None:
        """
        POST a command invocation to the bot's configured URL.
        """
        services = get_bot_services(bot_profile.id)
        if not services:
            logger.warning("Bot %s has no services configured for commands", bot_profile.id)
            return

        session = OutgoingSession(
            role="webhook",
            timeout=settings.OUTGOING_WEBHOOK_TIMEOUT_SECONDS,
            headers={"User-Agent": "ZulipBotCommand/" + ZULIP_VERSION},
        )

        for service in services:
            payload = {
                "type": "command_invocation",
                "token": service.token,
                "bot_email": bot_profile.email,
                "bot_full_name": bot_profile.full_name,
                "interaction_id": event.get("interaction_id"),
                "command": event["command"],
                "arguments": event.get("arguments", {}),
                "message_id": event["message_id"],
                "context": event.get("context", {}),
                "user": event.get("user", {}),
            }

            try:
                response = session.post(service.base_url, json=payload)
                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(
                        "Successfully delivered command to bot %s at %s",
                        bot_profile.email,
                        service.base_url,
                    )
                    self._process_command_response(event, bot_profile, response)
                    return  # Success - don't try other services
                else:
                    logger.warning(
                        "Bot %s returned status %s for command",
                        bot_profile.email,
                        response.status_code,
                    )
                    self._send_command_error_status(
                        event, bot_profile, f"Bot returned error (status {response.status_code})"
                    )
                    return
            except requests.exceptions.Timeout:
                logger.warning(
                    "Timeout delivering command to bot %s at %s",
                    bot_profile.email,
                    service.base_url,
                )
                self._send_command_error_status(
                    event, bot_profile, "Bot did not respond in time"
                )
                return
            except requests.exceptions.RequestException as e:
                logger.warning(
                    "Error delivering command to bot %s: %s",
                    bot_profile.email,
                    e,
                )
                self._send_command_error_status(
                    event, bot_profile, "Failed to reach bot"
                )
                return

    def _handle_embedded_bot_command(
        self, event: dict[str, Any], bot_profile: UserProfile
    ) -> None:
        """
        Deliver a command invocation to an embedded bot handler.
        """
        from zerver.lib.bot_lib import EmbeddedBotHandler, get_bot_handler

        services = get_bot_services(bot_profile.id)
        if not services:
            logger.warning("Embedded bot %s has no services configured", bot_profile.id)
            return

        for service in services:
            try:
                bot_handler = get_bot_handler(str(service.name))
                if bot_handler is None:
                    continue

                embedded_bot_handler = EmbeddedBotHandler(bot_profile)

                if hasattr(bot_handler, "handle_command"):
                    bot_handler.handle_command(
                        command={
                            "interaction_id": event.get("interaction_id"),
                            "name": event["command"],
                            "arguments": event.get("arguments", {}),
                            "message_id": event["message_id"],
                            "context": event.get("context", {}),
                            "user": event.get("user", {}),
                        },
                        bot_handler=embedded_bot_handler,
                    )
                    logger.info(
                        "Delivered command to embedded bot %s",
                        bot_profile.email,
                    )
                else:
                    logger.debug(
                        "Embedded bot %s does not support commands",
                        bot_profile.email,
                    )

            except Exception as e:
                logger.exception(
                    "Error delivering command to embedded bot %s: %s",
                    bot_profile.email,
                    e,
                )
                self._send_command_error_status(
                    event, bot_profile, "Bot encountered an error"
                )
                return

    def _process_command_response(
        self,
        event: dict[str, Any],
        bot_profile: UserProfile,
        response: requests.Response,
    ) -> None:
        """
        Process a bot's response to a command invocation.

        Bots can respond to commands with:
        - A new message (public reply)
        - An ephemeral response (visible only to the invoking user)
        - A private response (visible to a subset of users)
        - Widget content (interactive elements)
        """
        import json

        from zerver.actions.message_send import check_send_message
        from zerver.actions.submessage import do_add_submessage
        from zerver.models import Stream
        from zerver.models.clients import get_client

        try:
            if not response.text or response.text.strip() == "":
                return

            response_json = json.loads(response.text)
            if not isinstance(response_json, dict):
                return

            # Check if we have content or widget_content to send
            has_content = "content" in response_json and response_json["content"]
            has_widget = "widget_content" in response_json and response_json["widget_content"]

            if not has_content and not has_widget:
                return

            # Determine visibility for the response
            visible_user_ids: list[int] | None = None
            if response_json.get("ephemeral"):
                # Ephemeral response - only visible to the user who invoked the command
                visible_user_ids = [event["user"]["id"]]
            elif response_json.get("visible_user_ids"):
                # Private response - visible to specified users
                visible_user_ids = response_json["visible_user_ids"]

            # If response is ephemeral/private, create a submessage instead of a new message
            # This allows visibility filtering to work correctly
            if visible_user_ids is not None:
                message_id = event.get("message_id")
                if not message_id:
                    logger.warning("Cannot create ephemeral response: no message_id in event")
                    return

                # Create submessage with visibility constraint
                submessage_content = json.dumps(
                    {
                        "type": "ephemeral_response",
                        "interaction_id": event.get("interaction_id"),
                        "content": response_json.get("content", ""),
                        "widget_content": response_json.get("widget_content"),
                    }
                )

                do_add_submessage(
                    realm=bot_profile.realm,
                    sender_id=bot_profile.id,
                    message_id=message_id,
                    msg_type="widget",
                    content=submessage_content,
                    visible_user_ids=visible_user_ids,
                )
                logger.info("Created ephemeral/private submessage for command response")
                return

            # Public response - send as a new message
            # If we only have widget, provide minimal content
            content = response_json.get("content", "")
            if not content and has_widget:
                content = "\u200b"  # Zero-width space as minimal content

            context = event.get("context", {})
            client = get_client("BotCommandResponse")

            if context.get("stream_id"):
                recipient_type_name = "stream"
                stream = Stream.objects.get(id=context["stream_id"])
                message_to = [stream.name]
                topic_name = context.get("topic")
            else:
                recipient_type_name = "private"
                user_data = event.get("user", {})
                if not user_data.get("email"):
                    logger.warning("Cannot send DM response: no user email in event")
                    return
                message_to = [user_data["email"]]
                topic_name = None

            widget_content = response_json.get("widget_content")
            if widget_content is not None and not isinstance(widget_content, str):
                widget_content = json.dumps(widget_content)

            check_send_message(
                sender=bot_profile,
                client=client,
                recipient_type_name=recipient_type_name,
                message_to=message_to,
                topic_name=topic_name,
                message_content=content,
                widget_content=widget_content,
                realm=bot_profile.realm,
                skip_stream_access_check=True,
            )
            logger.info("Sent bot command response message")

        except json.JSONDecodeError:
            logger.debug("Bot command response was not valid JSON, ignoring")
        except Exception as e:
            logger.warning("Error processing bot command response: %s", e)

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
            logger.warning("Bot %s has no services configured for interactions", bot_profile.id)
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
                "interaction_id": event.get("interaction_id"),
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
            logger.warning("Embedded bot %s has no services configured", bot_profile.id)
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
                            "interaction_id": event.get("interaction_id"),
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
        - An ephemeral response (visible only to the interacting user)
        - A private response (visible to a subset of users)
        - No response (just acknowledge)
        """
        import json

        from zerver.actions.message_send import check_send_message
        from zerver.actions.submessage import do_add_submessage
        from zerver.models.clients import get_client

        try:
            if not response.text or response.text.strip() == "":
                return

            response_json = json.loads(response.text)
            if not isinstance(response_json, dict):
                return

            # Determine visibility for the response
            visible_user_ids: list[int] | None = None
            if response_json.get("ephemeral"):
                # Ephemeral response - only visible to interacting user
                visible_user_ids = [event["user"]["id"]]
            elif response_json.get("visible_user_ids"):
                # Private response - visible to specified users
                visible_user_ids = response_json["visible_user_ids"]

            # If response is ephemeral/private, create a submessage instead of a new message
            # This allows visibility filtering to work correctly
            if visible_user_ids is not None and "content" in response_json:
                message_info = event["message"]
                message_id = message_info["id"]

                # Create submessage with visibility constraint
                submessage_content = json.dumps(
                    {
                        "type": "bot_response",
                        "interaction_id": event.get("interaction_id"),
                        "content": response_json["content"],
                        "widget_content": response_json.get("widget_content"),
                    }
                )

                do_add_submessage(
                    realm=bot_profile.realm,
                    sender_id=bot_profile.id,
                    message_id=message_id,
                    msg_type="widget",
                    content=submessage_content,
                    visible_user_ids=visible_user_ids,
                )
                logger.info("Created ephemeral/private submessage for interaction response")
                return

            # Check if bot wants to send a public reply message
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

                # widget_content must be a JSON string for check_send_message
                # but bots may send it as an object for convenience
                widget_content = response_json.get("widget_content")
                if widget_content is not None and not isinstance(widget_content, str):
                    widget_content = json.dumps(widget_content)

                check_send_message(
                    sender=bot_profile,
                    client=client,
                    recipient_type_name=recipient_type_name,
                    message_to=message_to,
                    topic_name=topic_name,
                    message_content=response_json["content"],
                    widget_content=widget_content,
                    realm=bot_profile.realm,
                    skip_stream_access_check=True,
                )

        except json.JSONDecodeError:
            logger.debug("Bot response was not valid JSON, ignoring")
        except Exception as e:
            logger.warning("Error processing bot interaction response: %s", e)
