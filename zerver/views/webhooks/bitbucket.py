from __future__ import absolute_import

from six import text_type
from typing import Any, Mapping

from django.http import HttpRequest, HttpResponse

from zerver.models import get_client, UserProfile
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict
from zerver.decorator import REQ, has_request_variables, authenticated_rest_api_view

from .github import build_commit_list_content


@authenticated_rest_api_view(is_webhook=True)
@has_request_variables
def api_bitbucket_webhook(request, user_profile, payload=REQ(validator=check_dict([])),
                          stream=REQ(default='commits')):
    # type: (HttpRequest, UserProfile, Mapping[text_type, Any], text_type) -> HttpResponse
    repository = payload['repository']
    commits = [{u'id': commit['raw_node'], u'message': commit['message'],
                u'url': u'%s%scommits/%s' % (payload['canon_url'],
                                           repository['absolute_url'],
                                           commit['raw_node'])}
               for commit in payload['commits']]

    subject = repository['name']
    if len(commits) == 0:
        # Bitbucket doesn't give us enough information to really give
        # a useful message :/
        content = (u"%s [force pushed](%s)"
                   % (payload['user'],
                      payload['canon_url'] + repository['absolute_url']))
    else:
        branch = payload['commits'][-1]['branch']
        content = build_commit_list_content(commits, branch, None, payload['user'])
        subject += u'/%s' % (branch,)

    check_send_message(user_profile, get_client("ZulipBitBucketWebhook"), "stream",
                       [stream], subject, content)
    return json_success()
