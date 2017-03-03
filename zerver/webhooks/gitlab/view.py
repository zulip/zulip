from __future__ import absolute_import
from functools import partial
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.decorator import api_key_only_webhook_view, REQ, has_request_variables
from zerver.lib.webhooks.git import get_push_commits_event_message, EMPTY_SHA,\
    get_remove_branch_event_message, get_pull_request_event_message,\
    get_issue_event_message, SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE,\
    get_commits_comment_action_message, get_push_tag_event_message
from zerver.models import Client, UserProfile

from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Iterable, Optional, Text


class UnknownEventType(Exception):
    pass


def get_push_event_body(payload):
    # type: (Dict[str, Any]) -> Text
    if payload.get('after') == EMPTY_SHA:
        return get_remove_branch_event_body(payload)
    return get_normal_push_event_body(payload)

def get_normal_push_event_body(payload):
    # type: (Dict[str, Any]) -> Text
    compare_url = u'{}/compare/{}...{}'.format(
        get_repository_homepage(payload),
        payload['before'],
        payload['after']
    )

    commits = [
        {
            'sha': commit.get('id'),
            'message': commit.get('message'),
            'url': commit.get('url')
        }
        for commit in payload.get('commits')
    ]

    return get_push_commits_event_message(
        get_user_name(payload),
        compare_url,
        get_branch_name(payload),
        commits
    )

def get_remove_branch_event_body(payload):
    # type: (Dict[str, Any]) -> Text
    return get_remove_branch_event_message(
        get_user_name(payload),
        get_branch_name(payload)
    )

def get_tag_push_event_body(payload):
    # type: (Dict[str, Any]) -> Text
    return get_push_tag_event_message(
        get_user_name(payload),
        get_tag_name(payload),
        action="pushed" if payload.get('checkout_sha') else "removed"
    )

def get_issue_created_event_body(payload):
    # type: (Dict[str, Any]) -> Text
    return get_issue_event_message(
        get_issue_user_name(payload),
        'created',
        get_object_url(payload),
        payload.get('object_attributes').get('iid'),
        payload.get('object_attributes').get('description'),
        get_objects_assignee(payload)
    )

def get_issue_event_body(payload, action):
    # type: (Dict[str, Any], Text) -> Text
    return get_issue_event_message(
        get_issue_user_name(payload),
        action,
        get_object_url(payload),
        payload.get('object_attributes').get('iid'),
    )

def get_merge_request_updated_event_body(payload):
    # type: (Dict[str, Any]) -> Text
    if payload.get('object_attributes').get('oldrev'):
        return get_merge_request_event_body(payload, "added commit(s) to")
    return get_merge_request_open_or_updated_body(payload, "updated")

def get_merge_request_event_body(payload, action):
    # type: (Dict[str, Any], Text) -> Text
    pull_request = payload.get('object_attributes')
    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        pull_request.get('url'),
        pull_request.get('iid'),
        type='MR',
    )

def get_merge_request_open_or_updated_body(payload, action):
    # type: (Dict[str, Any], Text) -> Text
    pull_request = payload.get('object_attributes')
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
    )

def get_objects_assignee(payload):
    # type: (Dict[str, Any]) -> Optional[Text]
    assignee_object = payload.get('assignee')
    if assignee_object:
        return assignee_object.get('name')
    return None

def get_commented_commit_event_body(payload):
    # type: (Dict[str, Any]) -> Text
    comment = payload.get('object_attributes')
    action = u'[commented]({})'.format(comment['url'])
    return get_commits_comment_action_message(
        get_issue_user_name(payload),
        action,
        payload.get('commit').get('url'),
        payload.get('commit').get('id'),
        comment['note'],
    )

def get_commented_merge_request_event_body(payload):
    # type: (Dict[str, Any]) -> Text
    comment = payload.get('object_attributes')
    action = u'[commented]({}) on'.format(comment['url'])
    url = u'{}/merge_requests/{}'.format(
        payload.get('project').get('web_url'),
        payload.get('merge_request').get('iid')
    )
    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        url,
        payload.get('merge_request').get('iid'),
        message=comment['note'],
        type='MR'
    )

def get_commented_issue_event_body(payload):
    # type: (Dict[str, Any]) -> Text
    comment = payload.get('object_attributes')
    action = u'[commented]({}) on'.format(comment['url'])
    url = u'{}/issues/{}'.format(
        payload.get('project').get('web_url'),
        payload.get('issue').get('iid')
    )
    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        url,
        payload.get('issue').get('iid'),
        message=comment['note'],
        type='Issue'
    )

def get_commented_snippet_event_body(payload):
    # type: (Dict[str, Any]) -> Text
    comment = payload.get('object_attributes')
    action = u'[commented]({}) on'.format(comment['url'])
    url = u'{}/snippets/{}'.format(
        payload.get('project').get('web_url'),
        payload.get('snippet').get('id')
    )
    return get_pull_request_event_message(
        get_issue_user_name(payload),
        action,
        url,
        payload.get('snippet').get('id'),
        message=comment['note'],
        type='Snippet'
    )

def get_wiki_page_event_body(payload, action):
    # type: (Dict[str, Any], Text) -> Text
    return u"{} {} [Wiki Page \"{}\"]({}).".format(
        get_issue_user_name(payload),
        action,
        payload.get('object_attributes').get('title'),
        payload.get('object_attributes').get('url'),
    )

def get_build_hook_event_body(payload):
    # type: (Dict[str, Any]) -> Text
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

