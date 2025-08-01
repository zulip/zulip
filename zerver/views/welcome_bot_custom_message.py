from typing import Annotated

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import StringConstraints

from zerver.decorator import require_realm_admin
from zerver.lib.exceptions import JsonableError
from zerver.lib.onboarding import send_initial_direct_messages_to_user
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
    if len(welcome_message_custom_text) == 0:
        raise JsonableError(_("Message must not be empty"))

    message_ids = send_initial_direct_messages_to_user(
        user_profile, welcome_message_custom_text=welcome_message_custom_text
    )
    welcome_bot_custom_message_id = message_ids.welcome_bot_custom_message_id
    assert welcome_bot_custom_message_id is not None
    return json_success(request, data={"message_id": welcome_bot_custom_message_id})
