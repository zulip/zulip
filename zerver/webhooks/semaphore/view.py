# Webhooks for external integrations.
from typing import Any, Dict, List

from urllib.parse import urlparse

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

# Semaphore Classic Templates
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

# Semaphore 2.0 Templates
# There seems to be a possibility of only 3 types of events : Push ,
# Pull request (any push to a pull request) or tag (when a tag is pushed).
# These events can trigger a pipeline.

# As per the Semaphore2.0 documentation, notifications would be sent only when
# a pipeline is triggered.

PUSH_TEMPLATE = """
**[{username}]({profile_url})** pushed to branch **{branch_name}** of \
[{organization_name}/{project_name}]({repository_url}):
* **Commit**: [(#{commit_hash}) {commit_message}]({commit_url})
* **Pipeline**:
  - Name: {pipeline_name}
  - Result: {pipeline_result}
* **Blocks**:
{blocks}
""".strip()

PULL_REQUEST_TEMPLATE = """
**[{username}]({profile_url})** created a pull request to branch **{branch_name}** of \
[{organization_name}/{project_name}]({repository_url}):
* **Pull Request**: [{pull_request_title}]({pull_request_url})
* **Pipeline**:
  - Name: {pipeline_name}
  - Result: {pipeline_result}
* **Blocks**:
{blocks}
""".strip()

TAG_TEMPLATE = """
**[{username}]({profile_url})** pushed a tag to [{organization_name}/{project_name}]\
({repository_url}):
* **Tag**: [{tag_name}]({tag_url})
* **Pipeline**:
  - Name: {pipeline_name}
  - Result: {pipeline_result}
* **Blocks**:
{blocks}
""".strip()

DEFAULT_TEMPLATE = """
An activity occured on branch **{branch_name}** of \
[{organization_name}/{project_name}]({repository_url}):
* **Author**: []{username}]({profile_url})
* **Pipeline**:
  - Name: {pipeline_name}
  - Result: {pipeline_result}
* **Blocks**:
{blocks}
""".strip()

TOPIC_TEMPLATE = "{project}/{branch}"

@api_key_only_webhook_view('Semaphore')
@has_request_variables
def api_semaphore_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    if 'event' in payload.keys():
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
            content = BUILD_TEMPLATE.format(
                build_number=build_number,
                build_url=build_url,
                status=result,
                commit_hash=commit_id[:7],
                commit_message=message,
                commit_url=commit_url,
                email=author_email
            )

        elif event == "deploy":
            build_url = payload["build_html_url"]
            build_number = payload["build_number"]
            deploy_url = payload["html_url"]
            deploy_number = payload["number"]
            server_name = payload["server_name"]
            content = DEPLOY_TEMPLATE.format(
                deploy_number=deploy_number,
                deploy_url=deploy_url,
                build_number=build_number,
                build_url=build_url,
                status=result,
                commit_hash=commit_id[:7],
                commit_message=message,
                commit_url=commit_url,
                email=author_email,
                server_name=server_name
            )

        else:  # should never get here
            content = "{event}: {result}".format(
                event=event, result=result)

    else:
        organization_name = payload["organization"]["name"]
        project_name = payload["project"]["name"]
        repository_url = payload["repository"]["url"]
        pipeline_name = payload["pipeline"]["name"]
        pipeline_result = payload["pipeline"]["result"]
        author_username = payload["revision"]["sender"]["login"]
        profile_url = get_profile_url(author_username, repository_url)
        branch_name = payload["revision"]["branch"]["name"]
        blocks = get_blocks_data(payload["blocks"])

        if payload["revision"]["reference_type"] == "branch":  # push event
            commit_id = payload["revision"]["commit_sha"]
            commit_message = payload["revision"]["commit_message"]
            commit_url = get_commit_url(commit_id, repository_url)
            content = PUSH_TEMPLATE.format(
                username = author_username,
                profile_url = profile_url,
                branch_name = branch_name,
                organization_name = organization_name,
                project_name = project_name,
                repository_url = repository_url,
                commit_hash = commit_id[:7],
                commit_message = commit_message,
                commit_url = commit_url,
                pipeline_name = pipeline_name,
                pipeline_result = pipeline_result,
                blocks = blocks,
            )
        elif payload["revision"]["reference_type"] == "pull-request":
            pull_request_title = payload["revision"]["pull_request"]["name"]
            pull_request_number = payload["revision"]["pull_request"]["number"]
            pull_request_url = get_pr_url(pull_request_number, repository_url)
            content = PULL_REQUEST_TEMPLATE.format(
                username = author_username,
                profile_url = profile_url,
                branch_name = branch_name,
                organization_name = organization_name,
                project_name = project_name,
                repository_url = repository_url,
                pull_request_title = pull_request_title,
                pull_request_url = pull_request_url,
                pipeline_name = pipeline_name,
                pipeline_result = pipeline_result,
                blocks = blocks,
            )
        elif payload["revision"]["reference_type"] == "tag":
            tag_name = payload["revision"]["tag"]["name"]
            tag_url = get_tag_url(tag_name, repository_url)
            content = TAG_TEMPLATE.format(
                username = author_username,
                profile_url = profile_url,
                tag_name = tag_name,
                tag_url = tag_url,
                organization_name = organization_name,
                project_name = project_name,
                repository_url = repository_url,
                pipeline_name = pipeline_name,
                pipeline_result = pipeline_result,
                blocks = blocks,
            )
        else:  # nocoverage # should never get here #unknown Event
            content = DEFAULT_TEMPLATE.format(
                username= author_username,
                profile_url = profile_url,
                branch_name = branch_name,
                organization_name = organization_name,
                project_name = project_name,
                repository_url = repository_url,
                pipeline_name = pipeline_name,
                pipeline_result = pipeline_result,
                blocks = blocks,
            )

    subject = TOPIC_TEMPLATE.format(
        project=project_name,
        branch=branch_name
    )

    check_send_webhook_message(request, user_profile, subject, content)
    return json_success()

