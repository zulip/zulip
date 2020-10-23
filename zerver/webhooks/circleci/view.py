from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

outcome_to_formatted_status_map = {
    "success": "has succeeded",
    "failed": "has failed",
    "canceled": "was canceled",
}

@webhook_view('CircleCI')
@has_request_variables
def api_circleci_webhook(request: HttpRequest, user_profile: UserProfile,
                         payload: Dict[str, Any]=REQ(argument_type="body")) -> HttpResponse:
    payload = payload['payload']
    subject = get_subject(payload)
    body = get_body(payload)

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()

def get_subject(payload: Dict[str, Any]) -> str:
    repository_name = payload["reponame"]
    return f"{repository_name}"

def get_commit_range_info(payload: Dict[str, Any]) -> str:
    commits = payload["all_commit_details"]
    num_commits = len(commits)

    if num_commits == 1:
        commit_id = commits[0]["commit"][:10]
        commit_url = commits[0]["commit_url"]
        return f"- **Commit:** [{commit_id}]({commit_url})"

    vcs_provider = payload["user"]["vcs_type"]  # Same as payload["why"]?
    first_commit_id = commits[0]["commit"]
    shortened_first_commit_id = first_commit_id[:10]
    last_commit_id = commits[-1]["commit"]
    shortened_last_commit_id = last_commit_id[:10]
    if vcs_provider == "github":
        # Then use GitHub's commit range feature to form the appropriate url.
        vcs_url = payload["vcs_url"]
        commit_range_url = f"{vcs_url}/compare/{first_commit_id}...{last_commit_id}"
        return f"- **Commits ({num_commits}):** [{shortened_first_commit_id} ... {shortened_last_commit_id}]({commit_range_url})"
    else:
        # Bitbucket doesn't have a good commit range URL feature like GitHub does.
        # So let's just show the two separately.
        # https://community.atlassian.com/t5/Bitbucket-questions/BitBucket-4-14-diff-between-any-two-commits/qaq-p/632974
        first_commit_url = commits[0]["commit_url"]
        last_commit_url = commits[-1]["commit_url"]
        return f"- **Commits ({num_commits}):** [{shortened_first_commit_id}]({first_commit_url}) ... [{shortened_last_commit_id}]({last_commit_url})"

def get_authors_and_committer_info(payload: Dict[str, Any]) -> str:
    body = ""

    author_names = set()
    committer_names = set()
    for commit in payload["all_commit_details"]:
        author_name = commit["author_name"]
        author_username = commit["author_login"]
        if author_username:
            author_names.add(f"{author_name} ({author_username})")
        else:
            author_names.add(commit["author_name"])

        if commit.get("committer_email", None):
            committer_name = commit["committer_name"]
            committer_username = commit["committer_login"]
            if committer_username:
                committer_names.add(f"{committer_name} ({committer_username})")
            else:
                committer_names.add(commit["committer_name"])

    author_names_list = list(author_names)
    author_names_list.sort()
    committer_names_list = list(committer_names)
    committer_names_list.sort()
    authors = ", ".join(author_names_list)
    committers = ", ".join(committer_names_list)

    # Add the authors' information to the body.
    if len(author_names_list) > 1:
        body += f"- **Authors:** {authors}"
    else:
        body += f"- **Author:** {authors}"

    # Add information about the committers if it was provided.
    if len(committer_names) > 0:
        if len(committer_names) > 1:
            body += f"\n- **Committers:** {committers}"
        else:
            body += f"\n- **Committer:** {committers}"

    return body

def super_minimal_body(payload: Dict[str, Any]) -> str:
    branch_name = payload["branch"]
    status = payload["status"]
    formatted_status = outcome_to_formatted_status_map.get(status, status)
    build_url = payload["build_url"]
    username = payload["username"]
    return f"[Build]({build_url}) triggered by {username} on branch `{branch_name}` {formatted_status}."

def get_body(payload: Dict[str, Any]) -> str:
    build_num = payload.get("build_num", None)
    if not build_num:
        return super_minimal_body(payload)

    build_url = payload["build_url"]

    outcome = payload["outcome"]
    formatted_status = outcome_to_formatted_status_map.get(outcome, outcome)

    branch_name = payload["branch"]
    workflow_name = payload["workflows"]["workflow_name"]
    job_name = payload["workflows"]["job_name"]

    commit_range_info = get_commit_range_info(payload)
    pull_request_info = ""
    if len(payload["pull_requests"]) > 0:
        pull_request_url = payload["pull_requests"][0]["url"]
        pull_request_info = f"- **Pull Request:** {pull_request_url}"
    authors_and_committers_info = get_authors_and_committer_info(payload)

    body = f"""
Build [#{build_num}]({build_url}) of `{job_name}`/`{workflow_name}` on branch `{branch_name}` {formatted_status}.
{commit_range_info}
{pull_request_info}
{authors_and_committers_info}
""".strip()

    return body
