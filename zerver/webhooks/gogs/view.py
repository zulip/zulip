# -*- coding: utf-8 -*-
# vim:fenc=utf-8
from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import UserProfile
from zerver.lib.webhooks.git import get_push_commits_event_message, \
    get_pull_request_event_message, get_create_branch_event_message, \
    SUBJECT_WITH_BRANCH_TEMPLATE, SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE

from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Iterable, Optional, Text

def format_push_event(payload):
    # type: (Dict[str, Any]) -> Text

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

def format_new_branch_event(payload):
    # type: (Dict[str, Any]) -> Text

    branch_name = payload['ref']
    url = '{}/src/{}'.format(payload['repository']['html_url'], branch_name)

    data = {
        'user_name': payload['sender']['username'],
        'url': url,
        'branch_name': branch_name
    }
    return get_create_branch_event_message(**data)

def format_pull_request_event(payload):
    # type: (Dict[str, Any]) -> Text

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
def api_gogs_webhook(request, user_profile,
                     payload=REQ(argument_type='body'),
                     stream=REQ(default='commits'),
                     branches=REQ(default=None)):
    # type: (HttpRequest, UserProfile, Dict[str, Any], Text, Optional[Text]) -> HttpResponse

    repo = payload['repository']['name']
    event = request.META['HTTP_X_GOGS_EVENT']

    try:
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
    except KeyError as e:
        return json_error(_('Missing key {} in JSON').format(str(e)))

    check_send_message(user_profile, request.client, 'stream', [stream], topic, body)
    return json_success()
