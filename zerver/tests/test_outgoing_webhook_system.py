from typing import Any, Dict
from unittest import mock

import orjson
import requests
import responses

from version import ZULIP_VERSION
from zerver.lib.actions import do_create_user, do_deactivate_user
from zerver.lib.outgoing_webhook import (
    GenericOutgoingWebhookService,
    SlackOutgoingWebhookService,
    do_rest_call,
    fail_with_message,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import get_user_messages
from zerver.lib.topic import TOPIC_NAME
from zerver.lib.url_encoding import near_message_url
from zerver.lib.users import add_service
from zerver.models import Recipient, Service, UserProfile, get_display_recipient, get_realm


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
    raise requests.exceptions.ConnectionError()


class DoRestCallTests(ZulipTestCase):
    def mock_stream_message_event(self, bot_user: UserProfile) -> Dict[str, Any]:
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

    def mock_private_message_event(self, bot_user: UserProfile) -> Dict[str, Any]:
        return {
            # Similar to mock_event but triggered by private message with the bot as
            # one of the recipient.
            "failed_tries": 3,
            "message": {
                "display_recipient": [
                    {
                        "id": bot_user.id,
                        "email": "outgoing_webhook_bot@zulipdev.com",
                        "full_name": "outgoing_webhook_bot",
                        "is_mirror_dummy": False,
                    },
                    {
                        "email": "user9@zulipdev.com",
                        "full_name": "Desdemona",
                        "id": 9,
                        "is_mirror_dummy": False,
                    },
                ],
                "sender_id": bot_user.id,
                "sender_email": bot_user.email,
                "sender_realm_id": bot_user.realm.id,
                "sender_realm_str": bot_user.realm.string_id,
                "sender_delivery_email": bot_user.delivery_email,
                "sender_full_name": bot_user.full_name,
                "sender_avatar_source": UserProfile.AVATAR_FROM_GRAVATAR,
                "sender_avatar_version": 1,
                "recipient_type": "private",
                "recipient_type_id": 52,
                "sender_is_mirror_dummy": False,
                "id": "",
                "type": "private",
                "timestamp": 1,
            },
            "trigger": "private_message",
            "user_profile_id": bot_user.id,
            "command": "",
            "service_name": "",
        }

    def test_successful_request(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_stream_message_event = self.mock_stream_message_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        expect_send_response = mock.patch("zerver.lib.outgoing_webhook.send_response_message")
        with mock.patch.object(
            service_handler, "session"
        ) as session, expect_send_response as mock_send:
            session.post.return_value = ResponseMock(200, orjson.dumps(dict(content="whatever")))
            with self.assertLogs(level="INFO") as logs:
                do_rest_call("", mock_stream_message_event, service_handler)
            self.assert_length(logs.output, 1)
            self.assertIn(
                f"Outgoing webhook request from {bot_user.id}@zulip took ", logs.output[0]
            )

        self.assertTrue(mock_send.called)

        for service_class in [GenericOutgoingWebhookService, SlackOutgoingWebhookService]:
            handler = service_class("token", bot_user, "service")
            with mock.patch.object(handler, "session") as session:
                session.post.return_value = ResponseMock(200, b"{}")
                with self.assertLogs(level="INFO") as logs:
                    do_rest_call("", mock_stream_message_event, handler)
                self.assert_length(logs.output, 1)
                self.assertIn(
                    f"Outgoing webhook request from {bot_user.id}@zulip took ", logs.output[0]
                )
                session.post.assert_called_once()

    def test_retry_request(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_stream_message_event = self.mock_stream_message_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        with mock.patch.object(service_handler, "session") as session, self.assertLogs(
            level="WARNING"
        ) as m:
            session.post.return_value = ResponseMock(500)
            final_response = do_rest_call("", mock_stream_message_event, service_handler)
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

    def test_fail_request(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_stream_message_event = self.mock_stream_message_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        expect_fail = mock.patch("zerver.lib.outgoing_webhook.fail_with_message")

        with mock.patch.object(
            service_handler, "session"
        ) as session, expect_fail as mock_fail, self.assertLogs(level="WARNING") as m:
            session.post.return_value = ResponseMock(400)
            final_response = do_rest_call("", mock_stream_message_event, service_handler)
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

    def test_408_error_with_deactivated_owner_for_stream_message(self) -> None:
        # 408 errors occur when we get a timeout whilet rying to hit a url.
        # When we send an outgoing webhook event to a url, it may not be able to
        # process the request and may end up throwing a 408 timeout status code.
        # Between the period of sending the event to the timeout error, the bot owner may be
        # deactivated, which throws error in notify_bot_owner (fail_with_message works normal).
        # Hence test the error handling.
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_stream_message_event = self.mock_stream_message_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        # This deactivates the bot owner and ultimately the bot before
        # calling `fail_with_message`.
        # Note that the scope of the deactivated owner extends to the
        # `notify_bot_owner` as well due to which it raises JsonableError
        # as well.
        def deactivate_bot_owner_first(*args: Any) -> None:
            assert bot_user.bot_owner is not None
            do_deactivate_user(bot_user.bot_owner, acting_user=None)
            fail_with_message(*args)

        expected_fail = mock.patch(
            "zerver.lib.outgoing_webhook.fail_with_message", side_effect=deactivate_bot_owner_first
        )

        with mock.patch.object(
            service_handler, "session"
        ) as session, expected_fail as mock_fail, self.assertLogs(level="WARNING") as m:
            session.post.return_value = ResponseMock(408)
            final_response = do_rest_call("", mock_stream_message_event, service_handler)
            assert final_response is not None

            self.assertEqual(
                m.output,
                [
                    f'WARNING:root:Message http://zulip.testserver/#narrow/stream/999-Verona/topic/Foo/near/ triggered an outgoing webhook, returning status code 408.\n Content of response (in quotes): "{final_response.text}"'
                ],
            )

        self.assertTrue(mock_fail.called)

        failure_message = self.get_last_message()
        self.assertEqual(
            failure_message.content,
            "Failure! Third party responded with 408",
        )

    def test_408_error_with_deactivated_owner_for_private_message(self) -> None:
        # This is similar to the above test but checks the event for
        # private messages. In this case, both fail_with_message and
        # notify_bot_owner throws error.
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_private_message_event = self.mock_private_message_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        def deactivate_bot_owner_first(*args: Any) -> None:
            assert bot_user.bot_owner is not None
            do_deactivate_user(bot_user.bot_owner, acting_user=None)
            fail_with_message(*args)

        expected_fail = mock.patch(
            "zerver.lib.outgoing_webhook.fail_with_message", side_effect=deactivate_bot_owner_first
        )

        with mock.patch.object(
            service_handler, "session"
        ) as session, expected_fail as mock_fail, self.assertLogs(level="WARNING") as m:
            session.post.return_value = ResponseMock(408)
            final_response = do_rest_call("", mock_private_message_event, service_handler)
            assert final_response is not None

            self.assertEqual(
                m.output,
                [
                    f'WARNING:root:Message http://zulip.testserver/#narrow/pm-with/19,9-pm/near/ triggered an outgoing webhook, returning status code 408.\n Content of response (in quotes): "{final_response.text}"'
                ],
            )

        self.assertTrue(mock_fail.called)

        bot_messages = get_user_messages(bot_user)
        self.assert_length(bot_messages, 0)

    def test_headers(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_stream_message_event = self.mock_stream_message_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        session = service_handler.session
        with mock.patch.object(session, "send") as mock_send:
            mock_send.return_value = ResponseMock(200, b"{}")
            with self.assertLogs(level="INFO") as logs:
                final_response = do_rest_call(
                    "https://example.com/", mock_stream_message_event, service_handler
                )
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
        mock_stream_message_event = self.mock_stream_message_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")
        bot_user_email = self.example_user_map["outgoing_webhook_bot"]

        def helper(side_effect: Any, error_text: str) -> None:
            with mock.patch.object(service_handler, "session") as session:
                session.post.side_effect = side_effect
                do_rest_call("", mock_stream_message_event, service_handler)

            bot_owner_notification = self.get_last_message()
            self.assertIn(error_text, bot_owner_notification.content)
            self.assertIn("triggered", bot_owner_notification.content)
            assert bot_user.bot_owner is not None
            self.assertEqual(bot_owner_notification.recipient_id, bot_user.bot_owner.recipient_id)

        with self.assertLogs(level="INFO") as i:
            helper(side_effect=timeout_error, error_text="Request timed out after")
            helper(side_effect=connection_error, error_text="A connection error occurred.")

            log_output = [
                f"INFO:root:Trigger event {mock_stream_message_event['command']} on {mock_stream_message_event['service_name']} timed out. Retrying",
                f"WARNING:root:Maximum retries exceeded for trigger:{bot_user_email} event:{mock_stream_message_event['command']}",
                f"INFO:root:Trigger event {mock_stream_message_event['command']} on {mock_stream_message_event['service_name']} resulted in a connection error. Retrying",
                f"WARNING:root:Maximum retries exceeded for trigger:{bot_user_email} event:{mock_stream_message_event['command']}",
            ]

            self.assertEqual(i.output, log_output)

    def test_request_exception(self) -> None:
        bot_user = self.example_user("outgoing_webhook_bot")
        mock_stream_message_event = self.mock_stream_message_event(bot_user)
        service_handler = GenericOutgoingWebhookService("token", bot_user, "service")

        expect_logging_exception = self.assertLogs(level="ERROR")
        expect_fail = mock.patch("zerver.lib.outgoing_webhook.fail_with_message")

        # Don't think that we should catch and assert whole log output(which is actually a very big error traceback).
        # We are already asserting bot_owner_notification.content which verifies exception did occur.
        with mock.patch.object(
            service_handler, "session"
        ) as session, expect_logging_exception, expect_fail as mock_fail:
            session.post.side_effect = request_exception_error
            do_rest_call("", mock_stream_message_event, service_handler)

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
        mock_stream_message_event = self.mock_stream_message_event(bot_user)
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
                do_rest_call(
                    "https://example.zulip.com", mock_stream_message_event, service_handler
                )
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
        mock_stream_message_event = self.mock_stream_message_event(bot_user)
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
                do_rest_call(
                    "https://example.zulip.com", mock_stream_message_event, service_handler
                )
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
        mock_stream_message_event = self.mock_stream_message_event(bot_user)
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
                do_rest_call(
                    "https://example.zulip.com", mock_stream_message_event, service_handler
                )
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
        display_recipient = get_display_recipient(last_message.recipient)
        self.assertEqual(display_recipient, "Denmark")

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
