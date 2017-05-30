# See readme.md for instructions on running this code.
from __future__ import print_function
import requests
import json
import os
import sys
from six.moves.configparser import SafeConfigParser


class WeatherHandler(object):
    def __init__(self):
        self.directory = os.path.dirname(os.path.realpath(__file__)) + '/'
        self.config_name = '.weather_config'
        self.response_pattern = 'Weather in {}, {}:\n{} F / {} C\n{}'
        if not os.path.exists(self.directory + self.config_name):
            print('Weather bot config file not found, please set it up in {} file in this bot main directory'
                  '\n\nUsing format:\n\n[weather-config]\nkey=<OpenWeatherMap API key here>\n\n'.format(self.config_name))
            sys.exit(1)
        super(WeatherHandler, self).__init__()

    def usage(self):
        return '''
            This plugin will give info about weather in a specified city
            '''

    def handle_message(self, message, client, state_handler):
        help_content = '''
            This bot returns weather info for specified city.
            You specify city in the following format:
            city, state/country
            state and country parameter is optional(useful when there are many cities with the same name)
            For example:
            @**Weather Bot** Portland
            @**Weather Bot** Portland, Me
            '''.strip()

        if (message['content'] == 'help') or (message['content'] == ''):
            response = help_content
        else:
            url = 'http://api.openweathermap.org/data/2.5/weather?q=' + message['content'] + '&APPID='
            r = requests.get(url + get_weather_api_key_from_config(self.directory, self.config_name))
            if "city not found" in r.text:
                response = "Sorry, city not found"
            else:
                response = format_response(r.text, message['content'], self.response_pattern)

        client.send_reply(message, response)


def format_response(text, city, response_pattern):
    j = json.loads(text)
    city = j['name']
    country = j['sys']['country']
    fahrenheit = to_fahrenheit(j['main']['temp'])
    celsius = to_celsius(j['main']['temp'])
    description = j['weather'][0]['description'].title()

    return response_pattern.format(city, country, fahrenheit, celsius, description)


def to_celsius(temp_kelvin):
    return int(temp_kelvin) - 273.15


def to_fahrenheit(temp_kelvin):
    return int(temp_kelvin) * 9 / 5 - 459.67


def get_weather_api_key_from_config(directory, config_name):
    config = SafeConfigParser()
    with open(directory + config_name, 'r') as config_file:
        config.readfp(config_file)
    return config.get("weather-config", "key")

handler_class = WeatherHandler
