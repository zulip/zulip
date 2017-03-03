from __future__ import absolute_import
from django.conf import settings
from zerver.models import get_client, UserProfile
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict
from zerver.decorator import authenticated_api_view, REQ, has_request_variables, to_non_negative_int, flexible_boolean
from zerver.views.messages import send_message_backend
from zerver.lib.webhooks.git import get_push_commits_event_message,\
    SUBJECT_WITH_BRANCH_TEMPLATE, get_force_push_commits_event_message, \
    get_remove_branch_event_message, get_pull_request_event_message,\
    get_issue_event_message, SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE,\
    get_commits_comment_action_message
import logging
import re
import ujson

from typing import Any, Mapping, Optional, Sequence, Tuple, Text
from zerver.lib.str_utils import force_str
from django.http import HttpRequest, HttpResponse

ZULIP_TEST_REPO_NAME = 'zulip-test'
ZULIP_TEST_REPO_ID = 6893087

def is_test_repository(repository):
    # type: (Mapping[Text, Any]) -> bool
    return repository['name'] == ZULIP_TEST_REPO_NAME and repository['id'] == ZULIP_TEST_REPO_ID

class UnknownEventType(Exception):
    pass

def github_pull_request_content(payload):
    # type: (Mapping[Text, Any]) -> Text
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

def github_issues_content(payload):
    # type: (Mapping[Text, Any]) -> Text
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

def github_object_commented_content(payload, type):
    # type: (Mapping[Text, Any], Text) -> Text
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

def get_pull_request_or_issue_action(payload):
    # type: (Mapping[Text, Any]) -> Text
    return 'synchronized' if payload['action'] == 'synchronize' else payload['action']

def get_pull_request_or_issue_assignee(object_payload):
    # type: (Mapping[Text, Any]) -> Optional[Text]
    assignee_dict = object_payload.get('assignee')
    if assignee_dict:
        return assignee_dict.get('login')
    return None

def get_pull_request_or_issue_subject(repository, payload_object, type):
    # type: (Mapping[Text, Any], Mapping[Text, Any], Text) -> Text
    return SUBJECT_WITH_PR_OR_ISSUE_INFO_TEMPLATE.format(
        repo=repository['name'],
        type=type,
        id=payload_object['number'],
        title=payload_object['title']
    )

def github_generic_subject(noun, topic_focus, blob):
    # type: (Text, Text, Mapping[Text, Any]) -> Text
    # issue and pull_request objects have the same fields we're interested in
    return u'%s: %s %d: %s' % (topic_focus, noun, blob['number'], blob['title'])

def api_github_v1(user_profile, event, payload, branches, stream, **kwargs):
    # type: (UserProfile, Text, Mapping[Text, Any], Text, Text, **Any) -> Tuple[Text, Text, Text]
    """
    processes github payload with version 1 field specification
    `payload` comes in unmodified from github
    `stream` is set to 'commits' if otherwise unset
    """
    commit_stream = stream
    issue_stream = 'issues'
    return api_github_v2(user_profile, event, payload, branches, stream, commit_stream, issue_stream, **kwargs)


def api_github_v2(user_profile, event, payload, branches, default_stream,
                  commit_stream, issue_stream, topic_focus = None):
    # type: (UserProfile, Text, Mapping[Text, Any], Text, Text, Text, Text, Optional[Text]) -> Tuple[Text, Text, Text]
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
    topic_focus = topic_focus if topic_focus else repository['name']

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
        subject, content = build_message_from_gitlog(user_profile, topic_focus,
                                                     payload['ref'], payload['commits'],
                                                     payload['before'], payload['after'],
                                                     payload['compare'],
                                                     payload['pusher']['name'],
                                                     forced=payload['forced'],
                                                     created=payload['created'])
    elif event == 'commit_comment':
        subject = topic_focus

        comment = payload.get('comment')
        action = u'[commented]({})'.format(comment['html_url'])
        content = get_commits_comment_action_message(
            comment['user']['login'],
            action,
            comment['html_url'].split('#', 1)[0],
            comment['commit_id'],
            comment['body'],
        )

    else:
        raise UnknownEventType(force_str(u'Event %s is unknown and cannot be handled' % (event,)))

    return target_stream, subject, content

@authenticated_api_view(is_webhook=True)
@has_request_variables
def api_github_landing(request, user_profile, event=REQ(),
                       payload=REQ(validator=check_dict([])),
                       branches=REQ(default=''),
                       stream=REQ(default=''),
                       version=REQ(converter=to_non_negative_int, default=1),
                       commit_stream=REQ(default=''),
                       issue_stream=REQ(default=''),
                       exclude_pull_requests=REQ(converter=flexible_boolean, default=False),
                       exclude_issues=REQ(converter=flexible_boolean, default=False),
                       exclude_commits=REQ(converter=flexible_boolean, default=False),
                       emphasize_branch_in_topic=REQ(converter=flexible_boolean, default=False),
                       ):
    # type: (HttpRequest, UserProfile, Text, Mapping[Text, Any], Text, Text, int, Text, Text, bool, bool, bool, bool) -> HttpResponse

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
                                forged=False, subject_name=subject,
                                message_content=content)

def build_message_from_gitlog(user_profile, name, ref, commits, before, after, url, pusher, forced=None, created=None):
    # type: (UserProfile, Text, Text, List[Dict[str, str]], Text, Text, Text, Text, Optional[Text], Optional[Text]) -> Tuple[Text, Text]
    short_ref = re.sub(r'^refs/heads/', '', ref)
    subject = SUBJECT_WITH_BRANCH_TEMPLATE.format(repo=name, branch=short_ref)

    if re.match(r'^0+$', after):
        content = get_remove_branch_event_message(pusher, short_ref)
    # 'created' and 'forced' are github flags; the second check is for beanstalk
    elif (forced and not created) or (forced is None and len(commits) == 0):
        content = get_force_push_commits_event_message(pusher, url, short_ref, after[:7])
    else:
        commits = _transform_commits_list_to_common_format(commits)
        content = get_push_commits_event_message(pusher, url, short_ref, commits)

    return subject, content

def _transform_commits_list_to_common_format(commits):
    # type: (List[Dict[str, str]]) -> List[Dict[str, str]]
    new_commits_list = []
    for commit in commits:
        new_commits_list.append({
            'sha': commit.get('id'),
            'url': commit.get('url'),
            'message': commit.get('message'),
        })
    return new_commits_list
