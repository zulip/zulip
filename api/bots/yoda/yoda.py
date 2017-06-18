# See readme.md for instructions on running this code.

from __future__ import print_function
import logging
import ssl
import sys
try:
    import requests
except ImportError as e:
    logging.error("Dependency missing!!\n{}".format(e))
    sys.exit(0)

HELP_MESSAGE = '''
            This bot allows users to translate a sentence into
            'Yoda speak'.
            Users should preface messages with '@mention-bot'.

            Before running this, make sure to get a Mashape Api token.
            Instructions are in the 'readme.md' file.
            Store it in the 'yoda.config' file.
            The 'yoda.config' file should be located at '~/yoda.config'.
            Example input:
            @mention-bot You will learn how to speak like me someday.
            '''


class ApiKeyError(Exception):
    '''raise this when there is an error with the Mashape Api Key'''


class YodaSpeakHandler(object):
    '''
    This bot will allow users to translate a sentence into 'Yoda speak'.
    It looks for messages starting with '@mention-bot'.
    '''

    def initialize(self, bot_handler):
        self.api_key = bot_handler.get_config_info('yoda')['api_key']

    def usage(self):
        return '''
            This bot will allow users to translate a sentence into
            'Yoda speak'.
            Users should preface messages with '@mention-bot'.

            Before running this, make sure to get a Mashape Api token.
            Instructions are in the 'readme.md' file.
            Store it in the 'yoda.conf' file.
            The 'yoda.conf' file should be located in this bot's directory.
            Example input:
            @mention-bot You will learn how to speak like me someday.
            '''

    def handle_message(self, message, bot_handler, state_handler):
        handle_input(message, bot_handler)

handler_class = YodaSpeakHandler


def send_to_yoda_api(sentence, api_key):
    # function for sending sentence to api

    response = requests.get("https://yoda.p.mashape.com/yoda?sentence=" + sentence,
                            headers={
                                "X-Mashape-Key": api_key,
                                "Accept": "text/plain"
                            }
                            )

    if response.status_code == 200:
        return response.text
    if response.status_code == 403:
        raise ApiKeyError
    else:
        error_message = response.text['message']
        logging.error(error_message)
        error_code = response.status_code
        error_message = error_message + 'Error code: ' + error_code +\
            ' Did you follow the instructions in the `readme.md` file?'
        return error_message


def format_input(original_content):
    # gets rid of whitespace around the edges, so that they aren't a problem in the future
    message_content = original_content.strip()
    # replaces all spaces with '+' to be in the format the api requires
    sentence = message_content.replace(' ', '+')
    return sentence


def handle_input(message, bot_handler):

    original_content = message['content']
    if is_help(original_content):
        bot_handler.send_reply(message, HELP_MESSAGE)

    else:
        sentence = format_input(original_content)
        try:
            reply_message = send_to_yoda_api(sentence, handler_class.api_key)

        except ssl.SSLError or TypeError:
            reply_message = 'The service is temporarily unavailable, please try again.'
            logging.error(reply_message)

        except ApiKeyError:
            reply_message = 'Invalid Api Key. Did you follow the instructions in the ' \
                            '`readme.md` file?'
            logging.error(reply_message)

        bot_handler.send_reply(message, reply_message)

def send_message(bot_handler, message, stream, subject):
    # function for sending a message
    bot_handler.send_message(dict(
        type='stream',
        to=stream,
        subject=subject,
        content=message
    ))


def is_help(original_content):
    # gets rid of whitespace around the edges, so that they aren't a problem in the future
    message_content = original_content.strip()
    if message_content == 'help':
        return True
    else:
        return False
