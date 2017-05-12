# See readme.md for instructions on running this code.

from __future__ import absolute_import
from __future__ import division
from past.utils import old_div

import copy
import importlib
import sys
from math import log10, floor

import utils
import re

def is_float(value):
    try:
        float(value)
        return True
    except ValueError:
        return False

# Rounds the number 'x' to 'digits' significant digits.
# A normal 'round()' would round the number to an absolute amount of
# fractional decimals, e.g. 0.00045 would become 0.0.
# 'round_to()' rounds only the digits that are not 0.
# 0.00045 would then become 0.0005.
def round_to(x, digits):
    return round(x, digits-int(floor(log10(abs(x)))))

class ConverterHandler(object):
    '''
    This plugin allows users to make conversions between various units,
    e.g. Celsius to Fahrenheit, or kilobytes to gigabytes.
    It looks for messages of the format
    '@mention-bot <number> <unit_from> <unit_to>'
    The message '@mention-bot help' posts a short description of how to use
    the plugin, along with a list of all supported units.
    '''

    def usage(self):
        return '''
               This plugin allows users to make conversions between
               various units, e.g. Celsius to Fahrenheit,
               or kilobytes to gigabytes. It looks for messages of
               the format '@mention-bot <number> <unit_from> <unit_to>'
               The message '@mention-bot help' posts a short description of
               how to use the plugin, along with a list of
               all supported units.
               '''

    def handle_message(self, message, client, state_handler):
        bot_response = get_bot_converter_response(message, client)
        if message['type'] == 'private':
            client.send_message(dict(
                type='private',
                to=message['sender_email'],
                content=bot_response,
            ))
        else:
            client.send_message(dict(
                type='stream',
                to=message['display_recipient'],
                subject=message['subject'],
                content=bot_response,
            ))

def get_bot_converter_response(message, client):
    content = message['content']

    words = content.lower().split()
    convert_indexes = [i for i, word in enumerate(words) if word == "@convert"]
    convert_indexes = [-1] + convert_indexes
    results = []

    for convert_index in convert_indexes:
        if (convert_index + 1) < len(words) and words[convert_index + 1] == 'help':
            results.append(utils.HELP_MESSAGE)
            continue
        if (convert_index + 3) < len(words):
            number = words[convert_index + 1]
            unit_from = utils.ALIASES.get(words[convert_index + 2], words[convert_index + 2])
            unit_to = utils.ALIASES.get(words[convert_index + 3], words[convert_index + 3])
            exponent = 0

            if not is_float(number):
                results.append(number + ' is not a valid number. ' + utils.QUICK_HELP)
                continue

            number = float(number)
            number_res = copy.copy(number)

            for key, exp in utils.PREFIXES.items():
                if unit_from.startswith(key):
                    exponent += exp
                    unit_from = unit_from[len(key):]
                if unit_to.startswith(key):
                    exponent -= exp
                    unit_to = unit_to[len(key):]

            uf_to_std = utils.UNITS.get(unit_from, False)
            ut_to_std = utils.UNITS.get(unit_to, False)

            if uf_to_std is False:
                results.append(unit_from + ' is not a valid unit. ' + utils.QUICK_HELP)
            if ut_to_std is False:
                results.append(unit_to + ' is not a valid unit.' + utils.QUICK_HELP)
            if uf_to_std is False or ut_to_std is False:
                continue

            base_unit = uf_to_std[2]
            if uf_to_std[2] != ut_to_std[2]:
                unit_from = unit_from.capitalize() if uf_to_std[2] == 'kelvin' else unit_from
                results.append(unit_to.capitalize() + ' and ' + unit_from +
                               ' are not from the same category. ' + utils.QUICK_HELP)
                continue

            # perform the conversion between the units
            number_res *= uf_to_std[1]
            number_res += uf_to_std[0]
            number_res -= ut_to_std[0]
            number_res /= ut_to_std[1]

            if base_unit == 'bit':
                number_res *= 1024 ** (old_div(exponent, float(3)))
            else:
                number_res *= 10 ** exponent
            number_res = round_to(number_res, 7)

            results.append('{} {} = {} {}'.format(number,
                                                  words[convert_index + 2],
                                                  number_res,
                                                  words[convert_index + 3]))

        else:
            results.append('Too few arguments given. ' + utils.QUICK_HELP)

    new_content = ''
    for idx, result in enumerate(results, 1):
        new_content += ((str(idx) + '. conversion: ') if len(results) > 1 else '') + result + '\n'

    return new_content

handler_class = ConverterHandler
