# Webhooks for external integrations.
from __future__ import absolute_import
import re
from functools import partial
from typing import Any, Callable
from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import Client, UserProfile


BITBUCKET_SUBJECT_TEMPLATE = '{repository_name}'
USER_PART = 'User {display_name}(login: {username})'

BITBUCKET_PUSH_BODY = USER_PART + ' pushed [{number_of_commits} commit{s}]({commits_url}) into {branch} branch.'
BITBUCKET_FORK_BODY = USER_PART + ' forked the repository into [{fork_name}]({fork_url}).'
BITBUCKET_COMMIT_COMMENT_BODY = USER_PART + ' added [comment]({url_to_comment}) to commit.'
BITBUCKET_COMMIT_STATUS_CHANGED_BODY = '[System {key}]({system_url}) changed status of {commit_info} to {status}.'
BITBUCKET_ISSUE_ACTION_BODY = USER_PART + ' {action} [an issue]({issue_url})'
BITBUCKET_PULL_REQUEST_ACTION_BODY = USER_PART + ' {action} ["{title}" pull request]({pull_request_url})'
BITBUCKET_PULL_REQUEST_COMMENT_ACTION_BODY = USER_PART + ' {action} [comment]({comment_url} ' + \
                                             'in ["{title}" pull request]({pull_request_url})'

PULL_REQUEST_SUPPORTED_ACTIONS = [
    'approved',
    'unapproved',
    'created',
    'updated',
    'rejected',
    'merged',
    'comment_created',
    'comment_updated',
    'comment_deleted',
]

class UnknownTriggerType(Exception):
    pass


@api_key_only_webhook_view('Bitbucket2')
@has_request_variables
def api_bitbucket2_webhook(request, user_profile, client, payload=REQ(argument_type='body'),
                           stream=REQ(default='bitbucket')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], str) -> HttpResponse
    try:
        subject = get_subject(payload)
        type = get_type(request, payload)
        body = get_body_based_on_type(type)(payload)
    except KeyError as e:
        return json_error(_("Missing key {} in JSON").format(str(e)))

    check_send_message(user_profile, client, 'stream', [stream], subject, body)
    return json_success()

def get_subject(payload):
    # type: (Dict[str, Any]) -> str
    return BITBUCKET_SUBJECT_TEMPLATE.format(repository_name=payload['repository']['name'])

def get_type(request, payload):
    # type: (HttpRequest, Dict[str, Any]) -> str
    event_key = request.META.get("HTTP_X_EVENT_KEY")
    if payload.get('push'):
        return 'push'
    elif payload.get('fork'):
        return 'fork'
    elif payload.get('comment') and payload.get('commit'):
        return 'commit_comment'
    elif payload.get('commit_status'):
        return 'change_commit_status'
    elif payload.get('issue'):
        if payload.get('changes'):
            return "issue_updated"
        if payload.get('comment'):
            return 'issue_commented'
        return "issue_created"
    elif payload.get('pullrequest'):
        pull_request_template = 'pull_request_{}'
        action = re.match('pullrequest:(?P<action>.*)$', event_key)
        if action:
            action = action.group('action')
            if action in PULL_REQUEST_SUPPORTED_ACTIONS:
                return pull_request_template.format(action)
    raise UnknownTriggerType()

def get_body_based_on_type(type):
    # type: (str) -> Any
    return GET_BODY_DEPENDING_ON_TYPE_MAPPER.get(type)

def get_push_body(payload):
    # type: (Dict[str, Any]) -> str
    change = payload['push']['changes'][-1]
    number_of_commits = len(change['commits'])
    return BITBUCKET_PUSH_BODY.format(
        display_name=get_user_display_name(payload),
        username=get_user_username(payload),
        number_of_commits=number_of_commits if number_of_commits <= 5 else "more than 5",
        s='' if number_of_commits == 1 else 's',
        commits_url=change['links']['html']['href'],
        branch=change['new']['name']
    )

def get_fork_body(payload):
    # type: (Dict[str, Any]) -> str
    return BITBUCKET_FORK_BODY.format(
        display_name=get_user_display_name(payload),
        username=get_user_username(payload),
        fork_name=get_repository_name(payload['fork']),
        fork_url=get_repository_url(payload['fork'])
    )

