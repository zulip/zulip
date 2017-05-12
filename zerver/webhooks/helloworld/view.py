# Webhooks for external integrations.
from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string
from zerver.models import UserProfile

from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Iterable, Optional, Text

@api_key_only_webhook_view('HelloWorld')
@has_request_variables
def api_helloworld_webhook(request, user_profile,
                           payload=REQ(argument_type='body'), stream=REQ(default='test'),
                           topic=REQ(default='Hello World')):
    # type: (HttpRequest, UserProfile, Dict[str, Iterable[Dict[str, Any]]], Text, Optional[Text]) -> HttpResponse

    # construct the body of the message
    body = 'Hello! I am happy to be here! :smile:'

    # try to add the Wikipedia article of the day
    # return appropriate error if not successful
    try:
        body_template = '\nThe Wikipedia featured article for today is **[{featured_title}]({featured_url})**'
        body += body_template.format(**payload)
    except KeyError as e:
        return json_error(_("Missing key {} in JSON").format(str(e)))

    # send the message
    check_send_message(user_profile, request.client, 'stream', [stream], topic, body)

    return json_success()
