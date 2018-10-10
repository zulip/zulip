from typing import Any, AnyStr, Iterable, Dict, Tuple, Callable, Mapping, Optional

import requests
import json
import sys
import inspect
import logging
import re
import urllib
from functools import reduce
from requests import Response

from django.utils.translation import ugettext as _

from zerver.models import Realm, UserProfile, get_user_profile_by_id, get_client, \
    GENERIC_INTERFACE, Service, SLACK_INTERFACE, email_to_domain, get_service_profile
from zerver.lib.actions import check_send_message
from zerver.lib.queue import retry_event
from zerver.lib.url_encoding import encode_stream
from zerver.lib.validator import check_dict, check_string
from zerver.decorator import JsonableError

class OutgoingWebhookServiceInterface:

    def __init__(self, base_url: str, token: str, user_profile: UserProfile, service_name: str) -> None:
        self.base_url = base_url  # type: str
        self.token = token  # type: str
        self.user_profile = user_profile  # type: UserProfile
        self.service_name = service_name  # type: str

    # Given an event that triggers an outgoing webhook operation, returns:
    # - The REST operation that should be performed
    # - The body of the request
    #
    # The REST operation is a dictionary with the following keys:
    # - method
    # - base_url
    # - relative_url_path
    # - request_kwargs
    def process_event(self, event: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
        raise NotImplementedError()

    # Given a successful outgoing webhook REST operation, return
    # a dictionary with `content` and other relevant fields.
    # The main use case for this function is to massage data from
    # various APIs to have similar data structures.
    # It also allows bots to explictly set response_not_required.
    def process_success(self, response_json: Dict[str, Any],
                        event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError()

class GenericOutgoingWebhookService(OutgoingWebhookServiceInterface):

    def process_event(self, event: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
        rest_operation = {'method': 'POST',
                          'relative_url_path': '',
                          'base_url': self.base_url,
                          'request_kwargs': {}}
        request_data = {"data": event['command'],
                        "message": event['message'],
                        "bot_email": self.user_profile.email,
                        "token": self.token,
                        "trigger": event['trigger']}
        return rest_operation, json.dumps(request_data)

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
            return success_data

        return None

class SlackOutgoingWebhookService(OutgoingWebhookServiceInterface):

    def process_event(self, event: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
        rest_operation = {'method': 'POST',
                          'relative_url_path': '',
                          'base_url': self.base_url,
                          'request_kwargs': {}}

        if event['message']['type'] == 'private':
            failure_message = "Slack outgoing webhooks don't support private messages."
            fail_with_message(event, failure_message)
            return None, None

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

        return rest_operation, request_data

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
    service_interface = service_interface_class(base_url=service.base_url,
                                                token=service.token,
                                                user_profile=service.user_profile,
                                                service_name=service.name)
    return service_interface

def send_response_message(bot_id: str, message_info: Dict[str, Any], response_data: Dict[str, Any]) -> None:
    """
    bot_id is the user_id of the bot sending the response

    message_info is used to address the message and should have these fields:
        type - "stream" or "private"
        display_recipient - like we have in other message events
        subject - the topic name (if relevant)

    response_data is what the bot wants to send back and has these fields:
        content - raw markdown content for Zulip to render
    """

    message_type = message_info['type']
    display_recipient = message_info['display_recipient']
    topic_name = message_info.get('subject')

    bot_user = get_user_profile_by_id(bot_id)
    realm = bot_user.realm
    client = get_client('OutgoingWebhookResponse')

    content = response_data.get('content')
    if not content:
        raise JsonableError(_("Missing content"))

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
        realm=realm,
    )

def fail_with_message(event: Dict[str, Any], failure_message: str) -> None:
    bot_id = event['user_profile_id']
    message_info = event['message']
    content = "Failure! " + failure_message
    response_data = dict(content=content)
    send_response_message(bot_id=bot_id, message_info=message_info, response_data=response_data)

def get_message_url(event: Dict[str, Any], request_data: Dict[str, Any]) -> str:
    bot_user = get_user_profile_by_id(event['user_profile_id'])
    message = event['message']
    if message['type'] == 'stream':
        stream_url_frag = encode_stream(message.get('stream_id'), message['display_recipient'])
        message_url = ("%(server)s/#narrow/stream/%(stream)s/subject/%(subject)s/near/%(id)s"
                       % {'server': bot_user.realm.uri,
                          'stream': stream_url_frag,
                          'subject': message['subject'],
                          'id': str(message['id'])})
    else:
        recipient_emails = ','.join([recipient['email'] for recipient in message['display_recipient']])
        recipient_email_encoded = urllib.parse.quote(recipient_emails).replace('.', '%2E').replace('%', '.')
        message_url = ("%(server)s/#narrow/pm-with/%(recipient_emails)s/near/%(id)s"
                       % {'server': bot_user.realm.uri,
                          'recipient_emails': recipient_email_encoded,
                          'id': str(message['id'])})
    return message_url

def notify_bot_owner(event: Dict[str, Any],
                     request_data: Dict[str, Any],
                     status_code: Optional[int]=None,
                     response_content: Optional[AnyStr]=None,
                     exception: Optional[Exception]=None) -> None:
    message_url = get_message_url(event, request_data)
    bot_id = event['user_profile_id']
    bot_owner = get_user_profile_by_id(bot_id).bot_owner

    notification_message = "[A message](%s) triggered an outgoing webhook." % (message_url,)
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
                  failure_message: str,
                  exception: Optional[Exception]=None) -> None:
    def failure_processor(event: Dict[str, Any]) -> None:
        """
        The name of the argument is 'event' on purpose. This argument will hide
        the 'event' argument of the request_retry function. Keeping the same name
        results in a smaller diff.
        """
        bot_user = get_user_profile_by_id(event['user_profile_id'])
        fail_with_message(event, "Maximum retries exceeded! " + failure_message)
        notify_bot_owner(event, request_data, exception=exception)
        logging.warning("Maximum retries exceeded for trigger:%s event:%s" % (
            bot_user.email, event['command']))

    retry_event('outgoing_webhooks', event, failure_processor)

def process_success_response(event: Dict[str, Any],
                             service_handler: Any,
                             response: Response) -> None:
    response_json = json.loads(response.text)
    success_data = service_handler.process_success(response_json, event)

    if success_data is None:
        return

    content = success_data.get('content')

    if content is None:
        return

    bot_id = event['user_profile_id']
    message_info = event['message']
    response_data = dict(content=content)
    send_response_message(bot_id=bot_id, message_info=message_info, response_data=response_data)

def do_rest_call(rest_operation: Dict[str, Any],
                 request_data: Optional[Dict[str, Any]],
                 event: Dict[str, Any],
                 service_handler: Any,
                 timeout: Any=None) -> None:
    rest_operation_validator = check_dict([
        ('method', check_string),
        ('relative_url_path', check_string),
        ('request_kwargs', check_dict([])),
        ('base_url', check_string),
    ])

    error = rest_operation_validator('rest_operation', rest_operation)
    if error:
        raise JsonableError(error)

    http_method = rest_operation['method']
    final_url = urllib.parse.urljoin(rest_operation['base_url'], rest_operation['relative_url_path'])
    request_kwargs = rest_operation['request_kwargs']
    request_kwargs['timeout'] = timeout

    try:
        response = requests.request(http_method, final_url, data=request_data, **request_kwargs)
        if str(response.status_code).startswith('2'):
            process_success_response(event, service_handler, response)
        else:
            logging.warning("Message %(message_url)s triggered an outgoing webhook, returning status "
                            "code %(status_code)s.\n Content of response (in quotes): \""
                            "%(response)s\""
                            % {'message_url': get_message_url(event, request_data),
                               'status_code': response.status_code,
                               'response': response.content})
            failure_message = "Third party responded with %d" % (response.status_code)
            fail_with_message(event, failure_message)
            notify_bot_owner(event, request_data, response.status_code, response.content)

    except requests.exceptions.Timeout as e:
        logging.info("Trigger event %s on %s timed out. Retrying" % (
            event["command"], event['service_name']))
        request_retry(event, request_data, 'Unable to connect with the third party.', exception=e)

    except requests.exceptions.ConnectionError as e:
        response_message = ("The message `%s` resulted in a connection error when "
                            "sending a request to an outgoing "
                            "webhook! See the Zulip server logs for more information." % (event["command"],))
        logging.info("Trigger event %s on %s resulted in a connection error. Retrying"
                     % (event["command"], event['service_name']))
        request_retry(event, request_data, response_message, exception=e)

    except requests.exceptions.RequestException as e:
        response_message = ("An exception of type *%s* occurred for message `%s`! "
                            "See the Zulip server logs for more information." % (
                                type(e).__name__, event["command"],))
        logging.exception("Outhook trigger failed:\n %s" % (e,))
        fail_with_message(event, response_message)
        notify_bot_owner(event, request_data, exception=e)
