# Webhooks for external integrations.
from __future__ import absolute_import
from zerver.models import get_client
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, authenticated_rest_api_view
import ujson



@authenticated_rest_api_view
@has_request_variables
def api_stash_webhook(request, user_profile, stream=REQ(default='')):
    try:
        payload = ujson.loads(request.body)
    except ValueError:
        return json_error("Malformed JSON input")

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
        return json_error("Missing key %s in JSON" % (e.message,))

    try:
        stream = request.GET['stream']
    except (AttributeError, KeyError):
        stream = 'commits'

    subject = "%s/%s: %s" % (project_name, repo_name, branch_name)

    content = "`%s` was pushed to **%s** in **%s/%s** with:\n\n" % (
        head_ref, branch_name, project_name, repo_name)
    content += "\n".join("* `%s`: %s" % (
            commit[0], commit[1]) for commit in commits)

    check_send_message(user_profile, get_client("ZulipStashWebhook"), "stream",
                       [stream], subject, content)
    return json_success()
