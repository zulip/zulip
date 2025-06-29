import abc
import json
import logging
from contextlib import suppress
from time import perf_counter
from typing import Any, AnyStr

import requests
from django.conf import settings
from django.utils.translation import gettext as _
from requests import Response
from typing_extensions import override

from version import ZULIP_VERSION
from zerver.actions.message_send import check_send_message
from zerver.lib.exceptions import JsonableError, StreamDoesNotExistError
from zerver.lib.message_cache import MessageDict
from zerver.lib.outgoing_http import OutgoingSession
from zerver.lib.queue import retry_event
from zerver.lib.topic import get_topic_from_message_info
from zerver.lib.url_encoding import message_link_url
from zerver.lib.users import check_can_access_user, check_user_can_access_all_users
from zerver.models import Realm, Service, UserProfile
from zerver.models.bots import GENERIC_INTERFACE, SLACK_INTERFACE
from zerver.models.clients import get_client
from zerver.models.users import get_user_profile_by_id


class OutgoingWebhookServiceInterface(abc.ABC):
    def __init__(self, token: str, user_profile: UserProfile, service_name: str) -> None:
        self.token: str = token
        self.user_profile: UserProfile = user_profile
        self.service_name: str = service_name
        self.session: requests.Session = OutgoingSession(
            role="webhook",
            timeout=settings.OUTGOING_WEBHOOK_TIMEOUT_SECONDS,
            headers={"User-Agent": "ZulipOutgoingWebhook/" + ZULIP_VERSION},
        )

    @abc.abstractmethod
    def make_request(self, base_url: str, event: dict[str, Any], realm: Realm) -> Response | None:
        raise NotImplementedError

    @abc.abstractmethod
    def process_success(self, response_json: dict[str, Any]) -> dict[str, Any] | None:
        raise NotImplementedError


class GenericOutgoingWebhookService(OutgoingWebhookServiceInterface):
    @override
    def make_request(self, base_url: str, event: dict[str, Any], realm: Realm) -> Response | None:
        """
        We send a simple version of the message to outgoing
        webhooks, since most of them really only need
        `content` and a few other fields.  We may eventually
        allow certain bots to get more information, but
        that's not a high priority.  We do send the gravatar
        info to the clients (so they don't have to compute
        it themselves).
        """
        message_dict = MessageDict.finalize_payload(
            event["message"],
            apply_markdown=False,
            client_gravatar=False,
            allow_empty_topic_name=True,
            keep_rendered_content=True,
            can_access_sender=check_user_can_access_all_users(self.user_profile)
            or check_can_access_user(
                get_user_profile_by_id(event["message"]["sender_id"]), self.user_profile
            ),
            realm_host=realm.host,
            is_incoming_1_to_1=event["message"]["recipient_id"] == self.user_profile.recipient_id,
        )

        request_data = {
            "data": event["command"],
            "message": message_dict,
            "bot_email": self.user_profile.email,
            "bot_full_name": self.user_profile.full_name,
            "token": self.token,
            "trigger": event["trigger"],
        }

        return self.session.post(base_url, json=request_data)

    @override
    def process_success(self, response_json: dict[str, Any]) -> dict[str, Any] | None:
        if response_json.get("response_not_required", False):
            return None

        if "response_string" in response_json:
            # We are deprecating response_string.
            content = str(response_json["response_string"])
            success_data = dict(content=content)
            return success_data

        if "content" in response_json:
            content = str(response_json["content"])
            success_data = dict(content=content)
            if "widget_content" in response_json:
                success_data["widget_content"] = response_json["widget_content"]
            return success_data

        return None


class SlackOutgoingWebhookService(OutgoingWebhookServiceInterface):
    @override
    def make_request(self, base_url: str, event: dict[str, Any], realm: Realm) -> Response | None:
        if event["message"]["type"] == "private":
            failure_message = "Slack outgoing webhooks don't support direct messages."
            fail_with_message(event, failure_message)
            return None

        # https://api.slack.com/legacy/custom-integrations/outgoing-webhooks#legacy-info__post-data
        # documents the Slack outgoing webhook format:
        #
        # token=XXXXXXXXXXXXXXXXXX
        # team_id=T0001
        # team_domain=example
        # channel_id=C2147483705
        # channel_name=test
        # thread_ts=1504640714.003543
        # timestamp=1504640775.000005
        # user_id=U2147483697
        # user_name=Steve
        # text=googlebot: What is the air-speed velocity of an unladen swallow?
        # trigger_word=googlebot:

        request_data = [
            ("token", self.token),
            ("team_id", f"T{realm.id}"),
            ("team_domain", realm.host),
            ("channel_id", f"C{event['message']['stream_id']}"),
            ("channel_name", event["message"]["display_recipient"]),
            ("thread_ts", event["message"]["timestamp"]),
            ("timestamp", event["message"]["timestamp"]),
            ("user_id", f"U{event['message']['sender_id']}"),
            ("user_name", event["message"]["sender_full_name"]),
            ("text", event["command"]),
            ("trigger_word", event["trigger"]),
            ("service_id", event["user_profile_id"]),
        ]
        return self.session.post(base_url, data=request_data)

    @override
    def process_success(self, response_json: dict[str, Any]) -> dict[str, Any] | None:
        if "text" in response_json:
            content = response_json["text"]
            success_data = dict(content=content)
            return success_data

        return None


