from __future__ import absolute_import
from __future__ import print_function
import requests
import logging

# See readme.md for instructions on running this code.

class WikipediaHandler(object):
    '''
    This plugin facilitates searching Wikipedia for a
    specific key term and returns the top article from the
    search. It looks for messages starting with '@wikipedia'
     or '@wiki'.

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
            should preface searches with "@wikipedia" or
            "@wiki".
            '''

    def triage_message(self, message, client):
        # return True iff we want to (possibly) response to this message

        original_content = message['content']

        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting Wikipedia
        # searches for own Wikipedia searches!
        if message['sender_full_name'] == 'wikipedia-bot':
            return False
        is_wikipedia = (original_content.startswith('@wiki') or
                        original_content.startswith('@wikipedia'))

        return is_wikipedia

    def handle_message(self, message, client, state_handler):
        original_content = message['content']

        for prefix in ['@wikipedia', '@wiki']:
            if original_content.startswith(prefix):
                original_content = original_content[len(prefix)+1:]
                break

        query_wiki_link = 'https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch='
        try:
            data = requests.get(query_wiki_link + original_content + '&format=json')
        except:
            logging.error('broken link')
            return

        if data.status_code != 200:
            logging.error('unsuccessful data')
            return

        search_string = data.json()['query']['search'][0]['title'].replace(' ', '_')
        url = 'https://wikipedia.org/wiki/' + search_string
        new_content = 'For search term "' + original_content
        if len(data.json()['query']['search']) == 0:
            new_content = 'I am sorry. The search term you provided is not found :slightly_frowning_face:'
        else:
            new_content = new_content + '", ' + url

        client.send_message(dict(
            type=message['type'],
            to=message['display_recipient'],
            subject=message['subject'],
            content=new_content,
        ))

handler_class = WikipediaHandler
