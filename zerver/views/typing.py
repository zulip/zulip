from typing import List

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import REQ, has_request_variables
from zerver.lib.actions import check_send_typing_notification
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_int, check_list, check_string_in
from zerver.models import UserProfile

VALID_OPERATOR_TYPES = ["start", "stop"]
VALID_MESSAGE_TYPES = ["private"]


@has_request_variables
def send_notification_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    message_type: str = REQ(
        "type", str_validator=check_string_in(VALID_MESSAGE_TYPES), default="private"
    ),
    operator: str = REQ("op", str_validator=check_string_in(VALID_OPERATOR_TYPES)),
    user_ids: List[int] = REQ("to", validator=check_list(check_int)),
) -> HttpResponse:
    if len(user_ids) == 0:
        return json_error(_("Missing parameter: 'to' (recipient)"))

    check_send_typing_notification(user_profile, user_ids, operator)
    return json_success()
