# Webhooks for external integrations.
from __future__ import absolute_import
from typing import Text

from django.http import HttpRequest, HttpResponse

from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile, Client


@api_key_only_webhook_view("Heroku")
@has_request_variables
def api_heroku_webhook(request, user_profile, client, stream=REQ(default="heroku"),
                       head=REQ(), app=REQ(), user=REQ(), url=REQ(), git_log=REQ()):
    # type: (HttpRequest, UserProfile, Client, Text, Text, Text, Text, Text, Text) -> HttpResponse
    template = "{} deployed version {} of [{}]({})\n> {}"
    content = template.format(user, head, app, url, git_log)

    check_send_message(user_profile, client, "stream", [stream], app, content)
    return json_success()
