from typing import MutableMapping, Any, Optional
from django.conf import settings

import logging
import re
import json

from zerver.lib.validator import check_dict, check_list, check_string
from zerver.models import SubMessage


def do_widget_pre_save_actions(message: MutableMapping[str, Any]) -> None:
    if not settings.ALLOW_SUB_MESSAGES:
        return

    # this prevents errors of cyclical imports
    from zerver.lib.actions import do_set_user_display_setting
    content = message['message'].content
    user_profile = message['message'].sender

    if content == '/stats':
        message['message'].content = 'We are running **1 server**.'
        return

    if content == '/night':
        message['message'].content = 'Changed to night mode! To revert night mode, type `/day`.'
        do_set_user_display_setting(user_profile, 'night_mode', True)
        return

    if content == '/day':
        message['message'].content = 'Changed to day mode! To revert day mode, type `/night`.'
        do_set_user_display_setting(user_profile, 'night_mode', False)
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
        # We cannot trust any incoming content, so we catch
        # all exceptions and early-exit.
        try:
            widget_content = json.loads(widget_content)
        except Exception:
            logging.warning('API user sent invalid content')
            return

        try:
            widget_type = widget_content['widget_type']
            extra_data = widget_content['extra_data']
        except Exception:
            logging.warning('API user did not follow schema for widget_content.')
            return

        error_msg = check_widget_content(widget_type, extra_data)
        if error_msg:
            logging.warning('in widget: ' + error_msg)
            return

    m = re.match('/(zform) (.*)', content)
    if m:
        widget_type = m.group(1)
        flavor = m.group(2).strip()
        print('flavor', flavor)

        if flavor == 'convert':
            extra_data = dict(
                type='choices',
                heading='Let the bot do the math!',
                choices=[
                    dict(
                        tokens=[
                            dict(name='convert'),
                            dict(field='n', type='input'),
                            dict(name='feet to meters')
                        ],
                    ),
                    dict(
                        tokens=[
                            dict(name='convert'),
                            dict(field='n', type='input'),
                            dict(name='meters to feet')
                        ],
                    ),
                ],
            )
        elif flavor == 'quiz':
            extra_data = dict(
                type='choices',
                heading='What is the capitol of Maryland?',
                choices=[
                    dict(
                        type='multiple_choice',
                        shortcut='A',
                        answer='Annapolis',
                        reply='answer q123456 A',
                    ),
                    dict(
                        type='multiple_choice',
                        shortcut='B',
                        answer='Baltimore',
                        reply='answer q123456 B',
                    ),
                ],
            )
        else:
            extra_data = dict(
                type='choices',
                choices=[
                    dict(
                        tokens=[
                            dict(name='help')
                        ],
                    ),
                    dict(
                        tokens=[
                            dict(name='hello'),
                            dict(field='name', type='input'),
                            dict(name='how are you doing?')
                        ],
                    ),
                ],
            )

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

def check_widget_content(widget_type: str, data: object) -> Optional[str]:
    if not isinstance(data, dict):
        return 'data is not a dict'

    if widget_type == 'zform':

        if 'type' not in data:
            return 'zform is missing type field'

        if data['type'] == 'choices':
            check_choices = check_list(
                check_dict([
                    ('short_name', check_string),
                    ('long_name', check_string),
                    ('reply', check_string),
                ]),
            )

            checker = check_dict([
                ('heading', check_string),
                ('choices', check_choices),
            ])

            msg = checker('data', data)
            if msg:
                return msg

            return None

        return 'unknown zform type: ' + data['type']

    return 'unknown widget type: ' + widget_type
