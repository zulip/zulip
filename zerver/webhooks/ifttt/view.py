from typing import Any, Callable, Dict

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.models import UserProfile

@api_key_only_webhook_view('IFTTT')
@has_request_variables
def api_iftt_app_webhook(request: HttpRequest, user_profile: UserProfile,
                         payload: Dict[str, Any]=REQ(argument_type='body'),
                         stream: str=REQ(default='ifttt')) -> HttpResponse:
    subject = payload.get('subject')
    content = payload.get('content')
    if subject is None:
        return json_error(_("Subject can't be empty"))
    if content is None:
        return json_error(_("Content can't be empty"))
    check_send_stream_message(user_profile, request.client, stream, subject, content)
    return json_success()
