from typing import Text
from django.http import HttpRequest, HttpResponse
from zerver.lib.actions import check_send_stream_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile

@api_key_only_webhook_view('Dropbox')
@has_request_variables
def api_dropbox_webhook(request: HttpRequest, user_profile: UserProfile,
                        stream: Text=REQ(default='test'),
                        topic: Text=REQ(default='Dropbox')) -> HttpResponse:
    if request.method == 'GET':
        return HttpResponse(request.GET['challenge'])
    elif request.method == 'POST':
        check_send_stream_message(user_profile, request.client,
                                  stream, topic, "File has been updated on Dropbox!")
        return json_success()
