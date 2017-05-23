# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import mock
from typing import Any, Union, Mapping, Callable

from zerver.lib.test_classes import ZulipTestCase

from zerver.models import (
    get_realm_by_email_domain,
    UserProfile,
    Recipient,
    Service,
)
from zerver.lib.outgoing_webhook import do_rest_call

from zerver.lib.actions import do_create_user
import requests

rest_operation = {'method': "POST",
                  'relative_url_path': "",
                  'request_kwargs': {},
                  'base_url': ""}

class ResponseMock(object):
    def __init__(self, status_code, data, content):
        # type: (int, Any, str) -> None
        self.status_code = status_code
        self.data = data
        self.content = content

def request_exception_error(http_method, final_url, data, **request_kwargs):
    # type: (Any, Any, Any, Any) -> Any
    raise requests.exceptions.RequestException

def timeout_error(http_method, final_url, data, **request_kwargs):
    # type: (Any, Any, Any, Any) -> Any
    raise requests.exceptions.Timeout

class DoRestCallTests(ZulipTestCase):
    @mock.patch('zerver.lib.outgoing_webhook.succeed_with_message')
    def test_successful_request(self, mock_succeed_with_message):
        # type: (mock.Mock) -> None
        response = ResponseMock(200, {"message": "testing"}, '')
        with mock.patch('requests.request', return_value=response):
            do_rest_call(rest_operation, None, None)
            self.assertTrue(mock_succeed_with_message.called)

    @mock.patch('zerver.lib.outgoing_webhook.request_retry')
    def test_retry_request(self, mock_request_retry):
        # type: (mock.Mock) -> None
        response = ResponseMock(500, {"message": "testing"}, '')
        with mock.patch('requests.request', return_value=response):
            do_rest_call(rest_operation, None, None)
            self.assertTrue(mock_request_retry.called)

    @mock.patch('zerver.lib.outgoing_webhook.fail_with_message')
    def test_fail_request(self, mock_fail_with_message):
        # type: (mock.Mock) -> None
        response = ResponseMock(400, {"message": "testing"}, '')
        with mock.patch('requests.request', return_value=response):
            do_rest_call(rest_operation, None, None)
            self.assertTrue(mock_fail_with_message.called)

    @mock.patch('logging.info')
    @mock.patch('requests.request', side_effect=timeout_error)
    @mock.patch('zerver.lib.outgoing_webhook.request_retry')
    def test_timeout_request(self, mock_request_retry, mock_requests_request, mock_logger):
        # type: (mock.Mock, mock.Mock, mock.Mock) -> None
        do_rest_call(rest_operation, {"command": "", "service_name": ""}, None)
        self.assertTrue(mock_request_retry.called)

    @mock.patch('logging.exception')
    @mock.patch('requests.request', side_effect=request_exception_error)
    @mock.patch('zerver.lib.outgoing_webhook.fail_with_message')
    def test_request_exception(self, mock_fail_with_message, mock_requests_request, mock_logger):
        # type: (mock.Mock, mock.Mock, mock.Mock) -> None
        do_rest_call(rest_operation, {"command": ""}, None)
        self.assertTrue(mock_fail_with_message.called)


class TestMentionMessageTrigger(ZulipTestCase):

    def check_values_passed(self, queue_name, trigger_event, x):
        # type: (Any, Union[Mapping[Any, Any], Any], Callable[[Any], None]) -> None
        self.assertEqual(queue_name, "outgoing_webhooks")
        self.assertEqual(trigger_event['user_profile_id'], self.bot_profile.id)
        self.assertEqual(trigger_event['trigger'], "mention")
        self.assertEqual(trigger_event["message"]["sender_email"], self.user_profile.email)
        self.assertEqual(trigger_event["message"]["content"], self.content)
        self.assertEqual(trigger_event["message"]["type"], Recipient._type_names[Recipient.STREAM])
        self.assertEqual(trigger_event["message"]["display_recipient"], "Denmark")

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_mention_message_event_flow(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        self.user_profile = self.example_user("othello")
        self.bot_profile = do_create_user(email="foo-bot@zulip.com",
                                          password="test",
                                          realm=get_realm_by_email_domain("zulip.com"),
                                          full_name="FooBot",
                                          short_name="foo-bot",
                                          bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                          bot_owner=self.user_profile)
        self.content = u'@**FooBot** foo bar!!!'
        mock_queue_json_publish.side_effect = self.check_values_passed

        # TODO: In future versions this won't be required
        self.subscribe_to_stream(self.bot_profile.email, "Denmark")
        self.send_message(self.user_profile.email, "Denmark", Recipient.STREAM, self.content)
        self.assertTrue(mock_queue_json_publish.called)
