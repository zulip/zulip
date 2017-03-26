from __future__ import print_function

import datetime as dt
import requests
from os.path import expanduser
from six.moves import configparser as cp

home = expanduser('~')
CONFIG_PATH = home + '/commute.config'

class CommuteHandler(object):
    '''
    This plugin provides information regarding commuting
    from an origin to a destination, providing a multitude of information.
    It looks for messages starting with @mention of the bot.
    '''

    def __init__(self):
        self.api_key = self.get_api_key()

    def usage(self):
        return '''
            This plugin will allow briefings of estimated travel times,
            distances and fare information for transit travel.
            It can vary outputs depending on traffic conditions, departure and
            arrival times as well as user preferences
            (toll avoidance, preference for bus travel, etc.).
            It looks for messages starting with @mention of the bot.

            Users should input an origin and a destination
            in any stream or through private messages to the bot to receive a
            response in the same stream or through private messages if the
            input was originally private.

            Sample input:
            @mention-botname origins=Chicago,IL,USA destinations=New+York,NY,USA
            @mention-botname help
            '''

    help_info = '''
    Obligatory Inputs:
        Origin e.g. origins=New+York,NY,USA
        Destination e.g. destinations=Chicago,IL,USA
    Optional Inputs:
        Mode Of Transport (inputs: driving, walking, bicycling, transit)
        Default mode (no mode input) is driving
        e.g. mode=driving or mode=transit
        Units (metric or imperial)
        e.g. units=metric
        Restrictions (inputs: tolls, highways, ferries, indoor)
        e.g. avoid=tolls
        Departure Time (inputs: now or (YYYY, MM, DD, HH, MM, SS) departing)
        e.g. departure_time=now or departure_time=2016,12,17,23,40,40
        Arrival Time (inputs: (YYYY, MM, DD, HH, MM, SS) arriving)
        e.g. arrival_time=2016,12,17,23,40,40
        Languages:
        Languages list: https://developers.google.com/maps/faq#languagesupport)
        e.g. language=fr

    Sample request:
        @mention-botname origins=Chicago,IL,USA destinations=New+York,NY,USA language=fr

    Please note:
        Fare information can be derived, though is solely dependent on the
        availability of the information
        python run.py bots/followup/followup.py --config-file ~/.zuliprc-local
        released by public transport operators.
        Duration in traffic can only be derived if a departure time is set.
        If a location has spaces in its name, please use a + symbol in the
        place of the space/s.
        A departure time and a arrival time can not be inputted at the same time
        To add more than 1 input for a category,
        e.g. more than 1 destinations,
        use (|), e.g. destinations=Empire+State+Building|Statue+Of+Liberty
        No spaces within addresses.
        Departure times and arrival times must be in the UTC timezone,
        you can use the timezone bot.
                '''

    # adds API Authentication Key to url request
    def get_api_key(self):
        # commute.config must be moved from
        # ~/zulip/contrib_bots/bots/commute/commute.config into
        # ~/commute.config for program to work
        # see readme.md for more information
        with open(CONFIG_PATH) as settings:
            config = cp.ConfigParser()
            config.readfp(settings)
            return config.get('Google.com', 'api_key')

    # determines if bot will respond as a private message/ stream message
    def send_info(self, message, letter, client):
        if message['type'] == 'private':
            client.send_message(dict(
                type='private',
                to=message['sender_email'],
                content=letter,
            ))
        else:
            client.send_message(dict(
                type='stream',
                subject=message['subject'],
                to=message['display_recipient'],
                content=letter,
            ))

    def calculate_seconds(self, time_str):
        times = time_str.split(',')
        times = [int(x) for x in times]
        # UNIX time from January 1, 1970 00:00:00
        unix_start_date = dt.datetime(1970, 1, 1, 0, 0, 0)
        requested_time = dt.datetime(*times)
        total_seconds = str(int((requested_time-unix_start_date)
                                .total_seconds()))
        return total_seconds

    # adds departure time and arrival time paramaters into HTTP request
    def add_time_to_params(self, params):
        # limited to UTC timezone because of difficulty with user inputting
        # correct string for input
        if 'departure_time' in params:
            if 'departure_time' != 'now':
                params['departure_time'] = self.calculate_seconds(params['departure_time'])
        elif 'arrival_time' in params:
            params['arrival_time'] = self.calculate_seconds(params['arrival_time'])
        return

    # gets content for output and sends it to user
    def get_send_content(self, rjson, params, message, client):
        try:
            # JSON list of output variables
            variable_list = rjson["rows"][0]["elements"][0]
            # determines if user has valid inputs
            not_found = (variable_list["status"] == "NOT_FOUND")
            invalid_request = (rjson["status"] == "INVALID_REQUEST")
            no_result = (variable_list["status"] == "ZERO_RESULTS")

            if no_result:
                self.send_info(message,
                               "Zero results\nIf stuck, try '@commute help'.",
                               client)
                return
            elif not_found or invalid_request:
                raise IndexError
        except IndexError:
            self.send_info(message,
                           "Invalid input, please see instructions."
                           "\nIf stuck, try '@commute help'.", client)
            return

        # origin and destination strings
        begin = 'From: ' + rjson["origin_addresses"][0]
        end = 'To: ' + rjson["destination_addresses"][0]
        distance = 'Distance: ' + variable_list["distance"]["text"]
        duration = 'Duration: ' + variable_list["duration"]["text"]
        output = begin + '\n' + end + '\n' + distance
        # if user doesn't know that default mode is driving
        if 'mode' not in params:
            mode = 'Mode of Transport: Driving'
            output += '\n' + mode

        # determines if fare information is available
        try:
            fare = ('Fare: ' + variable_list["fare"]["currency"] +
                    variable_list["fare"]["text"])
            output += '\n' + fare
        except (KeyError, IndexError):
            pass

        # determines if traffic duration information is available
        try:
            traffic_duration = ('Duration in traffic: ' +
                                variable_list["duration_in_traffic"]
                                ["text"])
            output += '\n' + traffic_duration
        except (KeyError, IndexError):
            output += '\n' + duration

        # bot sends commute information to user
        self.send_info(message, output, client)

    # creates parameters for HTTP request
    def parse_pair(self, content_list):
        result = {}
        for item in content_list:
            # enables key value pair
            org = item.split('=')
            # ensures that invalid inputs are not entered into url request
            if len(org) != 2:
                continue
            key, value = org
            result[key] = value
        return result

    def receive_response(self, params, message, client):
        def validate_requests(request):
            if request.status_code == 200:
                return request.json()
            else:
                self.send_info(message,
                               "Something went wrong. Please try again." +
                               " Error: {error_num}.\n{error_text}"
                               .format(error_num=request.status_code,
                                       error_text=request.text), client)
                return
        r = requests.get('https://maps.googleapis.com/maps/api/' +
                         'distancematrix/json', params=params)
        result = validate_requests(r)
        return result

    def handle_message(self, message, client, state_handler):
        original_content = message['content']
        query = original_content.split()

        if "help" in query:
            self.send_info(message, self.help_info, client)
            return

        params = self.parse_pair(query)
        params['key'] = self.api_key
        self.add_time_to_params(params)

        rjson = self.receive_response(params, message, client)
        if not rjson:
            return

        self.get_send_content(rjson, params, message, client)

handler_class = CommuteHandler
handler = CommuteHandler()

def test_parse_pair():
    result = handler.parse_pair(['departure_time=2016,12,20,23,59,00',
                                'dog_foo=cat-foo'])
    assert result == dict(departure_time='2016,12,20,23,59,00',
                          dog_foo='cat-foo')

def test_calculate_seconds():
    result = handler.calculate_seconds('2016,12,20,23,59,00')
    assert result == str(1482278340)

def test_get_api_key():
    # must change to your own api key for test to work
    result = handler.get_api_key()
    assert result == 'abcdefghijksm'

def test_helper_functions():
    test_parse_pair()
    test_calculate_seconds()
    test_get_api_key()

if __name__ == '__main__':
    test_helper_functions()
    print('Success')
