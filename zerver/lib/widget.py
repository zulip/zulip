from typing import MutableMapping, Any, Optional, List, Tuple
from django.conf import settings

import re
import json

from zerver.models import SubMessage


def get_widget_data(content: str) -> Tuple[Optional[str], Optional[str]]:
    valid_widget_types = ['tictactoe', 'poll', 'todo']
    tokens = content.split(' ')

    # tokens[0] will always exist
    if tokens[0].startswith('/'):
        widget_type = tokens[0][1:]
        if widget_type in valid_widget_types:
            extra_data = get_extra_data_from_widget_type(tokens, widget_type)
            return widget_type, extra_data

    return None, None

def get_extra_data_from_widget_type(tokens: List[str],
                                    widget_type: Optional[str]) -> Any:
    if widget_type == 'poll':
        # This is used to extract the question from the poll command.
        # The command '/poll question' will pre-set the question in the poll
        question = ' '.join(tokens[1:])
        if not question:
            question = ''
        extra_data = {'question': question}
        return extra_data
    return None

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

    widget_type, extra_data = get_widget_data(content)
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
