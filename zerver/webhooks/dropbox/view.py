from typing import Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import has_request_variables, webhook_view
from zerver.lib.request import REQ, RequestVariableMissingError
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view('Dropbox', notify_bot_owner_on_invalid_json=False)
@has_request_variables
def api_dropbox_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    challenge: Optional[str]=REQ(default=None),
) -> HttpResponse:
    if request.method == 'POST':
        topic = 'Dropbox'
        check_send_webhook_message(request, user_profile, topic,
                                   "File has been updated on Dropbox!")
        return json_success()
    else:
        if challenge is None:
            raise RequestVariableMissingError("challenge")
        return HttpResponse(challenge, content_type="text/plain; charset=UTF-8")
