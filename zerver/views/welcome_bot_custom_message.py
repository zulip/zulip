from django.http import HttpRequest, HttpResponse

from zerver.decorator import require_realm_admin
from zerver.lib.onboarding import send_initial_direct_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_capped_string
from zerver.models.users import UserProfile


@require_realm_admin
@has_request_variables
def send_test_custom_welcome_bot_message(
    request: HttpRequest,
    user_profile: UserProfile,
    custom_welcome_bot_message: str = REQ(str_validator=check_capped_string(max_length=1000)),
) -> HttpResponse:
    custom_welcome_bot_message = custom_welcome_bot_message.strip()
    send_initial_direct_message(
        user=user_profile,
        custom_welcome_bot_message=custom_welcome_bot_message,
    )
    return json_success(request)