#Helper Functions
def get_blocks_data(blocks: List[Dict[str, Any]]) -> str:
    """
        Returns the markdown presentation of data related to blocks.
    """
    BLOCKS_DATA = """"""
    BLOCK_BODY = """  1. **{name}**:
    - Result: {result}
"""
    for block in blocks:
        name = block["name"].title()
        result = block["result"]
        content = BLOCK_BODY.format(name=name, result=result)
        BLOCKS_DATA += content
    return BLOCKS_DATA

def get_commit_url(commit_id: str, repo_url: str) -> str:
    """
        Returns the url of a particular commit using the commit_id and
        repository url.
    """
    repository_hosting_services = {
        "github.com": repo_url + '/commit/' + commit_id
    }
    # New hosting services must be added when semaphore extends it support.

    parsed_url = urlparse(repo_url)

    if parsed_url.hostname in repository_hosting_services:
        return repository_hosting_services[parsed_url.hostname]
    else:
        return repo_url

def get_pr_url(pr_number: int, repo_url: str) -> str:
    """
        Returns the url of a pull request using the pull request number and
        repository url.
    """
    repository_hosting_services = {
        "github.com": repo_url + '/pull/' + str(pr_number)
    }
    # New hosting services must be added when semaphore extends it support.

    parsed_url = urlparse(repo_url)

    if parsed_url.hostname in repository_hosting_services:
        return repository_hosting_services[parsed_url.hostname]
    else:
        return repo_url

def get_tag_url(tag_name: str, repo_url: str) -> str:
    """
        Returns the url of a tag using tag name and repository url.
    """
    repository_hosting_services = {
        "github.com": repo_url + '/releases/tag/' + str(tag_name)
    }
    # New hosting services must be added when semaphore extends it support.

    parsed_url = urlparse(repo_url)

    if parsed_url.hostname in repository_hosting_services:
        return repository_hosting_services[parsed_url.hostname]
    else:
        return repo_url

def get_profile_url(username: str, repo_url: str) -> str:
    """
        Returns the profile url of the author using username and
        repository url.
    """
    repository_hosting_services = {
        "github.com": 'https://github.com/' + username
    }
    # New hosting services must be added when semaphore extends it support.

    parsed_url = urlparse(repo_url)

    if parsed_url.hostname in repository_hosting_services:
        return repository_hosting_services[parsed_url.hostname]
    else:
        return repo_url
