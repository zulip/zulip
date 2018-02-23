import re
import json

from zerver.models import SubMessage

def enable_widgets_for_message(message):
    '''
    This is experimental code that only works with the
    webapp for now.
    '''
    content = message['message'].content
    sender_id = message['message'].sender_id
    message_id = message['message'].id

    widget_type = None
    extra_data = None
    if content in ['/poll', '/tictactoe']:
        widget_type = content[1:]

    m = re.match('/(form_letter) (.*)', content)
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
