# To use this plugin, you need to set up the Giphy API key for this bot in
# ~/.giphy_config

from __future__ import absolute_import
from __future__ import print_function
from six.moves.configparser import SafeConfigParser
import requests
import logging
import sys
import os
import re

GIPHY_TRANSLATE_API = 'http://api.giphy.com/v1/gifs/translate'

if not os.path.exists(os.environ['HOME'] + '/.giphy_config'):
    print('Giphy bot config file not found, please set up it in ~/.giphy_config'
          '\n\nUsing format:\n\n[giphy-config]\nkey=<giphy API key here>\n\n')
    sys.exit(1)


class GiphyHandler(object):
    '''
    This plugin posts a GIF in response to the keywords provided by the user.
    Images are provided by Giphy, through the public API.
    The bot looks for messages starting with @mention of the bot
    and responds with a message with the GIF based on provided keywords.
    It also responds to private messages.
    '''
    def usage(self):
        return '''
            This plugin allows users to post GIFs provided by Giphy.
            Users should preface keywords with the Giphy-bot @mention.
            The bot responds also to private messages.
            '''

    def handle_message(self, message, client, state_handler):
        bot_response = get_bot_giphy_response(message, client)
        client.send_reply(message, bot_response)


class GiphyNoResultException(Exception):
    pass


def get_giphy_api_key_from_config():
    config = SafeConfigParser()
    with open(os.environ['HOME'] + '/.giphy_config', 'r') as config_file:
        config.readfp(config_file)
    return config.get("giphy-config", "key")


def get_url_gif_giphy(keyword, api_key):
    # Return a URL for a Giphy GIF based on keywords given.
    # In case of error, e.g. failure to fetch a GIF URL, it will
    # return a number.
    query = {'s': keyword,
             'api_key': api_key}
    try:
        data = requests.get(GIPHY_TRANSLATE_API, params=query)
    except requests.exceptions.ConnectionError as e:  # Usually triggered by bad connection.
        logging.warning(e)
        raise

    search_status = data.json()['meta']['status']
    if search_status != 200 or not data.ok:
        raise requests.exceptions.ConnectionError

    try:
        gif_url = data.json()['data']['images']['original']['url']
    except (TypeError, KeyError):  # Usually triggered by no result in Giphy.
        raise GiphyNoResultException()

    return gif_url


def get_bot_giphy_response(message, client):
    # Each exception has a specific reply should "gif_url" return a number.
    # The bot will post the appropriate message for the error.
    keyword = message['content']
    try:
        gif_url = get_url_gif_giphy(keyword, get_giphy_api_key_from_config())
    except requests.exceptions.ConnectionError:
        return ('Uh oh, sorry :slightly_frowning_face:, I '
                'cannot process your request right now. But, '
                'let\'s try again later! :grin:')
    except GiphyNoResultException:
        return ('Sorry, I don\'t have a GIF for "%s"! '
                ':astonished:' % (keyword))
    return ('[Click to enlarge](%s)'
            '[](/static/images/interactive-bot/giphy/powered-by-giphy.png)'
            % (gif_url))

handler_class = GiphyHandler
