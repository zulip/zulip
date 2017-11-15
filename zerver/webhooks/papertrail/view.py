from typing import Any, Dict, Iterable, Optional, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_dict, check_string
from zerver.models import UserProfile

@api_key_only_webhook_view('Papertrail')
@has_request_variables
def api_papertrail_webhook(request, user_profile,
                           payload=REQ(argument_type='body'),
                           stream=REQ(default='papertrail'),
                           topic=REQ(default='logs')):
    # type: (HttpRequest, UserProfile, Dict[str, Any], Text, Text) -> HttpResponse

    # construct the message of the message
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

    # send the message
    check_send_stream_message(user_profile, request.client, stream, topic, post)

    # return json result
    return json_success()
