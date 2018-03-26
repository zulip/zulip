# Webhooks for external integrations.

import base64
from functools import wraps
from typing import Any, Callable, Dict, Optional, Text, TypeVar

from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_rest_api_view
from zerver.lib.types import ViewFuncT
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.validator import check_dict
from zerver.models import UserProfile, get_client
from zerver.webhooks.github.view import build_message_from_gitlog

# Beanstalk's web hook UI rejects url with a @ in the username section of a url
# So we ask the user to replace them with %40
# We manually fix the username here before passing it along to @authenticated_rest_api_view
def beanstalk_decoder(view_func: ViewFuncT) -> ViewFuncT:
    @wraps(view_func)
    def _wrapped_view_func(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        try:
            auth_type, encoded_value = request.META['HTTP_AUTHORIZATION'].split()  # type: str, str
            if auth_type.lower() == "basic":
                email, api_key = base64.b64decode(encoded_value).decode('utf-8').split(":")
                email = email.replace('%40', '@')
                credentials = u"%s:%s" % (email, api_key)
                encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf8')  # type: str
                request.META['HTTP_AUTHORIZATION'] = "Basic " + encoded_credentials
        except Exception:
            pass

        return view_func(request, *args, **kwargs)

    return _wrapped_view_func  # type: ignore # https://github.com/python/mypy/issues/1927

@beanstalk_decoder
@authenticated_rest_api_view(webhook_client_name="Beanstalk")
@has_request_variables
def api_beanstalk_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Dict[str, Any]=REQ(validator=check_dict([])),
                          branches: Optional[Text]=REQ(default=None)) -> HttpResponse:
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

        subject = "svn r%s" % (revision,)
        content = "%s pushed [revision %s](%s):\n\n> %s" % (author, revision, url, short_commit_msg)

    check_send_webhook_message(request, user_profile, subject, content)
    return json_success()
