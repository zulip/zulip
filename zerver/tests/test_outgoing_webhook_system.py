# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import mock
from typing import Any, Union, Mapping, Callable, Text, List

from zerver.lib.test_helpers import get_user_profile_by_email
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
        self.user_profile = get_user_profile_by_email("othello@zulip.com")
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

class PersonalMessageTriggersTest(ZulipTestCase):

    def setUp(self):
        # type: () -> None
        user_profile = get_user_profile_by_email("othello@zulip.com")
        self.bot_user = do_create_user(email="testvabs-bot@zulip.com",
                                       password="test",
                                       realm=get_realm_by_email_domain("zulip.com"),
                                       full_name="The Test Bot",
                                       short_name="bot",
                                       bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                       bot_owner=user_profile)
        self.temp_bot = do_create_user(email="temp-bot@zulip.com",
                                       password="temp",
                                       realm=get_realm_by_email_domain("zulip.com"),
                                       full_name="The Temp test Bot",
                                       short_name="tempbot",
                                       bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                       bot_owner=user_profile)

    def test_no_trigger_on_stream_message(self):
        # type: () -> None
        sender_email = "othello@zulip.com"
        recipients = "Denmark"
        message_type = Recipient.STREAM
        with mock.patch('zerver.lib.actions.queue_json_publish') as queue_json_publish:
            self.send_message(sender_email, recipients, message_type)
            self.assertFalse(queue_json_publish.called)

    def test_no_trigger_on_message_by_bot(self):
        # type: () -> None
        sender_email = "testvabs-bot@zulip.com"
        recipients = "othello@zulip.com"
        message_type = Recipient.PERSONAL

        with mock.patch('zerver.lib.actions.queue_json_publish') as queue_json_publish:
            self.send_message(sender_email, recipients, message_type)
            self.assertFalse(queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_trigger_on_private_message_by_user(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        sender_email = "othello@zulip.com"
        recipients = "testvabs-bot@zulip.com"
        message_type = Recipient.PERSONAL
        profile_id = self.bot_user.id

        def check_values_passed(queue_name, trigger_event, x):
            # type: (Any, Union[Mapping[Any, Any], Any], Callable[[Any], None]) -> None
            self.assertEqual(queue_name, "outgoing_webhooks")
            self.assertEqual(trigger_event["user_profile_id"], profile_id)
            self.assertEqual(trigger_event["trigger"], "private_message")
            self.assertEqual(trigger_event["failed_tries"], 0)
            self.assertEqual(trigger_event["message"]["sender_email"], sender_email)
            self.assertEqual(trigger_event["message"]["display_recipient"][0]["email"], sender_email)
            self.assertEqual(trigger_event["message"]["display_recipient"][1]["email"], recipients)
            self.assertEqual(trigger_event["message"]["type"], u'private')

        mock_queue_json_publish.side_effect = check_values_passed
        self.send_message(sender_email, recipients, message_type, subject='', content='test')
        self.assertTrue(mock_queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_trigger_on_huddle_message_by_user(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        sender_email = "othello@zulip.com"
        recipients = [u"testvabs-bot@zulip.com", u"temp-bot@zulip.com"]
        message_type = Recipient.HUDDLE
        profile_ids = [self.bot_user.id, self.temp_bot.id]

        def check_values_passed(queue_name, trigger_event, x):
            # type: (Any, Union[Mapping[Any, Any], Any], Callable[[Any], None]) -> None
            self.assertEqual(queue_name, "outgoing_webhooks")
            self.assertIn(trigger_event["user_profile_id"], profile_ids)
            profile_ids.remove(trigger_event["user_profile_id"])
            self.assertEqual(trigger_event["trigger"], "private_message")
            self.assertEqual(trigger_event["failed_tries"], 0)
            self.assertEqual(trigger_event["message"]["sender_email"], sender_email)
            self.assertEqual(trigger_event["message"]["type"], u'private')

        mock_queue_json_publish.side_effect = check_values_passed
        self.send_message(sender_email, recipients, message_type, subject='', content='test')
        self.assertEqual(mock_queue_json_publish.call_count, 2)
