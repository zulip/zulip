# -*- coding: utf-8 -*-
from typing import cast, Any, Dict

import mock
import json
import requests

from zerver.lib.outgoing_webhook import (
    get_service_interface_class,
    process_success_response,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic import TOPIC_NAME
from zerver.models import get_realm, get_user, SLACK_INTERFACE

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
        service_class = get_service_interface_class('whatever')  # GenericOutgoingWebhookService
        self.handler = service_class(service_name='test-service',
                                     token='abcdef',
                                     user_profile=self.bot_user)

    def test_process_success_response(self) -> None:
        class Stub:
            def __init__(self, text: str) -> None:
                self.text = text  # type: ignore

        def make_response(text: str) -> requests.Response:
            return cast(requests.Response, Stub(text=text))

        event = dict(
            user_profile_id=99,
            message=dict(type='private')
        )
        service_handler = self.handler

        response = make_response(text=json.dumps(dict(content='whatever')))

        with mock.patch('zerver.lib.outgoing_webhook.send_response_message') as m:
            process_success_response(
                event=event,
                service_handler=service_handler,
                response=response,
            )
        self.assertTrue(m.called)

        response = make_response(text='unparsable text')

        with mock.patch('zerver.lib.outgoing_webhook.fail_with_message') as m:
            process_success_response(
                event=event,
                service_handler=service_handler,
                response=response
            )
        self.assertTrue(m.called)

    def test_build_bot_request(self) -> None:
        request_data = self.handler.build_bot_request(self.event)
        request_data = json.loads(request_data)
        self.assertEqual(request_data['data'], "@**test**")
        self.assertEqual(request_data['token'], "abcdef")
        self.assertEqual(request_data['message'], self.event['message'])

    def test_process_success(self) -> None:
        response = dict(response_not_required=True)  # type: Dict[str, Any]
        success_response = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, None)

        response = dict(response_string='test_content')
        success_response = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, dict(content='test_content'))

        response = dict(
            content='test_content',
            widget_content='test_widget_content',
            red_herring='whatever',
        )
        success_response = self.handler.process_success(response, self.event)
        expected_response = dict(
            content='test_content',
            widget_content='test_widget_content',
        )
        self.assertEqual(success_response, expected_response)

        response = dict()
        success_response = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, None)

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
                TOPIC_NAME: 'test',
                'content': 'test content',
            }
        }

        service_class = get_service_interface_class(SLACK_INTERFACE)
        self.handler = service_class(token="abcdef",
                                     user_profile=None,
                                     service_name='test-service')

    def test_build_bot_request_stream_message(self) -> None:
        request_data = self.handler.build_bot_request(self.stream_message_event)

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

    @mock.patch('zerver.lib.outgoing_webhook.fail_with_message')
    def test_build_bot_request_private_message(self, mock_fail_with_message: mock.Mock) -> None:

        request_data = self.handler.build_bot_request(self.private_message_event)
        self.assertIsNone(request_data)
        self.assertTrue(mock_fail_with_message.called)

    def test_process_success(self) -> None:
        response = dict(response_not_required=True)  # type: Dict[str, Any]
        success_response = self.handler.process_success(response, self.stream_message_event)
        self.assertEqual(success_response, None)

        response = dict(text='test_content')
        success_response = self.handler.process_success(response, self.stream_message_event)
        self.assertEqual(success_response, dict(content='test_content'))
