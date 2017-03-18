from __future__ import absolute_import

from typing import Any, Mapping, Text

from django.http import HttpRequest, HttpResponse

from zerver.models import get_client, UserProfile
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict
from zerver.decorator import REQ, has_request_variables, authenticated_rest_api_view
from zerver.lib.webhooks.git import get_push_commits_event_message, SUBJECT_WITH_BRANCH_TEMPLATE


@authenticated_rest_api_view(is_webhook=True)
@has_request_variables
def api_bitbucket_webhook(request, user_profile, payload=REQ(validator=check_dict([])),
                          stream=REQ(default='commits')):
    # type: (HttpRequest, UserProfile, Mapping[Text, Any], Text) -> HttpResponse
    repository = payload['repository']

    commits = [
        {
            'sha': commit.get('raw_node'),
            'message': commit.get('message'),
            'url': u'{}{}commits/{}'.format(
                payload.get('canon_url'),
                repository.get('absolute_url'),
                commit.get('raw_node'))
        }
        for commit in payload.get('commits')
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
        content = get_push_commits_event_message(payload.get('user'), None, branch, commits)
        subject = SUBJECT_WITH_BRANCH_TEMPLATE.format(repo=repository['name'], branch=branch)

    check_send_message(user_profile, get_client("ZulipBitBucketWebhook"), "stream",
                       [stream], subject, content)
    return json_success()
