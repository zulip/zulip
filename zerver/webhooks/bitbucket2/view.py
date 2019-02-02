# Webhooks for external integrations.
import re
from functools import partial
from typing import Any, Dict, List, Optional
from inspect import signature

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message, \
    validate_extract_webhook_http_header, UnexpectedWebhookEventType
from zerver.lib.webhooks.git import TOPIC_WITH_BRANCH_TEMPLATE, \
    TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE, \
    get_commits_comment_action_message, get_force_push_commits_event_message, \
    get_issue_event_message, get_pull_request_event_message, \
    get_push_commits_event_message, get_push_tag_event_message, \
    get_remove_branch_event_message
from zerver.models import UserProfile

BITBUCKET_TOPIC_TEMPLATE = '{repository_name}'
USER_PART = 'User {display_name}(login: {username})'

BITBUCKET_FORK_BODY = USER_PART + ' forked the repository into [{fork_name}]({fork_url}).'
BITBUCKET_COMMIT_STATUS_CHANGED_BODY = ('[System {key}]({system_url}) changed status of'
                                        ' {commit_info} to {status}.')
BITBUCKET_REPO_UPDATED_CHANGED = ('{actor} changed the {change} of the **{repo_name}**'
                                  ' repo from **{old}** to **{new}**\n')
BITBUCKET_REPO_UPDATED_ADDED = '{actor} changed the {change} of the **{repo_name}** repo to **{new}**\n'

PULL_REQUEST_SUPPORTED_ACTIONS = [
    'approved',
    'unapproved',
    'created',
    'updated',
    'rejected',
    'fulfilled',
    'comment_created',
    'comment_updated',
    'comment_deleted',
]

@api_key_only_webhook_view('Bitbucket2')
@has_request_variables
def api_bitbucket2_webhook(request: HttpRequest, user_profile: UserProfile,
                           payload: Dict[str, Any]=REQ(argument_type='body'),
                           branches: Optional[str]=REQ(default=None),
                           user_specified_topic: Optional[str]=REQ("topic", default=None)) -> HttpResponse:
    type = get_type(request, payload)
    if type == 'push':
        # ignore push events with no changes
        if not payload['push']['changes']:
            return json_success()
        branch = get_branch_name_for_push_event(payload)
        if branch and branches:
            if branches.find(branch) == -1:
                return json_success()

    subject = get_subject_based_on_type(payload, type)
    body_function = get_body_based_on_type(type)
    if 'include_title' in signature(body_function).parameters:
        body = body_function(
            payload,
            include_title=user_specified_topic is not None
        )
    else:
        body = body_function(payload)

    if type != 'push':
        check_send_webhook_message(request, user_profile, subject,
                                   body, unquote_url_parameters=True)
    else:
        for b, s in zip(body, subject):
            check_send_webhook_message(request, user_profile, s, b,
                                       unquote_url_parameters=True)

    return json_success()

def get_subject_for_branch_specified_events(payload: Dict[str, Any],
                                            branch_name: Optional[str]=None) -> str:
    return TOPIC_WITH_BRANCH_TEMPLATE.format(
        repo=get_repository_name(payload['repository']),
        branch=get_branch_name_for_push_event(payload) if branch_name is None else branch_name
    )

def get_push_subjects(payload: Dict[str, Any]) -> List[str]:
    subjects_list = []
    for change in payload['push']['changes']:
        potential_tag = (change['new'] or change['old'] or {}).get('type')
        if potential_tag == 'tag':
            subjects_list.append(str(get_subject(payload)))
        else:
            if change.get('new'):
                branch_name = change['new']['name']
            else:
                branch_name = change['old']['name']
            subjects_list.append(str(get_subject_for_branch_specified_events(payload, branch_name)))
    return subjects_list

def get_subject(payload: Dict[str, Any]) -> str:
    assert(payload['repository'] is not None)
    return BITBUCKET_TOPIC_TEMPLATE.format(repository_name=get_repository_name(payload['repository']))

def get_subject_based_on_type(payload: Dict[str, Any], type: str) -> Any:
    if type.startswith('pull_request'):
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repository_name(payload['repository']),
            type='PR',
            id=payload['pullrequest']['id'],
            title=payload['pullrequest']['title']
        )
    if type.startswith('issue'):
        return TOPIC_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
            repo=get_repository_name(payload['repository']),
            type='Issue',
            id=payload['issue']['id'],
            title=payload['issue']['title']
        )
    if type == 'push':
        return get_push_subjects(payload)
    return get_subject(payload)

def get_type(request: HttpRequest, payload: Dict[str, Any]) -> str:
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
        # Note that we only need the HTTP header to determine pullrequest events.
        # We rely on the payload itself to determine the other ones.
        event_key = validate_extract_webhook_http_header(request, "X_EVENT_KEY", "BitBucket")
        assert event_key is not None
        action = re.match('pullrequest:(?P<action>.*)$', event_key)
        if action:
            action_group = action.group('action')
            if action_group in PULL_REQUEST_SUPPORTED_ACTIONS:
                return pull_request_template.format(action_group)
    else:
        event_key = validate_extract_webhook_http_header(request, "X_EVENT_KEY", "BitBucket")
        if event_key == 'repo:updated':
            return event_key

    raise UnexpectedWebhookEventType('BitBucket2', event_key)

