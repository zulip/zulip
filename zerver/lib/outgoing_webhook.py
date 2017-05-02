from __future__ import absolute_import
from typing import Any, Iterable, Dict, Tuple, Callable, Text, Mapping

import requests
import json
import sys
import inspect
import logging
from six.moves import urllib
from functools import reduce

from django.utils.translation import ugettext as _

from zerver.models import Realm, Service, get_realm_by_email_domain
from zerver.lib.actions import internal_send_message
from zerver.lib.queue import queue_json_publish
from zerver.lib.validator import check_dict, check_string
from zerver.decorator import JsonableError

class OutgoingWebhookServiceInterface(object):

    def __init__(self, base_url, token, bot_email, service_name):
        # type: (Text, Text, Text, Text) -> None
        self.base_url = None # type: Text
        self.token = None # type: Text
        self.bot_email = None  # type: Text
        self.service_name = None  # type: Text

    def process_command(self, event):
        # type: (Mapping[str, Any]) -> Tuple[Dict[str ,Any], Dict[str, Any]]
        raise NotImplementedError()

    def process_response(self, status_code, response_json, trigger_cache):
        # type: (Text, Any, Dict[Text, Any]) -> Tuple[Callable[[Any, Text], None], Text]
        raise NotImplementedError()

    def handle_remote_failure(self, status_code, response_json, trigger_cache):
        # type: (Text, Any, Dict[Text, Any]) -> Tuple[Callable[[Any, Text], None], Text]
        raise NotImplementedError()

class ServiceMessageActions(object):

    @staticmethod
    def send_response_message(realm, bot_email, trigger_message, response_message_content):
        # type: (Realm, Text, Dict[str, Any], Text) -> None
        recipient_type_name = trigger_message['type']
        if recipient_type_name == 'stream':
            recipients = trigger_message['recipient']
            internal_send_message(realm, bot_email, recipient_type_name, recipients,
                                  trigger_message['subject'], response_message_content)
        else:
            # Private message; only send if the bot is there in the recipients
            trigger_message_recipients = [recipient['email'] for recipient in trigger_message['recipient']]
            if trigger_message['sender_email'] not in trigger_message_recipients:
                trigger_message_recipients.append(trigger_message['sender_email'])
            recipient_type_name = 'private'
            if bot_email in trigger_message_recipients:
                recipients = ','.join(trigger_message_recipients)
                internal_send_message(realm, bot_email, recipient_type_name, recipients,
                                      trigger_message['subject'], response_message_content)

    @classmethod
    def succeed_with_message(cls, event, success_message):
        # type: (Dict[str, Any], Text) -> None
        bot_email = event['bot_email']
        trigger_message = event['message']
        realm = get_realm_by_email_domain(event['message']['sender_email'])
        cls.send_response_message(realm, bot_email, trigger_message, success_message)

    @classmethod
    def fail_with_message(cls, event, failure_message):
        # type: (Dict[str, Any], Text) -> None
        bot_email = event['bot_email']
        trigger_message = event['message']
        realm = get_realm_by_email_domain(event['message']['sender_email'])
        cls.send_response_message(realm, bot_email, trigger_message, failure_message)

    @classmethod
    def request_retry(cls, event, failure_message):
        # type: (Dict[str, Any], Text) -> None
        event['retry'] += 1
        if event['retry'] > 3:
            bot_email = event['bot_email']
            command = event['command']
            cls.fail_with_message(event, failure_message)
            logging.warning("Maximum retries exceeded for trigger:%s event:%s" % (bot_email, command))
        else:
            queue_json_publish("outgoing_webhooks", event, lambda x: None)

def do_rest_call(bot_interface, rest_operation, trigger_cache, timeout=None):
    # type: (Any, Dict[str, Any], Dict[str, Any], Any) -> Tuple[Callable[[Any, Text], None], Text]
    rest_operation_validator = check_dict([
        ('method', check_string),
        ('relative_url_path', check_string),
        ('request_kwargs', check_dict([]))
    ])

    error = rest_operation_validator('rest_operation', rest_operation)
    if error:
        raise JsonableError(_("%s") % (error,))

    http_method = rest_operation['method']
    relative_url_path = rest_operation['relative_url_path']
    final_url = urllib.parse.urljoin(bot_interface.base_url, relative_url_path)
    request_kwargs = rest_operation['request_kwargs']
    request_kwargs['auth'] = (bot_interface.service_name, bot_interface.token)
    request_kwargs['timeout'] = timeout

    try:
        response = requests.request(http_method, final_url, data=json.dumps(trigger_cache), **request_kwargs)
        if str(response.status_code).startswith('2'):
            return bot_interface.process_response(response.status_code, response.json(), trigger_cache)

        # On 50x errors, try retry
        elif str(response.status_code).startswith('5'):
            return (ServiceMessageActions.request_retry, 'Maximum retries exceeded')
        else:
            return bot_interface.handle_remote_failure(response.status_code, response.json(), trigger_cache)

    except requests.exceptions.Timeout:
        logging.info("Trigger event %s on %s timed out. Retrying" % (trigger_cache["command"], bot_interface.service_name))
        return (ServiceMessageActions.request_retry, 'Maximum retries exceeded')

    except requests.exceptions.RequestException as e:
        response_message = "An exception occured for event %s! See the logs for more information." % (trigger_cache["command"],)
        logging.exception("Outhook trigger failed:\n %s" % (e,))
        return (ServiceMessageActions.fail_with_message, response_message)

def get_outgoing_webhook_service_handler(service):
    # type: (Service) -> Any
    # Load this lazily to prevent circular dependency problems

    from zerver.outgoing_webhooks import get_service_interface_class

    service_interface_class = get_service_interface_class(service.interface_name())
    service_interface = service_interface_class(base_url=service.base_url,
                                                token=service.token,
                                                bot_email=service.user_profile.email,
                                                service_name=service.name)
    return service_interface
