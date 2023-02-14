from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_none_or, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("IFTTT")
@has_request_variables
def api_iftt_app_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    try:
        topic = payload.get("topic").tame(check_none_or(check_string))
        content = payload.get("content").tame(check_none_or(check_string))

        if topic is None:
            topic = payload.get("subject").tame(
                check_none_or(check_string)
            )  # Backwards-compatibility
            if topic is None:
                raise JsonableError(_("Topic can't be empty"))

        if content is None:
            raise JsonableError(_("Content can't be empty"))

    except ValidationError:
        raise JsonableError(_("Malformed payload"))

    check_send_webhook_message(request, user_profile, topic, content)
    return json_success(request)
