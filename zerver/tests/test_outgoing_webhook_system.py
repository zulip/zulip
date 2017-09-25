# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import mock
import requests
from typing import Any, Dict, Tuple, Text, Optional
from requests import Response

from zerver.lib.outgoing_webhook import do_rest_call, OutgoingWebhookServiceInterface
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_realm, get_user
from builtins import object

class ResponseMock(object):
    def __init__(self, status_code, data, content):
        # type: (int, Any, str) -> None
        self.status_code = status_code
        self.data = data
        self.content = content

def request_exception_error(http_method, final_url, data, **request_kwargs):
    # type: (Any, Any, Any, **Any) -> Any
    raise requests.exceptions.RequestException

def timeout_error(http_method, final_url, data, **request_kwargs):
    # type: (Any, Any, Any, **Any) -> Any
    raise requests.exceptions.Timeout

class MockServiceHandler(OutgoingWebhookServiceInterface):
    def process_success(self, response, event):
        # type: (Response, Dict[Text, Any]) -> Optional[str]
        return "Success!"

service_handler = MockServiceHandler(None, None, None, None)

class DoRestCallTests(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        realm = get_realm("zulip")
        user_profile = get_user("outgoing-webhook@zulip.com", realm)
        self.mock_event = {'message': {'display_recipient': '',
                                       'subject': '',
                                       'id': ''},
                           'user_profile_id': user_profile.id,
                           'command': '',
                           'service_name': ''}

        self.rest_operation = {'method': "POST",
                               'relative_url_path': "",
                               'request_kwargs': {},
                               'base_url': ""}

    @mock.patch('zerver.lib.outgoing_webhook.succeed_with_message')
    def test_successful_request(self, mock_succeed_with_message):
        # type: (mock.Mock) -> None
        response = ResponseMock(200, {"message": "testing"}, '')
        with mock.patch('requests.request', return_value=response):
            do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
            self.assertTrue(mock_succeed_with_message.called)

    @mock.patch('zerver.lib.outgoing_webhook.request_retry')
    def test_retry_request(self, mock_request_retry):
        # type: (mock.Mock) -> None
        response = ResponseMock(500, {"message": "testing"}, '')
        with mock.patch('requests.request', return_value=response):
            do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
            self.assertTrue(mock_request_retry.called)

    @mock.patch('zerver.lib.outgoing_webhook.fail_with_message')
    def test_fail_request(self, mock_fail_with_message):
        # type: (mock.Mock) -> None
        response = ResponseMock(400, {"message": "testing"}, '')
        with mock.patch('requests.request', return_value=response):
            do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
            self.assertTrue(mock_fail_with_message.called)

    @mock.patch('logging.info')
    @mock.patch('requests.request', side_effect=timeout_error)
    @mock.patch('zerver.lib.outgoing_webhook.request_retry')
    def test_timeout_request(self, mock_request_retry, mock_requests_request, mock_logger):
        # type: (mock.Mock, mock.Mock, mock.Mock) -> None
        do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
        self.assertTrue(mock_request_retry.called)

    @mock.patch('logging.exception')
    @mock.patch('requests.request', side_effect=request_exception_error)
    @mock.patch('zerver.lib.outgoing_webhook.fail_with_message')
    def test_request_exception(self, mock_fail_with_message, mock_requests_request, mock_logger):
        # type: (mock.Mock, mock.Mock, mock.Mock) -> None
        do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
        self.assertTrue(mock_fail_with_message.called)
