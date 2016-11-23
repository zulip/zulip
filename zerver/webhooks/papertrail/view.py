from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string

from zerver.models import Client, UserProfile

from django.http import HttpRequest, HttpResponse
from typing import Text
from typing import Dict, Any, Iterable, Optional

@api_key_only_webhook_view('Papertrail')
@has_request_variables
def api_papertrail_webhook(request, user_profile, client,
                           payload=REQ(argument_type='body'),
                           stream=REQ(default='papertrail'),
                           topic=REQ(default='logs')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], Text, Text) -> HttpResponse

    # construct the message of the message
    try:
        message_template = '**"{}"** search found **{}** matches - {}\n```'
        message = [message_template.format(payload["saved_search"]["name"],
                                           str(len(payload["events"])),
                                           payload["saved_search"]["html_search_url"])]
        for i, event in enumerate(payload["events"]):
            event_text = '{} {} {}:\n  {}'.format(event["display_received_at"],
                                                  event["source_name"],
                                                  payload["saved_search"]["query"],
                                                  event["message"])
            message.append(event_text)
            if i >= 3:
                message.append('```\n[See more]({})'.format(payload["saved_search"]["html_search_url"]))
                break
        else:
            message.append('```')
        post = '\n'.join(message)
    except KeyError as e:
        return json_error(_("Missing key {} in JSON").format(str(e)))

    # send the message
    check_send_message(user_profile, client, 'stream', [stream], topic, post)

    # return json result
    return json_success()
