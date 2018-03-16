from typing import Any, Dict, Iterable, Optional, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.validator import check_dict, check_string
from zerver.models import UserProfile

@api_key_only_webhook_view('Papertrail')
@has_request_variables
def api_papertrail_webhook(request: HttpRequest, user_profile: UserProfile,
                           payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

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

    topic = 'logs'

    # send the message
    check_send_webhook_message(request, user_profile, topic, post)

    # return json result
    return json_success()
