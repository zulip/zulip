# Webhooks for external integrations.

from typing import Any, Dict

import ujson
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile, get_client

@api_key_only_webhook_view('Semaphore')
@has_request_variables
def api_semaphore_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    # semaphore only gives the last commit, even if there were multiple commits
    # since the last build
    branch_name = payload["branch_name"]
    project_name = payload["project_name"]
    result = payload["result"]
    event = payload["event"]
    commit_id = payload["commit"]["id"]
    commit_url = payload["commit"]["url"]
    author_email = payload["commit"]["author_email"]
    message = payload["commit"]["message"]

    if event == "build":
        build_url = payload["build_url"]
        build_number = payload["build_number"]
        content = u"[build %s](%s): %s\n" % (build_number, build_url, result)

    elif event == "deploy":
        build_url = payload["build_html_url"]
        build_number = payload["build_number"]
        deploy_url = payload["html_url"]
        deploy_number = payload["number"]
        server_name = payload["server_name"]
        content = u"[deploy %s](%s) of [build %s](%s) on server %s: %s\n" % \
                  (deploy_number, deploy_url, build_number, build_url, server_name, result)

    else:  # should never get here
        content = u"%s: %s\n" % (event, result)

    content += "!avatar(%s) [`%s`](%s): %s" % (author_email, commit_id[:7],
                                               commit_url, message)
    subject = u"%s/%s" % (project_name, branch_name)

    check_send_webhook_message(request, user_profile, subject, content)
    return json_success()
