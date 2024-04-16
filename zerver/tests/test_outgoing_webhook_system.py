from typing import Any, Dict, Optional
from unittest import mock

import orjson
import requests
import responses

from version import ZULIP_VERSION
from zerver.actions.create_user import do_create_user
from zerver.actions.streams import do_deactivate_stream
from zerver.lib.exceptions import JsonableError
from zerver.lib.outgoing_webhook import (
    GenericOutgoingWebhookService,
    SlackOutgoingWebhookService,
    do_rest_call,
    fail_with_message,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.topic import TOPIC_NAME
from zerver.lib.url_encoding import near_message_url
from zerver.lib.users import add_service
from zerver.models import Recipient, Service, UserProfile
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream


class ResponseMock:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content
        self.text = content.decode()


def request_exception_error(final_url: Any, **request_kwargs: Any) -> Any:
    raise requests.exceptions.RequestException("I'm a generic exception :(")


def timeout_error(final_url: Any, **request_kwargs: Any) -> Any:
    raise requests.exceptions.Timeout("Time is up!")


def connection_error(final_url: Any, **request_kwargs: Any) -> Any:
    raise requests.exceptions.ConnectionError


class DoRestCallTests(ZulipTestCase):
    def mock_event(self, bot_user: UserProfile) -> Dict[str, Any]:
        return {
            # In the tests there is no active queue processor, so retries don't get processed.
            # Therefore, we need to emulate `retry_event` in the last stage when the maximum
            # retries have been exceeded.
            "failed_tries": 3,
            "message": {
                "display_recipient": "Verona",
                "stream_id": 999,
                "sender_id": bot_user.id,
                "sender_email": bot_user.email,
                "sender_realm_id": bot_user.realm.id,
                "sender_realm_str": bot_user.realm.string_id,
                "sender_delivery_email": bot_user.delivery_email,
                "sender_full_name": bot_user.full_name,
                "sender_avatar_source": UserProfile.AVATAR_FROM_GRAVATAR,
                "sender_avatar_version": 1,
                "sender_email_address_visibility": UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE,
                "recipient_type": "stream",
                "recipient_type_id": 999,
                "sender_is_mirror_dummy": False,
                TOPIC_NAME: "Foo",
                "id": "",
                "type": "stream",
                "timestamp": 1,
            },
            "trigger": "mention",
            "user_profile_id": bot_user.id,
            "command": "",
            "service_name": "",
        }

    def test_successful_request(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        def _helper(content: Optional[str]) -> None:
            expect_send_response = mock.patch("zerver.lib.outgoing_webhook.send_response_message")
            with mock.patch.object(
                service_handler, "session"
            ) as session, expect_send_response as mock_send:
                session.post.return_value = ResponseMock(200, orjson.dumps(dict(content=content)))
                with self.assertLogs(level="INFO") as logs:
                    do_rest_call("", mock_event, service_handler)
                self.assert_length(logs.output, 1)
                self.assertIn(
                    f"Outgoing webhook request from {bot_user.id}@zulip took ", logs.output[0]
                )

            if content == "":
                self.assertFalse(mock_send.called)
            else:
                self.assertTrue(mock_send.called)

            for service_class in [GenericOutgoingWebhookService, SlackOutgoingWebhookService]:
                handler = service_class("token", bot_user, "service")
                with mock.patch.object(handler, "session") as session:
                    session.post.return_value = ResponseMock(200, b"{}")
                    with self.assertLogs(level="INFO") as logs:
                        do_rest_call("", mock_event, handler)
                    self.assert_length(logs.output, 1)
                    self.assertIn(
                        f"Outgoing webhook request from {bot_user.id}@zulip took ", logs.output[0]
                    )
                    session.post.assert_called_once()

        _helper("whatever")
        _helper("")
        _helper(None)

    def test_retry_request(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        with mock.patch.object(service_handler, "session") as session, self.assertLogs(
            level="WARNING"
        ) as m:
            session.post.return_value = ResponseMock(500)
            final_response = do_rest_call("", mock_event, service_handler)
            assert final_response is not None

            self.assertEqual(
                m.output,
                [
                    f'WARNING:root:Message http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/ triggered an outgoing webhook, returning status code 500.\n Content of response (in quotes): "{final_response.text}"'
                ],
            )
        bot_owner_notification = self.get_last_message()
        self.assertEqual(
            bot_owner_notification.content,
            """[A message](http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/) to your bot @_**Outgoing Webhook** triggered an outgoing webhook.
The webhook got a response with status code *500*.""",
        )

        assert bot_user.bot_owner is not None
        self.assertEqual(bot_owner_notification.recipient_id, bot_user.bot_owner.recipient_id)

    def test_bad_msg_type(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        mock_event["message"]["type"] = "unknown"
        with mock.patch.object(service_handler, "session") as session, self.assertRaises(
            JsonableError
        ), self.assertLogs(level="INFO"):
            session.post.return_value = ResponseMock(200)
            url = "http://somewhere.com/api/call"
            with mock.patch("zerver.lib.outgoing_webhook.get_message_url", return_value=url):
                do_rest_call("", mock_event, service_handler)

    def test_response_none(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        with mock.patch(
            "zerver.lib.outgoing_webhook.GenericOutgoingWebhookService.make_request",
            return_value=None,
        ), self.assertLogs(level="INFO") as logs:
            resp = do_rest_call("", mock_event, service_handler)
            self.assertEqual(resp, None)
        self.assert_length(logs.output, 1)

    def test_fail_request(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        expect_fail = mock.patch("zerver.lib.outgoing_webhook.fail_with_message")

        with mock.patch.object(
            service_handler, "session"
        ) as session, expect_fail as mock_fail, self.assertLogs(level="WARNING") as m:
            session.post.return_value = ResponseMock(400)
            final_response = do_rest_call("", mock_event, service_handler)
            assert final_response is not None

            self.assertEqual(
                m.output,
                [
                    f'WARNING:root:Message http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/ triggered an outgoing webhook, returning status code 400.\n Content of response (in quotes): "{final_response.text}"'
                ],
            )

        self.assertTrue(mock_fail.called)

        bot_owner_notification = self.get_last_message()
        self.assertEqual(
            bot_owner_notification.content,
            """[A message](http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/) to your bot @_**Outgoing Webhook** triggered an outgoing webhook.
The webhook got a response with status code *400*.""",
        )

        assert bot_user.bot_owner is not None
        self.assertEqual(bot_owner_notification.recipient_id, bot_user.bot_owner.recipient_id)

    def test_headers(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        session = service_handler.session
        with mock.patch.object(session, "send") as mock_send:
            mock_send.return_value = ResponseMock(200, b"{}")
            with self.assertLogs(level="INFO") as logs:
                final_response = do_rest_call("https://example.com/", mock_event, service_handler)
            assert final_response is not None

            self.assert_length(logs.output, 1)
            self.assertIn(
                f"Outgoing webhook request from {bot_user.id}@zulip took ", logs.output[0]
            )

            mock_send.assert_called_once()
            prepared_request = mock_send.call_args[0][0]
            user_agent = "ZulipOutgoingWebhook/" + ZULIP_VERSION
            headers = {
                "Content-Type": "application/json",
                "User-Agent": user_agent,
            }
            self.assertLessEqual(headers.items(), prepared_request.headers.items())

    def test_error_handling(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")
        bot_user_email = self.example_user_map["outgoing_webhook_bot"]

        def helper(side_effect: Any, error_text: str) -> None:
            with mock.patch.object(service_handler, "session") as session:
                session.post.side_effect = side_effect
                do_rest_call("", mock_event, service_handler)

            bot_owner_notification = self.get_last_message()
            self.assertIn(error_text, bot_owner_notification.content)
            self.assertIn("triggered", bot_owner_notification.content)
            assert bot_user.bot_owner is not None
            self.assertEqual(bot_owner_notification.recipient_id, bot_user.bot_owner.recipient_id)

        with self.assertLogs(level="INFO") as i:
            helper(side_effect=timeout_error, error_text="Request timed out after")
            helper(side_effect=connection_error, error_text="A connection error occurred.")

            log_output = [
                f"INFO:root:Trigger event {mock_event['command']} on {mock_event['service_name']} timed out. Retrying",
                f"WARNING:root:Maximum retries exceeded for trigger:{bot_user_email} event:{mock_event['command']}",
                f"INFO:root:Trigger event {mock_event['command']} on {mock_event['service_name']} resulted in a connection error. Retrying",
                f"WARNING:root:Maximum retries exceeded for trigger:{bot_user_email} event:{mock_event['command']}",
            ]

            self.assertEqual(i.output, log_output)

    def test_request_exception(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        expect_logging_exception = self.assertLogs(level="ERROR")
        expect_fail = mock.patch("zerver.lib.outgoing_webhook.fail_with_message")

        # Don't think that we should catch and assert whole log output(which is actually a very big error traceback).
        # We are already asserting bot_owner_notification.content which verifies exception did occur.
        with mock.patch.object(
            service_handler, "session"
        ) as session, expect_logging_exception, expect_fail as mock_fail:
            session.post.side_effect = request_exception_error
            do_rest_call("", mock_event, service_handler)

        self.assertTrue(mock_fail.called)

        bot_owner_notification = self.get_last_message()
        self.assertEqual(
            bot_owner_notification.content,
            """[A message](http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/) to your bot @_**Outgoing Webhook** triggered an outgoing webhook.
When trying to send a request to the webhook service, an exception of type RequestException occurred:
```
I'm a generic exception :(
```""",
        )
        assert bot_user.bot_owner is not None
        self.assertEqual(bot_owner_notification.recipient_id, bot_user.bot_owner.recipient_id)

    def test_jsonable_exception(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        # The "widget_content" key is required to be a string which is
        # itself JSON-encoded; passing arbitrary text data in it will
        # cause the hook to fail.
        response = {"content": "whatever", "widget_content": "test"}
        expect_logging_info = self.assertLogs(level="INFO")
        expect_fail = mock.patch("zerver.lib.outgoing_webhook.fail_with_message")

        with responses.RequestsMock(assert_all_requests_are_fired=True) as requests_mock:
            requests_mock.add(
                requests_mock.POST, "https://example.zulip.com", status=200, json=response
            )
            with expect_logging_info, expect_fail as mock_fail:
                do_rest_call("https://example.zulip.com", mock_event, service_handler)
            self.assertTrue(mock_fail.called)
            bot_owner_notification = self.get_last_message()
            self.assertEqual(
                bot_owner_notification.content,
                """[A message](http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/) to your bot @_**Outgoing Webhook** triggered an outgoing webhook.
The outgoing webhook server attempted to send a message in Zulip, but that request resulted in the following error:
> Widgets: API programmer sent invalid JSON content\nThe response contains the following payload:\n```\n'{"content": "whatever", "widget_content": "test"}'\n```""",
            )
        assert bot_user.bot_owner is not None
        self.assertEqual(bot_owner_notification.recipient_id, bot_user.bot_owner.recipient_id)

    def test_invalid_response_format(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        expect_logging_info = self.assertLogs(level="INFO")
        expect_fail = mock.patch("zerver.lib.outgoing_webhook.fail_with_message")

        with responses.RequestsMock(assert_all_requests_are_fired=True) as requests_mock:
            # We mock the endpoint to return response with valid json which doesn't
            # translate to a dict like is expected,
            requests_mock.add(
                requests_mock.POST, "https://example.zulip.com", status=200, json=True
            )
            with expect_logging_info, expect_fail as mock_fail:
                do_rest_call("https://example.zulip.com", mock_event, service_handler)
            self.assertTrue(mock_fail.called)
            bot_owner_notification = self.get_last_message()
            self.assertEqual(
                bot_owner_notification.content,
                """[A message](http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/) to your bot @_**Outgoing Webhook** triggered an outgoing webhook.
The outgoing webhook server attempted to send a message in Zulip, but that request resulted in the following error:
> Invalid response format\nThe response contains the following payload:\n```\n'true'\n```""",
            )
        assert bot_user.bot_owner is not None
        self.assertEqual(bot_owner_notification.recipient_id, bot_user.bot_owner.recipient_id)

    def test_invalid_json_in_response(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_event = self.mock_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        expect_logging_info = self.assertLogs(level="INFO")
        expect_fail = mock.patch("zerver.lib.outgoing_webhook.fail_with_message")

        with responses.RequestsMock(assert_all_requests_are_fired=True) as requests_mock:
            # We mock the endpoint to return response with a body which isn't valid json.
            requests_mock.add(
                requests_mock.POST,
                "https://example.zulip.com",
                status=200,
                body="this isn't valid json",
            )
            with expect_logging_info, expect_fail as mock_fail:
                do_rest_call("https://example.zulip.com", mock_event, service_handler)
            self.assertTrue(mock_fail.called)
            bot_owner_notification = self.get_last_message()
            self.assertEqual(
                bot_owner_notification.content,
                """[A message](http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/) to your bot @_**Outgoing Webhook** triggered an outgoing webhook.
The outgoing webhook server attempted to send a message in Zulip, but that request resulted in the following error:
> Invalid JSON in response\nThe response contains the following payload:\n```\n"this isn't valid json"\n```""",
            )
        assert bot_user.bot_owner is not None
        self.assertEqual(bot_owner_notification.recipient_id, bot_user.bot_owner.recipient_id)


class TestOutgoingWebhookMessaging(ZulipTestCase):
    def create_outgoing_bot(self, bot_owner: UserProfile) -> UserProfile:
        return self.create_test_bot(
            "outgoing-webhook",
            bot_owner,
            full_name="Outgoing Webhook bot",
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            service_name="foo-service",
            payload_url='"https://bot.example.com/"',
        )

    @responses.activate
    def test_multiple_services(self) -> None:
        bot_owner = self.example_user("othello")

        bot = do_create_user(
            bot_owner=bot_owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            full_name="Outgoing Webhook Bot",
            email="whatever",
            realm=bot_owner.realm,
            password=None,
            acting_user=None,
        )

        add_service(
            "weather",
            user_profile=bot,
            interface=Service.GENERIC,
            base_url="https://weather.example.com/",
            token="weather_token",
        )

        add_service(
            "qotd",
            user_profile=bot,
            interface=Service.GENERIC,
            base_url="https://qotd.example.com/",
            token="qotd_token",
        )

        sender = self.example_user("hamlet")

        responses.add(
            responses.POST,
            "https://weather.example.com/",
            json={},
        )
        responses.add(
            responses.POST,
            "https://qotd.example.com/",
            json={},
        )
        with self.assertLogs(level="INFO") as logs:
            self.send_personal_message(
                sender,
                bot,
                content="some content",
            )
        self.assert_length(logs.output, 2)
        self.assertIn(f"Outgoing webhook request from {bot.id}@zulip took ", logs.output[0])
        self.assertIn(f"Outgoing webhook request from {bot.id}@zulip took ", logs.output[1])

        self.assert_length(responses.calls, 2)

        calls_by_url = {
            call.request.url: orjson.loads(call.request.body or b"") for call in responses.calls
        }
        weather_req = calls_by_url["https://weather.example.com/"]
        self.assertEqual(weather_req["token"], "weather_token")
        self.assertEqual(weather_req["message"]["content"], "some content")
        self.assertEqual(weather_req["message"]["sender_id"], sender.id)

        qotd_req = calls_by_url["https://qotd.example.com/"]
        self.assertEqual(qotd_req["token"], "qotd_token")
        self.assertEqual(qotd_req["message"]["content"], "some content")
        self.assertEqual(qotd_req["message"]["sender_id"], sender.id)

    @responses.activate
    def test_pm_to_outgoing_webhook_bot(self) -> None:
        bot_owner = self.example_user("othello")
        bot = self.create_outgoing_bot(bot_owner)
        sender = self.example_user("hamlet")

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json={"response_string": "Hidley ho, I'm a webhook responding!"},
        )
        with self.assertLogs(level="INFO") as logs:
            self.send_personal_message(sender, bot, content="foo")
        self.assert_length(logs.output, 1)
        self.assertIn(f"Outgoing webhook request from {bot.id}@zulip took ", logs.output[0])

        self.assert_length(responses.calls, 1)

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

    @responses.activate
    def test_pm_to_outgoing_webhook_bot_for_407_error_code(self) -> None:
        bot_owner = self.example_user("othello")
        bot = self.create_outgoing_bot(bot_owner)
        sender = self.example_user("hamlet")
        realm = get_realm("zulip")

        responses.add(responses.POST, "https://bot.example.com/", status=407, body="")
        expect_fail = mock.patch("zerver.lib.outgoing_webhook.fail_with_message")
        with expect_fail as mock_fail, self.assertLogs(level="WARNING"):
            message_id = self.send_personal_message(sender, bot, content="foo")

            self.assert_length(responses.calls, 1)

            # create message dict to get the message url
            message = {
                "display_recipient": [{"id": bot.id}, {"id": sender.id}],
                "stream_id": 999,
                TOPIC_NAME: "Foo",
                "id": message_id,
                "type": "",
            }
            message_url = near_message_url(realm, message)

            last_message = self.get_last_message()
            self.assertEqual(
                last_message.content,
                f"[A message]({message_url}) to your bot @_**{bot.full_name}** triggered an outgoing webhook.\n"
                "The URL configured for the webhook is for a private or disallowed network.",
            )
            self.assertEqual(last_message.sender_id, bot.id)
            self.assertEqual(
                last_message.recipient.type_id,
                bot_owner.id,
            )
            self.assertEqual(
                last_message.recipient.type,
                Recipient.PERSONAL,
            )
            self.assertTrue(mock_fail.called)

    @responses.activate
    def test_stream_message_to_outgoing_webhook_bot(self) -> None:
        bot_owner = self.example_user("othello")
        bot = self.create_outgoing_bot(bot_owner)

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json={"response_string": "Hidley ho, I'm a webhook responding!"},
        )

        with self.assertLogs(level="INFO") as logs:
            self.send_stream_message(
                bot_owner, "Denmark", content=f"@**{bot.full_name}** foo", topic_name="bar"
            )

        self.assert_length(responses.calls, 1)

        self.assert_length(logs.output, 1)
        self.assertIn(f"Outgoing webhook request from {bot.id}@zulip took ", logs.output[0])

        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "Hidley ho, I'm a webhook responding!")
        self.assertEqual(last_message.sender_id, bot.id)
        self.assertEqual(last_message.topic_name(), "bar")
        self.assert_message_stream_name(last_message, "Denmark")

    @responses.activate
    def test_stream_message_failure_to_outgoing_webhook_bot(self) -> None:
        realm = get_realm("zulip")
        bot_owner = self.example_user("othello")
        bot = self.create_outgoing_bot(bot_owner)

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            body=requests.exceptions.Timeout("Time is up!"),
        )

        with self.assertLogs(level="INFO") as logs:
            sent_message_id = self.send_stream_message(
                bot_owner, "Denmark", content=f"@**{bot.full_name}** foo", topic_name="bar"
            )

        self.assert_length(responses.calls, 4)
        self.assert_length(logs.output, 5)
        self.assertEqual(
            [
                "INFO:root:Trigger event @**Outgoing Webhook bot** foo on foo-service timed out. Retrying",
                f"INFO:root:Trigger event @**{bot.full_name}** foo on foo-service timed out. Retrying",
                f"INFO:root:Trigger event @**{bot.full_name}** foo on foo-service timed out. Retrying",
                f"INFO:root:Trigger event @**{bot.full_name}** foo on foo-service timed out. Retrying",
                f"WARNING:root:Maximum retries exceeded for trigger:outgoing-webhook-bot@zulip.testserver event:@**{bot.full_name}** foo",
            ],
            logs.output,
        )

        last_message = self.get_last_message()
        message_dict = {
            "stream_id": get_stream("Denmark", realm).id,
            "display_recipient": "Denmark",
            TOPIC_NAME: "bar",
            "id": sent_message_id,
            "type": "stream",
        }
        message_url = near_message_url(realm, message_dict)
        self.assertEqual(
            last_message.content,
            f"[A message]({message_url}) to your bot @_**{bot.full_name}** triggered an outgoing webhook.\n"
            "Request timed out after 10 seconds.",
        )
        self.assertEqual(last_message.sender_id, bot.id)
        assert bot.bot_owner is not None
        self.assertEqual(last_message.recipient_id, bot.bot_owner.recipient_id)

        stream_message = self.get_second_to_last_message()
        self.assertEqual(stream_message.content, "Failure! Bot is unavailable")
        self.assertEqual(stream_message.sender_id, bot.id)
        self.assertEqual(stream_message.topic_name(), "bar")
        self.assert_message_stream_name(stream_message, "Denmark")

    @responses.activate
    def test_stream_message_failure_deactivated_to_outgoing_webhook_bot(self) -> None:
        bot_owner = self.example_user("othello")
        bot = self.create_outgoing_bot(bot_owner)

        def wrapped(event: Dict[str, Any], failure_message: str) -> None:
            do_deactivate_stream(get_stream("Denmark", get_realm("zulip")), acting_user=None)
            fail_with_message(event, failure_message)

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            body=requests.exceptions.Timeout("Time is up!"),
        )
        with mock.patch(
            "zerver.lib.outgoing_webhook.fail_with_message", side_effect=wrapped
        ) as fail:
            with self.assertLogs(level="INFO") as logs:
                self.send_stream_message(
                    bot_owner, "Denmark", content=f"@**{bot.full_name}** foo", topic_name="bar"
                )

        self.assert_length(logs.output, 5)
        fail.assert_called_once()

        last_message = self.get_last_message()
        self.assertIn("Request timed out after 10 seconds", last_message.content)

        prev_message = self.get_second_to_last_message()
        self.assertIn(
            "tried to send a message to channel #**Denmark**, but that channel does not exist",
            prev_message.content,
        )

    @responses.activate
    def test_empty_string_json_as_response_to_outgoing_webhook_request(self) -> None:
        """
        Verifies that if the response to the request triggered by mentioning the bot
        is the json representation of the empty string, the outcome is the same
        as {"response_not_required": True} - since this behavior is kept for
        backwards-compatibility.
        """
        bot_owner = self.example_user("othello")
        bot = self.create_outgoing_bot(bot_owner)

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json="",
        )

        with self.assertLogs(level="INFO") as logs:
            stream_message_id = self.send_stream_message(
                bot_owner, "Denmark", content=f"@**{bot.full_name}** foo", topic_name="bar"
            )

        self.assert_length(responses.calls, 1)

        self.assert_length(logs.output, 1)
        self.assertIn(f"Outgoing webhook request from {bot.id}@zulip took ", logs.output[0])

        # We verify that no new message was sent, since that's the behavior implied
        # by the response_not_required option.
        last_message = self.get_last_message()
        self.assertEqual(last_message.id, stream_message_id)
