import re
from functools import partial
from inspect import signature
from typing import Any, Dict, List, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_bool
from zerver.lib.webhooks.common import (
    check_send_webhook_message,
    validate_extract_webhook_http_header,
)
from zerver.lib.webhooks.git import (
    EMPTY_SHA,
    TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE,
    get_commits_comment_action_message,
    get_issue_event_message,
    get_pull_request_event_message,
    get_push_commits_event_message,
    get_push_tag_event_message,
    get_remove_branch_event_message,
)
from zerver.models import UserProfile


def fixture_to_headers(fixture_name: str) -> Dict[str, Any]:
    if fixture_name.startswith("build"):
        return {}  # Since there are 2 possible event types.

    # Map "push_hook__push_commits_more_than_limit.json" into GitLab's
    # HTTP event title "Push Hook".
    return {"HTTP_X_GITLAB_EVENT": fixture_name.split("__")[0].replace("_", " ").title()}

def get_push_event_body(payload: Dict[str, Any]) -> str:
    if payload.get('after') == EMPTY_SHA:
        return get_remove_branch_event_body(payload)
    return get_normal_push_event_body(payload)

def get_normal_push_event_body(payload: Dict[str, Any]) -> str:
    compare_url = '{}/compare/{}...{}'.format(
        get_project_homepage(payload),
        payload['before'],
        payload['after'],
    )

    commits = [
        {
            'name': commit.get('author').get('name'),
            'sha': commit.get('id'),
            'message': commit.get('message'),
            'url': commit.get('url'),
        }
        for commit in payload['commits']
    ]

    return get_push_commits_event_message(
        get_user_name(payload),
        compare_url,
        get_branch_name(payload),
        commits,
    )

def get_remove_branch_event_body(payload: Dict[str, Any]) -> str:
    return get_remove_branch_event_message(
        get_user_name(payload),
        get_branch_name(payload),
    )

def get_tag_push_event_body(payload: Dict[str, Any]) -> str:
    return get_push_tag_event_message(
        get_user_name(payload),
        get_tag_name(payload),
        action="pushed" if payload.get('checkout_sha') else "removed",
    )

def get_issue_created_event_body(payload: Dict[str, Any],
                                 include_title: bool=False) -> str:
    description = payload['object_attributes'].get('description')
    # Filter out multiline hidden comments
    if description is not None:
        description = re.sub('<!--.*?-->', '', description, 0, re.DOTALL)
        description = description.rstrip()

    return get_issue_event_message(
        get_issue_user_name(payload),
        'created',
        get_object_url(payload),
        payload['object_attributes'].get('iid'),
        description,
        assignees=replace_assignees_username_with_name(get_assignees(payload)),
        title=payload['object_attributes'].get('title') if include_title else None,
    )

def get_issue_event_body(payload: Dict[str, Any], action: str,
                         include_title: bool=False) -> str:
    return get_issue_event_message(
        get_issue_user_name(payload),
        action,
        get_object_url(payload),
        payload['object_attributes'].get('iid'),
        title=payload['object_attributes'].get('title') if include_title else None,
    )

def get_merge_request_updated_event_body(payload: Dict[str, Any],
                                         include_title: bool=False) -> str:
    if payload['object_attributes'].get('oldrev'):
        return get_merge_request_event_body(
            payload, "added commit(s) to",
            include_title=include_title,
        )

    return get_merge_request_open_or_updated_body(
        payload, "updated",
        include_title=include_title,
    )

def get_merge_request_event_body(payload: Dict[str, Any], action: str,
                                 include_title: bool=False) -> str:
    pull_request = payload['object_attributes']
    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        pull_request.get('url'),
        pull_request.get('iid'),
        type='MR',
        title=payload['object_attributes'].get('title') if include_title else None,
    )