AVAILABLE_OUTGOING_WEBHOOK_INTERFACES: dict[str, Any] = {
    GENERIC_INTERFACE: GenericOutgoingWebhookService,
    SLACK_INTERFACE: SlackOutgoingWebhookService,
}


def get_service_interface_class(interface: str) -> Any:
    if interface not in AVAILABLE_OUTGOING_WEBHOOK_INTERFACES:
        return AVAILABLE_OUTGOING_WEBHOOK_INTERFACES[GENERIC_INTERFACE]
    else:
        return AVAILABLE_OUTGOING_WEBHOOK_INTERFACES[interface]


def get_outgoing_webhook_service_handler(service: Service) -> Any:
    service_interface_class = get_service_interface_class(service.interface_name())
    service_interface = service_interface_class(
        token=service.token, user_profile=service.user_profile, service_name=service.name
    )
    return service_interface


def send_response_message(
    bot_id: int, message_info: dict[str, Any], response_data: dict[str, Any]
) -> None:
    """
    bot_id is the user_id of the bot sending the response

    message_info is used to address the message and should have these fields:
        type - "stream" or "private"
        display_recipient - like we have in other message events
        topic - see get_topic_from_message_info

    response_data is what the bot wants to send back and has these fields:
        content - raw Markdown content for Zulip to render

    WARNING: This function sends messages bypassing the stream access check
    for the bot - so use with caution to not call this in codepaths
    that might let someone send arbitrary messages to any stream through this.
    """

    recipient_type_name = message_info["type"]
    display_recipient = message_info["display_recipient"]
    try:
        topic_name: str | None = get_topic_from_message_info(message_info)
    except KeyError:
        topic_name = None

    bot_user = get_user_profile_by_id(bot_id)
    realm = bot_user.realm
    client = get_client("OutgoingWebhookResponse")

    content = response_data.get("content")
    assert content

    widget_content = response_data.get("widget_content")

    if recipient_type_name == "stream":
        message_to = [display_recipient]
    elif recipient_type_name == "private":
        message_to = [recipient["email"] for recipient in display_recipient]
    else:
        raise JsonableError(_("Invalid message type"))

    check_send_message(
        sender=bot_user,
        client=client,
        recipient_type_name=recipient_type_name,
        message_to=message_to,
        topic_name=topic_name,
        message_content=content,
        widget_content=widget_content,
        realm=realm,
        skip_stream_access_check=True,
    )


def fail_with_message(event: dict[str, Any], failure_message: str) -> None:
    bot_id = event["user_profile_id"]
    message_info = event["message"]
    content = "Failure! " + failure_message
    response_data = dict(content=content)
    # If the stream has vanished while we were failing, there's no
    # reasonable place to report the error.
    with suppress(StreamDoesNotExistError):
        send_response_message(bot_id=bot_id, message_info=message_info, response_data=response_data)


def get_message_url(event: dict[str, Any]) -> str:
    bot_user = get_user_profile_by_id(event["user_profile_id"])
    message = event["message"]
    realm = bot_user.realm

    return message_link_url(
        realm=realm,
        message=message,
    )


def notify_bot_owner(
    event: dict[str, Any],
    status_code: int | None = None,
    response_content: AnyStr | None = None,
    failure_message: str | None = None,
    exception: Exception | None = None,
) -> None:
    message_url = get_message_url(event)
    bot_id = event["user_profile_id"]
    bot = get_user_profile_by_id(bot_id)
    bot_owner = bot.bot_owner
    assert bot_owner is not None

    notification_message = f"[A message]({message_url}) to your bot @_**{bot.full_name}** triggered an outgoing webhook."
    if exception:
        notification_message += (
            "\nWhen trying to send a request to the webhook service, an exception "
            f"of type {type(exception).__name__} occurred:\n```\n{exception}\n```"
        )
    elif failure_message:
        notification_message += "\n" + failure_message
    elif status_code == 407:
        notification_message += (
            "\nThe URL configured for the webhook is for a private or disallowed network."
        )
    elif status_code:
        notification_message += f"\nThe webhook got a response with status code *{status_code}*."

    if response_content:
        notification_message += (
            f"\nThe response contains the following payload:\n```\n{response_content!r}\n```"
        )

    message_info = dict(
        type="private",
        display_recipient=[dict(email=bot_owner.email)],
    )
    response_data = dict(content=notification_message)
    send_response_message(bot_id=bot_id, message_info=message_info, response_data=response_data)


