# Webhooks for external integrations.

from __future__ import absolute_import
from django.http import HttpRequest, HttpResponse
from zerver.models import get_client, UserProfile
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict
from zerver.decorator import REQ, has_request_variables, authenticated_rest_api_view

import base64
from functools import wraps

from .github import build_message_from_gitlog

from typing import Any, Callable, Dict, TypeVar
from zerver.lib.str_utils import force_str, force_bytes

ViewFuncT = TypeVar('ViewFuncT', bound=Callable[..., HttpResponse])

# Beanstalk's web hook UI rejects url with a @ in the username section of a url
# So we ask the user to replace them with %40
# We manually fix the username here before passing it along to @authenticated_rest_api_view
def beanstalk_decoder(view_func):
    # type: (ViewFuncT) -> ViewFuncT
    @wraps(view_func)
    def _wrapped_view_func(request, *args, **kwargs):
        # type: (HttpRequest, *Any, **Any) -> HttpResponse
        try:
            auth_type, encoded_value = request.META['HTTP_AUTHORIZATION'].split() # type: str, str
            if auth_type.lower() == "basic":
                email, api_key = base64.b64decode(force_bytes(encoded_value)).decode('utf-8').split(":")
                email = email.replace('%40', '@')
                credentials = u"%s:%s" % (email, api_key)
                encoded_credentials = force_str(base64.b64encode(credentials.encode('utf-8')))
                request.META['HTTP_AUTHORIZATION'] = "Basic " + encoded_credentials
        except Exception:
            pass

        return view_func(request, *args, **kwargs)

    return _wrapped_view_func # type: ignore # https://github.com/python/mypy/issues/1927

@beanstalk_decoder
@authenticated_rest_api_view(is_webhook=True)
@has_request_variables
def api_beanstalk_webhook(request, user_profile,
                          payload=REQ(validator=check_dict([]))):
    # type: (HttpRequest, UserProfile, Dict[str, Any]) -> HttpResponse
    # Beanstalk supports both SVN and git repositories
    # We distinguish between the two by checking for a
    # 'uri' key that is only present for git repos
    git_repo = 'uri' in payload
    if git_repo:
        # To get a linkable url,
        subject, content = build_message_from_gitlog(user_profile, payload['repository']['name'],
                                                     payload['ref'], payload['commits'],
                                                     payload['before'], payload['after'],
                                                     payload['repository']['url'],
                                                     payload['pusher_name'])
    else:
        author = payload.get('author_full_name')
        url = payload.get('changeset_url')
        revision = payload.get('revision')
        (short_commit_msg, _, _) = payload.get('message').partition("\n")

        subject = "svn r%s" % (revision,)
        content = "%s pushed [revision %s](%s):\n\n> %s" % (author, revision, url, short_commit_msg)

    check_send_message(user_profile, get_client("ZulipBeanstalkWebhook"), "stream",
                       ["commits"], subject, content)
    return json_success()
