from __future__ import absolute_import
from typing import Any, Dict, Optional
from six import text_type

from zerver.lib.outgoing_webhook import OutgoingWebhookBotInterface, BotMessageActions

class GenericBot(OutgoingWebhookBotInterface):

    def __init__(self, base_url, service_api_key, email, full_name):
        self.email = email # type: text_type
        self.full_name = full_name # type: text_type
        self.base_url = base_url # type: text_type
        self.service_api_key = service_api_key # type: text_type

    def process_command(self, command):
        rest_operation = {'method' : 'POST',
                          'relative_url_path': '',
                          'request_kwargs' : {}}

        trigger_cache = {} # type: Dict[text_type, Any]
        return (rest_operation, trigger_cache)

    def process_response(self, status_code, response_json, trigger_cache):
        return (BotMessageActions.succeed_with_message, response_json['message'])

    def handle_remote_failure(self, status_code, response_json, trigger_cache):
        return (BotMessageActions.fail_with_message, response_json['message'])
