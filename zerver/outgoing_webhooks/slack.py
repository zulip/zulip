from __future__ import absolute_import
from typing import Any, Dict, Text, Tuple, Callable, Mapping, Optional
import json
from requests import Response
from zerver.models import UserProfile, email_to_domain, get_service_profile

from zerver.lib.outgoing_webhook import OutgoingWebhookServiceInterface

class SlackOutgoingWebhookService(OutgoingWebhookServiceInterface):

    def process_event(self, event):
        # type: (Dict[Text, Any]) -> Tuple[Dict[str, Any], Any]
        rest_operation = {'method': 'POST',
                          'relative_url_path': '',
                          'base_url': self.base_url,
                          'request_kwargs': {}}

        if event['message']['type'] == 'private':
            raise NotImplementedError("Private messaging service not supported.")

        service = get_service_profile(event['user_profile_id'], str(self.service_name))
        request_data = [("token", self.token),
                        ("team_id", event['message']['sender_realm_str']),
                        ("team_domain", email_to_domain(event['message']['sender_email'])),
                        ("channel_id", event['message']['stream_id']),
                        ("channel_name", event['message']['display_recipient']),
                        ("timestamp", event['message']['timestamp']),
                        ("user_id", event['message']['sender_id']),
                        ("user_name", event['message']['sender_full_name']),
                        ("text", event['command']),
                        ("trigger_word", event['trigger']),
                        ("service_id", service.id),
                        ]

        return rest_operation, request_data

    def process_success(self, response, event):
        # type: (Response, Dict[Text, Any]) -> Optional[str]
        response_json = json.loads(response.text)
        response_text = ""
        if "text" in response_json:
            response_text = response_json["text"]
        return response_text

    def process_failure(self, response, event):
        # type: (Response, Dict[Text, Any]) -> Optional[str]
        return str(response.text)
