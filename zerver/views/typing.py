from django.http import HttpRequest, HttpResponse
from six import text_type

from zerver.decorator import authenticated_json_post_view,\
    has_request_variables, REQ, JsonableError
from zerver.lib.actions import check_send_typing_notification, \
    extract_recipients
from zerver.lib.response import json_success
from zerver.models import UserProfile

@has_request_variables
def send_notification_backend(request, user_profile, operator=REQ('op'),
                              notification_to = REQ('to', converter=extract_recipients, default=[])):
    # type: (HttpRequest, UserProfile, text_type, List[text_type]) -> HttpResponse
    check_send_typing_notification(user_profile, notification_to, operator)
    return json_success()
