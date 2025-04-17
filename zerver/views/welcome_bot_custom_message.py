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
    welcome_bot_custom_message: Annotated[
        str | None,
        StringConstraints(
            max_length=Realm.MAX_REALM_WELCOME_BOT_CUSTOM_MESSAGE_LENGTH,
        ),
    ] = None,
) -> HttpResponse:
    message_id = send_initial_direct_message(
        user_profile, welcome_bot_custom_message=welcome_bot_custom_message
    )
    return json_success(request, data={"message_id": message_id})
