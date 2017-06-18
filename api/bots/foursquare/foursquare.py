from __future__ import print_function
from __future__ import absolute_import

import datetime as dt
import re
import requests
from six.moves import range

class FoursquareHandler(object):
    def initialize(self, bot_handler):
        self.api_key = bot_handler.get_config_info('foursquare', 'Foursquare')['api_key']

    def usage(self):
        return '''
            This plugin allows users to search for restaurants nearby an inputted
            location to a limit of 3 venues for every location. The name, address
            and description of the restaurant will be outputted.
            It looks for messages starting with '@mention-bot'.
            If you need help, simply type:
            @mention-bot /help into the Compose Message box

            Sample input:
            @mention-bot Chicago, IL
            @mention-bot help
            '''

    help_info = '''
The Foursquare bot can receive keyword limiters that specify the location, distance (meters) and
cusine of a restaurant in that exact order.
Please note the required use of quotes in the search location.

Example Inputs:
@mention-bot 'Millenium Park' 8000 donuts
@mention-bot 'Melbourne, Australia' 40000 seafood
                '''

    def format_json(self, venues):
        def format_venue(venue):
            name = venue['name']
            address = ', '.join(venue['location']['formattedAddress'])
            keyword = venue['categories'][0]['pluralName']
            blurb = '\n'.join([name, address, keyword])
            return blurb

        return '\n'.join(format_venue(venue) for venue in venues)

    def send_info(self, message, letter, bot_handler):
        bot_handler.send_reply(message, letter)

    def handle_message(self, message, bot_handler, state_handler):
        words = message['content'].split()
        if "/help" in words:
            self.send_info(message, self.help_info, bot_handler)
            return

        # These are required inputs for the HTTP request.
        try:
            params = {'limit': '3'}
            params['near']  = re.search('\'[A-Za-z]\w+[,]?[\s\w+]+?\'', message['content']).group(0)
            params['v'] = 20170108
            params['oauth_token'] = self.api_key
        except AttributeError:
            pass

        # Optional params for HTTP request.
        if len(words) >= 1:
            try:
                params['radius'] = re.search('([0-9]){3,}', message['content']).group(0)
            except AttributeError:
                pass
            try:
                params['query'] = re.search('\s([A-Za-z]+)$', message['content']).group(0)[1:]
            except AttributeError:
                params['query'] = 'food'

        response = requests.get('https://api.foursquare.com/v2/venues/search?',
                                params=params)
        print(response.url)
        if response.status_code == 200:
            received_json = response.json()
        else:
            self.send_info(message,
                           "Invalid Request\nIf stuck, try '@mention-bot help'.",
                           bot_handler)
            return

        if received_json['meta']['code'] == 200:
            response_msg = ('Food nearby ' + params['near'] +
                            ' coming right up:\n' +
                            self.format_json(received_json['response']['venues']))
            self.send_info(message, response_msg, bot_handler)
            return

        self.send_info(message,
                       "Invalid Request\nIf stuck, try '@mention-bot help'.",
                       bot_handler)
        return

handler_class = FoursquareHandler
