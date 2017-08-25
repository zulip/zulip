# -*- coding: utf-8 -*-

import logging
import mock
import requests

from builtins import object
from django.test import override_settings
from requests import Response
from typing import Any, Dict, Tuple, Text, Optional

from zerver.lib.outgoing_webhook import do_rest_call, OutgoingWebhookServiceInterface
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_realm, get_user

class ResponseMock(object):
    def __init__(self, status_code, data, content):
        # type: (int, Any, str) -> None
        self.status_code = status_code
        self.data = data
        self.content = content

def request_exception_error(http_method, final_url, data, **request_kwargs):
    # type: (Any, Any, Any, **Any) -> Any
    raise requests.exceptions.RequestException("I'm a generic exception :(")

def timeout_error(http_method, final_url, data, **request_kwargs):
    # type: (Any, Any, Any, **Any) -> Any
    raise requests.exceptions.Timeout("Time is up!")

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
        self.mock_event = {
            # In the tests there is no active queue processor, so retries don't get processed.
            # Therefore, we need to emulate `retry_event` in the last stage when the maximum
            # retries have been exceeded.
            'failed_tries': 3,
            'message': {'display_recipient': 'Verona',
                        'subject': 'Foo',
                        'id': '',
                        'type': 'stream'},
            'user_profile_id': user_profile.id,
            'command': '',
            'service_name': ''}

        self.rest_operation = {'method': "POST",
                               'relative_url_path': "",
                               'request_kwargs': {},
                               'base_url': ""}
        self.bot_user = self.example_user('outgoing_webhook_bot')
        logging.disable(logging.WARNING)

    @mock.patch('zerver.lib.outgoing_webhook.succeed_with_message')
    def test_successful_request(self, mock_succeed_with_message):
        # type: (mock.Mock) -> None
        response = ResponseMock(200, {"message": "testing"}, '')
        with mock.patch('requests.request', return_value=response):
            do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
            self.assertTrue(mock_succeed_with_message.called)

    def test_retry_request(self):
        # type: (mock.Mock) -> None
        response = ResponseMock(500, {"message": "testing"}, '')

        self.mock_event['failed_tries'] = 3
        with mock.patch('requests.request', return_value=response):
            do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
            bot_owner_notification = self.get_last_message()
            self.assertEqual(bot_owner_notification.content,
                             '''[A message](http://zulip.testserver/#narrow/stream/Verona/subject/Foo/near/) triggered an outgoing webhook.
The webhook got a response with status code *500*.''')
            self.assertEqual(bot_owner_notification.recipient_id, self.bot_user.bot_owner.id)
        self.mock_event['failed_tries'] = 0

    @mock.patch('zerver.lib.outgoing_webhook.fail_with_message')
    def test_fail_request(self, mock_fail_with_message):
        # type: (mock.Mock) -> None
        response = ResponseMock(400, {"message": "testing"}, '')
        with mock.patch('requests.request', return_value=response):
            do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
            bot_owner_notification = self.get_last_message()
            self.assertTrue(mock_fail_with_message.called)
            self.assertEqual(bot_owner_notification.content,
                             '''[A message](http://zulip.testserver/#narrow/stream/Verona/subject/Foo/near/) triggered an outgoing webhook.
The webhook got a response with status code *400*.''')
            self.assertEqual(bot_owner_notification.recipient_id, self.bot_user.bot_owner.id)

    @mock.patch('logging.info')
    @mock.patch('requests.request', side_effect=timeout_error)
    def test_timeout_request(self, mock_requests_request, mock_logger):
        # type: (mock.Mock, mock.Mock, mock.Mock) -> None
        do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
        bot_owner_notification = self.get_last_message()
        self.assertEqual(bot_owner_notification.content,
                         '''[A message](http://zulip.testserver/#narrow/stream/Verona/subject/Foo/near/) triggered an outgoing webhook.
When trying to send a request to the webhook service, an exception of type Timeout occured:
```
Time is up!
```''')
        self.assertEqual(bot_owner_notification.recipient_id, self.bot_user.bot_owner.id)

    @mock.patch('logging.exception')
    @mock.patch('requests.request', side_effect=request_exception_error)
    @mock.patch('zerver.lib.outgoing_webhook.fail_with_message')
    def test_request_exception(self, mock_fail_with_message, mock_requests_request, mock_logger):
        # type: (mock.Mock, mock.Mock, mock.Mock) -> None
        do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
        bot_owner_notification = self.get_last_message()
        self.assertTrue(mock_fail_with_message.called)
        self.assertEqual(bot_owner_notification.content,
                         '''[A message](http://zulip.testserver/#narrow/stream/Verona/subject/Foo/near/) triggered an outgoing webhook.
When trying to send a request to the webhook service, an exception of type RequestException occured:
```
I'm a generic exception :(
```''')
        self.assertEqual(bot_owner_notification.recipient_id, self.bot_user.bot_owner.id)
