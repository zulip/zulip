from datetime import datetime, timezone
from unittest import mock

import time_machine
from openai.resources.chat.completions import Completions
from openai.types.chat import ChatCompletion
from typing_extensions import override

from zerver.actions.realm_settings import do_change_realm_permission_group_setting
from zerver.actions.topic_drift import clean_json_response
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import NamedUserGroup
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm


class TopicDriftTestCase(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("iago")
        self.channel_name = "Verona"
        self.topic_name = "Original Server Deployment"

        self.login_user(self.user)
        self.subscribe(self.user, self.channel_name)
        self.stream_id = self.get_stream_id(self.channel_name)

        not_last_day_of_any_month = datetime(2025, 2, 18, 1, tzinfo=timezone.utc)
        self.mocked_time_patcher = time_machine.travel(not_last_day_of_any_month, tick=False)
        self.mocked_time_patcher.start()

    @override
    def tearDown(self) -> None:
        self.mocked_time_patcher.stop()
        super().tearDown()

    def test_clean_json_response(self) -> None:
        self.assertEqual(clean_json_response('{"has_drift": true}'), '{"has_drift": true}')
        self.assertEqual(
            clean_json_response('```json\n{"has_drift": false}\n```'), '{"has_drift": false}'
        )
        self.assertEqual(clean_json_response("No json here"), "No json here")

    def test_check_drift_ai_disabled(self) -> None:
        with self.settings(TOPIC_SUMMARIZATION_MODEL=None):
            response = self.client_post(
                "/json/topics/check_drift",
                {"stream_id": self.stream_id, "topic_name": self.topic_name},
            )
            self.assert_json_error(response, "AI features are not enabled on this server.")

    def test_check_drift_permission_denied(self) -> None:
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

        response = self.client_post(
            "/json/topics/check_drift",
            {"stream_id": self.stream_id, "topic_name": self.topic_name},
        )
        self.assert_json_error(response, "Insufficient permission")

    def test_check_drift_short_topic_skips_llm(self) -> None:
        # 0 messages in topic -> should return has_drift=False without querying LLM
        response = self.client_post(
            "/json/topics/check_drift",
            {"stream_id": self.stream_id, "topic_name": "Empty Topic"},
        )
        self.assertEqual(response.status_code, 200)
        data = self.assert_json_success(response)
        self.assertFalse(data["has_drift"])
        self.assertIsNone(data["suggested_title"])

        # 1 message in topic -> should return has_drift=False without querying LLM
        self.send_stream_message(
            self.user,
            self.channel_name,
            content="Initial deployment started.",
            topic_name=self.topic_name,
        )

        response = self.client_post(
            "/json/topics/check_drift",
            {"stream_id": self.stream_id, "topic_name": self.topic_name},
        )
        self.assertEqual(response.status_code, 200)
        data = self.assert_json_success(response)
        self.assertFalse(data["has_drift"])
        self.assertIsNone(data["suggested_title"])

    def test_check_drift_detected_and_caching(self) -> None:
        # Send off-topic messages
        self.send_stream_message(
            self.user,
            self.channel_name,
            content="Initial deployment started.",
            topic_name=self.topic_name,
        )
        # Also test notification-bot message filtering
        notification_bot = self.notification_bot(self.user.realm)
        self.subscribe(notification_bot, self.channel_name)
        self.send_stream_message(
            notification_bot,
            self.channel_name,
            content="Topic resolved.",
            topic_name=self.topic_name,
        )
        self.send_stream_message(
            self.user,
            self.channel_name,
            content="Hey, let's redesign our database indexes for user analytics instead.",
            topic_name=self.topic_name,
        )

        fake_response_dict = {
            "id": "chatcmpl-test-drift",
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {
                        "content": (
                            '{"has_drift": true, '
                            '"suggested_title": "Database Indexing for Analytics"}'
                        ),
                        "role": "assistant",
                    },
                }
            ],
            "created": 1740000000,
            "model": "llama-3.3-70b-versatile",
            "object": "chat.completion",
            "usage": {
                "completion_tokens": 20,
                "prompt_tokens": 100,
                "total_tokens": 120,
            },
        }
        fake_response = ChatCompletion.model_validate(fake_response_dict)

        with (
            self.settings(
                TOPIC_SUMMARIZATION_MODEL="llama-3.3-70b-versatile",
                TOPIC_SUMMARIZATION_API_KEY="test-api-key",
            ),
            mock.patch.object(Completions, "create", return_value=fake_response) as mock_create,
        ):
            # First call -> queries LLM
            response = self.client_post(
                "/json/topics/check_drift",
                {"stream_id": self.stream_id, "topic_name": self.topic_name},
            )
            self.assertEqual(response.status_code, 200)
            data = self.assert_json_success(response)
            self.assertTrue(data["has_drift"])
            self.assertEqual(data["suggested_title"], "Database Indexing for Analytics")
            self.assertEqual(mock_create.call_count, 1)

            # Second call immediately -> hits cache
            response_cached = self.client_post(
                "/json/topics/check_drift",
                {"stream_id": self.stream_id, "topic_name": self.topic_name},
            )
            self.assertEqual(response_cached.status_code, 200)
            data_cached = self.assert_json_success(response_cached)
            self.assertTrue(data_cached["has_drift"])
            self.assertEqual(mock_create.call_count, 1)

    def test_check_drift_suggested_same_as_current_title(self) -> None:
        self.send_stream_message(
            self.user,
            self.channel_name,
            content="Message 1",
            topic_name="Server Maintenance",
        )
        self.send_stream_message(
            self.user,
            self.channel_name,
            content="Message 2",
            topic_name="Server Maintenance",
        )

        fake_response_dict = {
            "id": "chatcmpl-test-same",
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {
                        "content": '{"has_drift": true, "suggested_title": "Server Maintenance"}',
                        "role": "assistant",
                    },
                }
            ],
            "created": 1740000000,
            "model": "llama-3.3-70b-versatile",
            "object": "chat.completion",
            "usage": {
                "completion_tokens": 10,
                "prompt_tokens": 50,
                "total_tokens": 60,
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
            response = self.client_post(
                "/json/topics/check_drift",
                {"stream_id": self.stream_id, "topic_name": "Server Maintenance"},
            )
            self.assertEqual(response.status_code, 200)
            data = self.assert_json_success(response)
            self.assertFalse(data["has_drift"])
            self.assertIsNone(data["suggested_title"])

    def test_check_drift_json_parse_error(self) -> None:
        self.send_stream_message(
            self.user,
            self.channel_name,
            content="Message 1",
            topic_name="Deployment",
        )
        self.send_stream_message(
            self.user,
            self.channel_name,
            content="Message 2",
            topic_name="Deployment",
        )

        fake_response_dict = {
            "id": "chatcmpl-test-err",
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {
                        "content": "This is completely malformed text not json",
                        "role": "assistant",
                    },
                }
            ],
            "created": 1740000000,
            "model": "llama-3.3-70b-versatile",
            "object": "chat.completion",
            "usage": {
                "completion_tokens": 10,
                "prompt_tokens": 50,
                "total_tokens": 60,
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
            response = self.client_post(
                "/json/topics/check_drift",
                {"stream_id": self.stream_id, "topic_name": "Deployment"},
            )
            self.assertEqual(response.status_code, 200)
            data = self.assert_json_success(response)
            self.assertFalse(data["has_drift"])
            self.assertIsNone(data["suggested_title"])

    def test_check_drift_not_detected(self) -> None:
        self.send_stream_message(
            self.user,
            self.channel_name,
            content="Initial deployment started.",
            topic_name=self.topic_name,
        )
        self.send_stream_message(
            self.user,
            self.channel_name,
            content="Deploying pods to production Kubernetes cluster.",
            topic_name=self.topic_name,
        )

        fake_response_dict = {
            "id": "chatcmpl-test-no-drift",
            "choices": [
                {
                    "finish_reason": "stop",
                    "index": 0,
                    "message": {
                        "content": (
                            '{"has_drift": false, '
                            '"reason": "The conversation remains focused on server deployment.", '
                            '"suggested_title": ""}'
                        ),
                        "role": "assistant",
                    },
                }
            ],
            "created": 1740000000,
            "model": "llama-3.3-70b-versatile",
            "object": "chat.completion",
            "usage": {
                "completion_tokens": 20,
                "prompt_tokens": 90,
                "total_tokens": 110,
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
            response = self.client_post(
                "/json/topics/check_drift",
                {"stream_id": self.stream_id, "topic_name": self.topic_name},
            )
            self.assertEqual(response.status_code, 200)
            data = self.assert_json_success(response)
            self.assertFalse(data["has_drift"])
            self.assertIsNone(data["suggested_title"])

    def test_check_drift_credit_limit_exceeded(self) -> None:
        with self.settings(
            TOPIC_SUMMARIZATION_MODEL="llama-3.3-70b-versatile",
            MAX_PER_USER_MONTHLY_AI_COST=0,
        ):
            response = self.client_post(
                "/json/topics/check_drift",
                {"stream_id": self.stream_id, "topic_name": self.topic_name},
            )
            self.assert_json_error(response, "Reached monthly limit for AI credits.")
