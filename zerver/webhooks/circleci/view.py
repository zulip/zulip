from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_int, check_none_or, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

outcome_to_formatted_status_map = {
    "success": "has succeeded",
    "failed": "has failed",
    "canceled": "was canceled",
}

ALL_EVENT_TYPES = list(outcome_to_formatted_status_map.keys())


@webhook_view("CircleCI", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_circleci_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    payload = payload["payload"]
    subject = get_subject(payload)
    body = get_body(payload)

    check_send_webhook_message(
        request,
        user_profile,
        subject,
        body,
        payload["status"].tame(check_string)
        if "build_num" not in payload
        else payload["outcome"].tame(check_string),
    )
    return json_success(request)


def get_subject(payload: WildValue) -> str:
    return payload["reponame"].tame(check_string)


def get_commit_range_info(payload: WildValue) -> str:
    commits = payload["all_commit_details"]
    num_commits = len(commits)

    if num_commits == 1:
        commit_id = commits[0]["commit"].tame(check_string)[:10]
        commit_url = commits[0]["commit_url"].tame(check_string)
        return f"- **Commit:** [{commit_id}]({commit_url})"

    vcs_provider = payload["user"]["vcs_type"].tame(check_string)  # Same as payload["why"]?
    first_commit_id = commits[0]["commit"].tame(check_string)
    shortened_first_commit_id = first_commit_id[:10]
    last_commit_id = commits[-1]["commit"].tame(check_string)
    shortened_last_commit_id = last_commit_id[:10]
    if vcs_provider == "github":
        # Then use GitHub's commit range feature to form the appropriate url.
        vcs_url = payload["vcs_url"].tame(check_string)
        commit_range_url = f"{vcs_url}/compare/{first_commit_id}...{last_commit_id}"
        return f"- **Commits ({num_commits}):** [{shortened_first_commit_id} ... {shortened_last_commit_id}]({commit_range_url})"
    else:
        # Bitbucket doesn't have a good commit range URL feature like GitHub does.
        # So let's just show the two separately.
        # https://community.atlassian.com/t5/Bitbucket-questions/BitBucket-4-14-diff-between-any-two-commits/qaq-p/632974
        first_commit_url = commits[0]["commit_url"].tame(check_string)
        last_commit_url = commits[-1]["commit_url"].tame(check_string)
        return f"- **Commits ({num_commits}):** [{shortened_first_commit_id}]({first_commit_url}) ... [{shortened_last_commit_id}]({last_commit_url})"


def get_authors_and_committer_info(payload: WildValue) -> str:
    body = ""

    author_names = set()
    committer_names = set()
    for commit in payload["all_commit_details"]:
        author_name = commit["author_name"].tame(check_string)
        author_username = commit["author_login"].tame(check_none_or(check_string))
        if author_username is not None:
            author_names.add(f"{author_name} ({author_username})")
        else:
            author_names.add(author_name)

        if commit["committer_email"].tame(check_none_or(check_string)) is not None:
            committer_name = commit["committer_name"].tame(check_string)
            committer_username = commit["committer_login"].tame(check_none_or(check_string))
            if committer_username is not None:
                committer_names.add(f"{committer_name} ({committer_username})")
            else:
                committer_names.add(committer_name)

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


def super_minimal_body(payload: WildValue) -> str:
    branch_name = payload["branch"].tame(check_string)
    status = payload["status"].tame(check_string)
    formatted_status = outcome_to_formatted_status_map.get(status, status)
    build_url = payload["build_url"].tame(check_string)
    username = payload["username"].tame(check_string)
    return f"[Build]({build_url}) triggered by {username} on branch `{branch_name}` {formatted_status}."


def get_body(payload: WildValue) -> str:
    if "build_num" not in payload:
        return super_minimal_body(payload)

    build_num = payload["build_num"].tame(check_int)
    build_url = payload["build_url"].tame(check_string)

    outcome = payload["outcome"].tame(check_string)
    formatted_status = outcome_to_formatted_status_map.get(outcome, outcome)

    branch_name = payload["branch"].tame(check_string)
    workflow_name = payload["workflows"]["workflow_name"].tame(check_string)
    job_name = payload["workflows"]["job_name"].tame(check_string)

    commit_range_info = get_commit_range_info(payload)
    pull_request_info = ""
    if len(payload["pull_requests"]) > 0:
        pull_request_url = payload["pull_requests"][0]["url"].tame(check_string)
        pull_request_info = f"- **Pull request:** {pull_request_url}"
    authors_and_committers_info = get_authors_and_committer_info(payload)

    body = f"""
Build [#{build_num}]({build_url}) of `{job_name}`/`{workflow_name}` on branch `{branch_name}` {formatted_status}.
{commit_range_info}
{pull_request_info}
{authors_and_committers_info}
""".strip()

    return body
