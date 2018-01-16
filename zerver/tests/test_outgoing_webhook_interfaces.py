# -*- coding: utf-8 -*-
from typing import Any

import mock
import json

from requests.models import Response
from zerver.lib.outgoing_webhook import GenericOutgoingWebhookService, \
    SlackOutgoingWebhookService
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Service

class TestGenericOutgoingWebhookService(ZulipTestCase):

    def setUp(self) -> None:
        self.event = {
            u'command': '@**test**',
            u'message': {
                'content': 'test_content',
            }
        }
        self.handler = GenericOutgoingWebhookService(service_name='test-service',
                                                     base_url='http://example.domain.com',
                                                     token='abcdef',
                                                     user_profile=None)

    def test_process_event(self) -> None:
        rest_operation, request_data = self.handler.process_event(self.event)
        request_data = json.loads(request_data)
        self.assertEqual(request_data['data'], "@**test**")
        self.assertEqual(request_data['token'], "abcdef")
        self.assertEqual(rest_operation['base_url'], "http://example.domain.com")
        self.assertEqual(rest_operation['method'], "POST")
        self.assertEqual(request_data['message'], self.event['message'])

    def test_process_success(self) -> None:
        response = mock.Mock(spec=Response)
        response.text = json.dumps({"response_not_required": True})
        success_response = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, None)

        response.text = json.dumps({"response_string": 'test_content'})
        success_response = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, 'test_content')

        response.text = json.dumps({})
        success_response = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, None)

mock_service = Service()

class TestSlackOutgoingWebhookService(ZulipTestCase):

    def setUp(self) -> None:
        self.event = {
            u'command': '@**test**',
            u'user_profile_id': 12,
            u'service_name': 'test-service',
            u'trigger': 'mention',
            u'message': {
                'content': 'test_content',
                'type': 'stream',
                'sender_realm_str': 'zulip',
                'sender_email': 'sampleuser@zulip.com',
                'stream_id': '123',
                'display_recipient': 'integrations',
                'timestamp': 123456,
                'sender_id': 21,
                'sender_full_name': 'Sample User',
            }
        }
        self.handler = SlackOutgoingWebhookService(base_url='http://example.domain.com',
                                                   token="abcdef",
                                                   user_profile=None,
                                                   service_name='test-service')

    @mock.patch('zerver.lib.outgoing_webhook.get_service_profile', return_value=mock_service)
    def test_process_event(self, mock_get_service_profile: mock.Mock) -> None:
        rest_operation, request_data = self.handler.process_event(self.event)

        self.assertEqual(rest_operation['base_url'], 'http://example.domain.com')
        self.assertEqual(rest_operation['method'], 'POST')
        self.assertEqual(request_data[0][1], "abcdef")  # token
        self.assertEqual(request_data[1][1], "zulip")  # team_id
        self.assertEqual(request_data[2][1], "zulip.com")  # team_domain
        self.assertEqual(request_data[3][1], "123")  # channel_id
        self.assertEqual(request_data[4][1], "integrations")  # channel_name
        self.assertEqual(request_data[5][1], 123456)  # timestamp
        self.assertEqual(request_data[6][1], 21)  # user_id
        self.assertEqual(request_data[7][1], "Sample User")  # user_name
        self.assertEqual(request_data[8][1], "@**test**")  # text
        self.assertEqual(request_data[9][1], "mention")  # trigger_word
        self.assertEqual(request_data[10][1], mock_service.id)  # service_id

    def test_process_success(self) -> None:
        response = mock.Mock(spec=Response)
        response.text = json.dumps({"response_not_required": True})
        success_response = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, None)

        response.text = json.dumps({"text": 'test_content'})
        success_response = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, 'test_content')
