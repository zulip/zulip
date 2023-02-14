# Webhooks for external integrations.
from typing import Optional, Tuple
from urllib.parse import urlparse

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_int, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import get_short_sha
from zerver.models import UserProfile

# Semaphore Classic templates

BUILD_TEMPLATE = """
[Build {build_number}]({build_url}) {status}:
* **Commit**: [{commit_hash}: {commit_message}]({commit_url})
* **Author**: {email}
""".strip()

DEPLOY_TEMPLATE = """
[Deploy {deploy_number}]({deploy_url}) of [build {build_number}]({build_url}) {status}:
* **Commit**: [{commit_hash}: {commit_message}]({commit_url})
* **Author**: {email}
* **Server**: {server_name}
""".strip()

# Semaphore 2.0 templates

# Currently, Semaphore 2.0 only supports GitHub, while Semaphore Classic
# supports Bitbucket too. The payload does not have URLs for commits, tags,
# pull requests, etc. So, we use separate templates for GitHub and construct
# the URLs ourselves. For any other repository hosting services we use
# templates that don't have any links in them.

GH_PUSH_TEMPLATE = """
[{pipeline_name}]({workflow_url}) pipeline **{pipeline_result}**:
* **Commit**: [({commit_hash})]({commit_url}) {commit_message}
* **Branch**: {branch_name}
* **Author**: [{author_name}]({author_url})
""".strip()

PUSH_TEMPLATE = """
[{pipeline_name}]({workflow_url}) pipeline **{pipeline_result}**:
* **Commit**: ({commit_hash}) {commit_message}
* **Branch**: {branch_name}
* **Author**: {author_name}
""".strip()

GH_PULL_REQUEST_TEMPLATE = """
[{pipeline_name}]({workflow_url}) pipeline **{pipeline_result}**:
* **Pull request**: [{pull_request_title}]({pull_request_url})
* **Branch**: {branch_name}
* **Author**: [{author_name}]({author_url})
""".strip()

PULL_REQUEST_TEMPLATE = """
[{pipeline_name}]({workflow_url}) pipeline **{pipeline_result}**:
* **Pull request**: {pull_request_title} (#{pull_request_number})
* **Branch**: {branch_name}
* **Author**: {author_name}
""".strip()

GH_TAG_TEMPLATE = """
[{pipeline_name}]({workflow_url}) pipeline **{pipeline_result}**:
* **Tag**: [{tag_name}]({tag_url})
* **Author**: [{author_name}]({author_url})
""".strip()

TAG_TEMPLATE = """
[{pipeline_name}]({workflow_url}) pipeline **{pipeline_result}**:
* **Tag**: {tag_name}
* **Author**: {author_name}
""".strip()

DEFAULT_TEMPLATE = """
[{pipeline_name}]({workflow_url}) pipeline **{pipeline_result}** for {event_name} event
""".strip()

TOPIC_TEMPLATE = "{project}/{branch}"

GITHUB_URL_TEMPLATES = {
    "commit": "{repo_url}/commit/{commit_id}",
    "pull_request": "{repo_url}/pull/{pr_number}",
    "tag": "{repo_url}/tree/{tag_name}",
    "user": "https://github.com/{username}",
}

ALL_EVENT_TYPES = ["build", "tag", "unknown", "branch", "deploy", "pull_request"]


