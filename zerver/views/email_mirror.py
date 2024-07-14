from django.http import HttpRequest, HttpResponse

from zerver.decorator import internal_api_view
from zerver.lib.email_mirror import mirror_email_message
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint


@internal_api_view(False)
@typed_endpoint
def email_mirror_message(
    request: HttpRequest,
    *,
    rcpt_to: str,
    msg_base64: str,
) -> HttpResponse:
    result = mirror_email_message(rcpt_to, msg_base64)
    if result["status"] == "error":
        raise JsonableError(result["msg"])
    return json_success(request)