def get_body_based_on_type(type: str) -> Any:
    fn = GET_SINGLE_MESSAGE_BODY_DEPENDING_ON_TYPE_MAPPER.get(type)
    return fn

def get_push_bodies(payload: Dict[str, Any]) -> List[str]:
    messages_list = []
    for change in payload['push']['changes']:
        potential_tag = (change['new'] or change['old'] or {}).get('type')
        if potential_tag == 'tag':
            messages_list.append(get_push_tag_body(payload, change))
        # if change['new'] is None, that means a branch was deleted
        elif change.get('new') is None:
            messages_list.append(get_remove_branch_push_body(payload, change))
        elif change.get('forced'):
            messages_list.append(get_force_push_body(payload, change))
        else:
            messages_list.append(get_normal_push_body(payload, change))
    return messages_list

def get_remove_branch_push_body(payload: Dict[str, Any], change: Dict[str, Any]) -> str:
    return get_remove_branch_event_message(
        get_user_username(payload),
        change['old']['name'],
    )

def get_force_push_body(payload: Dict[str, Any], change: Dict[str, Any]) -> str:
    return get_force_push_commits_event_message(
        get_user_username(payload),
        change['links']['html']['href'],
        change['new']['name'],
        change['new']['target']['hash']
    )

def get_commit_author_name(commit: Dict[str, Any]) -> str:
    if commit['author'].get('user'):
        return commit['author']['user'].get('username')
    return commit['author']['raw'].split()[0]

def get_normal_push_body(payload: Dict[str, Any], change: Dict[str, Any]) -> str:
    commits_data = [{
        'name': get_commit_author_name(commit),
        'sha': commit.get('hash'),
        'url': commit.get('links').get('html').get('href'),
        'message': commit.get('message'),
    } for commit in change['commits']]

    return get_push_commits_event_message(
        get_user_username(payload),
        change['links']['html']['href'],
        change['new']['name'],
        commits_data,
        is_truncated=change['truncated']
    )

def get_fork_body(payload: Dict[str, Any]) -> str:
    return BITBUCKET_FORK_BODY.format(
        display_name=get_user_display_name(payload),
        username=get_user_username(payload),
        fork_name=get_repository_full_name(payload['fork']),
        fork_url=get_repository_url(payload['fork'])
    )

def get_commit_comment_body(payload: Dict[str, Any]) -> str:
    comment = payload['comment']
    action = u'[commented]({})'.format(comment['links']['html']['href'])
    return get_commits_comment_action_message(
        get_user_username(payload),
        action,
        comment['commit']['links']['html']['href'],
        comment['commit']['hash'],
        comment['content']['raw'],
    )

def get_commit_status_changed_body(payload: Dict[str, Any]) -> str:
    commit_api_url = payload['commit_status']['links']['commit']['href']
    commit_id = commit_api_url.split('/')[-1]

    commit_info = "[{short_commit_id}]({repo_url}/commits/{commit_id})".format(
        repo_url=get_repository_url(payload['repository']),
        short_commit_id=commit_id[:7],
        commit_id=commit_id
    )

    return BITBUCKET_COMMIT_STATUS_CHANGED_BODY.format(
        key=payload['commit_status']['key'],
        system_url=payload['commit_status']['url'],
        commit_info=commit_info,
        status=payload['commit_status']['state']
    )

def get_issue_commented_body(payload: Dict[str, Any],
                             include_title: Optional[bool]=False) -> str:
    action = '[commented]({}) on'.format(payload['comment']['links']['html']['href'])
    return get_issue_action_body(payload, action, include_title)

def get_issue_action_body(payload: Dict[str, Any], action: str,
                          include_title: Optional[bool]=False) -> str:
    issue = payload['issue']
    assignee = None
    message = None
    if action == 'created':
        if issue['assignee']:
            assignee = issue['assignee'].get('username')
        message = issue['content']['raw']

    return get_issue_event_message(
        get_user_username(payload),
        action,
        issue['links']['html']['href'],
        issue['id'],
        message,
        assignee,
        title=issue['title'] if include_title else None
    )

def get_pull_request_action_body(payload: Dict[str, Any], action: str,
                                 include_title: Optional[bool]=False) -> str:
    pull_request = payload['pullrequest']
    return get_pull_request_event_message(
        get_user_username(payload),
        action,
        get_pull_request_url(pull_request),
        pull_request.get('id'),
        title=pull_request['title'] if include_title else None
    )