def request_retry(event: dict[str, Any], failure_message: str | None = None) -> None:
    def failure_processor(event: dict[str, Any]) -> None:
        """
        The name of the argument is 'event' on purpose. This argument will hide
        the 'event' argument of the request_retry function. Keeping the same name
        results in a smaller diff.
        """
        bot_user = get_user_profile_by_id(event["user_profile_id"])
        fail_with_message(event, "Bot is unavailable")
        notify_bot_owner(event, failure_message=failure_message)
        logging.warning(
            "Maximum retries exceeded for trigger:%s event:%s",
            bot_user.email,
            event["command"],
        )

    retry_event("outgoing_webhooks", event, failure_processor)


def process_success_response(
    event: dict[str, Any], service_handler: Any, response: Response
) -> None:
    try:
        response_json = json.loads(response.text)
    except json.JSONDecodeError:
        raise JsonableError(_("Invalid JSON in response"))

    if response_json == "":
        # Versions of zulip_botserver before 2021-05 used
        # json.dumps("") as their "no response required" success
        # response; handle that for backwards-compatibility.
        return

    if not isinstance(response_json, dict):
        raise JsonableError(_("Invalid response format"))

    success_data = service_handler.process_success(response_json)

    if success_data is None:
        return

    content = success_data.get("content")

    if content is None or content.strip() == "":
        return

    widget_content = success_data.get("widget_content")
    bot_id = event["user_profile_id"]
    message_info = event["message"]
    response_data = dict(content=content, widget_content=widget_content)
    send_response_message(bot_id=bot_id, message_info=message_info, response_data=response_data)


def do_rest_call(
    base_url: str,
    event: dict[str, Any],
    service_handler: OutgoingWebhookServiceInterface,
) -> Response | None:
    """Returns response of call if no exception occurs."""
    try:
        start_time = perf_counter()
        bot_profile = service_handler.user_profile
        response = service_handler.make_request(
            base_url,
            event,
            bot_profile.realm,
        )
        logging.info(
            "Outgoing webhook request from %s@%s took %f seconds",
            bot_profile.id,
            bot_profile.realm.string_id,
            perf_counter() - start_time,
        )
        if response is None:
            return None
        if str(response.status_code).startswith("2"):
            try:
                process_success_response(event, service_handler, response)
            except JsonableError as e:
                response_message = e.msg
                logging.info("Outhook trigger failed:", stack_info=True)
                fail_with_message(event, response_message)
                response_message = f"The outgoing webhook server attempted to send a message in Zulip, but that request resulted in the following error:\n> {e}"
                notify_bot_owner(
                    event, response_content=response.text, failure_message=response_message
                )
                return None
        else:
            logging.warning(
                "Message %(message_url)s triggered an outgoing webhook, returning status "
                'code %(status_code)s.\n Content of response (in quotes): "'
                '%(response)s"',
                {
                    "message_url": get_message_url(event),
                    "status_code": response.status_code,
                    "response": response.text,
                },
            )
            failure_message = f"Third party responded with {response.status_code}"
            fail_with_message(event, failure_message)
            notify_bot_owner(event, response.status_code, response.content)
        return response
    except requests.exceptions.Timeout:
        logging.info(
            "Trigger event %s on %s timed out. Retrying",
            event["command"],
            event["service_name"],
        )
        failure_message = (
            f"Request timed out after {settings.OUTGOING_WEBHOOK_TIMEOUT_SECONDS} seconds."
        )
        request_retry(event, failure_message=failure_message)
        return None

    except requests.exceptions.ConnectionError:
        logging.info(
            "Trigger event %s on %s resulted in a connection error. Retrying",
            event["command"],
            event["service_name"],
        )
        failure_message = "A connection error occurred. Is my bot server down?"
        request_retry(event, failure_message=failure_message)
        return None

    except requests.exceptions.RequestException as e:
        response_message = (
            f"An exception of type *{type(e).__name__}* occurred for message `{event['command']}`! "
            "See the Zulip server logs for more information."
        )
        logging.exception("Outhook trigger failed:", stack_info=True)
        fail_with_message(event, response_message)
        notify_bot_owner(event, exception=e)
        return None
