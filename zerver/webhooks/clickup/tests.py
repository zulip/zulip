import json
from collections.abc import Callable
from functools import wraps
from typing import Concatenate

import orjson
import requests
import responses
from typing_extensions import ParamSpec

from zerver.lib.bot_config import set_bot_config
from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.clickup.view import IGNORED_EVENTS, get_clickup_api_data

ParamT = ParamSpec("ParamT")

TEAM_ID = "90161438581"
TASK_ID = "86d3cc9fu"
TASK_API_URL = f"https://api.clickup.com/api/v2/task/{TASK_ID}"
TASK_URL = f"https://app.clickup.com/t/{TEAM_ID}/{TASK_ID}"
TASK_NAME = "Zulip Test Task"
AUTHOR = "Sathwik Suresh Shetty"


def mock_clickup_api_calls(
    test_func: Callable[Concatenate["ClickUpHookTests", ParamT], None],
) -> Callable[Concatenate["ClickUpHookTests", ParamT], None]:
    @wraps(test_func)
    @responses.activate
    def _wrapped(self: "ClickUpHookTests", /, *args: ParamT.args, **kwargs: ParamT.kwargs) -> None:
        set_bot_config(self.test_user, "clickup_token", "token")
        responses.add(
            responses.GET,
            TASK_API_URL,
            self.webhook_fixture_data("clickup", "task_api_data"),
        )
        test_func(self, *args, **kwargs)

    return _wrapped


class ClickUpHookTests(WebhookTestCase):
    @mock_clickup_api_calls
    def test_task_created(self) -> None:
        self.check_webhook(
            "task_created",
            expected_topic_name=f"Task: {TASK_NAME}",
            expected_message=f"{AUTHOR} created [{TASK_NAME}]({TASK_URL}).",
        )

    @mock_clickup_api_calls
    def test_task_updated(self) -> None:
        self.check_webhook(
            "task_updated",
            expected_topic_name=f"Task: {TASK_NAME}",
            expected_message=f"{AUTHOR} updated [{TASK_NAME}]({TASK_URL}).",
        )

    def test_task_deleted(self) -> None:
        self.check_webhook(
            "task_deleted",
            expected_topic_name="Task",
            expected_message="A task was deleted.",
        )

    def test_task_event_without_token(self) -> None:
        self.check_webhook(
            "task_created",
            expected_topic_name="Task",
            expected_message=f"{AUTHOR} created [Task]({TASK_URL}).",
        )

    def test_ignored_events(self) -> None:
        payload = orjson.loads(self.webhook_fixture_data("clickup", "task_updated"))

        for event_type in IGNORED_EVENTS:
            with self.subTest(event_type=event_type):
                payload["event"] = event_type
                last_message = self.get_last_message()
                result = self.client_post(
                    self.url, orjson.dumps(payload), content_type="application/json"
                )
                self.assert_json_success(result)
                self.assertEqual(self.get_last_message().id, last_message.id)

    @responses.activate
    def test_get_clickup_data(self) -> None:
        self.assertIsNone(get_clickup_api_data(TASK_ID, "task", ""))

        responses.add(
            responses.GET,
            TASK_API_URL,
            self.webhook_fixture_data("clickup", "task_api_data"),
        )
        result = get_clickup_api_data(TASK_ID, "task", "token")
        assert result is not None
        self.assertEqual(result, json.loads(self.webhook_fixture_data("clickup", "task_api_data")))

        responses.add(
            responses.GET,
            TASK_API_URL,
            json={"object": "error", "status": 500, "message": "Internal error"},
            status=500,
        )
        with self.assertLogs("zerver.lib.webhooks.common", level="WARNING") as warn_logs:
            self.assertIsNone(get_clickup_api_data(TASK_ID, "task", "token"))
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.lib.webhooks.common:Failed to fetch data from {TASK_API_URL}"
                f" for ClickUp integration: 500 Server Error: Internal Server Error for url: {TASK_API_URL}"
            ],
        )

        responses.add(
            responses.GET,
            TASK_API_URL,
            body="invalid json",
            status=200,
        )
        self.assertIsNone(get_clickup_api_data(TASK_ID, "task", "token"))

        responses.add(
            responses.GET,
            TASK_API_URL,
            body=requests.RequestException("Connection error"),
        )
        with self.assertLogs("zerver.lib.webhooks.common", level="WARNING") as warn_logs:
            self.assertIsNone(get_clickup_api_data(TASK_ID, "task", "token"))
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.lib.webhooks.common:Failed to fetch data from {TASK_API_URL}"
                " for ClickUp integration: Connection error"
            ],
        )
