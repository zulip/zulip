# Webhooks for external integrations.
from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.models import get_client, get_user_profile_by_email
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile, Client
import ujson

from six import text_type
from typing import Any, Dict


@api_key_only_webhook_view('Semaphore')
@has_request_variables
def api_semaphore_webhook(request, user_profile, client,
                          payload=REQ(argument_type='body'),
                          stream=REQ(default='builds')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], str) -> HttpResponse

    # semaphore only gives the last commit, even if there were multiple commits
    # since the last build
    try:
        branch_name = payload["branch_name"]
        project_name = payload["project_name"]
        result = payload["result"]
        event = payload["event"]
        commit_id = payload["commit"]["id"]
        commit_url = payload["commit"]["url"]
        author_email = payload["commit"]["author_email"]
        message = payload["commit"]["message"]
    except KeyError as e:
        return json_error(_("Missing key %s in JSON") % (str(e),))

    if event == "build":
        try:
            build_url = payload["build_url"]
            build_number = payload["build_number"]
        except KeyError as e:
            return json_error(_("Missing key %s in JSON") % (str(e),))
        content = u"[build %s](%s): %s\n" % (build_number, build_url, result)

    elif event == "deploy":
        try:
            build_url = payload["build_html_url"]
            build_number = payload["build_number"]
            deploy_url = payload["html_url"]
            deploy_number = payload["number"]
            server_name = payload["server_name"]
        except KeyError as e:
            return json_error(_("Missing key %s in JSON") % (str(e),))
        content = u"[deploy %s](%s) of [build %s](%s) on server %s: %s\n" % \
                  (deploy_number, deploy_url, build_number, build_url, server_name, result)

    else: # should never get here
        content = u"%s: %s\n" % (event, result)

    content += "!avatar(%s) [`%s`](%s): %s" % (author_email, commit_id[:7],
                                               commit_url, message)
    subject = u"%s/%s" % (project_name, branch_name)

    check_send_message(user_profile, client, "stream",
                       [stream], subject, content)
    return json_success()
