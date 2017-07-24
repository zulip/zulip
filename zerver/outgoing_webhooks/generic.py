from __future__ import absolute_import
from typing import Any, Dict, Text, Tuple, Callable, Mapping, Optional
import json
from requests import Response
from zerver.models import UserProfile

from zerver.lib.outgoing_webhook import OutgoingWebhookServiceInterface

class GenericOutgoingWebhookService(OutgoingWebhookServiceInterface):

    def process_event(self, event):
        # type: (Dict[Text, Any]) -> Tuple[Dict[str, Any], Any]
        rest_operation = {'method': 'POST',
                          'relative_url_path': '',
                          'base_url': self.base_url,
                          'request_kwargs': {}}
        request_data = {"data": event['command'],
                        "message": event['message'],
                        "token": self.token}
        return rest_operation, json.dumps(request_data)

    def process_success(self, response, event):
        # type: (Response, Dict[Text, Any]) -> Optional[str]
        response_json = json.loads(response.text)

        if "response_not_required" in response_json and response_json['response_not_required']:
            return None
        if "response_string" in response_json:
            return str(response_json['response_string'])
        else:
            return ""

    def process_failure(self, response, event):
        # type: (Response, Dict[Text, Any]) -> Optional[str]
        return str(response.text)
