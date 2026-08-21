import json
from typing import Any
from unittest import mock

import requests
from typing_extensions import override

from zerver.lib.avatar import avatar_url
from zerver.lib.exceptions import JsonableError
from zerver.lib.message_cache import MessageDict
from zerver.lib.outgoing_webhook import (
    OutgoingWebhookResult,
    get_service_interface_class,
    process_success_response,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import TOPIC_NAME
from zerver.models import Message
from zerver.models.bots import SLACK_INTERFACE
from zerver.models.realms import get_realm
from zerver.models.scheduled_jobs import NotificationTriggers
from zerver.models.streams import get_stream
from zerver.models.users import get_user
from zerver.openapi.openapi import validate_against_openapi_schema


class TestGenericOutgoingWebhookService(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()

        self.bot_user = get_user("outgoing-webhook@zulip.com", get_realm("zulip"))
        service_class = get_service_interface_class("whatever")  # GenericOutgoingWebhookService
        self.handler = service_class(
            service_name="test-service", token="abcdef", user_profile=self.bot_user
        )

    def test_process_success_response(self) -> None:
        event = dict(
            user_profile_id=99,
            message=dict(type="private"),
        )
        service_handler = self.handler

        response = mock.Mock(spec=requests.Response)
        response.status_code = 200
        response.text = json.dumps(dict(content="whatever"))

        with mock.patch("zerver.lib.outgoing_webhook.send_response_message") as m:
            process_success_response(
                event=event,
                service_handler=service_handler,
                response=response,
            )
        self.assertTrue(m.called)

        response = mock.Mock(spec=requests.Response)
        response.status_code = 200
        response.text = "unparsable text"

        with self.assertRaisesRegex(JsonableError, "Invalid JSON in response"):
            process_success_response(
                event=event,
                service_handler=service_handler,
                response=response,
            )

    def test_make_request(self) -> None:
        othello = self.example_user("othello")
        stream = get_stream("Denmark", othello.realm)
        message_id = self.send_stream_message(
            othello,
            stream.name,
            content="@**test**",
        )

        message = Message.objects.get(id=message_id)

        expected_message_data: dict[str, Any] = {
            "avatar_url": avatar_url(othello),
            "client": "test suite",
            "content": "@**test**",
            "content_type": "text/x-markdown",
            "display_recipient": "Denmark",
            "id": message.id,
            "is_me_message": False,
            "reactions": [],
            "recipient_id": message.recipient_id,
            "rendered_content": "<p>@<strong>test</strong></p>",
            "sender_email": othello.email,
            "sender_full_name": "Othello, the Moor of Venice",
            "sender_id": othello.id,
            "sender_realm_str": "zulip",
            "stream_id": stream.id,
            TOPIC_NAME: "test",
            "submessages": [],
            "timestamp": datetime_to_timestamp(message.date_sent),
            "topic_links": [],
            "type": "stream",
        }

        wide_message_dict = MessageDict.wide_dict(message)

        event = {
            "command": "@**test**",
            "message": wide_message_dict,
            "trigger": "mention",
        }

        test_url = "https://example.com/example"
        with mock.patch.object(self.handler, "session") as session:
            self.handler.make_request(
                test_url,
                event,
                othello.realm,
            )
            session.post.assert_called_once()
            self.assertEqual(session.post.call_args[0], (test_url,))
            request_data = session.post.call_args[1]["json"]

        validate_against_openapi_schema(request_data, "/zulip-outgoing-webhook", "post", "200")
        self.assertEqual(request_data["bot_full_name"], self.bot_user.full_name)
        self.assertEqual(request_data["data"], "@**test**")
        self.assertEqual(request_data["token"], "abcdef")
        self.assertEqual(request_data["message"], expected_message_data)

        # Make sure we didn't accidentally mutate wide_message_dict.
        self.assertEqual(wide_message_dict["sender_realm_id"], othello.realm_id)

    def test_process_success(self) -> None:
        response: dict[str, Any] = dict(response_not_required=True)
        success_response = self.handler.process_success(response)
        self.assertEqual(success_response, None)

        response = dict(response_string="test_content")
        success_response = self.handler.process_success(response)
        self.assertEqual(success_response, OutgoingWebhookResult(content="test_content"))

        response = dict(
            content="test_content",
            widget_content={"widget_type": "zform", "extra_data": {}},
            red_herring="whatever",
        )
        success_response = self.handler.process_success(response)
        self.assertEqual(
            success_response,
            OutgoingWebhookResult(
                content="test_content", widget_content='{"widget_type": "zform", "extra_data": {}}'
            ),
        )

        response = {}
        success_response = self.handler.process_success(response)
        self.assertEqual(success_response, None)


class TestSlackOutgoingWebhookService(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.bot_user = get_user("outgoing-webhook@zulip.com", get_realm("zulip"))
        bot_name = self.bot_user.full_name  # "Outgoing Webhook"

        self.stream_message_event = {
            "command": f"@**{bot_name}** do something",
            "user_profile_id": 12,
            "service_name": "test-service",
            "trigger": "mention",
            "message": {
                "content": "test_content",
                "type": "stream",
                "sender_realm_str": "zulip",
                "sender_email": "sampleuser@zulip.com",
                "stream_id": "123",
                "display_recipient": "integrations",
                "timestamp": 123456,
                "sender_id": 21,
                "sender_full_name": "Sample User",
            },
        }

        self.private_message_event = {
            "user_profile_id": 24,
            "service_name": "test-service",
            "command": "test content",
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
            "message": {
                "sender_id": 3,
                "sender_realm_str": "zulip",
                "timestamp": 1529821610,
                "sender_email": "cordelia@zulip.com",
                "type": "private",
                "sender_realm_id": 1,
                "id": 219,
                TOPIC_NAME: "test",
                "content": "test content",
            },
        }

        service_class = get_service_interface_class(SLACK_INTERFACE)
        self.handler = service_class(
            token="abcdef", user_profile=self.bot_user, service_name="test-service"
        )

    def _get_request_data(self, event: dict[str, Any]) -> list[tuple[str, Any]]:
        """Helper to call make_request and return the posted data."""
        test_url = "https://example.com/example"
        with mock.patch.object(self.handler, "session") as session:
            self.handler.make_request(test_url, event, self.bot_user.realm)
            session.post.assert_called_once()
            self.assertEqual(session.post.call_args[0], (test_url,))
            return session.post.call_args[1]["data"]

    def test_make_request_stream_message(self) -> None:
        request_data = self._get_request_data(self.stream_message_event)

        request_dict = dict(request_data)
        self.assertEqual(request_dict["token"], "abcdef")
        self.assertEqual(request_dict["team_id"], "T2")
        self.assertEqual(request_dict["team_domain"], "zulip.testserver")
        self.assertEqual(request_dict["channel_id"], "C123")
        self.assertEqual(request_dict["channel_name"], "integrations")
        self.assertEqual(request_dict["thread_ts"], 123456)
        self.assertEqual(request_dict["timestamp"], 123456)
        self.assertEqual(request_dict["user_id"], "U21")
        self.assertEqual(request_dict["user_name"], "Sample User")
        # The leading bot mention is split into command and stripped from text.
        self.assertEqual(request_dict["text"], "do something")
        self.assertEqual(request_dict["command"], f"/{self.bot_user.full_name}")
        self.assertEqual(request_dict["trigger_word"], "mention")
        self.assertEqual(request_dict["service_id"], 12)

    def test_make_request_stream_message_silent_mention(self) -> None:
        """A silent mention (@_**Bot Name**) at the start is split the same way."""
        event = {
            **self.stream_message_event,
            "command": f"@_**{self.bot_user.full_name}** deploy prod",
        }
        request_data = self._get_request_data(event)
        request_dict = dict(request_data)
        self.assertEqual(request_dict["command"], f"/{self.bot_user.full_name}")
        self.assertEqual(request_dict["text"], "deploy prod")

    def test_make_request_stream_message_id_mention(self) -> None:
        """A mention with |user_id disambiguation is handled correctly."""
        event = {
            **self.stream_message_event,
            "command": f"@**{self.bot_user.full_name}|{self.bot_user.id}** status",
        }
        request_data = self._get_request_data(event)
        request_dict = dict(request_data)
        self.assertEqual(request_dict["command"], f"/{self.bot_user.full_name}")
        self.assertEqual(request_dict["text"], "status")

    def test_make_request_stream_message_non_numeric_id_mention(self) -> None:
        full_content = f"@**{self.bot_user.full_name}|not-a-user-id** status"
        event = {
            **self.stream_message_event,
            "command": full_content,
        }
        request_data = self._get_request_data(event)
        request_dict = dict(request_data)
        self.assertEqual(request_dict["text"], full_content)
        self.assertNotIn("command", request_dict)

    def test_make_request_stream_message_wrong_id_mention(self) -> None:
        full_content = f"@**{self.bot_user.full_name}|{self.bot_user.id + 1}** status"
        event = {
            **self.stream_message_event,
            "command": full_content,
        }
        request_data = self._get_request_data(event)
        request_dict = dict(request_data)
        self.assertEqual(request_dict["text"], full_content)
        self.assertNotIn("command", request_dict)

    def test_make_request_stream_message_wrong_name_with_id_mention(self) -> None:
        full_content = f"@**Not The Bot|{self.bot_user.id}** status"
        event = {
            **self.stream_message_event,
            "command": full_content,
        }
        request_data = self._get_request_data(event)
        request_dict = dict(request_data)
        self.assertEqual(request_dict["text"], full_content)
        self.assertNotIn("command", request_dict)

    def test_make_request_stream_message_mention_mid_message(self) -> None:
        """A bot mention that is NOT at the start → no command, text is full content."""
        full_content = f"Hey @**{self.bot_user.full_name}** help me"
        event = {
            **self.stream_message_event,
            "command": full_content,
        }
        request_data = self._get_request_data(event)
        request_dict = dict(request_data)
        self.assertEqual(request_dict["text"], full_content)
        self.assertNotIn("command", request_dict)

    def test_make_request_stream_message_different_user_mention(self) -> None:
        """A mention of a *different* user at the start → no split."""
        full_content = "@**Hamlet** do something"
        event = {
            **self.stream_message_event,
            "command": full_content,
        }
        request_data = self._get_request_data(event)
        request_dict = dict(request_data)
        self.assertEqual(request_dict["text"], full_content)
        self.assertNotIn("command", request_dict)

    def test_make_request_no_mention_trigger(self) -> None:
        """When trigger is not 'mention', no split is attempted."""
        full_content = f"@**{self.bot_user.full_name}** hello"
        event = {
            **self.stream_message_event,
            "command": full_content,
            "trigger": "stream",
        }
        request_data = self._get_request_data(event)
        request_dict = dict(request_data)
        self.assertEqual(request_dict["text"], full_content)
        self.assertNotIn("command", request_dict)

    def test_make_request_stream_message_leading_whitespace(self) -> None:
        """Leading whitespace before the mention doesn't prevent the split."""
        event = {
            **self.stream_message_event,
            "command": f"  \n @**{self.bot_user.full_name}** deploy",
        }
        request_data = self._get_request_data(event)
        request_dict = dict(request_data)
        self.assertEqual(request_dict["command"], f"/{self.bot_user.full_name}")
        self.assertEqual(request_dict["text"], "deploy")

    def test_make_request_stream_message_multiple_mentions(self) -> None:
        """Only the first mention becomes 'command'; the rest stays in 'text'."""
        event = {
            **self.stream_message_event,
            "command": f"@**{self.bot_user.full_name}** @**Hamlet** do thing",
        }
        request_data = self._get_request_data(event)
        request_dict = dict(request_data)
        self.assertEqual(request_dict["command"], f"/{self.bot_user.full_name}")
        self.assertEqual(request_dict["text"], "@**Hamlet** do thing")

    @mock.patch("zerver.lib.outgoing_webhook.fail_with_message")
    def test_make_request_private_message(self, mock_fail_with_message: mock.Mock) -> None:
        test_url = "https://example.com/example"
        with mock.patch.object(self.handler, "session") as session:
            response = self.handler.make_request(
                test_url,
                self.private_message_event,
                self.bot_user.realm,
            )
            session.post.assert_not_called()
        self.assertIsNone(response)
        self.assertTrue(mock_fail_with_message.called)

    def test_process_success(self) -> None:
        response: dict[str, Any] = dict(response_not_required=True)
        success_response = self.handler.process_success(response)
        self.assertEqual(success_response, None)

        response = dict(text="test_content")
        success_response = self.handler.process_success(response)
        self.assertEqual(success_response, OutgoingWebhookResult(content="test_content"))
