#See readme.md for instructions on running this code.

from __future__ import print_function
import os
import logging
import ssl
import sys
import json

try:
    import requests
except ImportError as e:
    logging.error("Dependency missing!!\n{}".format(e))
    sys.exit(0)

HELP_MESSAGE = '''
            This bot looks up slang terms in the Urban Dictionary.
            Users should preface messages with '@mention-bot'.

            Before running this, make sure to get a Mashape Api token.
            Instructions are in the 'readme.md' file.
            Store it in the 'udlookup.config' file.
            The 'udlookup.config' file should be located at '~/udlookup.config'.
            Example input:
            @mention-bot You will learn how to speak like me someday.
            '''


class ApiKeyError(Exception):
    '''raise this when there is an error with the Mashape Api Key'''


class UDlookupHandler(object):
    '''
    This bot looks up slang words in the Urban Dictionary.
    It looks for messages starting with '@mention-bot'.
    '''

    def usage(self):
        return '''
            This bot looks up slang words in the Urban Dictionary.
            Users should preface messages with '@mention-bot'.

            Before running this, make sure to get a Mashape Api token.
            Instructions are in the 'readme.md' file.
            Store it in the 'udlookup.config' file.
            The 'udlookup.config' file should be located at '~/udlookup.config'.
            Example input:
            @mention-bot You will learn how to speak like me someday.
            '''

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        stream = message['display_recipient']
        subject = message['subject']

        handle_input(client, original_content, stream, subject)

handler_class = UDlookupHandler


def send_to_udlookup_api(sentence, api_key):
    # function for sending sentence to api

    response = requests.get("https://mashape-community-urban-dictionary.p.mashape.com/define?term=" + sentence,
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

def format_output(retrieved_data):
    data = json.loads(retrieved_data)
    return data['list'][0]['definition']

def handle_input(client, original_content, stream, subject):

    if is_help(original_content):
        send_message(client, HELP_MESSAGE, stream, subject)

    else:
        sentence = format_input(original_content)
        try:
            reply_data = send_to_udlookup_api(sentence, get_api_key())
            reply_message = format_output(reply_data)

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
    with open(home + '/udlookup.config') as api_key_file:
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
    # gets rid of whitespace around the edges, so that they aren't a problem in the future
    message_content = original_content.strip()
    if message_content == 'help':
        return True
    else:
        return False
