# Webhooks for external integrations.
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
    topic: str,
    message: Annotated[str, ApiParamConfig(argument_type_is_body=True)],
) -> HttpResponse:
    """
    OpenSearch custom webhook notifications send the message as raw text.
    """
    check_send_webhook_message(request, user_profile, topic, message)
    return json_success(request)
