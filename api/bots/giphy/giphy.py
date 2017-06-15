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

    def initialize(self, bot_handler):
        global config_info
        config_info = bot_handler.get_config_info('giphy')

    def handle_message(self, message, bot_handler, state_handler):
        bot_response = get_bot_giphy_response(message, bot_handler)
        bot_handler.send_reply(message, bot_response)


class GiphyNoResultException(Exception):
    pass


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


def get_bot_giphy_response(message, bot_handler):
    # Each exception has a specific reply should "gif_url" return a number.
    # The bot will post the appropriate message for the error.
    keyword = message['content']
    try:
        gif_url = get_url_gif_giphy(keyword, config_info['key'])
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
