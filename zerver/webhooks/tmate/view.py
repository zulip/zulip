# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_rest_api_view, webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

import json

def api_tmate_webhook_register(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    json_body = json.loads(request.body)

    subject_template = "Session {entity_id}"
    subject = subject_template.format(**json_body)

    message = 'There is a new session registered.\nConnect with: `%s` or [this link](%s).' % (json_body['params']['ssh_cmd_fmt'] % json_body['params']['stoken'], json_body['params']['web_url_fmt'] % json_body['params']['stoken'])

    check_send_webhook_message(request, user_profile, subject, message)
    return json_success()

def api_tmate_webhook_join(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    json_body = json.loads(request.body)

    subject_template = "Session: {entity_id}"
    subject = subject_template.format(**json_body)

    message = 'Someone from %s id %s joined through %s.' % (json_body['params']['ip_address'], json_body['params']['id'], json_body['params']['type'])

    check_send_webhook_message(request, user_profile, subject, message)
    return json_success()

def api_tmate_webhook_left(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    json_body = json.loads(request.body)

    subject_template = "Session: {entity_id}"
    subject = subject_template.format(**json_body)

    message = 'Someone with id %s left.' % json_body['params']['id']

    check_send_webhook_message(request, user_profile, subject, message)
    return json_success()

def api_tmate_webhook_close(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    json_body = json.loads(request.body)

    subject_template = "Session: {entity_id}"
    subject = subject_template.format(**json_body)

    message = 'Session closed.'

    check_send_webhook_message(request, user_profile, subject, message)
    return json_success()

@webhook_view('Tmate')
@has_request_variables
def api_tmate_webhook(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    json_body = json.loads(request.body)

    if json_body['type'] == "session_register":
        return api_tmate_webhook_register(request, user_profile)
    elif json_body['type'] == "session_join":
        return api_tmate_webhook_join(request, user_profile)
    elif json_body['type'] == "session_left":
        return api_tmate_webhook_left(request, user_profile)
    elif json_body['type'] == "session_close":
        return api_tmate_webhook_close(request, user_profile)
    else:
        return
