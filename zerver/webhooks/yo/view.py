# Webhooks for external integrations.
from typing import Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_private_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile, get_user

@api_key_only_webhook_view('Yo', notify_bot_owner_on_invalid_json=False)
@has_request_variables
def api_yo_app_webhook(request: HttpRequest, user_profile: UserProfile,
                       email: str = REQ(default=""),
                       username: str = REQ(default='Yo Bot'),
                       topic: Optional[str] = REQ(default=None),
                       user_ip: Optional[str] = REQ(default=None)) -> HttpResponse:
    body = ('Yo from %s') % (username,)
    receiving_user = get_user(email, user_profile.realm)
    check_send_private_message(user_profile, request.client, receiving_user, body)
    return json_success()
