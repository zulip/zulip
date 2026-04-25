from zerver.lib.test_classes import ZulipTestCase
from zerver.models.messages import Task


class TasksApiUnitTest(ZulipTestCase):
    def test_list_my_tasks_assignee_query_param(self) -> None:
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        message_id = self.send_stream_message(
            iago, "Verona", topic_name="api", content="list by assignee"
        )
        Task.objects.create(
            message_id=message_id,
            assignee=hamlet,
            creator=iago,
            title="Hamlet only",
            description="",
        )
        result = self.api_get(iago, "/api/v1/users/me/tasks", {"assignee": hamlet.email})
        data = self.assert_json_success(result)
        self.assert_length(data["tasks"], 1)
        self.assertEqual(data["tasks"][0]["title"], "Hamlet only")

    def test_list_my_tasks_assignee_unknown_user(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.api_get(
            hamlet, "/api/v1/users/me/tasks", {"assignee": "not-a-real-user@zulip.com"}
        )
        self.assert_json_error(result, "User not-a-real-user@zulip.com not found")

    def test_create_task_invalid_due_date(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="due")
        result = self.api_post(
            hamlet,
            f"/api/v1/messages/{message_id}/tasks",
            {"title": "t", "description": "", "due_date": "invalid-date"},
        )
        self.assert_json_error(result, "Invalid due date format")

    def test_create_task_unknown_assignee(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="assignee bad")
        result = self.api_post(
            hamlet,
            f"/api/v1/messages/{message_id}/tasks",
            {"title": "t", "description": "", "assignee": "ghost@example.com"},
        )
        self.assert_json_error(result, "User ghost@example.com not found")

    def test_create_task_missing_title(self) -> None:
        hamlet = self.example_user("hamlet")
        message_id = self.send_stream_message(hamlet, "Verona", content="no title")
        result = self.api_post(
            hamlet,
            f"/api/v1/messages/{message_id}/tasks",
            {"title": "", "description": ""},
        )
        self.assert_json_error(result, "Missing title")

    def test_create_standalone_task_missing_title(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.api_post(hamlet, "/api/v1/tasks", {"title": "", "description": ""})
        self.assert_json_error(result, "Missing title")
