from typing import Dict

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Zapier", notify_bot_owner_on_invalid_json=False)
@has_request_variables
def api_zapier_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, object] = REQ(argument_type="body", json_validator=check_dict()),
) -> HttpResponse:
    if payload.get("type") == "auth":
        # The bot's details are used by our Zapier app to format a connection
        # label for users to be able to distinguish between different Zulip
        # bots and API keys in their UI
        return json_success(
            {
                "full_name": user_profile.full_name,
                "email": user_profile.email,
                "id": user_profile.id,
            }
        )

    topic = check_none_or(check_string)("topic", payload.get("topic"))
    content = check_string("content", payload.get("content"))

    if topic is None:
        topic = check_none_or(check_string)(
            "subject", payload.get("subject")
        )  # Backwards-compatibility
        if topic is None:
            raise JsonableError(_("Topic can't be empty"))

    check_send_webhook_message(request, user_profile, topic, content)
    return json_success()
