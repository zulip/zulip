import logging
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Text, Tuple

import ujson
from django.conf import settings
from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_api_view, \
    flexible_boolean, to_non_negative_int
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict
from zerver.lib.webhooks.git import SUBJECT_WITH_BRANCH_TEMPLATE, \
    SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE, \
    get_commits_comment_action_message, get_force_push_commits_event_message, \
    get_issue_event_message, get_pull_request_event_message, \
    get_push_commits_event_message, get_remove_branch_event_message
from zerver.models import UserProfile, get_client
from zerver.views.messages import send_message_backend

ZULIP_TEST_REPO_NAME = 'zulip-test'
ZULIP_TEST_REPO_ID = 6893087

def is_test_repository(repository: Mapping[Text, Any]) -> bool:
    return repository['name'] == ZULIP_TEST_REPO_NAME and repository['id'] == ZULIP_TEST_REPO_ID

class UnknownEventType(Exception):
    pass

def github_pull_request_content(payload: Mapping[Text, Any]) -> Text:
    pull_request = payload['pull_request']
    action = get_pull_request_or_issue_action(payload)

    if action in ('opened', 'edited'):
        return get_pull_request_event_message(
            payload['sender']['login'],
            action,
            pull_request['html_url'],
            pull_request['number'],
            pull_request['head']['ref'],
            pull_request['base']['ref'],
            pull_request['body'],
            get_pull_request_or_issue_assignee(pull_request)
        )
    return get_pull_request_event_message(
        payload['sender']['login'],
        action,
        pull_request['html_url'],
        pull_request['number']
    )

def github_issues_content(payload: Mapping[Text, Any]) -> Text:
    issue = payload['issue']
    action = get_pull_request_or_issue_action(payload)

    if action in ('opened', 'edited'):
        return get_issue_event_message(
            payload['sender']['login'],
            action,
            issue['html_url'],
            issue['number'],
            issue['body'],
            get_pull_request_or_issue_assignee(issue)
        )
    return get_issue_event_message(
        payload['sender']['login'],
        action,
        issue['html_url'],
        issue['number'],
    )

def github_object_commented_content(payload: Mapping[Text, Any], type: Text) -> Text:
    comment = payload['comment']
    issue = payload['issue']
    action = u'[commented]({}) on'.format(comment['html_url'])

    return get_pull_request_event_message(
        comment['user']['login'],
        action,
        issue['html_url'],
        issue['number'],
        message=comment['body'],
        type=type
    )

def get_pull_request_or_issue_action(payload: Mapping[Text, Any]) -> Text:
    return 'synchronized' if payload['action'] == 'synchronize' else payload['action']

def get_pull_request_or_issue_assignee(object_payload: Mapping[Text, Any]) -> Optional[Text]:
    assignee_dict = object_payload.get('assignee')
    if assignee_dict:
        return assignee_dict.get('login')
    return None

def get_pull_request_or_issue_subject(repository: Mapping[Text, Any],
                                      payload_object: Mapping[Text, Any],
                                      type: Text) -> Text:
    return SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
        repo=repository['name'],
        type=type,
        id=payload_object['number'],
        title=payload_object['title']
    )

def github_generic_subject(noun: Text, topic_focus: Text, blob: Mapping[Text, Any]) -> Text:
    # issue and pull_request objects have the same fields we're interested in
    return u'%s: %s %d: %s' % (topic_focus, noun, blob['number'], blob['title'])

def api_github_v1(user_profile: UserProfile,
                  event: Text,
                  payload: Mapping[Text, Any],
                  branches: Text,
                  stream: Text,
                  **kwargs: Any) -> Tuple[Text, Text, Text]:
    """
    processes github payload with version 1 field specification
    `payload` comes in unmodified from github
    `stream` is set to 'commits' if otherwise unset
    """
    commit_stream = stream
    issue_stream = 'issues'
    return api_github_v2(user_profile, event, payload, branches,
                         stream, commit_stream, issue_stream, **kwargs)


def api_github_v2(user_profile: UserProfile, event: Text, payload: Mapping[Text, Any],
                  branches: Text, default_stream: Text, commit_stream: Text,
                  issue_stream: Text, topic_focus: Optional[Text]=None) -> Tuple[Text, Text, Text]:
    """
    processes github payload with version 2 field specification
    `payload` comes in unmodified from github
    `default_stream` is set to what `stream` is in v1 above
    `commit_stream` and `issue_stream` fall back to `default_stream` if they are empty
    This and allowing alternative endpoints is what distinguishes v1 from v2 of the github configuration
    """
    target_stream = commit_stream if commit_stream else default_stream
    issue_stream = issue_stream if issue_stream else default_stream
    repository = payload['repository']
    updated_topic_focus = topic_focus if topic_focus else repository['name']

    # Event Handlers
    if event == 'pull_request':
        subject = get_pull_request_or_issue_subject(repository, payload['pull_request'], 'PR')
        content = github_pull_request_content(payload)
    elif event == 'issues':
        # in v1, we assume that this stream exists since it is
        # deprecated and the few realms that use it already have the
        # stream
        target_stream = issue_stream
        subject = get_pull_request_or_issue_subject(repository, payload['issue'], 'Issue')
        content = github_issues_content(payload)
    elif event == 'issue_comment':
        # Comments on both issues and pull requests come in as issue_comment events
        issue = payload['issue']
        if 'pull_request' not in issue or issue['pull_request']['diff_url'] is None:
            # It's an issues comment
            target_stream = issue_stream
            type = 'Issue'
            subject = get_pull_request_or_issue_subject(repository, payload['issue'], type)
        else:
            # It's a pull request comment
            type = 'PR'
            subject = get_pull_request_or_issue_subject(repository, payload['issue'], type)

        content = github_object_commented_content(payload, type)

    elif event == 'push':
        subject, content = build_message_from_gitlog(user_profile, updated_topic_focus,
                                                     payload['ref'], payload['commits'],
                                                     payload['before'], payload['after'],
                                                     payload['compare'],
                                                     payload['pusher']['name'],
                                                     forced=payload['forced'],
                                                     created=payload['created'],
                                                     deleted=payload['deleted'])
    elif event == 'commit_comment':
        subject = updated_topic_focus

        comment = payload['comment']
        action = u'[commented]({})'.format(comment['html_url'])
        content = get_commits_comment_action_message(
            comment['user']['login'],
            action,
            comment['html_url'].split('#', 1)[0],
            comment['commit_id'],
            comment['body'],
        )

    else:
        raise UnknownEventType(u'Event %s is unknown and cannot be handled' % (event,))

    return target_stream, subject, content

