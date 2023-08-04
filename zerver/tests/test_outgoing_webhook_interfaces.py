import json
from typing import Any, Dict
from unittest import mock

import requests

from zerver.lib.avatar import get_gravatar_url
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import MessageDict
from zerver.lib.outgoing_webhook import get_service_interface_class, process_success_response
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import TOPIC_NAME
from zerver.models import (
    SLACK_INTERFACE,
    Message,
    NotificationTriggers,
    get_realm,
    get_stream,
    get_user,
)
from zerver.openapi.openapi import validate_against_openapi_schema


class TestGenericOutgoingWebhookService(ZulipTestCase):
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

        gravatar_url = get_gravatar_url(
            othello.delivery_email,
            othello.avatar_version,
        )

        expected_message_data = {
            "avatar_url": gravatar_url,
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
        response: Dict[str, Any] = dict(response_not_required=True)
        success_response = self.handler.process_success(response)
        self.assertEqual(success_response, None)

        response = dict(response_string="test_content")
        success_response = self.handler.process_success(response)
        self.assertEqual(success_response, dict(content="test_content"))

        response = dict(
            content="test_content",
            widget_content="test_widget_content",
            red_herring="whatever",
        )
        success_response = self.handler.process_success(response)
        expected_response = dict(
            content="test_content",
            widget_content="test_widget_content",
        )
        self.assertEqual(success_response, expected_response)

        response = {}
        success_response = self.handler.process_success(response)
        self.assertEqual(success_response, None)


class TestSlackOutgoingWebhookService(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.bot_user = get_user("outgoing-webhook@zulip.com", get_realm("zulip"))
        self.stream_message_event = {
            "command": "@**test**",
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

    def test_make_request_stream_message(self) -> None:
        test_url = "https://example.com/example"
        with mock.patch.object(self.handler, "session") as session:
            self.handler.make_request(
                test_url,
                self.stream_message_event,
                self.bot_user.realm,
            )
            session.post.assert_called_once()
            self.assertEqual(session.post.call_args[0], (test_url,))
            request_data = session.post.call_args[1]["data"]

        self.assertEqual(request_data[0][1], "abcdef")  # token
        self.assertEqual(request_data[1][1], "T2")  # team_id
        self.assertEqual(request_data[2][1], "zulip.testserver")  # team_domain
        self.assertEqual(request_data[3][1], "C123")  # channel_id
        self.assertEqual(request_data[4][1], "integrations")  # channel_name
        self.assertEqual(request_data[5][1], 123456)  # thread_id
        self.assertEqual(request_data[6][1], 123456)  # timestamp
        self.assertEqual(request_data[7][1], "U21")  # user_id
        self.assertEqual(request_data[8][1], "Sample User")  # user_name
        self.assertEqual(request_data[9][1], "@**test**")  # text
        self.assertEqual(request_data[10][1], "mention")  # trigger_word
        self.assertEqual(request_data[11][1], 12)  # user_profile_id

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
        response: Dict[str, Any] = dict(response_not_required=True)
        success_response = self.handler.process_success(response)
        self.assertEqual(success_response, None)

        response = dict(text="test_content")
        success_response = self.handler.process_success(response)
        self.assertEqual(success_response, dict(content="test_content"))
