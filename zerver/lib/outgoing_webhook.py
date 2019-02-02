from typing import Any, AnyStr, Dict, Optional

import requests
import json
import logging
from requests import Response

from django.utils.translation import ugettext as _

from zerver.models import UserProfile, get_user_profile_by_id, get_client, \
    GENERIC_INTERFACE, Service, SLACK_INTERFACE, email_to_domain
from zerver.lib.actions import check_send_message
from zerver.lib.queue import retry_event
from zerver.lib.topic import get_topic_from_message_info
from zerver.lib.url_encoding import near_message_url
from zerver.decorator import JsonableError

from version import ZULIP_VERSION

class OutgoingWebhookServiceInterface:

    def __init__(self, token: str, user_profile: UserProfile, service_name: str) -> None:
        self.token = token  # type: str
        self.user_profile = user_profile  # type: UserProfile
        self.service_name = service_name  # type: str

class GenericOutgoingWebhookService(OutgoingWebhookServiceInterface):

    def build_bot_request(self, event: Dict[str, Any]) -> Optional[Any]:
        request_data = {"data": event['command'],
                        "message": event['message'],
                        "bot_email": self.user_profile.email,
                        "token": self.token,
                        "trigger": event['trigger']}
        return json.dumps(request_data)

    def send_data_to_server(self,
                            base_url: str,
                            request_data: Any) -> Response:
        user_agent = 'ZulipOutgoingWebhook/' + ZULIP_VERSION
        headers = {
            'content-type': 'application/json',
            'User-Agent': user_agent,
        }
        response = requests.request('POST', base_url, data=request_data, headers=headers)
        return response

    def process_success(self, response_json: Dict[str, Any],
                        event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if "response_not_required" in response_json and response_json['response_not_required']:
            return None

        if "response_string" in response_json:
            # We are deprecating response_string.
            content = str(response_json['response_string'])
            success_data = dict(content=content)
            return success_data

        if "content" in response_json:
            content = str(response_json['content'])
            success_data = dict(content=content)
            if 'widget_content' in response_json:
                success_data['widget_content'] = response_json['widget_content']
            return success_data

        return None

class SlackOutgoingWebhookService(OutgoingWebhookServiceInterface):

    def build_bot_request(self, event: Dict[str, Any]) -> Optional[Any]:
        if event['message']['type'] == 'private':
            failure_message = "Slack outgoing webhooks don't support private messages."
            fail_with_message(event, failure_message)
            return None

        request_data = [("token", self.token),
                        ("team_id", event['message']['sender_realm_str']),
                        ("team_domain", email_to_domain(event['message']['sender_email'])),
                        ("channel_id", event['message']['stream_id']),
                        ("channel_name", event['message']['display_recipient']),
                        ("timestamp", event['message']['timestamp']),
                        ("user_id", event['message']['sender_id']),
                        ("user_name", event['message']['sender_full_name']),
                        ("text", event['command']),
                        ("trigger_word", event['trigger']),
                        ("service_id", event['user_profile_id']),
                        ]

        return request_data

    def send_data_to_server(self,
                            base_url: str,
                            request_data: Any) -> Response:
        response = requests.request('POST', base_url, data=request_data)
        return response

    def process_success(self, response_json: Dict[str, Any],
                        event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if "text" in response_json:
            content = response_json['text']
            success_data = dict(content=content)
            return success_data

        return None

AVAILABLE_OUTGOING_WEBHOOK_INTERFACES = {
    GENERIC_INTERFACE: GenericOutgoingWebhookService,
    SLACK_INTERFACE: SlackOutgoingWebhookService,
}   # type: Dict[str, Any]

def get_service_interface_class(interface: str) -> Any:
    if interface is None or interface not in AVAILABLE_OUTGOING_WEBHOOK_INTERFACES:
        return AVAILABLE_OUTGOING_WEBHOOK_INTERFACES[GENERIC_INTERFACE]
    else:
        return AVAILABLE_OUTGOING_WEBHOOK_INTERFACES[interface]

def get_outgoing_webhook_service_handler(service: Service) -> Any:

    service_interface_class = get_service_interface_class(service.interface_name())
    service_interface = service_interface_class(token=service.token,
                                                user_profile=service.user_profile,
                                                service_name=service.name)
    return service_interface

def send_response_message(bot_id: str, message_info: Dict[str, Any], response_data: Dict[str, Any]) -> None:
    """
    bot_id is the user_id of the bot sending the response

    message_info is used to address the message and should have these fields:
        type - "stream" or "private"
        display_recipient - like we have in other message events
        topic - see get_topic_from_message_info

    response_data is what the bot wants to send back and has these fields:
        content - raw markdown content for Zulip to render
    """

    message_type = message_info['type']
    display_recipient = message_info['display_recipient']
    try:
        topic_name = get_topic_from_message_info(message_info)
    except KeyError:
        topic_name = None

    bot_user = get_user_profile_by_id(bot_id)
    realm = bot_user.realm
    client = get_client('OutgoingWebhookResponse')

    content = response_data.get('content')
    if not content:
        raise JsonableError(_("Missing content"))

    widget_content = response_data.get('widget_content')

    if message_type == 'stream':
        message_to = [display_recipient]
    elif message_type == 'private':
        message_to = [recipient['email'] for recipient in display_recipient]
    else:
        raise JsonableError(_("Invalid message type"))

    check_send_message(
        sender=bot_user,
        client=client,
        message_type_name=message_type,
        message_to=message_to,
        topic_name=topic_name,
        message_content=content,
        widget_content=widget_content,
        realm=realm,
    )

def fail_with_message(event: Dict[str, Any], failure_message: str) -> None:
    bot_id = event['user_profile_id']
    message_info = event['message']
    content = "Failure! " + failure_message
    response_data = dict(content=content)
    send_response_message(bot_id=bot_id, message_info=message_info, response_data=response_data)

def get_message_url(event: Dict[str, Any]) -> str:
    bot_user = get_user_profile_by_id(event['user_profile_id'])
    message = event['message']
    realm = bot_user.realm

    return near_message_url(
        realm=realm,
        message=message,
    )

def notify_bot_owner(event: Dict[str, Any],
                     request_data: Dict[str, Any],
                     status_code: Optional[int]=None,
                     response_content: Optional[AnyStr]=None,
                     failure_message: Optional[str]=None,
                     exception: Optional[Exception]=None) -> None:
    message_url = get_message_url(event)
    bot_id = event['user_profile_id']
    bot_owner = get_user_profile_by_id(bot_id).bot_owner

    notification_message = "[A message](%s) triggered an outgoing webhook." % (message_url,)
    if failure_message:
        notification_message += "\n" + failure_message
    if status_code:
        notification_message += "\nThe webhook got a response with status code *%s*." % (status_code,)
    if response_content:
        notification_message += "\nThe response contains the following payload:\n" \
                                "```\n%s\n```" % (response_content,)
    if exception:
        notification_message += "\nWhen trying to send a request to the webhook service, an exception " \
                                "of type %s occurred:\n```\n%s\n```" % (
                                    type(exception).__name__, str(exception))

    message_info = dict(
        type='private',
        display_recipient=[dict(email=bot_owner.email)],
    )
    response_data = dict(content=notification_message)
    send_response_message(bot_id=bot_id, message_info=message_info, response_data=response_data)

def request_retry(event: Dict[str, Any],
                  request_data: Dict[str, Any],
                  failure_message: Optional[str]=None) -> None:
    def failure_processor(event: Dict[str, Any]) -> None:
        """
        The name of the argument is 'event' on purpose. This argument will hide
        the 'event' argument of the request_retry function. Keeping the same name
        results in a smaller diff.
        """
        bot_user = get_user_profile_by_id(event['user_profile_id'])
        fail_with_message(event, "Bot is unavailable")
        notify_bot_owner(event, request_data, failure_message=failure_message)
        logging.warning("Maximum retries exceeded for trigger:%s event:%s" % (
            bot_user.email, event['command']))

    retry_event('outgoing_webhooks', event, failure_processor)

def process_success_response(event: Dict[str, Any],
                             service_handler: Any,
                             response: Response) -> None:
    try:
        response_json = json.loads(response.text)
    except ValueError:
        fail_with_message(event, "Invalid JSON in response")
        return

    success_data = service_handler.process_success(response_json, event)

    if success_data is None:
        return

    content = success_data.get('content')

    if content is None:
        return

    widget_content = success_data.get('widget_content')
    bot_id = event['user_profile_id']
    message_info = event['message']
    response_data = dict(content=content, widget_content=widget_content)
    send_response_message(bot_id=bot_id, message_info=message_info, response_data=response_data)

def do_rest_call(base_url: str,
                 request_data: Any,
                 event: Dict[str, Any],
                 service_handler: Any) -> None:
    try:
        response = service_handler.send_data_to_server(
            base_url=base_url,
            request_data=request_data,
        )
        if str(response.status_code).startswith('2'):
            process_success_response(event, service_handler, response)
        else:
            logging.warning("Message %(message_url)s triggered an outgoing webhook, returning status "
                            "code %(status_code)s.\n Content of response (in quotes): \""
                            "%(response)s\""
                            % {'message_url': get_message_url(event),
                               'status_code': response.status_code,
                               'response': response.content})
            failure_message = "Third party responded with %d" % (response.status_code)
            fail_with_message(event, failure_message)
            notify_bot_owner(event, request_data, response.status_code, response.content)

    except requests.exceptions.Timeout:
        logging.info("Trigger event %s on %s timed out. Retrying" % (
            event["command"], event['service_name']))
        failure_message = "A timeout occurred."
        request_retry(event, request_data, failure_message=failure_message)

    except requests.exceptions.ConnectionError:
        logging.info("Trigger event %s on %s resulted in a connection error. Retrying"
                     % (event["command"], event['service_name']))
        failure_message = "A connection error occurred. Is my bot server down?"
        request_retry(event, request_data, failure_message=failure_message)

    except requests.exceptions.RequestException as e:
        response_message = ("An exception of type *%s* occurred for message `%s`! "
                            "See the Zulip server logs for more information." % (
                                type(e).__name__, event["command"],))
        logging.exception("Outhook trigger failed:\n %s" % (e,))
        fail_with_message(event, response_message)
        notify_bot_owner(event, request_data, exception=e)
