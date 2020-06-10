from typing import List, Union

from django.http import HttpRequest, HttpResponse

from zerver.decorator import REQ, has_request_variables
from zerver.lib.actions import (
    check_send_typing_notification,
    extract_private_recipients,
)
from zerver.lib.response import json_success
from zerver.models import UserProfile

EMPTY_STRS: List[str] = []
EMPTY_STRS_OR_INTS: Union[List[str], List[int]] = EMPTY_STRS

@has_request_variables
def send_notification_backend(
    request: HttpRequest, user_profile: UserProfile,
    operator: str=REQ('op'),
    notification_to: Union[List[str], List[int]]=REQ(
        'to', converter=extract_private_recipients, default=EMPTY_STRS_OR_INTS,
    ),
) -> HttpResponse:
    check_send_typing_notification(user_profile, notification_to, operator)
    return json_success()
