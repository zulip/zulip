# Webhooks for external integrations.
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MESSAGE_TEMPLATE = """
Build update (see [build log]({build_log_url})):
* **Author**: {author}
* **Commit**: [{commit_id}]({commit_url})
* **Status**: {status} {emoji}
""".strip()

@webhook_view('SolanoLabs')
@has_request_variables
def api_solano_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    event = payload.get('event')
    topic = 'build update'
    if event == 'test':
        return handle_test_event(request, user_profile, topic)
    try:
        author = payload['committers'][0]
    except KeyError:
        author = 'Unknown'
    status = payload['status']
    build_log = payload['url']
    repository = payload['repository']['url']
    commit_id = payload['commit_id']

    good_status = ['passed']
    bad_status  = ['failed', 'error']
    neutral_status = ['running']
    emoji = ''
    if status in good_status:
        emoji = ':thumbs_up:'
    elif status in bad_status:
        emoji = ':thumbs_down:'
    elif status in neutral_status:
        emoji = ':arrows_counterclockwise:'

    # If the service is not one of the following, the URL is of the repository home, not the individual
    # commit itself.
    commit_url = repository.split('@')[1]
    if 'github' in repository:
        commit_url += f'/commit/{commit_id}'
    elif 'bitbucket' in repository:
        commit_url += f'/commits/{commit_id}'
    elif 'gitlab' in repository:
        commit_url += f'/pipelines/{commit_id}'

    body = MESSAGE_TEMPLATE.format(
        author=author, build_log_url=build_log,
        commit_id=commit_id[:7], commit_url=commit_url,
        status=status, emoji=emoji,
    )

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()

def handle_test_event(request: HttpRequest, user_profile: UserProfile,
                      topic: str) -> HttpResponse:
    body = 'Solano webhook set up correctly.'
    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()
