from __future__ import absolute_import
from django.conf import settings
from zerver.models import get_client, UserProfile
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict
from zerver.decorator import authenticated_api_view, REQ, has_request_variables, to_non_negative_int, flexible_boolean
from zerver.views.messages import send_message_backend
import logging
import re
import ujson

from six import text_type
from typing import Any, Mapping, Optional, Sequence, Tuple
from zerver.lib.str_utils import force_str
from django.http import HttpRequest, HttpResponse

COMMITS_IN_LIST_LIMIT = 10
ZULIP_TEST_REPO_NAME = 'zulip-test'
ZULIP_TEST_REPO_ID = 6893087

def is_test_repository(repository):
    # type: (Mapping[text_type, Any]) -> bool
    return repository['name'] == ZULIP_TEST_REPO_NAME and repository['id'] == ZULIP_TEST_REPO_ID

class UnknownEventType(Exception):
    pass


def github_generic_subject(noun, topic_focus, blob):
    # type: (text_type, text_type, Mapping[text_type, Any]) -> text_type
    # issue and pull_request objects have the same fields we're interested in
    return u'%s: %s %d: %s' % (topic_focus, noun, blob['number'], blob['title'])

def github_generic_content(noun, payload, blob):
    # type: (text_type, Mapping[text_type, Any], Mapping[text_type, Any]) -> text_type
    action = 'synchronized' if payload['action'] == 'synchronize' else payload['action']

    # issue and pull_request objects have the same fields we're interested in
    content = (u'%s %s [%s %s](%s)'
               % (payload['sender']['login'],
                  action,
                  noun,
                  blob['number'],
                  blob['html_url']))
    if payload['action'] in ('opened', 'reopened'):
        content += u'\n\n~~~ quote\n%s\n~~~' % (blob['body'],)
    return content


def api_github_v1(user_profile, event, payload, branches, stream, **kwargs):
    # type: (UserProfile, text_type, Mapping[text_type, Any], text_type, text_type, **Any) -> Tuple[text_type, text_type, text_type]
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
    # type: (UserProfile, text_type, Mapping[text_type, Any], text_type, text_type, text_type, text_type, Optional[text_type]) -> Tuple[text_type, text_type, text_type]
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
        pull_req = payload['pull_request']
        subject = github_generic_subject('pull request', topic_focus, pull_req)
        content = github_generic_content('pull request', payload, pull_req)
    elif event == 'issues':
        # in v1, we assume that this stream exists since it is
        # deprecated and the few realms that use it already have the
        # stream
        target_stream = issue_stream
        issue = payload['issue']
        subject = github_generic_subject('issue', topic_focus, issue)
        content = github_generic_content('issue', payload, issue)
    elif event == 'issue_comment':
        # Comments on both issues and pull requests come in as issue_comment events
        issue = payload['issue']
        if 'pull_request' not in issue or issue['pull_request']['diff_url'] is None:
            # It's an issues comment
            target_stream = issue_stream
            noun = 'issue'
        else:
            # It's a pull request comment
            noun = 'pull request'

        subject = github_generic_subject(noun, topic_focus, issue)
        comment = payload['comment']
        content = (u'%s [commented](%s) on [%s %d](%s)\n\n~~~ quote\n%s\n~~~'
                   % (comment['user']['login'],
                      comment['html_url'],
                      noun,
                      issue['number'],
                      issue['html_url'],
                      comment['body']))
    elif event == 'push':
        subject, content = build_message_from_gitlog(user_profile, topic_focus,
                                                     payload['ref'], payload['commits'],
                                                     payload['before'], payload['after'],
                                                     payload['compare'],
                                                     payload['pusher']['name'],
                                                     forced=payload['forced'],
                                                     created=payload['created'])
    elif event == 'commit_comment':
        comment = payload['comment']
        subject = u'%s: commit %s' % (topic_focus, comment['commit_id'])

        content = (u'%s [commented](%s)'
                   % (comment['user']['login'],
                      comment['html_url']))

        if comment['line'] is not None:
            content += u' on `%s`, line %d' % (comment['path'], comment['line'])

        content += u'\n\n~~~ quote\n%s\n~~~' % (comment['body'],)

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
    # type: (HttpRequest, UserProfile, text_type, Mapping[text_type, Any], text_type, text_type, int, text_type, text_type, bool, bool, bool, bool) -> HttpResponse

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

def build_commit_list_content(commits, branch, compare_url, pusher):
    # type: (Sequence[Mapping[text_type, Any]], text_type, Optional[text_type], text_type) -> text_type
    if compare_url is not None:
        push_text = u'[pushed](%s)' % (compare_url,)
    else:
        push_text = u'pushed'
    content = (u'%s %s to branch %s\n\n'
               % (pusher,
                  push_text,
                  branch))
    num_commits = len(commits)
    truncated_commits = commits[:COMMITS_IN_LIST_LIMIT]
    for commit in truncated_commits:
        short_id = commit['id'][:7]
        (short_commit_msg, _, _) = commit['message'].partition('\n')
        content += u'* [%s](%s): %s\n' % (short_id, commit['url'],
                                         short_commit_msg)
    if num_commits > COMMITS_IN_LIST_LIMIT:
        content += (u'\n[and %d more commits]'
                    % (num_commits - COMMITS_IN_LIST_LIMIT,))

    return content

def build_message_from_gitlog(user_profile, name, ref, commits, before, after, url, pusher, forced=None, created=None):
    # type: (UserProfile, text_type, text_type, Sequence[Mapping[text_type, Any]], text_type, text_type, text_type, text_type, Optional[text_type], Optional[text_type]) -> Tuple[text_type, text_type]
    short_ref = re.sub(r'^refs/heads/', '', ref)
    subject = name

    if re.match(r'^0+$', after):
        content = u'%s deleted branch %s' % (pusher,
                                            short_ref)
    # 'created' and 'forced' are github flags; the second check is for beanstalk
    elif (forced and not created) or (forced is None and len(commits) == 0):
        content = (u'%s [force pushed](%s) to branch %s.  Head is now %s'
                   % (pusher,
                      url,
                      short_ref,
                      after[:7]))
    else:
        content = build_commit_list_content(commits, short_ref, url, pusher)

    return subject, content
