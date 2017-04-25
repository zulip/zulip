from __future__ import absolute_import

import ujson

from django.http import HttpRequest, HttpResponse

from zerver.decorator import internal_notify_view
from zerver.lib.email_mirror import mirror_email_message
from zerver.lib.response import json_error, json_success


@internal_notify_view(False)
def email_mirror_message(request):
    # type: (HttpRequest) -> HttpResponse
    result = mirror_email_message(ujson.loads(request.POST['data']))
    if result["status"] == "error":
        return json_error(result['msg'])
    return json_success()
