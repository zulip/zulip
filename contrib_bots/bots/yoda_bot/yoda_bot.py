# See readme.md for instructions on running this code.

from __future__ import print_function
import os
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
            Users should preface messages with '@yoda'.

            Before running this, make sure to get a Mashape Api token.
            Instructions are in the 'readme.md' file.
            Store it in the 'yoda_bot.config' file.
            The 'yoda_bot.config' file should be located at '~/yoda_bot.config'.
            Example input:
            @yoda You will learn how to speak like me someday.
            '''


class ApiKeyError(Exception):
    '''raise this when there is an error with the Mashape Api Key'''


class YodaSpeakHandler(object):
    '''
    This bot will allow users to translate a sentence into 'Yoda speak'.
    It looks for messages starting with '@yoda'.
    '''

    def usage(self):
        return '''
            This bot will allow users to translate a sentence into
            'Yoda speak'.
            Users should preface messages with '@yoda'.

            Before running this, make sure to get a Mashape Api token.
            Instructions are in the 'readme.md' file.
            Store it in the 'yoda_bot.config' file.
            The 'yoda_bot.config' file should be located at '~/yoda_bot.config'.
            Example input:
            @yoda You will learn how to speak like me someday.
            '''

    def triage_message(self, message):
        original_content = message['content']

        return original_content.startswith('@yoda')

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        stream = message['display_recipient']
        subject = message['subject']

        # this handles the message if its starts with @yoda
        if original_content.startswith('@yoda'):
            handle_input(client, original_content, stream, subject)

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
    # replaces the '@yoda' with nothing, so that '@yoda' doesn't get sent to the api
    message_content = original_content.replace('@yoda', '')
    # gets rid of whitespace around the edges, so that they aren't a problem in the future
    message_content = message_content.strip()
    # replaces all spaces with '+' to be in the format the api requires
    sentence = message_content.replace(' ', '+')
    return sentence


def handle_input(client, original_content, stream, subject):

    if is_help(original_content):
        send_message(client, HELP_MESSAGE, stream, subject)

    else:
        sentence = format_input(original_content)
        try:
            reply_message = send_to_yoda_api(sentence, get_api_key())

        except ssl.SSLError or TypeError:
            reply_message = 'The service is temporarily unavailable, please try again.'
            logging.error(reply_message)

        except ApiKeyError:
            reply_message = 'Invalid Api Key. Did you follow the instructions in the ' \
                            '`readme.md` file?'
            logging.error(reply_message)

        send_message(client, reply_message, stream, subject)


def get_api_key():
    # function for getting Mashape api key
    home = os.path.expanduser('~')
    with open(home + '/yoda_bot.config') as api_key_file:
        api_key = api_key_file.read().strip()
    return api_key


def send_message(client, message, stream, subject):
    # function for sending a message
    client.send_message(dict(
        type='stream',
        to=stream,
        subject=subject,
        content=message
    ))


def is_help(original_content):
    # replaces the '@yoda' with nothing, so that '@yoda' doesn't get sent to the api
    message_content = original_content.replace('@yoda', '')
    # gets rid of whitespace around the edges, so that they aren't a problem in the future
    message_content = message_content.strip()
    if message_content == 'help':
        return True
    else:
        return False
