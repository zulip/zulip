from __future__ import absolute_import
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success
from zerver.decorator import api_key_only_webhook_view, REQ, has_request_variables


class UnknownEventType(Exception):
    pass

def get_opened_pull_request_subject_and_body(payload):
    pull_request = payload['pull_request']
    subject = 'Pull Request opened'
    body = "{} opened [PR #{} {}]({}).".format(
        pull_request['user']['login'],
        payload['number'],
        pull_request['title'],
        pull_request['html_url']
    )
    return subject, body

def get_closed_pull_request_subject_and_body(payload):
    subject = 'Pull Request closed'
    pull_request = payload['pull_request']
    action = 'merged' if pull_request['merged'] else 'closed without merge'
    body = "{} {} [PR #{} {}]({}).".format(
        pull_request['user']['login'],
        action,
        payload['number'],
        pull_request['title'],
        pull_request['html_url']
    )
    return subject, body

def get_membership_subject_and_body(payload):
    action = payload['action']
    member = payload['member']
    team = payload['team']

    subject = "New member {}".format(action)
    body = "{} {} {} to [{}]({}) team.".format(
        payload['sender']['login'],
        action,
        member['login'],
        team['name'],
        team['url']
    )
    return subject, body

def get_member_subject_and_body(payload):
    action = payload['action']
    member = payload['member']

    subject = "Collaborator {}".format(action)
    body = "{} {} {} as a collaborator to [{}]({}).".format(
        payload['sender']['login'],
        action,
        member['login'],
        get_repo_name(payload),
        payload['repository']['html_url']
    )
    return subject, body

def get_issue_subject_and_body(payload):
    action = payload['action']
    issue = payload['issue']
    subject = "Issue {}".format(action)
    body = "{} {} [{}]({}).".format(
        payload['sender']['login'],
        action,
        issue['title'],
        issue['url']
    )
    return subject, body

def get_issue_comment_subject_and_body(payload):
    action = payload['action']
    issue = payload['issue']
    subject = "Comment {}".format(action)
    body = "{} {} comment in [{}]({}).".format(
        payload['sender']['login'],
        action,
        issue['title'],
        issue['url']
    )
    return subject, body

def get_fork_subject_and_body(payload):
    forkee = payload['forkee']
    subject = "Repository forked"
    body = "{} forked [{}]({}).".format(
        payload['sender']['login'],
        forkee['name'],
        forkee['url']
    )
    return subject, body

def get_deployment_subject_and_body(payload):
    repo_name = get_repo_name(payload)
    deployment = payload['deployment']
    subject = '{}: deployment was created'.format(repo_name)
    body = '{} created [{}]({}) task.'.format(
        payload['sender']['login'],
        deployment['task'],
        deployment['url']
    )
    return subject, body

def get_delete_subject_and_body(payload):
    repo_name = get_repo_name(payload)
    ref_type = payload['ref_type']
    subject = '{}: {} was deleted'.format(repo_name, ref_type)
    body = '{} deleted {} {}.'.format(payload['sender']['login'], ref_type, payload['ref'])
    return subject, body

def get_create_subject_and_body(payload):
    repo_name = get_repo_name(payload)
    ref_type = payload['ref_type']
    subject = '{}: {} was created'.format(repo_name, ref_type)
    body = '{} created {}'.format(payload['sender']['login'], ref_type)
    if ref_type != 'repository':
        body += ' {}'.format(payload['ref'])
    body += '.'
    return subject, body

def get_commit_comment_subject_and_body(payload):
    comment = payload['comment']
    repo_name = get_repo_name(payload)
    subject = '{}: commit {}'.format(repo_name, comment['commit_id'])
    body = '{} [commented]({})'.format(comment['user']['login'], comment['html_url'])
    comment_line = comment['line']
    if comment_line is not None:
        body += ' on `{}`, line {}'.format(comment['path'], comment['line'])

    body += '\n\n~~~ quote\n{}\n~~~'.format(comment['body'],)
    return subject, body

def get_repo_name(payload):
    return payload['repository']['name']

EVENT_FUNCTION_MAPPER = {
    'commit_comment': get_commit_comment_subject_and_body,
    'create': get_create_subject_and_body,
    'delete': get_delete_subject_and_body,
    'deployment': get_deployment_subject_and_body,
    'fork': get_fork_subject_and_body,
    'issue_comment': get_issue_comment_subject_and_body,
    'issue': get_issue_subject_and_body,
    'member': get_member_subject_and_body,
    'membership': get_membership_subject_and_body,
    'opened_pull_request': get_opened_pull_request_subject_and_body,
    'closed_pull_request': get_closed_pull_request_subject_and_body,
}

@api_key_only_webhook_view("GithubWebhook")
@has_request_variables
def api_github_webhook(request, user_profile, client, stream=REQ(default='github'), payload=REQ(argument_type='body')):
    event = get_event(request, payload)
    subject, body = EVENT_FUNCTION_MAPPER[event](payload)
    check_send_message(user_profile, client, 'stream', [stream], subject, body)
    return json_success()

def get_event(request, payload):
    event = request.META['HTTP_X_GITHUB_EVENT']
    if event == 'pull_request':
        action = payload['action']
        if action == 'opened':
            return 'opened_pull_request'
        if action == 'closed':
            return 'closed_pull_request'
        raise UnknownEventType(u'Event pull_request with {} action is unsupported'.format(action))
    elif event in EVENT_FUNCTION_MAPPER.keys():
        return event
    raise UnknownEventType(u'Event {} is unknown and cannot be handled'.format(event))