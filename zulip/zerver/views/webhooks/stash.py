# Webhooks for external integrations.
from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.models import get_client
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, authenticated_rest_api_view
from zerver.models import UserProfile
import ujson

from six import text_type
from typing import Any, Dict


@authenticated_rest_api_view(is_webhook=True)
@has_request_variables
def api_stash_webhook(request, user_profile, payload=REQ(argument_type='body'),
                      stream=REQ(default='commits')):
    # type: (HttpRequest, UserProfile, Dict[str, Any], text_type) -> HttpResponse
    # We don't get who did the push, or we'd try to report that.
    try:
        repo_name = payload["repository"]["name"]
        project_name = payload["repository"]["project"]["name"]
        branch_name = payload["refChanges"][0]["refId"].split("/")[-1]
        commit_entries = payload["changesets"]["values"]
        commits = [(entry["toCommit"]["displayId"],
                    entry["toCommit"]["message"].split("\n")[0]) for \
                       entry in commit_entries]
        head_ref = commit_entries[-1]["toCommit"]["displayId"]
    except KeyError as e:
        return json_error(_("Missing key %s in JSON") % (str(e),))

    subject = "%s/%s: %s" % (project_name, repo_name, branch_name)

    content = "`%s` was pushed to **%s** in **%s/%s** with:\n\n" % (
        head_ref, branch_name, project_name, repo_name)
    content += "\n".join("* `%s`: %s" % (
            commit[0], commit[1]) for commit in commits)

    check_send_message(user_profile, get_client("ZulipStashWebhook"), "stream",
                       [stream], subject, content)
    return json_success()
