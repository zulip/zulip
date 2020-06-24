# Webhooks for external integrations.
import base64
import re
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, cast

from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_rest_api_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.types import ViewFuncT
from zerver.lib.validator import check_dict
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import TOPIC_WITH_BRANCH_TEMPLATE, get_push_commits_event_message
from zerver.models import UserProfile


def build_message_from_gitlog(user_profile: UserProfile, name: str, ref: str,
                              commits: List[Dict[str, str]], before: str, after: str,
                              url: str, pusher: str, forced: Optional[str]=None,
                              created: Optional[str]=None, deleted: bool=False,
                              ) -> Tuple[str, str]:
    short_ref = re.sub(r'^refs/heads/', '', ref)
    subject = TOPIC_WITH_BRANCH_TEMPLATE.format(repo=name, branch=short_ref)

    commits = _transform_commits_list_to_common_format(commits)
    content = get_push_commits_event_message(pusher, url, short_ref, commits, deleted=deleted)

    return subject, content

def _transform_commits_list_to_common_format(commits: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    new_commits_list = []
    for commit in commits:
        new_commits_list.append({
            'name': commit['author'].get('username'),
            'sha': commit.get('id'),
            'url': commit.get('url'),
            'message': commit.get('message'),
        })
    return new_commits_list

# Beanstalk's web hook UI rejects url with a @ in the username section of a url
# So we ask the user to replace them with %40
# We manually fix the username here before passing it along to @authenticated_rest_api_view
def beanstalk_decoder(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        auth_type: str
        encoded_value: str
        auth_type, encoded_value = request.META['HTTP_AUTHORIZATION'].split()
        if auth_type.lower() == "basic":
            email, api_key = base64.b64decode(encoded_value).decode('utf-8').split(":")
            email = email.replace('%40', '@')
            credentials = f"{email}:{api_key}"
            encoded_credentials: str = base64.b64encode(credentials.encode('utf-8')).decode('utf8')
            request.META['HTTP_AUTHORIZATION'] = "Basic " + encoded_credentials

        return view_func(request, *args, **kwargs)

    return cast(ViewFuncT, _wrapped_view_func)  # https://github.com/python/mypy/issues/1927

@beanstalk_decoder
@authenticated_rest_api_view(webhook_client_name="Beanstalk")
@has_request_variables
def api_beanstalk_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Dict[str, Any]=REQ(validator=check_dict([])),
                          branches: Optional[str]=REQ(default=None)) -> HttpResponse:
    # Beanstalk supports both SVN and git repositories
    # We distinguish between the two by checking for a
    # 'uri' key that is only present for git repos
    git_repo = 'uri' in payload
    if git_repo:
        if branches is not None and branches.find(payload['branch']) == -1:
            return json_success()
        # To get a linkable url,
        for commit in payload['commits']:
            commit['author'] = {'username': commit['author']['name']}

        subject, content = build_message_from_gitlog(user_profile, payload['repository']['name'],
                                                     payload['ref'], payload['commits'],
                                                     payload['before'], payload['after'],
                                                     payload['repository']['url'],
                                                     payload['pusher_name'])
    else:
        author = payload.get('author_full_name')
        url = payload.get('changeset_url')
        revision = payload.get('revision')
        (short_commit_msg, _, _) = payload['message'].partition("\n")

        subject = f"svn r{revision}"
        content = f"{author} pushed [revision {revision}]({url}):\n\n> {short_commit_msg}"

    check_send_webhook_message(request, user_profile, subject, content)
    return json_success()
