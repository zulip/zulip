from typing import Annotated

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import ApiParamConfig, typed_endpoint
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("OpenSearch")
@typed_endpoint
def api_opensearch_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: Annotated[str, ApiParamConfig(argument_type_is_body=True)],
) -> HttpResponse:
    """
    OpenSearch only sends text/plain payloads, even when the Content-Type is
    set to other formats.
    Supports passing in the topic as the first line of the payload, with the
    topic prefixed by "topic:".
    """
    end_of_line = payload.find("\n")
    if payload.startswith("topic:") and end_of_line != -1:
        topic = payload[6:end_of_line].strip()
        message = payload[end_of_line + 1 :]
        check_send_webhook_message(request, user_profile, topic, message)
    else:
        check_send_webhook_message(request, user_profile, "OpenSearch alerts", payload)
    return json_success(request)
