# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

PUBLISH_POST_OR_PAGE_TEMPLATE = """
New {type} published:
* [{title}]({url})
""".strip()
ALL_EVENT_TYPES = [
    "publish_post",
    "publish_page",
]


@webhook_view("WordPress", notify_bot_owner_on_invalid_json=False, all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_wordpress_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    hook: str = "WordPress action",
    post_title: str = "New WordPress post",
    post_type: str = "post",
    post_url: str = "WordPress post URL",
) -> HttpResponse:
    # remove trailing whitespace (issue for some test fixtures)
    hook = hook.rstrip()

    if hook in ("publish_post", "publish_page"):
        data = PUBLISH_POST_OR_PAGE_TEMPLATE.format(type=post_type, title=post_title, url=post_url)
    else:
        raise JsonableError(_("Unknown WordPress webhook action: {hook}").format(hook=hook))

    topic_name = "WordPress notification"

    check_send_webhook_message(request, user_profile, topic_name, data, hook)
    return json_success(request)
