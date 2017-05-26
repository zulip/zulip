# Webhooks for external integrations.
from __future__ import absolute_import
import ujson
from typing import Mapping, Any, Tuple, Text
from django.utils.translation import ugettext as _
from django.http import HttpRequest, HttpResponse
from zerver.lib.actions import check_send_message
from zerver.decorator import return_success_on_head_request
from zerver.lib.response import json_success, json_error
from zerver.models import UserProfile
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view

from .card_actions import SUPPORTED_CARD_ACTIONS, process_card_action
from .board_actions import SUPPORTED_BOARD_ACTIONS, process_board_action
from .exceptions import UnsupportedAction

@api_key_only_webhook_view('Trello')
@return_success_on_head_request
@has_request_variables
def api_trello_webhook(request, user_profile, payload=REQ(argument_type='body'), stream=REQ(default='trello')):
    # type: (HttpRequest, UserProfile, Mapping[str, Any], Text) -> HttpResponse
    payload = ujson.loads(request.body)
    action_type = payload['action'].get('type')
    try:
        subject, body = get_subject_and_body(payload, action_type)
    except UnsupportedAction:
        return json_error(_('Unsupported action_type: {action_type}'.format(action_type=action_type)))

    check_send_message(user_profile, request.client, 'stream', [stream], subject, body)
    return json_success()

def get_subject_and_body(payload, action_type):
    # type: (Mapping[str, Any], Text) -> Tuple[Text, Text]
    if action_type in SUPPORTED_CARD_ACTIONS:
        return process_card_action(payload, action_type)
    if action_type in SUPPORTED_BOARD_ACTIONS:
        return process_board_action(payload, action_type)
    raise UnsupportedAction('{} if not supported'.format(action_type))
