from functools import partial
from typing import Any, Dict, Optional
from inspect import signature
import re

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message, \
    validate_extract_webhook_http_header, UnexpectedWebhookEventType
from zerver.lib.webhooks.git import EMPTY_SHA, \
    TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE, \
    get_commits_comment_action_message, get_issue_event_message, \
    get_pull_request_event_message, get_push_commits_event_message, \
    get_push_tag_event_message, get_remove_branch_event_message
from zerver.models import UserProfile


def get_push_event_body(payload: Dict[str, Any]) -> str:
    if payload.get('after') == EMPTY_SHA:
        return get_remove_branch_event_body(payload)
    return get_normal_push_event_body(payload)

def get_normal_push_event_body(payload: Dict[str, Any]) -> str:
    compare_url = u'{}/compare/{}...{}'.format(
        get_repository_homepage(payload),
        payload['before'],
        payload['after']
    )

    commits = [
        {
            'name': commit.get('author').get('name'),
            'sha': commit.get('id'),
            'message': commit.get('message'),
            'url': commit.get('url')
        }
        for commit in payload['commits']
    ]

    return get_push_commits_event_message(
        get_user_name(payload),
        compare_url,
        get_branch_name(payload),
        commits
    )

def get_remove_branch_event_body(payload: Dict[str, Any]) -> str:
    return get_remove_branch_event_message(
        get_user_name(payload),
        get_branch_name(payload)
    )

def get_tag_push_event_body(payload: Dict[str, Any]) -> str:
    return get_push_tag_event_message(
        get_user_name(payload),
        get_tag_name(payload),
        action="pushed" if payload.get('checkout_sha') else "removed"
    )

def get_issue_created_event_body(payload: Dict[str, Any],
                                 include_title: Optional[bool]=False) -> str:
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
        get_objects_assignee(payload),
        payload.get('assignees'),
        title=payload['object_attributes'].get('title') if include_title else None
    )

def get_issue_event_body(payload: Dict[str, Any], action: str,
                         include_title: Optional[bool]=False) -> str:
    return get_issue_event_message(
        get_issue_user_name(payload),
        action,
        get_object_url(payload),
        payload['object_attributes'].get('iid'),
        title=payload['object_attributes'].get('title') if include_title else None
    )

def get_merge_request_updated_event_body(payload: Dict[str, Any],
                                         include_title: Optional[bool]=False) -> str:
    if payload['object_attributes'].get('oldrev'):
        return get_merge_request_event_body(
            payload, "added commit(s) to",
            include_title=include_title
        )

    return get_merge_request_open_or_updated_body(
        payload, "updated",
        include_title=include_title
    )

def get_merge_request_event_body(payload: Dict[str, Any], action: str,
                                 include_title: Optional[bool]=False) -> str:
    pull_request = payload['object_attributes']
    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        pull_request.get('url'),
        pull_request.get('iid'),
        type='MR',
        title=payload['object_attributes'].get('title') if include_title else None
    )

def get_merge_request_open_or_updated_body(payload: Dict[str, Any], action: str,
                                           include_title: Optional[bool]=False) -> str:
    pull_request = payload['object_attributes']
    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        pull_request.get('url'),
        pull_request.get('iid'),
        pull_request.get('source_branch'),
        pull_request.get('target_branch'),
        pull_request.get('description'),
        get_objects_assignee(payload),
        type='MR',
        title=payload['object_attributes'].get('title') if include_title else None
    )

def get_objects_assignee(payload: Dict[str, Any]) -> Optional[str]:
    assignee_object = payload.get('assignee')
    if assignee_object:
        return assignee_object.get('name')
    else:
        assignee_object = payload.get('assignees')
        if assignee_object:
            for assignee in payload.get('assignees'):
                return assignee['name']

    return None

def get_commented_commit_event_body(payload: Dict[str, Any]) -> str:
    comment = payload['object_attributes']
    action = u'[commented]({})'.format(comment['url'])
    return get_commits_comment_action_message(
        get_issue_user_name(payload),
        action,
        payload['commit'].get('url'),
        payload['commit'].get('id'),
        comment['note'],
    )

def get_commented_merge_request_event_body(payload: Dict[str, Any],
                                           include_title: Optional[bool]=False) -> str:
    comment = payload['object_attributes']
    action = u'[commented]({}) on'.format(comment['url'])
    url = u'{}/merge_requests/{}'.format(
        payload['project'].get('web_url'),
        payload['merge_request'].get('iid')
    )

    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        url,
        payload['merge_request'].get('iid'),
        message=comment['note'],
        type='MR',
        title=payload.get('merge_request').get('title') if include_title else None
    )

def get_commented_issue_event_body(payload: Dict[str, Any],
                                   include_title: Optional[bool]=False) -> str:
    comment = payload['object_attributes']
    action = u'[commented]({}) on'.format(comment['url'])
    url = u'{}/issues/{}'.format(
        payload['project'].get('web_url'),
        payload['issue'].get('iid')
    )

    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        url,
        payload['issue'].get('iid'),
        message=comment['note'],
        type='Issue',
        title=payload.get('issue').get('title') if include_title else None
    )

