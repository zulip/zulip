from typing import Annotated

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import StringConstraints

from zerver.actions.message_send import internal_send_private_message
from zerver.decorator import require_realm_admin
from zerver.lib.exceptions import JsonableError
from zerver.lib.onboarding import get_custom_welcome_message_string
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models.realms import Realm
from zerver.models.users import UserProfile, get_system_bot


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

    welcome_bot_custom_message_string = get_custom_welcome_message_string(
        user_profile.realm, welcome_message_custom_text
    )
    message_id = internal_send_private_message(
        get_system_bot(settings.WELCOME_BOT, user_profile.realm_id),
        user_profile,
        welcome_bot_custom_message_string,
        disable_external_notifications=True,
    )
    assert message_id is not None
    return json_success(request, data={"message_id": message_id})
