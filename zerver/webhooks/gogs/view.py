# -*- coding: utf-8 -*-
# vim:fenc=utf-8
from typing import Any, Dict, Iterable, Optional, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import SUBJECT_WITH_BRANCH_TEMPLATE, \
    SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE, get_create_branch_event_message, \
    get_pull_request_event_message, get_push_commits_event_message
from zerver.models import UserProfile

def format_push_event(payload: Dict[str, Any]) -> Text:

    for commit in payload['commits']:
        commit['sha'] = commit['id']
        commit['name'] = (commit['author']['username'] or
                          commit['author']['name'].split()[0])

    data = {
        'user_name': payload['sender']['username'],
        'compare_url': payload['compare_url'],
        'branch_name': payload['ref'].replace('refs/heads/', ''),
        'commits_data': payload['commits']
    }

    return get_push_commits_event_message(**data)

def format_new_branch_event(payload: Dict[str, Any]) -> Text:

    branch_name = payload['ref']
    url = '{}/src/{}'.format(payload['repository']['html_url'], branch_name)

    data = {
        'user_name': payload['sender']['username'],
        'url': url,
        'branch_name': branch_name
    }
    return get_create_branch_event_message(**data)

def format_pull_request_event(payload: Dict[str, Any]) -> Text:

    data = {
        'user_name': payload['pull_request']['user']['username'],
        'action': payload['action'],
        'url': payload['pull_request']['html_url'],
        'number': payload['pull_request']['number'],
        'target_branch': payload['pull_request']['head_branch'],
        'base_branch': payload['pull_request']['base_branch'],
    }

    if payload['pull_request']['merged']:
        data['user_name'] = payload['pull_request']['merged_by']['username']
        data['action'] = 'merged'

    return get_pull_request_event_message(**data)

@api_key_only_webhook_view('Gogs')
@has_request_variables
def api_gogs_webhook(request: HttpRequest, user_profile: UserProfile,
                     payload: Dict[str, Any]=REQ(argument_type='body'),
                     branches: Optional[Text]=REQ(default=None)) -> HttpResponse:

    repo = payload['repository']['name']
    event = request.META['HTTP_X_GOGS_EVENT']
    if event == 'push':
        branch = payload['ref'].replace('refs/heads/', '')
        if branches is not None and branches.find(branch) == -1:
            return json_success()
        body = format_push_event(payload)
        topic = SUBJECT_WITH_BRANCH_TEMPLATE.format(
            repo=repo,
            branch=branch
        )
    elif event == 'create':
        body = format_new_branch_event(payload)
        topic = SUBJECT_WITH_BRANCH_TEMPLATE.format(
            repo=repo,
            branch=payload['ref']
        )
    elif event == 'pull_request':
        body = format_pull_request_event(payload)
        topic = SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=repo,
            type='PR',
            id=payload['pull_request']['id'],
            title=payload['pull_request']['title']
        )
    else:
        return json_error(_('Invalid event "{}" in request headers').format(event))

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()
