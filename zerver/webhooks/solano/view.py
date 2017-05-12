# Webhooks for external integrations.
from __future__ import absolute_import

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.models import UserProfile, Client

from typing import Any, Dict


@api_key_only_webhook_view('SolanoLabs')
@has_request_variables
def api_solano_webhook(request, user_profile,
                       stream=REQ(default='solano labs'),
                       topic=REQ(default='build update'),
                       payload=REQ(argument_type='body')):
    # type: (HttpRequest, UserProfile, str, str, Dict[str, Any]) -> HttpResponse
    event = payload.get('event')
    if event == 'test':
        return handle_test_event(user_profile, request.client, stream, topic)
    try:
        try:
            author = payload['committers'][0]
        except KeyError:
            author = 'Unknown'
        status = payload['status']
        build_log = payload['url']
        repository = payload['repository']['url']
        commit_id = payload['commit_id']
    except KeyError as e:
        return json_error(_('Missing key {} in JSON').format(str(e)))

    good_status = ['passed']
    bad_status  = ['failed', 'error']
    neutral_status = ['running']
    emoji = ''
    if status in good_status:
        emoji = ':thumbsup:'
    elif status in bad_status:
        emoji = ':thumbsdown:'
    elif status in neutral_status:
        emoji = ':arrows_counterclockwise:'
    else:
        emoji = "(No emoji specified for status '%s'.)" % (status,)

    template = (
        u'Author: {}\n'
        u'Commit: [{}]({})\n'
        u'Build status: {} {}\n'
        u'[Build Log]({})')

    # If the service is not one of the following, the url is of the repository home, not the individual
    # commit itself.
    commit_url = repository.split('@')[1]
    if 'github' in repository:
        commit_url += '/commit/{}'.format(commit_id)
    elif 'bitbucket' in repository:
        commit_url += '/commits/{}'.format(commit_id)
    elif 'gitlab' in repository:
        commit_url += '/pipelines/{}'.format(commit_id)

    body = template.format(author, commit_id, commit_url, status, emoji, build_log)

    check_send_message(user_profile, request.client, 'stream', [stream], topic, body)
    return json_success()

def handle_test_event(user_profile, client, stream, topic):
    # type: (UserProfile, Client, str, str) -> HttpResponse
    body = 'Solano webhook set up correctly'
    check_send_message(user_profile, client, 'stream', [stream], topic, body)
    return json_success()
