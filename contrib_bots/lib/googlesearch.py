# See readme.md for instructions on running this code.
from google import search

class GoogleSearchHandler(object):
    '''
    This plugin allows users to search for specific
    terms in google and receive the first 20 URL's, within
    zulip. It looks for the tag @google.
    '''

    def usage(self):
        return '''
            This plugin will allow users to search for
            items on google. Users should preface their messages
            with @google.
            '''

    def triage_message(self, message):
        # return True iff we want to (possibly) response to this message

        original_content = message['content']

        # This next line of code is defensive, as we
        # never want to get into an infinite loop of posting google
        # URL's
        if message['display_recipient'] == 'google':
            return False
        is_google = (original_content.startswith('@google'))

        return is_google

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_sender = message['sender_email']
        original_content = original_content.split(' ', 1)[1]
        for url in search(original_content, stop=20):
            new_content = url                                              
        client.send_message(dict(
            type='private',
            to=original_sender,
            content=new_content,
        ))
handler_class = GoogleSearchHandler
