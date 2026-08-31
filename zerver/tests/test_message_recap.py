from datetime import datetime, timezone
from unittest import mock

import time_machine
from django.conf import settings
from openai.resources.chat.completions import Completions
from openai.types.chat import ChatCompletion
from typing_extensions import override

from analytics.models import UserCount
from zerver.actions.message_flags import do_mark_all_as_read
from zerver.actions.realm_settings import do_change_realm_permission_group_setting
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import NamedUserGroup
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm


class MessagesRecapTestCase(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("iago")
        self.channel_name = "Zulip features"
        self.topic_name = "New feature launch"

        self.login_user(self.user)
        self.subscribe(self.user, self.channel_name)

        # Send unread messages in stream
        self.other_user = self.example_user("hamlet")
        self.subscribe(self.other_user, self.channel_name)
        self.send_stream_message(
            self.other_user,
            self.channel_name,
            content="Hey team, here is the new recap feature design.",
            topic_name=self.topic_name,
        )
        self.send_stream_message(
            self.other_user,
            self.channel_name,
            content="Please check it out and leave comments.",
            topic_name=self.topic_name,
        )

        not_last_day_of_any_month = datetime(2025, 2, 18, 1, tzinfo=timezone.utc)
        self.mocked_time_patcher = time_machine.travel(not_last_day_of_any_month, tick=False)
        self.mocked_time_patcher.start()

    @override
    def tearDown(self) -> None:
        self.mocked_time_patcher.stop()
        super().tearDown()

    def test_recap_when_no_unreads(self) -> None:
        # Mark all messages as read first
        do_mark_all_as_read(self.user)

        response = self.client_get("/json/messages/recap")
        self.assertEqual(response.status_code, 200)
        data = self.assert_json_success(response)
        self.assertIn("no unread messages", data["recap"].lower())
        self.assertFalse(data["has_unreads"])

    def test_recap_ai_disabled(self) -> None:
        with self.settings(TOPIC_SUMMARIZATION_MODEL=None):
            response = self.client_get("/json/messages/recap")
            self.assert_json_error(response, "AI features are not enabled on this server.")

    def test_recap_permission_denied(self) -> None:
        realm = get_realm("zulip")
        nobody_group = NamedUserGroup.objects.get(
            name=SystemGroups.NOBODY, realm_for_sharding=realm, is_system_group=True
        )
        do_change_realm_permission_group_setting(
            realm,
            "can_summarize_topics_group",
            nobody_group,
            acting_user=None,
        )

        response = self.client_get("/json/messages/recap")
        self.assert_json_error(response, "Insufficient permission")

    def test_recap_success(self) -> None:
        fake_response_dict = {
            "id": "chatcmpl-test-recap",
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {
                        "content": (
                            "### #Zulip features > New feature launch\n"
                            "- Hamlet shared the recap feature design ([link](#narrow/channel/1-Zulip-features/topic/New.20feature.20launch/near/1000)).\n"
                            "- Hamlet requested feedback and comments from the team."
                        ),
                        "role": "assistant",
                    },
                }
            ],
            "created": 1740000000,
            "model": "llama-3.3-70b-versatile",
            "object": "chat.completion",
            "usage": {
                "completion_tokens": 40,
                "prompt_tokens": 120,
                "total_tokens": 160,
            },
        }
        fake_response = ChatCompletion.model_validate(fake_response_dict)

        with (
            self.settings(
                TOPIC_SUMMARIZATION_MODEL="llama-3.3-70b-versatile",
                TOPIC_SUMMARIZATION_API_KEY="test-api-key",
            ),
            mock.patch.object(Completions, "create", return_value=fake_response),
        ):
            response = self.client_get("/json/messages/recap")
            self.assertEqual(response.status_code, 200)
            data = self.assert_json_success(response)
            self.assertTrue(data["has_unreads"])
            self.assertIn("Hamlet", data["recap"])
            self.assertIn("href=\"#narrow/channel/", data["recap"])

    def test_recap_credit_limit_exceeded(self) -> None:
        with self.settings(
            TOPIC_SUMMARIZATION_MODEL="llama-3.3-70b-versatile",
            MAX_PER_USER_MONTHLY_AI_COST=0,
        ):
            response = self.client_get("/json/messages/recap")
            self.assert_json_error(response, "Reached monthly limit for AI credits.")