def get_merge_request_open_or_updated_body(payload: Dict[str, Any], action: str,
                                           include_title: bool=False) -> str:
    pull_request = payload['object_attributes']
    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        pull_request.get('url'),
        pull_request.get('iid'),
        pull_request.get('source_branch'),
        pull_request.get('target_branch'),
        pull_request.get('description'),
        assignees=replace_assignees_username_with_name(get_assignees(payload)),
        type='MR',
        title=payload['object_attributes'].get('title') if include_title else None,
    )

def get_assignees(payload: Dict[str, Any]) -> List[Dict[str, str]]:
    assignee_details = payload.get('assignees')
    if assignee_details is None:
        single_assignee_details = payload.get('assignee')
        if single_assignee_details is None:
            assignee_details = []
        else:
            assignee_details = [single_assignee_details]
    return assignee_details

def replace_assignees_username_with_name(assignees: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Replace the username of each assignee with their (full) name.

    This is a hack-like adaptor so that when assignees are passed to
    `get_pull_request_event_message` we can use the assignee's name
    and not their username (for more consistency).
    """
    for assignee in assignees:
        assignee["username"] = assignee["name"]
    return assignees

def get_commented_commit_event_body(payload: Dict[str, Any]) -> str:
    comment = payload['object_attributes']
    action = '[commented]({})'.format(comment['url'])
    return get_commits_comment_action_message(
        get_issue_user_name(payload),
        action,
        payload['commit'].get('url'),
        payload['commit'].get('id'),
        comment['note'],
    )

def get_commented_merge_request_event_body(payload: Dict[str, Any],
                                           include_title: bool=False) -> str:
    comment = payload['object_attributes']
    action = '[commented]({}) on'.format(comment['url'])
    url = '{}/merge_requests/{}'.format(
        payload['project'].get('web_url'),
        payload['merge_request'].get('iid'),
    )

    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        url,
        payload['merge_request'].get('iid'),
        message=comment['note'],
        type='MR',
        title=payload['merge_request'].get('title') if include_title else None,
    )

def get_commented_issue_event_body(payload: Dict[str, Any],
                                   include_title: bool=False) -> str:
    comment = payload['object_attributes']
    action = '[commented]({}) on'.format(comment['url'])
    url = '{}/issues/{}'.format(
        payload['project'].get('web_url'),
        payload['issue'].get('iid'),
    )

    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        url,
        payload['issue'].get('iid'),
        message=comment['note'],
        type='Issue',
        title=payload['issue'].get('title') if include_title else None,
    )

def get_commented_snippet_event_body(payload: Dict[str, Any],
                                     include_title: bool=False) -> str:
    comment = payload['object_attributes']
    action = '[commented]({}) on'.format(comment['url'])
    url = '{}/snippets/{}'.format(
        payload['project'].get('web_url'),
        payload['snippet'].get('id'),
    )

    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        url,
        payload['snippet'].get('id'),
        message=comment['note'],
        type='Snippet',
        title=payload['snippet'].get('title') if include_title else None,
    )

def get_wiki_page_event_body(payload: Dict[str, Any], action: str) -> str:
    return "{} {} [Wiki Page \"{}\"]({}).".format(
        get_issue_user_name(payload),
        action,
        payload['object_attributes'].get('title'),
        payload['object_attributes'].get('url'),
    )

def get_build_hook_event_body(payload: Dict[str, Any]) -> str:
    build_status = payload.get('build_status')
    if build_status == 'created':
        action = 'was created'
    elif build_status == 'running':
        action = 'started'
    else:
        action = f'changed status to {build_status}'
    return "Build {} from {} stage {}.".format(
        payload.get('build_name'),
        payload.get('build_stage'),
        action,
    )

def get_test_event_body(payload: Dict[str, Any]) -> str:
    return f"Webhook for **{get_repo_name(payload)}** has been configured successfully! :tada:"

def get_pipeline_event_body(payload: Dict[str, Any]) -> str:
    pipeline_status = payload['object_attributes'].get('status')
    if pipeline_status == 'pending':
        action = 'was created'
    elif pipeline_status == 'running':
        action = 'started'
    else:
        action = f'changed status to {pipeline_status}'

    project_homepage = get_project_homepage(payload)
    pipeline_url = '{}/pipelines/{}'.format(
        project_homepage,
        payload['object_attributes'].get('id'),
    )

    builds_status = ""
    for build in payload['builds']:
        build_url = '{}/-/jobs/{}'.format(
            project_homepage,
            build.get('id'),
        )
        artifact_filename = build.get('artifacts_file', {}).get('filename', None)
        if artifact_filename:
            artifact_download_url = f'{build_url}/artifacts/download'
            artifact_browse_url = f'{build_url}/artifacts/browse'
            artifact_string = f'  * built artifact: *{artifact_filename}* [[Browse]({artifact_browse_url})|[Download]({artifact_download_url})]\n'
        else:
            artifact_string = ''
        builds_status += "* [{}]({}) - {}\n{}".format(
            build.get('name'),
            build_url,
            build.get('status'),
            artifact_string,
        )
    return "[Pipeline ({})]({}) {} with build(s):\n{}.".format(
        payload['object_attributes'].get('id'),
        pipeline_url,
        action,
        builds_status[:-1],
    )

def get_repo_name(payload: Dict[str, Any]) -> str:
    if 'project' in payload:
        return payload['project']['name']

    # Apparently, Job Hook payloads don't have a `project` section,
    # but the repository name is accessible from the `repository`
    # section.
    return payload['repository']['name']

def get_user_name(payload: Dict[str, Any]) -> str:
    return payload['user_name']

def get_issue_user_name(payload: Dict[str, Any]) -> str:
    return payload['user']['name']

def get_project_homepage(payload: Dict[str, Any]) -> str:
    if 'project' in payload:
        return payload['project']['web_url']
    return payload['repository']['homepage']

def get_branch_name(payload: Dict[str, Any]) -> str:
    return payload['ref'].replace('refs/heads/', '')

def get_tag_name(payload: Dict[str, Any]) -> str:
    return payload['ref'].replace('refs/tags/', '')

def get_object_url(payload: Dict[str, Any]) -> str:
    return payload['object_attributes']['url']

EVENT_FUNCTION_MAPPER = {
    'Push Hook': get_push_event_body,
    'Tag Push Hook': get_tag_push_event_body,
    'Test Hook': get_test_event_body,
    'Issue Hook open': get_issue_created_event_body,
    'Issue Hook close': partial(get_issue_event_body, action='closed'),
    'Issue Hook reopen': partial(get_issue_event_body, action='reopened'),
    'Issue Hook update': partial(get_issue_event_body, action='updated'),
    'Confidential Issue Hook open': get_issue_created_event_body,
    'Confidential Issue Hook close': partial(get_issue_event_body, action='closed'),
    'Confidential Issue Hook reopen': partial(get_issue_event_body, action='reopened'),
    'Confidential Issue Hook update': partial(get_issue_event_body, action='updated'),
    'Note Hook Commit': get_commented_commit_event_body,
    'Note Hook MergeRequest': get_commented_merge_request_event_body,
    'Note Hook Issue': get_commented_issue_event_body,
    'Confidential Note Hook Issue': get_commented_issue_event_body,
    'Note Hook Snippet': get_commented_snippet_event_body,
    'Merge Request Hook approved': partial(get_merge_request_event_body, action='approved'),
    'Merge Request Hook unapproved': partial(get_merge_request_event_body, action='unapproved'),
    'Merge Request Hook open': partial(get_merge_request_open_or_updated_body, action='created'),
    'Merge Request Hook update': get_merge_request_updated_event_body,
    'Merge Request Hook merge': partial(get_merge_request_event_body, action='merged'),
    'Merge Request Hook close': partial(get_merge_request_event_body, action='closed'),
    'Merge Request Hook reopen': partial(get_merge_request_event_body, action='reopened'),
    'Wiki Page Hook create': partial(get_wiki_page_event_body, action='created'),
    'Wiki Page Hook update': partial(get_wiki_page_event_body, action='updated'),
    'Job Hook': get_build_hook_event_body,
    'Build Hook': get_build_hook_event_body,
    'Pipeline Hook': get_pipeline_event_body,
}

@webhook_view("GitLab")
@has_request_variables
def api_gitlab_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any]=REQ(argument_type='body'),
                       branches: Optional[str]=REQ(default=None),
                       use_merge_request_title: bool=REQ(default=True, validator=check_bool),
                       user_specified_topic: Optional[str]=REQ("topic", default=None)) -> HttpResponse:
    event = get_event(request, payload, branches)
    if event is not None:
        event_body_function = get_body_based_on_event(event)
        if 'include_title' in signature(event_body_function).parameters:
            body = event_body_function(
                payload,
                include_title=user_specified_topic is not None,
            )
        else:
            body = event_body_function(payload)

        # Add a link to the project if a custom topic is set
        if user_specified_topic:
            project_url = f"[{get_repo_name(payload)}]({get_project_homepage(payload)})"
            body = f"[{project_url}] {body}"

        topic = get_subject_based_on_event(event, payload, use_merge_request_title)
        check_send_webhook_message(request, user_profile, topic, body)
    return json_success()

def get_body_based_on_event(event: str) -> Any:
    return EVENT_FUNCTION_MAPPER[event]

def get_subject_based_on_event(event: str, payload: Dict[str, Any], use_merge_request_title: bool) -> str:
    if event == 'Push Hook':
        return f"{get_repo_name(payload)} / {get_branch_name(payload)}"
    elif event == 'Job Hook' or event == 'Build Hook':
        return "{} / {}".format(payload['repository'].get('name'), get_branch_name(payload))
    elif event == 'Pipeline Hook':
        return "{} / {}".format(
            get_repo_name(payload),
            payload['object_attributes'].get('ref').replace('refs/heads/', ''))
    elif event.startswith('Merge Request Hook'):
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='MR',
            id=payload['object_attributes'].get('iid'),
            title=payload['object_attributes'].get('title') if use_merge_request_title else "",
        )
    elif event.startswith('Issue Hook') or event.startswith('Confidential Issue Hook'):
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='Issue',
            id=payload['object_attributes'].get('iid'),
            title=payload['object_attributes'].get('title'),
        )
    elif event == 'Note Hook Issue' or event == 'Confidential Note Hook Issue':
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='Issue',
            id=payload['issue'].get('iid'),
            title=payload['issue'].get('title'),
        )
    elif event == 'Note Hook MergeRequest':
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='MR',
            id=payload['merge_request'].get('iid'),
            title=payload['merge_request'].get('title') if use_merge_request_title else "",
        )

    elif event == 'Note Hook Snippet':
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='Snippet',
            id=payload['snippet'].get('id'),
            title=payload['snippet'].get('title'),
        )
    return get_repo_name(payload)

def get_event(request: HttpRequest, payload: Dict[str, Any], branches: Optional[str]) -> Optional[str]:
    event = validate_extract_webhook_http_header(request, 'X_GITLAB_EVENT', 'GitLab')
    if event == "System Hook":
        # Convert the event name to a GitLab event title
        event_name = payload.get('event_name', payload.get('object_kind'))
        event = event_name.split("__")[0].replace("_", " ").title()
        event = f"{event} Hook"
    if event in ['Confidential Issue Hook', 'Issue Hook', 'Merge Request Hook', 'Wiki Page Hook']:
        action = payload['object_attributes'].get('action', 'open')
        event = f"{event} {action}"
    elif event in ['Confidential Note Hook', 'Note Hook']:
        action = payload['object_attributes'].get('noteable_type')
        event = f"{event} {action}"
    elif event == 'Push Hook':
        if branches is not None:
            branch = get_branch_name(payload)
            if branches.find(branch) == -1:
                return None

    if event in list(EVENT_FUNCTION_MAPPER.keys()):
        return event

    raise UnsupportedWebhookEventType(event)
