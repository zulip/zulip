from __future__ import absolute_import
from django.utils.translation import ugettext as _
from typing import Any, Callable, Dict
from django.http import HttpRequest, HttpResponse
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile, Client



@api_key_only_webhook_view('IFTTT')
@has_request_variables
def api_iftt_app_webhook(request, user_profile, client,
                         payload=REQ(argument_type='body'),
                         stream=REQ(default='ifttt')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], str) -> HttpResponse
    subject = payload.get('subject')
    content = payload.get('content')
    if subject is None:
        return json_error(_("Subject can't be empty"))
    if content is None:
        return json_error(_("Content can't be empty"))
    check_send_message(user_profile, client, "stream", [stream], subject, content)
    return json_success()
