from __future__ import absolute_import
from __future__ import print_function
import requests
import logging
import re

# See readme.md for instructions on running this code.

class WikipediaHandler(object):
    '''
    This plugin facilitates searching Wikipedia for a
    specific key term and returns the top article from the
    search. It looks for messages starting with '@mention-bot'

    In this example, we write all Wikipedia searches into
    the same stream that it was called from, but this code
    could be adapted to write Wikipedia searches to some
    kind of external issue tracker as well.
    '''

    def usage(self):
        return '''
            This plugin will allow users to directly search
            Wikipedia for a specific key term and get the top
            article that is returned from the search. Users
            should preface searches with "@mention-bot".
            '''

    def handle_message(self, message, client, state_handler):
        bot_response = self.get_bot_wiki_response(message, client)
        if message['type'] == 'private':
            client.send_message(dict(
                type='private',
                to=message['sender_email'],
                content=bot_response,
            ))
        else:
            client.send_message(dict(
                type='stream',
                to=message['display_recipient'],
                subject=message['subject'],
                content=bot_response,
            ))

    def get_bot_wiki_response(self, message, client):
        query = message['content']
        query_wiki_link = ('https://en.wikipedia.org/w/api.php?action=query&'
                           'list=search&srsearch=%s&format=json' % (query,))
        try:
            data = requests.get(query_wiki_link)
        except requests.exceptions.RequestException:
            logging.error('broken link')
            return

        if data.status_code != 200:
            logging.error('unsuccessful data')
            return

        new_content = 'For search term "' + query
        if len(data.json()['query']['search']) == 0:
            new_content = 'I am sorry. The search term you provided is not found :slightly_frowning_face:'
        else:
            search_string = data.json()['query']['search'][0]['title'].replace(' ', '_')
            url = 'https://en.wikipedia.org/wiki/' + search_string
            new_content = new_content + '", ' + url
        return new_content


handler_class = WikipediaHandler
