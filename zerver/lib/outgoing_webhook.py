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

from zerver.models import Realm, get_realm_by_email_domain, get_user_profile_by_id, get_client
from zerver.lib.actions import check_send_message
from zerver.lib.queue import queue_json_publish
from zerver.lib.validator import check_dict, check_string
from zerver.decorator import JsonableError

MAX_REQUEST_RETRIES = 3

def send_response_message(bot_id, message, response_message_content):
    # type: (str, Dict[str, Any], Text) -> None
    recipient_type_name = message['type']
    bot_user = get_user_profile_by_id(bot_id)
    realm = get_realm_by_email_domain(message['sender_email'])

    if recipient_type_name == 'stream':
        recipients = [message['display_recipient']]
        check_send_message(bot_user, get_client("OutgoingWebhookResponse"), recipient_type_name, recipients,
                           message['subject'], response_message_content, realm, forwarder_user_profile=bot_user)
    else:
        # Private message; only send if the bot is there in the recipients
        recipients = [recipient['email'] for recipient in message['display_recipient']]
        if bot_user.email in recipients:
            check_send_message(bot_user, get_client("OutgoingWebhookResponse"), recipient_type_name, recipients,
                               message['subject'], response_message_content, realm, forwarder_user_profile=bot_user)

def succeed_with_message(event, success_message):
    # type: (Dict[str, Any], Text) -> None
    success_message = "Success! " + success_message
    send_response_message(event['user_profile_id'], event['message'], success_message)

def fail_with_message(event, failure_message):
    # type: (Dict[str, Any], Text) -> None
    failure_message = "Failure! " + failure_message
    send_response_message(event['user_profile_id'], event['message'], failure_message)

def request_retry(event, failure_message):
    # type: (Dict[str, Any], Text) -> None
    event['failed_tries'] += 1
    if event['failed_tries'] > MAX_REQUEST_RETRIES:
        bot_user = get_user_profile_by_id(event['user_profile_id'])
        failure_message = "Maximum retries exceeded! " + failure_message
        fail_with_message(event, failure_message)
        logging.warning("Maximum retries exceeded for trigger:%s event:%s" % (bot_user.email, event['command']))
    else:
        queue_json_publish("outgoing_webhooks", event, lambda x: None)

def do_rest_call(rest_operation, event, timeout=None):
    # type: (Dict[str, Any], Dict[str, Any], Any) -> None
    rest_operation_validator = check_dict([
        ('method', check_string),
        ('relative_url_path', check_string),
        ('request_kwargs', check_dict([])),
        ('base_url', check_string),
    ])

    error = rest_operation_validator('rest_operation', rest_operation)
    if error:
        raise JsonableError(_("%s") % (error,))

    http_method = rest_operation['method']
    final_url = urllib.parse.urljoin(rest_operation['base_url'], rest_operation['relative_url_path'])
    request_kwargs = rest_operation['request_kwargs']
    request_kwargs['timeout'] = timeout

    try:
        response = requests.request(http_method, final_url, data=json.dumps(event), **request_kwargs)
        if str(response.status_code).startswith('2'):
            succeed_with_message(event, "received response: `" + str(response.content) + "`.")

        # On 50x errors, try retry
        elif str(response.status_code).startswith('5'):
            request_retry(event, "unable to connect with the third party.")
        else:
            fail_with_message(event, "unable to communicate with the third party.")

    except requests.exceptions.Timeout:
        logging.info("Trigger event %s on %s timed out. Retrying" % (event["command"], event['service_name']))
        request_retry(event, 'unable to connect with the third party.')

    except requests.exceptions.RequestException as e:
        response_message = "An exception occured for message `%s`! See the logs for more information." % (event["command"],)
        logging.exception("Outhook trigger failed:\n %s" % (e,))
        fail_with_message(event, response_message)
