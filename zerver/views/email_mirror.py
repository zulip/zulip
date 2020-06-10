from typing import Dict

import ujson
from django.http import HttpRequest, HttpResponse

from zerver.decorator import internal_notify_view
from zerver.lib.email_mirror import mirror_email_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_dict, check_string


@internal_notify_view(False)
@has_request_variables
def email_mirror_message(request: HttpRequest,
                         data: Dict[str, str]=REQ(validator=check_dict([
                             ('recipient', check_string),
                             ('msg_text', check_string)]))) -> HttpResponse:
    result = mirror_email_message(ujson.loads(request.POST['data']))
    if result["status"] == "error":
        return json_error(result['msg'])
    return json_success()
