# See zulip/contrib_bots/bots/readme.md for instructions on running this code.
from __future__ import print_function
import sys
import logging
try:
    from PyDictionary import PyDictionary as Dictionary
except ImportError:
    logging.error("Dependency Missing!")
    sys.exit(0)

#Uses Python's Dictionary module
#  pip install PyDictionary

def get_clean_response(m, method):
    try:
        response = method(m)
    except Exception as e:
        logging.exception(e)
        return e
    if isinstance(response, str):
        return response
    elif isinstance(response, list):
        return ', '.join(response)

def get_thesaurus_result(original_content):
    search_keyword = original_content.strip().split(' ', 1)[1]
    if search_keyword == 'help':
        help_message = "To use this bot, start messages with either \
                        @mention-bot synonym (to get the synonyms of a given word) \
                        or @mention-bot antonym (to get the antonyms of a given word). \
                        Phrases are not accepted so only use single words \
                        to search. For example you could search '@mention-bot synonym hello' \
                        or '@mention-bot antonym goodbye'."
        return help_message
    elif original_content.startswith('synonym'):
        result = get_clean_response(search_keyword, method = Dictionary.synonym)
    elif original_content.startswith('antonym'):
        result = get_clean_response(search_keyword, method = Dictionary.antonym)

    if result is None:
        result = "Sorry, no result found! Please check the word."
    return result

class ThesaurusHandler(object):
    '''
    This plugin allows users to enter a word in zulip
    and get synonyms, and antonyms, for that word sent
    back to the context (stream or private) in which
    it was sent. It looks for messages starting with
    '@mention-bot synonym' or '@mention-bot @antonym'.
    '''

    def usage(self):
        return '''
            This plugin will allow users to get both synonyms
            and antonyms for a given word from zulip. To use this
            plugin, users need to install the PyDictionary module
            using 'pip install PyDictionary'.Use '@mention-bot synonym help' or
            '@mention-bot antonym help' for more usage information. Users should
            preface messages with @mention-bot synonym or @mention-bot antonym.
            '''

    def handle_message(self, message, client, state_handler):
        original_content = message['content'].strip()
        original_sender = message['sender_email']
        new_content = get_thesaurus_result(original_content)

        if message['type'] == 'private':
            client.send_message(dict(
                type='private',
                to=original_sender,
                content=new_content,
            ))
        else:
            client.send_message(dict(
                type=message['type'],
                to=message['display_recipient'],
                subject=message['subject'],
                content=new_content,
            ))

handler_class = ThesaurusHandler
