# Webhooks for external integrations.
import re

from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.decorator import authenticated_rest_api_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import (
    TOPIC_WITH_BRANCH_TEMPLATE,
    get_push_commits_event_message,
    is_branch_name_notifiable,
)
from zerver.models import UserProfile


def build_message_from_gitlog(
    user_profile: UserProfile,
    name: str,
    ref: str,
    commits: WildValue,
    before: str,
    after: str,
    url: str,
    pusher: str,
    forced: str | None = None,
    created: str | None = None,
    deleted: bool = False,
) -> tuple[str, str]:
    short_ref = re.sub(r"^refs/heads/", "", ref)
    topic_name = TOPIC_WITH_BRANCH_TEMPLATE.format(repo=name, branch=short_ref)

    commits_data = _transform_commits_list_to_common_format(commits)
    content = get_push_commits_event_message(pusher, url, short_ref, commits_data, deleted=deleted)

    return topic_name, content


def _transform_commits_list_to_common_format(commits: WildValue) -> list[dict[str, str]]:
    return [
        {
            "name": commit["author"]["name"].tame(check_string),
            "sha": commit["id"].tame(check_string),
            "url": commit["url"].tame(check_string),
            "message": commit["message"].tame(check_string),
        }
        for commit in commits
    ]


@authenticated_rest_api_view(
    webhook_client_name="Beanstalk",
    # Beanstalk's web hook UI rejects URL with a @ in the username section
    # So we ask the user to replace them with %40
    beanstalk_email_decode=True,
)
@typed_endpoint
def api_beanstalk_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: Json[WildValue],
    branches: str | None = None,
) -> HttpResponse:
    # Beanstalk supports both SVN and Git repositories
    # We distinguish between the two by checking for a
    # 'uri' key that is only present for Git repos
    git_repo = "uri" in payload
    if git_repo:
        branch = payload["branch"].tame(check_string)
        if not is_branch_name_notifiable(branch, branches):
            return json_success(request)

        topic_name, content = build_message_from_gitlog(
            user_profile,
            payload["repository"]["name"].tame(check_string),
            payload["ref"].tame(check_string),
            payload["commits"],
            payload["before"].tame(check_string),
            payload["after"].tame(check_string),
            payload["repository"]["url"].tame(check_string),
            payload["pusher_name"].tame(check_string),
        )
    else:
        author = payload["author_full_name"].tame(check_string)
        url = payload["changeset_url"].tame(check_string)
        revision = payload["revision"].tame(check_int)
        (short_commit_msg, _, _) = payload["message"].tame(check_string).partition("\n")

        topic_name = f"svn r{revision}"
        content = f"{author} pushed [revision {revision}]({url}):\n\n> {short_commit_msg}"

    check_send_webhook_message(request, user_profile, topic_name, content)
    return json_success(request)
