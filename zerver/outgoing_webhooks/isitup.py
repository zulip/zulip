from __future__ import absolute_import

import json
import re
from zerver.lib.outgoing_webhook import OutgoingWebhookBotInterface, BotMessageActions

class IsItUpBot(OutgoingWebhookBotInterface):
    email = "isitup-bot@zulip.com"
    full_name = "IsItUpBot"

    def __init__(self, base_url, service_api_key, email=None, full_name=None):
        self.base_url = base_url
        self.service_api_key = service_api_key

    def process_command(self, command):
        tokens = command.lower().split(' ')
        url = None
        for token in tokens:
            if re.search(u'\..+', token):
                url = token

        if url is not None:
            rest_operation = {'method' : 'GET',
                              'relative_url_path': url + '.json',
                              'request_kwargs' : {}}

            trigger_cache = {'command' : command}
            return (rest_operation, trigger_cache)

        else:
            trigger_cache = {'command' : command}
            return (None, trigger_cache)

    def process_response(self, status_code, response_json, trigger_cache):
        status = int(response_json['status_code'])
        if status == 1:
            response = '**' + response_json['domain'] + '** is **up**!'
            return (BotMessageActions.succeed_with_message, response)
        else:
            response = '**' + response_json['domain'] + '** is ***down!**\n' + \
                    '`\n' + json.dumps(response_json, indent=4) + '\n`'
            return (BotMessageActions.succeed_with_message, response)

    def handle_remote_failure(self, status_code, response_json, trigger_cache):
        return (BotMessageActions.fail_with_message, '**Failed: **' + response_json)

    def handle_invalid_command(self, command, trigger_cache):
        return (BotMessageActions.fail_with_message, '**Invalid command: **' + command)
