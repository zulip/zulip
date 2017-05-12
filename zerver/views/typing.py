from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse
from typing import List, Text

from zerver.decorator import authenticated_json_post_view,\
    has_request_variables, REQ, JsonableError
from zerver.lib.actions import check_send_typing_notification, \
    extract_recipients
from zerver.lib.response import json_success
from zerver.models import UserProfile

@has_request_variables
def send_notification_backend(request, user_profile, operator=REQ('op'),
                              notification_to = REQ('to', converter=extract_recipients, default=[])):
    # type: (HttpRequest, UserProfile, Text, List[Text]) -> HttpResponse
    check_send_typing_notification(user_profile, notification_to, operator)
    return json_success()
