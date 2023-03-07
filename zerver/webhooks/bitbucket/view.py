from typing import Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_rest_api_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import TOPIC_WITH_BRANCH_TEMPLATE, get_push_commits_event_message
from zerver.models import UserProfile


@authenticated_rest_api_view(webhook_client_name="Bitbucket")
@has_request_variables
def api_bitbucket_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(converter=to_wild_value),
    branches: Optional[str] = REQ(default=None),
) -> HttpResponse:
    repository = payload["repository"]

    commits = [
        {
            "name": commit["author"].tame(check_string)
            if "author" in commit
            else payload.get("user", "Someone").tame(check_string),
            "sha": commit["raw_node"].tame(check_string),
            "message": commit["message"].tame(check_string),
            "url": "{}{}commits/{}".format(
                payload["canon_url"].tame(check_string),
                repository["absolute_url"].tame(check_string),
                commit["raw_node"].tame(check_string),
            ),
        }
        for commit in payload["commits"]
    ]

    if len(commits) == 0:
        # Bitbucket doesn't give us enough information to really give
        # a useful message :/
        subject = repository["name"].tame(check_string)
        content = "{} [force pushed]({}).".format(
            payload.get("user", "Someone").tame(check_string),
            payload["canon_url"].tame(check_string) + repository["absolute_url"].tame(check_string),
        )
    else:
        branch = payload["commits"][-1]["branch"].tame(check_string)
        if branches is not None and branches.find(branch) == -1:
            return json_success(request)

        committer = payload.get("user", "Someone").tame(check_string)
        content = get_push_commits_event_message(committer, None, branch, commits)
        subject = TOPIC_WITH_BRANCH_TEMPLATE.format(
            repo=repository["name"].tame(check_string), branch=branch
        )

    check_send_webhook_message(request, user_profile, subject, content, unquote_url_parameters=True)
    return json_success(request)
