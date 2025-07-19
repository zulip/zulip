from typing import Annotated

from django.http import HttpRequest, HttpResponse
from pydantic import StringConstraints

from zerver.decorator import require_realm_admin
from zerver.lib.onboarding import send_initial_direct_message
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models.realms import Realm
from zerver.models.users import UserProfile


@require_realm_admin
@typed_endpoint
def send_test_welcome_bot_custom_message(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    welcome_message_custom_text: Annotated[
        str,
        StringConstraints(
            max_length=Realm.MAX_REALM_WELCOME_MESSAGE_CUSTOM_TEXT_LENGTH,
        ),
    ],
) -> HttpResponse:
    message_ids = send_initial_direct_message(
        user_profile, welcome_message_custom_text=welcome_message_custom_text
    )
    # In the list of message IDs returned by the `send_initial_direct_message()` function,
    # the first value is the message ID of the initial message. The second value is the
    # message ID of the Welcome Bot custom message (if provided).
    assert len(message_ids) > 1
    welcome_bot_custom_message_id = message_ids[1]
    return json_success(request, data={"message_id": welcome_bot_custom_message_id})
