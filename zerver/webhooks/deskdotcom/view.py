# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_rest_api_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


# Desk.com's integrations all make the user supply a template, where it fills
# in stuff like {{customer.name}} and posts the result as a "data" parameter.
# There's no raw JSON for us to work from. Thus, it makes sense to just write
# a template Zulip message within Desk.com and have the webhook extract that
# from the "data" param and post it, which this does.
@authenticated_rest_api_view(webhook_client_name="Desk")
@typed_endpoint
def api_deskdotcom_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    data: str,
) -> HttpResponse:
    topic = "Desk.com notification"
    check_send_webhook_message(request, user_profile, topic, data)
    return json_success(request)