def get_commit_comment_body(payload):
    # type: (Dict[str, Any]) -> str
    return BITBUCKET_COMMIT_COMMENT_BODY.format(
        display_name=get_user_display_name(payload),
        username=get_user_username(payload),
        url_to_comment=payload['comment']['links']['html']['href']
    )

def get_commit_status_changed_body(payload):
    # type: (Dict[str, Any]) -> str
    commit_id = re.match('.*/commit/(?P<commit_id>[A-Za-z0-9]*$)', payload['commit_status']['links']['commit']['href'])
    if commit_id:
        commit_info = "{}/{}".format(get_repository_url(payload['repository']), commit_id.group('commit_id'))
    else:
        commit_info = 'commit'

    return BITBUCKET_COMMIT_STATUS_CHANGED_BODY.format(
        key=payload['commit_status']['key'],
        system_url=payload['commit_status']['url'],
        commit_info=commit_info,
        status=payload['commit_status']['state']
    )

def get_issue_action_body(payload, action):
    # type: (Dict[str, Any], str) -> str
    return BITBUCKET_ISSUE_ACTION_BODY.format(
        display_name=get_user_display_name(payload),
        username=get_user_username(payload),
        action=action,
        issue_url=payload['issue']['links']['html']['href']
    )

def get_pull_request_action_body(payload, action):
    # type: (Dict[str, Any], str) -> str
    return BITBUCKET_PULL_REQUEST_ACTION_BODY.format(
        display_name=get_user_display_name(payload),
        username=get_user_username(payload),
        action=action,
        title=get_pull_request_title(payload['pullrequest']),
        pull_request_url=get_pull_request_url(payload['pullrequest'])
    )

def get_pull_request_comment_action_body(payload, action):
    # type: (Dict[str, Any], str) -> str
    return BITBUCKET_PULL_REQUEST_COMMENT_ACTION_BODY.format(
        display_name=get_user_display_name(payload),
        username=get_user_username(payload),
        action=action,
        comment_url=payload['comment']['links']['html']['href'],
        title=get_pull_request_title(payload['pullrequest']),
        pull_request_url=get_pull_request_url(payload['pullrequest'])
    )

def get_pull_request_title(pullrequest_payload):
    # type: (Dict[str, Any]) -> str
    return pullrequest_payload['title']

def get_pull_request_url(pullrequest_payload):
    # type: (Dict[str, Any]) -> str
    return pullrequest_payload['links']['html']['href']

def get_repository_url(repository_payload):
    # type: (Dict[str, Any]) -> str
    return repository_payload['links']['html']['href']

def get_repository_name(repository_payload):
    # type: (Dict[str, Any]) -> str
    return repository_payload['full_name']

def get_user_display_name(payload):
    # type: (Dict[str, Any]) -> str
    return payload['actor']['display_name']

def get_user_username(payload):
    # type: (Dict[str, Any]) -> str
    return payload['actor']['username']

GET_BODY_DEPENDING_ON_TYPE_MAPPER = {
    'push': get_push_body,
    'fork': get_fork_body,
    'commit_comment': get_commit_comment_body,
    'change_commit_status': get_commit_status_changed_body,
    'issue_updated': partial(get_issue_action_body, action='updated'),
    'issue_created': partial(get_issue_action_body, action='created'),
    'issue_commented': partial(get_issue_action_body, action='commented'),
    'pull_request_created': partial(get_pull_request_action_body, action='created'),
    'pull_request_updated': partial(get_pull_request_action_body, action='updated'),
    'pull_request_approved': partial(get_pull_request_action_body, action='approved'),
    'pull_request_unapproved': partial(get_pull_request_action_body, action='unapproved'),
    'pull_request_merged': partial(get_pull_request_action_body, action='merged'),
    'pull_request_rejected': partial(get_pull_request_action_body, action='rejected'),
    'pull_request_comment_created': partial(get_pull_request_comment_action_body, action='created'),
    'pull_request_comment_updated': partial(get_pull_request_comment_action_body, action='updated'),
    'pull_request_comment_deleted': partial(get_pull_request_comment_action_body, action='deleted')
}
