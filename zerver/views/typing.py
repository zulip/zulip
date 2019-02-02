
from django.http import HttpRequest, HttpResponse
from typing import List

from zerver.decorator import has_request_variables, REQ
from zerver.lib.actions import check_send_typing_notification, \
    extract_recipients
from zerver.lib.response import json_success
from zerver.models import UserProfile

@has_request_variables
def send_notification_backend(
        request: HttpRequest, user_profile: UserProfile,
        operator: str=REQ('op'),
        notification_to: List[str]=REQ('to', converter=extract_recipients, default=[]),
) -> HttpResponse:
    check_send_typing_notification(user_profile, notification_to, operator)
    return json_success()
