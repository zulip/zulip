from __future__ import print_function
from __future__ import absolute_import

import logging
import os
import signal
import sys
import time
import re
from zerver.lib.actions import internal_send_message
from zerver.models import UserProfile

from six.moves import configparser

if False:
    from mypy_extensions import NoReturn
from typing import Any, Optional, List, Dict
from types import ModuleType

our_dir = os.path.dirname(os.path.abspath(__file__))

# For dev setups, we can find the API in the repo itself.
if os.path.exists(os.path.join(our_dir, '../../api')):
    sys.path.insert(0, os.path.join(our_dir, '../../api'))

from bots_api.bot_lib import RateLimit, send_reply

class EmbeddedBotHandler(object):
    def __init__(self, user_profile):
        # type: (UserProfile) -> None
        # Only expose a subset of our UserProfile's functionality
        self.user_profile = user_profile
        self._rate_limit = RateLimit(20, 5)
        try:
            self.full_name = user_profile['full_name']
            self.email = user_profile['email']
        except KeyError:
            logging.error('Cannot fetch user profile, make sure you have set'
                          ' up the zuliprc file correctly.')
            sys.exit(1)

    def send_message(self, message):
        # type: (Dict[str, Any]) -> None
        if self._rate_limit.is_legal():
            internal_send_message(realm=self.user_profile.realm, sender_email=message['sender'],
                                  recipient_type_name=message['type'], recipients=message['to'],
                                  subject=message['subject'], content=message['content'])
        else:
            self._rate_limit.show_error_and_exit()

    def send_reply(self, message, response):
        # type: (Dict[str, Any], str) -> None
        send_reply(message, response, self.email, self.send_message)

    def get_config_info(self, bot_name, section=None):
        # type: (str, Optional[str]) -> Dict[str, Any]
        conf_file_path = os.path.realpath(os.path.join(
            our_dir, '..', 'bots', bot_name, bot_name + '.conf'))
        section = section or bot_name
        config = configparser.ConfigParser()
        config.readfp(open(conf_file_path))  # type: ignore
        return dict(config.items(section))
