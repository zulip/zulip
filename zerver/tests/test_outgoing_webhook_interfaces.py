# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
from typing import Any

import mock
import json

from requests.models import Response
from zerver.lib.test_classes import ZulipTestCase
from zerver.outgoing_webhooks.generic import GenericOutgoingWebhookService

class Test_GenericOutgoingWebhookService(ZulipTestCase):

    def setUp(self):
        # type: () -> None
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

    def test_process_event(self):
        # type: () -> None
        rest_operation, request_data = self.handler.process_event(self.event)
        request_data = json.loads(request_data)
        self.assertEqual(request_data['data'], "@test")
        self.assertEqual(request_data['token'], "abcdef")
        self.assertEqual(rest_operation['base_url'], "http://example.domain.com")
        self.assertEqual(rest_operation['method'], "POST")
        self.assertEqual(request_data['message'], self.event['message'])

    def test_process_success(self):
        # type: () -> None

        response = mock.Mock(spec=Response)
        response.text = json.dumps({"response_not_required": True})
        success_response = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, None)

        response.text = json.dumps({"response_string": 'test_content'})
        success_response = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, 'test_content')

        response.text = json.dumps({})
        success_response = self.handler.process_success(response, self.event)
        self.assertEqual(success_response, "")

    def test_process_failure(self):
        # type: () -> None
        response = mock.Mock(spec=Response)
        response.text = 'test_content'
        success_response = self.handler.process_failure(response, self.event)
        self.assertEqual(success_response, 'test_content')
