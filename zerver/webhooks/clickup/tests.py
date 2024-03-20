import json
from typing import Any, Callable, Dict
from unittest.mock import MagicMock, patch

from django.http import HttpRequest, HttpResponse
from requests.exceptions import ConnectionError, HTTPError, Timeout

from zerver.decorator import webhook_view
from zerver.lib.test_classes import WebhookTestCase
from zerver.lib.test_helpers import HostRequestMock
from zerver.lib.users import get_api_key
from zerver.models import UserProfile
from zerver.webhooks.clickup.api_endpoints import (
    APIUnavailableCallBackError,
    BadRequestCallBackError,
    get_folder,
    get_goal,
    get_list,
    get_space,
    get_task,
    make_clickup_request,
)

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

    def test_missing_request_variable(self) -> None:
        self.url = self.build_webhook_url()
        exception_msg = "Missing 'clickup_api_key' argument"
        with self.assertRaisesRegex(AssertionError, exception_msg):
            expected_message = ":trash_can: A Goal has been deleted from your ClickUp space!"
            self.check_webhook(
                fixture_name="goal_deleted",
                expected_topic_name=EXPECTED_TOPIC,
                expected_message=expected_message,
            )

    def test_webhook_api_callback_unavailable_error(self) -> None:
        @webhook_view("ClientName")
        def my_webhook_raises_exception(
            request: HttpRequest, user_profile: UserProfile
        ) -> HttpResponse:
            raise APIUnavailableCallBackError

        request = HostRequestMock()
        request.method = "POST"
        request.host = "zulip.testserver"

        request._body = b"{}"
        request.content_type = "text/plain"
        request.POST["api_key"] = get_api_key(self.example_user("hamlet"))
        exception_msg = "ClientName integration couldn't reach an external API service; ignoring"
        with patch(
            "zerver.decorator.webhook_logger.exception"
        ) as mock_exception, self.assertRaisesRegex(APIUnavailableCallBackError, exception_msg):
            my_webhook_raises_exception(request)
        mock_exception.assert_called_once()
        self.assertIsInstance(mock_exception.call_args.args[0], APIUnavailableCallBackError)
        self.assertEqual(mock_exception.call_args.args[0].msg, exception_msg)
        self.assertEqual(
            mock_exception.call_args.kwargs, {"extra": {"request": request}, "stack_info": True}
        )

    def test_webhook_api_callback_bad_request_error(self) -> None:
        @webhook_view(webhook_client_name="ClientName")
        def my_webhook_raises_exception(
            request: HttpRequest, user_profile: UserProfile
        ) -> HttpResponse:
            raise BadRequestCallBackError("<error_code>")

        request = HostRequestMock()
        request.method = "POST"
        request.host = "zulip.testserver"

        request._body = b"{}"
        request.content_type = "text/plain"
        request.POST["api_key"] = get_api_key(self.example_user("hamlet"))
        exception_msg = (
            "ClientName integration tries to make a bad outgoing request: <error_code>; ignoring"
        )
        with patch(
            "zerver.decorator.webhook_logger.exception"
        ) as mock_exception, self.assertRaisesRegex(BadRequestCallBackError, exception_msg):
            my_webhook_raises_exception(request)
        mock_exception.assert_called_once()
        self.assertIsInstance(mock_exception.call_args.args[0], BadRequestCallBackError)
        self.assertEqual(mock_exception.call_args.args[0].msg, exception_msg)
        self.assertEqual(
            mock_exception.call_args.kwargs, {"extra": {"request": request}, "stack_info": True}
        )

    def test_verify_url_path(self) -> None:
        invalid_paths = ["oauth/token", "user", "webhook"]
        for path in invalid_paths:
            with self.assertRaises(BadRequestCallBackError):
                make_clickup_request(path, api_key="123")

    def test_clickup_request_http_error(self) -> None:
        with patch("zerver.webhooks.clickup.api_endpoints.ClickUpSession") as mock_clickup_session:
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_clickup_session.return_value.get.side_effect = HTTPError(response=mock_response)
            with self.assertRaises(BadRequestCallBackError):
                make_clickup_request("list/123123", api_key="123")
            mock_clickup_session.return_value.get.assert_called_once()

    def test_clickup_request_connection_error(self) -> None:
        with patch("zerver.webhooks.clickup.api_endpoints.ClickUpSession") as mock_clickup_session:
            mock_response = MagicMock()
            mock_clickup_session.return_value.get.side_effect = ConnectionError(
                response=mock_response
            )
            with self.assertRaises(APIUnavailableCallBackError):
                make_clickup_request("list/123123", api_key="123")
            mock_clickup_session.return_value.get.assert_called_once()

    def test_clickup_request_timeout_error(self) -> None:
        with patch("zerver.webhooks.clickup.api_endpoints.ClickUpSession") as mock_clickup_session:
            mock_response = MagicMock()
            mock_clickup_session.return_value.get.side_effect = Timeout(response=mock_response)
            with self.assertRaises(APIUnavailableCallBackError):
                make_clickup_request("list/123123", api_key="123")
            mock_clickup_session.return_value.get.assert_called_once()

    def test_clickup_api_endpoints(self) -> None:
        endpoint_map: Dict[str, Callable[[str, str], Dict[str, Any]]] = {
            "folder": get_folder,
            "list": get_list,
            "space": get_space,
            "task": get_task,
            "goal": get_goal,
        }
        for item, call_api in endpoint_map.items():
            mock_fixtures_path = f"zerver/webhooks/clickup/callback_fixtures/get_{item}.json"
            with patch(
                "zerver.webhooks.clickup.api_endpoints.ClickUpSession"
            ) as mock_clickup_session, open(mock_fixtures_path) as f:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.raise_for_status.side_effect = None
                item_fixture = json.load(f)
                mock_response.json.return_value = item_fixture
                mock_clickup_session.return_value.get.return_value = mock_response
                item_data = call_api("123", "XXXX")

                self.assertDictEqual(item_data, item_fixture)
                mock_clickup_session.return_value.get.assert_called_once()
