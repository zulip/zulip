# vim:fenc=utf-8
from typing import Any, Callable, Dict, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import (
    check_send_webhook_message,
    get_http_headers_from_filename,
    validate_extract_webhook_http_header,
)
from zerver.lib.webhooks.git import (
    TOPIC_WITH_BRANCH_TEMPLATE,
    TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE,
    TOPIC_WITH_RELEASE_TEMPLATE,
    get_create_branch_event_message,
    get_issue_event_message,
    get_pull_request_event_message,
    get_push_commits_event_message,
    get_release_event_message,
)
from zerver.models import UserProfile

fixture_to_headers = get_http_headers_from_filename("HTTP_X_GOGS_EVENT")

def get_issue_url(repo_url: str, issue_nr: int) -> str:
    return f"{repo_url}/issues/{issue_nr}"

def format_push_event(payload: Dict[str, Any]) -> str:

    for commit in payload['commits']:
        commit['sha'] = commit['id']
        commit['name'] = (commit['author']['username'] or
                          commit['author']['name'].split()[0])

    data = {
        'user_name': payload['sender']['username'],
        'compare_url': payload['compare_url'],
        'branch_name': payload['ref'].replace('refs/heads/', ''),
        'commits_data': payload['commits'],
    }

    return get_push_commits_event_message(**data)

def format_new_branch_event(payload: Dict[str, Any]) -> str:

    branch_name = payload['ref']
    url = '{}/src/{}'.format(payload['repository']['html_url'], branch_name)

    data = {
        'user_name': payload['sender']['username'],
        'url': url,
        'branch_name': branch_name,
    }
    return get_create_branch_event_message(**data)

def format_pull_request_event(payload: Dict[str, Any],
                              include_title: bool=False) -> str:

    data = {
        'user_name': payload['pull_request']['user']['username'],
        'action': payload['action'],
        'url': payload['pull_request']['html_url'],
        'number': payload['pull_request']['number'],
        'target_branch': payload['pull_request']['head_branch'],
        'base_branch': payload['pull_request']['base_branch'],
        'title': payload['pull_request']['title'] if include_title else None,
    }

    if payload['pull_request']['merged']:
        data['user_name'] = payload['pull_request']['merged_by']['username']
        data['action'] = 'merged'

    return get_pull_request_event_message(**data)

def format_issues_event(payload: Dict[str, Any], include_title: bool=False) -> str:
    issue_nr = payload['issue']['number']
    assignee = payload['issue']['assignee']
    return get_issue_event_message(
        payload['sender']['login'],
        payload['action'],
        get_issue_url(payload['repository']['html_url'], issue_nr),
        issue_nr,
        payload['issue']['body'],
        assignee=assignee['login'] if assignee else None,
        title=payload['issue']['title'] if include_title else None,
    )

def format_issue_comment_event(payload: Dict[str, Any], include_title: bool=False) -> str:
    action = payload['action']
    comment = payload['comment']
    issue = payload['issue']

    if action == 'created':
        action = '[commented]'
    else:
        action = f'{action} a [comment]'
    action += '({}) on'.format(comment['html_url'])

    return get_issue_event_message(
        payload['sender']['login'],
        action,
        get_issue_url(payload['repository']['html_url'], issue['number']),
        issue['number'],
        comment['body'],
        title=issue['title'] if include_title else None,
    )

def format_release_event(payload: Dict[str, Any], include_title: bool=False) -> str:
    data = {
        'user_name': payload['release']['author']['username'],
        'action': payload['action'],
        'tagname': payload['release']['tag_name'],
        'release_name': payload['release']['name'],
        'url': payload['repository']['html_url'],
    }

    return get_release_event_message(**data)

@webhook_view('Gogs')
@has_request_variables
def api_gogs_webhook(request: HttpRequest, user_profile: UserProfile,
                     payload: Dict[str, Any]=REQ(argument_type='body'),
                     branches: Optional[str]=REQ(default=None),
                     user_specified_topic: Optional[str]=REQ("topic", default=None)) -> HttpResponse:
    return gogs_webhook_main("Gogs", "X_GOGS_EVENT", format_pull_request_event,
                             request, user_profile, payload, branches, user_specified_topic)

def gogs_webhook_main(integration_name: str, http_header_name: str,
                      format_pull_request_event: Callable[..., Any],
                      request: HttpRequest, user_profile: UserProfile,
                      payload: Dict[str, Any],
                      branches: Optional[str],
                      user_specified_topic: Optional[str]) -> HttpResponse:
    repo = payload['repository']['name']
    event = validate_extract_webhook_http_header(request, http_header_name, integration_name)
    if event == 'push':
        branch = payload['ref'].replace('refs/heads/', '')
        if branches is not None and branch not in branches.split(','):
            return json_success()
        body = format_push_event(payload)
        topic = TOPIC_WITH_BRANCH_TEMPLATE.format(
            repo=repo,
            branch=branch,
        )
    elif event == 'create':
        body = format_new_branch_event(payload)
        topic = TOPIC_WITH_BRANCH_TEMPLATE.format(
            repo=repo,
            branch=payload['ref'],
        )
    elif event == 'pull_request':
        body = format_pull_request_event(
            payload,
            include_title=user_specified_topic is not None,
        )
        topic = TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=repo,
            type='PR',
            id=payload['pull_request']['id'],
            title=payload['pull_request']['title'],
        )
    elif event == 'issues':
        body = format_issues_event(
            payload,
            include_title=user_specified_topic is not None,
        )
        topic = TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=repo,
            type='Issue',
            id=payload['issue']['number'],
            title=payload['issue']['title'],
        )
    elif event == 'issue_comment':
        body = format_issue_comment_event(
            payload,
            include_title=user_specified_topic is not None,
        )
        topic = TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=repo,
            type='Issue',
            id=payload['issue']['number'],
            title=payload['issue']['title'],
        )
    elif event == 'release':
        body = format_release_event(
            payload,
            include_title=user_specified_topic is not None,
        )
        topic = TOPIC_WITH_RELEASE_TEMPLATE.format(
            repo=repo,
            tag=payload['release']['tag_name'],
            title=payload['release']['name'],
        )

    else:
        raise UnsupportedWebhookEventType(event)

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()
