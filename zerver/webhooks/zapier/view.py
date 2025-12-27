import re

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_none_or, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


def sanitize_links(content: str | None) -> str | None:
    """
    Remove whitespace inside URLs so links remain clickable.

    Example:
        "https://example.org/this /is /broken"
        becomes:
        "https://example.org/this/is/broken"
    """

    if content is None:
        return None

    # Match URLs that may contain spaces inside them
    url_pattern = re.compile(r"https?://\S+(?:\s+\S+)*")

    def _clean(match: re.Match[str]) -> str:
        url = match.group(0)
        # Remove ALL whitespace inside the URL
        return re.sub(r"\s+", "", url)

    return url_pattern.sub(_clean, content)


@webhook_view("Zapier", notify_bot_owner_on_invalid_json=False)
@typed_endpoint
def api_zapier_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    if payload.get("type").tame(check_none_or(check_string)) == "auth":
        return json_success(
            request,
            data={
                "full_name": user_profile.full_name,
                "email": user_profile.email,
                "id": user_profile.id,
            },
        )

    topic_name = payload.get("topic").tame(check_none_or(check_string))
    content = payload.get("content").tame(check_none_or(check_string))

    # 🔧 fix malformed Zapier links before sending
    content = sanitize_links(content)

    if topic_name is None:
        topic_name = payload.get("subject").tame(check_none_or(check_string))
        if topic_name is None:
            raise JsonableError(_("Topic can't be empty"))

    if content is None:
        raise JsonableError(_("Content can't be empty"))

    check_send_webhook_message(request, user_profile, topic_name, content)
    return json_success(request)
