from zerver.lib.test_classes import WebhookTestCase
from unittest.mock import patch

import json

EXPECTED_TOPIC = "ClickUp Notification"


class ClickUpHookTests(WebhookTestCase):
    STREAM_NAME = "ClickUp"
    URL_TEMPLATE = "/api/v1/external/clickup?api_key={api_key}&stream={stream}"
    FIXTURE_DIR_NAME = "clickup"
    WEBHOOK_DIR_NAME = "clickup"

    def test_task_created(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_task") as mock_get_task, open(
            "zerver/webhooks/clickup/callback_fixtures/get_task.json"
        ) as f:
            mock_get_task.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = (
                ":new: **[Task: Tanswer](https://app.clickup.com/XXXXXXXX/home)** has been created in your ClickUp space!"
                "\n - Created by: **Pieter CK**"
            )

            self.check_webhook(
                fixture_name="task_created",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_task.assert_called_once()

    def test_task_deleted(self) -> None:
        self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
        expected_message = ":trash_can: A Task has been deleted from your ClickUp space!"

        self.check_webhook(
            fixture_name="task_deleted",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_updated_time_spent(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_task") as mock_get_task, open(
            "zerver/webhooks/clickup/callback_fixtures/get_task.json"
        ) as f:
            mock_get_task.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = (
                "**[Task: Tanswer](https://app.clickup.com/XXXXXXXX/home)** has been updated!\n"
                "~~~ quote\n"
                " :stopwatch: Time spent changed to **19:02:00**\n"
                "~~~"
            )

            self.check_webhook(
                fixture_name="task_updated_time_spent",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_task.assert_called_once()

    def test_task_updated_time_estimate(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_task") as mock_get_task, open(
            "zerver/webhooks/clickup/callback_fixtures/get_task.json"
        ) as f:
            mock_get_task.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = (
                "**[Task: Tanswer](https://app.clickup.com/XXXXXXXX/home)** has been updated!\n"
                "~~~ quote\n"
                " :ruler: Time estimate changed from **None** to **1 hour 30 minutes** by **Pieter**\n"
                "~~~"
            )

            self.check_webhook(
                fixture_name="task_updated_time_estimate",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_task.assert_called_once()

    def test_task_updated_comment(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_task") as mock_get_task, open(
            "zerver/webhooks/clickup/callback_fixtures/get_task.json"
        ) as f:
            mock_get_task.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = (
                "**[Task: Tanswer](https://app.clickup.com/XXXXXXXX/home)** has been updated!\n"
                "~~~ quote\n"
                " :speaking_head: Commented by **Pieter**\n"
                "~~~"
            )

            self.check_webhook(
                fixture_name="task_updated_comment",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_task.assert_called_once()

    def test_task_moved(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_task") as mock_get_task, open(
            "zerver/webhooks/clickup/callback_fixtures/get_task.json"
        ) as f:
            mock_get_task.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = (
                "**[Task: Tanswer](https://app.clickup.com/XXXXXXXX/home)** has been updated!\n"
                "~~~ quote\n"
                " :folder: Moved from **Webhook payloads** to **webhook payloads 2**\n"
                "~~~"
            )

            self.check_webhook(
                fixture_name="task_moved",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_task.assert_called_once()

    def test_task_updated_assignee(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_task") as mock_get_task, open(
            "zerver/webhooks/clickup/callback_fixtures/get_task.json"
        ) as f:
            mock_get_task.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = (
                "**[Task: Tanswer](https://app.clickup.com/XXXXXXXX/home)** has been updated!\n"
                "~~~ quote\n"
                " :silhouette: Now assigned to **Sam**\n"
                "~~~"
            )

            self.check_webhook(
                fixture_name="task_updated_assignee",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_task.assert_called_once()

    def test_task_updated_due_date(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_task") as mock_get_task, open(
            "zerver/webhooks/clickup/callback_fixtures/get_task.json"
        ) as f:
            mock_get_task.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = (
                "**[Task: Tanswer](https://app.clickup.com/XXXXXXXX/home)** has been updated!\n"
                "~~~ quote\n"
                " :spiral_calendar: Due date updated from **2022-01-20** to **2022-01-31**\n"
                "~~~"
            )

            self.check_webhook(
                fixture_name="task_updated_due_date",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_task.assert_called_once()

    def test_task_updated_priority(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_task") as mock_get_task, open(
            "zerver/webhooks/clickup/callback_fixtures/get_task.json"
        ) as f:
            mock_get_task.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = (
                "**[Task: Tanswer](https://app.clickup.com/XXXXXXXX/home)** has been updated!\n"
                "~~~ quote\n"
                " :note: Updated task priority from **None** to **high**\n"
                "~~~"
            )

            self.check_webhook(
                fixture_name="task_updated_priority",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_task.assert_called_once()

    def test_task_updated_status(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_task") as mock_get_task, open(
            "zerver/webhooks/clickup/callback_fixtures/get_task.json"
        ) as f:
            mock_get_task.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = (
                "**[Task: Tanswer](https://app.clickup.com/XXXXXXXX/home)** has been updated!\n"
                "~~~ quote\n"
                " :note: Updated task status from **to do** to **in progress**\n"
                "~~~"
            )

            self.check_webhook(
                fixture_name="task_updated_status",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_task.assert_called_once()

    def test_list_created(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_list") as mock_get_list, open(
            "zerver/webhooks/clickup/callback_fixtures/get_list.json"
        ) as f:
            mock_get_list.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = ":new: **[List: List-an al Gaib](https://app.clickup.com/XXXXXXXX/home)** has been created in your ClickUp space!"
            self.check_webhook(
                fixture_name="list_created",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_list.assert_called_once()

    def test_list_deleted(self) -> None:
        self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
        expected_message = ":trash_can: A List has been deleted from your ClickUp space!"
        self.check_webhook(
            fixture_name="list_deleted",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_list_updated(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_list") as mock_get_list, open(
            "zerver/webhooks/clickup/callback_fixtures/get_list.json"
        ) as f:
            mock_get_list.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = (
                "**[List: List-an al Gaib](https://app.clickup.com/XXXXXXXX/home)** has been updated!\n"
                "~~~ quote\n"
                " :pencil: Renamed from **webhook payloads 2** to **Webhook payloads round 2**\n"
                "~~~"
            )
            self.check_webhook(
                fixture_name="list_updated",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_list.assert_called_once()

    def test_folder_created(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_folder") as mock_get_folder, open(
            "zerver/webhooks/clickup/callback_fixtures/get_folder.json"
        ) as f:
            mock_get_folder.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = ":new: **[Folder: Lord Foldemort](https://app.clickup.com/XXXXXXXX/home)** has been created in your ClickUp space!"
            self.check_webhook(
                fixture_name="folder_created",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_folder.assert_called_once()

    def test_folder_deleted(self) -> None:
        self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
        expected_message = ":trash_can: A Folder has been deleted from your ClickUp space!"
        self.check_webhook(
            fixture_name="folder_deleted",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_space_created(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_space") as mock_get_space, open(
            "zerver/webhooks/clickup/callback_fixtures/get_space.json"
        ) as f:
            mock_get_space.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = ":new: **[Space: the Milky Way](https://app.clickup.com/XXXXXXXX/home)** has been created in your ClickUp space!"
            self.check_webhook(
                fixture_name="space_created",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_space.assert_called_once()

    def test_space_deleted(self) -> None:
        self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
        expected_message = ":trash_can: A Space has been deleted from your ClickUp space!"
        self.check_webhook(
            fixture_name="space_deleted",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )

    def test_space_updated(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_space") as mock_get_space, open(
            "zerver/webhooks/clickup/callback_fixtures/get_space.json"
        ) as f:
            mock_get_space.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = "**[Space: the Milky Way](https://app.clickup.com/XXXXXXXX/home)** has been updated!"
            self.check_webhook(
                fixture_name="space_updated",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_space.assert_called_once()
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")

    def test_goal_created(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_goal") as mock_get_goal, open(
            "zerver/webhooks/clickup/callback_fixtures/get_goal.json"
        ) as f:
            mock_get_goal.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = ":new: **[Goal: hat-trick](https://app.clickup.com/512/goals/6)** has been created in your ClickUp space!"
            self.check_webhook(
                fixture_name="goal_created",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_goal.assert_called_once()

    def test_goal_updated(self) -> None:
        with patch("zerver.webhooks.clickup.view.get_goal") as mock_get_goal, open(
            "zerver/webhooks/clickup/callback_fixtures/get_goal.json"
        ) as f:
            mock_get_goal.return_value = json.load(f)
            self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
            expected_message = (
                "**[Goal: hat-trick](https://app.clickup.com/512/goals/6)** has been updated!"
            )
            self.check_webhook(
                fixture_name="goal_updated",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )
            mock_get_goal.assert_called_once()

    def test_goal_deleted(self) -> None:
        self.url = self.build_webhook_url(team_id="XXXXXXXX", clickup_api_key="123")
        expected_message = ":trash_can: A Goal has been deleted from your ClickUp space!"
        self.check_webhook(
            fixture_name="goal_deleted",
            expected_topic_name=EXPECTED_TOPIC,
            expected_message=expected_message,
        )
