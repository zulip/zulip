from typing import Any, Mapping, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_rest_api_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import TOPIC_WITH_BRANCH_TEMPLATE, \
    get_push_commits_event_message
from zerver.models import UserProfile

@authenticated_rest_api_view(webhook_client_name="Bitbucket")
@has_request_variables
def api_bitbucket_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Mapping[str, Any]=REQ(validator=check_dict([])),
                          branches: Optional[str]=REQ(default=None)) -> HttpResponse:
    repository = payload['repository']

    commits = [
        {
            'name': payload.get('user'),
            'sha': commit.get('raw_node'),
            'message': commit.get('message'),
            'url': u'{}{}commits/{}'.format(
                payload.get('canon_url'),
                repository.get('absolute_url'),
                commit.get('raw_node'))
        }
        for commit in payload['commits']
    ]

    if len(commits) == 0:
        # Bitbucket doesn't give us enough information to really give
        # a useful message :/
        subject = repository['name']
        content = (u"%s [force pushed](%s)"
                   % (payload['user'],
                      payload['canon_url'] + repository['absolute_url']))
    else:
        branch = payload['commits'][-1]['branch']
        if branches is not None and branches.find(branch) == -1:
            return json_success()
        content = get_push_commits_event_message(payload['user'], None, branch, commits)
        subject = TOPIC_WITH_BRANCH_TEMPLATE.format(repo=repository['name'], branch=branch)

    check_send_webhook_message(request, user_profile, subject, content,
                               unquote_url_parameters=True)
    return json_success()
