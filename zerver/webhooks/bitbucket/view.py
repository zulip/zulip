from __future__ import absolute_import

from typing import Any, Mapping, Text, Optional

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
                          stream=REQ(default='commits'), branches=REQ(default=None)):
    # type: (HttpRequest, UserProfile, Mapping[Text, Any], Text, Optional[Text]) -> HttpResponse
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
        subject = SUBJECT_WITH_BRANCH_TEMPLATE.format(repo=repository['name'], branch=branch)

    check_send_message(user_profile, get_client("ZulipBitBucketWebhook"), "stream",
                       [stream], subject, content)
    return json_success()
