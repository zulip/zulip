# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import mock
from typing import Any

from zerver.lib.test_helpers import get_user_profile_by_email
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Service, GENERIC_INTERFACE
from zerver.outgoing_webhooks import (
    AVAILABLE_OUTGOING_WEBHOOK_INTERFACES,
    get_service_interface_class,
)
from zerver.lib.outgoing_webhook import (
    do_rest_call,
    get_outgoing_webhook_service_handler,
    ServiceMessageActions,
)

import requests

service = Service.objects.get_or_create(name="test",
                                        base_url="http://requestb.in/18av3gx1",
                                        token="somerandomkey",
                                        user_profile=get_user_profile_by_email('notification-bot@zulip.com'),
                                        interface=1)[0]
service_handler = get_outgoing_webhook_service_handler(service)

rest_operation = {'method': "GET",
                  'relative_url_path': "",
                  'request_kwargs': {}}

class ResponseMock(object):
    def __init__(self, status_code, data):
        # type: (int, Any) -> None
        self.status_code = status_code
        self.data = data

    def json(self):
        # type: () -> str
        return self.data


def request_exception_error(http_method, final_url, data, **request_kwargs):
    # type: (Any, Any, Any, Any) -> Any
    raise requests.exceptions.RequestException

def timeout_error(http_method, final_url, data, **request_kwargs):
    # type: (Any, Any, Any, Any) -> Any
    raise requests.exceptions.Timeout

class DoRestCallTests(ZulipTestCase):
    @mock.patch('zerver.lib.outgoing_webhook.ServiceMessageActions.succeed_with_message')
    def test_successful_request(self, mock_succeed_with_message):
        # type: (mock.Mock) -> None
        response = ResponseMock(200, {"message": "testing"})
        with mock.patch('requests.request', return_value=response):
            result, message = do_rest_call(service_handler, rest_operation, None)
            self.assertEqual(result, mock_succeed_with_message)

    @mock.patch('zerver.lib.outgoing_webhook.ServiceMessageActions.request_retry')
    def test_retry_request(self, mock_request_retry):
        # type: (mock.Mock) -> None
        response = ResponseMock(500, {"message": "testing"})
        with mock.patch('requests.request', return_value=response):
            result, message = do_rest_call(service_handler, rest_operation, None)
            self.assertEqual(result, mock_request_retry)

    @mock.patch('zerver.lib.outgoing_webhook.ServiceMessageActions.fail_with_message')
    def test_fail_request(self, mock_fail_with_message):
        # type: (mock.Mock) -> None
        response = ResponseMock(400, {"message": "testing"})
        with mock.patch('requests.request', return_value=response):
            result, message = do_rest_call(service_handler, rest_operation, None)
            self.assertEqual(result, mock_fail_with_message)

    @mock.patch('logging.info')
    @mock.patch('requests.request', side_effect=timeout_error)
    @mock.patch('zerver.lib.outgoing_webhook.ServiceMessageActions.request_retry')
    def test_timeout_request(self, mock_request_retry, mock_requests_request, mock_logger):
        # type: (mock.Mock, mock.Mock, mock.Mock) -> None
        result, message = do_rest_call(service_handler, rest_operation, {"command": ""})
        self.assertEqual(result, mock_request_retry)

    @mock.patch('logging.exception')
    @mock.patch('requests.request', side_effect=request_exception_error)
    @mock.patch('zerver.lib.outgoing_webhook.ServiceMessageActions.fail_with_message')
    def test_request_exception(self, mock_fail_with_message, mock_requests_request, mock_logger):
        # type: (mock.Mock, mock.Mock, mock.Mock) -> None
        result, message = do_rest_call(service_handler, rest_operation, {"command": ""})
        self.assertEqual(result, mock_fail_with_message)

class OutgoingWebhookServiceHandlerTests(ZulipTestCase):

    def test_service_handler_provider(self):
        # type: () -> None
        service.interface = 1

        generic_interface_class = get_service_interface_class(GENERIC_INTERFACE)
        generic_interface = generic_interface_class(base_url=service.base_url,
                                                    token=service.token,
                                                    bot_email = service.user_profile.email,
                                                    service_name = service.name)

        service_handler = get_outgoing_webhook_service_handler(service)
        self.assertEqual(service_handler.base_url, generic_interface.base_url)
        self.assertEqual(service_handler.token, generic_interface.token)
        self.assertEqual(service_handler.bot_email, generic_interface.bot_email)
        self.assertEqual(service_handler.service_name, generic_interface.service_name)

        AVAILABLE_OUTGOING_WEBHOOK_INTERFACES.pop(u'test', None)
        with mock.patch('zerver.models.Service.interface_name', return_value=u'test'):
            service_handler = get_outgoing_webhook_service_handler(service)
        self.assertEqual(service_handler.base_url, generic_interface.base_url)
        self.assertEqual(service_handler.token, generic_interface.token)
        self.assertEqual(service_handler.bot_email, generic_interface.bot_email)
        self.assertEqual(service_handler.service_name, generic_interface.service_name)
