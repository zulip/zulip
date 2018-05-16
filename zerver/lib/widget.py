from typing import MutableMapping, Any
from django.conf import settings

import re
import json

from zerver.models import SubMessage


def get_fixed_content_for_widget(content: str) -> str:
    if not settings.ALLOW_SUB_MESSAGES:
        return content

    if content == '/stats':
        return 'We are running **1 server**.'

    return content

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
