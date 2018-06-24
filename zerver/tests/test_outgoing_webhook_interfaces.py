# -*- coding: utf-8 -*-
from typing import Any

import mock
import json

from requests.models import Response
from zerver.lib.outgoing_webhook import GenericOutgoingWebhookService, \
    SlackOutgoingWebhookService
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Service, get_realm, get_user

class TestGenericOutgoingWebhookService(ZulipTestCase):

    def setUp(self) -> None:
        self.event = {
            u'command': '@**test**',
            u'message': {
                'content': '@**test**',
            },
            u'trigger': 'mention',
        }
        self.bot_user = get_user("outgoing-webhook@zulip.com", get_realm("zulip"))
        self.handler = GenericOutgoingWebhookService(service_name='test-service',
                                                     base_url='http://example.domain.com',
                                                     token='abcdef',
                                                     user_profile=self.bot_user)

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
        success_response, _ = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, None)

        response.text = json.dumps({"response_string": 'test_content'})
        success_response, _ = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, 'test_content')

        response.text = json.dumps({})
        success_response, _ = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, None)

mock_service = Service()

class TestSlackOutgoingWebhookService(ZulipTestCase):

    def setUp(self) -> None:
        self.stream_message_event = {
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

        self.private_message_event = {
            u'user_profile_id': 24,
            u'service_name': 'test-service',
            u'command': 'test content',
            u'trigger': 'private_message',
            u'message': {
                'sender_id': 3,
                'sender_realm_str': 'zulip',
                'timestamp': 1529821610,
                'sender_email': 'cordelia@zulip.com',
                'type': 'private',
                'sender_realm_id': 1,
                'id': 219,
                'subject': 'test',
                'content': 'test content',
            }
        }

        self.handler = SlackOutgoingWebhookService(base_url='http://example.domain.com',
                                                   token="abcdef",
                                                   user_profile=None,
                                                   service_name='test-service')

    def test_process_event_stream_message(self) -> None:
        rest_operation, request_data = self.handler.process_event(self.stream_message_event)

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
        self.assertEqual(request_data[10][1], 12)  # user_profile_id

    @mock.patch('zerver.lib.outgoing_webhook.get_service_profile', return_value=mock_service)
    @mock.patch('zerver.lib.outgoing_webhook.fail_with_message')
    def test_process_event_private_message(self, mock_fail_with_message: mock.Mock,
                                           mock_get_service_profile: mock.Mock) -> None:

        rest_operation, request_data = self.handler.process_event(self.private_message_event)
        self.assertIsNone(request_data)
        self.assertIsNone(rest_operation)
        self.assertTrue(mock_fail_with_message.called)

    def test_process_success(self) -> None:
        response = mock.Mock(spec=Response)
        response.text = json.dumps({"response_not_required": True})
        success_response, _ = self.handler.process_success(response, self.stream_message_event)
        self.assertEqual(success_response, None)

        response.text = json.dumps({"text": 'test_content'})
        success_response, _ = self.handler.process_success(response, self.stream_message_event)
        self.assertEqual(success_response, 'test_content')