def get_pipeline_event_body(payload):
    # type: (Dict[str, Any]) -> Text
    pipeline_status = payload.get('object_attributes').get('status')
    if pipeline_status == 'pending':
        action = 'was created'
    elif pipeline_status == 'running':
        action = 'started'
    else:
        action = 'changed status to {}'.format(pipeline_status)

    builds_status = u""
    for build in payload.get('builds'):
        builds_status += u"* {} - {}\n".format(build.get('name'), build.get('status'))
    return u"Pipeline {} with build(s):\n{}.".format(action, builds_status[:-1])

def get_repo_name(payload):
    # type: (Dict[str, Any]) -> Text
    return payload['project']['name']

def get_user_name(payload):
    # type: (Dict[str, Any]) -> Text
    return payload['user_name']

def get_issue_user_name(payload):
    # type: (Dict[str, Any]) -> Text
    return payload['user']['name']

def get_repository_homepage(payload):
    # type: (Dict[str, Any]) -> Text
    return payload['repository']['homepage']

def get_branch_name(payload):
    # type: (Dict[str, Any]) -> Text
    return payload['ref'].replace('refs/heads/', '')

def get_tag_name(payload):
    # type: (Dict[str, Any]) -> Text
    return payload['ref'].replace('refs/tags/', '')

def get_object_iid(payload):
    # type: (Dict[str, Any]) -> Text
    return payload['object_attributes']['iid']

def get_object_url(payload):
    # type: (Dict[str, Any]) -> Text
    return payload['object_attributes']['url']

EVENT_FUNCTION_MAPPER = {
    'Push Hook': get_push_event_body,
    'Tag Push Hook': get_tag_push_event_body,
    'Issue Hook open': get_issue_created_event_body,
    'Issue Hook close': partial(get_issue_event_body, action='closed'),
    'Issue Hook reopen': partial(get_issue_event_body, action='reopened'),
    'Issue Hook update': partial(get_issue_event_body, action='updated'),
    'Note Hook Commit': get_commented_commit_event_body,
    'Note Hook MergeRequest': get_commented_merge_request_event_body,
    'Note Hook Issue': get_commented_issue_event_body,
    'Note Hook Snippet': get_commented_snippet_event_body,
    'Merge Request Hook open': partial(get_merge_request_open_or_updated_body, action='created'),
    'Merge Request Hook update': get_merge_request_updated_event_body,
    'Merge Request Hook merge': partial(get_merge_request_event_body, action='merged'),
    'Merge Request Hook close': partial(get_merge_request_event_body, action='closed'),
    'Wiki Page Hook create': partial(get_wiki_page_event_body, action='created'),
    'Wiki Page Hook update': partial(get_wiki_page_event_body, action='updated'),
    'Build Hook': get_build_hook_event_body,
    'Pipeline Hook': get_pipeline_event_body,
}

@api_key_only_webhook_view("Gitlab")
@has_request_variables
def api_gitlab_webhook(request, user_profile, client,
                       stream=REQ(default='gitlab'),
                       payload=REQ(argument_type='body')):
    # type: (HttpRequest, UserProfile, Client, Text, Dict[str, Any]) -> HttpResponse
    event = get_event(request, payload)
    body = get_body_based_on_event(event)(payload)
    subject = get_subject_based_on_event(event, payload)
    check_send_message(user_profile, client, 'stream', [stream], subject, body)
    return json_success()

def get_body_based_on_event(event):
    # type: (str) -> Any
    return EVENT_FUNCTION_MAPPER[event]

def get_subject_based_on_event(event, payload):
    # type: (str, Dict[str, Any]) -> Text
    if event == 'Push Hook':
        return u"{} / {}".format(get_repo_name(payload), get_branch_name(payload))
    elif event == 'Build Hook':
        return u"{} / {}".format(payload.get('repository').get('name'), get_branch_name(payload))
    elif event == 'Pipeline Hook':
        return u"{} / {}".format(
            get_repo_name(payload),
            payload.get('object_attributes').get('ref').replace('refs/heads/', ''))
    elif event.startswith('Merge Request Hook'):
        return SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='MR',
            id=payload.get('object_attributes').get('iid'),
            title=payload.get('object_attributes').get('title')
        )
    elif event.startswith('Issue Hook'):
        return SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='Issue',
            id=payload.get('object_attributes').get('iid'),
            title=payload.get('object_attributes').get('title')
        )
    elif event == 'Note Hook Issue':
        return SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='Issue',
            id=payload.get('issue').get('iid'),
            title=payload.get('issue').get('title')
        )
    elif event == 'Note Hook MergeRequest':
        return SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='MR',
            id=payload.get('merge_request').get('iid'),
            title=payload.get('merge_request').get('title')
        )

    elif event == 'Note Hook Snippet':
        return SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repo_name(payload),
            type='Snippet',
            id=payload.get('snippet').get('id'),
            title=payload.get('snippet').get('title')
        )
    return get_repo_name(payload)

def get_event(request, payload):
    # type: (HttpRequest,  Dict[str, Any]) -> str
    event = request.META['HTTP_X_GITLAB_EVENT']
    if event == 'Issue Hook':
        action = payload.get('object_attributes').get('action')
        event = "{} {}".format(event, action)
    elif event == 'Note Hook':
        action = payload.get('object_attributes').get('noteable_type')
        event = "{} {}".format(event, action)
    elif event == 'Merge Request Hook':
        action = payload.get('object_attributes').get('action')
        event = "{} {}".format(event, action)
    elif event == 'Wiki Page Hook':
        action = payload.get('object_attributes').get('action')
        event = "{} {}".format(event, action)

    if event in list(EVENT_FUNCTION_MAPPER.keys()):
        return event
    raise UnknownEventType(u'Event {} is unknown and cannot be handled'.format(event))
