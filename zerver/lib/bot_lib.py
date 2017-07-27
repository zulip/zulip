from __future__ import print_function
from __future__ import absolute_import

import logging
import os
import signal
import sys
import time
import re
import importlib
from zerver.lib.actions import internal_send_message
from zerver.models import UserProfile
from zerver.lib.integrations import EMBEDDED_BOTS

from six.moves import configparser

if False:
    from mypy_extensions import NoReturn
from typing import Any, Optional, List, Dict
from types import ModuleType

our_dir = os.path.dirname(os.path.abspath(__file__))

from zulip_bots.lib import RateLimit

def get_bot_handler(service_name):
    # type: (str) -> Any

    # Check that this service is present in EMBEDDED_BOTS, add exception handling.
    is_present_in_registry = any(service_name == embedded_bot_service.name for embedded_bot_service in EMBEDDED_BOTS)
    if not is_present_in_registry:
        return None
    bot_module_name = 'zulip_bots.bots.%s.%s' % (service_name, service_name)
    bot_module = importlib.import_module(bot_module_name)  # type: Any
    return bot_module.handler_class()

class EmbeddedBotHandler(object):
    def __init__(self, user_profile):
        # type: (UserProfile) -> None
        # Only expose a subset of our UserProfile's functionality
        self.user_profile = user_profile
        self._rate_limit = RateLimit(20, 5)
        self.full_name = user_profile.full_name
        self.email = user_profile.email

    def send_message(self, message):
        # type: (Dict[str, Any]) -> None
        if self._rate_limit.is_legal():
            internal_send_message(realm=self.user_profile.realm, sender_email=message['sender_email'],
                                  recipient_type_name=message['type'], recipients=message['to'],
                                  subject=message['subject'], content=message['content'])
        else:
            self._rate_limit.show_error_and_exit()

    def send_reply(self, message, response):
        # type: (Dict[str, Any], str) -> None
        if message['type'] == 'private':
            self.send_message(dict(
                type='private',
                to=[x['email'] for x in message['display_recipient'] if self.email != x['email']],
                content=response,
                sender_email=message['sender_email'],
            ))
        else:
            self.send_message(dict(
                type='stream',
                to=message['display_recipient'],
                subject=message['subject'],
                content=response,
                sender_email=message['sender_email'],
            ))

    def get_config_info(self, bot_name, section=None):
        # type: (str, Optional[str]) -> Dict[str, Any]
        conf_file_path = os.path.realpath(os.path.join(
            our_dir, '..', 'bots', bot_name, bot_name + '.conf'))
        section = section or bot_name
        config = configparser.ConfigParser()
        config.readfp(open(conf_file_path))  # type: ignore # likely typeshed issue
        return dict(config.items(section))
