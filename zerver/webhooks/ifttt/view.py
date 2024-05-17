from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("IFTTT")
@typed_endpoint
def api_iftt_app_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    try:
        topic_name = payload.get("topic").tame(check_none_or(check_string))
        content = payload.get("content").tame(check_none_or(check_string))

        if topic_name is None:
            topic_name = payload.get("subject").tame(
                check_none_or(check_string)
            )  # Backwards-compatibility
            if topic_name is None:
                raise JsonableError(_("Topic can't be empty"))

        if content is None:
            raise JsonableError(_("Content can't be empty"))

    except ValidationError:
        raise JsonableError(_("Malformed payload"))

    check_send_webhook_message(request, user_profile, topic_name, content)
    return json_success(request)
