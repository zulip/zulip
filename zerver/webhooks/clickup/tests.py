import json
from collections.abc import Callable
from functools import wraps
from typing import Any, Concatenate

import orjson
import requests
import responses
from typing_extensions import ParamSpec

from zerver.lib.bot_config import set_bot_config
from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.clickup.view import IGNORED_EVENTS, duration_pretty, get_clickup_api_data

ParamT = ParamSpec("ParamT")

TEAM_ID = "90161438581"
TASK_ID = "86d3cc9fu"
TASK_API_URL = f"https://api.clickup.com/api/v2/task/{TASK_ID}"
TASK_URL = f"https://app.clickup.com/t/{TEAM_ID}/{TASK_ID}"
TASK_NAME = "Zulip Test Task"
AUTHOR = "Sathwik Suresh Shetty"

SPACE_ID = "90167241645"
SPACE_API_URL = f"https://api.clickup.com/api/v2/space/{SPACE_ID}"
SPACE_URL = f"https://app.clickup.com/{TEAM_ID}/v/s/{SPACE_ID}"
SPACE_NAME = "Zulip Test"

FOLDER_ID = "901610136716"
FOLDER_API_URL = f"https://api.clickup.com/api/v2/folder/{FOLDER_ID}"
FOLDER_URL = f"https://app.clickup.com/{TEAM_ID}/v/o/f/{FOLDER_ID}"
FOLDER_NAME = "Zulip Test Folder"

GOAL_ID = "9d53e457-b8d6-47d4-9f1a-cab80be8d511"
GOAL_API_URL = f"https://api.clickup.com/api/v2/goal/{GOAL_ID}"
GOAL_URL = f"https://app.clickup.com/{TEAM_ID}/goals/1"
GOAL_LIST_URL = f"https://app.clickup.com/{TEAM_ID}/goals"
GOAL_NAME = "Weekly Goal"

KEY_RESULT_NAME = "Milestone 1"

