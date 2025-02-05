import os
import warnings
from unittest import mock

import orjson
from django.conf import settings
from typing_extensions import override

from analytics.models import UserCount
from zerver.lib.test_classes import ZulipTestCase

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pydantic")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="litellm")
# Avoid network query to fetch the model cost map.
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
import litellm

# Fixture file to store recorded responses
LLM_FIXTURES_FILE = "zerver/tests/fixtures/litellm/summary.json"


class MessagesSummaryTestCase(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("iago")
        self.topic_name = "New feature launch"
        self.channel_name = "Zulip features"

        self.login_user(self.user)
        self.subscribe(self.user, self.channel_name)
        content = "Zulip just launched a feature to generate summary of messages."
        self.send_stream_message(
            self.user, self.channel_name, content=content, topic_name=self.topic_name
        )

        content = "Sounds awesome! This will greatly help me when catching up."
        self.send_stream_message(
            self.user, self.channel_name, content=content, topic_name=self.topic_name
        )

        if settings.GENERATE_LITELLM_FIXTURES:  # nocoverage
            self.patcher = mock.patch("litellm.completion", wraps=litellm.completion)
            self.mocked_completion = self.patcher.start()

    @override
    def tearDown(self) -> None:
        if settings.GENERATE_LITELLM_FIXTURES:  # nocoverage
            self.patcher.stop()
        super().tearDown()

    def test_summarize_messages_in_topic(self) -> None:
        narrow = orjson.dumps([["channel", self.channel_name], ["topic", self.topic_name]]).decode()

        if settings.GENERATE_LITELLM_FIXTURES:  # nocoverage
            # NOTE: You need have proper credentials in zproject/dev-secrets.conf
            # to generate the fixtures. (Tested using aws bedrock.)
            # Trigger the API call to extract the arguments.
            self.client_get("/json/messages/summary", dict(narrow=narrow))
            call_args = self.mocked_completion.call_args

            # Once we have the arguments, call the original method and save its response.
            response = self.mocked_completion(**call_args.kwargs).json()
            with open(LLM_FIXTURES_FILE, "wb") as f:
                fixture_data = {
                    # Only store model and messages.
                    # We don't want to store any secrets.
                    "model": call_args.kwargs["model"],
                    "messages": call_args.kwargs["messages"],
                    "response": response,
                }
                f.write(orjson.dumps(fixture_data, option=orjson.OPT_INDENT_2) + b"\n")
            return

        # In this code path, we test using the fixtures.
        with open(LLM_FIXTURES_FILE, "rb") as f:
            fixture_data = orjson.loads(f.read())

        # Block summary requests if budget set to 0.
        with self.settings(
            TOPIC_SUMMARIZATION_MODEL="groq/llama-3.3-70b-versatile",
            MAX_PER_USER_MONTHLY_AI_COST=0,
        ):
            response = self.client_get("/json/messages/summary")
            self.assert_json_error_contains(response, "Reached monthly limit for AI credits.")

        # Fake credentials to ensure we crash if actual network
        # requests occur, which would reflect a problem with how the
        # fixtures were set up.
        with self.settings(
            TOPIC_SUMMARIZATION_MODEL="groq/llama-3.3-70b-versatile",
            TOPIC_SUMMARIZATION_API_KEY="test",
        ):
            input_tokens = fixture_data["response"]["usage"]["prompt_tokens"]
            output_tokens = fixture_data["response"]["usage"]["completion_tokens"]
            credits_used = (output_tokens * settings.OUTPUT_COST_PER_GIGATOKEN) + (
                input_tokens * settings.INPUT_COST_PER_GIGATOKEN
            )
            self.assertFalse(
                UserCount.objects.filter(
                    property="ai_credit_usage::day", value=credits_used, user_id=self.user.id
                ).exists()
            )
            with mock.patch("litellm.completion", return_value=fixture_data["response"]):
                payload = self.client_get("/json/messages/summary", dict(narrow=narrow))
                self.assertEqual(payload.status_code, 200)
            # Check that we recorded this usage.
            self.assertTrue(
                UserCount.objects.filter(
                    property="ai_credit_usage::day", value=credits_used, user_id=self.user.id
                ).exists()
            )

        # If we reached the credit usage limit, block summary requests.
        with self.settings(
            TOPIC_SUMMARIZATION_MODEL="groq/llama-3.3-70b-versatile",
            MAX_PER_USER_MONTHLY_AI_COST=credits_used / 1000000000,
        ):
            response = self.client_get("/json/messages/summary")
            self.assert_json_error_contains(response, "Reached monthly limit for AI credits.")
