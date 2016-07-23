from __future__ import absolute_import
from typing import Any, Dict, Text, Tuple, Callable, Mapping

from zerver.lib.outgoing_webhook import OutgoingWebhookServiceInterface, ServiceMessageActions

class Generic(OutgoingWebhookServiceInterface):

    def __init__(self, base_url, token, bot_email, service_name):
        # type: (Text, Text, Text, Text) -> None
        self.bot_email = bot_email # type: Text
        self.service_name = service_name # type: Text
        self.base_url = base_url # type: Text
        self.token = token # type: Text

    def process_command(self, event):
        # type: (Mapping[str, Any]) -> Tuple[Dict[str ,Any], Dict[str, Any]]
        rest_operation = {'method': 'POST',
                          'relative_url_path': '',
                          'request_kwargs': {}}
        trigger_cache = {"message": event['message'],
                         "command": event['command']} # type: Dict[str, Any]
        return (rest_operation, trigger_cache)

    def process_response(self, status_code, response_json, trigger_cache):
        # type: (Text, Dict[Text, Any], Dict[Text, Any]) -> Tuple[Callable[[Dict[str, Any], Text], None], Any]
        return (ServiceMessageActions.succeed_with_message, response_json)

    def handle_remote_failure(self, status_code, response_json, trigger_cache):
        # type: (Text, Dict[Text, Any], Dict[Text, Any]) -> Tuple[Callable[[Dict[str, Any], Text], None], Any]
        return (ServiceMessageActions.fail_with_message, response_json)
