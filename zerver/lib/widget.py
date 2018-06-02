from typing import MutableMapping, Any
from django.conf import settings

import re
import json

from zerver.models import SubMessage


def do_widget_pre_save_actions(message: MutableMapping[str, Any]) -> None:
    if not settings.ALLOW_SUB_MESSAGES:
        return

    content = message['message'].content

    if content == '/stats':
        message['message'].content = 'We are running **1 server**.'
        return

def do_widget_post_save_actions(message: MutableMapping[str, Any]) -> None:
    '''
    This is experimental code that only works with the
    webapp for now.
    '''
    if not settings.ALLOW_SUB_MESSAGES:
        return
    content = message['message'].content
    sender_id = message['message'].sender_id
    message_id = message['message'].id

    widget_type = None
    extra_data = None
    if content in ['/poll', '/tictactoe']:
        widget_type = content[1:]

    widget_content = message.get('widget_content')
    if widget_content is not None:
        # Note that we validate this data in check_message,
        # so we can trust it here.
        widget_type = widget_content['widget_type']
        extra_data = widget_content['extra_data']

    if widget_type:
        content = dict(
            widget_type=widget_type,
            extra_data=extra_data
        )
        submessage = SubMessage(
            sender_id=sender_id,
            message_id=message_id,
            msg_type='widget',
            content=json.dumps(content),
        )
        submessage.save()
        message['submessages'] = SubMessage.get_raw_db_rows([message_id])
