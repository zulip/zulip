# See zulip/contrib_bots/lib/readme.md for instructions on running this code.
from __future__ import print_function
import logging
import http.client
from six.moves.urllib.request import urlopen
from google import search

# Uses Google's Client Library
#   pip install --upgrade google-api-python-client

def get_google_result(original_content):
    search_keywords = original_content.strip().split(' ', 1)[1]
    if search_keywords == 'help':
        help_message = "To use this bot start message with @google \
                        followed by what you want to search for. If \
                        found, Zulip will return the first search result \
                        on Google. An example message that could be sent is:\
                        '@google zulip' or '@google how to create a chatbot'."
        return help_message
    else:
        try:
            urls = search(search_keywords, stop=20)
            urlopen('http://216.58.192.142', timeout=1)
        except http.client.RemoteDisconnected as er:
            logging.exception(er)
            return 'Error: No internet connection. {}.'.format(er)
        except Exception as e:
            logging.exception(e)
            return 'Error: Search failed. {}.'.format(e)

        if not urls:
            return "No URLs returned by google."

        url = next(urls)

        return 'Success: {}'.format(url)

class GoogleSearchHandler(object):
    '''
    This plugin allows users to enter a search
    term in Zulip and get the top URL sent back
    to the context (stream or private) in which
    it was called. It looks for messages starting
    with @google.
    '''

    def usage(self):
        return '''
            This plugin will allow users to search
            for a given search term on Google from
            Zulip. Use '@google help' to get more
            information on the bot usage. Users
            should preface messages with @google.
            '''

    def triage_message(self, message, client):
        # return True if we want to (possibly) respond to this message

        original_content = message['content']

        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting google
        # search links.
        if message['display_recipient'] == 'google':
            return False

        return original_content.startswith('@google')

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_sender = message['sender_email']
        result = get_google_result(original_content)

        if message['type'] == 'private':
            client.send_message(dict(
                type='private',
                to=original_sender,
                content=result,
            ))
        else:
            client.send_message(dict(
                type=message['type'],
                to=message['display_recipient'],
                subject=message['subject'],
                content=result,
            ))

handler_class = GoogleSearchHandler

def test():
    try:
        urlopen('http://216.58.192.142', timeout=1)
        print("Success")
        return True
    except http.client.RemoteDisconnected as e:
        print('Error: {}'.format(e))
        return False

if __name__ == '__main__':
    test()

