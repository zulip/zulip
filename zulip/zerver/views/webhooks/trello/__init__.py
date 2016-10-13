# Webhooks for external integrations.
from __future__ import absolute_import
import ujson
from six import text_type
from typing import Mapping, Any, Tuple
from django.utils.translation import ugettext as _
from django.http import HttpRequest, HttpResponse
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.models import UserProfile, Client
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view

from .card_actions import SUPPORTED_CARD_ACTIONS, process_card_action
from .board_actions import SUPPORTED_BOARD_ACTIONS, process_board_action
from .exceptions import UnsupportedAction

@api_key_only_webhook_view('Trello')
@has_request_variables
def api_trello_webhook(request, user_profile, client, payload=REQ(argument_type='body'), stream=REQ(default='trello')):
    # type: (HttpRequest, UserProfile, Client, Mapping[str, Any], text_type) -> HttpResponse
    payload = ujson.loads(request.body)
    action_type = payload.get('action').get('type')
    try:
        subject, body = get_subject_and_body(payload, action_type)
    except UnsupportedAction:
        return json_error(_('Unsupported action_type: {action_type}'.format(action_type=action_type)))

    check_send_message(user_profile, client, 'stream', [stream], subject, body)
    return json_success()

def get_subject_and_body(payload, action_type):
    # type: (Mapping[str, Any], text_type) -> Tuple[text_type, text_type]
    if action_type in SUPPORTED_CARD_ACTIONS:
        return process_card_action(payload, action_type)
    if action_type in SUPPORTED_BOARD_ACTIONS:
        return process_board_action(payload, action_type)
    raise UnsupportedAction('{} if not supported'.format(action_type))
