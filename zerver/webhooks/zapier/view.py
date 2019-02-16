from typing import Any, Dict, List

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_private_message_from_emails, \
    do_get_streams
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message, \
    validate_extract_webhook_http_header
from zerver.models import UserProfile
from zerver.views.users import do_get_members

def get_available_streams_for_bot_owner(bot: UserProfile) -> List[str]:
    assert bot.bot_owner is not None
    streams = do_get_streams(bot.bot_owner)
    stream_names = [s['name'] for s in streams]
    return stream_names

def get_all_users(user_profile: UserProfile) -> Dict[str, Any]:
    members = do_get_members(user_profile)
    # The format raw:label is what Zapier expects, where `raw` (user ID)
    # is the value associated with the `label` (name of user) that the
    # message will be sent to.
    result = {member['user_id']: member['full_name'] for member in members}
    return result

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
            # The bot's details are used by Zapier to format a connection
            # label for users to be able to distinguish between different
            # Zulip bots and API keys in their UI
            return json_success({
                'bot_name': user_profile.full_name,
                'bot_email': user_profile.email,
                'bot_id': user_profile.id
            })
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
        elif event_type == 'list_streams':
            # The list of stream names is used to pre-populate input fields
            # in Zapier's UI
            return json_success({
                'streams': get_available_streams_for_bot_owner(user_profile)
            })
        elif event_type == 'list_users':
            # The list of users is used to pre-populate input fields in
            # Zapier's UI
            return json_success({
                'users': get_all_users(user_profile)
            })

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
