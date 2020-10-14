# vim:fenc=utf-8
from typing import Any, Dict, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.webhooks.common import get_http_headers_from_filename
from zerver.lib.webhooks.git import get_pull_request_event_message
from zerver.models import UserProfile

# Gitea is a fork of Gogs, and so the webhook implementation is nearly the same.
from zerver.webhooks.gogs.view import gogs_webhook_main

fixture_to_headers = get_http_headers_from_filename("HTTP_X_GITEA_EVENT")

def format_pull_request_event(payload: Dict[str, Any],
                              include_title: bool=False) -> str:
    assignee = payload['pull_request']['assignee']
    data = {
        'user_name': payload['pull_request']['user']['username'],
        'action': payload['action'],
        'url': payload['pull_request']['html_url'],
        'number': payload['pull_request']['number'],
        'target_branch': payload['pull_request']['head']['ref'],
        'base_branch': payload['pull_request']['base']['ref'],
        'title': payload['pull_request']['title'] if include_title else None,
        'assignee': assignee['login'] if assignee else None,
    }

    if payload['pull_request']['merged']:
        data['user_name'] = payload['pull_request']['merged_by']['username']
        data['action'] = 'merged'

    return get_pull_request_event_message(**data)

@webhook_view('Gitea')
@has_request_variables
def api_gitea_webhook(request: HttpRequest, user_profile: UserProfile,
                      payload: Dict[str, Any]=REQ(argument_type='body'),
                      branches: Optional[str]=REQ(default=None),
                      user_specified_topic: Optional[str]=REQ("topic", default=None)) -> HttpResponse:
    return gogs_webhook_main('Gitea', 'X_GITEA_EVENT', format_pull_request_event,
                             request, user_profile, payload, branches, user_specified_topic)