@authenticated_api_view(is_webhook=True)
@has_request_variables
def api_github_landing(request: HttpRequest, user_profile: UserProfile, event: Text=REQ(),
                       payload: Mapping[Text, Any]=REQ(validator=check_dict([])),
                       branches: Text=REQ(default=''),
                       stream: Text=REQ(default=''),
                       version: int=REQ(converter=to_non_negative_int, default=1),
                       commit_stream: Text=REQ(default=''),
                       issue_stream: Text=REQ(default=''),
                       exclude_pull_requests: bool=REQ(converter=flexible_boolean, default=False),
                       exclude_issues: bool=REQ(converter=flexible_boolean, default=False),
                       exclude_commits: bool=REQ(converter=flexible_boolean, default=False),
                       emphasize_branch_in_topic: bool=REQ(converter=flexible_boolean, default=False),
                       ) -> HttpResponse:

    repository = payload['repository']

    # Special hook for capturing event data. If we see our special test repo, log the payload from github.
    try:
        if is_test_repository(repository) and settings.PRODUCTION:
            with open('/var/log/zulip/github-payloads', 'a') as f:
                f.write(ujson.dumps({'event': event,
                                     'payload': payload,
                                     'branches': branches,
                                     'stream': stream,
                                     'version': version,
                                     'commit_stream': commit_stream,
                                     'issue_stream': issue_stream,
                                     'exclude_pull_requests': exclude_pull_requests,
                                     'exclude_issues': exclude_issues,
                                     'exclude_commits': exclude_commits,
                                     'emphasize_branch_in_topic': emphasize_branch_in_topic,
                                     }))
                f.write('\n')
    except Exception:
        logging.exception('Error while capturing Github event')

    if not stream:
        stream = 'commits'

    short_ref = re.sub(r'^refs/heads/', '', payload.get('ref', ''))
    kwargs = dict()

    if emphasize_branch_in_topic and short_ref:
        kwargs['topic_focus'] = short_ref

    allowed_events = set()
    if not exclude_pull_requests:
        allowed_events.add('pull_request')

    if not exclude_issues:
        allowed_events.add('issues')
        allowed_events.add('issue_comment')

    if not exclude_commits:
        allowed_events.add('push')
        allowed_events.add('commit_comment')

    if event not in allowed_events:
        return json_success()

    # We filter issue_comment events for issue creation events
    if event == 'issue_comment' and payload['action'] != 'created':
        return json_success()

    if event == 'push':
        # If we are given a whitelist of branches, then we silently ignore
        # any push notification on a branch that is not in our whitelist.
        if branches and short_ref not in re.split('[\s,;|]+', branches):
            return json_success()

    # Map payload to the handler with the right version
    if version == 2:
        target_stream, subject, content = api_github_v2(user_profile, event, payload, branches,
                                                        stream, commit_stream, issue_stream,
                                                        **kwargs)
    else:
        target_stream, subject, content = api_github_v1(user_profile, event, payload, branches,
                                                        stream, **kwargs)

    request.client = get_client('ZulipGitHubWebhook')
    return send_message_backend(request, user_profile,
                                message_type_name='stream',
                                message_to=[target_stream],
                                forged=False, topic_name=subject,
                                message_content=content)

def build_message_from_gitlog(user_profile: UserProfile, name: Text, ref: Text,
                              commits: List[Dict[str, str]], before: Text, after: Text,
                              url: Text, pusher: Text, forced: Optional[Text]=None,
                              created: Optional[Text]=None, deleted: Optional[bool]=False
                              ) -> Tuple[Text, Text]:
    short_ref = re.sub(r'^refs/heads/', '', ref)
    subject = SUBJECT_WITH_BRANCH_TEMPLATE.format(repo=name, branch=short_ref)

    if re.match(r'^0+$', after):
        content = get_remove_branch_event_message(pusher, short_ref)
    # 'created' and 'forced' are github flags; the second check is for beanstalk
    elif (forced and not created) or (forced is None and len(commits) == 0):
        content = get_force_push_commits_event_message(pusher, url, short_ref, after[:7])
    else:
        commits = _transform_commits_list_to_common_format(commits)
        content = get_push_commits_event_message(pusher, url, short_ref, commits, deleted=deleted)

    return subject, content

def _transform_commits_list_to_common_format(commits: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    new_commits_list = []
    for commit in commits:
        new_commits_list.append({
            'name': commit['author'].get('username'),
            'sha': commit.get('id'),
            'url': commit.get('url'),
            'message': commit.get('message'),
        })
    return new_commits_list
