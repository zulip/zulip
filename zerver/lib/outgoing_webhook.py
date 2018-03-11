from typing import Any, AnyStr, Iterable, Dict, Tuple, Callable, Text, Mapping, Optional

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
from zerver.lib.notifications import encode_stream
from zerver.lib.queue import retry_event
from zerver.lib.validator import check_dict, check_string
from zerver.decorator import JsonableError

class OutgoingWebhookServiceInterface:

    def __init__(self, base_url: Text, token: Text, user_profile: UserProfile, service_name: Text) -> None:
        self.base_url = base_url  # type: Text
        self.token = token  # type: Text
        self.user_profile = user_profile  # type: Text
        self.service_name = service_name  # type: Text

    # Given an event that triggers an outgoing webhook operation, returns:
    # - The REST operation that should be performed
    # - The body of the request
    #
    # The REST operation is a dictionary with the following keys:
    # - method
    # - base_url
    # - relative_url_path
    # - request_kwargs
    def process_event(self, event: Dict[Text, Any]) -> Tuple[Dict[str, Any], Any]:
        raise NotImplementedError()

    # Given a successful outgoing webhook REST operation, returns the message
    # to sent back to the user (or None if no message should be sent).
    def process_success(self, response: Response, event: Dict[Text, Any]) -> Optional[str]:
        raise NotImplementedError()

class GenericOutgoingWebhookService(OutgoingWebhookServiceInterface):

    def process_event(self, event: Dict[Text, Any]) -> Tuple[Dict[str, Any], Any]:
        rest_operation = {'method': 'POST',
                          'relative_url_path': '',
                          'base_url': self.base_url,
                          'request_kwargs': {}}
        request_data = {"data": event['command'],
                        "message": event['message'],
                        "token": self.token}
        return rest_operation, json.dumps(request_data)

    def process_success(self, response: Response, event: Dict[Text, Any]) -> Optional[str]:
        response_json = json.loads(response.text)

        if "response_not_required" in response_json and response_json['response_not_required']:
            return None
        if "response_string" in response_json:
            return str(response_json['response_string'])
        else:
            return None

class SlackOutgoingWebhookService(OutgoingWebhookServiceInterface):

    def process_event(self, event: Dict[Text, Any]) -> Tuple[Dict[str, Any], Any]:
        rest_operation = {'method': 'POST',
                          'relative_url_path': '',
                          'base_url': self.base_url,
                          'request_kwargs': {}}

        if event['message']['type'] == 'private':
            raise NotImplementedError("Private messaging service not supported.")

        service = get_service_profile(event['user_profile_id'], str(self.service_name))
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
                        ("service_id", service.id),
                        ]

        return rest_operation, request_data

    def process_success(self, response: Response, event: Dict[Text, Any]) -> Optional[str]:
        response_json = json.loads(response.text)
        if "text" in response_json:
            return response_json["text"]
        else:
            return None

AVAILABLE_OUTGOING_WEBHOOK_INTERFACES = {
    GENERIC_INTERFACE: GenericOutgoingWebhookService,
    SLACK_INTERFACE: SlackOutgoingWebhookService,
}   # type: Dict[Text, Any]

def get_service_interface_class(interface: Text) -> Any:
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

def send_response_message(bot_id: str, message: Dict[str, Any], response_message_content: Text) -> None:
    recipient_type_name = message['type']
    bot_user = get_user_profile_by_id(bot_id)
    realm = bot_user.realm

    if recipient_type_name == 'stream':
        recipients = [message['display_recipient']]
        check_send_message(bot_user, get_client("OutgoingWebhookResponse"), recipient_type_name, recipients,
                           message['subject'], response_message_content, realm)
    elif recipient_type_name == 'private':
        recipients = [recipient['email'] for recipient in message['display_recipient']]
        check_send_message(bot_user, get_client("OutgoingWebhookResponse"), recipient_type_name, recipients,
                           None, response_message_content, realm)
    else:
        raise JsonableError(_("Invalid message type"))

def succeed_with_message(event: Dict[str, Any], success_message: Text) -> None:
    success_message = "Success! " + success_message
    send_response_message(event['user_profile_id'], event['message'], success_message)

def fail_with_message(event: Dict[str, Any], failure_message: Text) -> None:
    failure_message = "Failure! " + failure_message
    send_response_message(event['user_profile_id'], event['message'], failure_message)

def get_message_url(event: Dict[str, Any], request_data: Dict[str, Any]) -> Text:
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
    message_info = {'display_recipient': [{'email': bot_owner.email}],
                    'type': 'private'}
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
    send_response_message(bot_id, message_info, notification_message)

def request_retry(event: Dict[str, Any],
                  request_data: Dict[str, Any],
                  failure_message: Text,
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
            response_message = service_handler.process_success(response, event)
            if response_message is not None:
                succeed_with_message(event, response_message)
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