def get_pull_request_created_or_updated_body(payload: Dict[str, Any], action: str,
                                             include_title: Optional[bool]=False) -> str:
    pull_request = payload['pullrequest']
    assignee = None
    if pull_request.get('reviewers'):
        assignee = pull_request.get('reviewers')[0]['username']

    return get_pull_request_event_message(
        get_user_username(payload),
        action,
        get_pull_request_url(pull_request),
        pull_request.get('id'),
        target_branch=pull_request['source']['branch']['name'],
        base_branch=pull_request['destination']['branch']['name'],
        message=pull_request['description'],
        assignee=assignee,
        title=pull_request['title'] if include_title else None
    )

def get_pull_request_comment_created_action_body(
        payload: Dict[str, Any],
        include_title: Optional[bool]=False
) -> str:
    action = '[commented]({})'.format(payload['comment']['links']['html']['href'])
    return get_pull_request_comment_action_body(payload, action, include_title)

def get_pull_request_deleted_or_updated_comment_action_body(
        payload: Dict[str, Any], action: str,
        include_title: Optional[bool]=False
) -> str:
    action = "{} a [comment]({})".format(action, payload['comment']['links']['html']['href'])
    return get_pull_request_comment_action_body(payload, action, include_title)

def get_pull_request_comment_action_body(
        payload: Dict[str, Any], action: str,
        include_title: Optional[bool]=False
) -> str:
    action += ' on'
    return get_pull_request_event_message(
        get_user_username(payload),
        action,
        payload['pullrequest']['links']['html']['href'],
        payload['pullrequest']['id'],
        message=payload['comment']['content']['raw'],
        title=payload['pullrequest']['title'] if include_title else None
    )

def get_push_tag_body(payload: Dict[str, Any], change: Dict[str, Any]) -> str:
    if change.get('created'):
        tag = change['new']
        action = 'pushed'  # type: Optional[str]
    elif change.get('closed'):
        tag = change['old']
        action = 'removed'

    return get_push_tag_event_message(
        get_user_username(payload),
        tag.get('name'),
        tag_url=tag['links']['html'].get('href'),
        action=action
    )

def get_repo_updated_body(payload: Dict[str, Any]) -> str:
    changes = ['website', 'name', 'links', 'language', 'full_name', 'description']
    body = ""
    repo_name = payload['repository']['name']
    actor = payload['actor']['username']

    for change in changes:
        new = payload['changes'][change]['new']
        old = payload['changes'][change]['old']
        if change == 'full_name':
            change = 'full name'
        if new and old:
            message = BITBUCKET_REPO_UPDATED_CHANGED.format(
                actor=actor, change=change, repo_name=repo_name,
                old=old, new=new
            )
            body += message
        elif new and not old:
            message = BITBUCKET_REPO_UPDATED_ADDED.format(
                actor=actor, change=change, repo_name=repo_name, new=new
            )
            body += message

    return body

def get_pull_request_url(pullrequest_payload: Dict[str, Any]) -> str:
    return pullrequest_payload['links']['html']['href']

def get_repository_url(repository_payload: Dict[str, Any]) -> str:
    return repository_payload['links']['html']['href']

def get_repository_name(repository_payload: Dict[str, Any]) -> str:
    return repository_payload['name']

def get_repository_full_name(repository_payload: Dict[str, Any]) -> str:
    return repository_payload['full_name']

def get_user_display_name(payload: Dict[str, Any]) -> str:
    return payload['actor']['display_name']

def get_user_username(payload: Dict[str, Any]) -> str:
    return payload['actor']['username']

def get_branch_name_for_push_event(payload: Dict[str, Any]) -> Optional[str]:
    change = payload['push']['changes'][-1]
    potential_tag = (change['new'] or change['old'] or {}).get('type')
    if potential_tag == 'tag':
        return None
    else:
        return (change['new'] or change['old']).get('name')

GET_SINGLE_MESSAGE_BODY_DEPENDING_ON_TYPE_MAPPER = {
    'fork': get_fork_body,
    'commit_comment': get_commit_comment_body,
    'change_commit_status': get_commit_status_changed_body,
    'issue_updated': partial(get_issue_action_body, action='updated'),
    'issue_created': partial(get_issue_action_body, action='created'),
    'issue_commented': get_issue_commented_body,
    'pull_request_created': partial(get_pull_request_created_or_updated_body, action='created'),
    'pull_request_updated': partial(get_pull_request_created_or_updated_body, action='updated'),
    'pull_request_approved': partial(get_pull_request_action_body, action='approved'),
    'pull_request_unapproved': partial(get_pull_request_action_body, action='unapproved'),
    'pull_request_fulfilled': partial(get_pull_request_action_body, action='merged'),
    'pull_request_rejected': partial(get_pull_request_action_body, action='rejected'),
    'pull_request_comment_created': get_pull_request_comment_created_action_body,
    'pull_request_comment_updated': partial(get_pull_request_deleted_or_updated_comment_action_body,
                                            action='updated'),
    'pull_request_comment_deleted': partial(get_pull_request_deleted_or_updated_comment_action_body,
                                            action='deleted'),
    'push': get_push_bodies,
    'repo:updated': get_repo_updated_body,
}
