import json
from typing import Any
from unittest.mock import MagicMock, patch

from typing_extensions import override

from zerver.lib.test_classes import WebhookTestCase
from zerver.webhooks.clickup.view import get_clickup_api_data

EXPECTED_TOPIC = "ClickUp Notification"


class ClickUpHookTests(WebhookTestCase):
    CHANNEL_NAME = "ClickUp"
    URL_TEMPLATE = "/api/v1/external/clickup?api_key={api_key}&stream={stream}&team_id=XXXXXXX&clickup_api_key=123"
    FIXTURE_DIR_NAME = "clickup"
    WEBHOOK_DIR_NAME = "clickup"

    @override
    def setUp(self) -> None:
        super().setUp()
        self.mock_get_clickup_api_data = patch(
            "zerver.webhooks.clickup.view.get_clickup_api_data"
        ).start()
        self.mock_get_clickup_api_data.side_effect = self.mocked_get_clickup_api_data

    @override
    def tearDown(self) -> None:
        self.mock_get_clickup_api_data.stop()
        super().tearDown()

    def mocked_get_clickup_api_data(self, clickup_api_path: str, **kwargs: Any) -> None:
        item = clickup_api_path.split("/")[0]
        with open(f"zerver/webhooks/clickup/callback_fixtures/get_{item}.json") as f:
            return json.load(f)

    def test_task_created(self) -> None:
        expected_message = (
            ":new: **[Task: Tanswer](https://app.clickup.com/XXXXXXX/home)** has been created in your ClickUp space!"
            "\n - Created by: **Pieter CK**"
        )

        self.check_webhook(
            fixture_name="task_created",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_task_deleted(self) -> None:
        self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
        expected_message = ":trash_can: A Task has been deleted from your ClickUp space!"

        self.check_webhook(
            fixture_name="task_deleted",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_updated_time_spent(self) -> None:
        expected_message = (
            "**[Task: Tanswer](https://app.clickup.com/XXXXXXX/home)** has been updated!\n"
            "~~~ quote\n"
            " :stopwatch: Time spent changed to **19:02:00**\n"
            "~~~"
        )

        self.check_webhook(
            fixture_name="task_updated_time_spent",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_task_updated_time_estimate(self) -> None:
        expected_message = (
            "**[Task: Tanswer](https://app.clickup.com/XXXXXXX/home)** has been updated!\n"
            "~~~ quote\n"
            " :ruler: Time estimate changed from **None** to **1 hour 30 minutes** by **Pieter**\n"
            "~~~"
        )

        self.check_webhook(
            fixture_name="task_updated_time_estimate",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_task_updated_comment(self) -> None:
        expected_message = (
            "**[Task: Tanswer](https://app.clickup.com/XXXXXXX/home)** has been updated!\n"
            "~~~ quote\n"
            " :speaking_head: Commented by **Pieter**\n"
            "~~~"
        )

        self.check_webhook(
            fixture_name="task_updated_comment",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_task_moved(self) -> None:
        expected_message = (
            "**[Task: Tanswer](https://app.clickup.com/XXXXXXX/home)** has been updated!\n"
            "~~~ quote\n"
            " :folder: Moved from **Webhook payloads** to **webhook payloads 2**\n"
            "~~~"
        )

        self.check_webhook(
            fixture_name="task_moved",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_task_updated_assignee(self) -> None:
        expected_message = (
            "**[Task: Tanswer](https://app.clickup.com/XXXXXXX/home)** has been updated!\n"
            "~~~ quote\n"
            " :silhouette: Now assigned to **Sam**\n"
            "~~~"
        )

        self.check_webhook(
            fixture_name="task_updated_assignee",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_task_updated_due_date(self) -> None:
        expected_message = (
            "**[Task: Tanswer](https://app.clickup.com/XXXXXXX/home)** has been updated!\n"
            "~~~ quote\n"
            " :spiral_calendar: Due date updated from <time: 2022-01-20> to <time: 2022-01-31>\n"
            "~~~"
        )

        self.check_webhook(
            fixture_name="task_updated_due_date",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_task_updated_priority(self) -> None:
        expected_message = (
            "**[Task: Tanswer](https://app.clickup.com/XXXXXXX/home)** has been updated!\n"
            "~~~ quote\n"
            " :note: Updated task priority from **None** to **high**\n"
            "~~~"
        )

        self.check_webhook(
            fixture_name="task_updated_priority",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_task_updated_status(self) -> None:
        expected_message = (
            "**[Task: Tanswer](https://app.clickup.com/XXXXXXX/home)** has been updated!\n"
            "~~~ quote\n"
            " :note: Updated task status from **to do** to **in progress**\n"
            "~~~"
        )

        self.check_webhook(
            fixture_name="task_updated_status",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_list_created(self) -> None:
        expected_message = ":new: **[List: Listener](https://app.clickup.com/XXXXXXX/home)** has been created in your ClickUp space!"
        self.check_webhook(
            fixture_name="list_created",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_list_deleted(self) -> None:
        expected_message = ":trash_can: A List has been deleted from your ClickUp space!"
        self.check_webhook(
            fixture_name="list_deleted",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_list_updated(self) -> None:
        expected_message = (
            "**[List: Listener](https://app.clickup.com/XXXXXXX/home)** has been updated!\n"
            "~~~ quote\n"
            " :pencil: Renamed from **webhook payloads 2** to **Webhook payloads round 2**\n"
            "~~~"
        )
        self.check_webhook(
            fixture_name="list_updated",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_folder_created(self) -> None:
        expected_message = ":new: **[Folder: Lord Foldemort](https://app.clickup.com/XXXXXXX/home)** has been created in your ClickUp space!"
        self.check_webhook(
            fixture_name="folder_created",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_folder_deleted(self) -> None:
        expected_message = ":trash_can: A Folder has been deleted from your ClickUp space!"
        self.check_webhook(
            fixture_name="folder_deleted",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_space_created(self) -> None:
        expected_message = ":new: **[Space: the Milky Way](https://app.clickup.com/XXXXXXX/home)** has been created in your ClickUp space!"
        self.check_webhook(
            fixture_name="space_created",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_space_deleted(self) -> None:
        expected_message = ":trash_can: A Space has been deleted from your ClickUp space!"
        self.check_webhook(
            fixture_name="space_deleted",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_space_updated(self) -> None:
        expected_message = (
            "**[Space: the Milky Way](https://app.clickup.com/XXXXXXX/home)** has been updated!"
        )
        self.check_webhook(
            fixture_name="space_updated",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_goal_created(self) -> None:
        expected_message = ":new: **[Goal: hat-trick](https://app.clickup.com/512/goals/6)** has been created in your ClickUp space!"
        self.check_webhook(
            fixture_name="goal_created",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_goal_updated(self) -> None:
        expected_message = (
            "**[Goal: hat-trick](https://app.clickup.com/512/goals/6)** has been updated!"
        )
        self.check_webhook(
            fixture_name="goal_updated",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_goal_deleted(self) -> None:
        expected_message = ":trash_can: A Goal has been deleted from your ClickUp space!"
        self.check_webhook(
            fixture_name="goal_deleted",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_payload_with_spammy_field(self) -> None:
        expected_message = (
            "**[Task: Tanswer](https://app.clickup.com/XXXXXXX/home)** has been updated!"
        )
        self.check_webhook(
            fixture_name="payload_with_spammy_field",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_get_clickup_api_data_success_request(self) -> None:
        with patch("zerver.webhooks.clickup.view.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"key123": "value322"}

            mock_get.return_value = mock_response

            result = get_clickup_api_data("list/123123", token="123")

            mock_get.assert_called_once_with(
                "https://api.clickup.com/api/v2/list/123123",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "123",
                },
                params={},
            )
            self.assertEqual(result, {"key123": "value322"})

    def test_get_clickup_api_data_failure_request(self) -> None:
        with patch("zerver.webhooks.clickup.view.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_get.return_value = mock_response

            exception_msg = "HTTP error accessing the ClickUp API. Error: 404"

            with self.assertRaisesRegex(Exception, exception_msg):
                get_clickup_api_data("list/123123", token="123")

            mock_get.assert_called_once_with(
                "https://api.clickup.com/api/v2/list/123123",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "123",
                },
                params={},
            )

    def test_get_clickup_api_data_missing_api_token(self) -> None:
        with patch("zerver.webhooks.clickup.view.requests"):
            exception_msg = "ClickUp API 'token' missing in kwargs"
            with self.assertRaisesRegex(AssertionError, exception_msg):
                get_clickup_api_data("list/123123", asdasd="123")
