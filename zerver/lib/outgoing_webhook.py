from __future__ import absolute_import
from typing import Any, Iterable, Dict, Tuple, Callable
from six import text_type

import requests
import sys
import inspect
import logging
from six.moves import urllib
from functools import reduce

from django.utils.translation import ugettext as _

from zerver.models import get_outgoing_webhook_bot_profile, Realm
from zerver.lib.actions import internal_send_message
from zerver.lib.queue import queue_json_publish
from zerver.lib.validator import check_dict, check_string
from zerver.decorator import JsonableError

class OutgoingWebhookBotInterface(object):
    email = None # type: text_type
    full_name = None # type: text_type

    def __init__(self, base_url, service_api_key):
        self.base_url = None # type: text_type
        self.service_api_key = None # type: text_type

    def process_command(self, command):
        # type: (text_type) -> Tuple[Dict[text_type ,Any], Dict[text_type, Any]]
        raise NotImplementedError()

    def process_response(self, status_code, response_json, trigger_cache):
        # type : (text_type, Any, Dict[text_type, Any]) -> Tuple[Callable[[Any, text_type], None], text_type]
        raise NotImplementedError()

    def handle_remote_failure(self, status_code, response_json, trigger_cache):
        # type : (text_type, Any, Dict[text_type, Any]) -> Tuple[Callable[[Any, text_type], None], text_type]
        raise NotImplementedError()

class BotMessageActions(object):

    @staticmethod
    def send_response_message(bot_email, trigger_message, response_message_content):
        # type : (text_type, text_type, text_type) -> None
        recipient_type_name = trigger_message['type']
        if recipient_type_name == 'stream':
            recipients = trigger_message['display_recipient']
            internal_send_message(bot_email, recipient_type_name, recipients,
                                  trigger_message['subject'], response_message_content)
        else:
            # Private message; only send if the bot is there in the recipients
            trigger_message_recipients = [recipient['email'] for recipient in trigger_message['display_recipient']]
            if bot_email in trigger_message_recipients:
                recipients = ','.join(trigger_message_recipients)
                internal_send_message(bot_email, recipient_type_name, recipients,
                              trigger_message['subject'], response_message_content)

    @classmethod
    def succeed_with_message(cls, event, success_message):
        # type : (Dict[text_type, Any], text_type) -> None
        bot_email = event['bot_email']
        trigger_message = event['message']
        cls.send_response_message(bot_email, trigger_message, success_message)

    @classmethod
    def fail_with_message(cls, event, failure_message):
        # type : (Dict[text_type, Any], text_type) -> None
        bot_email = event['bot_email']
        trigger_message = event['message']
        cls.send_response_message(bot_email, trigger_message, failure_message)

    @classmethod
    def request_retry(cls, event, failure_message):
        # type : (Dict[text_type, Any], text_type) -> None
        event['retry'] += 1
        if event['retry'] > 3:
            bot_email = event['bot_email']
            command = event['command']
            cls.fail_with_message(event, failure_message)
            logging.warning("Maximum retries exceeded for trigger:%s event:%s" % (bot_email, command))
        else:
            queue_json_publish("outhook_worker", event, lambda x: None)

def do_rest_call(bot_interface, rest_operation, trigger_cache, timeout=None):
    # type: (Any, Dict[text_type, Any], Dict[text_type, Any], Any) -> Tuple[Callable[[Any, text_type], None], text_type]
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
    request_kwargs['auth'] = (bot_interface.full_name, bot_interface.service_api_key)
    request_kwargs['timeout'] = timeout

    try:
        response = requests.request(http_method, final_url, **request_kwargs)
        if str(response.status_code).startswith('2'):
            return bot_interface.process_response(response.status_code, response.json(), trigger_cache)

        # On 50x errors, try retry
        elif str(response.status_code).startswith('5'):
            return (BotMessageActions.request_retry, 'Maximum retries exceeded')
        else:
            return bot_interface.handle_remote_failure(response.status_code, response.json(), trigger_cache)

    except requests.exceptions.Timeout:
        logging.info("Trigger event %s on %s timed out. Retrying" % (trigger_cache["command"], bot_interface.full_name))
        return (BotMessageActions.request_retry, 'Maximum retries exceeded')

    except requests.exceptions.RequestException as e:
        response_message = "An exception occured for event %s! See the logs for more information." % (trigger_cache["command"],)
        logging.exception("Outhook trigger failed:\n %s" % (e,))
        return (BotMessageActions.fail_with_message, response_message)

def get_outgoing_webhook_bot_handler(bot_email, realm):
    # type: (text_type, Realm) -> Any
    # Load this lazily to prevent circular dependency problems
    from zerver.outgoing_webhooks import get_bot_instance_class

    bot_profile = get_outgoing_webhook_bot_profile(bot_email, realm)
    bot_interface_class = get_bot_instance_class(bot_profile.full_name)
    if bot_interface_class:
        bot_instance = bot_interface_class(base_url=bot_profile.base_url,
                                           service_api_key=bot_profile.service_api_key)
        return bot_instance
    else:
        bot_interface_class = get_bot_instance_class("GenericBot")
        bot_instance = bot_interface_class(post_url=bot_profile.post_url,
                                           service_api_key=bot_profile.service_api_key,
                                           email = bot_profile.email,
                                           full_name = bot_profile.full_name)
    return bot_instance
