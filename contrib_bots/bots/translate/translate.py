# See zulip/contrib_bots/lib/readme.md for instructions on running this code.
from __future__ import print_function
import sys
import logging
from os.path import expanduser
from six.moves import configparser as cp
try:
    from mstranslator import Translator
except ImportError:
    logging.error("Dependency Missing!")
    sys.exit(1)

# Uses mstranslator module
#  pip install mstranslator


def get_api_key():
    # translate_bot.config must have been moved from
    # ~/zulip/contrib_bots/lib/Translate/translate_bot.config into
    # /translate_bot.config for program to work
    # see readme.md for more information
    with open(CONFIG_PATH) as settings:
        config = cp.ConfigParser()
        config.readfp(settings)
        return config.get('auth', 'api_key')

home = expanduser('~')
CONFIG_PATH = home + '/translate_bot.config'

translator = Translator(get_api_key())


def get_translate_result(original_content):
    main_content = original_content.strip().split(' ')[1]
    if main_content == "help" and len(original_content.split()) < 3:
        help_message = "To use this plugin start messages with @translate \
                        followed by the word you want to translate and the \
                        language code (all language codes can be found in \
                        the Translate_Codes.md file found in the translate \
                        folder). Example usage of this bot is \
                        '@translate hello fr' or '@translate hello zh-CHT'."
        return help_message
    elif len(original_content.split()) < 3:
        return "Need language code"
    elif len(original_content.split()) > 3:
        return "Too many tokens"
    else:
        search_keyword = main_content.split(' ')[0]
        country_code = original_content.split(' ')[2]
        try:
            message = translator.translate(search_keyword, lang_to=country_code)
        except Exception as e:
            logging.exception(e)
            return "Error in translation bot"
        return message

class TranslateHandler(object):
    '''
    This plugin allows users to enter a word and a
    country code in zulip and get the translation of
    that word in their specified laguage sent back to
    the context (stream or private) in which it was sent.
    It looks for messages starting with @translate.
    '''

    def usage(self):
        return '''
            This plugin will allow users to get the translation
            for a given word to a specified language. To use this
            plugin, users need to install the PyDictionary module
            using 'pip install PyDictionary'.Use '@translate help'
            for more usage information. Users should preface messages
            with @translate.
            '''

    def triage_message(self, message, client):
        # return True if we want to (possibly) respond to this message

        original_content = message['content']
        is_translate = original_content.startswith('@translate')

        return is_translate

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        original_sender = message['sender_email']
        new_content = get_translate_result(original_content)

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

handler_class = TranslateHandler

def test():
    assert get_translate_result("@translate hello") == "Need language code"
    assert get_translate_result("@translate foo bar baz") == "Too many tokens"
    assert get_translate_result("@translate hello fr") == "Salut"
    assert get_translate_result("@translate table es") == "tabla"
if __name__ == "__main__":
    test()
