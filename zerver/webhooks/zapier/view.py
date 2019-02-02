from typing import Any, Dict

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_private_message_from_emails
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message, \
    validate_extract_webhook_http_header
from zerver.models import UserProfile

@api_key_only_webhook_view('Zapier', notify_bot_owner_on_invalid_json=False)
@has_request_variables
def api_zapier_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    # A request with the ZapierZulipApp user agent is a request from
    # the official Zulip app for Zapier
    user_agent = validate_extract_webhook_http_header(
        request, 'USER_AGENT', 'Zapier', fatal=False)
    if user_agent == 'ZapierZulipApp':
        event_type = payload.get('type')
        if event_type == 'auth':
            return json_success()
        elif event_type == 'stream':
            check_send_webhook_message(
                request, user_profile,
                payload['topic'], payload['content']
            )
        elif event_type == 'private':
            check_send_private_message_from_emails(
                user_profile, request.client,
                payload['to'], payload['content']
            )

        return json_success()

    topic = payload.get('topic')
    content = payload.get('content')

    if topic is None:
        topic = payload.get('subject')  # Backwards-compatibility
        if topic is None:
            return json_error(_("Topic can't be empty"))

    if content is None:
        return json_error(_("Content can't be empty"))

    check_send_webhook_message(request, user_profile, topic, content)
    return json_success()
