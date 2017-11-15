# Webhooks for external integrations.
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.models import UserProfile

@api_key_only_webhook_view('Transifex')
@has_request_variables
def api_transifex_webhook(request, user_profile,
                          project=REQ(), resource=REQ(),
                          language=REQ(), translated=REQ(default=None),
                          reviewed=REQ(default=None),
                          stream=REQ(default='transifex')):
    # type: (HttpRequest, UserProfile, str, str, str, Optional[int], Optional[int], str) -> HttpResponse
    subject = "{} in {}".format(project, language)
    if translated:
        body = "Resource {} fully translated.".format(resource)
    elif reviewed:
        body = "Resource {} fully reviewed.".format(resource)
    else:
        return json_error(_("Transifex wrong request"))
    check_send_stream_message(user_profile, request.client, stream, subject, body)
    return json_success()
