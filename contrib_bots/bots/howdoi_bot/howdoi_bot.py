"""
This bot uses the python library `howdoi` which is not a
dependency of Zulip. To use this module, you will have to
install it in your local machine. In your terminal, enter
the following command:

    $ sudo pip install howdoi --upgrade

Note:
    * You might have to use `pip3` if you are using python 3.
    * The install command would also download any dependency
      required by `howdoi`.
"""

import sys
import logging
from textwrap import fill
try:
    from howdoi.howdoi import howdoi
except ImportError:
    logging.error("Dependency missing!!\n%s" % (__doc__))
    sys.exit(0)


class HowdoiHandler(object):
    '''
    This plugin facilitates searching Stack Overflow for
    techanical answers based on the Python library `howdoi`.
    To get the best possible answer, only include keywords
    in your questions.

    There are two possible commands:
    * @mention-bot howdowe > This would return the answer to the same
                 stream that it was called from.

    * @mention-bot howdoi > The bot would send a private message to the
                user containing the answer.

    By default, howdoi only returns the coding section of the
    first search result if possible, to see the full answer
    from Stack Overflow, append a '!' to the commands.
    (ie '@mention-bot howdoi!', '@mention-bot howdowe!')
    '''

    MAX_LINE_LENGTH = 85

    def usage(self):
        return '''
            This plugin will allow users to get techanical
            answers from Stackoverflow. Users should preface
            their questions with one of the following:

                * @mention-bot howdowe > Answer to the same stream
                * @mention-bot howdoi > Answer via private message

                * @mention-bot howdowe! OR @mention-bot howdoi! > Full answer from SO
            '''

    def line_wrap(self, string, length):
        lines = string.split("\n")

        wrapped = [(fill(line) if len(line) > length else line)
                   for line in lines]

        return "\n".join(wrapped).strip()

    def get_answer(self, command, query):
        question = query[len(command):].strip()
        result = howdoi(dict(
            query=question,
            num_answers=1,
            pos=1,
            all=command[-1] == '!',
            color=False
        ))
        _answer = self.line_wrap(result, HowdoiHandler.MAX_LINE_LENGTH)

        answer = "Answer to '%s':\n```\n%s\n```" % (question, _answer)

        return answer

    def handle_message(self, message, client, state_handler):
        question = message['content'].strip()

        if question.startswith('howdowe!'):
            client.send_message(dict(
                type='stream',
                to=message['display_recipient'],
                subject=message['subject'],
                content=self.get_answer('howdowe!', question)
            ))

        elif question.startswith('howdoi!'):
            client.send_message(dict(
                type='private',
                to=message['sender_email'],
                content=self.get_answer('howdoi!', question)
            ))

        elif question.startswith('howdowe'):
            client.send_message(dict(
                type='stream',
                to=message['display_recipient'],
                subject=message['subject'],
                content=self.get_answer('howdowe', question)
            ))

        elif question.startswith('howdoi'):
            client.send_message(dict(
                type='private',
                to=message['sender_email'],
                content=self.get_answer('howdoi', question)
            ))


handler_class = HowdoiHandler
