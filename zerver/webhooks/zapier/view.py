from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Zapier", notify_bot_owner_on_invalid_json=False)
@typed_endpoint
def api_zapier_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    if payload.get("type").tame(check_none_or(check_string)) == "auth":
        # The bot's details are used by our Zapier app to format a connection
        # label for users to be able to distinguish between different Zulip
        # bots and API keys in their UI
        return json_success(
            request,
            data={
                "full_name": user_profile.full_name,
                "email": user_profile.email,
                "id": user_profile.id,
            },
        )

    topic = payload.get("topic").tame(check_none_or(check_string))
    content = payload.get("content").tame(check_none_or(check_string))

    if topic is None:
        topic = payload.get("subject").tame(check_none_or(check_string))  # Backwards-compatibility
        if topic is None:
            raise JsonableError(_("Topic can't be empty"))

    if content is None:
        raise JsonableError(_("Content can't be empty"))

    check_send_webhook_message(request, user_profile, topic, content)
    return json_success(request)