LIST_ID = "901615428252"
LIST_API_URL = f"https://api.clickup.com/api/v2/list/{LIST_ID}"
LIST_URL = f"https://app.clickup.com/{TEAM_ID}/v/l/li/{LIST_ID}"
LIST_NAME = "Zulip Task List"


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
            self.webhook_fixture_data("clickup", "api_responses/task_api_data"),
        )
        responses.add(
            responses.GET,
            SPACE_API_URL,
            self.webhook_fixture_data("clickup", "api_responses/space_api_data"),
        )
        responses.add(
            responses.GET,
            FOLDER_API_URL,
            self.webhook_fixture_data("clickup", "api_responses/folder_api_data"),
        )
        responses.add(
            responses.GET,
            GOAL_API_URL,
            self.webhook_fixture_data("clickup", "api_responses/goal_api_data"),
        )
        responses.add(
            responses.GET,
            LIST_API_URL,
            self.webhook_fixture_data("clickup", "api_responses/list_api_data"),
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
    def test_task_status_updated(self) -> None:
        self.check_webhook(
            "task_updated",
            expected_topic_name=f"Task: {TASK_NAME}",
            expected_message=f"{AUTHOR} updated the status of [{TASK_NAME}]({TASK_URL}) to complete.",
        )

    @mock_clickup_api_calls
    def test_task_priority_updated(self) -> None:
        self.check_task_update(
            [{"field": "priority", "after": {"priority": "urgent"}}],
            f"{AUTHOR} updated the priority of [{TASK_NAME}]({TASK_URL}) to urgent.",
        )

    @mock_clickup_api_calls
    def test_task_priority_cleared(self) -> None:
        self.check_task_update(
            [{"field": "priority", "after": None}],
            f"{AUTHOR} cleared the priority of [{TASK_NAME}]({TASK_URL}).",
        )

    @mock_clickup_api_calls
    def test_task_due_date_updated(self) -> None:
        self.check_task_update(
            [
                {"field": "duration", "after": ", , , , , 23040 minutes"},
                {"field": "due_date", "after": "1782167400000"},
            ],
            f"{AUTHOR} updated the due date of [{TASK_NAME}]({TASK_URL})"
            " to <time:2026-06-22T22:30:00+00:00>.",
        )

    @mock_clickup_api_calls
    def test_task_due_date_cleared(self) -> None:
        self.check_task_update(
            [
                {"field": "duration", "after": ", , , , , 23040 minutes"},
                {"field": "due_date", "after": None},
            ],
            f"{AUTHOR} cleared the due date of [{TASK_NAME}]({TASK_URL}).",
        )

    @mock_clickup_api_calls
    def test_task_start_date_updated(self) -> None:
        self.check_task_update(
            [{"field": "start_date", "after": "1784068200000"}],
            f"{AUTHOR} updated the start date of [{TASK_NAME}]({TASK_URL})"
            " to <time:2026-07-14T22:30:00+00:00>.",
        )

    @mock_clickup_api_calls
    def test_task_start_date_cleared(self) -> None:
        self.check_task_update(
            [{"field": "start_date", "after": None}],
            f"{AUTHOR} cleared the start date of [{TASK_NAME}]({TASK_URL}).",
        )

    @mock_clickup_api_calls
    def test_task_time_estimate_updated(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "time_estimate",
                    "after": "3600000",
                    "data": {"time_estimate_string": " 1 hours"},
                }
            ],
            f"{AUTHOR} updated the time estimate of [{TASK_NAME}]({TASK_URL}) to 1 hours.",
        )

    @mock_clickup_api_calls
    def test_task_time_estimate_cleared(self) -> None:
        self.check_task_update(
            [{"field": "time_estimate", "after": None}],
            f"{AUTHOR} cleared the time estimate of [{TASK_NAME}]({TASK_URL}).",
        )

    @mock_clickup_api_calls
    def test_task_time_tracked(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "time_spent",
                    "data": {"total_time": "900000"},
                    "after": {"id": "4218213762738104432", "time": "900000"},
                }
            ],
            f"{AUTHOR} tracked 15 mins on [{TASK_NAME}]({TASK_URL}).",
        )

    @mock_clickup_api_calls
    def test_task_assignee_added(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "assignee_add",
                    "after": {"username": AUTHOR},
                }
            ],
            f"{AUTHOR} assigned [{TASK_NAME}]({TASK_URL}) to {AUTHOR}.",
        )

    @mock_clickup_api_calls
    def test_task_assignee_removed(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "assignee_rem",
                    "before": {"username": AUTHOR},
                    "after": None,
                }
            ],
            f"{AUTHOR} unassigned {AUTHOR} from [{TASK_NAME}]({TASK_URL}).",
        )

    @mock_clickup_api_calls
    def test_task_comment_posted(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "comment",
                    "after": "90160077692010",
                    "comment": {"text_content": "what task?\n"},
                }
            ],
            f"{AUTHOR} commented on [{TASK_NAME}]({TASK_URL}):\n``` quote\nwhat task?\n```",
        )

    @mock_clickup_api_calls
    def test_task_comment_reply_posted(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "comment",
                    "after": "90160199733534",
                    "comment": {"text_content": "Ohh okay\n"},
                    "parent_comment": {"text_content": "what a task?\n"},
                }
            ],
            f"{AUTHOR} replied to a comment on [{TASK_NAME}]({TASK_URL}):\n``` quote\nOhh okay\n```",
        )

    @mock_clickup_api_calls
    def test_task_comment_posted_without_text(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "comment",
                    "after": "90160077692010",
                    "comment": {"text_content": ""},
                }
            ],
            f"{AUTHOR} commented on [{TASK_NAME}]({TASK_URL}).",
        )

    @mock_clickup_api_calls
    def test_task_custom_field_updated(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "custom_field",
                    "after": "good",
                    "custom_field": {"name": "new field", "type": "short_text"},
                }
            ],
            f"{AUTHOR} updated the new field of [{TASK_NAME}]({TASK_URL}) to good.",
        )

    @mock_clickup_api_calls
    def test_task_custom_field_date_updated(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "custom_field",
                    "after": "1782167400000",
                    "custom_field": {"name": "Deadline", "type": "date"},
                }
            ],
            f"{AUTHOR} updated the Deadline of [{TASK_NAME}]({TASK_URL})"
            " to <time:2026-06-22T22:30:00+00:00>.",
        )

    @mock_clickup_api_calls
    def test_task_custom_field_cleared(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "custom_field",
                    "after": None,
                    "custom_field": {"name": "description", "type": "short_text"},
                }
            ],
            f"{AUTHOR} cleared the description of [{TASK_NAME}]({TASK_URL}).",
        )

    @mock_clickup_api_calls
    def test_task_attachment_added(self) -> None:
        attachment_url = (
            "https://t90161438581.p.clickup-attachments.com"
            "/t90161438581/36f6c212-fd29-4315-8836-50eb63ba8fdb/Sathwik_Shetty_Cover_Letter.pdf"
        )
        self.check_task_update(
            [
                {
                    "field": "attachments",
                    "after": "36f6c212-fd29-4315-8836-50eb63ba8fdb.pdf",
                    "attachments": [{"title": "Sathwik_Shetty.pdf", "url": attachment_url}],
                }
            ],
            f"{AUTHOR} added [Sathwik_Shetty.pdf]({attachment_url}) to [{TASK_NAME}]({TASK_URL}).",
        )

    @mock_clickup_api_calls
    def test_task_checklist_item_added(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "checklist_items_added",
                    "after": "e9ecc97c-a040-457c-aa7e-635f317e5b5e",
                    "checklist": {"name": "To be done"},
                    "checklist_items": [{"name": "new"}],
                }
            ],
            f"{AUTHOR} added new to the To be done checklist on [{TASK_NAME}]({TASK_URL}).",
        )

    @mock_clickup_api_calls
    def test_task_checklist_item_resolved(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "checklist_item_resolved",
                    "before": "false",
                    "after": "true",
                    "checklist": {"name": "To be done"},
                    "checklist_item": {"name": "new1"},
                }
            ],
            f"{AUTHOR} checked off new1 in the To be done checklist on [{TASK_NAME}]({TASK_URL}).",
        )

    @mock_clickup_api_calls
    def test_task_moved(self) -> None:
        self.check_task_update(
            [
                {
                    "field": "section_moved",
                    "before": {
                        "id": "901615428490",
                        "name": "Backlog",
                        "project": {"name": "Zulip"},
                        "category": {"name": "hidden", "hidden": True},
                    },
                    "after": {
                        "id": "901615563789",
                        "name": "Sprint 1",
                        "project": {"name": "Team Space"},
                        "category": {"name": "Zulip Test", "hidden": False},
                    },
                }
            ],
            f"{AUTHOR} moved [{TASK_NAME}]({TASK_URL}) from Backlog to Sprint 1.",
        )

    @mock_clickup_api_calls
    def test_task_generic_update(self) -> None:
        self.check_task_update(
            [{"field": "tag", "after": [{"name": "bug"}]}],
            f"{AUTHOR} updated [{TASK_NAME}]({TASK_URL}).",
        )

    def test_duration_pretty(self) -> None:
        test_cases = [
            (0, "0 secs"),
            (1, "1 sec"),
            (45, "45 secs"),
            (59, "59 secs"),
            (60, "1 min"),
            (3599, "1 hr"),
            (3600, "1 hr"),
            (3645, "1 hr 1 min"),
            (3661, "1 hr 1 min"),
            (7200, "2 hrs"),
            (7320, "2 hrs 2 mins"),
        ]

        for duration, expected_output in test_cases:
            with self.subTest(duration=duration):
                self.assertEqual(duration_pretty(duration), expected_output)

    def check_task_update(self, history_items: list[dict[str, Any]], expected_message: str) -> None:
        payload = orjson.loads(self.webhook_fixture_data("clickup", "task_updated"))
        user = {"username": AUTHOR}
        payload["history_items"] = [{"user": user, **item} for item in history_items]
        self.subscribe(self.test_user, self.channel_name)
        msg = self.send_webhook_payload(
            self.test_user,
            self.url,
            orjson.dumps(payload).decode(),
            content_type="application/json",
        )
        self.assert_channel_message(
            message=msg,
            channel_name=self.channel_name,
            topic_name=f"Task: {TASK_NAME}",
            content=expected_message,
        )

    def test_task_deleted(self) -> None:
        self.check_webhook(
            "task_deleted",
            expected_topic_name=f"Task: {TASK_ID}",
            expected_message="A task was deleted.",
        )

    def test_task_event_without_token(self) -> None:
        with self.assertLogs("zerver.webhooks.clickup.view", level="WARNING") as warn_logs:
            self.check_webhook(
                "task_created",
                expected_topic_name=f"Task: {TASK_ID}",
                expected_message=f"{AUTHOR} created [Task]({TASK_URL}).",
            )
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.webhooks.clickup.view:ClickUp webhook for bot {self.test_user.full_name}"
                " has no configured API token; entity names can't be fetched."
            ],
        )

    def test_payload_without_event(self) -> None:
        result = self.client_post(self.url, {}, content_type="application/json")
        self.assert_json_error(
            result, "Unable to parse request: Did ClickUp generate this event?", 400
        )

    @mock_clickup_api_calls
    def test_space_created(self) -> None:
        self.check_webhook(
            "space_created",
            expected_topic_name=f"Space: {SPACE_NAME}",
            expected_message=f"[{SPACE_NAME}]({SPACE_URL}) was created.",
        )

    @mock_clickup_api_calls
    def test_space_updated(self) -> None:
        self.check_webhook(
            "space_updated",
            expected_topic_name=f"Space: {SPACE_NAME}",
            expected_message=f"[{SPACE_NAME}]({SPACE_URL}) was updated.",
        )

    def test_space_deleted(self) -> None:
        self.check_webhook(
            "space_deleted",
            expected_topic_name=f"Space: {SPACE_ID}",
            expected_message="A space was deleted.",
        )

    def test_space_event_without_token(self) -> None:
        with self.assertLogs("zerver.webhooks.clickup.view", level="WARNING") as warn_logs:
            self.check_webhook(
                "space_created",
                expected_topic_name=f"Space: {SPACE_ID}",
                expected_message=f"[Space]({SPACE_URL}) was created.",
            )
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.webhooks.clickup.view:ClickUp webhook for bot {self.test_user.full_name}"
                " has no configured API token; entity names can't be fetched."
            ],
        )

    @mock_clickup_api_calls
    def test_folder_created(self) -> None:
        self.check_webhook(
            "folder_created",
            expected_topic_name=f"Folder: {FOLDER_NAME}",
            expected_message=f"[{FOLDER_NAME}]({FOLDER_URL}) was created.",
        )

    @mock_clickup_api_calls
    def test_folder_updated(self) -> None:
        self.check_webhook(
            "folder_updated",
            expected_topic_name=f"Folder: {FOLDER_NAME}",
            expected_message=f"[{FOLDER_NAME}]({FOLDER_URL}) was updated.",
        )

    def test_folder_deleted(self) -> None:
        self.check_webhook(
            "folder_deleted",
            expected_topic_name=f"Folder: {FOLDER_ID}",
            expected_message="A folder was deleted.",
        )

    def test_folder_event_without_token(self) -> None:
        with self.assertLogs("zerver.webhooks.clickup.view", level="WARNING") as warn_logs:
            self.check_webhook(
                "folder_created",
                expected_topic_name=f"Folder: {FOLDER_ID}",
                expected_message=f"[Folder]({FOLDER_URL}) was created.",
            )
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.webhooks.clickup.view:ClickUp webhook for bot {self.test_user.full_name}"
                " has no configured API token; entity names can't be fetched."
            ],
        )

    @mock_clickup_api_calls
    def test_goal_created(self) -> None:
        self.check_webhook(
            "goal_created",
            expected_topic_name=f"Goal: {GOAL_NAME}",
            expected_message=f"[{GOAL_NAME}]({GOAL_URL}) was created.",
        )

    @mock_clickup_api_calls
    def test_goal_updated(self) -> None:
        self.check_webhook(
            "goal_updated",
            expected_topic_name=f"Goal: {GOAL_NAME}",
            expected_message=f"[{GOAL_NAME}]({GOAL_URL}) was updated.",
        )

    def test_goal_deleted(self) -> None:
        self.check_webhook(
            "goal_deleted",
            expected_topic_name=f"Goal: {GOAL_ID}",
            expected_message="A goal was deleted.",
        )

    def test_goal_event_without_token(self) -> None:
        with self.assertLogs("zerver.webhooks.clickup.view", level="WARNING") as warn_logs:
            self.check_webhook(
                "goal_created",
                expected_topic_name=f"Goal: {GOAL_ID}",
                expected_message=f"[Goal]({GOAL_LIST_URL}) was created.",
            )
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.webhooks.clickup.view:ClickUp webhook for bot {self.test_user.full_name}"
                " has no configured API token; entity names can't be fetched."
            ],
        )

    @mock_clickup_api_calls
    def test_key_result_created(self) -> None:
        self.check_webhook(
            "key_result_created",
            expected_topic_name=f"Goal: {GOAL_NAME}",
            expected_message=f"[{KEY_RESULT_NAME}]({GOAL_URL}) was created.",
        )

    @mock_clickup_api_calls
    def test_key_result_updated(self) -> None:
        self.check_webhook(
            "key_result_updated",
            expected_topic_name=f"Goal: {GOAL_NAME}",
            expected_message=f"[{KEY_RESULT_NAME}]({GOAL_URL}) was updated.",
        )

    def test_key_result_deleted(self) -> None:
        self.check_webhook(
            "key_result_deleted",
            expected_topic_name=f"Goal: {GOAL_ID}",
            expected_message="A key result was deleted.",
        )

    def test_key_result_event_without_token(self) -> None:
        with self.assertLogs("zerver.webhooks.clickup.view", level="WARNING") as warn_logs:
            self.check_webhook(
                "key_result_created",
                expected_topic_name=f"Goal: {GOAL_ID}",
                expected_message=f"[Key result]({GOAL_LIST_URL}) was created.",
            )
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.webhooks.clickup.view:ClickUp webhook for bot {self.test_user.full_name}"
                " has no configured API token; entity names can't be fetched."
            ],
        )

    @mock_clickup_api_calls
    def test_list_created(self) -> None:
        self.check_webhook(
            "list_created",
            expected_topic_name=f"List: {LIST_NAME}",
            expected_message=f"[{LIST_NAME}]({LIST_URL}) was created.",
        )

    @mock_clickup_api_calls
    def test_list_updated(self) -> None:
        self.check_webhook(
            "list_updated",
            expected_topic_name=f"List: {LIST_NAME}",
            expected_message=f"[{LIST_NAME}]({LIST_URL}) was updated.",
        )

    def test_list_deleted(self) -> None:
        self.check_webhook(
            "list_deleted",
            expected_topic_name=f"List: {LIST_ID}",
            expected_message="A list was deleted.",
        )

    def test_list_event_without_token(self) -> None:
        with self.assertLogs("zerver.webhooks.clickup.view", level="WARNING") as warn_logs:
            self.check_webhook(
                "list_created",
                expected_topic_name=f"List: {LIST_ID}",
                expected_message=f"[List]({LIST_URL}) was created.",
            )
        self.assertEqual(
            warn_logs.output,
            [
                f"WARNING:zerver.webhooks.clickup.view:ClickUp webhook for bot {self.test_user.full_name}"
                " has no configured API token; entity names can't be fetched."
            ],
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
            self.webhook_fixture_data("clickup", "api_responses/task_api_data"),
        )
        result = get_clickup_api_data(TASK_ID, "task", "token")
        assert result is not None
        self.assertEqual(
            result, json.loads(self.webhook_fixture_data("clickup", "api_responses/task_api_data"))
        )

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
