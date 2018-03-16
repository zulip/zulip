# Webhooks for external integrations.
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

@api_key_only_webhook_view('Transifex')
@has_request_variables
def api_transifex_webhook(request: HttpRequest, user_profile: UserProfile,
                          project: str=REQ(), resource: str=REQ(),
                          language: str=REQ(), translated: Optional[int]=REQ(default=None),
                          reviewed: Optional[int]=REQ(default=None)) -> HttpResponse:
    subject = "{} in {}".format(project, language)
    if translated:
        body = "Resource {} fully translated.".format(resource)
    elif reviewed:
        body = "Resource {} fully reviewed.".format(resource)
    else:
        return json_error(_("Transifex wrong request"))
    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()
