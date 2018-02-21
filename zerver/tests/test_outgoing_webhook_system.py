# -*- coding: utf-8 -*-

import ujson
import logging
import mock
import requests

from builtins import object
from django.test import override_settings
from requests import Response
from typing import Any, Dict, Tuple, Text, Optional

from zerver.lib.outgoing_webhook import do_rest_call, OutgoingWebhookServiceInterface
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import get_realm, get_user, UserProfile, get_display_recipient

class ResponseMock:
    def __init__(self, status_code: int, content: Optional[Any]=None) -> None:
        self.status_code = status_code
        self.content = content
        self.text = ujson.dumps(content)

def request_exception_error(http_method: Any, final_url: Any, data: Any, **request_kwargs: Any) -> Any:
    raise requests.exceptions.RequestException("I'm a generic exception :(")

def timeout_error(http_method: Any, final_url: Any, data: Any, **request_kwargs: Any) -> Any:
    raise requests.exceptions.Timeout("Time is up!")

class MockServiceHandler(OutgoingWebhookServiceInterface):
    def process_success(self, response: Response, event: Dict[Text, Any]) -> Optional[str]:
        return "Success!"

service_handler = MockServiceHandler(None, None, None, None)

class DoRestCallTests(ZulipTestCase):
    def setUp(self) -> None:
        realm = get_realm("zulip")
        user_profile = get_user("outgoing-webhook@zulip.com", realm)
        self.mock_event = {
            # In the tests there is no active queue processor, so retries don't get processed.
            # Therefore, we need to emulate `retry_event` in the last stage when the maximum
            # retries have been exceeded.
            'failed_tries': 3,
            'message': {'display_recipient': 'Verona',
                        'stream_id': 999,
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
    def test_successful_request(self, mock_succeed_with_message: mock.Mock) -> None:
        response = ResponseMock(200)
        with mock.patch('requests.request', return_value=response):
            do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
            self.assertTrue(mock_succeed_with_message.called)

    def test_retry_request(self: mock.Mock) -> None:
        response = ResponseMock(500)

        self.mock_event['failed_tries'] = 3
        with mock.patch('requests.request', return_value=response):
            do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
            bot_owner_notification = self.get_last_message()
            self.assertEqual(bot_owner_notification.content,
                             '''[A message](http://zulip.testserver/#narrow/stream/999-Verona/subject/Foo/near/) triggered an outgoing webhook.
The webhook got a response with status code *500*.''')
            self.assertEqual(bot_owner_notification.recipient_id, self.bot_user.bot_owner.id)
        self.mock_event['failed_tries'] = 0

    @mock.patch('zerver.lib.outgoing_webhook.fail_with_message')
    def test_fail_request(self, mock_fail_with_message: mock.Mock) -> None:
        response = ResponseMock(400)
        with mock.patch('requests.request', return_value=response):
            do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
            bot_owner_notification = self.get_last_message()
            self.assertTrue(mock_fail_with_message.called)
            self.assertEqual(bot_owner_notification.content,
                             '''[A message](http://zulip.testserver/#narrow/stream/999-Verona/subject/Foo/near/) triggered an outgoing webhook.
The webhook got a response with status code *400*.''')
            self.assertEqual(bot_owner_notification.recipient_id, self.bot_user.bot_owner.id)

    @mock.patch('logging.info')
    @mock.patch('requests.request', side_effect=timeout_error)
    def test_timeout_request(self, mock_requests_request: mock.Mock, mock_logger: mock.Mock) -> None:
        do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
        bot_owner_notification = self.get_last_message()
        self.assertEqual(bot_owner_notification.content,
                         '''[A message](http://zulip.testserver/#narrow/stream/999-Verona/subject/Foo/near/) triggered an outgoing webhook.
When trying to send a request to the webhook service, an exception of type Timeout occurred:
```
Time is up!
```''')
        self.assertEqual(bot_owner_notification.recipient_id, self.bot_user.bot_owner.id)

    @mock.patch('logging.exception')
    @mock.patch('requests.request', side_effect=request_exception_error)
    @mock.patch('zerver.lib.outgoing_webhook.fail_with_message')
    def test_request_exception(self, mock_fail_with_message: mock.Mock,
                               mock_requests_request: mock.Mock, mock_logger: mock.Mock) -> None:
        do_rest_call(self.rest_operation, None, self.mock_event, service_handler, None)
        bot_owner_notification = self.get_last_message()
        self.assertTrue(mock_fail_with_message.called)
        self.assertEqual(bot_owner_notification.content,
                         '''[A message](http://zulip.testserver/#narrow/stream/999-Verona/subject/Foo/near/) triggered an outgoing webhook.
When trying to send a request to the webhook service, an exception of type RequestException occurred:
```
I'm a generic exception :(
```''')
        self.assertEqual(bot_owner_notification.recipient_id, self.bot_user.bot_owner.id)

class TestOutgoingWebhookMessaging(ZulipTestCase):
    def setUp(self) -> None:
        self.user_profile = self.example_user("othello")
        self.bot_profile = self.create_test_bot('outgoing-webhook', self.user_profile,
                                                full_name='Outgoing Webhook bot',
                                                bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                                service_name='foo-service')

    @mock.patch('requests.request', return_value=ResponseMock(200, {"response_string": "Hidley ho, I'm a webhook responding!"}))
    def test_pm_to_outgoing_webhook_bot(self, mock_requests_request: mock.Mock) -> None:
        self.send_personal_message(self.user_profile.email, self.bot_profile.email,
                                   content="foo")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "Success! Hidley ho, I'm a webhook responding!")
        self.assertEqual(last_message.sender_id, self.bot_profile.id)
        display_recipient = get_display_recipient(last_message.recipient)
        # The next two lines error on mypy because the display_recipient is of type Union[Text, List[Dict[str, Any]]].
        # In this case, we know that display_recipient will be of type List[Dict[str, Any]].
        # Otherwise this test will error, which is wanted behavior anyway.
        self.assert_length(display_recipient, 1)  # type: ignore
        self.assertEqual(display_recipient[0]['email'], self.user_profile.email)   # type: ignore

    @mock.patch('requests.request', return_value=ResponseMock(200, {"response_string": "Hidley ho, I'm a webhook responding!"}))
    def test_stream_message_to_outgoing_webhook_bot(self, mock_requests_request: mock.Mock) -> None:
        self.send_stream_message(self.user_profile.email, "Denmark",
                                 content="@**{}** foo".format(self.bot_profile.full_name),
                                 topic_name="bar")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "Success! Hidley ho, I'm a webhook responding!")
        self.assertEqual(last_message.sender_id, self.bot_profile.id)
        self.assertEqual(last_message.subject, "bar")
        display_recipient = get_display_recipient(last_message.recipient)
        self.assertEqual(display_recipient, "Denmark")
