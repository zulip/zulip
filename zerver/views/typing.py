from typing import List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import REQ, has_request_variables
from zerver.lib.actions import check_send_typing_notification
from zerver.lib.response import json_success
from zerver.lib.validator import check_int, check_list
from zerver.models import UserProfile


@has_request_variables
def send_notification_backend(
        request: HttpRequest,
        user_profile: UserProfile,
        operator: str=REQ('op'),
        notification_to: List[int]=REQ('to', validator=check_list(check_int))) -> HttpResponse:
    check_send_typing_notification(user_profile, notification_to, operator)
    return json_success()