@webhook_view("Semaphore", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_semaphore_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    content, project_name, branch_name, event = (
        semaphore_classic(payload) if "event" in payload else semaphore_2(payload)
    )
    subject = (
        TOPIC_TEMPLATE.format(project=project_name, branch=branch_name)
        if branch_name
        else project_name
    )
    check_send_webhook_message(request, user_profile, subject, content, event)
    return json_success(request)


def semaphore_classic(payload: WildValue) -> Tuple[str, str, str, str]:
    # semaphore only gives the last commit, even if there were multiple commits
    # since the last build
    branch_name = payload["branch_name"].tame(check_string)
    project_name = payload["project_name"].tame(check_string)
    result = payload["result"].tame(check_string)
    event = payload["event"].tame(check_string)
    commit_id = payload["commit"]["id"].tame(check_string)
    commit_url = payload["commit"]["url"].tame(check_string)
    author_email = payload["commit"]["author_email"].tame(check_string)
    message = summary_line(payload["commit"]["message"].tame(check_string))

    if event == "build":
        build_url = payload["build_url"].tame(check_string)
        build_number = payload["build_number"].tame(check_int)
        content = BUILD_TEMPLATE.format(
            build_number=build_number,
            build_url=build_url,
            status=result,
            commit_hash=get_short_sha(commit_id),
            commit_message=message,
            commit_url=commit_url,
            email=author_email,
        )

    elif event == "deploy":
        build_url = payload["build_html_url"].tame(check_string)
        build_number = payload["build_number"].tame(check_int)
        deploy_url = payload["html_url"].tame(check_string)
        deploy_number = payload["number"].tame(check_int)
        server_name = payload["server_name"].tame(check_string)
        content = DEPLOY_TEMPLATE.format(
            deploy_number=deploy_number,
            deploy_url=deploy_url,
            build_number=build_number,
            build_url=build_url,
            status=result,
            commit_hash=get_short_sha(commit_id),
            commit_message=message,
            commit_url=commit_url,
            email=author_email,
            server_name=server_name,
        )

    else:  # should never get here
        content = f"{event}: {result}"

    return content, project_name, branch_name, event


def semaphore_2(payload: WildValue) -> Tuple[str, str, Optional[str], str]:
    repo_url = payload["repository"]["url"].tame(check_string)
    project_name = payload["project"]["name"].tame(check_string)
    organization_name = payload["organization"]["name"].tame(check_string)
    author_name = payload["revision"]["sender"]["login"].tame(check_string)
    workflow_id = payload["workflow"]["id"].tame(check_string)
    context = dict(
        author_name=author_name,
        author_url=GITHUB_URL_TEMPLATES["user"].format(repo_url=repo_url, username=author_name),
        pipeline_name=payload["pipeline"]["name"].tame(check_string),
        pipeline_result=payload["pipeline"]["result"].tame(check_string),
        workflow_url=f"https://{organization_name}.semaphoreci.com/workflows/{workflow_id}",
    )
    event = payload["revision"]["reference_type"].tame(check_string)

    if event == "branch":  # push event
        commit_id = payload["revision"]["commit_sha"].tame(check_string)
        branch_name = payload["revision"]["branch"]["name"].tame(check_string)
        context.update(
            branch_name=branch_name,
            commit_id=commit_id,
            commit_hash=get_short_sha(commit_id),
            commit_message=summary_line(payload["revision"]["commit_message"].tame(check_string)),
            commit_url=GITHUB_URL_TEMPLATES["commit"].format(
                repo_url=repo_url, commit_id=commit_id
            ),
        )
        template = GH_PUSH_TEMPLATE if is_github_repo(repo_url) else PUSH_TEMPLATE
        content = template.format(**context)
    elif event == "pull_request":
        pull_request = payload["revision"]["pull_request"]
        branch_name = pull_request["branch_name"].tame(check_string)
        pull_request_title = pull_request["name"].tame(check_string)
        pull_request_number = pull_request["number"].tame(check_string)
        pull_request_url = GITHUB_URL_TEMPLATES["pull_request"].format(
            repo_url=repo_url, pr_number=pull_request_number
        )
        context.update(
            branch_name=branch_name,
            pull_request_title=pull_request_title,
            pull_request_url=pull_request_url,
            pull_request_number=pull_request_number,
        )
        template = GH_PULL_REQUEST_TEMPLATE if is_github_repo(repo_url) else PULL_REQUEST_TEMPLATE
        content = template.format(**context)
    elif event == "tag":
        branch_name = ""
        tag_name = payload["revision"]["tag"]["name"].tame(check_string)
        tag_url = GITHUB_URL_TEMPLATES["tag"].format(repo_url=repo_url, tag_name=tag_name)
        context.update(
            tag_name=tag_name,
            tag_url=tag_url,
        )
        template = GH_TAG_TEMPLATE if is_github_repo(repo_url) else TAG_TEMPLATE
        content = template.format(**context)
    else:  # should never get here: unknown event
        branch_name = ""
        context.update(event_name=event)
        content = DEFAULT_TEMPLATE.format(**context)
    return content, project_name, branch_name, event


def is_github_repo(repo_url: str) -> bool:
    return urlparse(repo_url).hostname == "github.com"


def summary_line(message: str) -> str:
    return message.splitlines()[0]