def get_commented_snippet_event_body(payload: Dict[str, Any],
                                     include_title: Optional[bool]=False) -> str:
    comment = payload['object_attributes']
    action = u'[commented]({}) on'.format(comment['url'])
    url = u'{}/snippets/{}'.format(
        payload['project'].get('web_url'),
        payload['snippet'].get('id')
    )

    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        url,
        payload['snippet'].get('id'),
        message=comment['note'],
        type='Snippet',
        title=payload.get('snippet').get('title') if include_title else None
    )

def get_wiki_page_event_body(payload: Dict[str, Any], action: str) -> str:
    return u"{} {} [Wiki Page \"{}\"]({}).".format(
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
        action = 'changed status to {}'.format(build_status)
    return u"Build {} from {} stage {}.".format(
        payload.get('build_name'),
        payload.get('build_stage'),
        action
    )

def get_test_event_body(payload: Dict[str, Any]) -> str:
    return u"Webhook for **{repo}** has been configured successfully! :tada:".format(
        repo=get_repo_name(payload))

def get_pipeline_event_body(payload: Dict[str, Any]) -> str:
    pipeline_status = payload['object_attributes'].get('status')
    if pipeline_status == 'pending':
        action = 'was created'
    elif pipeline_status == 'running':
        action = 'started'
    else:
        action = 'changed status to {}'.format(pipeline_status)

    builds_status = u""
    for build in payload['builds']:
        builds_status += u"* {} - {}\n".format(build.get('name'), build.get('status'))
    return u"Pipeline {} with build(s):\n{}.".format(action, builds_status[:-1])

def get_repo_name(payload: Dict[str, Any]) -> str:
    return payload['project']['name']

def get_user_name(payload: Dict[str, Any]) -> str:
    return payload['user_name']

def get_issue_user_name(payload: Dict[str, Any]) -> str:
    return payload['user']['name']

def get_repository_homepage(payload: Dict[str, Any]) -> str:
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

@api_key_only_webhook_view("Gitlab")
@has_request_variables
def api_gitlab_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any]=REQ(argument_type='body'),
                       branches: Optional[str]=REQ(default=None),
                       user_specified_topic: Optional[str]=REQ("topic", default=None)) -> HttpResponse:
    event = get_event(request, payload, branches)
    if event is not None:
        event_body_function = get_body_based_on_event(event)
        if 'include_title' in signature(event_body_function).parameters:
            body = event_body_function(
                payload,
                include_title=user_specified_topic is not None
            )
        else:
            body = event_body_function(payload)

        topic = get_subject_based_on_event(event, payload)
        check_send_webhook_message(request, user_profile, topic, body)
    return json_success()

def get_body_based_on_event(event: str) -> Any:
    return EVENT_FUNCTION_MAPPER[event]

def get_subject_based_on_event(event: str, payload: Dict[str, Any]) -> str:
    if event == 'Push Hook':
        return u"{} / {}".format(get_repo_name(payload), get_branch_name(payload))
    elif event == 'Job Hook' or event == 'Build Hook':
        return u"{} / {}".format(payload['repository'].get('name'), get_branch_name(payload))
    elif event == 'Pipeline Hook':
        return u"{} / {}".format(
            get_repo_name(payload),
            payload['object_attributes'].get('ref').replace('refs/heads/', ''))
    elif event.startswith('Merge Request Hook'):
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='MR',
            id=payload['object_attributes'].get('iid'),
            title=payload['object_attributes'].get('title')
        )
    elif event.startswith('Issue Hook') or event.startswith('Confidential Issue Hook'):
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='Issue',
            id=payload['object_attributes'].get('iid'),
            title=payload['object_attributes'].get('title')
        )
    elif event == 'Note Hook Issue' or event == 'Confidential Note Hook Issue':
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='Issue',
            id=payload['issue'].get('iid'),
            title=payload['issue'].get('title')
        )
    elif event == 'Note Hook MergeRequest':
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='MR',
            id=payload['merge_request'].get('iid'),
            title=payload['merge_request'].get('title')
        )

    elif event == 'Note Hook Snippet':
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='Snippet',
            id=payload['snippet'].get('id'),
            title=payload['snippet'].get('title')
        )
    return get_repo_name(payload)

def get_event(request: HttpRequest, payload: Dict[str, Any], branches: Optional[str]) -> Optional[str]:
    event = validate_extract_webhook_http_header(request, 'X_GITLAB_EVENT', 'GitLab')
    if event in ['Confidential Issue Hook', 'Issue Hook', 'Merge Request Hook', 'Wiki Page Hook']:
        action = payload['object_attributes'].get('action')
        event = "{} {}".format(event, action)
    elif event in ['Confidential Note Hook', 'Note Hook']:
        action = payload['object_attributes'].get('noteable_type')
        event = "{} {}".format(event, action)
    elif event == 'Push Hook':
        if branches is not None:
            branch = get_branch_name(payload)
            if branches.find(branch) == -1:
                return None

    if event in list(EVENT_FUNCTION_MAPPER.keys()):
        return event

    raise UnexpectedWebhookEventType('GitLab', event)
