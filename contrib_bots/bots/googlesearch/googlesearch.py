# See readme.md for instructions on running this code.
from __future__ import print_function
import logging
import http.client
from six.moves.urllib.request import urlopen

# Uses the Google search engine bindings
#   pip install --upgrade google
from google import search


def get_google_result(search_keywords):
    help_message = "To use this bot, start messages with @mentioned-bot, \
                    followed by what you want to search for. If \
                    found, Zulip will return the first search result \
                    on Google.\
                    \
                    An example message that could be sent is:\
                    '@mentioned-bot zulip' or \
                    '@mentioned-bot how to create a chatbot'."
    if search_keywords == 'help':
        return help_message
    elif search_keywords == '' or search_keywords is None:
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

        try:
            url = next(urls)
        except AttributeError as a_err:
            # google.search query failed and urls is of object
            # 'NoneType'
            logging.exception(a_err)
            return "Error: Google search failed with a NoneType result. {}.".format(a_err)
        except TypeError as t_err:
            # google.search query failed and returned None
            # This technically should not happen but the prior
            # error check assumed this behavior
            logging.exception(t_err)
            return "Error: Google search function failed. {}.".format(t_err)
        except Exception as e:
            logging.exception(e)
            return 'Error: Search failed. {}.'.format(e)

        return 'Success: {}'.format(url)


class GoogleSearchHandler(object):
    '''
    This plugin allows users to enter a search
    term in Zulip and get the top URL sent back
    to the context (stream or private) in which
    it was called. It looks for messages starting
    with @mentioned-bot.
    '''

    def usage(self):
        return '''
            This plugin will allow users to search
            for a given search term on Google from
            Zulip. Use '@mentioned-bot help' to get
            more information on the bot usage. Users
            should preface messages with
            @mentioned-bot.
            '''

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        result = get_google_result(original_content)
        client.send_reply(message, result)

handler_class = GoogleSearchHandler


def test():
    try:
        urlopen('http://216.58.192.142', timeout=1)
        print('Success')
        return True
    except http.client.RemoteDisconnected as e:
        print('Error: {}'.format(e))
        return False

if __name__ == '__main__':
    test()
