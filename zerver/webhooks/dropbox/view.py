from typing import Text
from django.http import HttpRequest, HttpResponse
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile

@api_key_only_webhook_view('Dropbox')
@has_request_variables
def api_dropbox_webhook(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    if request.method == 'GET':
        return HttpResponse(request.GET['challenge'])
    elif request.method == 'POST':
        topic = 'Dropbox'
        check_send_webhook_message(request, user_profile, topic,
                                   "File has been updated on Dropbox!")
        return json_success()
