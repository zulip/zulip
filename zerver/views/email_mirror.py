from django.http import HttpRequest, HttpResponse

from zerver.decorator import internal_api_view
from zerver.lib.email_mirror import mirror_email_message
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success


@internal_api_view(False)
@has_request_variables
def email_mirror_message(
    request: HttpRequest,
    rcpt_to: str = REQ(),
    msg_base64: str = REQ(),
) -> HttpResponse:
    result = mirror_email_message(rcpt_to, msg_base64)
    if result["status"] == "error":
        raise JsonableError(result["msg"])
    return json_success(request)
