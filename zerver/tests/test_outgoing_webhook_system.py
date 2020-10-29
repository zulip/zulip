from typing import Any, Dict
from unittest import mock

import orjson
import requests

from version import ZULIP_VERSION
from zerver.lib.actions import do_create_user
from zerver.lib.outgoing_webhook import (
    GenericOutgoingWebhookService,
    SlackOutgoingWebhookService,
    do_rest_call,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic import TOPIC_NAME
from zerver.lib.users import add_service
from zerver.models import Recipient, Service, UserProfile, get_display_recipient


class ResponseMock:
    def __init__(self, status_code: int, content: bytes=b"") -> None:
        self.status_code = status_code
        self.content = content
        self.text = content.decode()

def request_exception_error(http_method: Any, final_url: Any, data: Any, **request_kwargs: Any) -> Any:
    raise requests.exceptions.RequestException("I'm a generic exception :(")

def timeout_error(http_method: Any, final_url: Any, data: Any, **request_kwargs: Any) -> Any:
    raise requests.exceptions.Timeout("Time is up!")

def connection_error(http_method: Any, final_url: Any, data: Any, **request_kwargs: Any) -> Any:
    raise requests.exceptions.ConnectionError()

class DoRestCallTests(ZulipTestCase):
    def mock_event(self, bot_user: UserProfile) -> Dict[str, Any]:
        return {
            # In the tests there is no active queue processor, so retries don't get processed.
            # Therefore, we need to emulate `retry_event` in the last stage when the maximum
            # retries have been exceeded.
            'failed_tries': 3,
            'message': {'display_recipient': 'Verona',
                        'stream_id': 999,
                        TOPIC_NAME: 'Foo',
                        'id': '',
                        'type': 'stream'},
            'user_profile_id': bot_user.id,
            'command': '',
            'service_name': ''}

    def test_successful_request(self) -> None:
        bot_user = self.example_user('outgoing_webhook_bot')
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        response = ResponseMock(200, orjson.dumps(dict(content='whatever')))
        expect_200 = mock.patch('requests.request', return_value=response)

        expect_send_response = mock.patch('zerver.lib.outgoing_webhook.send_response_message')
        with expect_200, expect_send_response as mock_send:
            do_rest_call('', None, mock_event, service_handler)
        self.assertTrue(mock_send.called)

        for service_class in [GenericOutgoingWebhookService, SlackOutgoingWebhookService]:
            handler = service_class("token", bot_user, "service")

            with expect_200:
                do_rest_call('', None, mock_event, handler)

            # TODO: assert something interesting here?

    def test_retry_request(self) -> None:
        bot_user = self.example_user('outgoing_webhook_bot')
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        response = ResponseMock(500)
        with mock.patch('requests.request', return_value=response), self.assertLogs(level="WARNING") as m:
            final_response = do_rest_call('',  None, mock_event, service_handler)
            assert final_response is not None

            self.assertEqual(m.output, [f"WARNING:root:Message http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/ triggered an outgoing webhook, returning status code 500.\n Content of response (in quotes): \"{final_response.content.decode()}\""])
        bot_owner_notification = self.get_last_message()
        self.assertEqual(bot_owner_notification.content,
                         '''[A message](http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/) triggered an outgoing webhook.
The webhook got a response with status code *500*.''')

        assert bot_user.bot_owner is not None
        self.assertEqual(bot_owner_notification.recipient_id, bot_user.bot_owner.id)

    def test_fail_request(self) -> None:
        bot_user = self.example_user('outgoing_webhook_bot')
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        response = ResponseMock(400)
        expect_400 = mock.patch("requests.request", return_value=response)
        expect_fail = mock.patch("zerver.lib.outgoing_webhook.fail_with_message")

        with expect_400, expect_fail as mock_fail, self.assertLogs(level="WARNING") as m:
            final_response = do_rest_call('', None, mock_event, service_handler)
            assert final_response is not None

            self.assertEqual(m.output, [f"WARNING:root:Message http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/ triggered an outgoing webhook, returning status code 400.\n Content of response (in quotes): \"{final_response.content.decode()}\""])

        self.assertTrue(mock_fail.called)

        bot_owner_notification = self.get_last_message()
        self.assertEqual(bot_owner_notification.content,
                         '''[A message](http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/) triggered an outgoing webhook.
The webhook got a response with status code *400*.''')

        assert bot_user.bot_owner is not None
        self.assertEqual(bot_owner_notification.recipient_id, bot_user.bot_owner.id)

    def test_headers(self) -> None:
        bot_user = self.example_user('outgoing_webhook_bot')
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        with mock.patch('requests.request') as mock_request, self.assertLogs(level="WARNING") as m:
            final_response = do_rest_call('', 'payload-stub', mock_event, service_handler)
            assert final_response is not None

            self.assertEqual(m.output, [f"WARNING:root:Message http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/ triggered an outgoing webhook, returning status code {final_response.status_code}.\n Content of response (in quotes): \"{final_response.content.decode()}\""])

        kwargs = mock_request.call_args[1]
        self.assertEqual(kwargs['data'], 'payload-stub')

        user_agent = 'ZulipOutgoingWebhook/' + ZULIP_VERSION
        headers = {
            'content-type': 'application/json',
            'User-Agent': user_agent,
        }
        self.assertEqual(kwargs['headers'], headers)

    def test_error_handling(self) -> None:
        bot_user = self.example_user('outgoing_webhook_bot')
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")
        bot_user_email = self.example_user_map['outgoing_webhook_bot']

        def helper(side_effect: Any, error_text: str) -> None:

            with mock.patch('requests.request', side_effect=side_effect):
                do_rest_call('', None, mock_event, service_handler)

            bot_owner_notification = self.get_last_message()
            self.assertIn(error_text, bot_owner_notification.content)
            self.assertIn('triggered', bot_owner_notification.content)
            assert bot_user.bot_owner is not None
            self.assertEqual(bot_owner_notification.recipient_id, bot_user.bot_owner.id)

        with self.assertLogs(level="INFO") as i:
            helper(side_effect=timeout_error, error_text='A timeout occurred.')
            helper(side_effect=connection_error, error_text='A connection error occurred.')

            log_output = [
                f"INFO:root:Trigger event {mock_event['command']} on {mock_event['service_name']} timed out. Retrying",
                f"WARNING:root:Maximum retries exceeded for trigger:{bot_user_email} event:{mock_event['command']}",
                f"INFO:root:Trigger event {mock_event['command']} on {mock_event['service_name']} resulted in a connection error. Retrying",
                f"WARNING:root:Maximum retries exceeded for trigger:{bot_user_email} event:{mock_event['command']}"
            ]

            self.assertEqual(i.output, log_output)

    def test_request_exception(self) -> None:
        bot_user = self.example_user('outgoing_webhook_bot')
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        expect_request_exception = mock.patch("requests.request", side_effect=request_exception_error)
        expect_logging_exception = self.assertLogs(level="ERROR")
        expect_fail = mock.patch("zerver.lib.outgoing_webhook.fail_with_message")

        # Don't think that we should catch and assert whole log output(which is actually a very big error traceback).
        # We are already asserting bot_owner_notification.content which verifies exception did occur.
        with expect_request_exception, expect_logging_exception, expect_fail as mock_fail:
            do_rest_call('', None, mock_event, service_handler)

        self.assertTrue(mock_fail.called)

        bot_owner_notification = self.get_last_message()
        self.assertEqual(bot_owner_notification.content,
                         '''[A message](http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/) triggered an outgoing webhook.
When trying to send a request to the webhook service, an exception of type RequestException occurred:
```
I'm a generic exception :(
```''')
        assert bot_user.bot_owner is not None
        self.assertEqual(bot_owner_notification.recipient_id, bot_user.bot_owner.id)

class TestOutgoingWebhookMessaging(ZulipTestCase):
    def create_outgoing_bot(self, bot_owner: UserProfile) -> UserProfile:
        return self.create_test_bot(
            'outgoing-webhook',
            bot_owner,
            full_name='Outgoing Webhook bot',
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            service_name='foo-service',
        )

    def test_multiple_services(self) -> None:
        bot_owner = self.example_user("othello")

        bot = do_create_user(
            bot_owner=bot_owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            full_name='Outgoing Webhook Bot',
            email='whatever',
            realm=bot_owner.realm,
            password=None,
        )

        add_service(
            'weather',
            user_profile=bot,
            interface=Service.GENERIC,
            base_url='weather_url',
            token='weather_token',
        )

        add_service(
            'qotd',
            user_profile=bot,
            interface=Service.GENERIC,
            base_url='qotd_url',
            token='qotd_token',
        )

        sender = self.example_user("hamlet")

        with mock.patch('zerver.worker.queue_processors.do_rest_call') as m:
            self.send_personal_message(
                sender,
                bot,
                content="some content",
            )

        url_token_tups = set()
        for item in m.call_args_list:
            args = item[0]
            base_url = args[0]
            request_data = orjson.loads(args[1])
            tup = (base_url, request_data['token'])
            url_token_tups.add(tup)
            message_data = request_data['message']
            self.assertEqual(message_data['content'], 'some content')
            self.assertEqual(message_data['sender_id'], sender.id)

        self.assertEqual(
            url_token_tups,
            {
                ('weather_url', 'weather_token'),
                ('qotd_url', 'qotd_token'),
            },
        )

    @mock.patch('requests.request', return_value=ResponseMock(200, orjson.dumps({"response_string": "Hidley ho, I'm a webhook responding!"})))
    def test_pm_to_outgoing_webhook_bot(self, mock_requests_request: mock.Mock) -> None:
        bot_owner = self.example_user("othello")
        bot = self.create_outgoing_bot(bot_owner)
        sender = self.example_user("hamlet")

        self.send_personal_message(sender, bot,
                                   content="foo")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "Hidley ho, I'm a webhook responding!")
        self.assertEqual(last_message.sender_id, bot.id)
        self.assertEqual(
            last_message.recipient.type_id,
            sender.id,
        )
        self.assertEqual(
            last_message.recipient.type,
            Recipient.PERSONAL,
        )

    @mock.patch('requests.request', return_value=ResponseMock(200, orjson.dumps({"response_string": "Hidley ho, I'm a webhook responding!"})))
    def test_stream_message_to_outgoing_webhook_bot(self, mock_requests_request: mock.Mock) -> None:
        bot_owner = self.example_user("othello")
        bot = self.create_outgoing_bot(bot_owner)

        self.send_stream_message(bot_owner, "Denmark",
                                 content=f"@**{bot.full_name}** foo",
                                 topic_name="bar")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "Hidley ho, I'm a webhook responding!")
        self.assertEqual(last_message.sender_id, bot.id)
        self.assertEqual(last_message.topic_name(), "bar")
        display_recipient = get_display_recipient(last_message.recipient)
        self.assertEqual(display_recipient, "Denmark")
